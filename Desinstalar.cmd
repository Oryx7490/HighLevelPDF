@echo off
setlocal
set "APPDIR=%LOCALAPPDATA%\CotizacionesHighLevel"
set "DESKTOP_LINK=%USERPROFILE%\Desktop\Cotizaciones HighLevel.lnk"
set "CONFIG_LINK=%USERPROFILE%\Desktop\Configurar Cotizaciones HighLevel.lnk"

if exist "%DESKTOP_LINK%" del /Q "%DESKTOP_LINK%"
if exist "%CONFIG_LINK%" del /Q "%CONFIG_LINK%"
if exist "%APPDIR%" rmdir /S /Q "%APPDIR%"

echo Cotizaciones HighLevel fue desinstalado.
echo Los accesos directos y la configuracion local fueron eliminados.
echo Python y ReportLab no fueron eliminados porque otras aplicaciones pueden utilizarlos.
pause
endlocal
