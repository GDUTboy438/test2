from __future__ import annotations

import os
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
from app.application.models import ExplorerEntry, ScanProgress
from app.infrastructure.app_runtime_logger import JsonlAppRuntimeLogger
from app.infrastructure.embedding_model import LocalSentenceTransformerModel
from app.infrastructure.file_opener import DefaultFileOpener
from app.infrastructure.library_repository import SqliteLibraryRepository
from app.infrastructure.media_indexer import FfmpegMediaIndexer
from app.infrastructure.reranker_model import LocalBgeRerankerModel
from app.infrastructure.scan_logger import JsonlScanLogger
from app.infrastructure.scanner_gateway import CoreScannerGateway
from app.infrastructure.tag_mining_logger import JsonlTagMiningLogger
from app.infrastructure.tokenizer_pkuseg import PkusegTokenizer


class LibrarySelectRequest(BaseModel):
    path: str


class EntryOpenRequest(BaseModel):
    path: str


class TagCreateRequest(BaseModel):
    names: list[str]


class TagIdListRequest(BaseModel):
    ids: list[int]


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


class ApiRuntime:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.progress = ScanState()


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


def _pick_directory() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Select Media Library")
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
    depth: int = Query(2, ge=1, le=5),
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
