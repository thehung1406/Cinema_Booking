# Kết quả M5 — Identity Service, 02/11/2026

Nhánh `codex/microservices-foundation`, tiếp nối [M4 Review](review-phase.md). Đã triển khai/cutover local; chưa commit/push hoặc chạy workflow trên GitHub.

## Đã hoàn tất

- Identity có DB/tài khoản, image, Alembic `identity_001`, health và API riêng. Owner users, roles, permissions, role_permissions và login_sessions. Auth/access-control/admin session/nhân viên đã chuyển gateway.
- Token mới có kid/issuer/audience/type/timing/sub/session/JTI; signing key ring chỉ thuộc Identity. Session/refresh digest lưu PostgreSQL, fixed TTL; logout thu hồi cả access/refresh của phiên, khóa tài khoản thu hồi mọi phiên. Quyền/active đọc hiện hành khi introspect, không tin role claim và không cache. [Contract](../../contracts/internal/identity.v1.md), [ADR](../adr/0006-identity-tokens-and-session-store.md) ghi cả rotation, timeout và giới hạn in-flight request.
- Monolith, AI, Review và Notification API đều hỏi Identity. Legacy introspection facade forward đến Identity sau cutover, không đọc user/RBAC archive. Profile API allowlist thay tên tác giả Review; admin catalog dùng quyền trong context. Không cấp DB Identity/signing key cho consumer.
- Source migration `013` điền contact snapshot cho đơn cũ, bỏ user FK ở Booking/SeatStatus và AI/Review archive, gỡ reverse ORM relationship. Đơn mới chụp tên/email/phone từ profile API; lịch sử/confirmation/outbox email chỉ đọc snapshot, không phụ thuộc Identity khi callback đang xử lý.
- Source users/RBAC có trigger chặn INSERT/UPDATE/DELETE và lock ownership chung transaction; chuyển owner đợi writer cũ kết thúc. Fence có audit/terminal state, env rollback không mở writer. Legacy Redis sessions không được nhập: tất cả người dùng cần đăng nhập lại, giữ nguyên ID/mật khẩu.
- Copy chỉ bốn bảng allowlist, giữ bcrypt hash/ID/timestamp/active/RBAC, high-water sequence, count/SHA256; transaction và từ chối divergent target/target đã phát sinh session. Cleanup CLI xóa phiên đã hết hạn quá retention, expiry được kiểm tra độc lập cleanup.

## Dữ liệu và cutover local

Dừng source API/relay, backup/restore khớp checksum **34 bảng** nguồn ở `012`. Trên restore đã thử `012 → 013`, xác nhận snapshot đơn cũ đầy đủ và không còn FK tham chiếu users từ miền khác, rồi mới nâng source. Không có HOLD đang hoạt động ở thời điểm inventory.

Đã freeze source Identity, copy và đối chiếu đủ **5 users, 4 roles, 11 permissions, 20 role_permissions**. Backup/restore target khớp checksum **6 bảng** ở `identity_001` trước mở writer. Source Identity chuyển terminal `service`, target writer bật; gateway domains `ai/review/identity`. AI/Review/Notification auth origins trỏ Identity trực tiếp. Nguồn hiện `013`; AI `ai_001`, Review `review_001`, Notification `notification_001` không đổi.

Bằng chứng local (bị ignore): `tmp/db-backups/identity-source-before-013.json`, `identity-target-before-writes.json`, `tmp/identity-migration/latest.json`, `tmp/m5-tests-final.log`, `tmp/microservices-tests.xml`. Dump chứa dữ liệu tài khoản và chỉ ở máy local.

## Kiểm chứng

- Regression Docker: **332 passed, 6 lỗi source-contract cũ, 1 skip**, không có lỗi mới. Skip vẫn là container test không có Docker CLI. Host chạy thêm Docker Compose contracts và gateway tests: **59 passed**, gồm hai ca Identity readiness bắt buộc/tùy chọn. Fixture đơn PostgreSQL cập nhật snapshot để phản ánh migration mới; các assertion email/outbox cũ giữ nguyên.
- Token giả/sai key/none algorithm/hết hạn/thiếu claim/sai issuer/audience/type/session, tự gán role, session deadline và legacy JWT bị từ chối. Grant/revoke/đổi role phản ánh ngay; khóa/unlock không hồi sinh phiên cũ. Logout và rotation overlap/retirement kiểm chứng trên DB test riêng.
- Transfer phản chiếu DDL nguồn thật, kiểm tra hash bcrypt cũ đăng nhập được, timestamp/active/RBAC/sequence high-water 100000 và từ chối overwrite. DB source guard chặn raw SQL sau freeze; env reset vẫn trả 410 cho legacy auth ở runtime local.
- Tài khoản đăng ký **chỉ trong DB Identity** đi qua auth monolith, hold/booking service, xác nhận IPN giả lập và private email outbox, Review API và AI/history trên các store test riêng. Không mirror user vào source; user khác không đọc được đơn/chat. Confirmation/history vẫn đạt khi profile API không khả dụng. Auth outage mô phỏng trả 503, không fallback archive.
- Live gateway smoke: auth/me, booking history, AI history, admin session/employees/catalog, Review moderation đạt đúng quyền; customer không vào admin session, header tự khai user/role không xác thực được. Private auth path bị gateway chặn, legacy login trả 410. Dùng hai phiên kỹ thuật ngắn hạn cho tài khoản có sẵn để kiểm tra đọc, xóa cả hai sau kiểm tra; không tạo user/order/review/payment hoặc gửi email trên dữ liệu ứng dụng. Không tuyên bố đã kiểm chứng password login thật của tài khoản khách qua browser.
- Gateway/Identity/AI/Review/Notification/source healthy; Identity là required domain của gateway readiness sau cutover. Kiểm tra environment runtime: Identity không có credential DB nguồn/payment/SMTP; consumer không có DB/signing key Identity. Không diễn tập dừng Identity container; outage kiểm chứng bằng mô phỏng.

M0.7 (load/concurrency/SLA), sáu lỗi frontend source-contract cũ, HA/TLS production và user hard-delete/purge chưa hoàn tất. Không có endpoint xóa user trong phạm vi M5; khóa tài khoản giữ lịch sử. Session DB thay Redis auth theo ADR; chưa có cache hoặc producer/consumer UserAccessChanged vì không dùng invalidation để cấp quyền.

## Tiến độ

**4/9 miền có writer/store độc lập: Notification, AI, Review, Identity.** M5.1–M5.7 hoàn tất trong phạm vi local ở trên. Tiếp theo là **M6 Catalog**. [Runbook M5](../runbooks/identity.md) có bộ sáu Compose file, copy/freeze/cutover/rotation/cleanup và giới hạn quay lui sau khi target nhận ghi.
