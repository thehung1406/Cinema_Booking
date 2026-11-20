# Hai mô hình cảm xúc phim dùng chung

Gói này chứa đúng hai artifact đã huấn luyện để chạy demo phân tích cảm xúc, không cần huấn luyện lại:

| Thư mục | Phiên bản | Thành phần |
| --- | --- | --- |
| `lr` | `lr-film-silver:s42:70c1e91b846e` | TF-IDF + Logistic Regression, `model.joblib`, metadata |
| `visobert` | `visobert-film-silver:s42:70c1e91b846e` | ViSoBERT đã fine-tune, `model.safetensors`, config, tokenizer và metadata |

Tổng dung lượng suy luận khoảng 395 MB. Ba tệp nhị phân và `tokenizer.json` được lưu bằng [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage), các tệp còn lại nằm trong Git thường. SHA-256 và kích thước chính xác của cả chín tệp ở `manifest.json`. Nội dung metadata được giữ nguyên từ lượt huấn luyện, chỉ chuẩn hóa xuống dòng của JSON sang LF; đường dẫn checkpoint tương đối bên trong chỉ ghi lại lịch sử, không cần tồn tại trên máy mới.

## Tải trên máy khác

Cài Git LFS nếu chưa có (Git for Windows thường có sẵn), sau đó từ thư mục dự án đã pull nhánh PR hoặc `main` sau merge:

```text
git lfs install
git lfs pull
python scripts/ai/check_sentiment_models.py
```

Lệnh kiểm tra chỉ cần Python 3.11/3.12; không tải model từ nơi khác và không nạp Joblib. Nếu báo tệp chỉ là Git LFS pointer, cần chạy `git lfs pull` thành công trước. Tải ZIP mã nguồn hoặc chỉ pull với chế độ bỏ qua LFS có thể chưa nhận được trọng số thật.

## Chạy trong ứng dụng

Khởi tạo các dịch vụ/tài khoản trên máy mới theo [hướng dẫn máy mới](../../../docs/AI_PORTABLE_SETUP.md). Profile `compose.ai-sentiment-demo.yml` mặc định gắn hai thư mục trong gói này ở chế độ chỉ đọc; không cần trỏ về `.local` của máy tác giả. Nếu đã đặt `REVIEW_DEMO_LR_ARTIFACT` hoặc `REVIEW_DEMO_VISOBERT_ARTIFACT`, các giá trị riêng đó vẫn được ưu tiên.

Với runtime đầy đủ đã khởi tạo có project name `backend`, từ root chạy:

```powershell
python scripts/ai/check_sentiment_models.py
if ($LASTEXITCODE -ne 0) { throw 'Download and verify the shared models first' }
$sentimentCompose = @('--env-file', '.env.microservices', '-p', 'backend', '-f', 'compose.yml', '-f', 'compose.ai-sentiment-demo.yml')
docker compose @sentimentCompose up -d --no-deps --build --wait review-service review-worker
```

Giữ project name và các tệp Compose theo runtime đang dùng; ví dụ này không tự khởi tạo database hay bật các dịch vụ nền còn thiếu. Với profile chatbot `cinema-ai-demo`, giữ `-p cinema-ai-demo` và thêm `-f compose.ai-local.yml` trước tệp sentiment. Hai artifact được mount ở runtime, không đóng vào image Docker. Đăng nhập tài khoản có quyền duyệt review, mở **Duyệt đánh giá → Nhãn cảm xúc → So sánh hai mô hình**.

Profile này giữ nguyên hành vi demo hiện có, gồm cấu hình tự duyệt review của profile. Việc bổ sung artifact không công bố hai mô hình làm model production. Các giới hạn và hướng dẫn vận hành vẫn ở [hướng dẫn demo](../../../docs/AI_GRAPH_DEMO.md#demo-so-sánh-hai-mô-hình-cảm-xúc).

## Thử riêng bằng Python, không cần Docker

Nếu đã có môi trường nghiên cứu chứa Review Service và thư viện suy luận:

```text
python scripts/ai/check_sentiment_models.py --smoke
```

Lệnh kiểm SHA-256 rồi nạp hai mô hình bằng đúng loader của Review Service, chạy CPU trên ba câu tự tạo. Không kết nối Hugging Face để tải model/tokenizer; không truy cập database hay bình luận thật. Đây là kiểm tra mô hình có chạy và trả đủ ba xác suất hợp lệ, không phải phép đo độ chính xác.

Môi trường độc lập nhẹ hơn bộ nghiên cứu đầy đủ có thể tạo như sau, từ root:

```text
python -m venv .venv-sentiment
```

Kích hoạt venv (`.venv-sentiment\Scripts\Activate.ps1` trên PowerShell, `source .venv-sentiment/bin/activate` trên Linux/macOS), rồi:

```text
python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install scikit-learn==1.9.0 joblib==1.5.3 transformers==4.57.1
python scripts/ai/check_sentiment_models.py --smoke
```

Không cần cài các owner/database để dùng lệnh smoke này. Chỉ nạp Joblib từ artifact tin cậy; xác minh checksum trước khi nạp. Môi trường demo Docker đã pin phiên bản sklearn/Joblib/Transformers phù hợp với artifact.

## Nguồn và giới hạn

Hai mô hình dùng seed 42, 426 nhãn AI silver để train và 36 nhãn người phát triển để chọn cấu hình. Đây là artifact thử nghiệm, chưa được duyệt cho production; giữ nguyên `production_promoted=false`. Không có dữ liệu bình luận, danh tính người gán nhãn, tài khoản hoặc credential trong gói chia sẻ. Metadata chỉ chứa cấu hình, số lượng và checksum dữ liệu huấn luyện.

ViSoBERT dựa trên `uitnlp/visobert`, revision `196a62afad9cbe4f52a54aabad828b13f0eec59a`, của Nam Nguyen, Thang Phan, Duc-Vu Nguyen và Kiet Nguyen. Gói dự án đã fine-tune cho ba nhãn cảm xúc phim. Xem [thông tin nguồn và điều kiện nghiên cứu](NOTICE.md) và [báo cáo pilot](../../../docs/reports/AI_FILM_HUMAN_PILOT_2026-11-04.md).

Qwen3:4B là mô hình chatbot riêng, tiếp tục tải theo `pipelines/configs/chat_runtime.lock.json` bằng profile Ollama. Gói này chỉ chia sẻ hai mô hình cảm xúc đã huấn luyện của dự án, không chứa cache Qwen hay toàn bộ các checkpoint thử nghiệm.
