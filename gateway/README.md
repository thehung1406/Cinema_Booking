# Cinema Booking Gateway

Gateway là process/image riêng, mặc định chuyển `/api/...` về `Backend` hiện tại. Notification đã tách DB và nhận sự kiện; AI và Review có DB riêng và tuyến HTTP riêng sau cutover. Backend vẫn quyết định xác thực/phân quyền cho các miền chưa tách.

## Chạy bằng Docker

Từ root repository, cần `Backend/.env` hợp lệ và đã sao lưu DB trước khi nâng revision:

```powershell
python scripts/dev/prepare_messaging.py
docker compose --env-file .env.microservices -f Backend/docker-compose.yml -f docker-compose.microservices.yml -f docker-compose.notifications.yml -f docker-compose.ai-service.yml -f docker-compose.reviews.yml -f docker-compose.identity.yml -f docker-compose.catalog.yml up -d --build
```

Backend Dockerfile hiện chạy `alembic upgrade head` lúc khởi động; lệnh trên có thể nâng DB hiện tại lên `012`. Xem [backup/restore](../docs/runbooks/backup-restore.md) trước khi dùng với DB có dữ liệu.

- Gateway: `http://127.0.0.1:8080/api/`
- Liveness: `http://127.0.0.1:8080/health/live`
- Readiness HTTP: `http://127.0.0.1:8080/health/ready`
- Swagger hiện tại vẫn ở backend: `http://127.0.0.1:8000/docs`.

## Chạy gateway bằng Python

Từ root, với Python 3.11 được khuyến nghị cho stack backend hiện tại:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r gateway/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn gateway.app.main:app --host 127.0.0.1 --port 8080 --no-proxy-headers --no-access-log
```

`gateway/.env` là tùy chọn, lấy mẫu từ `.env.example`. Gateway không cần `Backend/.env` hoặc password DB/VNPay. Nếu gateway và backend cùng chạy bằng Docker, origin backend là `http://fastapi:8000`; local mặc định `http://127.0.0.1:8000`.

## Frontend và quay về backend trực tiếp

Frontend dùng `VITE_API_BASE_URL=/api`; dev proxy mặc định giữ `/api` và chuyển đến gateway 8080. Nếu `.env` cũ còn base URL tuyệt đối 8000, request sẽ đi thẳng backend và bỏ qua proxy; cần đổi field này thành `/api`.

Chỉ trước khi chuyển owner mới được quay toàn bộ HTTP về monolith bằng các giá trị sau trong `Frontend/.env`, rồi khởi động lại Vite:

```dotenv
VITE_API_BASE_URL=/api
VITE_API_USE_GATEWAY=false
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

Để dùng lại gateway: `VITE_API_USE_GATEWAY=true`, target `http://127.0.0.1:8080`. Sau M3–M6, giữ gateway để sử dụng các owner mới; không quay proxy về monolith như cách rollback AI. Xem [runbook Identity](../docs/runbooks/identity.md). Không downgrade schema hoặc khôi phục DB chỉ vì gateway lỗi.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest gateway/tests -q
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test
```

Compose kiểm thử tạo PostgreSQL/Redis riêng, không publish port, không dùng volume DB ứng dụng và che `.env` thật bằng file mẫu. Test gateway–monolith dùng PostgreSQL transaction được rollback; VNPay/SMTP không được gọi thật. JUnit ở `tmp/microservices-tests.xml`.

Runner báo riêng sáu source-contract failures đã tái hiện trước chuyển đổi; bất kỳ lỗi mới/collection error đều trả exit code lỗi. Chi tiết trong [baseline](../docs/migration/baseline.md). Browser tests dùng fixture bị intercept và chứng minh UI hoạt động, không được xem là bằng chứng gọi backend thật.

## Giới hạn đợt này

- Hỗ trợ cấu hình upstream theo miền; mặc định tất cả miền HTTP vẫn về monolith. WebSocket chưa được hỗ trợ.
- Timeout trước khi gửi response trả 502/504; lỗi khi response stream đã bắt đầu sẽ đóng kết nối, không thể đổi status.
- Auth adapter/broker/outbox/Notification đã có trong đợt tiếp theo; xem [Notification](../services/notification-service/README.md). Không dùng header danh tính do client gửi để thay token. `/api/internal/...` luôn bị chặn.
- Swagger qua backend 8000; chưa đưa trang Swagger đầy đủ qua gateway.
- Dev proxy và Compose local đã cấu hình; production TLS, trusted proxy/IP chain, rate limiting và triển khai nhiều replica cần cấu hình ở các mốc tiếp theo.

Tham khảo kỹ thuật: [HTTPX async/manual streaming](https://www.python-httpx.org/async/), [FastAPI khi đứng sau proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).

## Bật upstream cho một miền khi tách tiếp

`GATEWAY_UPSTREAMS` là JSON map origin cố định; `GATEWAY_ENABLED_DOMAINS` chỉ bật miền đã qua cutover. Cấu hình AI đã bật trên máy hoàn tất M3:

```dotenv
GATEWAY_UPSTREAMS={"ai":"http://ai-service:8082"}
GATEWAY_ENABLED_DOMAINS=["ai"]
```

Các miền hợp lệ: identity, catalog, cinema, booking, payment, review, ai, reporting. Cấu hình thiếu/không hợp lệ bị từ chối khi startup. Rule review đứng trước films tổng quát; `/admin/catalog` vẫn về monolith đến khi có aggregation tương thích. Không tự fallback sang owner cũ khi service mới lỗi. Không tắt cờ route sau khi đã chuyển writer mà chưa đồng bộ dữ liệu theo runbook.

Readiness chỉ kiểm tra monolith và các miền trong `GATEWAY_REQUIRED_DOMAINS` (mặc định `[]`). AI là miền tùy chọn: outage không hạ readiness toàn gateway; request AI vẫn trả 502/504, không fallback.

Sau M6, `/admin/catalog` tổng hợp Catalog/Cinema tại gateway, cùng bearer và không partial success. Bộ bảy overlay và cách vận hành: [runbook Catalog](../docs/runbooks/catalog.md).


Cập nhật M7: Cinema đã tách store/writer và thay đường schedule legacy bằng sales version/ACK. Catalog hiện `catalog_002` có confirm/release và closure tombstone; các bước M6 ở trên là bằng chứng lịch sử. Vận hành mới nhất dùng tám overlay và [báo cáo Cinema](../docs/migration/cinema-phase.md).


Cập nhật M8: Booking/payment legacy đã chuyển sang store riêng; Cinema publication origin là Booking `8087`. Vận hành hiện tại dùng chín overlay, giữ source expiry/relay dừng. Xem [Booking M8](../docs/migration/booking-phase.md).
