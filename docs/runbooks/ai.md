# Vận hành AI trong kiến trúc microservices

Cập nhật 04/11/2026. Dùng root `compose.yml`, cấu hình riêng `.env.microservices` và database của từng owner.

## Chọn hướng dẫn

| Công việc | Tài liệu hiện hành |
| --- | --- |
| Mở hoặc khởi động lại chatbot local đã có dữ liệu | [Chatbot local](../AI_LOCAL_CHAT.md) |
| Cài môi trường nghiên cứu, gán nhãn, train/evaluate, nhập KB và thử RAG | [Runbook AI](../AI_RUNBOOK.md) |
| Khởi tạo mới hoặc vận hành toàn bộ chín owner | [Runtime chung](final-runtime.md) |
| Xem tính năng đã làm, kết quả thật và phần còn thiếu | [Trạng thái AI](../AI_IMPLEMENTATION_STATUS.md) |
| Xem phạm vi sản phẩm và yêu cầu học thuật | [Kế hoạch AI](../AI_FEATURE_PLAN.md) |

Với máy local đã cấu hình và có dữ liệu, chạy từ root:

```powershell
& scripts/ai/start_chat.ps1
```

Script khởi động các API cần cho chatbot, Cinema worker, Ollama và web. Đây là luồng demo chatbot; xem runtime chung khi cần toàn bộ worker, messaging và thanh toán.

## Ranh giới dữ liệu và suy luận

- AI Service sở hữu `ai_documents`, `ai_chunks`, `ai_conversations`, `ai_messages`; schema hiện tại `ai_002`, API riêng cổng 8082.
- Review Service sở hữu review, sentiment và quyết định nhân viên; schema hiện tại `review_003`, API riêng cổng 8083. `review-worker` poll công việc có lease; `review-relay` phát outbox.
- AI xác thực qua Identity và đọc dữ liệu động qua owner APIs của Catalog, Cinema, Booking và Review. Không truy vấn chéo database.
- Web ở `apps/web`, gọi gateway tại `/api`. AI nhận các tuyến `/api/ai/*`, `/api/admin/documents*`, `/api/admin/knowledge*`.
- Qwen3:4b chạy qua Ollama riêng; embedding/reranker là tiến trình suy luận riêng. Huấn luyện và đánh giá ở `pipelines/ml`, ngoài API image/request.
- Tài liệu KB nhập bằng `scripts/ai/import_knowledge.py` luôn ở trạng thái draft; người có quyền duyệt theo phiên bản. Giá, ghế và suất lấy từ owner API, không dùng KB tĩnh thay thế.

## Kiểm tra và khôi phục

Kiểm tra gateway `/health/ready` ở cổng 8080, AI ở 8082 và Review ở 8083. Readiness không thay cho kiểm tra chất lượng câu trả lời hoặc độ mới của dữ liệu Reporting. AI không khả dụng thì xử lý lỗi trong miền AI; không đổi sang database hay writer nguồn cũ.

Giữ private config, backup database theo owner và kiểm chứng restore vào DB độc lập. Xem [backup/restore](backup-restore.md). Không chạy initializer hoặc job chuyển dữ liệu khi khởi động lại máy đã có dữ liệu.

Bằng chứng tách miền tại thời điểm M3 được lưu riêng trong [báo cáo migration](../migration/ai-phase.md). Tài liệu đó là lịch sử chuyển đổi, không phải quy trình khởi động hiện tại.
