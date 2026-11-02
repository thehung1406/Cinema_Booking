# Vận hành Notification và cutover email

> Tài liệu lưu bằng chứng cutover lịch sử. Ứng dụng monolith và các overlay đã xóa ở đợt [dọn source](../migration/backend-removal.md); lệnh lịch sử cần source tại [commit 7d31b45](https://github.com/thehung1406/Cinema_Booking/tree/7d31b452d6ae0b05b8fa946759c5945c9805733e). Vận hành hiện tại dùng root `compose.yml` và [runbook runtime](../runbooks/final-runtime.md).

> Runbook này lưu quy trình cutover tại mốc lịch sử. Runtime hiện hành dùng root `compose.yml`: xem [runbook cuối](final-runtime.md) và [M10](../migration/reporting-phase.md). Không khởi động source/overlay cũ trên dữ liệu đã bàn giao.

Máy đã hoàn tất M6 dùng bộ **bảy Compose file** trong [runbook Catalog](catalog.md), giữ credential/cờ cutover hiện có. Các bước dưới đây mô tả mốc trước đó.

Máy đã hoàn tất M5 phải dùng bộ **sáu Compose file** và auth origins trong [runbook Identity](identity.md), giữ credential/cờ cutover hiện có. Các bước phía dưới mô tả mốc chuyển miền trước đó.

## Khởi động và kiểm tra

Từ root, dùng **cả năm Compose file sau M4** để duy trì `NOTIFICATION_TRANSPORT=events` và cấu hình SMTP tách khỏi monolith:

```powershell
python scripts/dev/prepare_messaging.py
docker compose --env-file .env.microservices -f Backend/docker-compose.yml -f docker-compose.microservices.yml -f docker-compose.notifications.yml -f docker-compose.ai-service.yml -f docker-compose.reviews.yml up -d --build
```

Kiểm tra gateway 8080 và Notification 8081 tại `/health/ready`. Mailpit tại `http://127.0.0.1:8025`; đây là môi trường giữ thư local, không gửi ra Internet.

Chỉ dùng hai file gateway sẽ không áp dụng overlay Notification. Không đổi qua lại bộ Compose/flag mà chưa kiểm tra đơn đang xác nhận, outbox và delivery backlog.

## Theo dõi và chẩn đoán

- Monolith outbox: PENDING đang chờ, PUBLISHED đã có broker confirm, BLOCKED cần xử lý. `last_error` chỉ lưu loại lỗi, không lưu URL chứa password.
- Delivery: PENDING → PROCESSING → SENT; lỗi → RETRY → DEAD sau số lần cấu hình. Lịch sử nằm ở delivery_attempts.
- SMTP/Notification DB/broker dừng: booking vẫn xác nhận bằng transaction DB nguồn; outbox giữ event, consumer/dispatcher tiếp tục khi phục hồi. Readiness API không có nghĩa worker/SMTP chắc chắn đang chạy; kiểm tra process và lag/job status.
- Payload hỏng/không hỗ trợ: vào `notification.email.dead.v1`, không tạo delivery job. Không replay hàng loạt dữ liệu chưa xác minh hoặc đổi event ID chỉ để bỏ qua dedup.
- `reporting.bootstrap.v1` giữ public facts cho giai đoạn Reporting; không purge queue để làm đẹp số liệu.

Xem queue counts, không in nội dung thư:

```powershell
docker compose --env-file .env.microservices -f Backend/docker-compose.yml -f docker-compose.microservices.yml -f docker-compose.notifications.yml exec rabbitmq rabbitmqctl -q list_queues -p /cinema-private name messages_ready messages_unacknowledged
```

Kiểm tra log consumer/dispatcher/relay bằng `docker compose ... logs --tail 50 <service>`. Log ứng dụng không chứa recipient hoặc payload email.

## Retry delivery DEAD có audit

Đặt access token ADMIN đang có quyền `notifications.manage` vào biến môi trường local `CINEMA_ADMIN_TOKEN`; không ghi token vào repository/lệnh có lịch sử chia sẻ. Ví dụ PowerShell:

```powershell
$runtimeKeys = Get-Content .env.microservices -Raw | ConvertFrom-StringData
$headers = @{
  'X-Service-Key' = $runtimeKeys.INTERNAL_SERVICE_KEY
  Authorization = "Bearer $env:CINEMA_ADMIN_TOKEN"
}
Invoke-RestMethod -Uri 'http://127.0.0.1:8081/internal/v1/deliveries/summary' -Headers $headers
$body = @{ reason = 'Đã sửa cấu hình SMTP' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8081/internal/v1/deliveries/JOB_UUID/retry' -Headers $headers -ContentType 'application/json' -Body $body
```

Chỉ retry sau khi kiểm tra nguyên nhân. API kiểm tra quyền hiện tại, ghi actor/reason và từ chối SENT/PROCESSING. Người vận hành lấy job UUID từ công cụ quản trị store Notification theo quyền của owner, không chia sẻ payload chứa thông tin cá nhân.

## Retry outbox BLOCKED

Sau khi sửa broker/topology, retry đúng event còn chưa publish, giữ event ID:

```powershell
docker compose --env-file .env.microservices -f Backend/docker-compose.yml -f docker-compose.microservices.yml -f docker-compose.notifications.yml exec outbox-relay python -m app.worker.outbox_relay --retry-event EVENT_UUID --reason 'Broker đã phục hồi'
```

Đây là thao tác đặc quyền local/container của owner nguồn; audit ghi `local-operator`. CLI từ chối event đã PUBLISHED. Không sửa tiền, recipient hoặc trạng thái đơn để khắc phục lỗi gửi thư.

DLQ có dữ liệu hỏng phải được cách ly/đối chiếu producer và schema trước. Retry DEAD job và outbox chưa publish đã có công cụ; đợt này không có lệnh tự sửa hoặc tự phát lại payload poison trong DLQ.

## Cutover và rollback

1. Kiểm tra backup/restore nguồn, migration `010`, store `notification_001`, topology/credential và worker readiness.
2. Tạm dừng writer lúc đổi producer; đợi payment transaction đang chạy, kiểm tra backlog Celery và các task đang thực thi. Đợt local 02/11/2026 có queue `celery=0`, không có worker legacy đang chạy.
3. Bật events, tắt SMTP của monolith và khởi động relay/consumer/dispatcher. Nếu có legacy backlog, task events-mode chỉ chuyển sang outbox sau khi xác minh đơn PAID + CONFIRMED và dedup; không gửi SMTP từ task cũ.
4. Quan sát pending/blocked/dead counts và kiểm tra mail capture trên môi trường test. Không tạo giao dịch khách thật chỉ để thử gửi thư.
5. Muốn quay về legacy: dừng nhận xác nhận mới, drain hoặc đối chiếu chính xác event/job nào đã gửi, dừng đường gửi mới, rồi mới đổi flag/writer. Không đơn giản bật lại SMTP và replay tất cả đơn.
6. Không downgrade/drop messaging tables hoặc restore DB cũ khi đã có event/job mới. Có backup riêng của source DB, Notification DB và broker volume; phục hồi kèm dedup/checkpoint đối soát.

Credential/hashes sinh local không được tự xoay bằng cách xóa file trong khi broker volume còn giữ user cũ. Rotation cần quy trình cập nhật broker + app, rồi thu hồi credential cũ.
