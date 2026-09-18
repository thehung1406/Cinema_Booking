# Triển khai AI Cinema Booking

Ngày cập nhật: 17/09/2026. Phạm vi đã thống nhất: xây dựng mã ứng dụng, mã huấn luyện và dữ liệu mẫu để con người rà soát; chưa có dữ liệu nghiệp vụ đã duyệt hoặc mô hình đã huấn luyện để nghiệm thu chất lượng AI.

## 1. Trạng thái bàn giao

| Hạng mục | Hiện trạng |
| --- | --- |
| Đánh giá phim | API tạo/sửa/xóa, một bản ghi mỗi tài khoản/phim, duyệt theo phiên bản; giao diện tại trang chi tiết phim |
| Kiểm duyệt | API chỉ dành cho STAFF/ADMIN; giao diện `/review-moderation`, có liên kết khi đăng nhập tài khoản nhân viên |
| Phân tích cảm xúc | Celery queue riêng, nạp model một lần mỗi worker; hỗ trợ artifact sklearn và PhoBERT; mặc định tắt khi chưa có model |
| Thống kê | Truy vấn dữ liệu hiện hành, cửa sổ mặc định 30 ngày, ba nhãn riêng, số đang xử lý/cần rà soát; Wilson, ngưỡng 10 và kiểm tra suất còn hiệu lực |
| Trợ lý | `/ai/chat` có đăng nhập, giới hạn tần suất, ngữ cảnh theo tài khoản có TTL; 5 công cụ chỉ đọc, hỏi lại khi thiếu tham số |
| RAG cơ sở | Vector từ vựng băm 256 chiều lưu JSON trong PostgreSQL; chỉ lấy tài liệu đã duyệt và đến ngày hiệu lực; thay phiên bản/thu hồi nguyên tử |
| Mô hình hội thoại | Mã LoRA thực sự, lưu adapter/tokenizer; dịch vụ suy luận riêng, giới hạn một yêu cầu suy luận đồng thời |
| Dữ liệu khởi đầu | 100 bình luận, 30 mẫu hội thoại và 6 tài liệu, đều là bản nháp chưa được người dùng duyệt |
| Đánh giá | Mã Macro-F1, precision/recall/F1 từng lớp, confusion matrix, độ trễ; so sánh mô hình gốc/adapter và ba cách xếp hạng |

RAG hiện là **baseline từ vựng**, chưa phải embedding ngữ nghĩa/pgvector. Thống kê được tính trực tiếp từ các bản ghi hiện hành thay vì bảng cache `film_sentiment_stats`, tránh dữ liệu cũ và cộng trùng. Có thể thêm cache hoặc materialized view sau khi đo tải.

Trợ lý hiện dùng định tuyến nghiệp vụ có quy tắc. Mô hình mở được tinh chỉnh cho nhiệm vụ chọn chứng cứ trong ngữ cảnh; backend hiển thị nguyên văn chứng cứ đã chọn. Đây là lựa chọn triển khai ban đầu để giá, chính sách và nguồn không bị mô hình tự viết lại. Chưa triển khai hội thoại sinh văn bản tự do, định tuyến hoàn toàn bằng mô hình, QLoRA, embedding ngữ nghĩa hoặc cá nhân hóa.

Chưa có trọng số/adapter được tạo từ dữ liệu đã duyệt; chưa chạy thử mô hình hội thoại để đo tốc độ; chưa có kết quả trước/sau fine-tuning. Việc sửa prompt, tạo tài liệu và viết mã huấn luyện không được tính là đã fine-tune.

## 2. Các bảng và dịch vụ tái sử dụng

- `users`, `films`, `theaters`, `cinema_rooms`, `showtimes`: nhận dạng và ngữ cảnh nghiệp vụ.
- `seat_types.base_price`: giá hiện tại; `SeatService.get_seats_by_showtime`: kết hợp ghế đã bán trong DB và ghế giữ trong Redis, không tiết lộ chủ ghế.
- `bookings.payment_status`: chỉ gắn nhãn “Đã mua vé” nếu có giao dịch PAID cho phim; không suy ra nhãn cảm xúc.
- Xác thực và phân quyền: `get_current_user`, `require_staff` sẵn có.
- Migration `005` thêm `reviews`, `review_sentiments`, `ai_documents`, `ai_chunks`.

