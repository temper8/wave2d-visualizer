@echo off
rem ============================================================
rem  Wave2D GUI navigator launcher (w2d_app.py) via uv only.
rem  Usage:  run_w2d_app.bat [<data_root>]
rem  Without an argument WAVE2D_DATA_DIR (or ./data) is used.
rem ============================================================
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if %errorlevel%==0 goto :run

echo [ERROR] uv was not found in PATH.
echo.
echo Install uv, then run this script again. Options:
echo   winget install --id astral-sh.uv -e
echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo.
echo After install reopen the terminal so PATH is refreshed.
pause
endlocal & exit /b 1

:run
uv run w2d_app.py %*
set "EXITCODE=%errorlevel%"
if not "%EXITCODE%"=="0" (
    echo.
    echo [ERROR] w2d_app.py exited with code %EXITCODE%.
    pause
)
endlocal & exit /b %EXITCODE%
