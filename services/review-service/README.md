# Review Service

Cập nhật 04/11/2026. Owner của reviews, moderation, sentiment và quyết định nhãn của nhân viên; có DB/Alembic/image riêng. User/film là ID ngoài miền; quan hệ sentiment–review nằm trong cùng store. Dữ liệu ngoài miền được đọc qua APIs của Identity, Catalog, Cinema và Booking.

## Các tiến trình

| Process | Nhiệm vụ |
| --- | --- |
| `review-service` | Review/mine/edit/delete, moderation/retry, summary/ranking và quyết định nhãn; kiểm tra token/quyền hiện hành |
| `review-worker` | Poll công việc bền vững trong `review_sentiments`, claim lease, nhả connection khi inference, kiểm tra version/generation/token trước commit |
| `review-relay` | Phát outbox lên RabbitMQ bằng credential riêng, retry và publisher confirms |
| `review-migrate` | Quản lý schema owner qua `review_001 → review_002 → review_003`; bản 003 bổ sung quyết định nhãn và audit |
| `review-backfill` | Job đặc quyền profile migration, không nằm trong luồng vận hành thường xuyên |

Gateway chuyển `/api/films/positive-trending`, `/api/films/{id}/reviews*`, `/api/films/{id}/sentiment-summary`, `/api/reviews/*` tới Review trước Catalog. Public list chỉ thấy review được duyệt/chưa xóa; mỗi user–film có một row, khôi phục sau xóa tiếp tục tăng content version.

## Quyết định nhãn và thống kê

Người có `reviews.moderate` dùng UI `/review-moderation` hoặc API:

- `GET /api/reviews/sentiment/pending`: danh sách cần rà soát theo trạng thái.
- `POST /api/reviews/{id}/sentiment-decision`: xác nhận/sửa nhãn với phiên bản và request ID.
- `GET /api/reviews/{id}/sentiment-decisions`: lịch sử quyết định.

Quyết định lưu người thực hiện, lý do và phiên bản; giữ điểm/model dự đoán ban đầu. API kiểm tra cập nhật đồng thời và gửi lại cùng request ID không tạo quyết định trùng. Sửa/xóa/retry làm kết quả cũ mất hiệu lực, inference đang chạy không được ghi đè quyết định mới.

Badge đã mua lấy bằng chứng booking PAID qua Booking API; không bắt buộc mua vé để viết review. Summary/ranking Wilson chỉ tính kết quả hợp lệ theo phiên bản, trạng thái duyệt, cửa sổ thời gian và lịch chiếu phù hợp. `ReviewChanged.v1`, `ReviewSentimentUpdated.v1` ghi cùng transaction với state; consumer xử lý trùng và thứ tự version.

## Chạy local và mô hình

Theo [runtime chung](../../docs/runbooks/final-runtime.md) khi chạy đầy đủ API/worker/relay. Cấu hình private ở `.env.microservices`; health riêng tại `http://127.0.0.1:8083/health/ready`. Chỉ migrate bằng schema thuộc Review.

Worker có image stage riêng với sklearn/joblib; API image không chứa thư viện huấn luyện. Mặc định `REVIEW_SENTIMENT_BACKEND=disabled`, công việc giữ pending. Chỉ đưa artifact đáng tin cậy, được đánh giá trên review phim vào `model-store/sentiment/`, mount read-only rồi cấu hình worker. Image mặc định hỗ trợ sklearn; transformers cần image/dependencies/Java/segmenter phù hợp. Baseline chạy trên dữ liệu ngân hàng chưa được coi là model phim đã nghiệm thu.

Lease phục hồi worker crash; retry có giới hạn. Model lỗi không xóa review hoặc tạo nhãn giả. Train/evaluate ở `pipelines/ml`, ngoài API request.

Công cụ gán nhãn, cấu hình nghiên cứu và kiểm thử: [AI_RUNBOOK.md](../../docs/AI_RUNBOOK.md). Kết quả hiện có và phần còn thiếu: [AI_IMPLEMENTATION_STATUS.md](../../docs/AI_IMPLEMENTATION_STATUS.md).
