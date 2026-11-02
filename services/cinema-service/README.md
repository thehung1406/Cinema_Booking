# Cinema service

Own PostgreSQL store for theaters, rooms, physical seats/types/prices, showtimes, immutable sales publications and durable admin operations. API port `8086`; independent worker resumes operations. Migration head `cinema_001`. Runtime has no source, Catalog DB, Identity signing, VNPay or SMTP credentials.

[Sales contract](../../contracts/internal/cinema-sales.v1.md), [runbook](../../docs/runbooks/cinema.md), [local evidence](../../docs/migration/cinema-phase.md), [ADR](../../docs/adr/0008-cinema-versioned-sales-gate.md).

Use all eight Compose overlays listed in the runbook. Default `CINEMA_WRITES_ENABLED=false`. `cinema-backfill` is a privileged one-shot migration profile, not a runtime dependency. Do not run it after target writes diverge.

API validates current Identity permissions. Configuration mutations return `202` and a durable operation ID. Wait for DONE; FAILED/WAITING/RETRY is not success. Existing holds drain before a new publication. Source Booking keeps availability and order/ticket/payment operations.

Run PostgreSQL tests via `docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test`. This runs real migrations, checksum copy, constraint races, lost ACK/retry/bootstrap recovery, Catalog closure lifecycle and the Cinema → Booking integration flow with isolated stores.


Cập nhật M8: Booking/payment legacy đã chuyển sang store riêng; Cinema publication origin là Booking `8087`. Vận hành hiện tại dùng chín overlay, giữ source expiry/relay dừng. Xem [Booking M8](../../docs/migration/booking-phase.md).
