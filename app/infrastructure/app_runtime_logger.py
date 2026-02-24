from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class JsonlAppRuntimeLogger:
    def __init__(self) -> None:
        self._root: Optional[Path] = None
        self._logs_dir: Optional[Path] = None

    def set_library_root(self, root: Path) -> None:
        self._root = root
        self._logs_dir = root / ".mm" / "logs"
        self._logs_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event: str,
        *,
        level: str = "info",
        module: str = "",
        action: str = "",
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
        request_id: str = "",
    ) -> None:
        if self._logs_dir is None:
            return
        now = int(time.time())
        row = {
            "ts_epoch": now,
            "event": str(event or "runtime_event").strip() or "runtime_event",
            "level": str(level or "info").strip().lower() or "info",
            "module": str(module or "").strip(),
            "action": str(action or "").strip(),
            "message": self._trim(str(message or "").strip(), max_chars=400),
            "payload": payload or {},
            "request_id": str(request_id or "").strip(),
        }

        path = self._current_log_path(now)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def list_logs(self, limit: int = 30) -> list[Path]:
        if self._logs_dir is None or not self._logs_dir.exists():
            return []
        logs = sorted(
            self._logs_dir.glob("runtime_*.jsonl"),
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
                            "ts_epoch": int(time.time()),
                            "event": "parse_error",
                            "level": "error",
                            "message": "invalid json line",
                            "raw": raw,
                        }
                    )
        return rows

    def _current_log_path(self, epoch: int) -> Path:
        if self._logs_dir is None:
            # Fallback path; the caller guards this branch.
            return Path(f"runtime_{datetime.now().strftime('%Y%m%d')}.jsonl")
        day_stamp = datetime.fromtimestamp(epoch).strftime("%Y%m%d")
        return self._logs_dir / f"runtime_{day_stamp}.jsonl"

    def _trim(self, text: str, max_chars: int = 800) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...(truncated)"
