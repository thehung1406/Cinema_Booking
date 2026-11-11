param([switch]$Build)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$taskRuntime = Join-Path $taskRoot '.local\runtime'
New-Item -ItemType Directory -Force -Path $taskRuntime | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot '.env.microservices'))) {
    throw 'Private runtime config is missing. Restore it together with the matching owner volumes; see docs/AI_LOCAL_CHAT.md.'
}
& docker version --format '{{.Server.Version}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop, then rerun this script.' }

function Test-ChatEndpoint([string]$Uri) {
    try { $taskResponse = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3; return $taskResponse.StatusCode -eq 200 } catch { return $false }
}
if (-not (Test-ChatEndpoint 'http://127.0.0.1:11434/api/tags')) {
    $taskOllama = Join-Path $taskRoot '.local\ollama\ollama.exe'
    if (-not (Test-Path -LiteralPath $taskOllama)) { throw 'Local Ollama is missing; see docs/AI_LOCAL_CHAT.md.' }
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    $env:OLLAMA_MODELS = Join-Path $taskRoot '.local\ollama-models'
    Start-Process -FilePath $taskOllama -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRuntime 'ollama.log') -RedirectStandardError (Join-Path $taskRuntime 'ollama-errors.log') | Out-Null
    $taskUntil = (Get-Date).AddSeconds(30)
    while (-not (Test-ChatEndpoint 'http://127.0.0.1:11434/api/tags')) {
        if ((Get-Date) -gt $taskUntil) { throw 'Ollama did not start; inspect .local/runtime/ollama-errors.log.' }
        Start-Sleep -Milliseconds 300
    }
}
Write-Output 'Warming up qwen3:4b before enabling chat requests...'
$taskPayload = @{ model='qwen3:4b'; stream=$false; think=$false; keep_alive='30m'; options=@{num_predict=1}; messages=@(@{role='user';content='Ready?'}) } | ConvertTo-Json -Depth 6 -Compress
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/chat' -Method Post -Body $taskPayload -ContentType 'application/json' -TimeoutSec 180 | Out-Null

Push-Location $taskRoot
try {
    $taskServices = @('gateway','identity-service','catalog-service','cinema-service','booking-service','review-service','ai-service','payment-service','reporting-service')
    if ($Build) {
        & docker compose --env-file .env.microservices build @taskServices
        if ($LASTEXITCODE -ne 0) { throw 'Owner image build failed.' }
    }
    & docker compose --env-file .env.microservices up -d --no-build @taskServices cinema-worker
    if ($LASTEXITCODE -ne 0) { throw 'Owner API startup failed.' }
    $taskUntil = (Get-Date).AddSeconds(60)
    while (-not (Test-ChatEndpoint 'http://127.0.0.1:8080/health/ready')) {
        if ((Get-Date) -gt $taskUntil) { throw 'Gateway dependencies are not ready. This script does not reset or seed databases.' }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-ChatEndpoint 'http://127.0.0.1:8082/health/ready')) { throw 'AI Service is not ready.' }
    if (-not (Test-ChatEndpoint 'http://127.0.0.1:5173')) {
        $taskWeb = Join-Path $taskRoot 'apps\web'
        if (-not (Test-Path -LiteralPath (Join-Path $taskWeb 'node_modules\vite\bin\vite.js'))) {
            throw 'Run npm ci inside apps/web first.'
        }
        $taskNode = (Get-Command node).Source
        Start-Process -FilePath $taskNode -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory $taskWeb -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRuntime 'web.log') -RedirectStandardError (Join-Path $taskRuntime 'web-errors.log') | Out-Null
        $taskUntil = (Get-Date).AddSeconds(20)
        while (-not (Test-ChatEndpoint 'http://127.0.0.1:5173')) {
            if ((Get-Date) -gt $taskUntil) { throw 'Web did not start; inspect .local/runtime/web-errors.log.' }
            Start-Sleep -Milliseconds 300
        }
    }
    Write-Output 'Chat application ready: http://127.0.0.1:5173'
    Write-Output 'Use an existing account or the private demo credentials in .local/runtime/demo-access.json.'
} finally { Pop-Location }
