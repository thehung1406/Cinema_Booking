# Review Service

Cập nhật 20/11/2026. Owner của nhận xét và phân tích cảm xúc tự động; có DB/Alembic/image riêng. User/film là ID ngoài miền; quan hệ sentiment–review nằm trong cùng store. Dữ liệu ngoài miền được đọc qua APIs của Identity, Catalog, Cinema và Booking.

## Các tiến trình

| Process | Nhiệm vụ |
| --- | --- |
| `review-service` | Review/mine/edit/delete, danh sách quản trị/retry, summary/ranking; kiểm tra token/quyền hiện hành |
| `review-worker` | Poll công việc bền vững trong `review_sentiments`, claim lease, nhả connection khi inference, kiểm tra version/generation/token trước commit |
| `review-relay` | Phát outbox lên RabbitMQ bằng credential riêng, retry và publisher confirms |
| `review-migrate` | Quản lý schema owner qua `review_001 → review_002 → review_003`; bản 003 bổ sung quyết định nhãn và audit |
| `review-backfill` | Job đặc quyền profile migration, không nằm trong luồng vận hành thường xuyên |

Gateway chuyển `/api/films/positive-trending`, `/api/films/{id}/reviews*`, `/api/films/{id}/sentiment-summary`, `/api/reviews` và các route con tới Review trước Catalog. Nhận xét mới/cập nhật luôn công khai ngay, không chờ phân tích. Public list chỉ thấy nhận xét công khai/chưa xóa; mỗi user–film có một row, khôi phục sau xóa tiếp tục tăng content version.

## Quản lý nhận xét và thống kê

Người có `reviews.moderate` dùng dashboard `/admin/reviews`; đường dẫn `/review-moderation` chuyển tới trang này. API:

- `GET /api/reviews`: danh sách chưa xóa, mới nhất trước; trả `{items, total}`. Bộ lọc: `q` (nội dung), `film_id`, `sentiment`, `analysis_status`, `moderation_status`; phân trang `offset`, `limit` (mặc định 20, tối đa 100).
- `DELETE /api/reviews/{id}`: chủ nhận xét hoặc nhân viên có quyền trên được xóa; xóa nội dung và vô hiệu hóa phân tích trong cùng transaction.
- `GET /api/reviews/{id}/sentiment-decisions`: lịch sử quyết định cũ, chỉ đọc.

Đã bỏ API ghi duyệt nội dung và xác nhận nhãn. Bảng audit cũ được giữ nguyên. Mô hình trả điểm hợp lệ sẽ hoàn tất với nhãn có điểm cao nhất; ngưỡng tin cậy chỉ điều khiển fallback, không tạo hàng chờ nhân viên. Sửa/xóa/retry làm kết quả cũ mất hiệu lực; inference đang chạy không được ghi đè phiên bản mới.

Badge đã mua lấy bằng chứng booking PAID qua Booking API; không bắt buộc mua vé để viết review. Summary/ranking Wilson chỉ tính kết quả hợp lệ theo phiên bản, trạng thái công khai, cửa sổ thời gian và lịch chiếu phù hợp. `ReviewChanged.v1`, `ReviewSentimentUpdated.v1` ghi cùng transaction với state; consumer xử lý trùng và thứ tự version.

## Chuyển nhận xét cũ sang công khai

Sau khi build/chạy phiên bản mới, chạy trong root project đang có `.env.microservices`:

```powershell
docker compose --env-file .env.microservices exec -T review-service python -m review_service.backfill_public_reviews
```

Lệnh yêu cầu `REVIEW_WRITES_ENABLED=true`: công khai bài đang chờ, đưa kết quả `needs_review` về `pending` và phát outbox trong cùng transaction. Giữ nguyên ngày tạo/sửa, phiên bản nội dung, bài bị từ chối, bài đã xóa và lịch sử quyết định. Có thể chạy lại; dòng đã chuyển không bị xử lý lần nữa. Khi backend phân tích đang disabled, bài vẫn hiển thị và công việc chờ đến lúc mô hình được nạp.

## Chạy local và mô hình

Theo [runtime chung](../../docs/runbooks/final-runtime.md) khi chạy đầy đủ API/worker/relay. Cấu hình private ở `.env.microservices`; health riêng tại `http://127.0.0.1:8083/health/ready`. Chỉ migrate bằng schema thuộc Review.

Worker có image stage riêng với sklearn/joblib; API image không chứa thư viện huấn luyện. Mặc định `REVIEW_SENTIMENT_BACKEND=disabled`, công việc giữ pending. Chỉ đưa artifact đáng tin cậy, được đánh giá trên review phim vào `model-store/sentiment/`, mount read-only rồi cấu hình worker. Image mặc định hỗ trợ sklearn; transformers cần image/dependencies/Java/segmenter phù hợp. Baseline chạy trên dữ liệu ngân hàng chưa được coi là model phim đã nghiệm thu.

Lease phục hồi worker crash; retry có giới hạn. Model lỗi không xóa review hoặc tạo nhãn giả. Train/evaluate ở `pipelines/ml`, ngoài API request.

Công cụ gán nhãn, cấu hình nghiên cứu và kiểm thử: [AI_RUNBOOK.md](../../docs/AI_RUNBOOK.md). Kết quả hiện có và phần còn thiếu: [AI_IMPLEMENTATION_STATUS.md](../../docs/AI_IMPLEMENTATION_STATUS.md).
