# Runtime cuối — 9 owner

Root `compose.yml` thay bộ overlay chuyển đổi. Project mặc định vẫn là `backend`, giữ nguyên tên volume/network `backend_*` hiện có. Volume/network theo project của Compose, cho phép một bản thử mới dùng project riêng mà không đụng dữ liệu cũ. Không đổi project name khi dùng dữ liệu đã cutover. `.env.microservices` và broker definitions là private; không in `docker compose config` chứa secret vào log chia sẻ. `python scripts/dev/audit_runtime.py` chỉ xuất kết quả audit đã lược giá trị. Profile AI cho máy mới ở [AI_PORTABLE_SETUP.md](../AI_PORTABLE_SETUP.md).

Ứng dụng monolith và 10 overlay chuyển tiếp đã xóa khỏi working tree. Schema nguồn dùng kiểm thử nằm ở `tests/fixtures/source-schema`, không thuộc runtime. [Chi tiết](../migration/backend-removal.md).

## Khởi tạo mới

Quy trình này chỉ dành cho DB mới rỗng. DB nguồn đang có dữ liệu phải đi qua transfer/fence theo từng runbook M2–M9, không seed/ghi đè. Đặc biệt Booking initializer từ chối tự bàn giao ledger payment legacy không rỗng.

1. Chạy `python scripts/dev/prepare_messaging.py` tại root. Script tạo hoặc bổ sung credential, giữ giá trị/password hash đang có; không dùng `--test` cho runtime chính.
2. Trong ignored `.env.microservices`, bật `IDENTITY_WRITES_ENABLED`, `CATALOG_WRITES_ENABLED`, `CINEMA_WRITES_ENABLED`, `BOOKING_WRITES_ENABLED`, `PAYMENT_WRITES_ENABLED`, `REVIEW_WRITES_ENABLED`, `AI_WRITES_ENABLED` thành `true`; giữ `REPORTING_WRITES_ENABLED=false` cho bootstrap. Cấu hình merchant/AI/SMTP theo nhu cầu môi trường; Mailpit là mặc định local. Không chuyển source DB/JWT/SMTP secret sang mọi service.
3. Build và khởi động APIs/DB/migrate:

```powershell
docker compose --env-file .env.microservices -f compose.yml build
docker compose --env-file .env.microservices -f compose.yml up -d rabbitmq mailpit identity-service catalog-service cinema-service booking-service payment-service review-service ai-service notification-api reporting-service
```

Mỗi API phụ thuộc migrate/DB của mình. Reporting readiness còn 503 khi chưa có đủ 5 snapshot; đây là trạng thái bootstrap. Đợi owner APIs healthy trước bước kế tiếp.

4. Tạo RBAC và admin đầu tiên bằng CLI chỉ hoạt động trên Identity DB rỗng:

```powershell
docker compose --env-file .env.microservices -f compose.yml run --rm --no-deps identity-service python -m identity_service.bootstrap
```

CLI hỏi username/email/name và password hai lần, không nhận password qua command line, không sửa tài khoản/RBAC có sẵn. Không chạy trên DB đã transfer. Sau đó mọi quản trị dùng đăng nhập/quyền bình thường, khách đăng ký nhận vai trò USER.

5. Khi `REPORTING_WRITES_ENABLED=false`, bootstrap qua HTTP owner APIs:

```powershell
docker compose --env-file .env.microservices -f compose.yml --profile migration run --rm --no-deps reporting-bootstrap
```

Đối chiếu count/checksum đủ 5 nguồn, backup Reporting target. Tạo/sửa dữ liệu owner trong lúc bootstrap vẫn được dirty/outbox giữ lại; stream có thể chồng snapshot, revision mới hơn thắng. Bootstrap CLI không được chạy với Reporting writer bật.

6. Bật `REPORTING_WRITES_ENABLED=true` trong private env, rồi:

```powershell
docker compose --env-file .env.microservices -f compose.yml up -d
python scripts/dev/audit_runtime.py
```

Xác nhận 9 API healthy, gateway `/health/ready`, đủ 5 verified watermark, không stale, backlog/DLQ drain và business report bằng số liệu owner. Web tại http://127.0.0.1:5173. Đăng nhập admin để nhập Catalog/Cinema qua gateway; không tạo seed tài chính giả. Sau bootstrap đã hoàn tất, lệnh `up -d` là đường khởi động thường xuyên.

## Cấu hình và quyền

Mỗi service chỉ có own DB owner credential. Report source capture chạy bằng image owner và DB owner tương ứng; Reporting bootstrap chỉ nhận own DB + private HTTP key, không nhận DSN nguồn. JWT signing key ring chỉ Identity; VNPay merchant key chỉ Payment API; SMTP password chỉ Notification dispatcher. RabbitMQ publisher/consumer có permission theo vai trò và topic producer cụ thể. Root runtime không dùng broad `env_file` trên service.

API AI không có model thì trả trạng thái phụ thuộc tương ứng; Review sentiment backend mặc định `disabled`. `model-store/` đang rỗng; chỉ mount artifact được duyệt read-only vào Review inference worker. Train/evaluate ở `pipelines/ml`, không ở request hoặc API image.

## Giám sát và diễn tập

Theo dõi health/readiness, queue depth/consumer count, outbox pending/failed age, DLQ, Reporting `stale`/watermark age và reconciliation cases Payment. Không chỉ dựa vào API 200 để kết luận report mới nhất. Reporting readiness yêu cầu đủ snapshot; freshness là field riêng, broker outage không xóa projection.

Scripts: `smoke_final_outages.py` điều phối local Identity/AI/broker outage với marker host; `smoke_reporting_dlq.py` gửi poison kỹ thuật và audited replay cùng ID. Chỉ chạy có cửa sổ bảo trì và operator role đúng DB/broker. Không dùng fixture tiền giả trên runtime thật. Xem [kết quả M10](../migration/reporting-phase.md) và [Reporting recovery](reporting.md).

## Backup, restore và archive

Backup từng DB owner kèm revision/checksum, RabbitMQ durable topology/data và private config được bảo quản riêng. Dùng [backup/restore procedure](backup-restore.md), restore vào DB độc lập trước, đối chiếu số tiền/vé và all-table checksums. Backup Reporting phải kèm source generation/checkpoint; giữ paired backups để không phục hồi lệch lịch sử. Không restore đè DB đang ghi. Không chạy initializer trên dữ liệu lịch sử.

Nếu restore source về trước revision mà Reporting đã nhận, dừng writer/capture/consumer liên quan và reconciliation theo [Reporting runbook](reporting.md). Không tự nới version/generation guard. Với Payment đã có callback thật, ưu tiên forward repair có audit/đối soát provider, không bật lại ledger writer legacy hoặc trả ownership về nguồn chỉ vì deploy lỗi.

Local cutover đã dừng `fastapi_app`, source `postgres`, source `redis`, `celery_worker`, `celery_beat`, `flower`, `pgadmin`, `backend-outbox-relay-1`; restart policy đều `no`. Database writer fences vẫn giữ. Giữ archive tối thiểu 30 ngày (từ 02/11/2026), backup tách khỏi volume và kiểm chứng restore trước khi lập đợt xóa riêng. Không chạy `down -v`, `--remove-orphans` hay source Compose để dọn tùy tiện.
