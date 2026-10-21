@echo off
REM ============================================================
REM  Everything.
REM
REM  Every service in scripts\services.txt, plus any sibling
REM  module repo declared in module.json `depends_on` that is
REM  checked out next to this one and has scripts\launch.ps1
REM  (M04 Memory, M11 Voice_Engine). Both are optional: the
REM  library runs without them.
REM
REM  Usage:  start_all.bat          launch everything
REM          start_all.bat -Check   verify prerequisites only
REM ============================================================

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" -All -Title "AI Interviewer - all services" %*
