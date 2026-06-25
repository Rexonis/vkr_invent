@echo off
set VITE_HTTPS=1
cd /d "%~dp0..\frontend"
node.exe node_modules\vite\bin\vite.js --host 0.0.0.0 --port 5173
