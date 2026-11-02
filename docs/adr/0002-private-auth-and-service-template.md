# ADR 0002 — Xác thực nội bộ và bộ khung service

Ngày: 02/11/2026. Trạng thái: đã triển khai trong đợt M1/Notification.

## Quyết định

- Trong thời gian Identity còn ở monolith, service gọi `POST /internal/v1/auth/introspect` với credential service và access token của người dùng trong body. Token không xuất hiện trong query/log.
- Adapter dùng lại blacklist, kiểm tra loại/expiry/sub của JWT, trạng thái hoạt động và quyền trong DB hiện tại. Không tin role trong token như quyền hiệu lực.
- Response chỉ gồm user ID, role, active và permission codes; không trả email, mật khẩu hay refresh token.
- Consumer không giữ signing key và không cache quyền. Timeout, lỗi upstream hoặc payload sai đều từ chối thao tác; đổi quyền/khóa user được áp dụng ở lần kiểm tra tiếp theo.
- Credential tối thiểu 32 ký tự; cấu hình trống trả 503. So sánh bằng `compare_digest`. Gateway loại header danh tính giả và chặn toàn bộ `/api/internal/...`, kể cả tên path percent-encoded.
- API vận hành Notification yêu cầu cả credential nội bộ và bearer user có `notifications.manage`; quyền này được cấp cho ADMIN bằng migration `010`.
- Bộ khung tạo bằng `scripts/dev/scaffold_service.py`: settings có prefix, DB/Alembic riêng, health/readiness, auth adapter, request ID/log không chứa URL nhạy cảm, Dockerfile và test. Generator từ chối ghi đè hoặc ghi ra ngoài repository.
- `cinema-platform` chỉ chứa auth client, logging, event envelope và bảng kỹ thuật inbox/outbox/audit. Không dùng chung ORM hoặc session nghiệp vụ.

## Giới hạn và kiểm chứng

Credential service hiện dùng trong mạng local/Docker. TLS/mTLS và issuer/audience/rotation của JWT được chốt khi chuyển Identity ở M5; chưa thay cách phát JWT hiện tại. Không đưa credential vào frontend.

Đã kiểm tra bằng PostgreSQL: service credential, role DB thay claim ADMIN, đổi quyền, blacklist, refresh-token sai loại và user bị khóa. Đã chạy generator rồi upgrade/downgrade DB riêng và health test của service được sinh ra.
