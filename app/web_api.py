from __future__ import annotations

import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

# Ensure package imports work when running `python app/web_api.py`.
_app_dir = Path(__file__).resolve().parent
_project_root = _app_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.application.library_service import LibraryService
from app.application.models import ExplorerEntry, ScanProgress, TagMiningProgress, TagMiningResult
from app.application.ports import EmbeddingModelPort, RerankerModelPort
from app.infrastructure.app_runtime_logger import JsonlAppRuntimeLogger
from app.infrastructure.embedding_model import LocalSentenceTransformerModel
from app.infrastructure.file_opener import DefaultFileOpener
from app.infrastructure.library_repository import SqliteLibraryRepository
from app.infrastructure.media_indexer import FfmpegMediaIndexer
from app.infrastructure.reranker_model import LocalBgeRerankerModel
from app.infrastructure.scan_logger import JsonlScanLogger
from app.infrastructure.scanner_gateway import CoreScannerGateway
from app.infrastructure.tag_mining_logger import JsonlTagMiningLogger
from app.infrastructure.tag_mining_thresholds import load_tag_mining_threshold_config
from app.infrastructure.tokenizer_pkuseg import PkusegTokenizer


class LibrarySelectRequest(BaseModel):
    path: str


class EntryOpenRequest(BaseModel):
    path: str


class TagCreateRequest(BaseModel):
    names: list[str]


class TagIdListRequest(BaseModel):
    ids: list[int]


class FeatureExtractionStartRequest(BaseModel):
    strategy: str = "auto"
    scope: str = "new_only"
    embedding_model: str = ""
    reranker_model: str = ""
    min_df: int = 2
    max_tags_per_video: int = 8
    max_terms: int = 400
    recall_top_k: Optional[int] = None
    recall_min_score: Optional[float] = None
    auto_apply: Optional[float] = None
    pending_review: Optional[float] = None


class FeatureModelPathRequest(BaseModel):
    path: str = ""


class FeatureModelOpenPathRequest(BaseModel):
    path: str


class ApiError(BaseModel):
    code: str
    message: str


def ok(data: Any) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data, "error": None})


def fail(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"ok": False, "data": None, "error": {"code": code, "message": message}},
        status_code=status,
    )


class CancelledError(Exception):
    pass


@dataclass
class ScanState:
    status: str = "idle"
    label: str = "Idle"
    percent: str = "0%"
    current: int = 0
    total: int = 0
    rel_path: str = ""


@dataclass
class FeatureTaskState:
    status: str = "idle"
    phase: str = "idle"
    message: str = "Idle"
    progress_percent: int = 0
    current: int = 0
    total: int = 0
    rel_path: str = ""
    started_epoch: int = 0
    updated_epoch: int = 0
    strategy: str = "auto"
    scope: str = "new_only"
    embedding_model: str = ""
    reranker_model: str = ""
    min_df: int = 2
    max_tags_per_video: int = 8
    max_terms: int = 400
    recall_top_k: Optional[int] = None
    recall_min_score: Optional[float] = None
    auto_apply: Optional[float] = None
    pending_review: Optional[float] = None
    result: Optional[dict[str, Any]] = None
    fallback_reason: str = ""
    dependency_status: str = "unknown"
    dependency_message: str = ""


class ApiRuntime:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.progress = ScanState()
        self.feature_lock = threading.Lock()
        self.feature_cancel = threading.Event()
        self.feature_thread: Optional[threading.Thread] = None
        self.feature_task = FeatureTaskState()
        self.feature_model_root = (_project_root / "tools" / "models").resolve()
        self.feature_imported_paths: set[str] = set()


def build_service() -> LibraryService:
    scan_logger = JsonlScanLogger()
    tag_logger = JsonlTagMiningLogger()
    runtime_logger = JsonlAppRuntimeLogger()
    embedding_model = LocalSentenceTransformerModel()
    reranker_model = LocalBgeRerankerModel()
    tokenizer = PkusegTokenizer()
    service = LibraryService(
        repository=SqliteLibraryRepository(),
        scanner=CoreScannerGateway(),
        media_indexer=FfmpegMediaIndexer(logger=scan_logger),
        opener=DefaultFileOpener(),
        scan_logger=scan_logger,
        tag_mining_logger=tag_logger,
        runtime_logger=runtime_logger,
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        tokenizer=tokenizer,
    )
    return service


app = FastAPI(title="Portable Video Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

runtime = ApiRuntime()
service = build_service()

REQUIRED_TAG_ROUTES = (
    "/api/tags/library",
    "/api/tags/library/create",
    "/api/tags/library/delete",
    "/api/tags/candidates",
    "/api/tags/candidates/approve",
    "/api/tags/candidates/reject",
    "/api/tags/candidates/blacklist",
    "/api/tags/candidates/requeue",
    "/api/tags/candidates/clear-pending",
    "/api/tags/blacklist",
)

LOG_SOURCES = ("scan", "tag_mining", "app_runtime")

FEATURE_MODEL_TYPES = ("embedding", "reranker")

EMBEDDING_PRESETS: dict[str, str] = {
    "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
    "bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
    "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
}

RERANKER_PRESETS: dict[str, str] = {
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "bge-reranker-large": "BAAI/bge-reranker-large",
}


def _auto_select_library() -> None:
    env_root = os.environ.get("PVM_LIBRARY_ROOT", "").strip()
    if not env_root:
        env_root = os.environ.get("PVM_LIBRARY_PATH", "").strip()
    if not env_root:
        return
    root = Path(env_root).expanduser()
    if not root.exists() or not root.is_dir():
        print(f"[web_api] Invalid PVM_LIBRARY_ROOT: {root}", file=sys.stderr)
        return
    try:
        service.select_library(root)
        print(f"[web_api] Auto-selected library: {root}")
    except Exception as exc:
        print(f"[web_api] Failed to auto-select library: {exc}", file=sys.stderr)


_auto_select_library()


def _format_duration(duration_ms: int) -> str:
    if duration_ms <= 0:
        return "--"
    sec = int(duration_ms / 1000)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.2f} {units[idx]}"


