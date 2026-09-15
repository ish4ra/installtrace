@echo off
cd /d "%~dp0"
py -3 -m installtrace
if errorlevel 1 pause
