# Gán nhãn AI và mẫu người kiểm tra

Đây là phương án pilot bổ sung nhằm giảm đọc tay, không tự thay thế bộ D1 được duyệt trong plan học thuật. Không commit/push trong bước này. Các bình luận thật và kết quả gán nhãn vẫn ở thư mục `.local/annotations`, bị Git bỏ qua; code và hướng dẫn có thể đi theo repository.

## Phần người dùng cần làm

**Đã hoàn tất 100/100 câu ngày 04/11/2026**, bởi một người thật: 50 negative, 27 neutral, 23 positive. Không cần nhập lại. Đã đóng băng bản chụp/SHA, đối chiếu Qwen cùng protocol cũ và sáu model Bank; chạy thêm LR/ViSoBERT bằng silver trên một protocol riêng. Xem [báo cáo và giới hạn pilot](reports/AI_FILM_HUMAN_PILOT_2026-11-04.md). Qwen khớp 55/100 (Macro-F1 0,5843, 10 từ chối); ViSoBERT silver 56/100 (0,5636). Chưa đủ cơ sở tự nhận nhãn AI là gold hay bật model production.

Trang local http://127.0.0.1:8770 vẫn giữ dữ liệu đã nhập và không hiển thị gợi ý AI. Không cần tiếp tục đọc toàn bộ danh sách 600 để hoàn tất pilot này. Nếu người thật chủ động sửa quyết định, giữ snapshot cũ và xuất một phiên bản đánh giá mới, không ghi đè bằng chứng.

36 quyết định đã có từ pass B được giữ nguyên tại nguồn và sao lưu riêng trong bản chia mới. Các câu này và hai câu gần trùng thuộc cùng họ được để riêng cho phát triển, không trộn vào AI training hoặc tập pilot mới.

100 câu là bước đánh giá ban đầu, không mặc nhiên đủ quy mô báo cáo cuối. Sau pilot cần xem số lượng từng lớp thực, các câu không thuộc phim, mức bất đồng và độ bất định của kết quả trước khi chốt tập validation/test chính thức. Tập test chính thức cần khóa trước khi huấn luyện/chọn cấu hình; không dùng nó để sửa prompt/model rồi tiếp tục gọi là kiểm tra cuối độc lập.

## Đã chia dữ liệu thế nào

Nguồn là cùng 600 câu đã chuẩn bị, vốn được lấy cân bằng theo nhãn gợi ý nhà phát hành. Đây không phải mẫu ngẫu nhiên từ mọi bình luận phim trong thực tế. Công cụ không xem nhãn người để lựa chọn lớp.

| Nhóm | Số câu | Cách dùng |
| --- | ---: | --- |
| Công việc con người đã có và họ gần trùng | 38, gồm 36 câu đã xác nhận | Giữ cho phát triển, bảo toàn công sức; không nhận là test ngẫu nhiên |
| Pilot mù | 100 | Người đọc độc lập; không gửi các câu này vào lượt gán nhãn AI cho train |
| Ứng viên nhãn AI | 462 | Qwen local đọc và gán nhãn tự động, chưa phải human gold |

`partition-manifest.json` đã ghi danh sách ID, seed, SHA và quy tắc chia trước khi gọi model. Các họ văn bản trùng/gần trùng ở ngưỡng 0,88 được giữ cùng nhóm. Thiếu ID phim/tác giả nên không tuyên bố đã chia độc lập theo phim.

AI chọn một trong positive, neutral, negative, needs_context hoặc not_film_review. Hai nhóm sau không được ép thành neutral và không có nhãn sentiment. Confidence low/medium/high chỉ là tự ước lượng của model, không phải xác suất đúng đã đo. Output lỗi được giữ trace và xử lý riêng; không tự điền nhãn để làm đẹp số lượng.

Mọi nhãn AI có `reviewer=null`, trạng thái chưa được người duyệt và nguồn model/digest. Pipeline benchmark chính tiếp tục từ chối chúng như dữ liệu human gold. Nếu sau này huấn luyện bằng chúng, phải dùng protocol silver/weak supervision riêng, validation/test người thật và báo cáo rõ thay đổi phương án dữ liệu. Không tính lượt pilot này là đã hoàn thành D1 hoặc 54 ô còn thiếu.

## Chạy bằng Python

Kích hoạt môi trường nghiên cứu theo [hướng dẫn máy mới](AI_PORTABLE_SETUP.md), đặt PYTHONPATH gồm root và pipelines. Từ root:

```text
python -m ml.assist_dataset .local/annotations/cinema-double-blind-v1/pass-A-pending.jsonl --human-work .local/annotations/cinema-double-blind-v1/pass-B-confirmed.jsonl --output .local/annotations/cinema-ai-assisted-v1 --holdout 100
python -m ml.auto_annotate .local/annotations/cinema-ai-assisted-v1/train-ai-pending.jsonl --output .local/annotations/cinema-ai-assisted-v1/ai-run-v2 --batch-size 6
python -m ml.annotation_app .local/annotations/cinema-ai-assisted-v1/gold-pilot-pending.jsonl --output .local/annotations/cinema-ai-assisted-v1/gold-pilot-human.jsonl --port 8770
```

