$ErrorActionPreference = "Stop"

$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installDir = Join-Path $env:LOCALAPPDATA "CotizacionesHighLevel"
$logPath = Join-Path $env:TEMP "CotizacionesHighLevel-instalacion.log"

function Write-Step([string]$message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) $message"
}

function Find-Python {
    $candidates = @()
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike "*WindowsApps*") {
        $candidates += $pythonCommand.Source
    }
    $programPython = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path -LiteralPath $programPython) {
        $candidates += Get-ChildItem -LiteralPath $programPython -Directory -Filter "Python*" -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "python.exe" }
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate) {
            try {
                $version = & $candidate -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $version) { return $candidate }
            } catch { }
        }
    }
    return $null
}

try {
    Set-Content -LiteralPath $logPath -Value "Cotizaciones HighLevel - registro de instalacion"
    Write-Step "Comprobando Python"
    $pythonExe = Find-Python

    if (-not $pythonExe) {
        Write-Step "Python no esta instalado. Instalando Python 3.13 para el usuario actual"
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $winget) {
            throw "Windows Package Manager (winget) no esta disponible. Instala App Installer desde Microsoft Store y vuelve a ejecutar Instalar.cmd."
        }
        & $winget.Source install --exact --id Python.Python.3.13 --scope user --silent `
            --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) {
            throw "winget no pudo instalar Python. Codigo de salida: $LASTEXITCODE"
        }
        $pythonExe = Find-Python
        if (-not $pythonExe) {
            $expectedPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
            if (Test-Path -LiteralPath $expectedPython) { $pythonExe = $expectedPython }
        }
        if (-not $pythonExe) {
            throw "Python fue instalado, pero no fue posible localizar python.exe. Reinicia Windows y ejecuta nuevamente Instalar.cmd."
        }
    } else {
        Write-Host "Python encontrado: $pythonExe"
    }

    Write-Step "Instalando o actualizando ReportLab"
    & $pythonExe -m pip install --disable-pip-version-check --user --upgrade reportlab
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible instalar ReportLab. Revisa la conexion a Internet o el proxy de la red."
    }

    Write-Step "Copiando la aplicacion"
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $installDir "static") | Out-Null
    Copy-Item -LiteralPath (Join-Path $sourceDir "app.py") -Destination $installDir -Force
    Copy-Item -LiteralPath (Join-Path $sourceDir "demo-estimates.json") -Destination $installDir -Force
    Copy-Item -LiteralPath (Join-Path $sourceDir "static\index.html") -Destination (Join-Path $installDir "static") -Force
    Copy-Item -LiteralPath (Join-Path $sourceDir "LEEME.txt") -Destination $installDir -Force
    Copy-Item -LiteralPath (Join-Path $sourceDir "Desinstalar.cmd") -Destination $installDir -Force

    $configPath = Join-Path $installDir "config.local.json"
    if (-not (Test-Path -LiteralPath $configPath)) {
        Copy-Item -LiteralPath (Join-Path $sourceDir "config.empty.json") -Destination $configPath
        Write-Host "Se creo config.local.json vacio."
    } else {
        Write-Host "Se conservo el config.local.json existente."
    }

    $launcherPath = Join-Path $installDir "Iniciar Cotizaciones HighLevel.cmd"
    $launcher = @"
@echo off
title Cotizaciones HighLevel
cd /d "$installDir"
"$pythonExe" "$installDir\app.py"
if errorlevel 1 pause
"@
    Set-Content -LiteralPath $launcherPath -Value $launcher -Encoding ASCII

    $configurePath = Join-Path $installDir "Configurar credenciales.cmd"
    $configure = @"
@echo off
start "" notepad.exe "$configPath"
"@
    Set-Content -LiteralPath $configurePath -Value $configure -Encoding ASCII

    Write-Step "Creando accesos directos"
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    $startShortcut = $shell.CreateShortcut((Join-Path $desktop "Cotizaciones HighLevel.lnk"))
    $startShortcut.TargetPath = $launcherPath
    $startShortcut.WorkingDirectory = $installDir
    $startShortcut.Description = "Consultar Estimates y generar cotizaciones PDF"
    $startShortcut.Save()
    $configShortcut = $shell.CreateShortcut((Join-Path $desktop "Configurar Cotizaciones HighLevel.lnk"))
    $configShortcut.TargetPath = $configurePath
    $configShortcut.WorkingDirectory = $installDir
    $configShortcut.Description = "Editar Location ID y Private Integration Token"
    $configShortcut.Save()

    Write-Step "Instalacion completada"
    Write-Host "Carpeta instalada: $installDir" -ForegroundColor Green
    Write-Host "No fue necesario cambiar permanentemente la Execution Policy." -ForegroundColor Green
    Write-Host "Se abrira config.local.json para capturar las credenciales." -ForegroundColor Yellow
    Start-Process notepad.exe -ArgumentList $configPath
} catch {
    $message = $_.Exception.Message
    Write-Host "`nERROR: $message" -ForegroundColor Red
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) ERROR: $message"
    Write-Host "Registro: $logPath"
    exit 1
}
