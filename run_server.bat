@echo off
set "PYTHON_EXE=C:\Users\intec\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Python was not found at %PYTHON_EXE%
    pause
    exit /b 1
)

echo Starting INTECH FG Scan Counter ^& Verification Server...
echo Please enter the COM Port for the scanner (e.g. COM4).
echo If you just want to run in web dashboard mode without a physical scanner, press Enter.
set /p PORT="COM Port (or press Enter for dashboard-only): "

if "%PORT%"=="" (
    "%PYTHON_EXE%" fg_scan_counter.py
) else (
    "%PYTHON_EXE%" fg_scan_counter.py --line L04 --port %PORT%
)

pause
