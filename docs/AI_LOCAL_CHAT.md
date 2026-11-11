# Chatbot đang chạy trên máy

Hướng dẫn dưới ghi môi trường local đã vận hành trước đây. Bạn cùng nhóm sau khi pull dùng [AI_PORTABLE_SETUP.md](AI_PORTABLE_SETUP.md): Docker tự tải model, CPU mặc định, không cần file `.local` hay tài khoản của tác giả. Profile đã được kiểm tra từ source copy và DB/cache mới; phần nghiệm thu học thuật vẫn theo checklist riêng.

Cập nhật 03/11/2026, sau yêu cầu triển khai bước 1. **Chatbot đã chạy qua giao diện với Qwen3:4B, gateway và các owner API thật.** Không còn chỉ là lượt thử dùng owner fixtures. [Trạng thái toàn bộ AI](AI_IMPLEMENTATION_STATUS.md) vẫn ghi riêng những phần học thuật/RAG chưa hoàn tất.

## Dùng ngay

1. Mở **http://127.0.0.1:5173** và đăng nhập.
2. Dùng tài khoản hiện có đã được chuyển từ dữ liệu cũ, hoặc tài khoản `cinema_demo_admin`. Mật khẩu của tài khoản demo được sinh ngẫu nhiên và lưu riêng ở `.local/runtime/demo-access.json`; không nằm trong Git hay tài liệu này.
3. Nhấn **Hỏi trợ lý** ở góc dưới và thử:

> Tối mai tôi muốn xem phim hài, hai người, tổng tiền vé dưới 250k, sau 18h.

Kết quả đã kiểm tra: phim **DEMO - Chuyến đi vui vẻ**, rạp **DEMO - Rạp thử trợ lý Cinema**, suất ngày **04/11/2026 lúc 19:00**, 12 ghế, giá 80.000đ/vé, hai vé từ 160.000đ. Suất được lấy từ Booking Service và có đường dẫn mở sơ đồ ghế tương ứng.

Có thể hỏi tiếp **“Suất thứ 1 còn ghế nào?”**, hoặc bắt đầu hội thoại mới và hỏi **“Ngày mai hai người muốn xem phim hài dưới 250k”**. Trường hợp ngân sách chưa rõ, trợ lý hỏi mỗi vé hay tổng nhóm; trả lời **“Tổng cả nhóm”** để tiếp tục. Đổi ngân sách tổng xuống 100k sẽ báo không có phương án hai vé, thay vì tạo một mức giá phù hợp giả.

## Khởi động lại

Mở Docker Desktop trước, rồi chạy tại root dự án:

```powershell
& scripts/ai/start_chat.ps1
```

Nếu vừa sửa code API, dùng `& scripts/ai/start_chat.ps1 -Build` để build image trước khi chạy. Script khởi động/warmup Ollama, các API cần thiết, Cinema worker và Vite nếu chưa chạy; chờ gateway/AI sẵn sàng rồi thông báo URL. Không tạo lại dữ liệu, không đổi tài khoản hiện có hoặc xóa volume.

Cần giữ bộ `.env.microservices` private cùng các volume owner hiện tại. Không sinh credential mới thay file bị mất khi vẫn còn DB volume. Model Ollama ở `.local/ollama-models`; inference chạy trên host, AI container gọi qua `host.docker.internal:11434`.

## Dữ liệu đang sử dụng

| Phần | Số lượng |
| --- | ---: |
| Phim cũ đã chuyển | 4 |
| Rạp cũ đã chuyển | 3 |
| Phòng cũ đã chuyển | 4 |
| Ghế cũ đã chuyển | 80 |
| Suất cũ đã chuyển | 9 |
| Đơn cũ đã chuyển | 3 |
| Thanh toán lịch sử đã chuyển | 3 |
| Phim demo được nhóm cho phép thêm | 2 |
| Rạp/phòng demo | 1 rạp, 1 phòng |
| Ghế phòng demo | 12 |
| Suất demo | 6, ngày 04–06/11/2026 |

Tất cả suất gốc đã qua. Sáu suất mới được ghi rõ DEMO để có thể kiểm tra luồng chọn ghế, không sửa ngày của suất lịch sử. Hai phim demo là nội dung giả lập, không phải lịch phát hành thật. Cấu hình demo giá 80.000đ/vé được xuất bản bằng API Catalog/Cinema và được Booking xác nhận phiên bản trước khi mở bán.

Một số tên/nhãn tiếng Việt trong DB cũ đã có ký tự `?` ngay từ nguồn. Đã giữ nguyên các bản ghi đó khi chuyển; nội dung demo mới dùng UTF-8 đúng. Không tự đoán lại những ký tự đã mất.

## Cách chuyển dữ liệu đã thực hiện

Volume gốc `cinema_booking_pgdata` chỉ được gắn read-only để sao chép sang `cinema_ai_source_snapshot_20261103`. Container cũ `postgres`, `fastapi_app`, các worker legacy vẫn dừng. Trong bản sao riêng, tạo DB `cinema_runtime_source_test` để diễn tập nâng schema lịch sử từ 009 lên 016; không chạy migration đó trên volume gốc.

