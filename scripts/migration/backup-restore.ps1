param(
    [Parameter(Mandatory = $true)]
    [string]$Container
)
# Requires application writers to be stopped/read-only while comparing snapshot checksums.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$backupDirectory = Join-Path $projectRoot 'tmp\db-backups'
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
$suffix = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$restoreDatabase = 'cinema_restore_test_' + ($suffix -replace '-', '_')
$containerDump = '/tmp/cinema-baseline-' + $suffix + '.dump'
$localDump = Join-Path $backupDirectory ('cinema-baseline-' + $suffix + '.dump')

# No application writes, no drop/clean, no password in arguments or output.
docker exec $Container sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl --file="$1"' sh $containerDump
if ($LASTEXITCODE -ne 0) { throw 'Application backup failed.' }
docker cp "${Container}:$containerDump" $localDump
if ($LASTEXITCODE -ne 0) { throw 'Copying backup failed.' }
docker exec $Container sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh $restoreDatabase
if ($LASTEXITCODE -ne 0) { throw 'Creating a fresh restore test DB failed; existing databases were not modified.' }
docker exec $Container sh -c 'pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --no-owner --no-acl "$2"' sh $restoreDatabase $containerDump
if ($LASTEXITCODE -ne 0) { throw 'Restoring test DB failed.' }

$sql = @'
SELECT version_num FROM alembic_version;
SELECT count(*) FROM pg_tables WHERE schemaname = 'public';
SELECT format($f$SELECT %L, count(*), md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY row_to_json(t)::text), '')) FROM %I.%I t;$f$, tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
'@
$sourceResult = @($sql | docker exec -i $Container sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1')
if ($LASTEXITCODE -ne 0) { throw 'Source metadata check failed.' }
$restoreResult = @($sql | docker exec -i $Container sh -c 'psql -U "$POSTGRES_USER" -d "$1" -At -v ON_ERROR_STOP=1' sh $restoreDatabase)
if ($LASTEXITCODE -ne 0) { throw 'Restore metadata check failed.' }
if (($sourceResult -join "`n") -ne ($restoreResult -join "`n")) { throw 'Revision, row count or content checksum differs after restore.' }
$hash = (Get-FileHash -LiteralPath $localDump -Algorithm SHA256).Hash
$manifest = [ordered]@{
    backup = $localDump
    sha256 = $hash
    restore_database = $restoreDatabase
    revision = $sourceResult[0]
    public_table_count = $sourceResult[1]
    verified_table_checksums = $sourceResult.Count - 2
    restored_at_utc = [DateTime]::UtcNow.ToString('o')
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backupDirectory 'latest-manifest.json') -Encoding utf8
$manifest | ConvertTo-Json
