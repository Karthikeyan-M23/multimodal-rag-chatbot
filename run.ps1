$ErrorActionPreference = "Stop"
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
