from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.application.models import ScanProgress, ScannedFile
from app.application.ports import ProgressCallback
from app.core.scanner import collect_scan_files


class CoreScannerGateway:
    def scan(
        self, root: Path, progress: Optional[ProgressCallback] = None
    ) -> list[ScannedFile]:
        def _on_file(record, current):  # type: ignore[no-untyped-def]
            if progress is None:
                return
            progress(
                ScanProgress(
                    phase="scan_files",
                    message=f"正在扫描文件 {current}: {record.filename}",
                    current=current,
                    total=0,
                    indeterminate=True,
                    rel_path=record.rel_path,
                )
            )

        return [
            ScannedFile(
                rel_path=record.rel_path,
                filename=record.filename,
                ext=record.ext,
                size_bytes=record.size_bytes,
                mtime_epoch=record.mtime_epoch,
            )
            for record in collect_scan_files(root, on_file=_on_file)
        ]
