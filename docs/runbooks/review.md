# Vận hành và cutover Review — M4

> Tài liệu lưu bằng chứng cutover lịch sử. Ứng dụng monolith và các overlay đã xóa ở đợt [dọn source](../migration/backend-removal.md); lệnh lịch sử cần source tại [commit 7d31b45](https://github.com/thehung1406/Cinema_Booking/tree/7d31b452d6ae0b05b8fa946759c5945c9805733e). Vận hành hiện tại dùng root `compose.yml` và [runbook runtime](../runbooks/final-runtime.md).

> Runbook này lưu quy trình cutover tại mốc lịch sử. Runtime hiện hành dùng root `compose.yml`: xem [runbook cuối](final-runtime.md) và [M10](../migration/reporting-phase.md). Không khởi động source/overlay cũ trên dữ liệu đã bàn giao.

Máy đã hoàn tất M6 dùng bộ **bảy Compose file** trong [runbook Catalog](catalog.md), giữ credential/cờ cutover hiện có. Các bước dưới đây mô tả mốc trước đó.

Máy đã hoàn tất M5 phải dùng bộ **sáu Compose file** và auth origins trong [runbook Identity](identity.md), giữ credential/cờ cutover hiện có. Các bước phía dưới mô tả mốc chuyển miền trước đó.

## Chuẩn bị sau M3

M3 phải ổn định: AI đã có store/tuyến riêng. Dùng đủ **năm overlay** từ repository root sau M4; giữ `.env.microservices`, không sinh lại credential khác cho volume đã tồn tại.

```powershell
python scripts/dev/prepare_messaging.py
$reviewCompose = @('--env-file', '.env.microservices', '-f', 'Backend/docker-compose.yml', '-f', 'docker-compose.microservices.yml', '-f', 'docker-compose.notifications.yml', '-f', 'docker-compose.ai-service.yml', '-f', 'docker-compose.reviews.yml')
docker compose @reviewCompose build fastapi review-service review-worker review-relay review-migrate review-backfill
```

Script bổ sung DB password và public publisher riêng cho Review, giữ credential/hash/topology đã có. `SERVICE_GATEWAY_DOMAINS` ban đầu kế thừa domain AI đang bật, không tắt AI khi thêm overlay thứ năm. Trên broker đã chạy, nạp definitions bổ sung rồi kiểm tra user/permissions; không purge queue hoặc thay volume:

```powershell
docker compose @reviewCompose exec -T rabbitmq rabbitmqctl import_definitions /etc/rabbitmq/definitions.json
```

Import diễn ra bất đồng bộ; xác nhận `review-publisher` có quyền publish public exchange và kết nối được trước mở relay. API/worker không được cấp broker password; relay không có quyền private vhost/email queue. Broker mới tự nạp definitions khi khởi động.

## Backup, freeze và copy

1. Trước nâng nguồn, dừng các writer nguồn đang hoạt động (API/relay và mọi worker/scheduler). Chạy [backup/restore](backup-restore.md), lưu manifest riêng, thử migration `011 → 012` trên DB restore mới. Xác nhận owner AI vẫn `service` và Review được khởi tạo `monolith`. Không restore đè hoặc đổi `.env` ứng dụng sang DB test.
2. Trong `.env.microservices`, giữ `REVIEW_STORAGE_OWNER=monolith`, `REVIEW_WRITES_ENABLED=false`, `SERVICE_GATEWAY_DOMAINS=["ai"]`. Triển khai source + Review chưa mở ghi:

```powershell
docker compose @reviewCompose up -d --no-build fastapi gateway outbox-relay review-service review-worker review-relay
docker compose @reviewCompose exec -T fastapi python -m app.worker.ai_ownership maintenance --domain review --reason 'M4 freeze before copy'
docker compose @reviewCompose --profile migration run --rm review-backfill
```

3. CLI dùng hàng fence Review riêng trong `domain_ownership`, chờ writer cũ giữ khóa share hoàn tất. Legacy inference nhả connection khi tính model và phải lấy lại fence trước ghi. Dừng sentiment worker/overlay ML legacy nếu đang chạy; task retry cũ bị fence và không còn phân tích store nguồn. Khôi phục các worker/scheduler Booking vốn hoạt động trước bảo trì bằng đúng cấu hình Notification events.
4. Job đòi source owner maintenance và target API writes=false; worker/relay mới phải cùng cấu hình false và không có process ngoài Compose đang ghi target. Copy hai bảng trong snapshot read-only, giữ ID, content version, moderation/deletion, timestamps, scores, model version, attempts và sequence high-water. So count/SHA256 trên các cột legacy trước commit. Cột kỹ thuật mới event_version=0, analysis_generation=1, lease rỗng. Đích phải rỗng hoặc giống hệt; đích đã có outbox/event hoặc khác dữ liệu bị từ chối. Manifest ở `tmp/review-migration/latest.json` bị ignore. Job migration là thành phần duy nhất nhận credential DB nguồn.
5. Backup/restore target khi writes vẫn false nếu cần: `./scripts/migration/backup-restore.ps1 -Container backend-review-db-1`. Lưu `latest-manifest.json` sang tên riêng vì script ghi lại tệp này.

## Chuyển owner và kiểm chứng

Chỉ khi copy/checksum đạt:

```powershell
docker compose @reviewCompose exec -T fastapi python -m app.worker.ai_ownership service --domain review --reason 'M4 checksum verified; hand over Review'
```

Đặt `REVIEW_STORAGE_OWNER=service`, `REVIEW_WRITES_ENABLED=true`, `SERVICE_GATEWAY_DOMAINS=["ai","review"]` trong `.env.microservices`. Giữ `AI_STORAGE_OWNER=service`, `AI_WRITES_ENABLED=true` đã có. Chuyển riêng các giá trị auto-approve/backend/threshold/window/min-reviews cũ sang các khóa `REVIEW_*` tương ứng; không cấp `Backend/.env` cho API/worker/relay. Bản local hiện dùng disabled, chưa có artifact đã duyệt.

```powershell
docker compose @reviewCompose up -d --no-build fastapi gateway review-service review-worker review-relay
.venv/Scripts/python.exe scripts/migration/smoke_gateway.py --ai http://127.0.0.1:8082 --review http://127.0.0.1:8083
```

Kiểm tra health 8080/8081/8082/8083, public/mine/summary/moderation, UI qua Vite `/api`, báo cáo admin và xếp hạng AI. Live smoke chỉ đọc; các ca tạo/sửa/xóa/ML/retry chạy với dữ liệu test độc lập. Tránh tạo đơn/thanh toán hoặc gửi thư khách để kiểm chứng.

## Theo dõi

- Review API readiness chỉ chứng minh own DB trả lời; không chứng minh auth/read facade/model hoạt động. Khi Identity hoặc business read facade lỗi, chức năng liên quan fail-closed.
- Worker: pending/failed, attempts, lease expiry, generation, model_version; hết retry cần moderation/retry thủ công. Backend disabled không phân tích và không tự tăng attempts.
- Relay: outbox PENDING/PUBLISHED/BLOCKED, số attempts và error class. Dùng `python -m review_service.relay --retry-event <id> --reason <lý-do>` trong process relay để retry unpublished có audit; không phát lại hàng loạt hoặc đổi event ID để né dedup.
- Khi Review lỗi: gateway vẫn phục vụ các tuyến khác theo cấu hình required_domains mặc định; request Review lỗi 502/504. Báo cáo admin trả 503 thay vì dùng sentiment archive. AI vẫn có thể tra các dữ liệu khác; phần ranking phụ thuộc Review có thể báo không khả dụng.
- Bốn bảng AI và hai bảng Review nguồn là archive. Các service mới không có source DB credential, không có FK user/film xuyên store. Source PostgreSQL superuser chưa bị thu hồi quyền DML vật lý; operator không được sửa archive.

## Quay lui

Trước terminal: giữ target writes=false và không có process ghi đích; có thể hủy bằng CLI `maintenance → monolith` có reason, giữ gateway Review ở monolith. Sau terminal/ghi mới: sửa tiến hoặc đối soát/sync ngược được kiểm chứng; CLI cố ý từ chối mở nguồn lại, downgrade `012` cũng bị chặn. Không tắt route Review để trỏ tới archive thiếu dữ liệu.

Các chức năng admin report/AI ranking hiện qua HTTP adapter, chưa phải Reporting projection hay Catalog/Cinema riêng. Khi M5–M10 tách owner, thay facade bằng contract tương ứng, không thêm SQL/credential xuyên store.
