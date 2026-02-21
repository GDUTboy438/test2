from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


LIB_DIRNAME = ".mm"
LIB_FILENAME = "library.json"
LIB_VERSION = 1


def _now_epoch() -> int:
    return int(time.time())


@dataclass
class LibraryPaths:
    root: Path
    lib_dir: Path
    lib_file: Path


class LibraryStore:
    def __init__(self, root_dir: Path) -> None:
        self.paths = LibraryPaths(
            root=root_dir,
            lib_dir=root_dir / LIB_DIRNAME,
            lib_file=root_dir / LIB_DIRNAME / LIB_FILENAME,
        )
        self.data: Dict[str, Any] = {}

    def load_or_create(self) -> None:
        self.paths.lib_dir.mkdir(parents=True, exist_ok=True)
        if self.paths.lib_file.exists():
            with self.paths.lib_file.open("r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            now = _now_epoch()
            self.data = {
                "version": LIB_VERSION,
                "root_id": str(uuid.uuid4()),
                "created_at": now,
                "updated_at": now,
                "videos": {},
            }
            self.save_atomic()

        if "videos" not in self.data or not isinstance(self.data["videos"], dict):
            self.data["videos"] = {}

    def save_atomic(self) -> None:
        self.data["updated_at"] = _now_epoch()
        tmp_path = self.paths.lib_file.with_suffix(self.paths.lib_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.paths.lib_file)

    def get_videos(self) -> Dict[str, Any]:
        return self.data.get("videos", {})
