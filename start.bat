@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  Dispatcher. The launchers are start_all.bat and
REM  start_viva.bat; this file exists because every README on
REM  this platform tells you to type `start.bat`.
REM
REM    start.bat            everything     -> start_all.bat
REM    start.bat viva       this module    -> start_viva.bat
REM    start.bat m20        same thing
REM    start.bat check      prerequisites, launch nothing
REM
REM  What actually runs the services: scripts\launch.ps1
REM  What you add a service to:       scripts\services.txt
REM  What closes them again:          scripts\control.ps1
REM ============================================================

if /i "%~1"=="check" goto CHECK
if /i "%~1"=="viva"  goto VIVA
if /i "%~1"=="m20"   goto VIVA
if /i "%~1"=="all"   goto ALL
if "%~1"==""         goto ALL
goto USAGE

:ALL
call "%~dp0start_all.bat"
goto :EOF

:VIVA
call "%~dp0start_viva.bat"
goto :EOF

:CHECK
call "%~dp0start_all.bat" -Check
goto :EOF

:USAGE
echo Usage: start.bat [all^|viva^|m20^|check]
exit /b 1
