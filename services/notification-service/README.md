# Notification Service

Service nghiệp vụ đầu tiên được tách khỏi backend: inbox, delivery job, retry và SMTP có database/credential/process riêng. Không import model nghiệp vụ hoặc truy vấn database monolith.

## Chạy local

Từ root, Python trong lệnh đầu chỉ cần standard library:

```powershell
python scripts/dev/prepare_messaging.py
docker compose --env-file .env.microservices -f compose.yml up -d --build
```

Chuẩn bị [backup/restore](../../docs/runbooks/backup-restore.md) trước khi dùng DB có dữ liệu. Notification có migration riêng `notification_001`, chạy bằng job `notification-migrate` trước consumer/dispatcher.

- Giao diện hiện tại: `http://127.0.0.1:5173`.
- Gateway: `http://127.0.0.1:8080/api/`.
- Notification health: `http://127.0.0.1:8081/health/ready`.
- **Mailpit local:** `http://127.0.0.1:8025`. SMTP mặc định chỉ vào Mailpit, không chuyển thư ra ngoài.

`.env.microservices` và `infra/broker/.runtime/definitions.json` là tệp credential/hash sinh local, bị ignore. Giữ chúng cùng bản backup broker; không xóa rồi sinh credential khác trong khi volume broker vẫn dùng credential cũ. Script không in giá trị bí mật. Notification chỉ nhận cấu hình theo role, không đọc env nguồn.

## Process và dữ liệu

| Thành phần | Vai trò |
| --- | --- |
| `notification-api` | Health, thống kê trạng thái và retry DEAD job có xác thực/audit |
| `notification-consumer` | RabbitMQ → inbox + delivery job trong cùng transaction → ACK |
| `notification-dispatcher` | Claim/lease job, gửi SMTP ngoài transaction, ghi attempt và trạng thái |
| `notification-db` | Store riêng: delivery_jobs, delivery_attempts và ba bảng messaging kỹ thuật |
| `booking-relay` | Publish event từ outbox của Booking với confirms |
| `rabbitmq` | Public/private vhost, durable queues, DLQ, credential tách theo quyền |

`POST /internal/v1/deliveries/{job_id}/retry` chỉ nhận job DEAD, yêu cầu service credential + bearer user có quyền `notifications.manage`; quyền được hỏi lại ở Identity, không cache. Không gửi lại SENT job bằng endpoint này. Thống kê tại `GET /internal/v1/deliveries/summary` cũng cùng quyền, không trả recipient/payload.

## Chạy test

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm service-tests
```

Môi trường này có PostgreSQL nguồn, PostgreSQL notification, RabbitMQ và Mailpit riêng; không dùng credential/volume ứng dụng. Bao gồm full pipeline chạy consumer/dispatcher thật, giao lại sau mất ACK, duplicate event ID, nhiều consumer/dispatcher, lease recovery, SMTP retry/DEAD/audit và schema migration của service template.

Test runner độc lập chỉ cài package service; mọi lỗi làm runner thất bại. Không chạy ứng dụng monolith.

## Đặc tính và giới hạn

- Callback trùng không tạo thêm event/job; replay event đã nhận không tự gửi lại email.
- SMTP lỗi không rollback payment/booking: việc gửi nằm sau commit và được retry trong store Notification.
- Crash sau SMTP nhận thư nhưng trước commit SENT có thể gây thư lặp khi lease hết hạn. Message-ID cố định dùng để truy vết, không hứa exactly-once ở SMTP.
- Legacy Celery email task còn như bridge cho backlog; ở events mode nó chỉ ghi private outbox, không dùng SMTP. Không bật lại flag legacy khi chưa đối chiếu pending outbox/jobs.
- Broker local một node, chưa phải HA production. Tham số retention, replica/TLS và SMTP thật được cấu hình theo môi trường triển khai.

Xem [runbook](../../docs/runbooks/notification.md), [ADR](../../docs/adr/0003-messaging-and-email-ownership.md) và [kết quả đợt này](../../docs/migration/notification-phase.md).
