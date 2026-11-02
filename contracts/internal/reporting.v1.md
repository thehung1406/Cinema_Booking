# Reporting export v1

Internal only. Header `X-Service-Key`; fixed owner origins, no arbitrary user URL. Sources: `booking`, `payment`, `catalog`, `cinema`, `review`. Neither payload nor manifest exports contact details, review text, token, merchant key or ticket QR.

| Endpoint at each source | Response |
| --- | --- |
| `POST /internal/v1/reporting/snapshots` | `snapshot_id`, `source`, `generation` UUID, aware `as_of`, `count`, `sha256` |
| `GET /internal/v1/reporting/snapshots/{uuid}?after=-1&limit=250` | frozen `items`, monotonic ordinal `next_cursor`; limit 1–500 |
| `GET /internal/v1/reporting/state` | `generation`, pending dirty key count |

Manifest identifies a stable copy of materialized facts. Capture continues while pages are read. Full facts can overlap the snapshot; source entity revisions and retained tombstones determine the winner. The manifest timestamp alone is not proof of current-source freshness; only matching streamed checkpoints provide that proof.

`ReportFactChanged.v1` uses the platform envelope, producer `reporting-source:{source}`, aggregate ID `{source}:{kind}:{key}`, aggregate version equal to fact version. Data fields: `source`, `generation`, `kind` (lowercase/underscore, ≤30), `key` (≤100), positive `version`, aware `changed_at`, `deleted`, full `payload`. Tombstone uses empty payload and retained revision. Retry uses deterministic event UUID derived from generation/kind/key/revision.

`ReportCheckpoint.v1` producer is the same; aggregate ID `{source}:checkpoint`, monotonic checkpoint aggregate version. Data: `source`, `generation`, nonnegative `count`, 64-hex `sha256`, aware `as_of`. Canonical digest is SHA-256 of facts sorted lexicographically by `(kind,key)`, each serialized as sorted-key compact JSON plus newline, including deleted facts and versions. No max timestamp/ID cursor is supported.

Public routing key is `{event_type}.reporting-source:{source}`. Per-source topic permissions restrict producer identity. Reporting consumes durable `reporting.bootstrap.v1`, records `reporting.facts.v1` inbox and ACKs after local commit. Rejected messages dead-letter into `reporting.dead.v1`; replay retains event ID with operator audit. Legacy business events are audited only after all sources are bootstrapped.

Projection accepts strictly newer entity versions, ignores older versions/identical duplicates, rejects same-version different content and source generation mismatch. Every applied change invalidates source verification until a full digest/count checkpoint agrees. Reporting API returns conservative `as_of`, `stale` and `watermarks`; default stale threshold is 60 seconds. During unavailable broker it serves the last projection with explicit staleness.
