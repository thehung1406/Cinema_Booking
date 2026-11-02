# Frozen source schema fixture

The sixteen Alembic revisions reconstruct the source PostgreSQL schema used by
owner transfer/checksum/sequence tests. They contain DDL and historical constraints,
not an API, ORM package, worker, application settings or production credentials.

`alembic/env.py` reads only `SOURCE_SCHEMA_DATABASE_URL` and rejects database names
without `test`. The test Compose initializes this fixture on its isolated
`postgres-test`; no source schema is installed in the nine-owner runtime.

The historical OpenAPI/schema/import baselines in `contracts/` and `docs/migration/`
remain immutable evidence. Current exports come exclusively from owner packages.
Historical application code is available in Git at commit `7d31b45`; it is not
copied or renamed into another application folder.
