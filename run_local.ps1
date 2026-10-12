param(
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"
# Keep Python's UTF-8 log text readable in Windows PowerShell 5.1 and in the
# saved log file. The source files and requests already use UTF-8.
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONIOENCODING = "utf-8"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "main.py"
$logDir = Join-Path $root "logs"

if (-not $NoInstall -and -not (Test-Path $python)) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_local.ps1")
}
if (-not (Test-Path $python)) {
    throw "Virtual environment is missing: $python"
}
if (-not (Test-Path (Join-Path $root ".env"))) {
    throw "Missing $root\.env. Copy .env.example to .env and configure WEIBO_COOKIE first."
}

# Make sure the local cookie sync service is running: the Edge extension pushes a
# fresh WEIBO_COOKIE into .env, and main.py waits for it before retrying a dead cookie.
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "cookie_server.ps1") -Quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Cookie sync service did not start; continuing without auto refresh." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Cookie sync service did not start: $($_.Exception.Message)" -ForegroundColor Yellow
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $logDir "local_$stamp.log"

# These values are process-local and do not modify the user's .env file.
$env:SEARCH_SLEEP_MIN = "1"
$env:SEARCH_SLEEP_MAX = "1"
$env:GENERAL_SLEEP_MIN = "1"
$env:GENERAL_SLEEP_MAX = "1"
$env:PROBE_SLEEP_SECONDS = "1"
$env:LOCAL_MODEL = "1"
$env:LOCAL_MODEL_NAME = "C:\Users\Lenovo\Downloads\Erlangshen-Roberta-110M-Sentiment"
$env:LOCAL_MODEL_OFFLINE = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:LOCAL_MODEL_BATCH_SIZE = "8"
$env:MAX_PAGES = "1"
$env:REPORT_URL = "https://kiwi-lilo.github.io/aliyun-opinion-report/"

# Ensure application settings are loaded from this project's .env for scheduled
# tasks, whose environment does not inherit variables from an interactive shell.
foreach ($line in Get-Content (Join-Path $root ".env" -Encoding UTF8) -ErrorAction Stop) {
    $entry = $line.Trim()
    if (-not $entry -or $entry.StartsWith("#") -or $entry.IndexOf("=") -lt 1) { continue }
    $parts = $entry -split "=", 2
    $name = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Push-Location $root
try {
    Write-Host "Starting local monitoring. Log: $log"
    # Python logging writes warnings to stderr. Run through cmd so PowerShell
    # receives one ordinary output stream instead of raising NativeCommandError.
    $command = 'chcp 65001>nul & "{0}" "{1}" 2>&1' -f $python, $main
    cmd.exe /d /s /c $command | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($code -ne 0) {
    Write-Host "Monitoring failed with exit code $code. See $log" -ForegroundColor Red
    exit $code
}
Write-Host "Monitoring completed. Report files are in $root and $root\public."
