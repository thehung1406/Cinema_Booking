# Đối chiếu yêu cầu AI của GVHD

Cập nhật 04/11/2026. Đây là checklist triển khai và minh chứng, không phải xác nhận đã hoàn tất nghiệm thu học thuật. Báo cáo Word: [Minh chứng AI](reports/AI_GVHD_2026-11-04.docx). Mọi thay đổi ở local, không commit/push.

## Ưu tiên nộp so sánh bốn dataset tiếng Việt

**Đã có đủ 24/24 lượt thật** của [protocol bốn corpus](AI_FOUR_DATASET_COMPARISON.md): Bank, ViSFD GENERAL, Shopee và phim silver; 5 Transformer + LR, seed 42. [Word cập nhật Chương 3 và 4](reports/AI_GVHD_4_DATASET_2026-11-04.docx), [bảng số](reports/AI_GVHD_4_DATASET_2026-11-04.md), [bằng chứng](reports/evidence/2026-11-04-four-vi/summary.json). Shopee hai lớp, phim train bằng AI silver và có nhãn người cho validation/pilot phải ghi rõ trong quyển; không tuyên bố bốn bộ gold ba lớp hoặc ma trận ba seed đã xong. Kết quả được kiểm lại từ confusion và hash dữ liệu/config, không còn ô NOT RUN trong bảng mới. Chương 4 giữ nguồn/PDF/output KB/IN–OUT đã chạy ở mốc cùng ngày, không tự đổi thành duyệt KB hoặc đánh giá RAG độc lập. Những bảng ghi chỉ một dataset/18 lượt bên dưới là lịch sử protocol cũ, không thay thế bảng bốn corpus hiện hành.

## Mốc sau 100 nhãn người thật

- Đã có **100/100 nhãn pilot của một người**, cộng 36 quyết định phát triển đã có trước; không còn là 0 nhãn người. Giữ riêng nhãn AI chưa duyệt.
- Đã đo Qwen, sáu artifact Bank và hai lượt huấn luyện silver LR/ViSoBERT. [Báo cáo mới](reports/AI_FILM_HUMAN_PILOT_2026-11-04.md) và [bằng chứng công khai](reports/evidence/2026-11-04-film-human-pilot/summary.json) có phân bố, bảng, bootstrap, ma trận nhầm lẫn, cấu hình chạy thật/SHA và phiếu bất đồng chưa người chấm.
- Vẫn thiếu đồng thuận người thứ hai, final test phim độc lập, ba dataset/54 lượt ma trận chính và đánh giá KB/RAG độc lập. Hai lượt silver bổ sung không được cộng vào 18/72. Chưa bật model cảm xúc chính thức.

Các bảng dưới là snapshot trước khi người dùng hoàn tất pilot, giữ số liệu theo đúng mốc thực hiện.

## Bổ sung lần triển khai tiếp theo ngày 04 tháng 11

