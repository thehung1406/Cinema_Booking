# Trạng thái hoàn thiện AI chatbot

Ngày kiểm tra: **20/11/2026** (Asia/Saigon). Runtime local: Compose project `backend`, OpenAI `gpt-4.1-mini`.

## Đã xong

| Hạng mục | Kết quả và bằng chứng |
| --- | --- |
| Tìm câu hỏi ngắn | Điều chỉnh ngưỡng lexical theo số từ khóa. Test có nguồn đúng, sai scope, nguồn chưa duyệt, câu không có từ khóa và từ khóa không tồn tại. |
| Tiếp nối hội thoại | Giữ công cụ đang chờ khi người dùng bổ sung phim/rạp/mã suất dù planner bật; có test đổi sang nội dung phim hoặc chính sách. |
| Giảm lượt gọi model | Câu hỏi giá/ghế có mã suất đi thẳng đến đọc dữ liệu; không bỏ qua xác minh ngữ cảnh. |
| Provider của công cụ | Benchmark đọc `AI_LLM_PROVIDER`, hỗ trợ OpenAI/Ollama. Startup chỉ warmup Ollama khi chọn Ollama, dùng đúng model/origin. Test startup không cần credential riêng. |
| Hướng dẫn KB | Cập nhật `pipelines/knowledge/booking-guide.md`, manifest phiên bản `draft-2-20261120`; trích xuất 10 block, 1.879 ký tự, không có cảnh báo. Nhập qua API quản trị thành tài liệu ID 1, **approved=false**. Artifact local: `.local/knowledge/booking-guide.draft.json`. |
| Đồng bộ runtime | Build và cập nhật AI, Booking và Web, giữ nguyên volume và credential. AI/Booking healthy; các endpoint đặt vé mới tới được qua gateway và từ chối payload không hợp lệ. |
| Kiểm tra frontend | `npm test`: 13 passed; lint và production build đạt. `chat-booking-flow.mjs` và `ai-flow.mjs` đạt trên bản web sau cập nhật, không có browser runtime error. Các luồng này dùng API fixture, không phải giao dịch thanh toán thật. |
| Scope trống từ model | Tái hiện `knowledge_scope=""` từ OpenAI thật; xử lý chuỗi rỗng/null riêng tại đầu ra planner, không chấp nhận scope lạ. Chạy lại thật đạt `mode=model_planned`. |
| Bộ test Python | **161 passed, 1 skipped**, bao gồm AI owner, RAG, provider và transfer từ schema legacy sang DB test riêng. Test bị skip là migration của **Review owner** do không cấp `REVIEW_DATABASE_URL` riêng trong lượt kiểm tra chatbot; migration AI đã chạy. Có 1 cảnh báo deprecation AnyIO/Starlette, không có test thất bại. |
| Giao diện với API thật | Đăng nhập tài khoản demo có sẵn, nhận thẻ suất, mở “Đặt trong chat” và tải danh sách ghế thật. Không giữ ghế, tạo đơn hoặc thanh toán. Ảnh local: `.local/evidence/chatbot-deployed.png`. Các hội thoại smoke do lượt kiểm tra tạo đã được xóa. |

## Kết quả smoke trên runtime thật

| Yêu cầu | Kết quả | Thời gian một lượt |
| --- | --- | --- |
| Ngày mai, phim hài, hai người, tổng dưới 250k | `ok`, `model_planned`, 1 thẻ suất | 1.812 ms |
| Giá vé mã suất 9 | `ok`, `retrieval_only`, đúng tool tra giá | 47 ms |
| Mã suất 9 còn ghế nào | `ok`, `retrieval_only`, đúng tool tra ghế | 49 ms |
| Hướng dẫn đặt vé | `no_evidence`, không đưa nguồn chưa duyệt vào câu trả lời | 831 ms |

Đây là **một lượt smoke**, không phải SLA, benchmark tải hay kết quả đánh giá độc lập. Không so với số đo trước sửa để suy ra phần trăm cải thiện. Báo cáo local: `.local/evidence/chatbot-completion-api.json`.

## Cần người xác nhận

