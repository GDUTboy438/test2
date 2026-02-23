from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
REQUIRED_TAG_ROUTES = (
    "/api/tags/library",
    "/api/tags/library/create",
    "/api/tags/library/delete",
    "/api/tags/candidates",
    "/api/tags/candidates/approve",
    "/api/tags/candidates/reject",
    "/api/tags/candidates/blacklist",
    "/api/tags/candidates/requeue",
    "/api/tags/candidates/clear-pending",
    "/api/tags/blacklist",
)


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


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.6)
        return sock.connect_ex((host, port)) == 0


def _fetch_json(url: str, timeout: float = 1.2) -> Optional[dict]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _probe_api_contract(port: int) -> dict[str, object]:
    base_url = f"http://127.0.0.1:{port}"
    runtime_payload = _fetch_json(f"{base_url}/api/runtime/info")
    if runtime_payload:
        runtime_data = runtime_payload.get("data")
        if isinstance(runtime_data, dict):
            missing = runtime_data.get("missing_tag_routes")
            missing_routes = [str(item) for item in list(missing or [])]
            app_title = str(runtime_data.get("app_title") or "")
            has_tag_routes = bool(runtime_data.get("has_tag_routes"))
            return {
                "reachable": True,
                "source": "runtime",
                "is_pvm": app_title == "Portable Video Manager API",
                "has_tag_routes": has_tag_routes,
                "missing_tag_routes": missing_routes,
                "app_title": app_title,
            }

    openapi_payload = _fetch_json(f"{base_url}/openapi.json")
    if not openapi_payload:
        return {
            "reachable": False,
            "source": "none",
            "is_pvm": False,
            "has_tag_routes": False,
            "missing_tag_routes": list(REQUIRED_TAG_ROUTES),
            "app_title": "",
        }

    info = openapi_payload.get("info")
    paths = openapi_payload.get("paths")
    app_title = str(info.get("title") if isinstance(info, dict) else "")
    path_set = set(paths.keys()) if isinstance(paths, dict) else set()
    missing_routes = [
        route
        for route in REQUIRED_TAG_ROUTES
        if route not in path_set
    ]
    is_pvm = app_title == "Portable Video Manager API"
    return {
        "reachable": True,
        "source": "openapi",
        "is_pvm": is_pvm,
        "has_tag_routes": is_pvm and len(missing_routes) == 0,
        "missing_tag_routes": missing_routes,
        "app_title": app_title,
    }


def _list_listening_pids_windows(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        tokens = line.split()
        if len(tokens) < 5:
            continue
        if tokens[0].upper() != "TCP":
            continue
        local_addr = tokens[1]
        state = tokens[3].upper()
        if state != "LISTENING":
            continue
        if not local_addr.endswith(f":{port}"):
            continue
        try:
            pid = int(tokens[4])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return sorted(pids)


def _kill_process_tree_windows(pid: int) -> bool:
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _find_spawn_children_pids_windows(parent_pid: int) -> list[int]:
    query = (
        "name='python.exe' and "
        f"commandline like '%spawn_main(parent_pid={parent_pid}%'"
    )
    result = subprocess.run(
        ["wmic", "process", "where", query, "get", "ProcessId"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        text = line.strip()
        if not text.isdigit():
            continue
        pid = int(text)
        if pid > 0:
            pids.add(pid)
    return sorted(pids)


def _wait_port_released(port: int, timeout_sec: float = 8.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not _is_port_in_use(port):
            return True
        time.sleep(0.2)
    return not _is_port_in_use(port)


def _ensure_api_port_available(port: int) -> tuple[bool, bool]:
    if not _is_port_in_use(port):
        return True, False

    probe = _probe_api_contract(port)
    is_pvm = bool(probe.get("is_pvm"))
    has_tag_routes = bool(probe.get("has_tag_routes"))
    missing = list(probe.get("missing_tag_routes") or [])
    app_title = str(probe.get("app_title") or "")
    source = str(probe.get("source") or "")
    print(f"[dev] API port {port} is already in use.")
    print(f"[dev] Existing service probe: source={source} title={app_title or 'unknown'}")

    if is_pvm and not has_tag_routes:
        if os.name != "nt":
            print("[dev] Detected old PVM API but automatic takeover is implemented for Windows only.")
            print(f"[dev] Missing tag routes: {', '.join(missing) or '(unknown)'}")
            return False, False

        pids = _list_listening_pids_windows(port)
        if not pids:
            print("[dev] Could not resolve listening PID for occupied API port.")
            return False, False

        print(f"[dev] Detected old PVM API missing tag routes, taking over port {port}.")
        print(f"[dev] Missing tag routes: {', '.join(missing) or '(none)'}")
        for pid in pids:
            ok = _kill_process_tree_windows(pid)
            fallback_killed: list[int] = []
            if not ok:
                for child_pid in _find_spawn_children_pids_windows(pid):
                    if _kill_process_tree_windows(child_pid):
                        fallback_killed.append(child_pid)
                if fallback_killed:
                    ok = True
            status = "ok" if ok else "failed"
            if fallback_killed:
                print(
                    f"[dev] taskkill pid={pid}: {status} "
                    f"(fallback child kill: {', '.join(str(item) for item in fallback_killed)})"
                )
            else:
                print(f"[dev] taskkill pid={pid}: {status}")

        if not _wait_port_released(port):
            print(f"[dev] API port {port} is still occupied after takeover attempt.")
            return False, False
        return True, True

    if is_pvm and has_tag_routes:
        print("[dev] API port is already occupied by a current PVM API instance.")
        print("[dev] Stop that process first, or choose another --api-port.")
        return False, False

    print("[dev] API port is occupied by a non-PVM service or unrecognized API.")
    print("[dev] Refusing to kill unknown process automatically.")
    print("[dev] Use another --api-port or free this port manually.")
    return False, False


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
    api_takeover_performed = False

    print(f"[dev] Python: {sys.executable}")
    print(f"[dev] CWD: {PROJECT_ROOT}")

    if not args.web_only:
        available, takeover = _ensure_api_port_available(args.api_port)
        api_takeover_performed = takeover
        print(f"[dev] API port takeover: {'yes' if api_takeover_performed else 'no'}")
        if not available:
            return 1

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