| Nội dung | Kết quả thực và giới hạn |
| --- | --- |
| Chạy sau khi pull trên máy khác | Có profile Docker CPU, lock image/model và script tạo credential mới. Bản copy chỉ gồm source Git nhìn thấy đã tự tải model, tạo DB mới, trả card thật `model_planned` cho hai người với tổng 160.000đ. Không dùng env/cache/DB cũ. Mới kiểm thử Linux containers trên host Windows này, chưa chạy trên nhiều máy vật lý. |
| Ma trận và ablation | Ma trận chính vẫn **18/72**. Đã chạy thêm **6 lượt** ViSoBERT: LR 1e-5 và sqrt-balanced ở LR 2e-5, mỗi cấu hình ba seed. Mean Macro F1 0,655478 và 0,656294, thấp hơn baseline 0,657934; neutral F1 vẫn 0. Không nhập sáu lượt phụ thành ô mới của ma trận. |
| Gán nhãn phim | Chuẩn bị 600 câu thật lấy có chủ đích theo nhãn gợi ý và nền tảng; hai pass không hiển thị gợi ý, có Cohen κ trước phân xử và kiểm tra người thứ ba/lý do. Hiện 0 nhãn người xác nhận; κ ban đầu null. Không nhận mẫu cân bằng này là phân bố tự nhiên. |
| Chunking và truy xuất | 3 cấu hình 600/0, 1200/0, 1200/120 ký tự/overlap × 5 chiến lược × 24 câu AI pilot. Các tỷ lệ truy xuất trên bộ nhỏ này bằng nhau giữa ba cấu hình; chưa đủ cơ sở chọn chunking tối ưu. Retriever vẫn trả đoạn cho nhiều câu thiếu đáp án. |
| Generation và từ chối | Giữ cả các lượt lỗi. Bản đầu trả lời 6/10 câu thiếu thông tin; bản cuối từ chối 10/10 và trả lời 14/14 câu dự kiến có đáp án. Có lọc dữ kiện cụ thể và ánh xạ source span, không chỉ kiểm tra citation ID. Đây là phát triển trên chính bộ câu hỏi này, chưa phải accuracy/gold độc lập hoặc groundedness đã được người chấm. |
| Review với artifact thật | Artifact LR Bank → worker → thống kê → hai sự kiện RabbitMQ trong schema/queue test đã chạy thật. Không xác nhận nhãn thủ công thay người, không bật Bank model cho review phim production. |
| Bằng chứng đi theo Git | [Snapshot gọn](reports/evidence/2026-11-04/README.md) có bảng, hình, IN–OUT, metadata và SHA. Không cần copy `.local` chỉ để đọc báo cáo. PDF/model có công cụ tải lại theo khóa; raw review/weights/private env không đưa vào Git. |
| Regression hiện hành | **227 bài pass**, có broker test thật, không skip; 6 cảnh báo Pydantic sẵn có. Kết quả 204/1 skip ở phần v3 bên dưới là lượt kiểm tra trước đó. |

Hướng dẫn cho bạn cùng nhóm: [AI_PORTABLE_SETUP.md](AI_PORTABLE_SETUP.md). Phần người thật cần làm: [AI_HUMAN_REVIEW.md](AI_HUMAN_REVIEW.md). Những mục v3 bên dưới là bằng chứng gốc, được bổ sung bởi bảng cập nhật này.

## Kết quả thực nghiệm đã chạy

Đã hoàn tất **18 lượt validation trên UTS2017 Bank**: năm transformer và LR, mỗi model ba seed 17/42/73. Đây là 18/72 lượt của ma trận dự kiến, tương ứng một trong bốn dataset; không phải đã đủ ma trận. Chưa mở final test.

| Model | Seed hoàn tất | Macro F1 trung bình | Độ lệch chuẩn giữa seed |
| --- | ---: | ---: | ---: |
| PhoBERT | 3 | 0,6433 | 0,0031 |
| ViSoBERT | 3 | 0,6579 | 0,0015 |
| ViDeBERTa | 3 | 0,5925 | 0,0062 |
| mBERT | 3 | 0,6410 | 0,0030 |
| XLM R | 3 | 0,6511 | 0,0029 |
| TF IDF LR | 3 | 0,6333 | 0,0000 |

ViSoBERT có điểm validation quan sát cao nhất trong bản chụp này; chưa đủ cơ sở chốt model phim hoặc khẳng định ưu thế tổng quát. Cả sáu model vẫn có F1 neutral bằng 0 trên validation rất ít mẫu neutral. Độ lệch chuẩn thể hiện biến động giữa seed, không phải khoảng tin cậy trên dữ liệu phim.

Kiểm chứng Python: **204 passed, 1 skipped**; skip do RabbitMQ chưa chạy trong môi trường kiểm thử. Log tại `.local/evidence/advisor-v3/python-tests.log`. Kiểm tra link/UTF-8 tài liệu và `git diff --check` đạt. Không chạy lại web build vì lượt bổ sung này không đổi mã web.

## Yêu cầu và bằng chứng

