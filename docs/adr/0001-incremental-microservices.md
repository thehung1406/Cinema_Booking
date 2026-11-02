# ADR 0001 — Chuyển từng miền qua gateway

Ngày: 02/11/2026. Trạng thái: áp dụng cho đợt nền tảng.

Backend hiện dùng một ứng dụng, session DB và Redis chung. Payment xác nhận ghế, đơn và vé trong transaction local; tách payment ngay sẽ làm mất ranh giới nguyên tử này.

## Quyết định

- Giữ monorepo, React và FastAPI. Gateway riêng chỉ chuyển `/api` đến monolith ở đợt này; owner DB chưa thay đổi.
- Giữ public method/path/body/status; query ký VNPay không được decode/re-encode. Không tự retry request ghi khi upstream lỗi.
- Gateway không giữ signing key, user session hoặc DB. Bearer token chuyển đến backend; backend tiếp tục xác thực user/quyền. Header giả danh user/role/internal/forwarded bị loại ở biên.
- HTTPX client dùng connection pool và streaming, nhưng từng request được tạo độc lập để tránh áp cookie của người dùng trước. Response giữ raw bytes/encoding và các Set-Cookie riêng.
- Request ID được tạo ở gateway; không log query/token/ticket path. Liveness tách readiness HTTP upstream. Readiness này không thay thế health DB/Redis của backend.
- Dùng origin backend cố định theo cấu hình; client không được chọn upstream host. Redirect nội bộ được đưa lại dưới `/api`; redirect sang VNPay ngoài hệ thống giữ nguyên.
- Owner đích: Identity (4 bảng), Catalog (7), Cinema (5), Booking (5), Payment (1), Review (2), AI (4). Tổng 28 bảng gốc; Notification và Reporting sẽ thêm store riêng.
- Booking giữ seat_status, bookings, booking_details, booking_food_items, tickets. Ghế vật lý/lịch/giá cấu hình thuộc Cinema. Snapshot món thuộc Booking dù model gốc ở `food.py`.
- Chuyển owner theo kế hoạch M0–M10; FK/join/ORM/caller phải đổi trước cutover. Không dùng SQL xuyên store làm giải pháp lâu dài.

## Hệ quả

Frontend dev cần gateway cổng 8080; chế độ quay lại backend 8000 vẫn được cấu hình. Gateway thêm một hop và điểm phụ thuộc cần đo latency. Tách dịch vụ nghiệp vụ, auth introspection, broker/outbox/inbox, routing nhiều upstream và distributed traces thuộc các phần M1/M2 tiếp theo; chưa được đánh dấu hoàn tất trong đợt này.

## Bằng chứng

[Gateway tests](../../gateway/tests/test_proxy.py), [monolith integration](../../tests/integration/test_gateway_monolith.py), [baseline](../migration/baseline.md), [kế hoạch](../../MICROSERVICES_MIGRATION_PLAN.md).
