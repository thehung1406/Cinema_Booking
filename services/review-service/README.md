# Review Service

Owner của reviews, moderation và sentiment, có DB/Alembic/image riêng. User/film là ID ngoài miền; FK sentiment→review vẫn thuộc store này. API và worker không truy vấn DB monolith, AI hoặc Notification.

| Process | Nhiệm vụ |
| --- | --- |
| `review-service` | Review/mine/edit/delete, moderation/retry, summary và ranking; auth adapter kiểm tra token/quyền hiện hành |
| `review-worker` | Poll job bền vững trong `review_sentiments`, claim lease, nhả connection khi inference, kiểm tra lại version/generation/token trước commit |
| `review-relay` | Publish outbox với confirms lên public vhost bằng credential riêng; retry có giới hạn và audit |
| `review-migrate` | Alembic `review_001`: hai bảng nghiệp vụ + ba bảng messaging |
| `review-backfill` | Job đặc quyền profile migration, chỉ chép hai bảng allowlist từ nguồn; runtime không có credential nguồn |

API giữ các route cũ qua `/api`: `/films/positive-trending`, `/films/{id}/reviews*`, `/films/{id}/sentiment-summary`, `/reviews/*`. Gateway chọn Review trước Catalog. Các thao tác kiểm duyệt/retry yêu cầu `reviews.moderate`, không suy quyền từ claim role. Public list chỉ thấy bản approved/chưa xóa; mỗi user–film có một row, khôi phục sau xóa tiếp tục tăng content version.

Phim/lịch đang bán, tên tác giả và badge đã mua được lấy qua typed read-only facade. Badge giữ semantics cũ: có booking PAID cho user/phim; không thêm điều kiện mua vé để được viết review. Ranking Wilson chỉ dùng kết quả hiện hành, review approved/chưa xóa, trong cửa sổ và có lịch chiếu phù hợp.

## Chạy local

Chuẩn bị [runbook Review](../../docs/runbooks/review.md) trước lần cutover đầu. Từ root, giữ credential và cờ của máy đã chuyển:

```powershell
python scripts/dev/prepare_messaging.py
docker compose --env-file .env.microservices -f Backend/docker-compose.yml -f docker-compose.microservices.yml -f docker-compose.notifications.yml -f docker-compose.ai-service.yml -f docker-compose.reviews.yml -f docker-compose.identity.yml -f docker-compose.catalog.yml up -d --build
```

Health: `http://127.0.0.1:8083/health/ready`. Nguồn hiện `014`, AI `ai_001`, Review `review_001`, Notification `notification_001`, Identity `identity_001`, Catalog `catalog_001`. Mặc định install mới chưa chuyển owner/writer; cần làm M3, M4 rồi M5 theo runbook. Máy đã cutover dùng `.env.microservices` hiện có.

## Inference và lỗi

Worker có image stage `worker` với sklearn/joblib; API stage `api` không cài các thư viện ML. Compose giới hạn worker 1 CPU/1 GiB RAM, mount artifact chỉ đọc. Mặc định `disabled` giữ review pending, không tạo nhãn giả. Cài artifact operator đã duyệt tại `model-store/sentiment/` gồm `metadata.json` có `model_version` và `model.joblib`, đặt `REVIEW_SENTIMENT_BACKEND=sklearn`, rồi recreate worker. Backend transformers cần image có thêm dependencies/Java/segmenter và cấu hình artifact tương ứng; image mặc định này chỉ đóng gói sklearn. Không dùng model tổng hợp kiểm thử làm model ứng dụng.

Lease 5 phút phục hồi worker crash; retry tối đa 5 attempts, failed job chờ ít nhất 60 giây. Sau hết attempts, người có quyền dùng API retry để reset generation/attempts. Model lỗi/scores sai không làm mất review hoặc tăng counter thống kê. Edit/delete/moderation/retry vô hiệu lượt đang chạy, kể cả cùng content version; inference cũ không được ghi kết quả hoặc event.

`ReviewChanged.v1` và `ReviewSentimentUpdated.v1` ghi cùng transaction với state. Hai event chứa facts phục vụ projection, không có nội dung review, user ID hoặc thông tin liên hệ. `aggregate_version` là thứ tự thay đổi riêng của review, tăng cả khi moderation/retry/inference; khác `content_version`. Relay là at-least-once, consumer tương lai phải dedup envelope/event ID và xử lý version. M4 chưa nhận event từ service khác, nên chưa có consumer inbox nghiệp vụ.

## Kiểm thử

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml --profile verification run --build --rm review-inference-smoke
python -m pytest Backend/tests/test_docker_compose_contract.py -q
.venv/Scripts/python.exe scripts/migration/smoke_gateway.py --ai http://127.0.0.1:8082 --review http://127.0.0.1:8083
```

Test DB/broker/ML artifact độc lập dữ liệu ứng dụng. [Kết quả M4 và giới hạn kiểm chứng](../../docs/migration/review-phase.md).

Sau M5 dùng đủ sáu overlay và `REVIEW_IDENTITY_ORIGIN` trỏ Identity. [Runbook Identity](../../docs/runbooks/identity.md).

Sau M6 dùng bộ bảy overlay; facade phim/tác giả/lịch chỉ đọc Catalog/Identity/Cinema đúng owner, không JOIN Catalog archive. [Runbook Catalog](../../docs/runbooks/catalog.md).