| Yêu cầu | Trạng thái | Đầu ra hoặc phần cần hoàn thiện |
| --- | --- | --- |
| Microservices và thiết kế khớp code | Có | AI/Review sở hữu DB riêng; owner API cho dữ liệu động, ML offline; báo cáo mô tả đúng ranh giới |
| Learning rate theo config | Đã sửa | `benchmark.training_command` truyền LR/weight decay; `train_sentiment.transformer_training_arguments` cấp cho Trainer; regression dùng LR khác mặc định |
| Kiến trúc, layer, tham số | Có exporter | `ml.export_evidence --resolve-configs` lấy config checkpoint pin, đếm classifier ba lớp bằng meta tensors; bảng dự kiến ghi rõ chưa phải weights đã train |
| Thông số thực chạy | Có | `metadata.json` schema 2, `training_arguments.json`, `model_config.json`, `training_history.json`; seed, LR, epoch xong, batch hiệu dụng, optimizer và best checkpoint |
| LR baseline được mô tả đúng | Đã sửa | Metadata model TF IDF LR; layer/epoch/LR DL là null/N/A; lưu C, solver, max_iter và số vòng tối ưu thực tế |
| Bảng ngang cả trang Chương 3 | Có bản Word | Các cột model, đặc trưng, kiến trúc, layer, tham số, LR, epoch, batch, gradient accumulation, max length, optimizer; bảng dự kiến và kết quả thực tách riêng |
| Dữ liệu, phân bố, tiền xử lý | Có cho UTS2017 Bank | Data card, phân bố lớp/độ dài, source manifest/ID bị loại; các bộ còn thiếu không tự tạo EDA giả |
| So sánh 5 transformer × 4 dataset × 3 seed | Chưa đủ | Có lượt thật trên UTS2017 Bank; số run hoàn tất và Macro F1 nằm trong manifest. Còn thiếu các dataset độc lập đủ điều kiện; không lấy ba split làm ba dataset |
| Visual và phân tích lỗi | Có đầu ra thật, còn chấm định tính | Ma trận giữ ô not run, confusion matrices, F1 từng lớp/learning curves; xuất ID lỗi validation để người phân tích phủ định/mỉa mai/không dấu |
| Final test và ablation đầy đủ | Còn thiếu | Chưa mở final test; chưa hoàn tất các so sánh tiền xử lý/cân bằng lớp/threshold/reranker theo plan. Không coi bảng config và vài lượt pilot là đã đủ các phép thử này |
| Link nguồn KB và file PDF đã thu thập | Có | Manifest ba nguồn, PDF Open SUNY 94 trang/10.954.345 byte và SHA đối chiếu raw; link/file local trong Word |
| KB output một trang và giải thích | Có bản xuất draft | Ba documents, 226 chunks; một trang trình bày chunk sách PDF trang 26, metadata và nội dung; chưa nhận là KB live được duyệt |
| RAG kết nối KB đúng code | Có | Chunks lexical hash JSON trong AI DB; dense E5 qua inference API, cache RAM; chưa có vector DB/dense index bền vững |
| IN OUT thật và citation | Có pilot | Query, nguồn/page/score, request_body/schema/messages/context, JSON trả về và câu trả lời; `semantic_groundedness_human_reviewed=false` |
| So sánh truy xuất | Có pilot 5 chiến lược | Lexical/BM25/dense/hybrid/rerank trên ba câu pilot do AI tạo, có câu thiếu đáp án; BGE reranker đã chạy thật, chưa phải benchmark học thuật |
| Duyệt KB và gold độc lập | Còn thiếu | Người phụ trách xác nhận chính sách/nguồn và bộ câu hỏi; chấm correctness/groundedness/citation, hiệu chỉnh answerability và thử reranker |
| Bộ dữ liệu phim thật | Đã tìm/tải, chờ nhãn chuẩn | ViMovieABSA 10.797 dòng raw; 7.935 dòng chuẩn bị pending, nhãn gợi ý nhà phát hành tách khỏi nhãn người xác nhận |
| Không phải chờ xin VLSP | Đã đổi lựa chọn | Config v3 giữ một vị trí nguồn mở ba lớp cần chốt; nguồn Kaggle và điều kiện nhãn trong `AI_DATA_SOURCES.md` |

## Đọc đầu ra trên máy

