@echo off
setlocal
set "APPDIR=%LOCALAPPDATA%\CotizacionesHighLevel"
if not exist "%APPDIR%\config.local.json" (
  echo No se encontro la instalacion en "%APPDIR%".
  echo Ejecuta primero Instalar.cmd.
  pause
  exit /b 1
)
start "" notepad.exe "%APPDIR%\config.local.json"
endlocal
