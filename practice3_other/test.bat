@echo off
cd /d "%~dp0"
python nnn.py --config config.xml --vfs vfs --startup start.txt
pause
