# So sánh bốn dataset tiếng Việt cho báo cáo tiến độ

Phạm vi mới phục vụ yêu cầu nộp đủ bốn bộ ngay đợt này, sau khi nhóm chọn giữ tất cả bằng tiếng Việt. Config: `pipelines/configs/ai_research.four-vi.v1.json`. Năm Transformer gồm PhoBERT, ViSoBERT, ViDeBERTa, mBERT, XLM-R; LR là baseline thứ sáu. Mỗi model được huấn luyện riêng trên từng dataset, seed 42, ba epoch cho Transformer. Kết quả validation chỉ được ghi hoàn tất khi có đủ 24 artifact; không dùng model Bank suy luận bốn bộ để thay thế các lượt fine-tune.

**Trạng thái: đã hoàn tất 24/24.** [Word Chương 3 và 4](reports/AI_GVHD_4_DATASET_2026-11-04.docx), [bảng kết quả](reports/AI_GVHD_4_DATASET_2026-11-04.md), [summary và nguồn bằng chứng](reports/evidence/2026-11-04-four-vi/summary.json). Mọi điểm số là validation hoặc pilot có ghi rõ; chưa mở final test.

## Bốn nguồn và điều chỉnh phương án

| Dataset | Ngôn ngữ / nhãn | Phần dữ liệu dùng | Nguồn giám sát |
| --- | --- | --- | --- |
| UTS2017 Bank | Tiếng Việt, ba lớp | Train 1.543 / validation 272 / test 494 đã xử lý gần trùng ở mốc trước | Nhãn nhà phát hành |
| UIT-ViSFD GENERAL | Tiếng Việt, ba lớp | Train 4.852 / validation 688 / test 1.381 sau lọc | Chỉ aspect GENERAL do tác giả gán; không suy nhãn từ sao hay các aspect khác |
| Shopee | Tiếng Việt, hai lớp | Train 6.719 / validation 1.440 / test 1.440 | Nhãn nội dung do nhà phát hành cung cấp; chưa xác minh người/cách gán từng dòng |
| ViMovieABSA phim silver | Tiếng Việt, ba lớp | Train 426 / validation 36 / pilot phát triển 100 | Train bằng nhãn AI chưa duyệt; validation/pilot là nhãn người thật đã nhập |

Đây là bốn **nguồn corpus** khác nhau, không phải bốn bản dịch/split/augmentation. Ba nguồn dùng nhãn nhà phát hành và một nguồn là thực nghiệm giám sát yếu. **Không gọi chúng là bốn bộ gold tiếng Việt ba lớp.** Shopee giữ hai lớp gốc; không tự thêm neutral. Bộ phim giữ trạng thái silver, không tự ghi người duyệt cho nhãn AI. Mỗi dataset có bảng riêng, không lấy mean điểm nhị phân và ba lớp để xếp hạng tổng.

Plan gốc vẫn được lưu: năm Transformer × bốn dataset gold ba lớp × ba seed, cùng LR bổ sung. Ma trận đó đã có 18/72 ở mốc Bank. So sánh tiến độ hiện tại đổi nguồn, mức giám sát, số lớp và batch; không cộng 24 lượt mới rồi nhận đã hoàn tất 72 lượt cũ. Việc chọn mức giám sát yếu đáp ứng yêu cầu giảm đọc tay của nhóm, phải được giải thích khi trình bày với GVHD. Không khẳng định GVHD đã duyệt thay đổi phương án này.

## Nguồn và quyền sử dụng đã ghi nhận