Các hàm transfer của từng owner sao chép vào store mới đang khóa ghi, đối chiếu count/SHA256 các cột gốc trong transaction và từ chối ghi đè dữ liệu khác. Các bảng đặt vé/ghế được thêm snapshot kỹ thuật giữ nguyên ID/giá/lịch sử. Booking tạo reservation/checkout kỹ thuật cho lịch sử; Payment boundary tạo bằng chứng từ đơn/vé lịch sử rồi mới bàn giao sau đối chiếu. Không phát callback giả, cấp vé mới hoặc gửi email để làm bằng chứng.

Manifest ở `.local/runtime/*-copy-manifest.json`; source clone và dữ liệu owner mới đều còn trên máy. Script diễn tập một lần ở `.local/runtime/` được giữ làm bằng chứng, không chạy lại như lệnh khởi động thông thường. Sau khi đã có ghi mới, transfer cố ý từ chối target không còn giống source.

## Runtime hiện tại

| Thành phần | Địa chỉ trên host |
| --- | --- |
| Web Vite | `127.0.0.1:5173` |
| Gateway | `127.0.0.1:8080` |
| AI / Review / Identity | `8082` / `8083` / `8084` |
| Catalog / Cinema / Booking | `8085` / `8086` / `8087` |
| Payment / Reporting API | `8088` / `8089` |
| Ollama | `127.0.0.1:11434` |

Tám owner API và gateway đã healthy; mỗi owner có DB riêng, AI có Redis riêng. Cinema worker xử lý việc xuất bản cấu hình ghế/giá/suất. Reporting đã nhận snapshot/checksum của năm nguồn để gateway sẵn sàng. Broker/Notification worker chưa nằm trong bước chatbot này; API Payment đang chỉ đọc vì chưa bật giao dịch. Không nhận là đã nghiệm thu toàn bộ stack bán vé/thanh toán.

Private config chatbot: `AI_LLM_PROVIDER=ollama`, `AI_LLM_MODEL=qwen3:4b`, timeout 12 giây, `AI_LLM_KEEP_ALIVE=30m`, `AI_DIRECT_READS_ENABLED=true`, `AI_WRITES_ENABLED=true`. Model được warmup trước khi dùng; mỗi lượt giữ model trong bộ nhớ theo cấu hình keep-alive của [Ollama Chat API](https://docs.ollama.com/api/chat). Không huấn luyện/fine-tune model trong request.

KB live hiện chưa có tài liệu được nhóm duyệt. Câu hỏi chính sách thiếu nguồn sẽ báo thiếu căn cứ. Nhập/duyệt nguồn và hoàn thiện answerability của RAG thuộc bước tiếp theo, không tự nhận đã hoàn tất ở bước 1.

## Kiểm chứng đã chạy

`apps/web/tests/live-ai.mjs` dùng trình duyệt, API, PostgreSQL, Redis và Ollama thật, **không intercept XHR/fetch**. Chỉ dùng tài khoản và suất DEMO đã được cho phép. Đã đạt:

- Đăng nhập qua form bình thường, tra phim/ngày/ngân sách và nhận thẻ suất.
- Hiểu “mai” là ngày mai trong câu tư vấn, không tự chọn phim *Mai*.
- Hỏi tiếp suất thứ nhất, lấy tình trạng ghế qua đúng công cụ.
- Mở sơ đồ ghế, giữ A1 bằng giao diện rồi bỏ chọn để giải phóng ghế.
- Hỏi lại ngân sách, tiếp nối “Tổng cả nhóm”, báo không có kết quả nếu thiếu ngân sách.
- Từ chối thao tác giữ ghế/thanh toán hộ từ hội thoại; lịch sử tải được sau refresh.

Tất cả lượt hội thoại trong báo cáo đạt `mode=model_planned`. Kiểm tra DB sau chạy: vẫn 3 đơn lịch sử, 3 thanh toán lịch sử; không còn hold demo đang hiệu lực. Không có browser runtime error. Output và ảnh: `.local/evidence/live-ui/report.json`, `chat-cards-desktop.png`, `seat-selected.png`, `history-mobile.png`.

Chạy lại có chủ ý trên dữ liệu demo local:

```powershell
$env:CINEMA_LIVE_DEMO_TEST = '1'
$env:BROWSER_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node apps/web/tests/live-ai.mjs
```

Script tự dọn hold do chính nó tạo; không chạy khi muốn giữ ghế đó để thao tác thủ công. `scripts/ai/create_chat_demo.py --create-demo` có thể tạo thêm lịch demo theo ngày chạy bằng tài khoản demo; chỉ gọi khi chủ đích muốn thêm dữ liệu mới, không đưa vào startup tự động.

Hai lỗi phát hiện từ dữ liệu/chạy thật đã có regression test: Catalog cần phân biệt tên phim ngắn với từ chỉ ngày; AI phải giữ đúng công cụ cho câu hỏi rõ về giá/ghế dù model đề xuất sai. Bộ Python hiện **198 passed, 1 skipped**, web **10 unit test**, lint và build đạt. Những kết quả này chứng minh luồng local đã chạy, chưa phải đánh giá chất lượng học thuật hoặc test tải.
