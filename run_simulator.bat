@echo off
set "PYTHON_EXE=C:\Users\intec\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Python was not found at %PYTHON_EXE%
    pause
    exit /b 1
)

echo Starting Conveyor Event Simulator CLI...
"%PYTHON_EXE%" simulate_multi_scanner.py
pause
