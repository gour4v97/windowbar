@echo off
REM Double-click to install Winyard. Extra flags are passed through, e.g.  setup.bat --uninstall
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0setup_winyard.py" %*
    goto :done
)
where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0setup_winyard.py" %*
    goto :done
)
echo Python 3.9+ was not found.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again.
:done
echo.
pause
