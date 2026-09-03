@echo off
setlocal
title Instalador - Cotizaciones HighLevel
echo Iniciando instalacion de Cotizaciones HighLevel...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
if errorlevel 1 (
  echo.
  echo La instalacion no pudo completarse. Revisa el mensaje anterior.
  pause
  exit /b 1
)
echo.
echo Instalacion terminada correctamente.
pause
endlocal