Chỉ chạy lệnh chia đầu tiên khi thư mục đầu ra chưa tồn tại. Lệnh AI có checkpoint theo batch và tiếp tục khi chạy lại cùng input, code, model/digest. Đổi code/model thì dùng thư mục output phiên bản mới. File người duyệt không bị ghi đè bởi AI.

## Chạy bằng Docker sau khi pull

Không cần venv, Torch/CUDA hoặc Ollama cài trên host cho các lệnh dưới. Dùng cấu hình riêng và model đã khởi tạo bằng `local_stack.py` như [hướng dẫn portable](AI_PORTABLE_SETUP.md). Chuẩn bị corpus/danh sách 600 theo cùng hướng dẫn, hoặc dùng các lệnh tạo dữ liệu trong image annotation nếu chưa có. Trên PowerShell/Linux/macOS đều có thể dùng lệnh một dòng:

```text
docker compose -p cinema-ai-demo --env-file .env.microservices -f compose.yml -f compose.ai-local.yml -f compose.ai-tools.yml build annotation-job
docker compose -p cinema-ai-demo --env-file .env.microservices -f compose.yml -f compose.ai-local.yml -f compose.ai-tools.yml run --rm annotation-job python /app/prepare_public_movie_reviews.py --output /work/cinema-public-v1
docker compose -p cinema-ai-demo --env-file .env.microservices -f compose.yml -f compose.ai-local.yml -f compose.ai-tools.yml run --rm annotation-job python -m ml.blind_annotation prepare --input /work/cinema-public-v1/cinema-pending.jsonl --output /work/cinema-double-blind-v1
docker compose -p cinema-ai-demo --env-file .env.microservices -f compose.yml -f compose.ai-local.yml -f compose.ai-tools.yml run --rm annotation-job python -m ml.assist_dataset /work/cinema-double-blind-v1/pass-A-pending.jsonl --output /work/cinema-ai-assisted-v1 --holdout 100
docker compose -p cinema-ai-demo --env-file .env.microservices -f compose.yml -f compose.ai-local.yml -f compose.ai-tools.yml run --rm annotation-job python -m ml.auto_annotate /work/cinema-ai-assisted-v1/train-ai-pending.jsonl --output /work/cinema-ai-assisted-v1/ai-run-v2 --origin http://ollama:11434 --batch-size 6
docker compose -p cinema-ai-demo --env-file .env.microservices -f compose.yml -f compose.ai-local.yml -f compose.ai-tools.yml up -d annotation-gold
```

Giữ project name của môi trường đang dùng nếu khác `cinema-ai-demo`. Không mở thêm container annotation-gold nếu đã chạy công cụ Python trên cùng cổng 8770. Profile chỉ publish UI trên loopback; các job không nhận credential DB owner. Các container AI tư vấn/đặt vé không phải chạy logic gán nhãn trong request.

Hai lệnh tải/chuẩn bị corpus chỉ dùng khi chưa có thư mục tương ứng. Nếu đã có file người làm, thêm `--human-work /work/.../pass-B-confirmed.jsonl` vào lệnh chia. Đường dẫn sai sẽ bị từ chối thay vì bỏ qua công việc con người. Máy mới chưa có 36 quyết định của tác giả sẽ có số ứng viên AI khác; lấy số thực trong manifest, không tự sao chép số 462 vào báo cáo của lần chạy khác.

## Đầu ra trên máy

Thư mục `.local/annotations/cinema-ai-assisted-v1` chứa bản chia, file pilot, bản sao 36 quyết định thật và các lượt AI. `ai-run-v2/ai-labels.jsonl` có nhãn máy; `summary.json` đếm các loại quyết định, không đo accuracy. `batches` giữ request/output thật; các file `failed-*` giữ cả lượt lỗi. Chỉ sau khi có người chấm độc lập mới được tính chất lượng nhãn hoặc mô hình.

Lượt thực chạy đã xong 462 câu: **426 nhãn sentiment** gồm 140 negative, 161 neutral, 125 positive; **25 needs_context** và **11 not_film_review** không có nhãn sentiment. Không có người duyệt do AI tạo. Tập 100 câu không xuất hiện trong các request AI của lượt này. [Bản đếm và checksum](reports/evidence/2026-11-04-ai-labeling/summary.json) không chứa bình luận hoặc danh tính người gán nhãn.

Đã kiểm tra toàn bộ regression liên quan: 233 bài pass, 6 cảnh báo Pydantic sẵn có; Docker image annotation build và CLI hoạt động. Đã sửa việc chuẩn bị broker test chờ ứng dụng RabbitMQ thật sẵn sàng thay vì chỉ chờ tiến trình Erlang. Các kiểm tra này xác nhận code/luồng dữ liệu, không thay thế đánh giá độ đúng của 426 nhãn AI.
