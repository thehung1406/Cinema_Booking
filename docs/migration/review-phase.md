# Kết quả M4 — Review Service, 02/11/2026

Nhánh `codex/microservices-foundation`, tiếp nối [M3 AI](ai-phase.md). Đã triển khai/cutover local; chưa commit/push hoặc chạy workflow trên GitHub.

## Phạm vi đã hoàn tất

- Own Review DB/migration `review_001`: reviews, review_sentiments và ba bảng messaging. Film/user là ID ngoài miền, uniqueness user–film và FK sentiment→review được giữ.
- API review/mine/edit/delete/restore, moderation/pending/retry, sentiment summary và ranking chuyển gateway trước rule Catalog. Auth introspection kiểm tra active/quyền hiện hành, moderation cần `reviews.moderate`; không nâng quyền từ role claim.
- Typed private read facade cho phim/lịch đang bán/tác giả/verified_purchase. Badge PAID, window, Wilson, moderation/deletion và version giữ semantics cũ. Không import ORM/query DB nghiệp vụ khác trong runtime Review.
- Worker riêng poll pending state có lease 5 phút, retry có giới hạn, nhả DB connection trong inference. Generation riêng vô hiệu lượt phân tích sau retry/moderation cùng content version; edit/delete cũng loại kết quả cũ. Chỉ ghi DB Review, giới hạn 1 CPU/1 GiB RAM.
- ReviewChanged/ReviewSentimentUpdated và state cùng transaction; aggregate_version tăng độc lập content_version. Relay có public publisher credential riêng, confirms/retry/audit; không có contact/user ID/nội dung review trong event. M4 không nhận event ngoài nên chưa có consumer inbox nghiệp vụ; Reporting sẽ dedup/replay theo envelope/version ở M10.
- AI ranking và sentiment trong admin report dùng Review HTTP API. Báo cáo giữ khoảng ngày Việt Nam/theater-film filter/current-version/pending/coverage, không join store Review. Source `012` có fence bền vững riêng, giữ owner AI; source API/writer/worker cũ bị chặn, env rollback không mở lại writer.

## Dữ liệu và môi trường local

Đã dừng API/relay, backup và restore khớp checksum cả **34 bảng** nguồn ở `011`. Bản restore nâng `011 → 012`, xác nhận AI vẫn service và Review ban đầu monolith; sau đó mới nâng nguồn. Target Review backup/restore khớp **6 bảng** tại `review_001` trước mở ghi.

Hai bảng Review nguồn local hiện **0 bản ghi**; snapshot/count/SHA256 source-target đạt, không có dữ liệu cũ cần chép. Test chuyển dữ liệu không rỗng phản chiếu DDL legacy thật, giữ deleted/rejected/content_version/model_version/scores/attempts/timestamp, source high-water 100000 và uniqueness; đích không cần user/phim gốc và từ chối overwrite khi có ghi mới.

Hiện nguồn `012`, AI `ai_001`, Review `review_001`, Notification `notification_001`. Review owner service, writer mới bật, gateway domains ai/review. `.env.microservices`, dump và manifest đều bị ignore. Bằng chứng local: `tmp/db-backups/review-source-before-012.json`, `review-target-before-writes.json` cùng thư mục; `tmp/review-migration/latest.json`, `tmp/microservices-tests.xml`.

Sentiment vẫn **disabled**, giống cấu hình trước M4; chưa có model đã duyệt được cài cho dữ liệu ứng dụng. Worker image đã chạy thử load/inference sklearn bằng artifact tổng hợp trong schema test riêng, tạo một kết quả và hai event transaction; artifact tạm được dọn. Đây là kiểm chứng kỹ thuật, không đánh giá chất lượng model.

Kiểm tra image có thể chạy lại bằng service `review-inference-smoke` của Compose test, dùng [script chỉ chấp nhận DB test](../../scripts/migration/smoke_review_inference.py); bước này đã chạy đạt tại local và được thêm vào workflow CI.

## Kiểm chứng

- Regression Docker: **312 passed, 6 lỗi source-contract cũ, 1 skip**, không có lỗi mới. Hai bài Docker Compose contract chạy trên host: **2 passed**. Skip là image test không có Docker CLI.
- Tạo trùng, user scope, quyền bị thu hồi/active, claim ADMIN giả, stale moderation/edit, xóa/khôi phục tăng version; public visibility, auto-approve mặc định, dữ liệu nguồn không bị ghi.
- Inference chạy khi review edit/retry/delete/moderate: kết quả cũ không ghi DB/event. Worker đồng thời, lease hết hạn/worker cũ hoàn tất muộn chỉ ghi một result event; invalid scores, retry hết giới hạn/manual reset; outbox lỗi rollback cả review/job.
- Summary/ranking/window/report giữ semantics; real TestClient giữa hai app dùng identity/business read facade và Review API cho AI/admin. Sự kiện producer thật đi qua RabbitMQ public vhost bằng credential riêng và khớp schema, không in payload/contact.
- Simulated Review connection outage: ranking/report trả 503, bắt SQL chứng minh không đọc bảng Review legacy; optional Review outage không hạ gateway readiness. Thao tác thử dừng service local bị automatic approval review chặn với thông báo “blocked by policy”, nên kiểm chứng outage bằng test mô phỏng; không tuyên bố đã diễn tập outage Review trên container local.
- Live smoke chỉ đọc: public/authenticated Review qua gateway/Vite, admin report → Review API, AI read → Review ranking → business read facade đều đạt. Source env owner=monolith vẫn bị fence trả 410. Private route bị gateway chặn. Broker publisher credential kết nối được, không publish dữ liệu tổng hợp vào broker ứng dụng.
- Đã kiểm tra API/worker/relay không có DB nguồn/signing/payment/SMTP credentials; chỉ DB Review. Worker có CPU/RAM limits; gateway/Notification/AI/Review healthy. Không tạo review/order/payment hoặc gửi email khách trên dữ liệu ứng dụng.

[HTTP smoke](latency-smoke.json) chỉ là mẫu localhost tuần tự, chưa phải load/SLA. Sáu lỗi cũ và M0.7 vẫn mở. Chưa diễn tập outage container Review, chưa có production HA/TLS, chưa đánh giá/cài artifact sentiment production.

## Tiến độ

**3/9 miền có writer/store độc lập: Notification, AI, Review.** M4.1–M4.6 hoàn tất trong phạm vi local ở trên. Mốc tiếp theo là **M5 Identity**, gồm user/RBAC/session và gỡ dependency/FK/caller theo kế hoạch. [Runbook Review](../runbooks/review.md) có lệnh chạy/freeze/copy/cutover/retry và giới hạn quay lui.
