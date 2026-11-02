# Bỏ ứng dụng monolith khỏi repository

Ngày: 03/11/2026. Sau M10, toàn bộ runtime đã dùng 9 owner nhưng test/CI vẫn cài và import ứng dụng cũ. Đợt này xóa hoàn toàn thư mục `Backend/`, không chuyển nguyên ứng dụng sang một thư mục archive khác.

## Phân bổ phần cần giữ

| Thành phần | Vị trí hiện tại |
| --- | --- |
| Logic/API/model/DB nghiệp vụ | `services/*-service`, đã chuyển owner từ M1–M10 |
| Web contract regression | `tests/contracts/test_web_contracts.py` |
| Test dữ liệu/train cần người duyệt | `pipelines/tests/test_ml_data.py` |
| Regression hội thoại, thay context và invalid showtime | `services/ai-service/tests/test_chat_context.py` |
| Luồng gateway → Identity/Booking/Payment/Notification | `tests/integration/test_gateway_services.py` |
| Schema nguồn 001–016 cho transfer/sequence/checksum và raw SQL fence tests | `tests/fixtures/source-schema` |
| Export OpenAPI/event/schema hiện hành | `scripts/migration/export_baseline.py`, chỉ import owner packages |
| Build/test độc lập | `infra/compose/Dockerfile.tests`, Compose job `service-tests` |

Fixture schema chỉ có lịch sử Alembic/DDL, không có API, ORM ứng dụng, worker hay env reader cũ. Env của fixture từ chối DB không có `test` trong tên. Mỗi owner vẫn dùng migration và DB của chính mình trong runtime.

Đã xóa Dockerfile/API/Celery/Redis-lock implementation cũ, SQL seed/file full-DB trùng lịch sử migration, cache, script nguồn đã được exporter hiện hành thay thế, và 10 Compose overlay chuyển tiếp. Cấu hình private nguồn local được giữ riêng trong ignored `.local/`, không đưa vào image/Git; công cụ tạo cấu hình không còn đọc env ứng dụng cũ. Database/archive/backup được giữ nguyên theo retention đã chốt, không xóa volume.

## Bộ test sau khi bỏ source cũ

Test chỉ kiểm tra implementation monolith hoặc facade chuyển tiếp đã bị loại cùng implementation đó. Test Redis lock/Celery cũ không mô tả cơ chế reservation PostgreSQL/owner worker hiện tại. Các kiểm tra độc lập còn phù hợp được chuyển như bảng trên; giữ các bộ test service, transfer dữ liệu thật, race/idempotency, outbox/inbox, DLQ/SMTP, auth và report semantics hiện hành.

[Danh sách theo từng file và suite hiện hành](retired-monolith-tests.json) ghi rõ những test nguồn được nghỉ dùng. Số test mới không được trình bày như toàn bộ 436 test cũ vẫn còn nguyên. Các test bổ sung kiểm tra real owner APIs sau gateway, session revocation xuyên service, đúng một delivery job khi replay, raw SQL fences, không import bare `app`/`main`, và build/test không phụ thuộc thư mục đã xóa.

OpenAPI/schema/import baseline lịch sử giữ nguyên để đối chiếu; exporter không cố tái sinh chúng từ app đã xóa. Nếu cần điều tra mã nguồn trước khi xóa, dùng [commit 7d31b45](https://github.com/thehung1406/Cinema_Booking/tree/7d31b452d6ae0b05b8fa946759c5945c9805733e), không khởi động lại writer nguồn trên dữ liệu đã bàn giao.

## Kiểm chứng

Lệnh chuẩn từ root:

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm service-tests
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml --profile verification run --build --rm review-inference-smoke
python scripts/dev/audit_runtime.py
```

**Kết quả sau khi xóa source:** 248 tests đạt, 0 lỗi, 0 skip trong runner PostgreSQL/RabbitMQ độc lập; 89 kiểm tra host đạt. Review inference image smoke đạt. Root Compose build lại toàn bộ image thành công khi thư mục cũ không tồn tại. Credential/runtime audit đạt đủ 9 owner; gateway vẫn ready. Runtime không cần deploy thay đổi nghiệp vụ: root Compose tiếp tục phục vụ 9 API/DB, web và workers hiện tại. Cấu hình và bộ test mới được chạy sau khi thư mục nguồn đã bị xóa vật lý.
