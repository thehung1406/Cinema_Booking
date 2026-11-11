# Isolated broker only. No production vhost, notification consumer or email worker.
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$taskName = 'cinema-ai-rabbitmq-test'
$taskPurpose = docker inspect $taskName --format '{{index .Config.Labels "cinema.purpose"}}' 2>$null
if ($LASTEXITCODE -ne 0) {
    docker run -d --name $taskName --label cinema.purpose=isolated-ai-tests -p 127.0.0.1:5673:5672 -e RABBITMQ_DEFAULT_USER=ai-test-operator -e RABBITMQ_DEFAULT_PASS=isolated-test-only-operator -e RABBITMQ_DEFAULT_VHOST=rabbitmq-test 'rabbitmq:4.1-management@sha256:e1763bfb4a15f9646f9bad2fbae857f4499614577d1165450331189efdb6ea3b' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot start isolated test broker' }
} elseif ($taskPurpose -ne 'isolated-ai-tests') {
    throw 'Existing container has a different purpose; refusing to change it'
} else {
    docker start $taskName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot start isolated test broker' }
}
$taskReady = $false
for ($taskAttempt=0; $taskAttempt -lt 40; $taskAttempt++) {
    # Erlang ping can succeed before the Rabbit application/database is ready.
    docker exec $taskName rabbitmq-diagnostics -q check_running *> $null
    if ($LASTEXITCODE -eq 0) { $taskReady=$true; break }
    Start-Sleep -Seconds 1
}
if (-not $taskReady) { throw 'Isolated broker did not become ready' }
$taskUserJson = docker exec $taskName rabbitmqctl list_users --formatter json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read isolated broker users' }
$taskUsers = $taskUserJson | ConvertFrom-Json
if ($taskUsers.user -notcontains 'ai-test-review-publisher') {
    docker exec $taskName rabbitmqctl add_user ai-test-review-publisher isolated-test-only-review | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create isolated review publisher' }
}
docker exec $taskName rabbitmqctl set_permissions -p rabbitmq-test ai-test-review-publisher '^$' '^cinema.events.v1$' '^$' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict isolated review publisher' }
$env:TEST_AMQP_OPERATOR_PUBLIC='amqp://ai-test-operator:isolated-test-only-operator@127.0.0.1:5673/rabbitmq-test'
$env:REVIEW_AMQP_PUBLIC_URL='amqp://ai-test-review-publisher:isolated-test-only-review@127.0.0.1:5673/rabbitmq-test'
& (Join-Path $taskRoot '.local/ai-venv/Scripts/python.exe') -c "import os,pika; c=pika.BlockingConnection(pika.URLParameters(os.environ['TEST_AMQP_OPERATOR_PUBLIC'])); c.channel().exchange_declare(exchange='cinema.events.v1',exchange_type='topic',durable=True); c.close()"
if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare isolated event exchange' }
Write-Output 'Dedicated broker ready on loopback port 5673; test publisher has exchange write permission only.'
