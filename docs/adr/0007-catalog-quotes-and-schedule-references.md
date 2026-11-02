# ADR 0007 — Catalog quote and schedule-reference boundary

Status: accepted for M6 local migration, 02/11/2026. Implements the Catalog portion of [ADR 0004](0004-quotes-sales-and-payment-consistency.md).

Move seven catalog tables into a dedicated PostgreSQL store. Keep food-line snapshots and order money decisions in legacy Booking. Catalog issues immutable UUID/revision/deadline quotes; Booking validates and stores the quote facts before commit. Prices/components on historical orders do not follow later menu edits. Decimal/Numeric remains the money representation.

Remove external Catalog FKs/ORM relationships from source schedules, reviews and booking food. Backfill schedule/booking film snapshots first. Catalog must never check a source HTTP reference list and then hard-delete a film: that permits a schedule/delete race. Instead, keep IDs permanently and serialize film updates/retirement with durable schedule grants using the same Film row lock. Backfill every existing schedule as a reference before changing ownership.

The source requests the grant before taking business room locks, validates its own room/hold/order/overlap rules and stores the returned snapshot. Source transactional ownership guards prevent old catalog writers and missing/stale schedule grants after cutover. Failed/ambiguous source writes may leave conservative references; they cannot be expired automatically without proving that a source writer cannot still commit. M6 retains them and returns 409 for incompatible lifecycle changes. Confirmation/release/close-sales orchestration will be completed with Cinema M7, not inferred from elapsed time.

This grant is a Catalog configuration reference, **not** M7 sales_version or an inventory/hold reservation. Seat availability, hold expiry and payment transactions remain where they were; M0.7 and M7–M9 are still open.

`/admin/catalog` is now genuine gateway aggregation with per-owner bearer authorization; the gateway has no DB or internal-service credential. Review route precedence is preserved. AI/Review and report callers use Catalog APIs or published historical snapshots, with no reads from the transferred archive. Catalog does not produce reporting/invalidation events in this phase; M10 still needs bootstrap/snapshot/checkpoint contracts for catalog dimensions. No event-driven cache is used to decide current schedule grants.

See [Catalog v1](../../contracts/internal/catalog.v1.md) and [runbook](../runbooks/catalog.md) for request shapes, TTL/failure semantics, copy/freeze/ownership and reconciliation boundaries.