def _format_date(epoch: int) -> str:
    if epoch <= 0:
        return ""
    return time.strftime("%Y-%m-%d", time.localtime(epoch))


def _resolution_label(width: int, height: int) -> str:
    if height >= 2160 or width >= 3840:
        return "4K"
    if height >= 1440:
        return "1440P"
    if height >= 1080:
        return "1080P"
    if height >= 720:
        return "720P"
    if height > 0:
        return f"{height}P"
    return "--"


def _status_label(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in {"missing"}:
        return "Missing"
    if value in {"normal", "ok", "indexed"}:
        return "Indexed"
    return "Indexed"


def _scan_progress_label(progress: ScanProgress) -> str:
    phase_labels = {
        "scan_start": "Scanning file list...",
        "db_apply_scan": "Updating library index...",
        "media_prepare": "Preparing media analysis...",
        "media_probe": "Reading media metadata...",
        "thumbnail": "Generating thumbnails...",
        "db_apply_media": "Saving metadata...",
        "media_skip": "No media updates required.",
        "scan_done": "Scan completed.",
        "scan_error": "Scan failed.",
    }
    message = phase_labels.get(progress.phase, "").strip()
    if message:
        return message
    return "Scanning..."


def _entry_to_video(entry: ExplorerEntry) -> dict[str, Any]:
    rel_path = entry.rel_path
    parent = "/".join(rel_path.split("/")[:-1])
    parent = f"/{parent}" if parent else "/"
    file_path = f"/{rel_path}"
    detail = f"Format: {entry.ext.upper() or '--'} | Resolution: {_resolution_label(entry.width, entry.height)}"
    thumb_url = (
        f"/api/thumbnails?path={entry.thumb_rel_path}"
        if entry.thumb_rel_path
        else None
    )
    return {
        "id": rel_path,
        "name": entry.name,
        "path": parent,
        "filePath": file_path,
        "duration": _format_duration(entry.duration_ms),
        "resolution": _resolution_label(entry.width, entry.height),
        "size": _format_size(entry.size_bytes),
        "modified": _format_date(entry.mtime_epoch),
        "status": _status_label(entry.status),
        "tags": entry.tags,
        "detail": detail,
        "thumbUrl": thumb_url,
    }


def _build_dir_nodes(rel_dir: str, depth: int) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for name in service.list_subdirectories(rel_dir):
        child_rel = name if not rel_dir else f"{rel_dir}/{name}"
        has_children = bool(service.list_subdirectories(child_rel))
        children = _build_dir_nodes(child_rel, depth - 1) if depth > 1 else []
        node = {
            "id": child_rel,
            "name": name,
            "path": f"/{child_rel}",
            "hasChildren": has_children,
            "children": children if children else None,
        }
        nodes.append(node)
    return nodes


def _build_recursive_entries(rel_dir: str) -> list[ExplorerEntry]:
    if rel_dir == "":
        return service.list_all_video_entries()
    prefix = f"{rel_dir}/"
    return [
        entry
        for entry in service.list_all_video_entries()
        if entry.rel_path.startswith(prefix)
    ]


def _validate_and_select_library(path: Path) -> JSONResponse | None:
    if not path.exists() or not path.is_dir():
        return fail("INVALID_PATH", "Path does not exist or is not a directory.")
    service.select_library(path)
    return None


def _pick_directory(title: str = "Select Media Library") -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=title)
    finally:
        root.destroy()
    return str(selected or "")


def _ensure_library_selected() -> JSONResponse | None:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    return None


