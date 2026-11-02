# Cinema Booking

Hệ thống đặt vé FastAPI/React đã chuyển sang **9 service có database riêng**: Identity, Catalog, Cinema, Booking, Payment, Review, AI, Notification và Reporting. Gateway cung cấp API chung; Booking giữ ghế/cấp vé, Payment xử lý VNPay và saga, Reporting đọc projection từ sự kiện. Runtime cuối không chạy monolith/Celery cũ.

Source monolith đã được xóa; test/CI hiện chỉ dùng package service và fixture SQL độc lập. Xem [kết quả dọn source](docs/migration/backend-removal.md).

Kết quả và giới hạn kiểm chứng: [M10](docs/migration/reporting-phase.md). Quy trình chạy, bootstrap và phục hồi: [runbook runtime](docs/runbooks/final-runtime.md). Lịch sử từng mốc: [kế hoạch M1–M10](MICROSERVICES_MIGRATION_PLAN.md).

## Cấu trúc

```text
apps/web/                  React/Vite; Nginx phục vụ SPA và proxy /api
gateway/                  HTTP routing, composition và readiness
services/*-service/        9 owner: package, router, DB/Alembic, API và worker riêng
packages/python-platform/  Auth client, envelope, outbox/inbox, reporting transport
pipelines/ml/              Chuẩn bị dữ liệu, train/evaluate offline
model-store/               Artifact ML được duyệt; ignored, worker mount read-only
contracts/                 Hợp đồng public/private API và events
scripts/                   Migration, smoke, audit credential/runtime
infra/                     RabbitMQ và môi trường kiểm thử độc lập
compose.yml                Runtime chính tại repository root
tests/contracts/           Contract web và kiểm tra ranh giới source/build
tests/fixtures/            Schema nguồn đóng băng cho test chuyển dữ liệu
docs/                      ADR, bằng chứng chuyển đổi và runbook
```

`main.py` của service khởi tạo app, middleware/lifespan; `router/` định nghĩa endpoint và dependency HTTP. Business logic và model thuộc owner tương ứng. Service không truy vấn database của service khác. Ứng dụng monolith đã xóa khỏi working tree; test/công cụ hiện chạy độc lập. Xem [đợt bỏ monolith](docs/migration/backend-removal.md).

## Chạy local

Cần Docker Compose v2; Node 22 và Python 3.11 nếu phát triển ngoài container.

```powershell
python scripts/dev/prepare_messaging.py
# Điền các cấu hình riêng trong .env.microservices, không commit file này.
docker compose --env-file .env.microservices -f compose.yml build
```

Lần chạy đầu cần migrate các DB, bootstrap Reporting và bật writer theo thứ tự trong [runbook](docs/runbooks/final-runtime.md#khởi-tạo-mới). Không bật Reporting consumer trước bootstrap. Với môi trường đã chuyển đổi/bootstrap:

```powershell
docker compose --env-file .env.microservices -f compose.yml up -d
python scripts/dev/audit_runtime.py
```

| Địa chỉ local | Mục đích |
| --- | --- |
| http://127.0.0.1:5173 | Web |
| http://127.0.0.1:8080/api | API qua gateway |
| http://127.0.0.1:8080/health/ready | Readiness các service lõi |
| http://127.0.0.1:8025 | Mailpit cho email local |
| 127.0.0.1:8081–8089 | Notification, AI, Review, Identity, Catalog, Cinema, Booking, Payment, Reporting |

Fresh database không có tài khoản/dữ liệu phim/ghế mẫu; tạo qua quy trình quản trị của owner. Không dùng `--remove-orphans` hay `down -v` với môi trường chuyển đổi còn giữ archive.

## Kiểm thử

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm service-tests
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml --profile verification run --build --rm review-inference-smoke
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml down

cd apps/web
npm ci
npm test
npm run lint
npm run build
```

Benchmark M10 chạy riêng, tránh phụ thuộc tốc độ máy trong CI: `python -m pytest services/reporting-service/tests/benchmark_m10.py -q -s` bên trong test runner đã cài các service và cấu hình DB/broker test. Chi tiết tải/ngưỡng và bằng chứng nằm trong báo cáo M10.

VNPay thật, SMTP production và model đã được đánh giá cần cấu hình theo môi trường triển khai. M10 không phát sinh giao dịch tiền thật hoặc tự train/promote model. Khi sentiment backend bị tắt, review không được gán nhãn giả.
