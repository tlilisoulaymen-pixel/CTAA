@echo off
echo Starting CTA-Sim PRO...

:: Navigate to backend and start uvicorn in a new window
echo Starting FastAPI Backend...
cd backend
start "CTA-Sim PRO Backend" cmd /k ".\venv\Scripts\activate && uvicorn main:app --reload --host 127.0.0.1 --port 8000"
cd ..

:: Start a simple HTTP server for the frontend in a new window
echo Starting Frontend Server...
start "CTA-Sim PRO Frontend" cmd /k "python -m http.server 8080"

:: Start Environmental Advisor Agent
echo Starting Environmental Advisor Agent API...
start "Environmental Advisor Agent" cmd /k ".\venv\Scripts\activate && python environemental_advisor_agent.py\api.py"

:: Wait for servers to initialize
echo Waiting for servers to initialize...
timeout /t 4 /nobreak > NUL

:: Open the frontend in the default browser via HTTP
echo Opening Frontend at http://localhost:8080...
start "" "http://localhost:8080/index.html"

echo.
echo ==========================================
echo  CTA-Sim PRO is running!
echo  Frontend: http://localhost:8080
echo  API Docs: http://localhost:8000/docs
echo ==========================================
echo.
