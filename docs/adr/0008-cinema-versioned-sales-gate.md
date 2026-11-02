# ADR 0008 — Cinema publications and a Booking sales gate

Date: 2026-11-02. Scope: M7 local extraction.

## Decision

Cinema owns its five domain tables in a separate database. Booking stores a separate immutable projection (`booking_sales_configurations`) and a monotonic control gate (`booking_sales_gates`), rather than copies of Cinema's physical tables. Orders and seat reservations carry the publication version. Remove source Booking/seat FKs and ORM relationships to physical Cinema entities only after publication contracts and guards exist.

An admin change closes new holds, drains valid holds/pending checkout, applies and persists a new full publication atomically, waits for exact Booking ACK, then opens selling. Every command has an increasing epoch. The gate row is locked by both customer transactions and publication/control changes. Customer confirmation/history uses local immutable order/version facts; it needs no Cinema read during a provider callback.

Long changes are durable jobs returning `202`. They have room ownership, persisted phases/payload/epochs, a session advisory lock across commits, and a worker that resumes WAITING/RETRY jobs. The UI displays pending/failed work and waits for DONE. Terminal failures close selling and require explicit recovery. Capacity, same-room seat type and schedule overlap are also enforced by PostgreSQL.

Catalog grants are reserved until confirmed; replaced/deleted/unapplied references are durably released. A release tombstone fences even a late bind request. Referenced film/format IDs stay permanent; released bindings no longer require a current `film_formats` association.

## Consequences

Booking availability remains authoritative across configuration versions and a Cinema outage. Price edits do not change paid orders. Existing valid holders can finish after close. A slow or failed dependency can leave admin operations waiting and selling closed; the UI must show this state accurately. Background jobs are authorized when accepted and do not depend on retaining a user token.

The per-show gate deliberately serializes selling/control for correctness. Focused PostgreSQL race tests are required, but do not establish production load/SLA. M8 still needs hold/reservation IDs, create-order idempotency, atomic multi-seat ordering and its own deployment/store. Payment remains in the same transaction for M7/M8; saga separation belongs to M9. Archived source tables are fenced and retained for reconciliation, not a fallback read or writer.