- `.local/evidence/advisor-v3/research/research-evidence.json`: bảng config có nguồn/SHA, metadata thực của từng run và tình trạng ma trận.
- `.local/evidence/advisor-v3/research/model-table-planned.csv` và `MODEL_TABLE.md`: bảng dự kiến, không gắn nhãn đã train.
- `.local/evidence/advisor-v3/research/validation-summary.json`: chỉ tổng hợp run hoàn tất; final test chưa mở.
- `.local/evidence/advisor-v3/research/validation-errors.jsonl`: lỗi theo ID/model/seed, cột người đánh giá còn trống.
- `.local/evidence/advisor-v3/eda/` và `figures/`: phân bố, ma trận, F1 từng lớp, learning curves và confusion.
- `.local/evidence/advisor-v3/kb/`: source inventory, toàn bộ chunks JSONL, chunk đại diện và link nguồn.
- `.local/evidence/advisor-v3/rag-in-out.json`: trace thực trên ba nguồn draft trong RAM; không ghi credential.
- `.local/evidence/advisor-v3/rag-retrieval-pilot.json`: so sánh truy xuất và lỗi trả đoạn cho câu không có đáp án.
- `.local/evidence/advisor-v3/rag-in-out-dense-before-rerank.json`: trường hợp lỗi đã quan sát; giữ lại khi thay reranker/prompt, không che kết quả không tốt.
- `pipelines/ml/runs/advisor-v3/`: artifact, metadata, môi trường và lịch sử huấn luyện theo dataset/model/seed.

## Cách hiểu kết quả

Ngân hàng có validation 272 câu nhưng chỉ ba câu neutral. Macro F1/F1 từng lớp cần được đọc cùng support và confusion; accuracy cao không đủ để chọn model phim. Ba seed không biến một dataset thành ba bộ dữ liệu. Chưa dùng final test để chỉnh cấu hình hoặc ngưỡng.

Trace RAG là một lượt kiểm tra cơ chế với nguồn draft được bật tạm trong SQLite RAM. Citation ID đúng chưa chứng minh câu trả lời đúng nghĩa. Pilot truy xuất vẫn trả đoạn gần chủ đề cho câu không có chính sách; cần bộ gold và hiệu chỉnh trước khi nhận đủ chất lượng cho người dùng.

Đã nạp `BAAI/bge-reranker-v2-m3` revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, card Apache 2.0, chạy GPU/fp16/batch 4/max length 512 ở port private 8012. Case dense trước đó lấy đoạn cinematography thay vì định nghĩa genre; sau bổ sung reranker/prompt, case này đã trả hai câu tiếng Việt có citation đến chunk định nghĩa trang 26. Đây là case phát triển đã biết, chưa phải đánh giá độc lập hoặc người chấm groundedness. `pipelines/configs/rag_runtime.lock.json` ghi cả revision và digest model Ollama.

Nhóm đã chọn tìm dữ liệu công khai thay vì chờ xin VLSP. Các tập binary hoặc nhãn mixed LLM/human chưa được nhập lẫn vào benchmark ba lớp. Review phim công khai đã chuẩn bị để nhóm đọc xác nhận ở http://127.0.0.1:8766; công cụ không ký tên hay gán nhãn human thay thành viên.

## Phần cần nhóm tham gia

1. Chốt một tập review phim từ nguồn đã tải, gán nhãn thật/độc lập theo quy tắc và lưu người duyệt. Nhóm không cần tự thu thập lại corpus phim đã có.
2. Chọn thêm nguồn ba lớp có nhãn/provenance phù hợp trong danh mục, hoặc thống nhất nghiên cứu phụ hai lớp riêng cho Shopee/IMDb. Không tự đổi protocol để có đủ số dataset trên giấy.
3. Duyệt nguồn KB/chính sách nghiệp vụ và chấm bộ câu hỏi RAG độc lập. Các bước này cần người chịu trách nhiệm, không thay bằng tên/ngày duyệt do AI tạo.

Lệnh xuất lại và kiểm chứng ở [runbook AI](AI_RUNBOOK.md). Các thay đổi tài liệu không bật sentiment production, không tự phê duyệt KB, không sửa dữ liệu giao dịch hay tạo thanh toán.

Sơ đồ kiến trúc và ma trận thiết kế → code → bằng chứng ở [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md). Audit token hóa đo sau tiền xử lý của cả năm model, có special tokens và tỷ lệ vượt max length; không chạy mô hình trên test để chọn tham số. Learning curves dùng mean theo epoch; vùng mờ là ±1 độ lệch chuẩn khi có ít nhất hai seed, không phải khoảng tin cậy theo dân số.
