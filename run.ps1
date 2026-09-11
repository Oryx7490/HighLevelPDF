$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledPython = "C:\Users\RGB\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = if (Test-Path -LiteralPath $BundledPython) { $BundledPython } else { "python" }

Set-Location -LiteralPath $ProjectDir
& $PythonExe ".\app.py"
