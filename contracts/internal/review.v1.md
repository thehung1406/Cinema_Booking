# Private Review contracts v1

Tất cả endpoint sau yêu cầu `X-Service-Key`, 401 nếu sai và 503 nếu chưa cấu hình. Gateway chặn `/api/internal/*`. Runtime Review chỉ gọi fixed-origin facade, không dùng SQL/ORM/credential của các miền khác.

| Owner hiện tại / Method/path | Input | Output |
| --- | --- | --- |
| Monolith GET `/internal/v1/review-read/films/{id}` | Film ID | `{id, title, image}` nếu phim chưa deleted; 404 khi không có |
| Monolith POST `/internal/v1/review-read/authors` | `{items: [{user_id, film_id}]}` tối đa 100 | `[{user_id, film_id, author, verified_purchase}]`; username hiện hành, badge theo booking PAID |
| Monolith GET `/internal/v1/review-read/candidates` | theater_id?, show_date?, evening? | `[{id, title, image}]` có suất ACTIVE trong phòng/rạp/phim chưa xóa, tương lai theo giờ Việt Nam; evening từ 18h |
| Monolith GET `/internal/v1/review-read/ownership` | Không | `{owner: monolith/maintenance/service}` từ durable fence + env chặt hơn |
| Review GET `/internal/v1/positive-films` | theater_id?, show_date?, evening?, window_days?, limit? | Cùng ranking DTO như public `/films/positive-trending`; có bộ lọc evening dùng cho AI |
| Review POST `/internal/v1/report-sentiments` | `{start_date, end_date, film_ids?: [id] hoặc null}` | `{positive, neutral, negative, total, pending, coverage}` |
| Review GET `/internal/v1/migration/state` | Không | `{writes_enabled: boolean}` |

Ba business read facade đều chỉ đọc; POST authors dùng body để giới hạn batch. ReadClient timeout 5 giây, không theo redirect; sai contract/lỗi upstream thì fail-closed. Báo cáo dùng khoảng ngày inclusive theo giờ Việt Nam, end+1 exclusive; tối đa chênh lệch 366 ngày như ReportFilters cũ. `film_ids=null` là không lọc, `[]` là không có phim phù hợp; theater filter được caller nguồn tính bằng lịch chiếu theo semantics báo cáo cũ. Đếm approved/chưa xóa theo review.updated_at trong khoảng và không ở tương lai; analyzed chỉ khi sentiment succeeded, label hợp lệ và content version khớp. Pending=total−analyzed, coverage=analyzed/total.

Schema typed: [read client](../../services/review-service/src/review_service/read_client.py), [report DTO/API](../../services/review-service/src/review_service/main.py), [public Review OpenAPI](../openapi/review.v1.json).

Event `ReviewChanged.v1` và `ReviewSentimentUpdated.v1` dùng [envelope](../events/v1/envelope.schema.json) với producer review, aggregate_id=review ID và aggregate_version là monotonic event_version. [Payload Changed](../events/v1/ReviewChanged.schema.json) / [Payload SentimentUpdated](../events/v1/ReviewSentimentUpdated.schema.json) là full projection facts tại phiên bản đó: film/review ID, content version, moderation/deletion, review updated_at, analysis status/label/model version; không có text review, user ID hoặc contact. Consumer dedup event_id, bỏ phiên bản cũ và áp dụng payload bằng replacement; không cộng dồn sentiment counters khi replay. M4 chưa có consumer nghiệp vụ nhận events; Reporting snapshot/checkpoint ở M10 phải bootstrap cả dữ liệu đã backfill trước khi có các event này.
