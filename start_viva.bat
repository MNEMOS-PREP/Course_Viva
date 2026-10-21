@echo off
REM ============================================================
REM  M20 - Course Viva, on its own.
REM
REM  This module's services only (PORTS.txt: API 8120, web 5220).
REM  Nothing else is needed: the course library browses,
REM  imports and searches with no other module running.
REM
REM  Usage:  start_viva.bat          launch M20
REM          start_viva.bat -Check   verify prerequisites only
REM ============================================================

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" -Only m20 -Title "M20 - Course Viva" %*
