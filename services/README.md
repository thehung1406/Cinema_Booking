# Quy ước service Python

`notification-service` là service nghiệp vụ đầu tiên. Các service khác chỉ được tạo khi tới mốc tương ứng, không dùng folder rỗng để đánh dấu hoàn tất.

Tạo một service từ template:

```powershell
python scripts/dev/scaffold_service.py ai-service
```

Chỉ chạy khi thư mục đích chưa có. Generator tạo package riêng, settings với prefix, DB/Alembic, health/readiness, auth helper, request ID/log, Dockerfile, `.env.example` và test. Đã kiểm chứng upgrade/downgrade DB và health trên service được sinh ra trong môi trường test.

## Làm việc local bằng Python 3.11

Từ root, cài dependency backend khi chạy backend, rồi package kỹ thuật và service cần phát triển:

```powershell
python -m pip install -r Backend/requirements.txt
python -m pip install -e packages/python-platform -e services/notification-service
```

Gateway có requirements riêng. Khuyến nghị chạy backend/notification tests bằng Compose để giữ Python/driver khớp dependency hiện tại; Python 3.14 trên máy không có wheel cho psycopg2 pin của dự án.

Mỗi Dockerfile service nhận **repository root** làm build context để cài `cinema-platform`; không dùng `docker build .` từ Backend với Dockerfile mới. Compose đã cấu hình context phù hợp. Sentiment overlay giữ image/context riêng vì chưa dùng platform package.

Không đưa user/film/booking ORM, repository hoặc session nghiệp vụ vào `cinema-platform`. Module trong package này chỉ là hạ tầng kỹ thuật; mỗi service dùng engine, credential và migration của chính nó. Không đưa credential vào frontend, sample data hoặc output CI.

Hiện đã tách Notification, AI, Review, Identity, Catalog, Cinema, Booking và Payment (8/9 miền); Reporting còn ở backend nguồn. Identity dùng PostgreSQL sessions; các auth consumer hỏi Identity trực tiếp sau M5. Chạy môi trường bằng bộ mười overlay trong [runbook Payment](../docs/runbooks/payment.md).