| Việc chưa hoàn tất | Bằng chứng / lý do | Bước tiếp theo và điều kiện hoàn thành |
| --- | --- | --- |
| Duyệt và công bố hướng dẫn KB | Tài liệu ID 1 đang là bản nháp. Bot chưa dùng tài liệu chưa duyệt để trả lời. | Người có `knowledge.manage` đọc tại `/admin/documents`, kiểm tra đúng ứng dụng rồi công bố. Hoàn tất khi câu hỏi hướng dẫn trả được nguồn đúng phiên bản qua giao diện thật. |
| Chính sách hoàn tiền, đổi/hủy vé và thời hạn giữ ghế | Chưa có nguồn được xác nhận; hướng dẫn không tự đặt số phút hoặc hứa hoàn tiền. | Người phụ trách cung cấp quy định, ngày hiệu lực; nhập và duyệt thành tài liệu riêng. Kiểm tra cả câu được phép trả lời và câu thiếu căn cứ. |
| Bản dịch và trích đoạn điện ảnh | Nguồn trong `pipelines/knowledge/sources.json` còn yêu cầu review. | Đối chiếu bản dịch với trang gốc, kiểm tra phạm vi sử dụng, tác giả và trang trích; chỉ công bố bản đã xác nhận. |
| Bộ câu hỏi đánh giá độc lập | Bộ development hiện có ghi rõ AI soạn, chưa phải gold được người chấm độc lập. | Người đánh giá xác nhận đáp án/nguồn/câu cần từ chối; giữ tập đánh giá tách khỏi câu dùng chỉnh prompt. Hoàn tất khi có bộ câu hỏi và điểm correctness, groundedness, citation, refusal đã duyệt. |

## Chưa kiểm chứng

| Việc còn thiếu | Bước tiếp theo | Tiêu chí hoàn thành |
| --- | --- | --- |
| Benchmark model thật có hệ thống | Dùng `scripts/ai/benchmark_rag_answers.py` với provider hiện dùng và corpus/câu hỏi đã duyệt; chạy từ root, cấu hình qua biến môi trường riêng, không ghi API key vào báo cáo. | Có median/P95 thời gian phản hồi, usage/token từ trace OpenAI, tỷ lệ lỗi và điểm chấm của người. Vài câu smoke không đủ kết luận chất lượng. |
| Chịu tải nhiều người dùng | Chạy trên dữ liệu/tài khoản test riêng, tăng số người dùng đồng thời; đo timeout, 429 và fallback do giới hạn suy luận. | Có mức tải mục tiêu, số đo và giới hạn vận hành được chốt. |
| Đặt vé/thanh toán xuyên suốt thực tế | Kiểm tra trong môi trường thanh toán sandbox, gồm hết hạn giữ ghế, retry, callback và phát hành vé. | Có bằng chứng giao dịch sandbox khớp Booking/Payment/vé, không trùng đơn hoặc trừ tiền. Chưa chạy thanh toán thật trong lượt này. |
| Ollama thật | Startup và benchmark Ollama đã có test giả lập; chưa gọi model Ollama thật trong lượt này. | Chạy lại với provider Ollama trên máy có đúng model và xác nhận kết quả tương đương hợp đồng API. |

## Giới hạn và cách kiểm tra lại

- Trước khi tạo PR, đã áp dụng riêng bản sửa lên `main` mới nhất (base `5dc720c`) và chạy lại: **165 test Python passed, 1 test migration Review skipped**, 13 test frontend passed, test startup ba provider passed. Số 161 phía trên ghi lượt kiểm chứng runtime trước khi cập nhật base.
- Các test Python chạy trong container với PostgreSQL/Redis test riêng, không dùng DB ứng dụng để test migration/transfer. Chỉ nhập một tài liệu draft qua API ứng dụng.
- Test migration Review bị bỏ qua vì thiếu `REVIEW_DATABASE_URL` test; không phải test chấm tay. Các điểm chấm người đánh giá vẫn chưa có và không được thay bằng điểm tự sinh. Có cảnh báo deprecation AnyIO của Starlette TestClient, không làm test thất bại.
- Không thay model, thêm framework agent, vector database, fine-tuning hoặc tự duyệt nguồn.
- Kiểm tra nhanh: `powershell -File tests/ai/test_start_chat.ps1`; frontend chạy `npm test`, `npm run lint`, `npm run build` tại `apps/web`. Các test trình duyệt dùng `UI_BASE_URL` và `BROWSER_EXECUTABLE` phù hợp máy.
- Các thay đổi giao diện đã có trước lượt này được giữ nguyên; không tạo commit gộp chúng vào phần sửa chatbot.
