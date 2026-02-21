from __future__ import annotations

import time
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
        return result

    def reject_tag_candidates(self, candidate_ids: list[int]) -> int:
        return self._repo.reject_tag_candidates(candidate_ids)

    def blacklist_tag_candidates(self, candidate_ids: list[int]) -> Dict[str, int]:
        return self._repo.blacklist_tag_candidates(candidate_ids)

    def requeue_tag_candidates(self, candidate_ids: list[int]) -> int:
        return self._repo.requeue_tag_candidates(candidate_ids)

    def clear_pending_tag_candidates(self) -> int:
        return self._repo.clear_pending_tag_candidates()

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
        return created

    def delete_tags_by_ids(self, tag_ids: list[int]) -> int:
        removed = self._repo.delete_tags_by_ids(tag_ids)
        if removed > 0:
            self.rebuild_index()
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
