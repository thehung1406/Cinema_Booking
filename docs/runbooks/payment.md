# Payment cutover, reconciliation and recovery

M9 adds `docker-compose.payment.yml` as the tenth overlay, after
`docker-compose.booking.yml`. Use the same `--env-file .env.microservices` and
preceding overlays from the Booking runbook; call the resulting array
`$paymentCompose`. Compose resolves build/mount paths from `Backend/`.

## Prepare and freeze

1. Run `python scripts/dev/prepare_messaging.py`. It preserves existing secret
   values/hashes and merges new broker principals, durable queues and DLQs. Import
   the mounted definitions with `rabbitmqctl import_definitions
   /etc/rabbitmq/definitions.json` and verify completion. Never delete broker data
   or rotate existing hashes as a topology update.
2. Run the full isolated suite, frontend checks and `payment-flow.mjs`. Build all
   role images, including migrate/backfill/worker/relay: Compose may otherwise
   reuse an old role image even when the API image has been rebuilt.
3. Drain pending checkouts and active holds. Stop Booking API, expiry and relay
   writers; keep the old source writers fenced. Capture old history/report facts.
   Run `backup-restore.ps1 -Container backend-booking-db-1`; save its manifest under
   a unique name. Rehearse booking_001 → booking_002 in the fresh restore DB and
   verify original tickets/money before upgrading the application DB.
4. Set BOOKING_WRITES_ENABLED=false, BOOKING_PAYMENT_STORAGE_OWNER=maintenance,
   PAYMENT_WRITES_ENABLED=false. Run the rebuilt Booking migration. Then use:

```powershell
docker compose @paymentCompose run --rm --no-deps booking-service python -m booking_service.payment_ownership maintenance --reason 'M9 verified backup and boundary rehearsal'
```

Start the frozen Booking API for private fact reads, and the new Payment API/DB
with writes false. Health must verify each owned schema. Payment runtime never
receives the source DB URL; only the backfill profile does.

## Copy and handoff

```powershell
docker compose @paymentCompose --profile migration run --rm --no-deps payment-backfill
docker compose @paymentCompose --profile migration run --rm --no-deps payment-backfill python -m payment_service.migrate --manifest /migration-manifests/verified-before-cutover.json
```

Copy requires the durable source owner to be maintenance, target writes false,
zero pending orders/active holds, an empty or identical destination, matching
checkout facts and original-column payment checksums. Source is read under a
repeatable-read snapshot. Reseed preserves the source sequence high-water.
Historical PAID needs a backfilled Booking receipt proving valid issued tickets
or explicit rejection. Transfer results are labelled LEGACY_TRANSFER, not signed
callbacks. No capture or email event is fabricated. Divergence is a hard failure;
never overwrite a nonempty financial store.

Backup/restore and checksum all tables of both booking_002 and payment_001 while
writers remain disabled. Retain the three distinct manifests/dumps locally.
Only then advance Booking's durable Payment owner:

```powershell
docker compose @paymentCompose run --rm --no-deps booking-service python -m booking_service.payment_ownership service --reason 'M9 financial checksums and both restore rehearsals verified'
```

Set BOOKING_PAYMENT_STORAGE_OWNER=service, BOOKING_WRITES_ENABLED=true and
PAYMENT_WRITES_ENABLED=true. Keep all enabled gateway domains and require Identity,
Booking and Payment readiness. Gateway payment and reconciliation routes now go
to Payment8088. The overlay clears Booking API/migration merchant credentials;
only Payment API receives them among the new runtime processes. Start Booking
API/expiry/relay/payment-consumer and Payment API/worker/relay, then gateway.

Check old Booking callback routes return 410 even if its env owner is reset;
archived payment writes must fail at the DB. Compare complete historical order
responses and report business facts (excluding the report's moving as_of clock),
verify valid tickets/money, queue consumers and all readiness endpoints. Use
technical sessions on existing users only for read smoke, then remove them.

## Reconciliation

The worker logs a changed `reconciliation open_cases=N` count. At least every 30
seconds it checks PAID without a terminal Booking result, recovers sealed results
over authenticated HTTP, detects BLOCKED capture events, and durably records
PAID_UNCONFIRMED. Published captures with a missing ACK can be republished under
the same event ID. BLOCKED events require an audited retry. The admin page
`/admin/payment-reconciliation` requires reports.view and lists open cases.

| Situation | Action |
| --- | --- |
| PAID_UNCONFIRMED / EVENT_BLOCKED | Check Booking API/consumer, broker queues/DLQ and both relays. Verify exact checkout/result identity. Restore delivery and use the audited retry with a reason. A terminal sealed result resolves transient cases. |
| AMOUNT_MISMATCH | Compare expected/collected amounts, merchant_ref and provider transaction. Retain evidence; investigate before any money action. |
| DUPLICATE_PAYMENT / ADDITIONAL_COLLECTION | Verify each provider settlement and one accepted ticket funding. Keep the extra collection visible even when the customer has valid tickets. |
| BOOKING_REJECTED / expired hold | Confirm no tickets were issued for that payment and no newer hold was consumed. Contact the customer and follow verified provider/manual money procedures. |
| PROVIDER_REFERENCE_CONFLICT / legacy case | Compare original provider evidence and ticket receipts; preserve all ledger rows and references. |

Never set PAID to FAILED, generate another charge URL for a PAID order, extend a
checkout deadline, invent tickets, edit an immutable receipt or mark a refund
complete from a retry button. No automated refund/close-money-case endpoint is
provided. Permanent money cases remain open until a verified resolution workflow
is implemented. Monitor logs/case counts; production paging/SLA is M10 work.

For a DLQ event, identify the payload/identity error, repair the cause, and replay
the original event ID via an operator credential with an audit reason. Verify the
inbox and sealed result before ACK/removing the DLQ delivery. Do not change its ID
to bypass deduplication, purge live queues, or replay old confirmation emails as
a smoke test. Private email is created only after the Booking commit.

## Recovery and isolated outage drill

API receipt commits continue during broker/Booking outages. Keep one callback
owner, restore delivery, inspect all unmatched collections, and allow the worker
to repair missing ACKs. Poison payloads go to durable DLQs; infrastructure errors
reconnect and requeue unacknowledged deliveries. Never roll the gateway back to
legacy callbacks after handoff. Restore both financial/booking stores under a
freeze, preserve terminal ownership, reconcile provider settlements, accepted
receipts, ticket usage and outbox/inbox, then reopen. Prefer repair forward.

For a **test-only** broker stop drill, run
`scripts/migration/smoke_payment_outage.py` in the isolated migration-test container
with Payment installed. Wait for `/tmp/ready`, stop only
`cinema-migration-tests-rabbitmq-test-1`, then touch `/tmp/broker-stopped` in the
drill container. It verifies signed callbacks commit once and PAID/outbox survive.
After `/tmp/outage-verified`, restart and wait for healthy test RabbitMQ, then touch
`/tmp/broker-restored`. It verifies delivery of the same capture ID and removes its
own temporary Payment schema. It never contacts the live Booking/provider/SMTP.

Production provider settlement/refund integration, load thresholds M0.7,
external alert delivery and final credential/legacy cleanup remain separately
tracked; this local cutover does not constitute production approval.