Nội dung đánh giá bị sửa sẽ tăng `content_version`, hủy kết quả trước và trở về chờ duyệt. Worker đọc văn bản, giải phóng transaction trước khi suy luận, khóa và đọc lại bản ghi trước khi lưu. Kết quả khác phiên bản bị bỏ. Retry ghi đè một kết quả, không cộng vào bộ đếm. Xóa đánh giá xóa nội dung và loại ngay khỏi tổng hợp.

## 3. Chạy ứng dụng

Lệnh backend chạy trong thư mục `Backend`. Tạo `.env` từ `.env.example` nếu chưa có; không ghi đè cấu hình riêng. Cần PostgreSQL và Redis có thể kết nối. Chạy migration trước khi worker xử lý đánh giá.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Ở các terminal khác, khởi động worker nghiệp vụ và beat như cấu hình hiện có. Worker cảm xúc dùng queue riêng; trên Windows dùng pool solo. Trên Linux dùng concurrency 1, có thể tăng sau khi đo RAM/độ trễ.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai-inference.txt
.\.venv\Scripts\python.exe -m celery -A app.worker.celery_config worker -Q sentiment --pool=solo --concurrency=1 --loglevel=info
```

```powershell
.\.venv\Scripts\python.exe -m celery -A app.worker.celery_config beat --loglevel=info
```

Nếu chạy Docker Compose ở thư mục gốc:

```powershell
docker compose -f Backend/docker-compose.yml -f docker-compose.ai.yml up --build -d
```

Overlay thêm worker sklearn riêng trên network `backend` và mount `Backend/artifacts` chỉ đọc. Các đường dẫn tương đối được tính từ file Compose đầu tiên trong `Backend`. `DATABASE_URL` của worker được đặt cùng giá trị với FastAPI và worker nghiệp vụ, trỏ tới `postgres:5432`; khi thay cấu hình DB, cập nhật đồng bộ các dịch vụ này. Với PhoBERT, xây image worker riêng từ môi trường huấn luyện có Java/VnCoreNLP và transformers; image sklearn mặc định chưa chứa các dependency này.

Frontend chạy trong thư mục `Frontend`:

```powershell
npm ci
npm run dev
```

Mặc định `SENTIMENT_BACKEND=disabled`, đánh giá đã duyệt sẽ ở trạng thái chờ xử lý, không bị gán nhãn giả. `REVIEW_AUTO_APPROVE=False`: duyệt ở `/review-moderation`. Nếu cần thử nghiệm dữ liệu giả trong DB demo riêng, có thể bật auto approve; không cần đổi mặc định của ứng dụng.

Khi có model: đặt artifact ở `Backend/artifacts/sentiment`, cấu hình `SENTIMENT_BACKEND=sklearn` hoặc `transformers`, khởi động lại worker. Beat quét pending/failed mỗi 5 phút, tối đa 5 lần suy luận thất bại. Để chạy lại một kết quả đã lỗi nhiều lần hoặc đổi model, STAFF/ADMIN gọi `POST /reviews/{id}/retry`; kết quả cũ bị loại ngay cho tới khi phân tích mới thành công. Artifact joblib phải do nhóm quản lý, không nhận file mô hình từ người dùng ứng dụng.

## 4. Dữ liệu và huấn luyện

Xem [hướng dẫn gán nhãn](AI_GAN_NHAN.md). Các file trong `Backend/ml/data/drafts` không được đưa thẳng vào ứng dụng hoặc dùng làm tập kiểm thử chuẩn. Script `ml.prepare_samples` có thể tạo lại bản nháp; chỉ chạy vào thư mục mới để không ghi đè phần đã sửa.

Sau khi duyệt và bổ sung đủ mẫu:

```powershell
.\.venv\Scripts\python.exe -m ml.data ml/data/reviewed/sentiment.jsonl ml/data/reviewed/sentiment-splits
.\.venv\Scripts\python.exe -m pip install -r requirements-ai-inference.txt
.\.venv\Scripts\python.exe -m ml.train_sentiment --data ml/data/reviewed/sentiment-splits --output artifacts/sentiment-lr-v1
```

Script chuẩn hóa NFC/khoảng trắng giống runtime, gộp nhóm cùng nguồn/biến thể và gần trùng trước khi chia 70/15/15 theo nhóm. Chia nhóm có thể lệch tỷ lệ theo số mẫu. Script từ chối nếu một tập cảm xúc thiếu lớp; cần thu thập thêm hoặc rà soát cách nhóm, không kéo bản gần trùng sang tập khác. TF-IDF ký tự 2–5 gram + Logistic Regression chọn C bằng Macro-F1 trên validation.

Huấn luyện PhoBERT và LoRA trong một môi trường riêng có `ml/requirements.txt`. Cài Java và tải bộ VnCoreNLP từ nguồn chính thức, ghi lại phiên bản; truyền đường dẫn đã tải. Thay `MODEL_COMMIT_SHA` bằng commit thực tế của mô hình đã kiểm tra giấy phép, không sử dụng tên nhánh thay cho phiên bản khi báo cáo.

```powershell
python -m ml.train_sentiment --backend transformers --data ml/data/reviewed/sentiment-splits --output artifacts/phobert-v1 --model vinai/phobert-base --revision MODEL_COMMIT_SHA --segmenter-path C:/models/vncorenlp
python -m ml.data ml/data/reviewed/chat.jsonl ml/data/reviewed/chat-splits
python -m ml.train_chat --data ml/data/reviewed/chat-splits --output artifacts/chat-lora-v1 --model Qwen/Qwen2.5-0.5B-Instruct --revision MODEL_COMMIT_SHA
```

Mỗi run tạo metadata, checksum dữ liệu, seed, cấu hình, môi trường `pip freeze`, validation và artifact. Đường dẫn segmenter trong metadata phải có thực tại máy suy luận. LoRA mask token đầu vào, chỉ học phần trả lời; không đưa lịch chiếu/giá cố định vào trọng số. Các câu hỏi động trong bản nháp cần bổ sung snapshot API và câu trả lời đúng trước khi duyệt.

PhoBERT yêu cầu tách từ tiếng Việt nhất quán giữa train/runtime: xem [hướng dẫn của VinAI](https://huggingface.co/vinai/phobert-base-v2). Mã LoRA dựa trên [PEFT](https://huggingface.co/docs/peft/main/package_reference/lora). Qwen 0.5B là ứng viên nhỏ cho thử nghiệm, không cam kết chất lượng tiếng Việt; đối chiếu [model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) và [giấy phép của bản cụ thể](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/blob/main/LICENSE) trước khi tải/phân phối.

## 5. RAG và phục vụ mô hình

Sao chép `ml/data/drafts/knowledge.json` sang vùng dữ liệu được quản lý. Rà từng phát biểu với hệ thống, bổ sung `reviewer`, đổi `approved` thành `true` cho tài liệu hợp lệ. Không tự bổ sung chính sách hoàn tiền, đổi/hủy hoặc ưu đãi chưa được công bố. Sau đó:

```powershell
python -m ml.import_knowledge ml/data/reviewed/knowledge.json
```

Giữ `source_id` khi sửa tài liệu, tăng `version`, sửa `effective_at`. Import thay toàn bộ chunks trong một transaction cho từng tài liệu. Thu hồi bằng `approved=false` rồi import lại. Nguồn có ngày hiệu lực trong tương lai không được dùng. Không nhập đánh giá người dùng, giá ghế hoặc ghế trống vào kho chính sách.

Mô hình hội thoại chạy ở tiến trình khác:

```powershell
python -m ml.serve_chat --model Qwen/Qwen2.5-0.5B-Instruct --revision MODEL_COMMIT_SHA --adapter artifacts/chat-lora-v1 --port 8010
```

Đặt `AI_MODEL_URL=http://127.0.0.1:8010` nếu FastAPI và inference cùng máy. Khi FastAPI ở Docker còn model ở host Windows, dùng `http://host.docker.internal:8010` và cấu hình mạng riêng phù hợp; mặc định model server chỉ bind loopback, không tự mở ra mạng. Có thể bỏ adapter để chạy đối chứng. Không cấu hình URL thì dùng RAG cơ sở. Khi model chậm/lỗi/ra mã nguồn không hợp lệ, trả tài liệu truy xuất trực tiếp và báo trạng thái `model_unavailable`. Nếu model chọn danh sách rỗng hợp lệ, trả thiếu căn cứ.

