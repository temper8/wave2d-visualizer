@echo off
rem ============================================================
rem  Wave2D GUI navigator launcher (w2d_app.py) via uv only.
rem  Usage:  run_w2d_app.bat [<data_root>]
rem  Without an argument WAVE2D_DATA_DIR (or ./data) is used.
rem
rem  The console stays open and shows startup info, uv output
rem  and error messages. For a launch without a console window
rem  use run_w2d_app.vbs.
rem ============================================================
setlocal
cd /d "%~dp0"

rem --- resolve the data root the same way the app does ---------
set "DATA_ROOT=%~1"
if not defined DATA_ROOT set "DATA_ROOT=%WAVE2D_DATA_DIR%"
if not defined DATA_ROOT set "DATA_ROOT=%CD%\data"

echo ============================================================
echo  Wave2D GUI navigator
echo ============================================================
echo  Script dir : "%CD%"
echo  Data root  : "%DATA_ROOT%"
echo ------------------------------------------------------------

where uv >nul 2>nul
if not %errorlevel%==0 goto :no_uv

echo  uv version:
uv --version
echo ------------------------------------------------------------
echo  Starting the app. The GUI runs until you close its window;
echo  errors and tracebacks (if any) will appear below.
echo ------------------------------------------------------------

uv run w2d_app.py %*
set "EXITCODE=%errorlevel%"

echo ------------------------------------------------------------
if not "%EXITCODE%"=="0" (
    echo  [ERROR] w2d_app.py exited with code %EXITCODE%.
    echo.
    pause
    endlocal & exit /b %EXITCODE%
)

echo  w2d_app.py finished normally.
endlocal & exit /b 0

:no_uv
echo  [ERROR] uv was not found in PATH.
echo.
echo  Install uv, then run this script again. Options:
echo    winget install --id astral-sh.uv -e
echo    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo.
echo  After install reopen the terminal so PATH is refreshed.
pause
endlocal & exit /b 1
