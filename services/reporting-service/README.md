# Reporting Service

Own PostgreSQL projection, source generation/checkpoints and transactional inbox. API 8089 serves `/admin/reports` and `/admin/reports.csv` with Identity `reports.view`. It reads no foreign database. Five source owners expose frozen internal snapshots and emit full versioned facts/tombstones plus digest checkpoints. Last projection remains available with explicit stale metadata during broker outage.

Root `compose.yml` runs the API, migration, consumer and optional bootstrap profile. See [final runtime](../../docs/runbooks/final-runtime.md), [repair/replay](../../docs/runbooks/reporting.md), [contract](../../contracts/internal/reporting.v1.md) and [M10 evidence](../../docs/migration/reporting-phase.md). First bootstrap requires writer disabled; enable consumer only after all source manifests verify. `alembic upgrade head` owns only Reporting DB.

`tests/test_reporting.py` covers report semantics, snapshot/stream overlap, deletion/revisions, watermarks, generation guards, real messaging and DLQ. `tests/benchmark_m10.py` is an explicit isolated load run, excluded from default pytest naming to keep CI independent of machine speed.
