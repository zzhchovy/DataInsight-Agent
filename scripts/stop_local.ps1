param(
    [int[]]$Ports = @(8000, 8501)
)

$ErrorActionPreference = "Stop"

foreach ($Port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "No local service is listening on port $Port."
        continue
    }

    $processIds = $connections |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -and $_ -gt 0 }

    foreach ($ProcessId in $processIds) {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }
        Write-Host "Stopping port $Port process: $($process.ProcessName) (PID $ProcessId)."
        Stop-Process -Id $ProcessId -Force
    }
}
