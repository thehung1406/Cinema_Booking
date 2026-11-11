param([int]$Port = 55432, [switch]$WithBroker)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$taskPython = Join-Path $taskRoot '.local\ai-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .local/ai-venv first; see docs/AI_RUNBOOK.md' }
$env:PYTHONUTF8 = '1'
if ($WithBroker) { & (Join-Path $PSScriptRoot 'prepare_test_broker.ps1') }
$taskDomains = @('AI','REVIEW','CATALOG','CINEMA','BOOKING','PAYMENT','IDENTITY','NOTIFICATION','REPORTING')
foreach ($taskDomain in $taskDomains) {
    [Environment]::SetEnvironmentVariable($taskDomain+'_DATABASE_URL', "postgresql+psycopg2://cinema_test_owner@127.0.0.1:$Port/cinema_"+$taskDomain.ToLower()+'_test', 'Process')
    [Environment]::SetEnvironmentVariable($taskDomain+'_SERVICE_KEY', 'isolated-internal-service-key-32-characters-test-only', 'Process')
}
$env:AI_REDIS_URL = 'redis://127.0.0.1:6379/0'
$env:BOOKING_TMN_CODE = 'isolated-test-merchant'
$env:BOOKING_HASH_SECRET = 'isolated-test-payment-key'
$env:SOURCE_SCHEMA_DATABASE_URL = "postgresql+psycopg2://cinema_test_owner@127.0.0.1:$Port/cinema_source_test"
$env:TEST_POSTGRES_URL = $env:SOURCE_SCHEMA_DATABASE_URL
$taskPaths = @($taskRoot, (Join-Path $taskRoot 'pipelines'))
foreach ($taskDomain in @('ai','review','catalog','cinema','booking','identity','payment','reporting','notification')) {
    $taskPaths += Join-Path $taskRoot ('services/'+$taskDomain+'-service/tests')
}
$env:PYTHONPATH = $taskPaths -join ';'
Push-Location $taskRoot
try {
    & $taskPython -m pytest services/ai-service/tests services/review-service/tests services/catalog-service/tests services/cinema-service/tests services/booking-service/tests tests/ai pipelines/tests gateway/tests tests/contracts -q --import-mode=importlib --junitxml=.local/evidence/ai-tests.xml --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'AI checks failed' }
} finally { Pop-Location }
