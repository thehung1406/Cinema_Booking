# AI read contracts v1 — owner APIs

Root runtime bật `AI_DIRECT_READS_ENABLED=true`. AI đọc fixed-origin APIs của Catalog/Cinema/Booking/Review; không dùng HTTP facade monolith đã nghỉ hoạt động. Mọi private call có `X-Service-Key`, timeout 5 giây, không theo redirect. Gateway chặn `/api/internal/*`.

| Nhu cầu | API owner |
| --- | --- |
| Match tên phim/rạp | Catalog `POST /internal/v1/films/matches`; Cinema `POST /internal/v1/theaters/matches` |
| Thông tin phim | Catalog `POST /internal/v1/films/batch` hoặc `/search` |
| Xác minh context phim/rạp/ngày/suất | Catalog batch, Cinema `GET /theaters/{id}`, Booking `POST /internal/v1/booking-read/context` |
| Suất/giá/ghế | Booking `POST /internal/v1/booking-read/tool` |
| Phim được đánh giá tích cực còn suất phù hợp | Review `GET /films/positive-trending` với theater/date/evening |

DTO `ToolCall`/`ToolContext` ở [AI schemas](../../services/ai-service/src/ai_service/schemas.py); response/client typed ở [read_client.py](../../services/ai-service/src/ai_service/read_client.py). Các công cụ được phép: `search_films`, `get_showtimes`, `get_positive_films`, `get_ticket_prices`, `get_seat_availability`. Evidence có `{id,title,text,url,kind,version?}`; URL nội bộ được validate. Model không được chọn API/URL tùy ý, viết SQL, tạo đơn, giữ ghế hoặc thanh toán.

Credential sai: 401; thiếu credential: 503; context không hợp lệ: 422. Lỗi kết nối/DTO fail closed, không fallback sang archive hoặc truy cập DB owner. AI không chép giá/ghế vào DB của mình. Public API được xuất tại [AI OpenAPI](../openapi/ai.v1.json). Contract HTTP facade M3 trước đây xem trong Git tại commit `7d31b45`.
