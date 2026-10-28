# Windows equivalent of `make dev`: API on :8000 and the UI on :5173, each in its own window.
$root = $PSScriptRoot
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\backend'; .\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\frontend'; npm run dev"
Write-Host "Starting... open http://localhost:5173 (API docs: http://localhost:8000/docs)"
