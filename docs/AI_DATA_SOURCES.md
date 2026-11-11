# Nguồn dữ liệu cảm xúc có thể tải trực tiếp

Kiểm tra ngày 04/11/2026. Nhóm ưu tiên nguồn tải trực tiếp, không chờ xin VLSP2016. Các lựa chọn dưới đây phân biệt văn bản nhận xét thật, phương pháp gán nhãn, ngôn ngữ và số lớp. Bản sao/biến thể của cùng nguồn chỉ tính là một dataset.

## Những nguồn đã kiểm tra

**Phương án bốn bộ cho đợt nộp hiện tại:** [AI_FOUR_DATASET_COMPARISON.md](AI_FOUR_DATASET_COMPARISON.md). Đã bổ sung nguồn tác giả UIT-ViSFD, chỉ dùng aspect GENERAL có nhãn người theo tác giả. Bộ phim train bằng AI silver và Shopee hai lớp được mô tả riêng; không ghi thành bốn dataset human gold ba lớp. UIT-VSFC/VLSP chưa được tự đổi điều kiện sử dụng để đủ số bộ.

| Bộ dữ liệu và link | Dữ liệu và nhãn | Khả năng dùng trong dự án |
| --- | --- | --- |
| [UTS2017 Bank của underthesea](https://huggingface.co/datasets/undertheseanlp/UTS2017_Bank) | Tiếng Việt, ngân hàng, negative/neutral/positive; nhãn do bên phát hành cung cấp, card Apache 2.0 | Đã tải, làm sạch/chia tập, EDA và thực nghiệm. Dùng được cho so sánh đa miền, chưa chứng minh chất lượng trên phim |
| [UIT-ViSFD tác giả](https://github.com/LuongPhan/UIT-ViSFD) | 11.122 bình luận smartphone được người gán theo tác giả; mười aspect và ba polarity. README cho dùng nghiên cứu, thương mại liên hệ riêng; không tự ghi SPDX | Đã pin revision `4b11ec2e4e97839600e6035b49d1645c79023354`, tải ZIP gốc; chỉ giữ GENERAL, loại thiếu aspect và gần trùng giữa split. Sau xử lý: train 4.852 / validation 688 / test 1.381; không suy nhãn từ rating |
| [Shopee Vietnamese Product Reviews Sentiment trên Kaggle](https://www.kaggle.com/datasets/dduongdev/shopee-vietnamese-product-reviews-sentiment) | Card mô tả review Shopee thật, nhãn theo nội dung. File gốc tải được có 9.599 dòng: 5.965 negative, 3.634 positive. Card Apache 2.0 | Đã tải version 1, giữ ZIP/checksum. Chỉ hai lớp; dùng cho thực nghiệm phụ hai lớp hoặc làm nguồn chờ rà soát, chưa nhập vào ma trận ba lớp |
| [IMDb 50K trên Kaggle](https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews) và [nguồn tác giả Stanford](https://ai.stanford.edu/~amaas/data/sentiment/) | Đã tải version 1 và kiểm CSV: 50.000 review tiếng Anh, 25.000 positive/25.000 negative. Bộ gốc dùng mức rating chọn review phân cực, không có neutral | Giữ ZIP/metadata/checksum/profile trên máy. Dùng cho thực nghiệm phim tiếng Anh riêng; không tính bản dịch là dataset tiếng Việt tự nhiên độc lập hoặc tự thêm neutral. License Kaggle là Other theo mô tả, cần dẫn điều kiện nguồn Stanford |
| [UIT VSFC do nhóm UIT phát hành](https://huggingface.co/datasets/uitnlp/vietnamese_students_feedback) và [repo tác giả](https://github.com/kietnv/uit-vsfc) | Phản hồi sinh viên tiếng Việt, ba lớp sentiment; có train/validation/test. HF không chặn đăng nhập; license hiện ghi unknown | Phù hợp về nhãn. Cần có căn cứ điều kiện sử dụng khi chốt bộ thực nghiệm; không tự ghi Apache/MIT cho dữ liệu này |
| [Vietnamese Sentiment Analysis trên Kaggle](https://www.kaggle.com/datasets/phuocthanhngo/vietnamese-sentiment-analysis) | File CSV đã tải có 192.986 dòng, cột comments/flag; flag 0: 60.716, 1: 70.424, 2: 61.846. Card Apache 2.0 | Card chưa giải thích rõ mapping flag, nguồn từng mẫu và người/cách gán nhãn. Giữ làm ứng viên; không đoán 0/1/2 tương ứng nhãn nào, chưa đưa vào benchmark |

Shopee có thêm 1.348 biến thể không dấu trong `aug_unaccented_reviews.jsonl`. Đây là augmentation, không phải bộ dữ liệu độc lập; không trộn ngẫu nhiên với bản gốc rồi chia train/test. Card mô tả cách gán theo nội dung, nhưng kiểm tra ZIP chưa xác minh chất lượng gán nhãn hoặc người gán cho từng dòng. Không nhận đó là nhãn nhóm tự gán.

## Những nguồn chưa chọn thay thế trực tiếp

- [NEU ESC của tác giả](https://huggingface.co/datasets/hung20gg/NEU-ESC): card Apache 2.0, có neutral/positive/negative/toxic nhưng đang yêu cầu đăng nhập và chấp nhận điều kiện chia sẻ thông tin. Chưa tải file. Nếu dùng ba lớp phải mô tả rõ việc loại toxic; không tự gộp toxic thành negative.
- [ViMovieABSA của tác giả](https://github.com/AlyThien/ViMovieABSA-A-Vietnamese-Aspect-Based-Sentiment-Dataset-for-Movie-Reviews-with-Reliability-Decompos): **đã tải CSV 10.797 dòng** tại revision `2ceae3b15ece8f9a6c24f7b73465d940b0f8ce18`, card CC BY 4.0. Đây là văn bản phim do tác giả mô tả đã thu thập thật; nhãn có phần bằng LLM và chỉ một phần được người kiểm tra. CSV không có cột nhận diện các dòng gold đó, nên chưa dùng nguyên nhãn làm benchmark con người.
- [VSA Food Reviews trên Kaggle](https://www.kaggle.com/datasets/guutran/vietnamese-sentiment-analysis-food-reviews): card mô tả gộp hai nguồn review đồ ăn với nhãn nhị phân; license metadata hiện unknown. Chưa chọn cho benchmark chính.
- [Synthetic Vietnamese Students Feedback](https://www.kaggle.com/datasets/toreleon/synthetic-vietnamese-students-feedback-corpus): tên/card ghi synthetic, không dùng làm dữ liệu thật.

Việc tải được một ZIP không chứng minh nguồn/nhãn phù hợp. Cần đọc card, kiểm tra file và giữ lại phiên bản/checksum; không sử dụng bản sao VLSP không rõ quyền để tránh quy trình của tác giả.

## Cách lấy nhanh cho nhóm

Trên Kaggle mở link dataset, đăng nhập nếu trang yêu cầu, chọn Download. Giữ ZIP gốc và file mô tả; chỉ gửi đường dẫn local cho pipeline, không đưa dữ liệu lên GitHub. Không cần nhóm viết scraper. Hai nguồn đã tải được đặt tại:

- `.local/datasets/kaggle-shopee-v1/`: ZIP, publisher metadata và manifest số dòng/nhãn/SHA.
- `.local/datasets/kaggle-imdb-v1/`: ZIP IMDb 50K, publisher metadata, manifest SHA và `csv-profile.json` kiểm đủ 50.000 dòng.
- `.local/evidence/advisor-v3/dataset-discovery/kaggle-vietnamese-sentiment.zip`: ứng viên comments/flag chưa đủ thông tin nhãn.
- `.local/annotations/cinema-public-v1/`: CSV ViMovieABSA gốc, manifest và `cinema-pending.jsonl` cho nhóm duyệt. Có **7.935 dòng pending**, loại khỏi đầu vào này 2.861 dòng `overall=none` và một dòng lỗi chính tả `negavitve`. Không biến `none` thành neutral. Giữ nhãn nhà phát hành ở `suggested_label`; `label/reviewer` vẫn trống. ID theo dòng nguồn vì phát hiện 1.816 comment ID trùng.

Công cụ tải Kaggle đã có, không tự duyệt dữ liệu:

```powershell
.local/ai-venv/Scripts/python.exe scripts/ai/fetch_public_reviews.py shopee --output .local/datasets/kaggle-shopee-new-version
.local/ai-venv/Scripts/python.exe scripts/ai/fetch_public_reviews.py imdb --output .local/datasets/kaggle-imdb-v1
```

Script đọc version đang công bố rồi tải đúng version, lưu checksum và đọc danh sách thành viên ZIP mà không giải nén đường dẫn tùy ý. Thư mục output phải mới. Chạy importer/audit riêng sau khi thống nhất protocol và nhãn; tải raw không đồng nghĩa admitted.

### Dùng ngay review phim đã tải

```powershell
$env:PYTHONPATH = "$(Get-Location);$(Join-Path (Get-Location) 'pipelines')"
.local/ai-venv/Scripts/python.exe -m ml.annotation_app .local/annotations/cinema-public-v1/cinema-pending.jsonl --output .local/annotations/cinema-public-v1/cinema-confirmed.jsonl --port 8766
```

Mở http://127.0.0.1:8766, nhập mã thành viên thật và xác nhận từng câu. Có thể chia phần cho thành viên bằng CSV theo [runbook](AI_RUNBOOK.md); ít nhất 20% nên được hai người gán độc lập. Không cần duyệt hết 7.935 câu trước khi thử pipeline, nhưng tập được chọn cần đủ nhóm độc lập và đủ ba lớp; công bố số mẫu thực duyệt và quy tắc chọn, không nhận là đã duyệt toàn corpus.

CSV nguồn không có movie ID hoặc cờ gold/human theo từng dòng. Group chuẩn bị hiện theo văn bản chuẩn hóa; chưa được nhận là split độc lập theo phim/tác giả/thời gian. Khi có thông tin bổ sung, curator cần ghi nhóm trước khi chia và kiểm tra họ gần trùng bằng pipeline.

## Điều chỉnh ma trận nghiên cứu

VLSP2016 được chuyển thành nguồn tùy chọn nếu sau này nhóm muốn dùng. Mục tiêu 5 transformer × 4 dataset độc lập vẫn giữ; hiện chỉ UTS2017 Bank đã đủ điều kiện chạy trong protocol ba lớp. Các nguồn binary có thể thành nghiên cứu phụ nếu chốt một protocol hai lớp riêng, cùng dữ liệu/split cho các model và chỉ số đúng nhãn. Không thêm neutral giả hoặc đưa điểm binary vào bảng xếp hạng ba lớp.

Nếu dùng review phim công khai chưa có nhãn gold, nhóm có thể gán bằng công cụ trong [runbook](AI_RUNBOOK.md). Dữ liệu phim do nhóm tự thu thập là một lựa chọn bổ sung, không phải bắt buộc phải tự viết review mới khi đã tìm được corpus phù hợp.