Backend chỉ chấp nhận mã chứng cứ thuộc lần truy xuất hiện tại. Nội dung sinh tự do, link hoặc lệnh từ model không được thực thi. Câu trả lời động được dựng từ kết quả công cụ hiện tại. Nguồn đúng mã vẫn chưa chứng minh liên quan về nghĩa: phải chấm hỗ trợ nội dung theo rubric ở tài liệu đánh giá.

## 6. Hợp đồng API

| Endpoint | Quyền / dữ liệu chính |
| --- | --- |
| `POST /films/{id}/reviews` | Đăng nhập; `{content}`, 201; trùng tài khoản/phim trả 409 |
| `GET /films/{id}/reviews` | Công khai; chỉ đã duyệt; `skip`, `limit` |
| `GET /films/{id}/reviews/mine` | Đăng nhập; gồm trạng thái chờ duyệt/từ chối |
| `PATCH /reviews/{id}` | Chủ sở hữu; `{content, content_version}`; phiên bản cũ trả 409 |
| `DELETE /reviews/{id}` | Chủ sở hữu; 204 |
| `GET /reviews/moderation/pending` | STAFF/ADMIN; phân trang |
| `PATCH /reviews/{id}/moderation` | STAFF/ADMIN; `{status, content_version}`; status pending/approved/rejected |
| `POST /reviews/{id}/retry` | STAFF/ADMIN; phân tích lại bản đã duyệt |
| `GET /films/{id}/sentiment-summary` | `window_days` 1–365; số ba nhãn, pending, needs_review, total, score, eligible, as_of |
| `GET /films/positive-trending` | `theater_id`, `show_date`, `window_days`, `limit`; chỉ đủ dữ liệu/còn suất ACTIVE ở tương lai |
| `POST /ai/chat` | Đăng nhập; ví dụ bên dưới |

