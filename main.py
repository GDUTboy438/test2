from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"


def _detect_package_manager(web_dir: Path) -> str:
    if (web_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (web_dir / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _resolve_tool(name: str) -> Optional[str]:
    return (
        shutil.which(name)
        or shutil.which(f"{name}.cmd")
        or shutil.which(f"{name}.exe")
    )


def _spawn(cmd: list[str], cwd: Path, env: Optional[dict[str, str]] = None) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=None,
        stderr=None,
        stdin=None,
    )


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
    except Exception:
        return
    try:
        proc.wait(timeout=8)
        return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _wait_for_exit(procs: Iterable[subprocess.Popen]) -> int:
    try:
        while True:
            for proc in procs:
                code = proc.poll()
                if code is not None:
                    return code
            time.sleep(0.4)
    except KeyboardInterrupt:
        return 0


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Dev entrypoint: start API (FastAPI) + Web (Vite)."
    )
    parser.add_argument(
        "--library",
        help="Library root path (sets PVM_LIBRARY_ROOT).",
        default=os.environ.get("PVM_LIBRARY_ROOT", "")
        or os.environ.get("PVM_LIBRARY_PATH", ""),
    )
    parser.add_argument("--api-host", default="0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=5173)
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--web-only", action="store_true")
    args = parser.parse_args()

    if args.api_only and args.web_only:
        print("Cannot use --api-only and --web-only together.")
        return 2

    env = os.environ.copy()
    if args.library:
        env["PVM_LIBRARY_ROOT"] = args.library

    procs: list[subprocess.Popen] = []

    if not args.web_only:
        api_cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.web_api:app",
            "--reload",
            "--host",
            args.api_host,
            "--port",
            str(args.api_port),
        ]
        print(f"[dev] API: {' '.join(api_cmd)}")
        procs.append(_spawn(api_cmd, PROJECT_ROOT, env=env))

    if not args.api_only:
        if not WEB_DIR.exists():
            print(f"[dev] Web directory not found: {WEB_DIR}")
            return 1
        manager = _detect_package_manager(WEB_DIR)
        tool = _resolve_tool(manager)
        if not tool:
            print(f"[dev] {manager} not found in PATH.")
            return 1
        if not (WEB_DIR / "node_modules").exists():
            print("[dev] node_modules not found. Run:")
            print(f"  cd {WEB_DIR}")
            print(f"  {tool} install")
            return 1
        if manager == "pnpm":
            web_cmd = [tool, "dev", "--", "--port", str(args.web_port)]
        elif manager == "yarn":
            web_cmd = [tool, "dev", "--port", str(args.web_port)]
        else:
            web_cmd = [tool, "run", "dev", "--", "--port", str(args.web_port)]
        print(f"[dev] Web: {' '.join(web_cmd)}")
        procs.append(_spawn(web_cmd, WEB_DIR, env=env))

    exit_code = _wait_for_exit(procs)
    for proc in procs:
        _terminate(proc)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
