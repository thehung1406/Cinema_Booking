# Cinema M7 — local operation and cutover

> Runbook này lưu quy trình cutover tại mốc lịch sử. Runtime hiện hành dùng root `compose.yml`: xem [runbook cuối](final-runtime.md) và [M10](../migration/reporting-phase.md). Không khởi động source/overlay cũ trên dữ liệu đã bàn giao.

Run from the repository root in PowerShell:

```powershell
python scripts/dev/prepare_messaging.py
$cinemaCompose = @('--env-file','.env.microservices',
  '-f','Backend/docker-compose.yml','-f','docker-compose.microservices.yml',
  '-f','docker-compose.notifications.yml','-f','docker-compose.ai-service.yml',
  '-f','docker-compose.reviews.yml','-f','docker-compose.identity.yml',
  '-f','docker-compose.catalog.yml','-f','docker-compose.cinema.yml')
docker compose @cinemaCompose build fastapi gateway catalog-service cinema-service
```

The ignored credential file retains all existing keys. Target runtime receives only its own database URL, fixed HTTP origins and service key. Backfill receives the source DB credential only through its migration profile. Do not print credential files or compose configuration containing expanded secrets.

## Prepare and migrate

1. Inventory source Cinema's five tables, room capacities, overlaps, active holds and nonexpired pending orders. Capture public/admin/history/report contracts using an existing account with a short technical session; delete the session finally. Test customer writes only against isolated test databases.
2. Pause source API/outbox relay and Catalog API writers. Backup/restore source `014` and Catalog `catalog_001` using `scripts/migration/backup-restore.ps1`, saving distinct manifests. Rehearse `014 → 015` and `catalog_001 → catalog_002` against fresh restored databases using process-only URL overrides. Never restore over the application DB.
3. Upgrade source `015`, Catalog `catalog_002`, and the new separate Cinema DB `cinema_001`; start APIs with Cinema writer false and old gateway routes. Restart source after migration so all selling/history code uses the new boundary. Source archive owner is still monolith until freeze.
4. Freeze, drain and copy:

```powershell
docker compose @cinemaCompose exec -T fastapi python -m app.worker.ai_ownership maintenance --domain cinema --reason 'M7 freeze Cinema for verified copy'
docker compose @cinemaCompose --profile migration run --rm cinema-backfill
```

The one-shot verifies source maintenance + destination writer false, preserves IDs/Decimal/deletion/snapshots and sequence high-water, compares SHA-256 checksums on all original columns, and refuses divergent nonempty destinations. It then initializes version 1 publications, closes/imports/opens each source gate with exact ACK and confirms existing Catalog bindings. Past/inactive/empty configurations stay closed. Bootstrap epochs/ACKs persist so a lost open response resumes without replaying an older close. Legacy rows inserted between schema upgrade and freeze receive version 1 without changing their financial facts. Any active hold/checkout prevents bootstrap.

5. Backup/restore the target after verified copy/publication and before enabling writes. Save both the copy manifest and distinct backup manifests. Check source projection counts and all eight publications ACKed; compare public/admin/history/report contracts.
6. Transfer source Cinema ownership terminally to service. Set the following values in the ignored env, preserving earlier domains/required domains:

```text
CINEMA_STORAGE_OWNER=service
CINEMA_WRITES_ENABLED=true
SERVICE_GATEWAY_DOMAINS=["ai","review","identity","catalog","cinema"]
SERVICE_GATEWAY_REQUIRED_DOMAINS=["identity"]
```

```powershell
docker compose @cinemaCompose exec -T fastapi python -m app.worker.ai_ownership service --domain cinema --reason 'M7 copy and Booking publications verified'
docker compose @cinemaCompose up -d --no-deps fastapi outbox-relay catalog-service cinema-service cinema-worker gateway
```

7. Verify health, correct route/service headers, private-path rejection, admin authorization, source API+raw DB fences even after resetting only the env, and unchanged history/payment/report facts. Keep source archive read-only. Do not mark M7 complete from a healthy empty service alone.

## Admin operation recovery

Use the admin task panel or permission-protected `/admin/cinema-operations/{id}`. `202` means accepted; only DONE is completion. WAITING drains valid holds and unexpired pending orders. Source expiry uses deadlines; no worker may extend a closed gate's hold. RETRY resumes exact persisted epochs/publications after a dependency or DB error; restore the dependency and let the worker retry. COMPENSATING seals a rejected unused Catalog grant before releasing it; never delete/expire grants manually while a writer might still commit.

FAILED leaves affected sales closed and frees the room for a corrected operation. Check the message and current version, correct the input, then publish/open explicitly when valid. Shows with order history cannot move/retime/delete; booked/referenced seats cannot be removed/disabled. Create a new show/seat configuration instead of rewriting history. Do not force DONE or clear a busy room ID in SQL. Accepted work continues after the initiating user's session expires; no caller token is stored by the worker.

Cinema is optional for gateway readiness. On outage, keep its owner as service, recover its DB/API/worker, and preserve source Booking's local versions/gates. An already-published order/payment/history needs no Cinema API. Source held-seat availability is still `/seats*`; Catalog/Cinema admin aggregation can be unavailable while callbacks continue. Do not route Cinema back to the archive or downgrade `015`; after target writes, rollback requires explicit reconciliation of publications, operations, Booking references and Catalog bindings. Prefer repairing forward.

## Verification

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml down
```

Frontend: unit/lint/build and isolated browser admin fixtures exercise `202 → WAITING → DONE` with no premature saved state. PostgreSQL tests cover real constraint races, hold/close and checkout/import serialization, lost/incomplete ACK, immutable old prices/history, expired late callbacks vs new holds, Catalog tombstones, frozen copy/high-water and bootstrap recovery. Production load/SLA, HA/TLS and M8 hold/order idempotency remain separate gates.


Cập nhật M8: Booking/payment legacy đã chuyển sang store riêng; Cinema publication origin là Booking `8087`. Vận hành hiện tại dùng chín overlay, giữ source expiry/relay dừng. Xem [Booking M8](booking.md).
