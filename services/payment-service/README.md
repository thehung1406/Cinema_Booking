# Payment Service — M9

Own PostgreSQL, API 8088, inbox/reconciliation worker and outbox relay. The API
validates VNPay signatures and fresh authenticated checkout facts from Booking.
Booking alone confirms seats and tickets after PaymentCaptured.v1.

Apply `docker-compose.payment.yml` after the nine M8 overlays. Defaults keep
Payment writes disabled. Prepare ignored credentials/topology with
`python scripts/dev/prepare_messaging.py`, then follow the
[cutover and recovery runbook](../../docs/runbooks/payment.md).

Run all isolated checks using `infra/compose/compose.migration-tests.yml` after
`prepare_messaging.py --test`. Tests exercise actual PostgreSQL migrations,
separate stores, signed ASGI callbacks, concurrency, RabbitMQ redelivery, running
consumers and poisoned-message DLQs. No live provider or customer order is used.

[Contract](../../contracts/internal/payment.v1.md),
[decision](../../docs/adr/0010-payment-saga.md),
[local evidence](../../docs/migration/payment-phase.md).
