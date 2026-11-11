# AI Service

Cập nhật 04/11/2026. Owner của chatbot, lịch sử hội thoại, Knowledge Base và RAG; có PostgreSQL, Redis, Alembic và image riêng. User ID là tham chiếu ngoài miền. AI không nhận credential database của owner khác, JWT signing key, SMTP hay payment secret.

## Kiến trúc hiện tại

- Xác thực và quyền hiện hành qua private Identity API. Đọc phim, rạp, suất, giá, ghế và thống kê cảm xúc qua typed HTTP APIs của các owner.
- Planner Ollama trả dữ liệu theo schema; AI Service kiểm tra công cụ và tham số, giải tên thành ID qua owner API. Model không tự chọn URL, SQL hoặc thực hiện thao tác ghi.
- Chat đưa thẻ suất và link tới màn hình chọn ghế. Giữ ghế, tạo đơn và thanh toán tiếp tục qua luồng ứng dụng.
- PostgreSQL lưu lịch sử chính; Redis phục vụ rate limit và cache ngữ cảnh có TTL. Cập nhật hội thoại kiểm tra phiên bản và quyền sở hữu.
- KB chỉ truy xuất tài liệu đã duyệt, đúng scope/ngày hiệu lực. Có lexical, BM25, dense, hybrid và tùy chọn reranker. Embedding/reranker chạy riêng, không truy cập DB.
- Qwen3:4b qua Ollama đã được thử trong ứng dụng local. Mặc định source config vẫn tắt LLM; runtime private bật theo môi trường. Chưa có model chat fine-tune được nghiệm thu.

## Chạy và quản lý schema

Từ root, xem [vận hành AI](../../docs/runbooks/ai.md). Máy local đã cấu hình dùng:

```powershell
& scripts/ai/start_chat.ps1
```

Khởi tạo mới hoặc chạy toàn bộ stack theo [runtime chung](../../docs/runbooks/final-runtime.md); không chạy lại initializer/transfer trên dữ liệu đã có.

- Gateway: `/api/ai/*`, `/api/admin/documents*`, `/api/admin/knowledge*`.
- Health riêng: `http://127.0.0.1:8082/health/ready`.
- DB: `ai_documents`, `ai_chunks`, `ai_conversations`, `ai_messages`; migrations `ai_001 → ai_002`.
- `ai-migrate` quản lý schema owner. Job `ai-backfill` thuộc profile migration, không nằm trong luồng khởi động chatbot.

## KB và kiểm chứng

Chuẩn bị nguồn, PDF/provenance và nhập draft bằng `scripts/ai/prepare_knowledge.py`, `scripts/ai/import_knowledge.py`. CLI nhập qua API cần token có `knowledge.manage`; không tự duyệt. Người phụ trách duyệt tại `/admin/documents`, kiểm tra version và `expected_updated_at`. Sửa tài liệu làm mất phê duyệt.

DB lưu chunks cùng biểu diễn lexical hash dạng JSON. Dense E5 tính điểm qua tiến trình suy luận riêng; chưa có vector database hay chỉ mục dense được lưu bền vững. Output pilot không thay kết quả đánh giá học thuật.

Lệnh môi trường, kiểm thử Python/UI và RAG: [AI_RUNBOOK.md](../../docs/AI_RUNBOOK.md). Kết quả đã chạy và giới hạn: [AI_IMPLEMENTATION_STATUS.md](../../docs/AI_IMPLEMENTATION_STATUS.md). Hướng dẫn demo qua API thật: [AI_LOCAL_CHAT.md](../../docs/AI_LOCAL_CHAT.md).
