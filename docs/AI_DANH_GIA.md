# Trạng thái kiểm tra và kế hoạch thực nghiệm AI

## Kiểm tra triển khai ngày 17/09/2026

- Backend: 122 kiểm thử đạt trong môi trường `.venv` Python 3.12 với dependency của repo; gồm 19 kiểm thử mới cho đánh giá/AI/chia dữ liệu. Các cảnh báo Pydantic ở schema booking là cảnh báo hiện có.
- Frontend: production build thành công; 3 kiểm thử authStorage đạt; lint bốn component AI mới đạt.
- Import FastAPI và sinh OpenAPI thành công; migration từ 001 đến 005 sinh được PostgreSQL SQL offline; compile Python thành công.
- Trình duyệt: kiểm tra mở/đóng khung trợ lý và trạng thái chưa đăng nhập khi backend không hoạt động. Chưa xác nhận luồng browser end-to-end với DB thật.
- Docker daemon chưa hoạt động tại thời điểm kiểm tra. Chưa chạy migration lên PostgreSQL, worker thật hoặc kiểm thử khóa hàng đồng thời trên PostgreSQL.
- `nvidia-smi` không đọc được GPU do quyền truy cập. Chưa xác định VRAM, chưa tải/chạy PhoBERT hoặc Qwen, chưa đo độ trễ mô hình, chưa huấn luyện/đánh giá trọng số.
- Máy kiểm tra: Windows 11 Home Single Language, AMD Ryzen AI 9 HX 370, 12 nhân/24 luồng, bộ nhớ hệ điều hành nhìn thấy khoảng 31,1 GiB. Đây chưa phải cấu hình đã đo hiệu năng AI.

Các test mới chạy trên SQLite cô lập, giả lập Redis/auth/model tại các ranh giới bên ngoài; kiểm tra được logic và hợp đồng HTTP, không thay thế thử nghiệm hạ tầng PostgreSQL/Redis/Celery.

## Những trường hợp đã kiểm thử bằng mã

Tạo trùng đánh giá, sửa/xóa trái quyền, optimistic version conflict, duyệt sai phiên bản, retry idempotent, chỉnh sửa trong lúc suy luận, xóa/tạo lại, pending/low-confidence/lỗi không vào xếp hạng, cửa sổ thời gian, neutral riêng với negative, điều kiện suất tương lai, 2/2 so với 180/200 theo Wilson, RAG chờ duyệt/ngày hiệu lực/đổi phiên bản/thu hồi, nguồn URL không hợp lệ, hỏi thêm rạp, ngữ cảnh cách ly theo tài khoản, đổi chủ đề khi đang hỏi lại, giá từ DB, ID công cụ không hợp lệ/không khớp, rate limit, Redis/API lỗi, chỉ dẫn nhiễu không tạo lệnh hoặc thông tin do model bịa, route cố định trước route film_id, duyệt chỉ dành cho nhân viên, dữ liệu nháp bị chặn và nhóm gần trùng không rò rỉ.

## Thực nghiệm cảm xúc sau khi có dữ liệu được duyệt

```powershell
python -m ml.evaluate_sentiment --data ml/data/reviewed/sentiment-splits --models artifacts/sentiment-lr-v1 artifacts/phobert-v1 --output ml/runs/sentiment-test.json
```

Tạo thư mục `ml/runs` trước khi chạy. Công cụ kiểm tra checksum giống run huấn luyện; tính Macro-F1, precision/recall/F1 từng lớp, confusion matrix theo thứ tự negative/neutral/positive và p50/p95 suy luận ấm. Chỉ lưu mã mẫu và loại lỗi, không ghi lại văn bản khách hàng. Lần đánh giá test không chọn lại threshold. Chọn threshold trên validation bằng cách xem tradeoff tỷ lệ cần rà soát/chất lượng phần được chấp nhận.

