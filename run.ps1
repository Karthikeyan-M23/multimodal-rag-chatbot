$ErrorActionPreference = "Stop"
.\.venv\Scripts\Activate.ps1

# Open the browser shortly after the server starts (model imports take a few seconds).
Start-Job { Start-Sleep -Seconds 8; Start-Process "http://127.0.0.1:8000" } | Out-Null

uvicorn backend.main:app --reload
