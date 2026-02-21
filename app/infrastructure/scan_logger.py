from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.application.models import MediaRecord, ScanResult, ScannedFile


class JsonlScanLogger:
    def __init__(self) -> None:
        self._root: Optional[Path] = None
        self._logs_dir: Optional[Path] = None
        self._current_log: Optional[Path] = None
        self._scan_started_epoch: int = 0

    def set_library_root(self, root: Path) -> None:
        self._root = root
        self._logs_dir = root / ".mm" / "logs"
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        self._current_log = None
        self._scan_started_epoch = 0

    def begin_scan(self, total_files: int) -> None:
        if self._logs_dir is None:
            return
        now = int(time.time())
        stamp = datetime.fromtimestamp(now).strftime("%Y%m%d_%H%M%S")
        self._current_log = self._logs_dir / f"scan_{stamp}.jsonl"
        self._scan_started_epoch = now
        self._write_event(
            {
                "event": "scan_start",
                "level": "info",
                "total_files": total_files,
            }
        )

    def log_file_discovered(self, scanned_file: ScannedFile) -> None:
        if self._current_log is None:
            return
        self._write_event(
            {
                "event": "file_discovered",
                "level": "info",
                "rel_path": scanned_file.rel_path,
                "size_bytes": scanned_file.size_bytes,
                "mtime_epoch": scanned_file.mtime_epoch,
            }
        )

    def log_media_record(self, record: MediaRecord) -> None:
        if self._current_log is None:
            return

        if record.probe_status == "ok":
            self._write_event(
                {
                    "event": "media_probe_ok",
                    "level": "info",
                    "rel_path": record.rel_path,
                    "duration_ms": record.duration_ms,
                    "width": record.width,
                    "height": record.height,
                    "video_codec": record.video_codec,
                    "audio_codec": record.audio_codec,
                    "media_created_epoch": record.media_created_epoch,
                }
            )
        else:
            self._write_event(
                {
                    "event": "media_probe_error",
                    "level": "error",
                    "rel_path": record.rel_path,
                    "error": self._trim_message(record.probe_error),
                }
            )

        if record.thumb_status == "ok":
            self._write_event(
                {
                    "event": "thumb_ok",
                    "level": "info",
                    "rel_path": record.rel_path,
                    "thumb_rel_path": record.thumb_rel_path,
                    "thumb_width": record.thumb_width,
                    "thumb_height": record.thumb_height,
                    "frame_ms": record.frame_ms,
                }
            )
        else:
            self._write_event(
                {
                    "event": "thumb_error",
                    "level": "error",
                    "rel_path": record.rel_path,
                    "error": self._trim_message(record.thumb_error),
                }
            )

    def end_scan(self, result: ScanResult, elapsed_ms: int) -> None:
        if self._current_log is None:
            return
        self._write_event(
            {
                "event": "scan_summary",
                "level": "info",
                "added": result.added,
                "updated": result.updated,
                "seen": result.seen,
                "refresh_count": len(result.refresh_rel_paths),
                "elapsed_ms": elapsed_ms,
            }
        )
        self._current_log = None
        self._scan_started_epoch = 0

    def log_error(self, stage: str, message: str, rel_path: str = "") -> None:
        self._write_event(
            {
                "event": "error",
                "level": "error",
                "stage": stage,
                "rel_path": rel_path,
                "error": self._trim_message(message),
            }
        )

    def list_logs(self, limit: int = 30) -> list[Path]:
        if self._logs_dir is None or not self._logs_dir.exists():
            return []
        logs = sorted(
            self._logs_dir.glob("scan_*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return logs[:limit]

    def latest_log_path(self) -> Optional[Path]:
        logs = self.list_logs(limit=1)
        return logs[0] if logs else None

    def read_log(self, log_path: Path) -> list[Dict[str, Any]]:
        if not log_path.exists():
            return []
        records: list[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {
                        "event": "parse_error",
                        "level": "error",
                        "error": "invalid json line",
                        "raw": raw,
                    }
                records.append(payload)
        return records

    def _write_event(self, payload: Dict[str, Any]) -> None:
        if self._current_log is None:
            if self._logs_dir is None:
                return
            # If called outside a scan cycle, append to latest fallback file.
            now = int(time.time())
            stamp = datetime.fromtimestamp(now).strftime("%Y%m%d_%H%M%S")
            self._current_log = self._logs_dir / f"scan_{stamp}.jsonl"

        event = {
            "ts_epoch": int(time.time()),
            **payload,
        }
        self._current_log.parent.mkdir(parents=True, exist_ok=True)
        with self._current_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _trim_message(self, text: str, max_chars: int = 800) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...(truncated)"
