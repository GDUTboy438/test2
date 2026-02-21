from __future__ import annotations

import sys
from pathlib import Path

# Ensure package imports work when running `python app/main.py`.
_app_dir = Path(__file__).resolve().parent
_project_root = _app_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.ui.bootstrap import bootstrap_windows_dll_paths

bootstrap_windows_dll_paths()

from PySide6.QtWidgets import QApplication

from app.application.library_service import LibraryService
from app.infrastructure.file_opener import DefaultFileOpener
from app.infrastructure.embedding_model import LocalSentenceTransformerModel
from app.infrastructure.reranker_model import LocalBgeRerankerModel
from app.infrastructure.library_repository import SqliteLibraryRepository
from app.infrastructure.media_indexer import FfmpegMediaIndexer
from app.infrastructure.scanner_gateway import CoreScannerGateway
from app.infrastructure.scan_logger import JsonlScanLogger
from app.infrastructure.tag_mining_logger import JsonlTagMiningLogger
from app.infrastructure.tokenizer_pkuseg import PkusegTokenizer
from app.ui.main_window import MainWindow


def main() -> int:
    scan_logger = JsonlScanLogger()
    tag_logger = JsonlTagMiningLogger()
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
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        tokenizer=tokenizer,
    )
    app = QApplication(sys.argv)
    window = MainWindow(service=service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
