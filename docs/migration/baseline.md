# Baseline và kết quả đợt gateway — 02/11/2026

Nguồn ban đầu: `main`, commit `3db6e3b`. Nhánh thực hiện: `codex/microservices-foundation`. Đã triển khai gateway riêng, frontend dev proxy, source contracts, test environment riêng và CI nền tảng. Chưa chuyển owner DB của một miền nghiệp vụ nào.

## Dữ liệu và phục hồi

- Ban đầu DB local ở revision `008`, có 28 bảng nghiệp vụ + `alembic_version`.
- Đã chạy [backup/restore](../../scripts/migration/backup-restore.ps1) khi backend/worker dừng: dump custom format, SHA256, restore vào database test mới, khớp row count và checksum nội dung cả 29 bảng.
- Bản restore nâng `008 → 009` thành công, xác nhận revision và cột `users.is_active`.
- Sau kiểm chứng, khởi động backend theo Dockerfile hiện có đã áp dụng migration `009` vào DB local. Không đổi owner hay di chuyển bảng sang store service mới.
- Dump/manifest ở `tmp/db-backups/` bị Git ignore; DB restore vẫn được giữ để kiểm tra, không commit dữ liệu cá nhân.

## Inventory và môi trường

| Thành phần | Bằng chứng |
| --- | --- |
| OpenAPI | [monolith.v1.json](../../contracts/openapi/monolith.v1.json), 90 tổ hợp method/path |
| Model/schema | [schema-baseline.json](schema-baseline.json), 28 bảng, cột và FK theo model |
| Imports | [import-baseline.json](import-baseline.json), 57 tệp có dependency `app.*` |
| Phụ thuộc liên miền | [dependency-matrix.md](dependency-matrix.md) |
| Kiến trúc | [ADR 0001](../adr/0001-incremental-microservices.md) |
| Fixture tổng hợp | [gateway-smoke.v1.json](../../contracts/fixtures/gateway-smoke.v1.json) |
| Backend được kiểm chứng | Python 3.11 trong Docker, dependency theo `Backend/requirements.txt` |
| Gateway được kiểm chứng | Python 3.11 trong Docker, Python 3.14 trong venv local |

Host có Python 3.14; cài requirements backend thất bại do `psycopg2-binary==2.9.9` không có wheel phù hợp và máy thiếu C++ build tools. Host cũng thiếu bcrypt trước kiểm chứng. Không thay pin backend để vượt lỗi môi trường; kết quả backend dùng Python 3.11 với dependency đúng dự án.

## Kết quả kiểm thử

| Kiểm tra | Kết quả |
| --- | --- |
| Gateway HTTP | 34 đạt: methods/body/auth, raw query/path, redirects, cookie isolation, gzip, duplicate headers, timeout, không retry POST |
| Gateway + monolith + PostgreSQL | 4 đạt: danh mục/auth/admin guards/AI history, callback trùng, ownership, combo + chữ ký VNPay thật với giao dịch test |
| Python suite qua Compose riêng | 230 đạt, 6 lỗi cũ, 1 skip; tổng 237 bài, không lỗi mới |
| Frontend unit | 7 đạt |
| Frontend lint/build | Đạt; có cảnh báo bundle trên 500 kB đã tồn tại |
| Browser UI | 37 layout đạt, không browser error |
| Browser food | 3 kích thước đạt: combo/món, bỏ qua, menu lỗi, retry và hết hạn |
| Browser admin | Các flow CRUD/permission/report đạt với fixture |
| HTTP local thật | Body/status backend và gateway khớp ở 7 đường đọc; Vite `/api/food-items` có request ID gateway; slash redirect giữ `/api` |

Browser tests chặn fetch/XHR bằng fixture, không chứng minh truy cập DB thật. Integration gateway–monolith dùng PostgreSQL riêng và rollback transaction; không gọi VNPay/SMTP bên ngoài. Test HMAC dùng verify thật với secret/giao dịch tổng hợp.

Một bài skip trong container là `test_ai_overlay_resolves_paths_network_and_database`, vì image test không có Docker Compose CLI. Có thể chạy riêng trên host đã cài Docker; không gắn Docker socket ứng dụng vào container test.

Đã chạy riêng `python -m pytest Backend/tests/test_docker_compose_contract.py -q` trên host có Docker CLI: cả 2 bài đạt, gồm bài bị skip trong container.

## Sáu lỗi source-contract đã có trước chuyển đổi

| Module | Test |
| --- | --- |
| `test_booking_flow_contract.py` | `test_ticket_booking_reads_query_params` |
| `test_booking_flow_contract.py` | `test_home_page_passes_film_id_to_booking` |
| `test_booking_flow_contract.py` | `test_movie_pages_pass_film_id_to_booking` |
| `test_film_contract.py` | `test_no_n_plus_one_in_main_home_page` |
| `test_film_contract.py` | `test_no_n_plus_one_in_movie_page` |
| `test_payment_contract.py` | `test_frontend_payment_components_contract` |

Các assertion kiểm tra chuỗi/tên biến JSX cũ. Không sửa UI chỉ để khớp chuỗi. [run_checks.py](../../scripts/migration/run_checks.py) vẫn chạy và báo các lỗi, không đánh dấu xfail/skip; chỉ đúng sáu test được ghi nhận là ngoại lệ baseline. Lỗi mới, collection error hoặc không có report làm CI thất bại. JUnit đầy đủ ở `tmp/microservices-tests.xml` và được CI upload khi chạy. Thay các bài source-contract bằng kiểm tra hành vi là công việc riêng.

## Đo HTTP nhẹ và giới hạn

[latency-smoke.json](latency-smoke.json) được tạo bởi [script read-only](../../scripts/migration/smoke_gateway.py): 20 request nối tiếp sau warm-up cho từng đường đọc menu. Trên máy này: backend median 7.27 ms/p95 8.51 ms; gateway median 9.82 ms/p95 11.30 ms. Đây là quan sát local có Docker, chưa phải load test hoặc SLA.

Suite PostgreSQL đã kiểm tra row-lock race, nhưng chưa đo throughput giữ ghế và thời gian xác nhận ở tải mục tiêu. M0.7 còn mở: phải chốt kịch bản/số người đồng thời/ngưỡng nghiệm thu trước khi thay giao dịch booking/payment.

## Chạy lại

```powershell
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test
.\.venv\Scripts\python.exe -m pytest gateway/tests -q
.\.venv\Scripts\python.exe scripts/migration/smoke_gateway.py
```

Smoke cần backend 8000, gateway 8080 và Vite 5173. Compose test không dùng volume/credential DB ứng dụng; `.env` thật được che bằng file mẫu trong bind mount.

Phần tiếp theo: hoàn thiện ADR/auth adapter/service template, broker/outbox/inbox ở M1 và đo tải còn thiếu, rồi mới chuyển Notification ở M2. Gateway hoạt động không có nghĩa chín miền đã tách.
