from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class DefaultFileOpener:
    def open_file(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
            return
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
            return
        subprocess.run(["xdg-open", str(path)], check=False)
