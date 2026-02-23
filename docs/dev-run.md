# Dev Runbook

## Standard Startup

Always start from project root with the project virtual environment:

```powershell
.venv\Scripts\python.exe main.py --library "E:\downloads\videos" --api-port 8000 --web-port 5173
```

## Tag Manager 404 Troubleshooting

If Tag Manager shows `加载标签库失败` and network logs contain `404 /api/tags/*`:

1. Check API contract:

```powershell
.venv\Scripts\python.exe tools\check_tag_api_contract.py --base-url http://127.0.0.1:8000
```

2. Expected pass output contains:

```text
[result] PASS: tag API contract is complete.
```

3. If contract fails, restart with the command in **Standard Startup**.

## Quick API Validation

After startup, verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/runtime/info
Invoke-RestMethod http://127.0.0.1:8000/api/tags/library
```

Expected:

- `/api/runtime/info` -> `has_tag_routes: true`
- `/api/tags/library` -> `{ ok: true, data: { items, total } }`
