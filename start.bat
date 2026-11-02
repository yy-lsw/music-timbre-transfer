@echo off
cd /d "%~dp0"

start "Backend  API (port 5000)" powershell -NoExit -ExecutionPolicy Bypass -Command "$env:SEEDVC_HF_ENDPOINT='https://hf-mirror.com'; Set-Location '%~dp0'; python -m backend.app"

start "Frontend UI (port 3000)" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%~dp0frontend'; npm.cmd run dev"

echo.
echo Two windows have been opened:
echo   - Backend API on http://127.0.0.1:5000
echo   - Frontend UI on http://localhost:3000
echo Open http://localhost:3000 in your browser once the frontend is ready.
echo.
echo Keep both windows open while you use the app.
pause
