@echo off
echo Running API Quick Test
echo ======================

REM Activate virtual environment
call venv\Scripts\activate

REM Run the test
python test_api.py

pause