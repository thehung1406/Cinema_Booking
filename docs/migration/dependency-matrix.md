# Dependency cần tháo trước khi chuyển owner

Theo source baseline, không phải danh sách service đã tách. [Import đầy đủ](import-baseline.json) và [FK theo bảng](schema-baseline.json) cung cấp inventory chi tiết.

| Miền | Coupling hiện tại | Thay thế cần xây | Gate trước cutover |
| --- | --- | --- | --- |
| Identity | `dependencies.py` đọc User/RolePermission chung; FK user từ booking/hold/review/chat; admin ghi user/RBAC | Auth/active/permission adapter, store Identity; ID ngoài miền/snapshot hồ sơ | User mới dùng booking/review/chat không cần chép user gốc vào DB cũ |
| Catalog | Film/Genre/Format liên kết lịch qua FK/ORM; FoodService quote/save cùng session booking | Film lifecycle versioned; quote giữ giá; lưu BookingFoodItem ở Booking | Không hard-delete ID đang dùng; menu đổi không đổi đơn cũ |
| Cinema | Showtime composite FK vào FilmFormat; Booking đọc Seat/SeatType/giá trực tiếp | API phim; snapshot sales_version, close/drain/reopen | Không lịch trùng, không nhận hold mới sau đóng bán |
| Booking | Đọc Show/Seat/SeatType/Food/User; lịch sử JOIN nhiều miền | Snapshot phim/rạp/ghế/giá/quote, hold binding với đơn, idempotency | Nhiều ghế nguyên tử; không đọc store Cinema/Catalog/Identity |
| Payment | Ghi Payment/Booking/SeatStatus và issue Ticket cùng transaction; Redis lock theo booking | Checkout snapshot, outbox/inbox, event kết quả và đối soát | Callback trùng/muộn/broker lỗi/PAID không vé đều xử lý, một writer |
| Review | Review/sentiment cùng User/Film DB; ranking đọc lịch/phim; worker dùng config chung | API phim/lịch/auth; store/worker riêng, event versioned | Kết quả cũ không đè content_version mới; moderation/ranking đúng |
| AI | `ai_tools.py` đọc Film/Theater/Showtime/CinemaRoom/SeatType, gọi SeatService; chat FK user | Typed HTTP clients chỉ đọc, auth adapter, bốn bảng AI riêng | Không SQL xuyên owner; giữ quyền sở hữu chat/approval/version tài liệu |
| Notification | PaymentService gọi email task sau commit; worker/config dùng chung | Event trong transaction, outbox, delivery consumer/store, snapshot gửi thư | Một đường gửi, dedup job; SMTP lỗi không rollback booking |
| Reporting | `admin_repo.report` JOIN Booking/Payment/Ticket/SeatStatus/Showtime/Film/Review | Projection/checkpoint/snapshot replay; API đọc tạm lúc chuyển | Đối chiếu doanh thu/ghế/cảm xúc, không đếm đôi attempt/replay |

## Caller và cấu hình dùng chung

- `router/admin.py`, `schemas/admin.py`, `admin_service.py`: chia về owner, không chép nguyên module cho mọi service.
- `/admin/catalog`: cần gateway aggregation với timeout/contract; chưa triển khai aggregation trong đợt gateway đầu.
- `core/database.py`, `models/__init__.py`: giữ ở legacy cho đến khi từng miền có engine/migration riêng; không chia sẻ toàn bộ ORM trong package chung.
- `worker/tasks.py`: cleanup theo Booking, email theo Notification; không để hai scheduler cũ/mới cùng làm việc mà thiếu chống trùng.
- `worker/ai_tasks.py`: sentiment/retry thuộc Review; AI Service không ghi DB Review.
- Frontend `api.js`: một base `/api`; Vite chọn gateway hoặc backend trực tiếp, giữ route UI.

Bỏ FK phải đi cùng thay ORM relationship, JOIN, validation và lifecycle. Giữ ID/snapshot tham chiếu ngoài miền; constraint trong cùng miền vẫn thuộc DB owner.

## Thay đổi đã hoàn tất ở M3

AI runtime đã thay mọi truy vấn nghiệp vụ legacy bằng `ReadSession` HTTP tới facade `/internal/v1/ai-read/{matches,context,tool}`. Facade hiện vẫn nằm ở owner monolith của các miền phim/rạp/booking/review và chỉ đọc. Khi các owner này tách ở các mốc sau, đổi adapter/facade theo contract, không cấp credential DB của chúng cho AI.

Bốn bảng AI thuộc store `ai_001`, user ID không có FK sang Identity. `/ai/*` và `/admin/documents*` đã chuyển gateway; importer mới ở `ai_service.import_knowledge`. Nguồn `011` giữ ownership/audit và chặn API/writer cũ. Báo cáo admin không JOIN bảng AI. Archive legacy cùng FK cũ chưa bị xóa; không dùng nó để cấp dữ liệu cho chức năng hiện hành. [Kết quả/giới hạn M3](ai-phase.md).

## Thay đổi đã hoàn tất ở M4

Review runtime sở hữu hai bảng riêng, không có FK tới User/Film. Phim/lịch/tác giả/verified purchase qua typed facade `/internal/v1/review-read/*`; worker ML và relay chỉ ghi store Review. Source `012` đăng ký fence riêng; API review đã đổi gateway, legacy writers/inference bị chặn. AI positive ranking và `admin_repo.report` thay phần đọc Review bằng HTTP adapter, không dùng archive làm fallback. Events có full projection facts không có nội dung/user ID; consumer Reporting/dedup/backfill thuộc M10. [Bằng chứng M4](review-phase.md).

## Thay đổi đã hoàn tất ở M5

Identity sở hữu users/RBAC/login_sessions trong DB riêng; monolith/AI/Review/Notification dùng introspection hiện hành. Booking/SeatStatus cùng AI/Review archive không còn FK/relationship tới User. Booking lưu contact snapshot và callback/history không JOIN user; Review author facade lấy profile qua Identity. Source 013 có DB trigger/fence/audit, archive user/RBAC không phải fallback sau cutover. Session PostgreSQL thay Redis auth theo ADR 0006, legacy token phải đăng nhập lại. [Bằng chứng M5](identity-phase.md), [contract](../../contracts/internal/identity.v1.md).

## Thay đổi đã hoàn tất ở M6

Catalog sở hữu bảy bảng phim/phân loại/menu cùng food_quotes/schedule_bindings. Source 014 bỏ Film/Format/Food external FK và Film–Showtime ORM links, backfill snapshot lịch/đơn, fence cả Catalog writers lẫn thay đổi lịch trong freeze. Booking/confirmation dùng historical snapshots; report giữ nhãn hiện hành qua Catalog API; AI/Review facades hỏi Catalog. `/admin/catalog` tổng hợp tại gateway theo auth của từng owner. New film/format/food tạo ở Catalog dùng được ở source mà không mirror. Tham chiếu sau lỗi source được giữ an toàn; confirm/release và sales lifecycle thuộc M7. [Bằng chứng M6](catalog-phase.md), [contract](../../contracts/internal/catalog.v1.md).
