param([ValidateSet('A','B')][string]$Pass = 'A')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$taskPython = Join-Path $taskRoot '.venv-ai-research/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython=Join-Path $taskRoot '.local/ai-venv/Scripts/python.exe' }
$taskBatch = Join-Path $taskRoot '.local/annotations/cinema-double-blind-v1'
$taskPort = if ($Pass -eq 'A') { 8767 } else { 8768 }
if (-not (Test-Path -LiteralPath (Join-Path $taskBatch "pass-$Pass-pending.jsonl"))) { throw 'Prepare the blind annotation batch first; see docs/AI_HUMAN_REVIEW.md' }
if (Get-NetTCPConnection -State Listen -LocalPort $taskPort -ErrorAction SilentlyContinue) {
    Write-Output "Port $taskPort is already in use. Open http://127.0.0.1:$taskPort if it is your annotation session."
    exit
}
$env:PYTHONUTF8='1'
$env:PYTHONPATH=Join-Path $taskRoot 'pipelines'
$taskLog = Join-Path $taskBatch "pass-$Pass-server"
Start-Process -FilePath $taskPython -ArgumentList @('-m','ml.annotation_app',".local/annotations/cinema-double-blind-v1/pass-$Pass-pending.jsonl",'--output',".local/annotations/cinema-double-blind-v1/pass-$Pass-confirmed.jsonl",'--port',"$taskPort") -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput "$taskLog.out.log" -RedirectStandardError "$taskLog.err.log"
Write-Output "Pass ${Pass}: http://127.0.0.1:$taskPort. Each pass needs a different person."