def _clean_tag_names(names: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for raw_name in list(names or []):
        name = str(raw_name or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _clean_tag_ids(ids: list[int]) -> list[int]:
    return sorted({int(value) for value in list(ids or []) if int(value) > 0})


def _parse_candidate_statuses(statuses: str) -> tuple[list[str] | None, str | None]:
    raw = str(statuses or "").strip()
    if not raw:
        return None, None

    allowed = {"pending", "approved", "blacklisted", "mapped"}
    parsed = sorted({part.strip().lower() for part in raw.split(",") if part.strip()})
    for part in parsed:
        if part not in allowed:
            return None, f"Unsupported candidate status: {part}"
    return parsed, None


def _parse_log_source(source: str) -> tuple[str | None, str | None]:
    value = str(source or "").strip().lower()
    if value in LOG_SOURCES:
        return value, None
    return None, f"Unsupported log source: {source}"


def _to_log_file_meta(log_path: Path, source: str) -> dict[str, Any]:
    stat = log_path.stat()
    return {
        "log_id": log_path.name,
        "file_name": log_path.name,
        "source": source,
        "mtime_epoch": int(stat.st_mtime),
        "size_bytes": int(stat.st_size),
    }


def _collect_runtime_info() -> dict[str, Any]:
    route_paths = sorted(
        {
            str(getattr(route, "path", ""))
            for route in app.routes
            if str(getattr(route, "path", "")).strip()
        }
    )
    missing_routes = [
        route
        for route in REQUIRED_TAG_ROUTES
        if route not in route_paths
    ]
    return {
        "app_title": app.title,
        "app_version": app.version,
        "python_executable": sys.executable,
        "cwd": str(Path.cwd()),
        "api_file": str(Path(__file__).resolve()),
        "route_count": len(route_paths),
        "has_tag_routes": len(missing_routes) == 0,
        "required_tag_routes": list(REQUIRED_TAG_ROUTES),
        "missing_tag_routes": missing_routes,
    }


def _looks_like_embedding_model_dir(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    markers = ("config.json", "modules.json", "tokenizer_config.json")
    return all((path / marker).exists() for marker in markers)


def _looks_like_reranker_model_dir(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    base_markers = ("config.json", "tokenizer_config.json")
    if not all((path / marker).exists() for marker in base_markers):
        return False
    weight_markers = ("pytorch_model.bin", "model.safetensors")
    return any((path / marker).exists() for marker in weight_markers)


def _safe_model_name(raw: str) -> str:
    normalized = re.sub(r"\s+", " ", str(raw or "").strip())
    return normalized or "model"


def _normalize_model_hint(raw: str) -> str:
    hint = str(raw or "").strip()
    if not hint:
        return ""
    as_path = Path(hint).expanduser()
    if as_path.is_absolute():
        return str(as_path.resolve()).lower()
    candidate = (runtime.feature_model_root / hint).expanduser()
    if candidate.exists() and candidate.is_dir():
        return str(candidate.resolve()).lower()
    return hint.lower()


def _resolve_model_hint(raw: str) -> str:
    hint = str(raw or "").strip()
    if not hint:
        return ""
    as_path = Path(hint).expanduser()
    if as_path.exists() and as_path.is_dir():
        return str(as_path.resolve())
    candidate = (runtime.feature_model_root / hint).expanduser()
    if candidate.exists() and candidate.is_dir():
        return str(candidate.resolve())
    return hint


def _build_feature_model_items() -> list[dict[str, Any]]:
    root = runtime.feature_model_root
    selected_embedding = _normalize_model_hint(runtime.feature_task.embedding_model)
    selected_reranker = _normalize_model_hint(runtime.feature_task.reranker_model)
    items: list[dict[str, Any]] = []

    def append_item(
        *,
        model_type: str,
        name: str,
        source: str,
        repo_id: str,
        downloaded: bool,
        local_path: Path | None,
    ) -> None:
        model_name = _safe_model_name(name)
        resolved_path = str(local_path.resolve()) if (local_path and local_path.exists()) else ""
        select_value = resolved_path or model_name
        normalized_select = _normalize_model_hint(select_value)
        selected_hint = selected_embedding if model_type == "embedding" else selected_reranker
        items.append(
            {
                "id": f"{model_type}:{model_name}",
                "type": model_type,
                "name": model_name,
                "source": source,
                "downloaded": downloaded,
                "download_status": "downloaded" if downloaded else "missing",
                "local_path": resolved_path,
                "download_url": f"https://huggingface.co/{repo_id}" if repo_id else "",
                "repo_id": repo_id,
                "select_value": select_value,
                "selected": bool(selected_hint) and selected_hint == normalized_select,
            }
        )

    for key, repo_id in EMBEDDING_PRESETS.items():
        local_path = (root / key).resolve()
        append_item(
            model_type="embedding",
            name=key,
            source="preset",
            repo_id=repo_id,
            downloaded=_looks_like_embedding_model_dir(local_path),
            local_path=local_path,
        )

    for key, repo_id in RERANKER_PRESETS.items():
        local_path = (root / key).resolve()
        append_item(
            model_type="reranker",
            name=key,
            source="preset",
            repo_id=repo_id,
            downloaded=_looks_like_reranker_model_dir(local_path),
            local_path=local_path,
        )

    preset_names = set(EMBEDDING_PRESETS.keys()) | set(RERANKER_PRESETS.keys())
    custom_paths: set[Path] = set()
    if root.exists() and root.is_dir():
        for child in root.iterdir():
            if not child.is_dir() or child.name in preset_names:
                continue
            custom_paths.add(child.resolve())
    for raw_path in runtime.feature_imported_paths:
        candidate = Path(raw_path).expanduser()
        if candidate.exists() and candidate.is_dir():
            custom_paths.add(candidate.resolve())

    for custom_path in sorted(custom_paths, key=lambda p: str(p).lower()):
        if _looks_like_embedding_model_dir(custom_path):
            append_item(
                model_type="embedding",
                name=custom_path.name,
                source="custom",
                repo_id="",
                downloaded=True,
                local_path=custom_path,
            )
        if _looks_like_reranker_model_dir(custom_path):
            append_item(
                model_type="reranker",
                name=custom_path.name,
                source="custom",
                repo_id="",
                downloaded=True,
                local_path=custom_path,
            )

    return items


def _feature_threshold_payload() -> dict[str, Any]:
    config = load_tag_mining_threshold_config(service.library_root())
    return {
        "source_path": config.source_path,
        "warning": config.warning,
        "recall_top_k": int(config.recall_top_k),
        "recall_min_score": float(config.recall_min_score),
        "auto_apply": float(config.defaults.auto_apply),
        "pending_review": float(config.defaults.pending_review),
    }


def _read_latest_dependency_event() -> dict[str, Any] | None:
    latest = service.latest_log("tag_mining")
    if latest is None:
        return None
    rows = service.read_tag_mining_log(latest)
    for row in reversed(rows):
        if str(row.get("event") or "").strip().lower() != "dependency_loaded":
            continue
        return {
            "status": str(row.get("status") or "").strip().lower(),
            "reason": str(row.get("reason") or "").strip(),
            "strategy_used": str(row.get("strategy_used") or "").strip(),
            "ts_epoch": int(row.get("ts_epoch") or 0),
            "log_id": latest.name,
        }
    return None


def _feature_task_payload() -> dict[str, Any]:
    with runtime.feature_lock:
        task = runtime.feature_task
        payload = {
            "status": task.status,
            "phase": task.phase,
            "message": task.message,
            "progress_percent": int(task.progress_percent),
            "current": int(task.current),
            "total": int(task.total),
            "rel_path": task.rel_path,
            "started_epoch": int(task.started_epoch),
            "updated_epoch": int(task.updated_epoch),
            "strategy": task.strategy,
            "scope": task.scope,
            "embedding_model": task.embedding_model,
            "reranker_model": task.reranker_model,
            "min_df": int(task.min_df),
            "max_tags_per_video": int(task.max_tags_per_video),
            "max_terms": int(task.max_terms),
            "recall_top_k": task.recall_top_k,
            "recall_min_score": task.recall_min_score,
            "auto_apply": task.auto_apply,
            "pending_review": task.pending_review,
            "fallback_reason": task.fallback_reason,
            "dependency_status": task.dependency_status,
            "dependency_message": task.dependency_message,
            "result": task.result or {},
            "running_lock_model_switch": task.status in {"running", "stopping"},
            "background_run_supported": True,
        }

    latest_dependency = _read_latest_dependency_event()
    if latest_dependency is not None:
        if not payload["dependency_status"] or payload["dependency_status"] == "unknown":
            payload["dependency_status"] = latest_dependency.get("status") or "unknown"
        if not payload["dependency_message"]:
            payload["dependency_message"] = latest_dependency.get("reason") or ""
        payload["dependency_log"] = latest_dependency

    return payload


def _task_progress_percent(progress: TagMiningProgress) -> int:
    if progress.total > 0:
        return int(max(0, min(100, (progress.current / progress.total) * 100)))
    if progress.phase in {"tag_done"}:
        return 100
    return 0


def _resolve_threshold_defaults(
    payload: FeatureExtractionStartRequest,
) -> dict[str, Optional[float | int]]:
    defaults = _feature_threshold_payload()
    return {
        "recall_top_k": int(payload.recall_top_k) if payload.recall_top_k is not None else int(defaults["recall_top_k"]),
        "recall_min_score": (
            float(payload.recall_min_score)
            if payload.recall_min_score is not None
            else float(defaults["recall_min_score"])
        ),
        "auto_apply": float(payload.auto_apply) if payload.auto_apply is not None else float(defaults["auto_apply"]),
        "pending_review": (
            float(payload.pending_review)
            if payload.pending_review is not None
            else float(defaults["pending_review"])
        ),
    }


@app.post("/api/library/select")
def select_library(payload: LibrarySelectRequest) -> JSONResponse:
    path = Path(payload.path).expanduser()
    maybe_error = _validate_and_select_library(path)
    if maybe_error is not None:
        return maybe_error
    return ok({"name": service.library_name(), "root": str(path)})


@app.post("/api/library/pick")
def pick_library() -> JSONResponse:
    try:
        selected_path = _pick_directory()
    except Exception as exc:
        return fail("PICKER_UNAVAILABLE", str(exc), status=500)

    if not selected_path:
        return fail("CANCELLED", "No folder selected.")

    path = Path(selected_path).expanduser()
    maybe_error = _validate_and_select_library(path)
    if maybe_error is not None:
        return maybe_error
    return ok({"name": service.library_name(), "root": str(path)})


@app.get("/api/library/current")
def current_library() -> JSONResponse:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    root = service.library_root()
    if root is None:
        return fail("NO_LIBRARY", "No library selected.")
    return ok({"name": service.library_name(), "root": str(root)})


@app.get("/api/runtime/info")
def runtime_info() -> JSONResponse:
    return ok(_collect_runtime_info())


@app.get("/api/directories")
def list_directories(
    path: str = Query("", description="Relative path"),
    depth: int = Query(8, ge=1, le=20),
) -> JSONResponse:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    rel_dir = path.strip().lstrip("/")
    if rel_dir and not service.directory_exists(rel_dir):
        return fail("INVALID_PATH", "Directory does not exist.")
    nodes = _build_dir_nodes(rel_dir, depth)
    return ok(nodes)


@app.get("/api/entries")
def list_entries(
    path: str = Query("", description="Relative path"),
    recursive: bool = Query(False, description="Include subtree entries"),
) -> JSONResponse:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    rel_dir = path.strip().lstrip("/")
    if rel_dir and not service.directory_exists(rel_dir):
        return fail("INVALID_PATH", "Directory does not exist.")
    if recursive:
        entries = _build_recursive_entries(rel_dir)
    else:
        entries = [entry for entry in service.list_entries(rel_dir) if not entry.is_dir]
    items = [_entry_to_video(entry) for entry in entries]
    return ok({"items": items, "total": len(items)})


@app.post("/api/entries/open")
def open_entry(payload: EntryOpenRequest) -> JSONResponse:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    rel_path = str(payload.path or "").strip().lstrip("/")
    if not rel_path:
        return fail("INVALID_PATH", "Path is required.")
    try:
        service.open_entry(rel_path)
    except FileNotFoundError:
        return fail("NOT_FOUND", "File not found.", status=404)
    except Exception as exc:
        return fail("OPEN_FAILED", str(exc), status=500)
    return ok({"status": "opened", "path": f"/{rel_path}"})


@app.get("/api/search")
def search_entries(q: str = Query("", min_length=1)) -> JSONResponse:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    entries = service.search_video_entries(query=q)
    items = [_entry_to_video(entry) for entry in entries]
    return ok({"items": items, "total": len(items)})


@app.get("/api/tags/library")
def list_tag_library() -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    items = service.list_tag_library()
    return ok({"items": items, "total": len(items)})


@app.post("/api/tags/library/create")
def create_tag_library(payload: TagCreateRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    names = _clean_tag_names(payload.names)
    if not names:
        return fail("INVALID_PAYLOAD", "At least one tag name is required.")

    created = service.create_tags(names)
    return ok({"created": int(created)})


@app.post("/api/tags/library/delete")
def delete_tag_library(payload: TagIdListRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    tag_ids = _clean_tag_ids(payload.ids)
    if not tag_ids:
        return fail("INVALID_PAYLOAD", "At least one tag id is required.")

    removed = service.delete_tags_by_ids(tag_ids)
    return ok({"removed": int(removed)})


@app.get("/api/tags/candidates")
def list_tag_candidates(
    statuses: str = Query("", description="Comma-separated statuses"),
) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    parsed_statuses, status_error = _parse_candidate_statuses(statuses)
    if status_error:
        return fail("INVALID_QUERY", status_error)

    items = service.list_tag_candidates(statuses=parsed_statuses)
    return ok({"items": items, "total": len(items)})


@app.post("/api/tags/candidates/approve")
def approve_tag_candidates(payload: TagIdListRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    candidate_ids = _clean_tag_ids(payload.ids)
    if not candidate_ids:
        return fail("INVALID_PAYLOAD", "At least one candidate id is required.")

    before_total = len(service.list_tag_library())
    result = service.approve_tag_candidates(candidate_ids)
    after_total = len(service.list_tag_library())

    approved_candidates = int(result.get("approved_candidates") or 0)
    linked_relations = int(result.get("applied_relations") or result.get("linked_relations") or 0)
    created_tags = max(0, after_total - before_total)

    return ok({
        "approved_candidates": approved_candidates,
        "created_tags": created_tags,
        "linked_relations": linked_relations,
    })


@app.post("/api/tags/candidates/reject")
def reject_tag_candidates(payload: TagIdListRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    candidate_ids = _clean_tag_ids(payload.ids)
    if not candidate_ids:
        return fail("INVALID_PAYLOAD", "At least one candidate id is required.")

    rejected = service.reject_tag_candidates(candidate_ids)
    return ok({"rejected": int(rejected)})


@app.post("/api/tags/candidates/blacklist")
def blacklist_tag_candidates(payload: TagIdListRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    candidate_ids = _clean_tag_ids(payload.ids)
    if not candidate_ids:
        return fail("INVALID_PAYLOAD", "At least one candidate id is required.")

    result = service.blacklist_tag_candidates(candidate_ids)
    return ok({
        "blacklisted_candidates": int(result.get("blacklisted_candidates") or 0),
        "blacklist_terms_added": int(result.get("blacklist_terms_added") or 0),
    })


@app.post("/api/tags/candidates/requeue")
def requeue_tag_candidates(payload: TagIdListRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    candidate_ids = _clean_tag_ids(payload.ids)
    if not candidate_ids:
        return fail("INVALID_PAYLOAD", "At least one candidate id is required.")

    requeued = service.requeue_tag_candidates(candidate_ids)
    return ok({"requeued": int(requeued)})


@app.post("/api/tags/candidates/clear-pending")
def clear_pending_tag_candidates() -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    removed = service.clear_pending_tag_candidates()
    return ok({"removed": int(removed)})


@app.get("/api/tags/blacklist")
def list_tag_blacklist() -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    items = service.list_tag_blacklist()
    return ok({"items": items, "total": len(items)})


@app.get("/api/logs/sources")
def list_log_sources() -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error
    return ok(
        {
            "items": [
                {"source": "scan", "label": "扫描日志"},
                {"source": "tag_mining", "label": "标签提取日志"},
                {"source": "app_runtime", "label": "项目运行日志"},
            ],
            "default_source": "app_runtime",
        }
    )


@app.get("/api/logs/files")
def list_log_files(
    source: str = Query("app_runtime", description="scan|tag_mining|app_runtime"),
    limit: int = Query(30, ge=1, le=2000),
) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    source_key, source_error = _parse_log_source(source)
    if source_error:
        return fail("INVALID_QUERY", source_error)

    files = service.list_logs(source=source_key, limit=limit)
    items = [_to_log_file_meta(path, source_key) for path in files]
    return ok({"source": source_key, "items": items, "total": len(items)})


@app.get("/api/logs/latest")
def latest_log_file(source: str = Query("app_runtime", description="scan|tag_mining|app_runtime")) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    source_key, source_error = _parse_log_source(source)
    if source_error:
        return fail("INVALID_QUERY", source_error)

    latest = service.latest_log(source_key)
    item = _to_log_file_meta(latest, source_key) if latest is not None else None
    return ok({"source": source_key, "item": item})


@app.get("/api/logs/events")
def list_log_events(
    source: str = Query("app_runtime", description="scan|tag_mining|app_runtime"),
    log_id: str = Query("", description="Log filename"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    level: str = Query("", description="info|error"),
    event: str = Query("", description="Exact event name"),
    q: str = Query("", description="Keyword search"),
    from_ts: Optional[int] = Query(None, description="Inclusive epoch lower bound"),
    to_ts: Optional[int] = Query(None, description="Inclusive epoch upper bound"),
) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    source_key, source_error = _parse_log_source(source)
    if source_error:
        return fail("INVALID_QUERY", source_error)
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        return fail("INVALID_QUERY", "from_ts must be <= to_ts")

    try:
        data = service.read_log_events(
            source=source_key,
            log_id=log_id,
            page=page,
            page_size=page_size,
            level=level,
            event=event,
            q=q,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except ValueError as exc:
        return fail("INVALID_QUERY", str(exc))
    except FileNotFoundError:
        return fail("LOG_NOT_FOUND", "Requested log file was not found.", status=404)

    return ok(data)


@app.get("/api/logs/analysis")
def analyze_log_events(
    source: str = Query("app_runtime", description="scan|tag_mining|app_runtime"),
    log_id: str = Query("", description="Log filename"),
    level: str = Query("", description="info|error"),
    event: str = Query("", description="Exact event name"),
    q: str = Query("", description="Keyword search"),
    from_ts: Optional[int] = Query(None, description="Inclusive epoch lower bound"),
    to_ts: Optional[int] = Query(None, description="Inclusive epoch upper bound"),
) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    source_key, source_error = _parse_log_source(source)
    if source_error:
        return fail("INVALID_QUERY", source_error)
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        return fail("INVALID_QUERY", "from_ts must be <= to_ts")

    try:
        data = service.analyze_log_events(
            source=source_key,
            log_id=log_id,
            level=level,
            event=event,
            q=q,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except ValueError as exc:
        return fail("INVALID_QUERY", str(exc))
    except FileNotFoundError:
        return fail("LOG_NOT_FOUND", "Requested log file was not found.", status=404)

    return ok(data)


def _build_feature_embedding_model(hint: str) -> Optional[EmbeddingModelPort]:
    model_hint = _resolve_model_hint(hint)
    if not model_hint:
        return None
    return LocalSentenceTransformerModel(model_hint=model_hint)


def _build_feature_reranker_model(hint: str) -> Optional[RerankerModelPort]:
    model_hint = _resolve_model_hint(hint)
    if not model_hint:
        return None
    return LocalBgeRerankerModel(model_hint=model_hint)


def _feature_extraction_worker() -> None:
    with runtime.feature_lock:
        task = runtime.feature_task
        strategy = task.strategy
        scope = task.scope
        embedding_hint = task.embedding_model
        reranker_hint = task.reranker_model
        min_df = int(task.min_df)
        max_tags_per_video = int(task.max_tags_per_video)
        max_terms = int(task.max_terms)
        recall_top_k = int(task.recall_top_k) if task.recall_top_k is not None else None
        recall_min_score = (
            float(task.recall_min_score) if task.recall_min_score is not None else None
        )
        auto_apply = float(task.auto_apply) if task.auto_apply is not None else None
        pending_review = (
            float(task.pending_review) if task.pending_review is not None else None
        )

    def _should_stop() -> bool:
        return runtime.feature_cancel.is_set()

    def _on_progress(progress: TagMiningProgress) -> None:
        with runtime.feature_lock:
            runtime.feature_task.phase = progress.phase
            runtime.feature_task.message = progress.message
            runtime.feature_task.current = int(progress.current)
            runtime.feature_task.total = int(progress.total)
            runtime.feature_task.rel_path = progress.rel_path
            runtime.feature_task.progress_percent = _task_progress_percent(progress)
            runtime.feature_task.updated_epoch = int(time.time())
            if runtime.feature_task.status not in {"running", "stopping"}:
                runtime.feature_task.status = "running"

    embedding_model = _build_feature_embedding_model(embedding_hint)
    reranker_model = _build_feature_reranker_model(reranker_hint)

    try:
        result = service.mine_title_tags(
            progress=_on_progress,
            min_df=min_df,
            max_tags_per_video=max_tags_per_video,
            max_terms=max_terms,
            recall_top_k=recall_top_k,
            recall_min_score=recall_min_score,
            auto_apply=auto_apply,
            pending_review=pending_review,
            embedding_model=embedding_model,
            reranker_model=reranker_model,
            should_stop=_should_stop,
            strategy=strategy,
            scope=scope,
        )
        final_status = "cancelled" if result.status == "cancelled" else "completed"
        dependency_status = "normal"
        dependency_message = ""
        if result.fallback_reason:
            dependency_status = "degraded"
            dependency_message = result.fallback_reason

        with runtime.feature_lock:
            runtime.feature_task.status = final_status
            runtime.feature_task.phase = "tag_done" if final_status == "completed" else "tag_cancelled"
            runtime.feature_task.message = (
                "标签提取完成" if final_status == "completed" else "标签提取已取消"
            )
            runtime.feature_task.progress_percent = (
                100 if final_status == "completed" else runtime.feature_task.progress_percent
            )
            runtime.feature_task.updated_epoch = int(time.time())
            runtime.feature_task.fallback_reason = result.fallback_reason
            runtime.feature_task.dependency_status = dependency_status
            runtime.feature_task.dependency_message = dependency_message
            runtime.feature_task.result = _feature_result_payload(result)
    except Exception as exc:
        with runtime.feature_lock:
            runtime.feature_task.status = "failed"
            runtime.feature_task.phase = "tag_error"
            runtime.feature_task.message = f"标签提取失败: {exc}"
            runtime.feature_task.updated_epoch = int(time.time())
            runtime.feature_task.result = {
                "status": "failed",
                "error": str(exc),
            }
    finally:
        runtime.feature_cancel.clear()


def _feature_result_payload(result: TagMiningResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "processed_videos": int(result.processed_videos),
        "selected_terms": int(result.selected_terms),
        "tagged_videos": int(result.tagged_videos),
        "created_relations": int(result.created_relations),
        "pending_candidate_terms": int(result.pending_candidate_terms),
        "pending_candidate_hits": int(result.pending_candidate_hits),
        "semantic_auto_hits": int(result.semantic_auto_hits),
        "semantic_pending_hits": int(result.semantic_pending_hits),
        "semantic_rejected_hits": int(result.semantic_rejected_hits),
        "elapsed_ms": int(result.elapsed_ms),
        "strategy_requested": result.strategy_requested,
        "strategy_used": result.strategy_used,
        "model_name": result.model_name,
        "reranker_name": result.reranker_name,
        "fallback_reason": result.fallback_reason,
        "scope": result.scope,
        "threshold_config_path": result.threshold_config_path,
        "top_terms": list(result.top_terms or []),
    }


def _feature_model_payload() -> dict[str, Any]:
    items = _build_feature_model_items()
    embedding_options = [
        item for item in items if item["type"] == "embedding" and item["downloaded"]
    ]
    reranker_options = [
        item for item in items if item["type"] == "reranker" and item["downloaded"]
    ]
    return {
        "model_root": str(runtime.feature_model_root),
        "items": items,
        "embedding_options": embedding_options,
        "reranker_options": reranker_options,
    }


@app.get("/api/feature-extraction/status")
def feature_extraction_status() -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error
    return ok(_feature_task_payload())


@app.get("/api/feature-extraction/thresholds")
def feature_extraction_thresholds() -> JSONResponse:
    return ok(_feature_threshold_payload())


@app.get("/api/feature-extraction/models")
def feature_extraction_models() -> JSONResponse:
    return ok(_feature_model_payload())


@app.post("/api/feature-extraction/models/select-root")
def feature_select_model_root(payload: FeatureModelPathRequest) -> JSONResponse:
    path_raw = str(payload.path or "").strip()
    selected = path_raw
    if not selected:
        try:
            selected = _pick_directory(title="Select Feature Model Directory")
        except Exception as exc:
            return fail("PICKER_UNAVAILABLE", str(exc), status=500)
        if not selected:
            return fail("CANCELLED", "No folder selected.")

    path = Path(selected).expanduser()
    if not path.exists() or not path.is_dir():
        return fail("INVALID_PATH", "Model root path does not exist or is not a directory.")

    runtime.feature_model_root = path.resolve()
    return ok(_feature_model_payload())


@app.post("/api/feature-extraction/models/import-directory")
def feature_import_model_directory(payload: FeatureModelPathRequest) -> JSONResponse:
    path_raw = str(payload.path or "").strip()
    selected = path_raw
    if not selected:
        try:
            selected = _pick_directory(title="Import Model Directory")
        except Exception as exc:
            return fail("PICKER_UNAVAILABLE", str(exc), status=500)
        if not selected:
            return fail("CANCELLED", "No folder selected.")

    path = Path(selected).expanduser()
    if not path.exists() or not path.is_dir():
        return fail("INVALID_PATH", "Import path does not exist or is not a directory.")
    if not _looks_like_embedding_model_dir(path) and not _looks_like_reranker_model_dir(path):
        return fail("INVALID_MODEL_DIR", "Directory does not look like a supported local model.")

    runtime.feature_imported_paths.add(str(path.resolve()))
    return ok(
        {
            "imported_path": str(path.resolve()),
            **_feature_model_payload(),
        }
    )


@app.post("/api/feature-extraction/models/open-path")
def feature_open_model_path(payload: FeatureModelOpenPathRequest) -> JSONResponse:
    path = Path(str(payload.path or "")).expanduser()
    if not path.exists():
        return fail("NOT_FOUND", "Path not found.", status=404)
    try:
        DefaultFileOpener().open_file(path)
    except Exception as exc:
        return fail("OPEN_FAILED", str(exc), status=500)
    return ok({"status": "opened", "path": str(path.resolve())})


@app.post("/api/feature-extraction/start")
def start_feature_extraction(payload: FeatureExtractionStartRequest) -> JSONResponse:
    maybe_error = _ensure_library_selected()
    if maybe_error is not None:
        return maybe_error

    with runtime.feature_lock:
        if runtime.feature_thread and runtime.feature_thread.is_alive():
            return fail("TASK_RUNNING", "Feature extraction task is already running.", status=409)

        strategy = str(payload.strategy or "auto").strip().lower() or "auto"
        scope = str(payload.scope or "new_only").strip().lower() or "new_only"
        if strategy not in {"auto", "rule", "model"}:
            return fail("INVALID_PAYLOAD", "strategy must be one of auto/rule/model.")
        if scope not in {"all", "new_only"}:
            return fail("INVALID_PAYLOAD", "scope must be one of all/new_only.")

        resolved_thresholds = _resolve_threshold_defaults(payload)
        runtime.feature_task = FeatureTaskState(
            status="running",
            phase="model_loading",
            message="正在检查模型与依赖...",
            progress_percent=0,
            current=0,
            total=0,
            rel_path="",
            started_epoch=int(time.time()),
            updated_epoch=int(time.time()),
            strategy=strategy,
            scope=scope,
            embedding_model=_resolve_model_hint(payload.embedding_model),
            reranker_model=_resolve_model_hint(payload.reranker_model),
            min_df=max(1, int(payload.min_df)),
            max_tags_per_video=max(1, int(payload.max_tags_per_video)),
            max_terms=max(1, int(payload.max_terms)),
            recall_top_k=int(resolved_thresholds["recall_top_k"]) if resolved_thresholds["recall_top_k"] is not None else None,
            recall_min_score=(
                float(resolved_thresholds["recall_min_score"])
                if resolved_thresholds["recall_min_score"] is not None
                else None
            ),
            auto_apply=float(resolved_thresholds["auto_apply"]) if resolved_thresholds["auto_apply"] is not None else None,
            pending_review=(
                float(resolved_thresholds["pending_review"])
                if resolved_thresholds["pending_review"] is not None
                else None
            ),
            result={},
            fallback_reason="",
            dependency_status="unknown",
            dependency_message="",
        )

    runtime.feature_cancel.clear()
    thread = threading.Thread(target=_feature_extraction_worker, daemon=True)
    runtime.feature_thread = thread
    thread.start()
    return ok({"status": "started", "task": _feature_task_payload()})


@app.post("/api/feature-extraction/stop")
def stop_feature_extraction() -> JSONResponse:
    with runtime.feature_lock:
        if not runtime.feature_thread or not runtime.feature_thread.is_alive():
            return fail("TASK_NOT_RUNNING", "Feature extraction task is not running.", status=409)
        runtime.feature_task.status = "stopping"
        runtime.feature_task.message = "正在请求停止..."
        runtime.feature_task.updated_epoch = int(time.time())
    runtime.feature_cancel.set()
    return ok({"status": "stop_requested"})


@app.get("/api/scan/progress")
def scan_progress() -> JSONResponse:
    with runtime.lock:
        data = {
            "label": runtime.progress.label,
            "percent": runtime.progress.percent,
            "current": runtime.progress.current,
            "total": runtime.progress.total,
            "state": runtime.progress.status,
            "rel_path": runtime.progress.rel_path,
        }
    return ok(data)


def _scan_worker() -> None:
    with runtime.lock:
        runtime.progress = ScanState(status="running", label="Preparing scan...", percent="0%")

    def _on_progress(progress: ScanProgress) -> None:
        if runtime.cancel.is_set():
            raise CancelledError("scan cancelled")
        with runtime.lock:
            runtime.progress.label = _scan_progress_label(progress)
            runtime.progress.current = progress.current
            runtime.progress.total = progress.total
            runtime.progress.rel_path = progress.rel_path
            runtime.progress.status = "running"
            if progress.total > 0:
                pct = int(min(100, (progress.current / progress.total) * 100))
                runtime.progress.percent = f"{pct}%"

    try:
        service.scan(progress=_on_progress)
        with runtime.lock:
            runtime.progress.status = "done"
            runtime.progress.percent = "100%"
    except CancelledError:
        with runtime.lock:
            runtime.progress.status = "cancelled"
            runtime.progress.label = "Scan cancelled"
    except Exception as exc:
        with runtime.lock:
            runtime.progress.status = "error"
            runtime.progress.label = f"Scan failed: {exc}"
    finally:
        runtime.cancel.clear()


@app.post("/api/scan/start")
def start_scan() -> JSONResponse:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    if runtime.thread and runtime.thread.is_alive():
        return fail("SCAN_RUNNING", "Scan is already running.", status=409)
    runtime.cancel.clear()
    thread = threading.Thread(target=_scan_worker, daemon=True)
    runtime.thread = thread
    thread.start()
    return ok({"status": "started"})


@app.post("/api/scan/stop")
def stop_scan() -> JSONResponse:
    runtime.cancel.set()
    return ok({"status": "stop_requested"})


@app.get("/api/thumbnails", response_model=None)
def get_thumbnail(path: str = Query("", min_length=1)) -> Response:
    if not service.has_library():
        return fail("NO_LIBRARY", "No library selected.")
    rel_path = path.strip().lstrip("/")
    full_path = service.resolve_path(rel_path)
    if not full_path.exists():
        return fail("NOT_FOUND", "Thumbnail not found.", status=404)
    return FileResponse(str(full_path))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.web_api:app", host="0.0.0.0", port=8000, reload=True)
