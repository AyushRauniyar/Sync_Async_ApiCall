@echo off
echo Starting Sync vs Async API Demo
echo ================================

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Start the API server
echo Starting API server at http://localhost:8000
echo Press Ctrl+C to stop
echo.
cd src
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000