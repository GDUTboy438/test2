from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional


VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv"}


@dataclass(frozen=True)
class ScanFileRecord:
    rel_path: str
    filename: str
    ext: str
    size_bytes: int
    mtime_epoch: int


def _iter_video_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if ".mm" in path.parts:
            continue
        if path.suffix.lower() in VIDEO_EXTS:
            yield path


def collect_scan_files(
    root: Path, on_file: Optional[Callable[[ScanFileRecord, int], None]] = None
) -> List[ScanFileRecord]:
    records: List[ScanFileRecord] = []
    current = 0
    for file_path in _iter_video_files(root):
        stat = file_path.stat()
        rel_path = file_path.relative_to(root).as_posix()
        record = ScanFileRecord(
            rel_path=rel_path,
            filename=file_path.name,
            ext=file_path.suffix.lower().lstrip("."),
            size_bytes=int(stat.st_size),
            mtime_epoch=int(stat.st_mtime),
        )
        records.append(record)
        current += 1
        if on_file is not None:
            on_file(record, current)
    records.sort(key=lambda x: x.rel_path.lower())
    return records
