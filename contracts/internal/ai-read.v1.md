# AI read facade v1

API tạm tại monolith, không public OpenAPI. Mọi endpoint yêu cầu `X-Service-Key` hợp lệ; gateway chặn `/api/internal/*`. Chỉ process nội bộ được cấu hình origin cố định mới gọi; không chuyển user SQL/model action vào facade.

| Method/path | Input | Output |
| --- | --- | --- |
| POST `/internal/v1/ai-read/matches` | `{message: string}` tối đa 2000 ký tự | `{film_id: [{id, name}], theater_id: [{id, name}]}`; entity đang hoạt động khớp tên đã bỏ dấu |
| POST `/internal/v1/ai-read/context` | `ToolContext` theo AI OpenAPI | `{film_name: string hoặc null, theater_name: string hoặc null}` sau kiểm tra ID/ngày/suất tương thích |
| POST `/internal/v1/ai-read/tool` | `{call: ToolCall, evening: boolean}` | List evidence `{id, title, text, url, kind, version?}`; URL nội bộ |
| GET `/internal/v1/ai-read/ownership` | Không có | `{owner: monolith hoặc maintenance hoặc service}` từ fence bền vững + cấu hình chặt hơn; dùng bởi job migration |

Ba POST đều chỉ đọc. `ToolCall.name` chỉ chấp nhận `search_films`, `get_showtimes`, `get_positive_films`, `get_ticket_prices`, `get_seat_availability`; không có tạo đơn, giữ ghế, thanh toán hoặc SQL. DTO `ToolCall`/`ToolContext` nằm trong [schema typed của facade](../../Backend/app/schemas/ai.py); response/client typed ở [read_client.py](../../services/ai-service/src/ai_service/read_client.py). API public riêng được lưu tại [AI OpenAPI](../openapi/ai.v1.json).

Sai credential: 401; credential chưa cấu hình: 503; input/context không hợp lệ: 422. Client có timeout 5 giây, không theo redirect; lỗi kết nối/response không đúng contract làm AI fail-closed. Facade không chép giá/ghế vào DB AI. Private migration state ở AI là GET `/internal/v1/migration/state`, cùng credential, trả `{writes_enabled: boolean}`.
