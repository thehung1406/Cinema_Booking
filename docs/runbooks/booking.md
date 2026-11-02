> M9 đã thay phần payment tạm ở tài liệu M8 này bằng Payment Service riêng. Luồng hiện tại và các lệnh cutover/recovery: [runbook Payment](payment.md). Không bật lại legacy payment sau M9.

> Runbook này lưu quy trình cutover tại mốc lịch sử. Runtime hiện hành dùng root `compose.yml`: xem [runbook cuối](final-runtime.md) và [M10](../migration/reporting-phase.md). Không khởi động source/overlay cũ trên dữ liệu đã bàn giao.

# Booking M8 — operation and local cutover

The block includes legacy VNPay payment. It is not the M9 independent Payment service.

```powershell
python scripts/dev/prepare_messaging.py
$bookingCompose = @('--env-file','.env.microservices',
  '-f','Backend/docker-compose.yml','-f','docker-compose.microservices.yml',
  '-f','docker-compose.notifications.yml','-f','docker-compose.ai-service.yml',
  '-f','docker-compose.reviews.yml','-f','docker-compose.identity.yml',
  '-f','docker-compose.catalog.yml','-f','docker-compose.cinema.yml',
  '-f','docker-compose.booking.yml')
docker compose @bookingCompose build fastapi booking-service gateway
docker compose @bookingCompose up -d booking-db booking-migrate booking-service
```

Prepare preserves existing credentials. It copies only the four legacy merchant/hash/frontend/provider settings from Backend/.env when no BOOKING override already exists; confirm they match the running source before cutover, without printing secrets. Runtime API gets its own DB, Identity/Catalog HTTP origins, service credential and VNPay settings. Expiry gets only its own DB/writer flag; relay gets own DB/writer/broker publisher URLs. Never inject the source env_file into those runtime services. The one-shot backfill profile alone needs it.

## Preconditions and copy

1. Run the isolated full suite and browser lost-response checkout flow. Capture public/admin/report contracts and the existing order-history facts. Inventory holds, all pending orders, open sales and unfinished Cinema operations. Finish Cinema operations; if holds/checkouts are active, close new holds through Cinema and wait for existing checkout to settle before freezing. Run legacy expiry cleanup before freeze when expired PENDING orders remain. Do not force expiry of a live customer checkout or rewrite monetary facts.
2. Stop source API/outbox relay, Cinema API/worker and old Celery worker/beat for the window. Backup/restore source `015` with `scripts/migration/backup-restore.ps1`; retain a distinct manifest. Rehearse `015 → 016` on the fresh restored DB using a process-only URL override, then upgrade the application source. Start the new source API with old gateway routing and freeze Booking:

```powershell
docker compose @bookingCompose run --rm --no-deps --entrypoint python fastapi -m app.worker.ai_ownership maintenance --domain booking --reason 'M8 freeze drained Booking/payment and projection writers'
docker compose @bookingCompose up -d --no-deps fastapi
docker compose @bookingCompose --profile migration run --rm booking-backfill
```

Source ownership endpoint is `/internal/v1/booking-read/ownership`; target migration state is private. Copy requires source maintenance and target writer false, independently checks the durable source fence, and refuses live holds or any unsettled PENDING order. Keep Cinema's publication writer paused so gate epochs/publication ACKs cannot advance between snapshot and handoff.

3. The copy streams and SHA-256 compares all original columns of eleven tables: booking_sales_configurations, booking_sales_gates, bookings, booking_details, booking_food_items, payments, tickets, seat_status, outbox_events, inbox_events, message_replay_audits. It preserves IDs, money, timestamps, contacts, references/codes, event payloads/statuses and sequence high-water. Nonempty divergent targets are refused. Inside one locked destination transaction it temporarily disables user triggers on only those allowlisted tables for historical rows, derives deterministic reservation and immutable checkout records, verifies original checksums again, re-enables triggers, then commits. Bootstrap failure rolls everything back; never clear or overwrite the target to force success.
4. Inspect the copy manifest and derived checkout/reservation counts, verify zero disabled triggers and unchanged existing order responses. A historical null expires_at remains null; its checkout/reservation deadline is the original booking_date plus ten minutes. No fake user/order/payment is needed to smoke the live store.
5. Backup/restore the target at `booking_001` before enabling writes. Keep the source and target backup manifests/dumps separately, ignored and local. Do not advance ownership merely because the new API is healthy and empty.

## Handoff

```powershell
docker compose @bookingCompose exec -T fastapi python -m app.worker.ai_ownership service --domain booking --reason 'M8 original-column checksums checkout bootstrap and backup restore verified'
```

Preserve credentials/other domains and set:

```text
BOOKING_STORAGE_OWNER=service
BOOKING_WRITES_ENABLED=true
CINEMA_BOOKING_ORIGIN=http://booking-service:8087
SERVICE_GATEWAY_DOMAINS=["ai","review","identity","catalog","cinema","booking","payment"]
SERVICE_GATEWAY_REQUIRED_DOMAINS=["identity","booking"]
```

```powershell
docker compose @bookingCompose up -d --no-deps fastapi booking-service booking-worker booking-relay cinema-service cinema-worker gateway
```

Do not restart the source outbox relay/expiry owner. The new source beat config removes the cleanup entry and a stale cleanup task returns migrated without querying Booking rows; archive write guards remain authoritative even if an old env flag is reset. Old explicit email tasks bridge by deterministic event ID to Booking; never run a paid customer's old email task merely to smoke a migration.

Verify new route/service headers, auth/ownership/check-in permissions, private-path protection, all historical fields and report totals, Cinema's private state read at the new origin, enabled source guards and worker/relay process state. A verify-only backfill command can compare original columns after cutover before any new business write:

```powershell
docker compose @bookingCompose --profile migration run --rm --no-deps booking-backfill python -m booking_service.migrate --manifest /migration-manifests/verified-after-cutover.json
```

It intentionally fails once legitimate target writes diverge; it is not ongoing replication. Never use apply to overwrite those writes.

## Recovery

API `503` during freeze is deliberate; provider retries must reach the active Booking owner after handoff. New orders need live Identity contacts and Catalog quotes for selected food; published seat prices, history, confirmation, expiry and ticketing use local snapshots. Cinema outage must not reopen stale source sales.

Unknown create-order result: retry the same body/key; use the frontend's pending-attempt retry after reload. A changed payload under an accepted key is 409. CHECKOUT holds cannot be released through seat API. Cancel an unpaid order through its authorized flow; never change reservation deadlines or clear IDs in SQL.

An attempt PAID with an unconfirmed/expired order requires reconciliation; do not generate another payment URL or invent a refund. A confirmation failure retains validated evidence, rolls back seats/tickets/outbox, and may be retried against the same checkout. Late callbacks cannot take a newer reservation's hold. Stable event IDs make retries deterministic.

Owner service is terminal. After target writes, source restore/environment rollback alone is unsafe: reconcile orders/reservations, provider evidence, ticket usage, publication epochs and outbox/inbox first. Prefer repair forward. Keep archives fenced and backups private. Production load/SLA, HA/TLS and M9 payment saga/refunds remain separate work.
