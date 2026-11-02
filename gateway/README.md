# Cinema Gateway

Gateway giữ đường dẫn `/api` và chuyển đến owner đã tách. Root `compose.yml` bật đủ 8 miền HTTP (Notification xử lý email riêng), tắt `GATEWAY_LEGACY_ENABLED`, không fallback sang monolith. Identity quyết định auth; gateway không có DB/JWT signing/VNPay/SMTP credential. `/api/internal/...` luôn bị chặn.

Chạy runtime/bootstrap theo [runbook cuối](../docs/runbooks/final-runtime.md). Môi trường đã bootstrap:

```powershell
docker compose --env-file .env.microservices -f compose.yml up -d
python scripts/dev/audit_runtime.py
```

- API: http://127.0.0.1:8080/api
- Liveness: http://127.0.0.1:8080/health/live
- Readiness: http://127.0.0.1:8080/health/ready

`GATEWAY_UPSTREAMS` là JSON map origin cố định; `GATEWAY_ENABLED_DOMAINS` gồm identity, catalog, cinema, booking, payment, review, ai, reporting. Root Compose yêu cầu readiness Identity/Booking/Payment/Reporting. AI là miền tùy chọn: outage gây lỗi request AI nhưng không hạ readiness lõi. Review rules đứng trước films tổng quát. `/admin/catalog` tổng hợp Catalog/Cinema cùng bearer, không trả partial success. Báo cáo JSON/CSV đi Reporting.

Web dùng `VITE_API_BASE_URL=/api`; Nginx hoặc Vite proxy chuyển đến gateway. Sau chuyển owner không đổi proxy về Backend cũ để rollback; giữ writer fences, sửa theo runbook owner.

Phát triển gateway bằng Python 3.11: `python -m pip install -r gateway/requirements-dev.txt`, cấu hình fixed origins đến các API local và tắt legacy, rồi `python -m uvicorn gateway.app.main:app --host 127.0.0.1 --port 8080 --no-proxy-headers --no-access-log`. File `.env.example` của gateway giữ default tương thích test lịch sử; cấu hình runtime cuối được khai báo rõ ở root Compose.

Kiểm tra host: `python -m pytest gateway/tests -q`. Kiểm tra PostgreSQL/RabbitMQ và contracts dùng project `cinema-migration-tests` trong README root. Regression hiện không chấp nhận lỗi được miễn trừ. Browser tests intercept fixture; smoke trước/sau cutover gọi API thật được ghi riêng ở [M10](../docs/migration/reporting-phase.md).

Streaming timeout trước header trả 502/504; sau khi response bắt đầu chỉ có thể đóng stream. WebSocket chưa hỗ trợ. TLS/proxy/rate limiting và capacity production cần cấu hình theo hạ tầng đích. OpenAPI được xuất trong `contracts/openapi`; runtime service tắt public Swagger.
