# Kết quả đợt M1–M2 — 02/11/2026

Nhánh: `codex/microservices-foundation`. Tiếp nối [baseline gateway](baseline.md).

## Đã triển khai

- Auth adapter nội bộ có service credential, blacklist/token type/active user/quyền DB; client fail-closed và không cache quyền. Gateway chặn private endpoint.
- Service scaffold có cấu hình/DB/migration/image/health/auth/log/test riêng; package kỹ thuật không chứa business ORM.
- Registry routing theo miền và công tắc upstream, mặc định các miền chưa tách vẫn về monolith. Notification hoạt động qua event, không có public gateway route.
- RabbitMQ hai vhost với publisher/consumer/operator credentials tách quyền; public confirmation không có contact. Inbox/outbox/fingerprint, publisher confirms, ACK sau commit, DLQ, retry và audit.
- Notification Service có DB và migration riêng, consumer/dispatcher/API riêng. SMTP mặc định dùng Mailpit local.
- Payment giữ nguyên transaction xác nhận đơn/ghế/vé, thêm ghi public/private event trong cùng transaction. Legacy producer tắt ở events mode; task tồn dư có bridge dedup thay cho SMTP.

## Dữ liệu và môi trường local

Đã tạo backup mới lúc API/worker dừng, khôi phục và khớp row count/checksum của cả 29 bảng tại revision `009`. Bản restore được thử nâng `009 → 010`, xác nhận ba bảng messaging trước khi nâng DB local.

Đã bật overlay mới ở local: DB nguồn `010`, DB Notification `notification_001`; flag API `events`, service key có cấu hình, SMTP monolith bị tắt. Legacy queue kiểm tra bằng LLEN có 0 job, worker legacy không chạy lúc cutover. Dump và credential bị ignore, không commit dữ liệu.

Gateway/Notification readiness trả 200, frontend `/api/food-items` vẫn đi qua gateway. Endpoint nội bộ qua gateway trả 404; Notification summary không có credential trả 401. Consumer kết nối private vhost; relay/dispatcher chạy riêng. Không tạo đơn hoặc gửi email khách thật để smoke test.

## Kiểm thử

Tại lần kiểm chứng chức năng: **275 passed, 6 lỗi source-contract cũ, 1 skip**, không có lỗi mới. Bao gồm:

- Revocation/đổi quyền/khóa user, claim ADMIN không nâng role DB, lỗi/timeout identity fail-closed.
- Raw query VNPay giữ nguyên, private route bị chặn và route reviews ưu tiên đúng khi bật một upstream riêng.
- Rollback sau event flush không để lại vé/outbox, vẫn giữ provider evidence đúng logic hiện tại.
- Publisher confirm xong mất commit sẽ phát lại cùng event ID; consumer mất ACK không tạo thêm job.
- Consumer/dispatcher đồng thời, lease recovery, SMTP retry → DEAD → retry có audit, không gửi lại SENT job.
- RabbitMQ credential Notification không vào public vhost hoặc publish; poison event của consumer thật vào DLQ.
- Full pipeline từ DB nguồn riêng → relay → RabbitMQ → consumer/dispatcher processes → SMTP Mailpit, replay không gửi thêm email.
- Service generator từ chối ghi đè/path ngoài workspace; service sinh ra upgrade/downgrade DB và health hoạt động.
- Booking kèm combo qua gateway chạy cả legacy/events mode và payload thực tế khớp schema Notification; task email legacy ở events mode chỉ bridge một private event, không gửi SMTP.

Các email đều có địa chỉ tổng hợp và chỉ được giữ ở Mailpit test. Một skip là kiểm tra Docker Compose CLI bên trong image không chứa Docker CLI; có thể chạy riêng trên host như ở baseline. Chưa chạy workflow trên GitHub, mới cấu hình và chạy các lệnh kiểm tra tương ứng ở local.

## Trạng thái kế hoạch và việc tiếp theo

Các phần nền tảng M1 và Notification M2 đã có code, migrations và bằng chứng kiểm chứng; [snapshot Reporting](reporting-bootstrap.md) mới là thiết kế + queue lưu public events, chưa phải Reporting Service.

M0.7 vẫn mở: load/SLA mục tiêu trước khi thay transaction booking/payment. Broker local chưa có HA/TLS production; SMTP exactly-once không được bảo đảm khi crash sau provider accept. DLQ poison giữ để triage, không tự sửa/phát lại.

Phần tiếp theo theo kế hoạch là M3: tách AI/history/knowledge, thay truy vấn trong AI tools bằng API đọc, backfill có kiểm chứng và chuyển route qua gateway khi đủ điều kiện. Các miền Identity/Catalog/Cinema/Booking/Payment/Review/Reporting chưa được tách DB ở đợt này.