Thêm phân tích lỗi theo phủ định, mỉa mai, tiếng lóng, không dấu, hỗn hợp, nhầm phim/rạp. Ghi cấu hình CPU/GPU/RAM, phiên bản OS/framework, hash model, split hash, số mẫu từng lớp và thời gian train. Không khẳng định mô hình tinh chỉnh tốt hơn baseline nếu kết quả không chứng minh.

## Thực nghiệm trợ lý

Chuẩn bị 100–150 câu đã được người duyệt kiểm tra, độc lập với train/validation. Chụp cố định cùng tài liệu truy xuất và snapshot API để so sánh base/LoRA; dữ liệu động phải có thời điểm và điều kiện query. Không dùng tài liệu thay cho snapshot ghế/giá.

```powershell
python -m ml.evaluate_chat --data ml/data/reviewed/chat-splits --model Qwen/Qwen2.5-0.5B-Instruct --revision MODEL_COMMIT_SHA --adapter artifacts/chat-lora-v1 --output ml/runs/chat-test.json
```

Script đo tỷ lệ chọn đúng bộ chứng cứ, đầu ra hợp lệ, p50/p95 trên cùng ngữ cảnh. Đó chưa phải tỷ lệ trả lời đúng đầy đủ của chatbot. Cần chấm thêm qua `/ai/chat` với bảng sau; cột chưa chấm để trống, không mặc định đạt:

| case_id | nhóm | đúng nội dung 0/1 | nguồn hỗ trợ 0/1 | công cụ/tham số đúng 0/1/NA | hỏi lại/từ chối đúng 0/1/NA | latency_ms | snapshot_id | ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chưa thực hiện | | | | | | | | |

Một câu chỉ đạt nguồn hỗ trợ nếu từng phát biểu được chứng cứ trực tiếp xác nhận và phù hợp câu hỏi. Link tồn tại hoặc mã nguồn hợp lệ không đủ. Chấm lỗi model chọn đoạn không liên quan, bỏ sót chứng cứ, hỏi lại dư/thiếu và định tuyến theo từ khóa. Backend render nguyên văn giúp tránh sửa số liệu nhưng vẫn cần kiểm tra độ liên quan của câu trả lời.

## So sánh xếp hạng

Xuất cùng snapshot số tích cực/tổng hợp lệ cho các phim đủ điều kiện; mỗi dòng JSON có `film_id`, `positive`, `total`. Chạy:

```powershell
python -m ml.evaluate_ranking ml/runs/ranking-snapshot.json ml/runs/ranking-report.json --minimum 10
```

So sánh đếm tích cực, tỷ lệ thuần và Wilson trên cùng tập. Chạy bản riêng với minimum 1 để khảo sát phim rất ít đánh giá (2/2, 180/200); không đổi ngưỡng production chỉ để đưa phim demo vào danh sách. Kiểm tra số trung lập, cửa sổ 7/30/60 ngày, phim hết suất và trạng thái CANCELLED.

## Các bước còn lại để nghiệm thu toàn bộ kế hoạch

1. Rà soát và thu thập đủ dữ liệu được phép sử dụng, duyệt chính sách, gán nhãn chéo và tạo test độc lập.
2. Xác định máy huấn luyện/demo, thử mô hình nhỏ và chọn cấu hình sau đo đạc.
3. Huấn luyện baseline, PhoBERT và LoRA; bàn giao artifact, checksum, báo cáo và hướng dẫn môi trường thực tế.
4. Thử retriever ngữ nghĩa/pgvector với cùng tập câu hỏi và đo so với baseline từ vựng trước khi quyết định.
5. Chạy PostgreSQL/Redis/Celery và browser end-to-end, kiểm thử đồng thời/restart worker/broker outage, đo tải và chốt mục tiêu độ trễ.
6. Hoàn tất chấm câu trả lời, nguồn, tool, lỗi phân loại/định tuyến và toàn bộ kịch bản demo trong kế hoạch gốc.
