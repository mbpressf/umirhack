param(
    [int]$Port = 8765,
    [switch]$Rebuild,
    [ValidateSet("index", "how_it_works")]
    [string]$Page = "index"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BuildScript = Join-Path $PSScriptRoot "build_visual_report.py"
$ServeScript = Join-Path $PSScriptRoot "serve_visual_report.py"
$LatestDir = Join-Path $PSScriptRoot "output\latest"
$PageFile = if ($Page -eq "how_it_works") { "how_it_works.html" } else { "index.html" }
$IndexPath = Join-Path $LatestDir $PageFile
$Url = "http://127.0.0.1:$Port/$PageFile"

if (-not (Test-Path $PythonExe)) {
    throw "Не найден Python в .venv: $PythonExe"
}

if ($Rebuild -or -not (Test-Path $IndexPath)) {
    & $PythonExe $BuildScript
}

try {
    $null = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 2
}
catch {
    Start-Process -FilePath $PythonExe -ArgumentList $ServeScript, "--port", $Port -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
}

Write-Host "HTML report:" $IndexPath
Write-Host "Browser URL:" $Url
Start-Process $Url | Out-Null
