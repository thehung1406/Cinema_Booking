# ADR 0003 — Messaging tin cậy và quyền sở hữu email

Ngày: 02/11/2026. Trạng thái: triển khai M1–M2 trên môi trường local.

## Ranh giới và hạ tầng

- Booking/Payment/Seat/Ticket vẫn trong transaction monolith. Thêm ba bảng kỹ thuật `outbox_events`, `inbox_events`, `message_replay_audits`, không thêm vào danh sách 28 entity nghiệp vụ SQLModel.
- Notification có PostgreSQL/credential riêng; chỉ giữ inbox/outbox kỹ thuật, delivery job và lịch sử lần gửi. Không import `Backend.app` hoặc đọc DB booking/user.
- RabbitMQ tách `/cinema-public` và `/cinema-private`. Publisher chỉ có quyền ghi exchange tương ứng, không đọc queue. Notification chỉ đọc queue email trong private vhost, không vào public vhost hoặc publish.
- Topology nạp từ definitions; password/hashes và service key sinh local, nằm trong tệp bị ignore. Các service không có quyền tự tạo topology.
- `BookingConfirmed.v1` chỉ có facts dùng cho báo cáo. `BookingConfirmationEmailRequested.v1` mang snapshot/recipient tối thiểu trong private vhost. Reporting không được cấp private credential.

## Giao dịch và lỗi

- Chỉ tạo events sau khi đơn PAID + CONFIRMED và vé đã flush, nhưng trước commit. Lỗi event flush/transaction rollback không để lại vé hoặc outbox nửa chừng; provider evidence vẫn được giữ theo logic đối soát hiện có.
- Relay chọn row `FOR UPDATE SKIP LOCKED`, publish persistent + mandatory và chờ publisher confirm trước khi đánh dấu PUBLISHED. Lỗi retry có backoff, quá ngưỡng BLOCKED; replay chỉ cho event chưa published và ghi audit.
- Consumer ghi inbox fingerprint và delivery job trong một transaction, rồi ACK. Commit xong mất ACK sẽ nhận lại, không tạo thêm job. Cùng event ID khác nội dung bị từ chối.
- Dedup key theo booking confirmation bảo vệ cả trường hợp cùng đơn nhưng event ID khác. Event schema và aggregate/version được kiểm tra trước nhận; payload hỏng đi DLQ.
- SMTP là process khác: claim job bằng row lock + lease, gửi ngoài DB transaction, rồi lưu kết quả. Lỗi có backoff, tối đa 5 lần mặc định rồi DEAD. Retry thủ công cần quyền hiện tại và lý do audit; không gửi lại job SENT bằng API retry.
- Crash sau SMTP chấp nhận nhưng trước commit SENT vẫn có thể gây email lặp khi lease hết hạn. Message-ID cố định hỗ trợ truy vết, không được coi là bảo đảm SMTP exactly-once.

## Cutover email

- Flag `NOTIFICATION_TRANSPORT=events` bật đường outbox và tắt producer Celery email mới. Task legacy còn để nhận backlog, nhưng ở events mode chỉ chuyển việc sang outbox cùng dedup key, không gửi SMTP.
- Overlay Notification xóa cấu hình SMTP khỏi API/worker monolith; chỉ dispatcher mới có cấu hình gửi.
- Local dùng Mailpit, không relay thư ra ngoài. Cấu hình SMTP thật thuộc lần triển khai môi trường tương ứng, không sao chép secret backend sang repository.
- Đổi flag về legacy chỉ sau khi dừng/chốt đơn đang xác nhận và đối chiếu backlog; không bật lại hai đường gửi cùng xử lý một tập đơn.

## Phạm vi đảm bảo

Broker local một node, durable queue và named volume, chưa phải HA cluster hoặc chiến lược phục hồi production. DLQ được theo dõi và không tự replay payload chưa kiểm tra. Báo cáo full bootstrap/các event khác còn theo [kế hoạch snapshot](../migration/reporting-bootstrap.md).

Nguyên tắc publisher confirm/ACK dựa trên [RabbitMQ](https://www.rabbitmq.com/docs/confirms); thuật toán hash credentials và import topology theo [passwords](https://www.rabbitmq.com/docs/passwords), [definitions](https://www.rabbitmq.com/docs/definitions). Local DB transaction theo [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).
