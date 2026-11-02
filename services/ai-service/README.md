# AI Service

Owner của chat, lịch sử hội thoại, tài liệu kiến thức và RAG. Có PostgreSQL, Redis, Alembic và image riêng; user ID là tham chiếu ngoài miền, không có FK tới bảng user legacy.

Runtime chỉ nhận `AI_*`: không có signing key, SMTP/payment secret hoặc credential DB nguồn. Xác thực và quyền `knowledge.manage` được hỏi lại qua private identity API; các công cụ chỉ đọc phim/rạp/suất/giá/ghế qua typed HTTP facade. Model chỉ được chọn evidence ID đã có; nội dung và URL trả về lấy từ evidence.

## Chạy

Từ root dùng [runtime cuối](../../docs/runbooks/final-runtime.md), giữ `.env.microservices` đã sinh:

```powershell
python scripts/dev/prepare_messaging.py
docker compose --env-file .env.microservices -f compose.yml up -d --build
```

Root runtime chuyển AI qua gateway, bật đọc trực tiếp APIs của owner và tắt legacy fallback. Writer phải được bật sau khởi tạo/chuyển dữ liệu theo runbook; cấu hình local hiện hành nằm trong `.env.microservices`.

- API qua gateway: `/api/ai/*`, `/api/admin/documents*`.
- Health riêng: `http://127.0.0.1:8082/health/ready`.
- DB: `ai_documents`, `ai_chunks`, `ai_conversations`, `ai_messages`; migration `ai_001`.
- Redis riêng giữ rate limit/context có TTL; PostgreSQL là nguồn lịch sử chính.
- `ai-backfill` là job đặc quyền chạy một lần, thuộc profile `migration`; đây là thành phần duy nhất được cấp credential nguồn để chép bốn bảng allowlist. API không dùng job này.

## Nhập tài liệu

Import tài liệu đã duyệt bằng `python -m ai_service.import_knowledge <reviewed.json>` trong môi trường AI owner. File là JSON list theo `DocumentWrite`; `approved: true` phải có `reviewer`. File phải có sẵn trong container hoặc được mount chỉ đọc. CLI từ chối khi writer bị khóa; không có model sinh chính sách tự duyệt.

UI admin tiếp tục dùng API cũ qua gateway: sửa tài liệu sẽ bỏ phê duyệt; duyệt phải khớp version và `expected_updated_at`.

## Kiểm thử

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm service-tests
python scripts/dev/audit_runtime.py
```

Test dùng DB/Redis/broker/Mailpit riêng. Runner chỉ cho phép đúng sáu lỗi source-contract legacy đã ghi nhận; mọi lỗi mới đều làm lệnh thất bại. [Bằng chứng M3](../../docs/migration/ai-phase.md).

Sau M5, `AI_IDENTITY_ORIGIN` trỏ Identity và người dùng cần đăng nhập lại bằng tài khoản cũ. [Runbook Identity](../../docs/runbooks/identity.md).

Sau M6, facade AI đọc phim qua Catalog API; dùng bộ bảy overlay trong [runbook Catalog](../../docs/runbooks/catalog.md).
