from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

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


def fetch_json(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
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


def check_contract(base_url: str) -> tuple[int, list[str]]:
    lines: list[str] = []
    runtime = fetch_json(f"{base_url}/api/runtime/info")
    if runtime and isinstance(runtime.get("data"), dict):
        data = runtime["data"]
        app_title = str(data.get("app_title") or "")
        has_tag_routes = bool(data.get("has_tag_routes"))
        missing = [str(item) for item in list(data.get("missing_tag_routes") or [])]
        lines.append(f"[runtime] title={app_title or 'unknown'} has_tag_routes={has_tag_routes}")
        if has_tag_routes:
            lines.append("[result] PASS: tag API contract is complete.")
            return 0, lines
        lines.append(f"[result] FAIL: missing routes: {', '.join(missing) or '(unknown)'}")
        lines.append("[hint] Restart with project venv:")
        lines.append("       .venv\\Scripts\\python.exe main.py --library \"E:\\downloads\\videos\"")
        return 1, lines

    openapi = fetch_json(f"{base_url}/openapi.json")
    if not openapi:
        lines.append("[result] ERROR: API is unreachable or returned invalid JSON.")
        lines.append("[hint] Start API first:")
        lines.append("       .venv\\Scripts\\python.exe main.py --api-only --library \"E:\\downloads\\videos\"")
        return 2, lines

    info = openapi.get("info")
    paths = openapi.get("paths")
    app_title = str(info.get("title") if isinstance(info, dict) else "")
    path_set = set(paths.keys()) if isinstance(paths, dict) else set()
    missing = [route for route in REQUIRED_TAG_ROUTES if route not in path_set]

    lines.append(f"[openapi] title={app_title or 'unknown'} path_count={len(path_set)}")
    if app_title != "Portable Video Manager API":
        lines.append("[result] ERROR: target service is not Portable Video Manager API.")
        return 3, lines
    if missing:
        lines.append(f"[result] FAIL: missing routes: {', '.join(missing)}")
        lines.append("[hint] You likely started an old API instance. Restart main.py from this repo.")
        return 1, lines

    lines.append("[result] PASS: tag API contract is complete.")
    return 0, lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Check /api/tags route contract on a running API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = str(args.base_url).rstrip("/")
    code, lines = check_contract(base_url)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
