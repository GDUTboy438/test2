from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Ensure package imports work when running `python tools/smoke_tag_mining.py`.
_tool_file = Path(__file__).resolve()
_project_root = _tool_file.parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.application.library_service import LibraryService
from app.application.models import ScannedFile
from app.infrastructure.file_opener import DefaultFileOpener
from app.infrastructure.library_repository import SqliteLibraryRepository
from app.infrastructure.media_indexer import FfmpegMediaIndexer
from app.infrastructure.scan_logger import JsonlScanLogger
from app.infrastructure.scanner_gateway import CoreScannerGateway
from app.infrastructure.tag_mining_logger import JsonlTagMiningLogger


def main() -> int:
    repo = SqliteLibraryRepository()
    scan_logger = JsonlScanLogger()
    tag_logger = JsonlTagMiningLogger()
    service = LibraryService(
        repository=repo,
        scanner=CoreScannerGateway(),
        media_indexer=FfmpegMediaIndexer(logger=scan_logger),
        opener=DefaultFileOpener(),
        scan_logger=scan_logger,
        tag_mining_logger=tag_logger,
    )

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        try:
            service.select_library(root)
            repo.apply_scan(
                [
                    ScannedFile(
                        rel_path="a/hello_cat_video.mp4",
                        filename="hello_cat_video.mp4",
                        ext="mp4",
                        size_bytes=100,
                        mtime_epoch=1,
                    ),
                    ScannedFile(
                        rel_path="a/cute_cat_clip.mp4",
                        filename="cute_cat_clip.mp4",
                        ext="mp4",
                        size_bytes=101,
                        mtime_epoch=1,
                    ),
                    ScannedFile(
                        rel_path="b/dog_cat_trailer.mp4",
                        filename="dog_cat_trailer.mp4",
                        ext="mp4",
                        size_bytes=102,
                        mtime_epoch=1,
                    ),
                ]
            )
            service.rebuild_index()
            result = service.mine_title_tags(min_df=2, max_tags_per_video=5, max_terms=50)
            print(
                "mine_result",
                result.processed_videos,
                result.selected_terms,
                result.tagged_videos,
                result.created_relations,
            )
            print("tag_logs", len(service.list_tag_mining_logs()))
        finally:
            # Must close before TemporaryDirectory cleanup, otherwise Windows may lock library.db.
            service.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