- Bank: [publisher undertheseanlp](https://huggingface.co/datasets/undertheseanlp/UTS2017_Bank), revision `4d1319fa229720d392c1dc0e323d10b40eeacbd0`, card Apache-2.0.
- ViSFD: [repository tác giả](https://github.com/LuongPhan/UIT-ViSFD), revision `4b11ec2e4e97839600e6035b49d1645c79023354`. README tác giả ghi dùng miễn phí cho nghiên cứu, yêu cầu liên hệ riêng nếu sử dụng thương mại; không có căn cứ tự ghi CC BY 4.0 theo một mirror. [Bài báo tác giả](https://arxiv.org/abs/2105.15079) mô tả 11.122 bình luận do người gán; nghiên cứu này chỉ dùng các dòng có GENERAL.
- Shopee: [publisher Kaggle](https://www.kaggle.com/datasets/dduongdev/shopee-vietnamese-product-reviews-sentiment), version 1, card Apache-2.0. Chỉ file `shopee_reviews_dataset.jsonl`, không dùng 1.348 augmentation không dấu. License do publisher khai báo không chứng minh đã kiểm định quyền từng bình luận trên nền tảng.
- Phim: [ViMovieABSA tác giả](https://github.com/AlyThien/ViMovieABSA-A-Vietnamese-Aspect-Based-Sentiment-Dataset-for-Movie-Reviews-with-Reliability-Decompos), revision `2ceae3b15ece8f9a6c24f7b73465d940b0f8ce18`, README CC BY 4.0. Chỉ lấy văn bản gốc; nhãn train là lượt Qwen riêng, nhãn validation/pilot từ người thật. Nhãn mixed LLM/human ban đầu của nhà phát hành không được nhận là toàn bộ gold.

UIT-VSFC vẫn không được tự đổi thành Apache/MIT chỉ vì tải được. Card chính thức ghi license unknown; trang UIT và repo tổng hợp có các hướng dẫn nhận dữ liệu khác nhau. Nguồn này không phải một trong bốn bộ đã chốt ở config trên. Không phải chờ xin VLSP để chạy so sánh hiện tại.

## Chia tập và đo kết quả

Giữ split chính thức của Bank/ViSFD trong phạm vi task đã chọn; loại dòng train gần validation/test, loại validation gần test, lưu ID bị loại. Shopee chia cả họ trùng/gần trùng thành khoảng 70/15/15, seed 42. SequenceMatcher 0,88 là quy tắc xác nhận; RapidFuzz LCS chỉ lọc nhanh bằng cận trên, không thay đổi định nghĩa. Thiếu ID phim/tác giả nên không nhận là chia độc lập theo phim/tác giả.

Transformer: LR 2e-5, weight decay 0, AdamW, scheduler linear, warmup 0, max length 256, ba epoch, seed 42; batch 4 × tích lũy 2. Nếu có OOM thật, protocol cho batch 2 × 4 hoặc 1 × 8 và giữ log lỗi. Batch hiệu dụng vẫn 8; metadata giữ thông số thực tế. Chọn checkpoint tốt nhất theo validation Macro-F1. LR dùng char TF-IDF 2–5, balanced, C trong 0,25/1/4, chọn trên validation; epoch/LR/batch DL ghi N/A.

Đánh giá chính của đợt này là **validation**, không phải final test. Test Bank/ViSFD/Shopee còn khóa; các nhãn chỉ dùng kiểm tra phân bố/chia tập, không dùng chọn cấu hình từ kết quả model trên test. 100 câu phim đã dùng để phát triển từ trước nên chỉ là pilot, kể cả file nội bộ mang tên `test.jsonl`. Dữ liệu validation phim chỉ có 36 câu; một seed chưa đủ kết luận độ ổn định hoặc ý nghĩa thống kê.

## Máy khác tái lập sau khi pull

Tạo môi trường nghiên cứu bằng [AI_PORTABLE_SETUP.md](AI_PORTABLE_SETUP.md); `pipelines/requirements-research.txt` có RapidFuzz pin. Các lệnh dùng Python của môi trường đó, PYTHONPATH gồm root và pipelines. PhoBERT cần Java 17 và VnCoreNLP như cùng hướng dẫn. Các đường dẫn bên dưới tương đối với repo; không sao chép env, DB hay model cache của máy tác giả.

```text
python scripts/ai/fetch_uts2017.py --output pipelines/ml/data/reviewed/uts2017-bank
python scripts/ai/fetch_public_reviews.py shopee --version 1 --output .local/datasets/kaggle-shopee-v1
python scripts/ai/prepare_four_datasets.py shopee --output .local/datasets/four-vi-v1/shopee
python scripts/ai/prepare_four_datasets.py visfd --output .local/datasets/four-vi-v1/uit-visfd-general
python scripts/ai/reproduce_cinema_labels.py restore --input pipelines/configs/cinema_four_vi_labels.v1.json --output .local/datasets/four-vi-v1/cinema-silver
python scripts/ai/run_four_comparison.py --segmenter-path <thu-muc-VnCoreNLP>
python scripts/ai/export_four_comparison.py
```

Không chạy lại fetch/prepare vào thư mục dữ liệu đã có; chọn phiên bản output mới nếu muốn làm lại. Driver bỏ qua artifact đã hoàn tất nếu hash dữ liệu còn khớp; lưu partial/OOM riêng. File protocol tại thư mục output khóa config/hash dữ liệu của lượt chạy đó. Dùng output mới khi thay config/data, không ghi đè bằng chứng.

Driver hiện chụp mã ML và config bất biến trước khi fit, chạy từ các byte trong snapshot để tránh việc đang sửa source làm sai SHA cuối lượt. Các lượt đầu của đợt này giữ nguyên metadata cũ và có hai bản CLI được lưu theo SHA. Có một lượt Shopee ViDeBERTa đã nạp CLI cũ nhưng ghi SHA tệp mới ở cuối lượt trong lúc bỏ tham số segmenter không dùng cho model normalize; sidecar `source-provenance.json` công khai điểm này và lưu cả hai bản code. Hàm fitting, dữ liệu và siêu tham số không thay đổi; không sửa metadata/weights/điểm số để che khác biệt. Phiên bản CLI đã nạp được suy ra từ namespace thực lưu; đây là suy luận được đánh dấu trong provenance, không tuyên bố đã có snapshot trước giờ chạy cho các lượt cũ. Luồng chụp nguồn mới đã được thử train LR và cho cùng kết quả validation trên bộ phim.

Snapshot nhãn phim đi cùng source chỉ có ID/nhãn/nhóm/provenance và SHA văn bản. Script tải CSV gốc theo revision + SHA rồi khôi phục đúng văn bản/thứ tự. Người duyệt được thay bằng pseudonym của người đã thực sự xác nhận, không phải AI tự tạo người. Nhãn AI vẫn `reviewer=null`, `ai_labeled_unreviewed`. Các ghi chú, thời điểm và tên thật không được xuất. **Semantic SHA của đầu vào model/nhãn/nhóm khớp bản gốc**, nhưng hash toàn file JSONL thay đổi do bỏ trường riêng tư; không tuyên bố giống từng byte bản private. Bản khôi phục đã được kiểm tra trên máy này.

Đã kiểm chứng cả bốn bộ bằng container Linux CPU mới: tự tải toàn bộ nguồn theo phiên bản, khôi phục nhãn phim từ snapshot chỉ chứa ID/label, kiểm semantic SHA của đủ 12 split. Kết quả khớp văn bản đầu vào, nhãn, thứ tự và họ văn bản; không dùng file annotation private/cache/DB từ host. Thực hiện bằng `python scripts/ai/check_four_dataset_reproduction.py` trong môi trường có dependencies nghiên cứu; chỉ tải/chuẩn bị dữ liệu, không train hoặc mở final model test.

Để kiểm tra luồng trên máy chỉ có CPU, có thể chạy trước `python scripts/ai/run_four_comparison.py --dataset shopee --model lr`; LR không cần Java/VnCoreNLP. Chỉ PhoBERT cần `--segmenter-path`. Full Transformer có thể chạy CPU nhưng cần nhiều thời gian; GPU là lựa chọn phù hợp cho huấn luyện. Chatbot Docker vẫn có profile CPU riêng, không phụ thuộc môi trường CUDA nghiên cứu.

Sau khi hoàn tất train, chạy tokenization audit theo `ml.tokenization_audit --help` cho từng path trong config rồi export evidence. Exporter mặc định từ chối báo cáo hoàn tất nếu thiếu bất kỳ ô nào; `--allow-incomplete` chỉ dùng cho snapshot tiến độ nội bộ và thể hiện ô NOT RUN, không điền điểm 0.

## Đầu ra bàn giao

- `docs/reports/AI_GVHD_4_DATASET_2026-11-04.docx`: phần Chương 3 cập nhật và Chương 4 KB/RAG từ bằng chứng đã đo, để ghép vào quyển sau khi đủ 24 lượt và được render kiểm tra.
- File Markdown cùng tên và `docs/reports/evidence/2026-11-04-four-vi/`: bảng số, hình, metadata thực chạy, nhãn/protocol, phân bố, tokenization, lỗi theo ID và SHA256SUMS.
- Các kết quả cũ ngày 04/11 vẫn giữ đúng mốc; báo cáo mới không sửa lịch sử thành đã có bốn dataset trước khi thực nghiệm xong.

Việc có đủ so sánh trên bốn corpus không đồng nghĩa đã nghiệm thu classifier phim, hoàn tất ba seed/final test, hoặc đánh giá KB/RAG độc lập. Các việc đó tiếp tục được ghi riêng trong checklist. Mọi thay đổi hiện ở local; chưa commit/push.
