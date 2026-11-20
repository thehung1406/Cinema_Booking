$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot '../../scripts/ai/start_chat.ps1'
$global:chatTestProvider = 'openai'
$global:chatTestWarmups = @()
function docker {
    $global:LASTEXITCODE = 0
    if ($args -contains 'config') {
        return (@{services=@{'ai-service'=@{environment=@{
            AI_LLM_PROVIDER=$global:chatTestProvider; AI_LLM_MODEL='fixture-model';
            AI_LLM_BASE_URL='http://127.0.0.1:11434'
        }}}} | ConvertTo-Json -Depth 8 -Compress)
    }
}
function Invoke-WebRequest { return @{StatusCode=200} }
function Test-Path { return $true }
function New-Item { }
function Invoke-RestMethod {
    param($Uri,$Method,$Body,$ContentType,$TimeoutSec)
    $global:chatTestWarmups += @{uri=$Uri; body=($Body | ConvertFrom-Json)}
}
function Start-Process { throw 'Tests must not start processes' }
foreach ($global:chatTestProvider in @('openai','disabled','ollama')) {
    $global:chatTestWarmups = @()
    & $scriptPath | Out-Null
    $expected = if ($global:chatTestProvider -eq 'ollama') { 1 } else { 0 }
    if ($global:chatTestWarmups.Count -ne $expected) { throw "Unexpected warmup count for $global:chatTestProvider" }
    if ($expected -and ($global:chatTestWarmups[0].body.model -ne 'fixture-model' -or
        $global:chatTestWarmups[0].uri -ne 'http://127.0.0.1:11434/api/chat')) { throw 'Ollama ignored configured model/origin' }
}
Write-Output 'Startup provider checks passed: openai, disabled, ollama.'
