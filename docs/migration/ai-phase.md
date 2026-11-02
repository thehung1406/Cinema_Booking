# Kết quả M3 — AI Service, 02/11/2026

Nhánh `codex/microservices-foundation`, tiếp nối [Notification M1–M2](notification-phase.md). Đã chuyển local; chưa commit/push hoặc chạy CI trên GitHub.

## Kết quả

- AI có image/package/config/health, PostgreSQL và Redis riêng; migration `ai_001` tạo bốn bảng AI. Không có business ORM/DB nguồn hoặc signing/payment/SMTP secret trong runtime mới. `user_id` là ID ngoài miền; FK message→conversation và chunk→document vẫn nội bộ.
- Chat, RAG, multi-turn context, lịch sử theo user, phân trang/xóa, kiểm soát ghi đồng thời và quản lý/duyệt tài liệu đã chuyển. RAG giữ lexical hash256-v2; model chỉ chọn evidence ID có sẵn và không được thay nội dung/URL.
- Typed read-only client gọi private facade có credential để lấy phim/rạp/lịch/giá/ghế. Auth và quyền hiện hành được introspect mỗi request, fail-closed. M3 chưa tách Identity/Catalog/Cinema/Booking/Review.
- Gateway chuyển `/ai/*`, `/admin/documents*` tới AI. Importer knowledge có bản thuộc owner AI. Báo cáo legacy không truy vấn bốn bảng AI; admin documents đã đổi tuyến. Code legacy giữ để tương thích baseline nhưng các writer/API cũ bị fence.
- Migration nguồn `011` có ownership/audit bền vững. Freeze đợi các transaction writer cũ; chat kiểm tra lại sau model I/O. Source `service` không thể tự mở lại do quên env/overlay hay downgrade schema.

## Dữ liệu và cutover local

Nguồn trước nâng: `010`, 32 bảng gồm Alembic. Đã dừng API/relay, backup custom, restore sang DB mới và khớp checksum toàn bộ 32 bảng; nâng bản restore `010 → 011` đạt rồi mới nâng nguồn. AI target cũng được backup/restore khớp cả 5 bảng trước mở ghi. Dump/credential/manifest có dữ liệu nằm trong các đường dẫn bị ignore.

Sau freeze, cả bốn bảng nguồn hiện có **0 bản ghi**. Job đối chiếu source/target count + SHA256 đạt; không có dữ liệu lịch sử cần chép ở môi trường này. Chuyển dữ liệu không rỗng đã kiểm thử trên DB riêng với cột/constraint phản chiếu từ schema nguồn đã chạy Alembic, gồm UUID, metadata JSON, vector/version, timestamp và sequence high-water mark 100000.

Đã chuyển source owner `service`, target writes=true, gateway domain ai. Nguồn `011`, target `ai_001`. Tệp bằng chứng local: `tmp/db-backups/ai-source-before-011.json`, `ai-target-before-writes.json` cùng thư mục, `tmp/ai-migration/latest.json`, `tmp/microservices-tests.xml`.

## Kiểm chứng

- Regression Docker: **292 passed, 6 lỗi source-contract legacy đã ghi nhận, 1 skip**, không có lỗi mới. Skip là Docker Compose CLI trong image; chạy hai bài compose contract trên host: **2 passed**.
- Auth boundary thật giữa hai app, user scope/role, quyền documents, token hiện hành; AI không ghi bảng nguồn. Concurrency update/delete lịch sử trả 409, commit lỗi không để hội thoại dở; rate limit/freeze/invalid context/upstream failure được kiểm tra.
- Duyệt đúng version/timestamp; sửa tài liệu hủy duyệt; model trả ID giả/text/URL giả không thay evidence. Backfill giữ dữ liệu/sequence, chạy lại idempotent, từ chối ghi đè target khác. Persistent fence chặn rollback env, đợi transaction đang chạy, thiếu ownership thì fail-closed và audit chuyển trạng thái.
- Live HTTP read-only qua gateway/Vite đạt; route AI/documents có header owner AI và yêu cầu auth, private API bị chặn, legacy AI trả 410. Đã kiểm tra GET lịch sử với token có hiệu lực và quyền documents qua AI/gateway, không in/ghi dữ liệu user.
- Đã dừng AI để thử: gateway readiness/phim/menu vẫn 200; AI trả 504 khi timeout kết nối, không fallback. Đã khởi động lại AI và xác nhận healthy. Live process đặt lại env owner=monolith vẫn bị fence nguồn chặn 410; kiểm tra runtime chỉ có DB/Redis AI, không có secret nguồn. Không tạo đơn/thanh toán hoặc gửi email khách thật.

HTTP latency trong [smoke report](latency-smoke.json) là mẫu localhost tuần tự, chưa phải kiểm thử tải/SLA M0.7. Kết quả M1–M2 trong báo cáo cũ là snapshot tại thời điểm đó.

## Phần tiếp theo

Đã có **2/9 miền với writer/DB độc lập: Notification và AI**, cùng gateway/nền messaging/auth. Phần tiếp theo là **M4 Review** (review/moderation/sentiment/worker/store). Các mốc M4–M10, HA/TLS production, user-lifecycle purge và load/SLA chưa hoàn tất. [Runbook AI](../runbooks/ai.md) có lệnh chạy, freeze, copy, cutover và quy tắc quay lui sau khi writer mới nhận dữ liệu.
