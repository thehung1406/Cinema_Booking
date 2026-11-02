# Identity — vận hành và cutover M5

> Tài liệu lưu bằng chứng cutover lịch sử. Ứng dụng monolith và các overlay đã xóa ở đợt [dọn source](../migration/backend-removal.md); lệnh lịch sử cần source tại [commit 7d31b45](https://github.com/thehung1406/Cinema_Booking/tree/7d31b452d6ae0b05b8fa946759c5945c9805733e). Vận hành hiện tại dùng root `compose.yml` và [runbook runtime](../runbooks/final-runtime.md).

> Runbook này lưu quy trình cutover tại mốc lịch sử. Runtime hiện hành dùng root `compose.yml`: xem [runbook cuối](final-runtime.md) và [M10](../migration/reporting-phase.md). Không khởi động source/overlay cũ trên dữ liệu đã bàn giao.

Máy đã hoàn tất M6 dùng bộ **bảy Compose file** trong [runbook Catalog](catalog.md), giữ credential/cờ cutover hiện có. Các bước dưới đây mô tả mốc trước đó.

Chạy từ repository root. Giữ `.env.microservices` đã sinh; không đổi password/key ngẫu nhiên cho volume đang tồn tại. Bộ **sáu Compose file** duy trì Notification/AI/Review và Identity. Các lệnh copy/backup có dữ liệu tài khoản; chỉ lưu manifest/dump ở `tmp/` bị ignore.

```powershell
python scripts/dev/prepare_messaging.py
$identityCompose = @('--env-file','.env.microservices',
  '-f','Backend/docker-compose.yml','-f','docker-compose.microservices.yml',
  '-f','docker-compose.notifications.yml','-f','docker-compose.ai-service.yml',
  '-f','docker-compose.reviews.yml','-f','docker-compose.identity.yml')
docker compose @identityCompose config --quiet
docker compose @identityCompose build identity-service
```

Máy đã cutover: chỉ cần `docker compose @identityCompose up -d fastapi outbox-relay gateway identity-service ai-service review-service notification-api`; các env local phải giữ `IDENTITY_STORAGE_OWNER=service`, `IDENTITY_WRITES_ENABLED=true`, `IDENTITY_AUTH_ORIGIN=http://identity-service:8084`, `SERVICE_GATEWAY_DOMAINS=["ai","review","identity"]`, `SERVICE_GATEWAY_REQUIRED_DOMAINS=["identity"]`.

## Cài mới / chuyển từ M4

1. Đặt writer Identity mới false, source owner monolith, giữ gateway ai/review. Thông báo người dùng sẽ cần đăng nhập lại sau cửa sổ chuyển. Kiểm tra không có worker ghi source khác.
2. Dừng source API/relay trong cửa sổ backup rồi chạy `./scripts/migration/backup-restore.ps1`; giữ manifest riêng `tmp/db-backups/identity-source-before-013.json`. Thử Alembic `012 → 013` trên DB restore bằng override URL **chỉ cho tiến trình**; kiểm tra snapshots contact đã điền và không còn FK từ các miền khác sang users. Không đổi env ứng dụng sang DB restore.
3. Nâng source `013`, mở lại API/relay. Tạo Identity DB/migrate/API với writer false; schema `identity_001` không seed user/RBAC vì dữ liệu sẽ được copy nguyên ID.

```powershell
docker compose @identityCompose up -d identity-db identity-migrate identity-service
docker compose @identityCompose exec -T fastapi python -m app.worker.ai_ownership maintenance --domain identity --reason 'M5 freeze before copy'
docker compose @identityCompose --profile migration run --rm identity-backfill
```

Copy kiểm tra cả source fence và destination writer false, copy bốn bảng trong transaction, SHA256/count và high-water sequences; từ chối ghi đè target khác nguồn/target đã có phiên đăng nhập. Manifest không chứa password/profile. Source DB trigger chặn mọi INSERT/UPDATE/DELETE vào users/RBAC và đợi transaction writer cũ kết thúc khi freeze. Đừng khởi tạo user mới trước copy.

4. Backup/restore target trước mở ghi: `./scripts/migration/backup-restore.ps1 -Container backend-identity-db-1`, lưu manifest riêng. Kiểm tra count/checksum copy và login bằng hash cũ trong DB test.
5. Chuyển persistent ownership và cập nhật `.env.microservices` (không in nội dung secret):

```powershell
docker compose @identityCompose exec -T fastapi python -m app.worker.ai_ownership service --domain identity --reason 'M5 accounts/RBAC checksums verified'
```

Giữ các env AI/Review đang dùng, đặt `IDENTITY_STORAGE_OWNER=service`, `IDENTITY_WRITES_ENABLED=true`, `IDENTITY_AUTH_ORIGIN=http://identity-service:8084`, `SERVICE_GATEWAY_DOMAINS=["ai","review","identity"]`, `SERVICE_GATEWAY_REQUIRED_DOMAINS=["identity"]`. Khởi động lại các consumer auth:

```powershell
docker compose @identityCompose up -d --no-deps identity-service fastapi ai-service review-service notification-api gateway
```

6. Smoke qua gateway: public routes; login/me/refresh/logout; admin session đúng quyền; AI history/Review authenticated; legacy writer trả 410; private path bị chặn. Không tạo tài khoản/đơn/thanh toán giả hoặc gửi email khách trên dữ liệu ứng dụng để diễn tập: dùng bộ DB test riêng cho các luồng ghi.

## Khóa ký, session và lỗi

[Contract token/session](../../contracts/internal/identity.v1.md) quy định TTL và hành vi. `.env.microservices` chỉ cấp key ring cho Identity API/migrator/backfill; các consumer chỉ có service credential và HTTP origin. Khi xoay, thêm key mới vào `IDENTITY_SIGNING_KEYS`, đổi `IDENTITY_CURRENT_KID`, recreate Identity; giữ key cũ tối thiểu bằng TTL refresh kể từ lần ký cuối, rồi mới bỏ và recreate. Bỏ sớm đồng nghĩa buộc người giữ token key cũ đăng nhập lại. Không đổi issuer/audience khi rotate thông thường.

Phiên hết hạn bị từ chối ngay cả khi chưa dọn DB. Dọn session đã hết hạn trên 30 ngày (output chỉ có số lượng):

```powershell
docker compose @identityCompose exec -T identity-service python -m identity_service.sessions --retention-days 30
```

Identity outage trả 503 cho protected API, không đọc user/RBAC archive. Kiểm tra DB, migration revision, key ring/current kid và service credential; không bật signing ở consumer để bỏ qua lỗi. AI/Review readiness vẫn báo tình trạng store riêng; kiểm tra auth riêng khi diễn tập.

Trước khi target nhận ghi, có thể sửa tiến hoặc đồng bộ/kiểm tra rồi chuyển theo owner đã audit. `service` là terminal; không hạ env về monolith hoặc restore source cũ để quay lui. Sau khi target có ghi, chỉ sửa tiến hoặc lập quy trình đồng bộ ngược có đối chiếu users/RBAC/sessions/contact snapshots. Không downgrade 013 trên DB đã freeze/transfer; không xóa archive/Redis cũ trong đợt này. Legacy Redis token không còn được chấp nhận và tự hết TTL.
