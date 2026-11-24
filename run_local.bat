@echo off
echo ========================================================
echo        Starting IntelliNotes AI Study Assistant
echo ========================================================
echo.

echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "IntelliNotes Backend (FastAPI)" cmd /k "cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Vite Frontend on http://localhost:5173 ...
start "IntelliNotes Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo.
echo Both services are launching in separate windows!
echo Open your browser at: http://localhost:5173/
echo.
pause
