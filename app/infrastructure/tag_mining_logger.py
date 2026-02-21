from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class JsonlTagMiningLogger:
    def __init__(self) -> None:
        self._root: Optional[Path] = None
        self._logs_dir: Optional[Path] = None
        self._current_log: Optional[Path] = None

    def set_library_root(self, root: Path) -> None:
        self._root = root
        self._logs_dir = root / ".mm" / "logs"
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        self._current_log = None

    def begin_run(self, total_videos: int, config: Dict[str, Any]) -> None:
        if self._logs_dir is None:
            return
        now = int(time.time())
        stamp = datetime.fromtimestamp(now).strftime("%Y%m%d_%H%M%S")
        self._current_log = self._logs_dir / f"tag_mining_{stamp}.jsonl"
        self._write_event(
            {
                "event": "tag_mining_start",
                "level": "info",
                "total_videos": total_videos,
                "config": config,
            }
        )

    def log_event(self, event: str, payload: Dict[str, Any]) -> None:
        self._write_event(
            {
                "event": event,
                "level": "info",
                **payload,
            }
        )

    def log_video_processed(
        self, video_id: str, rel_path: str, terms: list[str], selected_terms: list[str]
    ) -> None:
        self._write_event(
            {
                "event": "video_processed",
                "level": "info",
                "video_id": video_id,
                "rel_path": rel_path,
                "terms_preview": terms[:12],
                "selected_terms": selected_terms,
            }
        )

    def log_summary(self, summary: Dict[str, Any]) -> None:
        self._write_event(
            {
                "event": "tag_mining_summary",
                "level": "info",
                "summary": summary,
            }
        )
        self._current_log = None

    def log_error(self, stage: str, message: str, rel_path: str = "") -> None:
        self._write_event(
            {
                "event": "tag_mining_error",
                "level": "error",
                "stage": stage,
                "rel_path": rel_path,
                "error": self._trim(message),
            }
        )

    def list_logs(self, limit: int = 30) -> list[Path]:
        if self._logs_dir is None or not self._logs_dir.exists():
            return []
        logs = sorted(
            self._logs_dir.glob("tag_mining_*.jsonl"),
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
        rows: list[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    rows.append(json.loads(raw))
                except json.JSONDecodeError:
                    rows.append(
                        {
                            "event": "parse_error",
                            "level": "error",
                            "raw": raw,
                        }
                    )
        return rows

    def _write_event(self, payload: Dict[str, Any]) -> None:
        if self._logs_dir is None:
            return
        if self._current_log is None:
            now = int(time.time())
            stamp = datetime.fromtimestamp(now).strftime("%Y%m%d_%H%M%S")
            self._current_log = self._logs_dir / f"tag_mining_{stamp}.jsonl"
        event = {"ts_epoch": int(time.time()), **payload}
        self._current_log.parent.mkdir(parents=True, exist_ok=True)
        with self._current_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _trim(self, text: str, max_chars: int = 800) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...(truncated)"
