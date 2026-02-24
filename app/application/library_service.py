from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.application.models import (
    ExplorerEntry,
    ScanProgress,
    ScanResult,
    ScannedFile,
    TagMiningResult,
)
from app.application.ports import (
    AppRuntimeLoggerPort,
    EmbeddingModelPort,
    FileOpenerPort,
    LibraryRepositoryPort,
    MediaIndexerPort,
    ProgressCallback,
    RerankerModelPort,
    ScanLoggerPort,
    ScannerPort,
    TagGeneratorPort,
    TagMiningLoggerPort,
    TagMiningProgressCallback,
    TokenizerPort,
)
from app.application.tag_mining_service import TitleTagMiningService


class LibraryService:
    def __init__(
        self,
        repository: LibraryRepositoryPort,
        scanner: ScannerPort,
        media_indexer: MediaIndexerPort,
        opener: FileOpenerPort,
        scan_logger: ScanLoggerPort,
        tag_mining_logger: Optional[TagMiningLoggerPort] = None,
        runtime_logger: Optional[AppRuntimeLoggerPort] = None,
        embedding_model: Optional[EmbeddingModelPort] = None,
        reranker_model: Optional[RerankerModelPort] = None,
        tag_generator_model: Optional[TagGeneratorPort] = None,
        tokenizer: Optional[TokenizerPort] = None,
    ) -> None:
        self._repo = repository
        self._scanner = scanner
        self._media_indexer = media_indexer
        self._opener = opener
        self._scan_logger = scan_logger
        self._tag_mining_logger = tag_mining_logger
        self._runtime_logger = runtime_logger
        self._embedding_model = embedding_model
        self._reranker_model = reranker_model
        self._tag_generator_model = tag_generator_model
        self._tokenizer = tokenizer

        self._dir_children: Dict[str, set[str]] = {}
        self._dir_files: Dict[str, list[ExplorerEntry]] = {}

    def select_library(self, root: Path) -> None:
        self._repo.open(root)
        self._scan_logger.set_library_root(root)
        if self._tag_mining_logger is not None:
            self._tag_mining_logger.set_library_root(root)
        if self._runtime_logger is not None:
            self._runtime_logger.set_library_root(root)
            self._runtime_log(
                event="library_selected",
                action="select_library",
                message="Library selected",
                payload={"root": str(root)},
            )
        self.rebuild_index()

    def close(self) -> None:
        self._repo.close()

    def has_library(self) -> bool:
        return self._repo.root_path() is not None

    def library_root(self) -> Optional[Path]:
        return self._repo.root_path()

    def library_name(self) -> str:
        root = self._repo.root_path()
        return root.name if root and root.name else "视频库"

    def scan(self, progress: Optional[ProgressCallback] = None) -> ScanResult:
        root = self._require_root()
        started = time.time()
        self._emit_progress(
            progress,
            phase="scan_start",
            message="正在扫描文件列表...",
            indeterminate=True,
        )
        scanned_files = self._scanner.scan(root, progress=progress)
        self._runtime_log(
            event="scan_start",
            action="scan",
            message="Scan started",
            payload={"total_files": len(scanned_files)},
        )
        self._scan_logger.begin_scan(total_files=len(scanned_files))
        for scanned_file in scanned_files:
            self._scan_logger.log_file_discovered(scanned_file)

        try:
            self._emit_progress(
                progress,
                phase="db_apply_scan",
                message=f"正在更新数据库记录（文件数：{len(scanned_files)}）...",
                indeterminate=True,
            )
            result = self._repo.apply_scan(scanned_files)
            targets = self._build_media_index_targets(
                scanned_files=scanned_files,
                refresh_rel_paths=result.refresh_rel_paths,
            )
            if targets:
                self._emit_progress(
                    progress,
                    phase="media_prepare",
                    message=f"准备处理媒体信息（目标数：{len(targets)}）...",
                    indeterminate=True,
                )
                media_records = self._media_indexer.index(
                    root, targets, progress=progress
                )
                self._emit_progress(
                    progress,
                    phase="db_apply_media",
                    message="正在写入元数据和缩略图索引...",
                    indeterminate=True,
                )
                self._repo.apply_media_records(media_records)
            else:
                self._emit_progress(
                    progress,
                    phase="media_skip",
                    message="无需更新媒体元数据和缩略图。",
                    indeterminate=True,
                )
            elapsed_ms = int((time.time() - started) * 1000)
            self._scan_logger.end_scan(result=result, elapsed_ms=elapsed_ms)
            self._runtime_log(
                event="scan_done",
                action="scan",
                message="Scan completed",
                payload={
                    "added": int(result.added),
                    "updated": int(result.updated),
                    "seen": int(result.seen),
                    "elapsed_ms": elapsed_ms,
                },
            )
            self._emit_progress(
                progress,
                phase="scan_done",
                message=(
                    f"扫描完成：新增 {result.added}，更新 {result.updated}，"
                    f"本次发现 {result.seen}"
                ),
                current=1,
                total=1,
                indeterminate=False,
            )
        except Exception as exc:
            self._scan_logger.log_error(stage="scan", message=str(exc))
            self._runtime_log(
                event="scan_error",
                level="error",
                action="scan",
                message=str(exc),
                payload={"stage": "scan"},
            )
            self._emit_progress(
                progress,
                phase="scan_error",
                message=f"扫描失败：{exc}",
                current=0,
                total=1,
                indeterminate=False,
            )
            raise

        self.rebuild_index()
        return result

    def list_scan_logs(self, limit: int = 30) -> list[Path]:
        return self._scan_logger.list_logs(limit=limit)

    def latest_scan_log(self) -> Optional[Path]:
        return self._scan_logger.latest_log_path()

    def read_scan_log(self, log_path: Path) -> list[Dict[str, Any]]:
        return self._scan_logger.read_log(log_path)

    def mine_title_tags(
        self,
        progress: Optional[TagMiningProgressCallback] = None,
        min_df: int = 2,
        max_tags_per_video: int = 8,
        max_terms: int = 400,
        should_stop: Optional[Callable[[], bool]] = None,
        strategy: str = "auto",
        scope: str = "all",
    ) -> TagMiningResult:
        if self._tag_mining_logger is None:
            raise RuntimeError("未配置标签提取日志器")
        self._runtime_log(
            event="tag_mining_start",
            action="mine_title_tags",
            message="Tag mining started",
            payload={
                "strategy": strategy,
                "scope": scope,
                "min_df": int(min_df),
                "max_tags_per_video": int(max_tags_per_video),
                "max_terms": int(max_terms),
            },
        )
        try:
            result = TitleTagMiningService(
                repository=self._repo,
                logger=self._tag_mining_logger,
                embedding_model=self._embedding_model,
                reranker_model=self._reranker_model,
                tag_generator_model=self._tag_generator_model,
                tokenizer=self._tokenizer,
            ).mine(
                progress=progress,
                min_df=min_df,
                max_tags_per_video=max_tags_per_video,
                max_terms=max_terms,
                should_stop=should_stop,
                strategy=strategy,
                scope=scope,
            )
        except Exception as exc:
            self._runtime_log(
                event="tag_mining_error",
                level="error",
                action="mine_title_tags",
                message=str(exc),
            )
            raise
        self._runtime_log(
            event="tag_mining_done",
            action="mine_title_tags",
            message="Tag mining completed",
            payload={
                "processed_videos": int(result.processed_videos),
                "selected_terms": int(result.selected_terms),
                "tagged_videos": int(result.tagged_videos),
                "created_relations": int(result.created_relations),
                "pending_candidate_terms": int(result.pending_candidate_terms),
            },
        )
        self.rebuild_index()
        return result

    def list_tag_mining_logs(self, limit: int = 30) -> list[Path]:
        if self._tag_mining_logger is None:
            return []
        return self._tag_mining_logger.list_logs(limit=limit)

    def latest_tag_mining_log(self) -> Optional[Path]:
        if self._tag_mining_logger is None:
            return None
        return self._tag_mining_logger.latest_log_path()

    def read_tag_mining_log(self, log_path: Path) -> list[Dict[str, Any]]:
        if self._tag_mining_logger is None:
            return []
        return self._tag_mining_logger.read_log(log_path)

    def list_runtime_logs(self, limit: int = 30) -> list[Path]:
        if self._runtime_logger is None:
            return []
        return self._runtime_logger.list_logs(limit=limit)

    def latest_runtime_log(self) -> Optional[Path]:
        if self._runtime_logger is None:
            return None
        return self._runtime_logger.latest_log_path()

    def read_runtime_log(self, log_path: Path) -> list[Dict[str, Any]]:
        if self._runtime_logger is None:
            return []
        return self._runtime_logger.read_log(log_path)

    def list_logs(self, source: str, limit: int = 30) -> list[Path]:
        source_key = self._normalize_log_source(source)
        if source_key == "scan":
            return self.list_scan_logs(limit=limit)
        if source_key == "tag_mining":
            return self.list_tag_mining_logs(limit=limit)
        return self.list_runtime_logs(limit=limit)

    def latest_log(self, source: str) -> Optional[Path]:
        source_key = self._normalize_log_source(source)
        if source_key == "scan":
            return self.latest_scan_log()
        if source_key == "tag_mining":
            return self.latest_tag_mining_log()
        return self.latest_runtime_log()

    def read_log_events(
        self,
        source: str,
        log_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
        level: str = "",
        event: str = "",
        q: str = "",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        source_key = self._normalize_log_source(source)
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")

        log_path, rows = self._load_filtered_log_rows(
            source=source_key,
            log_id=log_id,
            level=level,
            event=event,
            q=q,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "source": source_key,
            "log_id": log_path.name,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": rows[start:end],
        }

    def analyze_log_events(
        self,
        source: str,
        log_id: str,
        *,
        level: str = "",
        event: str = "",
        q: str = "",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        source_key = self._normalize_log_source(source)
        log_path, rows = self._load_filtered_log_rows(
            source=source_key,
            log_id=log_id,
            level=level,
            event=event,
            q=q,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        error_count = 0
        parse_error_count = 0
        last_error_ts = 0
        event_counter: Dict[str, int] = {}

        for row in rows:
            row_level = str(row.get("level") or "").strip().lower()
            row_event = str(row.get("event") or "").strip()
            row_ts = self._safe_int(row.get("ts_epoch"), default=0)
            if row_event:
                event_counter[row_event] = event_counter.get(row_event, 0) + 1
            if row_level == "error":
                error_count += 1
                if row_ts > last_error_ts:
                    last_error_ts = row_ts
            if row_event.lower() == "parse_error":
                parse_error_count += 1

        top_events = [
            {"event": name, "count": count}
            for name, count in sorted(
                event_counter.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ]
        return {
            "source": source_key,
            "log_id": log_path.name,
            "total": len(rows),
            "error_count": error_count,
            "parse_error_count": parse_error_count,
            "last_error_ts": last_error_ts or None,
            "top_events": top_events,
        }

    def clear_ai_title_tags(self) -> int:
        removed = self._repo.clear_ai_title_tags()
        self.rebuild_index()
        return removed

    def list_pending_tag_candidates(self) -> list[Dict[str, Any]]:
        return self._repo.list_pending_tag_candidates()

    def list_tag_candidates(self, statuses: Optional[list[str]] = None) -> list[Dict[str, Any]]:
        return self._repo.list_tag_candidates(statuses=statuses)

    def list_tag_blacklist(self) -> list[Dict[str, Any]]:
        return self._repo.list_tag_blacklist()

    def list_blacklist_terms(self) -> list[str]:
        return self._repo.list_blacklist_terms()

    def approve_tag_candidates(self, candidate_ids: list[int]) -> Dict[str, int]:
        result = self._repo.approve_tag_candidates(candidate_ids)
        if int(result.get("approved_candidates") or 0) > 0:
            self.rebuild_index()
        self._runtime_log(
            event="tag_candidates_approved",
            action="approve_tag_candidates",
            message="Approved tag candidates",
            payload={
                "candidate_ids_count": len(candidate_ids),
                "approved_candidates": int(result.get("approved_candidates") or 0),
                "applied_relations": int(result.get("applied_relations") or 0),
            },
        )
        return result

    def approve_tag_candidates_with_mapping(
        self,
        candidate_ids: list[int],
        target_tag_id: int,
    ) -> Dict[str, int]:
        result = self._repo.approve_tag_candidates_with_mapping(
            candidate_ids,
            target_tag_id,
        )
        if int(result.get("approved_candidates") or 0) > 0:
            self.rebuild_index()
        self._runtime_log(
            event="tag_candidates_mapped_approved",
            action="approve_tag_candidates_with_mapping",
            message="Approved candidates with mapping",
            payload={
                "candidate_ids_count": len(candidate_ids),
                "target_tag_id": int(target_tag_id),
                "approved_candidates": int(result.get("approved_candidates") or 0),
                "applied_relations": int(result.get("applied_relations") or 0),
            },
        )
        return result

    def reject_tag_candidates(self, candidate_ids: list[int]) -> int:
        rejected = self._repo.reject_tag_candidates(candidate_ids)
        self._runtime_log(
            event="tag_candidates_rejected",
            action="reject_tag_candidates",
            message="Rejected tag candidates",
            payload={
                "candidate_ids_count": len(candidate_ids),
                "rejected": int(rejected),
            },
        )
        return rejected

    def blacklist_tag_candidates(self, candidate_ids: list[int]) -> Dict[str, int]:
        result = self._repo.blacklist_tag_candidates(candidate_ids)
        self._runtime_log(
            event="tag_candidates_blacklisted",
            action="blacklist_tag_candidates",
            message="Blacklisted tag candidates",
            payload={
                "candidate_ids_count": len(candidate_ids),
                "blacklisted_candidates": int(result.get("blacklisted_candidates") or 0),
                "blacklist_terms_added": int(result.get("blacklist_terms_added") or 0),
            },
        )
        return result

    def requeue_tag_candidates(self, candidate_ids: list[int]) -> int:
        requeued = self._repo.requeue_tag_candidates(candidate_ids)
        self._runtime_log(
            event="tag_candidates_requeued",
            action="requeue_tag_candidates",
            message="Requeued tag candidates",
            payload={
                "candidate_ids_count": len(candidate_ids),
                "requeued": int(requeued),
            },
        )
        return requeued

    def clear_pending_tag_candidates(self) -> int:
        removed = self._repo.clear_pending_tag_candidates()
        self._runtime_log(
            event="tag_candidates_cleared",
            action="clear_pending_tag_candidates",
            message="Cleared pending tag candidates",
            payload={"removed": int(removed)},
        )
        return removed

    def list_tag_alias_memory(self) -> list[Dict[str, Any]]:
        return self._repo.list_tag_alias_memory()

    def upsert_tag_alias_memory(
        self,
        alias_to_tag_id: Dict[str, int],
        source: str = "manual",
        status: str = "verified",
    ) -> int:
        return self._repo.upsert_tag_alias_memory(
            alias_to_tag_id=alias_to_tag_id,
            source=source,
            status=status,
        )

    def list_pending_tag_alias_suggestions(self) -> list[Dict[str, Any]]:
        return self._repo.list_pending_tag_alias_suggestions()

    def approve_tag_alias_suggestions(self, suggestion_ids: list[int]) -> Dict[str, int]:
        return self._repo.approve_tag_alias_suggestions(suggestion_ids)

    def reject_tag_alias_suggestions(self, suggestion_ids: list[int]) -> int:
        return self._repo.reject_tag_alias_suggestions(suggestion_ids)

    def list_tag_library(self) -> list[Dict[str, Any]]:
        return self._repo.list_tags()

    def create_tags(self, names: list[str]) -> int:
        created = self._repo.upsert_tags(names)
        if created > 0:
            self.rebuild_index()
        self._runtime_log(
            event="tags_created",
            action="create_tags",
            message="Created tags",
            payload={"input_count": len(names), "created": int(created)},
        )
        return created

    def delete_tags_by_ids(self, tag_ids: list[int]) -> int:
        removed = self._repo.delete_tags_by_ids(tag_ids)
        if removed > 0:
            self.rebuild_index()
        self._runtime_log(
            event="tags_deleted",
            action="delete_tags_by_ids",
            message="Deleted tags",
            payload={"input_count": len(tag_ids), "removed": int(removed)},
        )
        return removed

    def add_manual_tag_to_video(self, rel_path: str, tag_name: str) -> bool:
        video_id = self._video_id_from_rel_path(rel_path)
        if not video_id:
            return False
        ok = self._repo.add_manual_tag_to_video(video_id, tag_name)
        if ok:
            self.rebuild_index()
        return ok

    def remove_tag_from_video(self, rel_path: str, tag_name: str) -> int:
        video_id = self._video_id_from_rel_path(rel_path)
        if not video_id:
            return 0
        removed = self._repo.remove_tag_from_video(video_id, tag_name)
        if removed > 0:
            self.rebuild_index()
        return removed

    def get_video_info(self, rel_path: str) -> Optional[Dict[str, Any]]:
        for info in self._repo.videos().values():
            if str(info.get("rel_path") or "") == rel_path:
                return dict(info)
        return None

    def rebuild_index(self) -> None:
        self._dir_children = {"": set()}
        self._dir_files = {"": []}

        for info in self._repo.videos().values():
            rel_path = info.get("rel_path")
            if not isinstance(rel_path, str):
                continue
            parts = [p for p in rel_path.split("/") if p]
            if not parts:
                continue

            parent_dir = "/".join(parts[:-1])
            self._ensure_dir(parent_dir)
            self._dir_files.setdefault(parent_dir, []).append(self._to_entry(info))

        for rel_dir, files in self._dir_files.items():
            files.sort(key=lambda x: x.name.lower())

    def list_subdirectories(self, rel_dir: str) -> list[str]:
        return sorted(self._dir_children.get(rel_dir, set()), key=str.lower)

    def list_entries(self, rel_dir: str) -> list[ExplorerEntry]:
        entries: list[ExplorerEntry] = []
        for child_name in self.list_subdirectories(rel_dir):
            child_rel = child_name if not rel_dir else f"{rel_dir}/{child_name}"
            entries.append(ExplorerEntry(name=child_name, rel_path=child_rel, is_dir=True))
        entries.extend(self._dir_files.get(rel_dir, []))
        return entries

    def list_all_video_entries(self) -> list[ExplorerEntry]:
        entries: list[ExplorerEntry] = []
        for info in self._repo.videos().values():
            rel_path = str(info.get("rel_path") or "")
            if not rel_path:
                continue
            if bool(info.get("missing")):
                continue
            entries.append(self._to_entry(info))
        entries.sort(key=lambda item: item.rel_path.lower())
        return entries

    def search_video_entries(
        self,
        query: str = "",
        tag_filter: str = "",
        tag_filters: Optional[list[str]] = None,
    ) -> list[ExplorerEntry]:
        query_key = str(query or "").strip().lower()
        normalized_tag_filters: list[str] = []
        seen_filter_keys = set()
        for raw_tag in list(tag_filters or []):
            key = str(raw_tag or "").strip().lower()
            if not key or key in seen_filter_keys:
                continue
            seen_filter_keys.add(key)
            normalized_tag_filters.append(key)
        if not normalized_tag_filters:
            single_tag = str(tag_filter or "").strip().lower()
            if single_tag:
                normalized_tag_filters.append(single_tag)

        if not query_key and not normalized_tag_filters:
            return self.list_all_video_entries()

        out: list[ExplorerEntry] = []
        for entry in self.list_all_video_entries():
            tags = [str(tag or "").strip().lower() for tag in list(entry.tags or [])]
            text_blob = f"{entry.name} {entry.rel_path}".lower()

            query_ok = True
            if query_key:
                text_match = query_key in text_blob
                tag_match = any(query_key in tag for tag in tags)
                query_ok = text_match or tag_match

            tag_filter_ok = True
            if normalized_tag_filters:
                tag_set = set(tags)
                tag_filter_ok = all(tag_name in tag_set for tag_name in normalized_tag_filters)

            if query_ok and tag_filter_ok:
                out.append(entry)

        return out

    def directory_exists(self, rel_dir: str) -> bool:
        if rel_dir == "":
            return self.has_library()
        parent = self.parent_directory(rel_dir)
        name = rel_dir.split("/")[-1]
        return name in self._dir_children.get(parent, set())

    def parent_directory(self, rel_dir: str) -> str:
        if not rel_dir:
            return ""
        return "/".join(rel_dir.split("/")[:-1])

    def resolve_path(self, rel_path: str) -> Path:
        return self._require_root() / Path(rel_path)

    def open_entry(self, rel_path: str) -> None:
        full_path = self.resolve_path(rel_path)
        if not full_path.exists():
            raise FileNotFoundError(str(full_path))
        self._opener.open_file(full_path)

    def _require_root(self) -> Path:
        root = self._repo.root_path()
        if root is None:
            raise RuntimeError("未选择视频库根目录")
        return root

    def _load_filtered_log_rows(
        self,
        source: str,
        log_id: str,
        *,
        level: str = "",
        event: str = "",
        q: str = "",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> tuple[Path, list[Dict[str, Any]]]:
        log_path = self._resolve_log_path(source, log_id)
        if source == "scan":
            raw_events = self.read_scan_log(log_path)
        elif source == "tag_mining":
            raw_events = self.read_tag_mining_log(log_path)
        else:
            raw_events = self.read_runtime_log(log_path)

        level_filter = level.strip().lower()
        event_filter = event.strip().lower()
        q_filter = q.strip().lower()

        rows: list[Dict[str, Any]] = []
        for line_no, payload in enumerate(raw_events, start=1):
            item = dict(payload or {})
            ts_epoch = self._safe_int(item.get("ts_epoch"), default=0)
            row_level = str(item.get("level") or "info").strip().lower()
            row_event = str(item.get("event") or "").strip()
            rel_path = str(item.get("rel_path") or item.get("thumb_rel_path") or "").strip()
            summary = self._summarize_log_event(item)
            search_blob = (
                f"{row_event} {row_level} {rel_path} "
                f"{summary} {item.get('error', '')} {item.get('message', '')}"
            ).lower()

            if level_filter and row_level != level_filter:
                continue
            if event_filter and row_event.lower() != event_filter:
                continue
            if from_ts is not None and ts_epoch < from_ts:
                continue
            if to_ts is not None and ts_epoch > to_ts:
                continue
            if q_filter and q_filter not in search_blob:
                continue

            rows.append(
                {
                    "line_no": line_no,
                    "ts_epoch": ts_epoch,
                    "level": row_level,
                    "event": row_event,
                    "rel_path": rel_path,
                    "summary": summary,
                    "payload": item,
                }
            )

        return log_path, rows

    def _normalize_log_source(self, source: str) -> str:
        value = str(source or "").strip().lower()
        if value in {"scan", "tag_mining", "app_runtime"}:
            return value
        raise ValueError(f"Unsupported log source: {source}")

    def _resolve_log_path(self, source: str, log_id: str) -> Path:
        cleaned = str(log_id or "").strip()
        if not cleaned:
            latest = self.latest_log(source)
            if latest is None:
                raise FileNotFoundError("No log available.")
            return latest

        candidate = Path(cleaned)
        if cleaned != candidate.name or "/" in cleaned or "\\" in cleaned:
            raise ValueError("log_id must be a plain filename.")

        for path in self.list_logs(source, limit=5000):
            if path.name == cleaned:
                return path
        raise FileNotFoundError(f"Log file not found: {cleaned}")

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _summarize_log_event(self, event: Dict[str, Any]) -> str:
        event_name = str(event.get("event") or "").strip().lower()
        if event_name == "scan_start":
            return f"Scan started, total_files={self._safe_int(event.get('total_files'), 0)}"
        if event_name == "file_discovered":
            return str(event.get("rel_path") or "")
        if event_name == "media_probe_ok":
            return (
                f"Probe OK: {event.get('video_codec', '--')} / "
                f"{self._safe_int(event.get('width'))}x{self._safe_int(event.get('height'))}"
            )
        if event_name == "media_probe_error":
            return f"Probe error: {str(event.get('error') or '')[:160]}"
        if event_name == "thumb_ok":
            return f"Thumbnail OK @ {self._safe_int(event.get('frame_ms'))}ms"
        if event_name == "thumb_error":
            return f"Thumbnail error: {str(event.get('error') or '')[:160]}"
        if event_name == "scan_summary":
            return (
                "Summary: "
                f"added={self._safe_int(event.get('added'))}, "
                f"updated={self._safe_int(event.get('updated'))}, "
                f"seen={self._safe_int(event.get('seen'))}"
            )
        if event_name == "error":
            return f"{event.get('stage', 'unknown')}: {str(event.get('error') or '')[:160]}"
        if event_name == "tag_mining_start":
            return f"Tag mining started, total_videos={self._safe_int(event.get('total_videos'))}"
        if event_name == "video_processed":
            selected = event.get("selected_terms") or []
            return f"Video processed, selected_terms={len(selected)}"
        if event_name == "tag_mining_summary":
            return f"Tag mining summary: {str(event.get('summary') or '')[:180]}"
        if event_name == "tag_mining_error":
            return f"Tag mining error: {str(event.get('error') or '')[:160]}"
        if event_name == "parse_error":
            return "Invalid JSON line."
        if event_name.startswith("tag_candidates_"):
            return f"{event_name.replace('_', ' ')}"
        if event_name in {"tags_created", "tags_deleted", "library_selected"}:
            return str(event.get("message") or event_name)

        ts_epoch = self._safe_int(event.get("ts_epoch"))
        ts_label = ""
        if ts_epoch > 0:
            ts_label = datetime.fromtimestamp(ts_epoch).strftime("%Y-%m-%d %H:%M:%S")
        fallback = str(event.get("message") or event.get("error") or "").strip()
        if fallback:
            return fallback[:180]
        if ts_label:
            return f"{event_name or 'event'} @ {ts_label}"
        return event_name or "event"

    def _runtime_log(
        self,
        *,
        event: str,
        action: str = "",
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
        level: str = "info",
    ) -> None:
        if self._runtime_logger is None:
            return
        try:
            self._runtime_logger.log_event(
                event=event,
                level=level,
                module="library_service",
                action=action,
                message=message,
                payload=payload or {},
            )
        except Exception:
            # Runtime logs must never break user-facing flows.
            pass

    def _video_id_from_rel_path(self, rel_path: str) -> str:
        for video_id, info in self._repo.videos().items():
            if str(info.get("rel_path") or "") == rel_path:
                return str(video_id)
        return ""

    def _ensure_dir(self, rel_dir: str) -> None:
        if rel_dir in self._dir_files:
            return

        parts = [p for p in rel_dir.split("/") if p]
        current = ""
        parent = ""
        for part in parts:
            current = part if not current else f"{current}/{part}"
            if current in self._dir_files:
                parent = current
                continue

            self._dir_files[current] = []
            self._dir_children.setdefault(current, set())
            self._dir_children.setdefault(parent, set()).add(part)
            parent = current

    def _to_entry(self, info: Dict[str, Any]) -> ExplorerEntry:
        rel_path = str(info.get("rel_path") or "")
        filename = str(info.get("filename") or Path(rel_path).name)
        title_guess = str(info.get("title_guess") or filename)
        display_name = title_guess if title_guess == filename else f"{title_guess} [{filename}]"

        status = "missing" if info.get("missing") else str(info.get("status") or "normal")
        tags = [str(tag) for tag in (info.get("tags") or [])]

        return ExplorerEntry(
            name=display_name,
            rel_path=rel_path,
            is_dir=False,
            mtime_epoch=int(info.get("mtime_epoch") or 0),
            size_bytes=int(info.get("size_bytes") or 0),
            status=status,
            tags=tags,
            ext=str(info.get("ext") or "").lower(),
            duration_ms=int(info.get("duration_ms") or 0),
            width=int(info.get("width") or 0),
            height=int(info.get("height") or 0),
            media_created_epoch=int(info.get("media_created_epoch") or 0),
            thumb_rel_path=str(info.get("thumb_rel_path") or ""),
        )

    def _build_media_index_targets(
        self, scanned_files: list[ScannedFile], refresh_rel_paths: list[str]
    ) -> list[ScannedFile]:
        """
        Decide which files need FFmpeg indexing in this scan:
        1) New or changed files from incremental scanner.
        2) Backfill files that still miss media fields or thumbnail.
        """
        indexed_rel_paths = set(refresh_rel_paths)
        videos = self._repo.videos()
        scanned_map = {f.rel_path: f for f in scanned_files}

        for info in videos.values():
            rel_path = str(info.get("rel_path") or "")
            if not rel_path:
                continue
            if rel_path not in scanned_map:
                continue
            if bool(info.get("missing")):
                continue

            duration_ms = int(info.get("duration_ms") or 0)
            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            thumb_rel_path = str(info.get("thumb_rel_path") or "")
            if duration_ms <= 0 or width <= 0 or height <= 0 or not thumb_rel_path:
                indexed_rel_paths.add(rel_path)

        return [scanned_map[p] for p in sorted(indexed_rel_paths) if p in scanned_map]

    def _emit_progress(
        self,
        progress: Optional[ProgressCallback],
        phase: str,
        message: str,
        current: int = 0,
        total: int = 0,
        indeterminate: bool = False,
        rel_path: str = "",
    ) -> None:
        if progress is None:
            return
        try:
            progress(
                ScanProgress(
                    phase=phase,
                    message=message,
                    current=current,
                    total=total,
                    indeterminate=indeterminate,
                    rel_path=rel_path,
                )
            )
        except Exception:
            pass
