# ADR 0009 — Booking store with co-located legacy payment

Date: 2026-11-02. Scope: M8 local extraction.

## Decision

Move Booking's transaction tables, local sales projection and messaging state into its own PostgreSQL store. Include legacy payment attempts and provider confirmation in the same deployment/transaction for this milestone. M9 will separate Payment through an explicit checkout/event boundary; it is not considered independently extracted in M8.

Use PostgreSQL as hold/checkout authority. A reservation has an ID, user/show/sales version, mutable ACTIVE seat set and fixed deadline. Checkout seals it. One user/show active reservation and one order/reservation are enforced by uniqueness; multi-seat operations lock the show gate and seats consistently. User-scoped idempotency locks/fingerprints replay a committed response after lost network results and reject changed payloads. The frontend persists the exact pending request/key.

Persist immutable versioned checkout facts and public CheckoutCreated/BookingExpired events in the local transaction. Preserve the M7 close/drain/ACK protocol. Keep confirmation/ticket/outbox atomic and retain validated provider evidence when confirmation fails; an expired order cannot consume a newer hold. Serialize expiry, payment, cancellation and check-in through the same gate/order lock order. The old source expiry schedule/relay is stopped and guarded against stale invocation.

Keep source AI/Review/reporting adapters temporarily, but replace all their runtime Booking-table reads with authenticated HTTP facts. Runtime Booking imports no foreign-domain ORM or source credentials. Historical contacts/prices/labels remain local snapshots. Cinema's publication origin now points directly to Booking.

## Migration

Source `016` registers terminal Booking ownership and write guards on eleven archived transaction/projection/messaging tables. Freeze/drain source and Cinema writers, copy/compare all original columns and sequence high-water, then derive deterministic reservation/checkout records without changing original facts. Historical null expires_at uses booking_date + ten minutes in the new checkout; the original column remains null. Historical BOOKED rows load only inside the frozen, locked copy transaction with allowlisted user triggers temporarily disabled; re-enable and verify before commit. No divergent destination is overwritten.

Backup/restore and checksum verification precede enabling target writes. Preserve payment references, ticket codes and outbox event IDs/payloads/statuses. A failed historical bootstrap rolls back the entire copy. After target writes, restore/rollback requires reconciling reservations, payment evidence, tickets, sales epochs and messaging; repair forward.

## Consequences

Booking's customer operations and callbacks can run without source/Cinema/Catalog DB access. Dependent contact/food APIs are needed only when creating a new order. A per-show gate deliberately favors correctness; focused race tests do not establish production throughput/SLA. No automatic refunds or independent Payment saga is introduced. M0.7 production load/HA and the six pre-existing frontend source-contract failures remain separate work.