```json
{
  "message": "Phim nào được khen và có suất tối nay?",
  "conversation_id": null,
  "context": {"theater_id": 1}
}
```

Chat trả `answer`, `sources`, `links`, `status`, `mode`, `missing_fields`, `context`, `conversation_id`, `as_of`, `tool`. Gửi lại ID và context cho lượt tiếp. Bộ lọc cho phép chọn rõ phim/rạp/ngày/mã suất; ID phải tồn tại và khớp nhau. Ngày hiểu theo Asia/Ho_Chi_Minh, “tối nay” lọc từ 18:00. Hết hạn hoặc sai tài khoản trả 404; frontend có nút hội thoại mới. Giới hạn mặc định 10 câu/phút/tài khoản; Redis không khả dụng thì chỉ trợ lý trả 503.

Context Redis giữ tối đa 30 phút mặc định, chỉ gồm ID phim/rạp/ngày/suất và công cụ đang hỏi lại, không lưu câu hỏi/câu trả lời. Kết quả Celery AI không lưu result backend. Log đánh giá offline chỉ lưu mã mẫu, mã chứng cứ, nhãn, lỗi và độ trễ. Không đưa token, đơn hàng cá nhân hoặc thông tin thanh toán vào tập huấn luyện.

## 7. Kiểm tra và demo

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

Frontend: `npm run build`, `node --test tests/authStorage.test.mjs`; lint các component mới. [Báo cáo trạng thái và đánh giá](AI_DANH_GIA.md) ghi rõ kiểm tra đã chạy và chưa chạy.

Khi DB/Redis đã sẵn sàng, model và tài liệu đã được rà soát:

1. Đăng nhập khách hàng, vào phim và viết đánh giá; xác nhận đang chờ duyệt.
2. Đăng nhập nhân viên, duyệt; worker sentiment cập nhật sau suy luận.
3. Sửa đánh giá; tổng hợp loại bản trước ngay, cần duyệt lại. Chạy retry và xác nhận không tăng số lượng.
4. Xem danh sách tích cực: phim dưới ngưỡng không xuất hiện, trang phim ghi “Chưa đủ đánh giá”. Không tạo dữ liệu giả trong DB thật để vượt ngưỡng.
5. Hỏi “Cách đặt vé?” và mở nguồn. Hỏi chính sách chưa có để kiểm tra thiếu căn cứ.
6. Hỏi “Phim nào được khen và có suất tối nay?”, chọn rạp nếu được hỏi; tiếp tục hỏi lịch chiếu và chọn link `/seat-selection/{id}`.
7. Thử model/Redis ngừng hoạt động; kiểm tra thông báo và tiếp tục luồng đặt vé thông thường. Trợ lý không tự giữ ghế hay xác nhận thanh toán.
