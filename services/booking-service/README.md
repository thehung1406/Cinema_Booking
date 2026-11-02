> M9: Payment đã tách DB/API/worker/relay riêng. Booking tiếp nhận PaymentCaptured và là owner duy nhất của ghế/vé. Các mô tả payment chung dưới đây ghi lại giai đoạn M8; xem [Payment runbook](../../docs/runbooks/payment.md).

# Booking and legacy Payment

Independent API on `8087`, PostgreSQL store at `booking_001`, expiry worker and outbox relay. Own transaction/reservation/checkout models and local Cinema sales publications only; no foreign-domain ORM, source DB, JWT signing or SMTP secrets. The API temporarily holds the legacy VNPay credential. Expiry/relay processes do not receive that credential.

Payment remains co-located and transactionally coupled with Booking/seat/ticket/outbox in M8. The gateway's payment alias points to this API; M9 separation is pending.

[Contract](../../contracts/internal/booking.v1.md), [runbook](../../docs/runbooks/booking.md), [evidence](../../docs/migration/booking-phase.md), [ADR](../../docs/adr/0009-booking-store-and-immutable-checkout.md).

Use all nine overlays in the runbook. Default writer is false; `booking-backfill` alone receives the source credential through its migration profile. Do not seed physical Cinema/Catalog/Identity rows or run the copy after target writes diverge. Source archive guards and stopped schedulers remain in place after cutover.

Run the full isolated suite with `python scripts/dev/prepare_messaging.py --test` and `docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test`. Tests use real migrations/constraints, copied historical rows, callback/expiry/idempotency races and HTTP boundaries. Frontend browser fixtures block every fetch/XHR from reaching live services.
