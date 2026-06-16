param(
    [string]$HostAddress = "127.0.0.1",
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [string]$VenvPython = "D:\codex\DataInsight-Agent\.venv\Scripts\python.exe",
    [string]$LogDir = "D:\codex\DataInsight-Agent\logs"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LocalVenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Resolve-Python {
    if (Test-Path $VenvPython) {
        return $VenvPython
    }
    if (Test-Path $LocalVenvPython) {
        return $LocalVenvPython
    }
    return "python"
}

function Get-ListeningProcess {
    param([int]$Port)
    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 25
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 700
        }
    }
    return $false
}

$Python = Resolve-Python
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$ApiUrl = "http://${HostAddress}:${ApiPort}"
$UiUrl = "http://${HostAddress}:${UiPort}"

$ApiProcess = Get-ListeningProcess -Port $ApiPort
if ($ApiProcess) {
    Write-Host "FastAPI already running on $ApiUrl (PID $($ApiProcess.OwningProcess))."
}
else {
    Write-Host "Starting FastAPI on $ApiUrl ..."
    Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", "$ApiPort") `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "fastapi_$Stamp.out.log") `
        -RedirectStandardError (Join-Path $LogDir "fastapi_$Stamp.err.log")
}

if (-not (Wait-HttpOk -Url "$ApiUrl/docs" -TimeoutSeconds 25)) {
    Write-Warning "FastAPI did not become ready. Check logs in $LogDir."
}

$UiProcess = Get-ListeningProcess -Port $UiPort
if ($UiProcess) {
    Write-Host "Streamlit already running on $UiUrl (PID $($UiProcess.OwningProcess))."
}
else {
    Write-Host "Starting Streamlit on $UiUrl ..."
    Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            "-m", "streamlit", "run", "frontend\streamlit_app.py",
            "--server.address", $HostAddress,
            "--server.port", "$UiPort",
            "--server.headless", "true"
        ) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "streamlit_$Stamp.out.log") `
        -RedirectStandardError (Join-Path $LogDir "streamlit_$Stamp.err.log")
}

if (-not (Wait-HttpOk -Url $UiUrl -TimeoutSeconds 25)) {
    Write-Warning "Streamlit did not become ready. Check logs in $LogDir."
}

Write-Host ""
Write-Host "DataInsight-Agent is ready:"
Write-Host "  FastAPI docs : $ApiUrl/docs"
Write-Host "  Streamlit UI : $UiUrl"
Write-Host "  Logs         : $LogDir"
