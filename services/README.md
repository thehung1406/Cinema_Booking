# Quy ước service Python

`notification-service` là service nghiệp vụ đầu tiên. Các service khác chỉ được tạo khi tới mốc tương ứng, không dùng folder rỗng để đánh dấu hoàn tất.

Tạo một service từ template:

```powershell
python scripts/dev/scaffold_service.py ai-service
```

Chỉ chạy khi thư mục đích chưa có. Generator tạo package riêng, settings với prefix, DB/Alembic, health/readiness, auth helper, request ID/log, Dockerfile, `.env.example` và test. Đã kiểm chứng upgrade/downgrade DB và health trên service được sinh ra trong môi trường test.

## Làm việc local bằng Python 3.11

Từ root, dùng virtual environment riêng cho package kỹ thuật và service cần phát triển:

```powershell
python -m pip install -e packages/python-platform -e services/notification-service
```

Gateway có requirements riêng. Khuyến nghị chạy service tests bằng Compose để giữ Python/driver khớp dependency hiện tại; Python 3.14 trên máy không có wheel cho psycopg2 pin của dự án.

Mỗi Dockerfile service nhận **repository root** làm build context để cài `cinema-platform`; không build từ thư mục service với context thiếu package chung. Compose đã cấu hình context phù hợp. Review inference worker có image/dependency ML riêng; API không cài training/inference stack.

Không đưa user/film/booking ORM, repository hoặc session nghiệp vụ vào `cinema-platform`. Module trong package này chỉ là hạ tầng kỹ thuật; mỗi service dùng engine, credential và migration của chính nó. Không đưa credential vào frontend, sample data hoặc output CI.

Hiện đã tách đủ **9/9 miền** gồm Reporting. Chạy runtime bằng root `compose.yml`, theo [runbook cuối](../docs/runbooks/final-runtime.md). Mỗi service có `router/` cho endpoint/dependency HTTP; `main.py` chỉ khởi tạo app/middleware/lifecycle. Booking chia router theo chức năng; các service còn lại gom endpoint trong `router/api.py`. Identity dùng PostgreSQL sessions; auth consumer hỏi Identity trực tiếp. Reporting chỉ đọc DB projection của mình.
