# Triển khai và vận hành phần AI

Cập nhật tài liệu 04/11/2026. Đọc cùng [plan](AI_FEATURE_PLAN.md) và [trạng thái thực hiện](AI_IMPLEMENTATION_STATUS.md). Tất cả thay đổi hiện ở máy cục bộ, chưa commit/push. Các lệnh chạy từ root repository, không bắt buộc đường dẫn `C:\code\Cinema_Booking`. Đây là hướng dẫn AI cho kiến trúc microservices: API trong `services/`, web trong `apps/web`, train/evaluate trong `pipelines/`, runtime tại root `compose.yml`.

Máy mới sau khi pull dùng [AI_PORTABLE_SETUP.md](AI_PORTABLE_SETUP.md): `local_stack.py prepare/up`, Docker CPU mặc định, tự tải đúng model, credential/volume riêng. Các tên `.local/ai-venv` và `.local/research-cuda` bên dưới ghi môi trường đo của tác giả; không cần sao chép chúng. Môi trường nghiên cứu mới được tạo bằng `bootstrap_research.py` tại `.venv-ai-research`.

Lệnh bổ sung: `run_bank_ablation.py` khai báo trước hai cấu hình và ba seed, chỉ dùng validation; `run_rag_chunk_ablation.py` replay ba cấu hình chunk; `benchmark_rag_answers.py` xuất trace và phiếu người chấm; `score_rag_human_review.py` kiểm tra checksum, không tự điền điểm. `check.ps1 -WithBroker` trên môi trường test hiện có bật broker riêng, không còn bỏ qua test sự kiện. [Hướng dẫn hai lượt gán nhãn và phân xử](AI_HUMAN_REVIEW.md).

Snapshot đọc được ngay sau khi pull ở `docs/reports/evidence/2026-11-04`; các đường dẫn tuyệt đối trong metadata là vị trí đã đo, không phải cấu hình triển khai. Source PDF có `fetch_knowledge_sources.py` theo checksum; `fetch_uts2017.py` nay khóa revision, không lấy nhánh main thay đổi theo thời gian.

**Chatbot đã chạy trong ứng dụng local:** mở http://127.0.0.1:5173; hướng dẫn đăng nhập, lệnh khởi động lại `scripts/ai/start_chat.ps1` và kết quả E2E với owner API thật ở [AI_LOCAL_CHAT.md](AI_LOCAL_CHAT.md). Các phần dưới vẫn phân biệt mặc định source/config mẫu với private runtime đã bật.

## 1. Thành phần đã có

- AI Service: hội thoại có ngữ cảnh; trích xuất yêu cầu bằng Ollama; đọc suất/giá/ghế từ Booking; hiển thị thẻ chọn ghế; hỏi lại khi thiếu ngày hoặc ngân sách chưa rõ mỗi vé/tổng nhóm.
- Review Service: worker phân tích cảm xúc; hàng đợi nhân viên xác nhận/sửa nhãn; giữ nguyên điểm dự đoán, lưu quyết định và sự kiện trong một transaction. Sửa nội dung làm kết quả cũ mất hiệu lực.
- Knowledge Base: tài liệu có tác giả/quyền sử dụng/phạm vi/checksum; sách PDF có số trang; tài liệu mới luôn chờ duyệt. Có lexical, BM25, dense, hybrid RRF và tùy chọn reranker.
- Nghiên cứu: nhập/xuất nhãn, giao diện gán nhãn, gợi ý bằng AI, audit/EDA, ma trận model × dataset × seed, huấn luyện, khóa final test và hình từ kết quả chạy thật.

Model chat đang thử là `qwen3:4b` chạy qua Ollama. Embedding thử là `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Đây chưa phải lựa chọn sản xuất đã vượt ngưỡng nghiệm thu. Sentiment sản xuất vẫn `disabled` cho tới khi có model phù hợp review phim.

**Yêu cầu GVHD ngày 04/11:** [checklist](AI_GVHD_CHECKLIST.md), [nguồn dữ liệu tải trực tiếp](AI_DATA_SOURCES.md) và [báo cáo Word](reports/AI_GVHD_2026-11-04.docx). Config mới `pipelines/configs/ai_research.advisor-v3.json` thay vị trí VLSP bằng nguồn mở chờ xác minh, giữ nguyên lock cũ để tái lập. Kết quả v3 ở `pipelines/ml/runs/advisor-v3`; không trộn vào kết quả v2 bên dưới.

## Bổ sung xuất minh chứng cho báo cáo

Môi trường `.local/research-cuda` hiện đã kiểm tra PyTorch `2.10.0+cu128` sử dụng RTX 5060 Laptop. `.local/ai-venv` vẫn giữ PyTorch CPU; việc cài thêm môi trường GPU không sửa môi trường API. Khi chạy nghiên cứu GPU dùng đúng executable và giữ manifest môi trường của từng run.

```powershell
$py = '.local/research-cuda/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = "$(Get-Location);$(Join-Path (Get-Location) 'pipelines')"
& $py -m ml.benchmark plan --config pipelines/configs/ai_research.advisor-v3.json --output pipelines/ml/runs/advisor-v3
& $py -m ml.export_evidence --config pipelines/configs/ai_research.advisor-v3.json --runs pipelines/ml/runs/advisor-v3 --output .local/evidence/advisor-v3/research --resolve-configs
& $py scripts/ai/export_validation_errors.py --runs pipelines/ml/runs/advisor-v3 --output .local/evidence/advisor-v3/research
& $py -m ml.research_figures pipelines/ml/runs/advisor-v3 --config pipelines/configs/ai_research.advisor-v3.json --output .local/evidence/advisor-v3/figures
& $py scripts/ai/export_knowledge.py --corpus .local/knowledge/booking-guide.json .local/knowledge/film-book.json .local/knowledge/cinematography-summary.json --output .local/evidence/advisor-v3/kb
```

Transformer nhận `--learning-rate`/`--weight-decay` thật từ config. Metadata schema 2 lưu riêng `requested_arguments`, `architecture` và `training`; TrainingArguments JSON ghi cấu hình thư viện thực dùng. LR không nhận epoch/LR của transformer; bảng lấy C, solver và số vòng tối ưu thực tế. Exporter chỉ tổng hợp run có metadata và validation hoàn tất, không tự gán 0 cho ô thiếu.

Khi Ollama và embedding đã nạp/ấm:

```powershell
& $py scripts/ai/smoke_rag_answer.py --corpus .local/knowledge/booking-guide.json .local/knowledge/film-book.json .local/knowledge/cinematography-summary.json --output .local/evidence/advisor-v3/rag-in-out.json
```

Trace chỉ bật trong CLI replay cô lập: lưu `request_body` đúng schema/messages/options gửi Ollama, `response_content`, JSON được validate và source/page/score. Không ghi HTTP headers/token. Context có nội dung tài liệu nên giữ trace trong thư mục evidence local, chỉ xuất phần được phép đưa vào báo cáo. Lượt cold embedding từng vượt timeout 8 giây; warm trace không được báo thành latency cold hay SLA.

Tạo Word bằng `scripts/ai/build_advisor_report.py` trong môi trường tài liệu; sau tạo phải render và kiểm tra đủ các trang, đặc biệt trang ngang model và một trang output KB. Không tự coi file DOCX sinh thành công là đã kiểm tra bố cục.

## 2. Môi trường Python riêng

Máy hiện đã có `.local/ai-venv`; không cần cài lại khi tiếp tục công việc này. Khi tạo môi trường mới, cài PyTorch phù hợp CPU/CUDA trước, rồi:

```powershell
python -m venv .local/ai-venv
$py = '.local/ai-venv/Scripts/python.exe'
& $py -m pip install -r pipelines/requirements-research.txt
& $py -m pip install -e packages/python-platform -e services/ai-service -e services/review-service -e services/catalog-service -e services/cinema-service -e services/booking-service
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = "$(Get-Location);$(Join-Path (Get-Location) 'pipelines')"
```

Notebook/research/inference nặng tách khỏi API owner. `pipelines/ml/serve_retrieval.py` không truy cập DB. CLI replay KB có dùng model DB của AI nằm tại `scripts/ai/evaluate_rag.py`, ngoài pipeline huấn luyện.

## 3. Công cụ gán nhãn cho nhóm

Nói đơn giản: mỗi câu review cần người đọc xác nhận **tích cực / trung lập / tiêu cực** về bộ phim. AI làm lượt gợi ý đầu; không tự ký tên thay thành viên. Nhãn phim và nhận xét về rạp/dịch vụ cần phân biệt. Câu mỉa mai, hỗn hợp hoặc thiếu ngữ cảnh cần ghi chú hoặc để chờ xử lý.

| Nhãn | Quy tắc |
| --- | --- |
| `positive` | Kết luận tốt về phim hoặc khuyến khích xem |
| `negative` | Kết luận không tốt, thất vọng hoặc không khuyến khích xem |
| `neutral` | Mô tả phim mà không thể hiện rõ đánh giá |

Câu hỗn hợp theo kết luận tổng thể nếu rõ. Không ép câu thiếu bối cảnh/mỉa mai vào neutral. Tách nhận xét chỉ về rạp, nhân viên hoặc thanh toán khỏi tập cảm xúc phim; không suy nhãn từ số sao hoặc trạng thái mua vé. Có thể ghi tags `negation`, `slang`, `sarcasm`, `mixed`, `no-diacritics`, `wrong-target` để phân tích lỗi.

### Dùng ngay bộ mẫu đã có

`pipelines/ml/data/drafts/sentiment_100.jsonl` chứa 100 câu **do AI soạn**, có dấu `synthetic=true`. Chỉ dùng học quy trình, kiểm thử và thảo luận quy tắc; không đổi tên thành D1 thật. Lượt gợi ý mới được lưu tại `.local/annotations/sentiment-suggested.jsonl` sau khi chạy xong.

```powershell
$py = '.local/ai-venv/Scripts/python.exe'
$env:PYTHONPATH = "$(Get-Location);$(Join-Path (Get-Location) 'pipelines')"
& $py -m ml.annotation_app .local/annotations/sentiment-suggested.jsonl --output .local/annotations/sentiment-confirmed.jsonl
```

Mở **http://127.0.0.1:8765**, nhập tên/mã thành viên thật, đọc từng câu rồi xác nhận. Có thể để lại câu khó. Kết quả được lưu nguyên tử sau mỗi lần lưu; mở lại cùng lệnh để tiếp tục. Công cụ giữ cờ synthetic và phân biệt gợi ý với nhãn xác nhận. Không tự train hoặc gửi dữ liệu lên GitHub. Đóng cửa sổ terminal bằng Ctrl+C để dừng.

Nếu chưa có file gợi ý, dùng thẳng file draft làm input. Không chạy hai instance cùng ghi một file output.

### Chuẩn bị review thật của dự án

Sau khi Review Service có dữ liệu đã duyệt và nhóm có cơ sở cho phép dùng nghiên cứu, xuất qua API chỉ đọc. Thay danh sách film ID và nội dung quyền sử dụng bằng thông tin thật:

```powershell
& $py scripts/ai/export_reviews.py --origin http://127.0.0.1:8083 --film-id 1 2 3 --license 'Nội dung quyền sử dụng đã được nhóm xác minh' --output .local/annotations/cinema-raw.jsonl
& $py -m ml.suggest_annotations .local/annotations/cinema-raw.jsonl --output .local/annotations/cinema-suggested.jsonl
& $py -m ml.annotation_app .local/annotations/cinema-suggested.jsonl --output .local/annotations/cinema-confirmed.jsonl
```

Lệnh gợi ý dùng Ollama ở localhost, để `label/reviewer` trống và `review_status=pending`. Nếu model lỗi, câu đó vẫn chờ duyệt. Export không sao chép tên/tài khoản tác giả, không chuyển số sao hoặc nhãn model thành ground truth. Chụp dữ liệu lúc tạm ngừng sửa review để tránh phân trang bị trôi.

### Hai người gán nhãn và giải quyết bất đồng

CSV có các cột `label`, `reviewer`, `second_label`, `second_reviewer`, `annotation_note`. Người thứ hai gán độc lập; lưu người thật, ghi quyết định xử lý bất đồng. Chưa có chỉ số agreement nếu chưa có lượt gán độc lập thật.

Mục tiêu gán độc lập ít nhất 20% rồi giải quyết bất đồng, không chỉ sao chép nhãn người thứ nhất. Giữ nguồn, ngày thu thập, quyền sử dụng và `group_id` theo cùng nguồn/phim/họ diễn đạt cần cách ly; chỉ đặt `review_status=approved` sau rà soát thật.

```powershell
& $py -m ml.annotations export .local/annotations/cinema-raw.jsonl .local/annotations/cinema-sheet.csv
# Nhóm điền CSV, đặt review_status=approved cho các câu đã chốt.
& $py -m ml.annotations import .local/annotations/cinema-raw.jsonl .local/annotations/cinema-sheet.csv --output .local/annotations/cinema-reviewed.jsonl
& $py -m ml.data .local/annotations/cinema-reviewed.jsonl pipelines/ml/data/reviewed/cinema-vi --seed 42
& $py -m ml.dataset_audit pipelines/ml/data/reviewed/cinema-vi --output .local/evidence/cinema-vi-eda
```

Gộp phim và họ câu gần trùng trước khi chia; không chia một họ câu sang train/test để đủ tỷ lệ. Cần ít nhất 7 nhóm độc lập trong splitter hiện tại và cả ba nhãn ở mỗi split mới được train. Số lượng này chỉ là rào kiểm tra kỹ thuật, không đủ để khẳng định dataset có chất lượng học thuật. Đọc bảng phân bố trước/sau và kiểm tra nhãn ít mẫu.

## 4. Thực nghiệm cảm xúc

Config `pipelines/configs/ai_research.json` là khai báo. `ai_research.lock.json` ghi SHA checkpoint đã tra từ nguồn, không chứa weights. Nếu đổi model/config, tạo lock mới thay vì sửa đè lock cũ. Phải kiểm tra điều khoản của checkpoint, đặc biệt hai card chưa khai báo license; chưa coi việc pin SHA là xác minh quyền sử dụng.

```powershell
& $py scripts/ai/lock_experiment.py --help
& $py -m ml.benchmark plan --config pipelines/configs/ai_research.lock.json --output pipelines/ml/runs/proposed
```

72 lượt gồm 5 transformer + LR bổ sung × 4 dataset × 3 seed. Tập dữ liệu thiếu bị ghi `blocked`; kết quả chưa chạy không được điền 0. PhoBERT cần Java/VnCoreNLP và `--segmenter-path` thực; các model khác dùng chuẩn hóa NFC/khoảng trắng. Mặc định max length 256, batch 1, gradient accumulation 8; ghi môi trường, fingerprint dữ liệu, SHA code Python và model version theo nguồn/seed/dữ liệu.

Nguồn công khai UTS2017_Bank đã có importer: giữ nhãn do tác giả phát hành và giữ test gốc; loại train gần trùng với test; tách validation theo họ gần trùng, ghi ID đã bỏ trong source manifest. Nhãn này được ghi là nhãn tác giả ngoài dự án, không nhận là nhóm tự gán.

```powershell
& $py scripts/ai/fetch_uts2017.py --help
& $py -m ml.benchmark train --config pipelines/configs/ai_research.lock.json --dataset uts2017-bank --model lr --output pipelines/ml/runs/validation-v2
& $py -m ml.benchmark summary --config pipelines/configs/ai_research.lock.json --output pipelines/ml/runs/validation-v2
& $py -m ml.research_figures pipelines/ml/runs/validation-v2 --output .local/evidence/sentiment-figures-v2
```

Để chạy transformer, đổi `--model` sang ID config và cung cấp segmenter khi cần. `.local/ai-venv` dùng PyTorch CPU; `.local/research-cuda` đã kiểm tra chạy GPU trong lượt v3. Ollama dùng GPU không tự làm môi trường Python khác có CUDA. Đọc metadata của đúng run khi dẫn kết quả.

Chuẩn bị PhoBERT trên Windows bằng file phân đoạn/Java đã pin và kiểm SHA:

```powershell
& $py scripts/ai/prepare_segmenter.py --include-java
$env:JAVA_HOME = (Get-ChildItem .local/java -Directory | Select-Object -First 1).FullName
$env:PATH = (Join-Path $env:JAVA_HOME 'bin') + ';' + $env:PATH
& $py -m ml.benchmark train --config pipelines/configs/ai_research.advisor-v3.json --dataset uts2017-bank --model phobert --segmenter-path (Join-Path (Get-Location) '.local/vncorenlp') --output pipelines/ml/runs/advisor-v3
```

Lock tại `pipelines/configs/segmentation.lock.json`; đây là portable JRE trong `.local`, không cài đè Java hệ thống. CLI từ chối ghi đè file khác checksum. Trainer khôi phục working directory sau khi VnCoreNLP khởi tạo và lưu SHA jar/vocabulary/rules vào metadata; đường dẫn tương đối không bị thư viện chuyển sang thư mục model.

Chọn cấu hình bằng validation, cố định lựa chọn/ngưỡng, rồi mới mở final test bằng `ml.benchmark evaluate ... --final-test` hoặc `ml.evaluate_sentiment ... --final-test`. Không lặp test để chọn C/epoch/threshold. Hiện mới có kết quả validation LR; không đưa model miền ngân hàng vào Review Service như model review phim đã nghiệm thu.

## 5. KB đa nguồn và sách PDF

Neo4j, công bố phiên bản KB và so sánh hai mô hình demo được hướng dẫn tại [AI_GRAPH_DEMO.md](AI_GRAPH_DEMO.md).

Manifest: `pipelines/knowledge/sources.json`. Có hướng dẫn nội bộ, sách Open SUNY thật và bản tóm tắt/dịch Wikibooks có attribution/license. Bản tóm tắt không được mô tả là đã crawl toàn bộ website. Tất cả đang là draft chờ kiểm tra nội dung/quyền dùng theo bối cảnh.

PDF local: `.local/knowledge/raw/exploring-movie-construction.pdf`. SHA-256 trong manifest; bản tải từ mirror cơ sở giáo dục vì URL nhà xuất bản trả 403 lúc tải. Không thêm PDF vào Git. Có 94 trang PDF; trang PDF có thể khác số trang in trong sách. Trích xuất báo các trang ít text; chưa OCR và chưa tự phê duyệt.

```powershell
& $py scripts/ai/prepare_knowledge.py pipelines/knowledge/sources.json cinema-booking-guide pipelines/knowledge/booking-guide.md --output .local/knowledge/booking-guide.json
& $py scripts/ai/prepare_knowledge.py pipelines/knowledge/sources.json open-suny-film-construction .local/knowledge/raw/exploring-movie-construction.pdf --output .local/knowledge/film-book.json
& $py scripts/ai/prepare_knowledge.py pipelines/knowledge/sources.json wikibooks-cinematography-summary pipelines/knowledge/cinematography-summary.md --output .local/knowledge/cinematography-summary.json
```

Kết quả có `approved=false`, metadata, checksum, page blocks và file `.extraction.json`. Người có `knowledge.manage` nhập qua API rồi duyệt ở `/admin/documents`. Khai báo token đăng nhập hợp lệ trong biến môi trường `CINEMA_ADMIN_TOKEN`, không ghi token vào file/lịch sử Git. Dùng origin AI Service `http://127.0.0.1:8082` hoặc origin gateway theo runtime:

```powershell
& $py scripts/ai/import_knowledge.py .local/knowledge/film-book.json --origin http://127.0.0.1:8082
```

Lặp cho hai nguồn còn lại. CLI này chỉ tạo draft. Với nguồn đã tồn tại, dùng `--revision-of <document-id>` để lưu bản mới trong lúc bản hiện tại tiếp tục phục vụ. Nếu có đồ thị đã nạp cho phiên bản mới, thêm `--graph-release-id <release-id>`.

Trang quản trị cho xem chunk, metadata, trang PDF; thử lexical/BM25/dense/hybrid/rerank và xem nguồn/điểm/độ trễ. PDF sửa bằng pipeline nhập để giữ provenance. Thu hồi duyệt làm tài liệu mất khỏi truy xuất tiếp theo. Giá/ghế/suất sống trong owner API, không chép vào KB tĩnh.

### Embedding và tùy chọn reranker

```powershell
& $py -m ml.serve_retrieval --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3 --port 8011
```

Runtime bind localhost, nạp model pinned, batch passage và cache trong RAM; endpoint `/similarity`, `/rerank`, `/health/ready`. Server CPU port 8011 không cấu hình reranker; nếu gọi `/rerank` ở server đó thì unavailable. Ngày 04/11 đã tải và chạy BGE reranker thật trên GPU ở private port 8012:

```powershell
$gpuPy = '.local/research-cuda/Scripts/python.exe'
& $gpuPy -m ml.serve_retrieval --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3 --reranker BAAI/bge-reranker-v2-m3 --reranker-revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e --device cuda --fp16 --port 8012
```

Embedding giữ dtype mặc định; `--fp16` áp dụng cho reranker, batch 4/max length 512. Lock tại `pipelines/configs/rag_runtime.lock.json`, model card Apache 2.0. Đây là runtime phục vụ pilot; chưa tự bật vào AI Service hoặc vượt nghiệm thu gold. Cần warmup trước đo truy vấn ấm, vẫn ghi nhận timeout cold đã quan sát.

```powershell
& $py scripts/ai/smoke_rag_answer.py --corpus .local/knowledge/booking-guide.json .local/knowledge/film-book.json .local/knowledge/cinematography-summary.json --strategy rerank --embedding-url http://127.0.0.1:8012 --reranker-url http://127.0.0.1:8012 --output .local/evidence/advisor-v3/rag-in-out-rerank.json
```

Trace có runtime health và digest Qwen bên cạnh request/response thật. Case dense trả lời nhầm trọng tâm đã giữ lại riêng; prompt mới yêu cầu chọn nguồn trực tiếp và trả tối đa hai câu. Cải thiện trên pilot đã biết không được tính là chất lượng trên test độc lập.

```powershell
& $py scripts/ai/evaluate_rag.py --corpus .local/knowledge/booking-guide.json .local/knowledge/film-book.json .local/knowledge/cinematography-summary.json --gold pipelines/knowledge/pilot-questions.jsonl --pilot --strategies lexical bm25 dense hybrid --embedding-url http://127.0.0.1:8011 --output .local/evidence/rag-pilot-v2.json
```

`--pilot` chỉ duyệt tạm trong SQLite RAM riêng để kiểm tra pipeline, không sửa trạng thái file hoặc DB dự án. Bộ câu hỏi kèm repo do AI soạn, chưa phải gold benchmark. Đánh giá chính thức bỏ `--pilot`, dùng corpus đã duyệt và câu hỏi do người duyệt có reviewer/source/license/group_id, expected source_id/version/pages. Báo Recall@k/MRR/nDCG@k, query không trả lời được, latency và trace; không tự nhận đã đo độ đúng của câu trả lời sinh.

Dense similarity dương chưa phải ngưỡng đủ căn cứ. Cần gold/hard negative để hiệu chỉnh answerability/rerank và người đánh giá groundedness. Mặc định runtime vẫn lexical; không bật dense cho khách chỉ dựa vào vài câu pilot.

## 6. Chat và runtime ứng dụng

Theo [runbook runtime chung](runbooks/final-runtime.md) khi chạy toàn bộ dự án. Migration owner hiện dùng AI `ai_003` và Review `review_003`. Migrate trước API/worker mới.

Đã thêm các biến cấu hình vào `services/ai-service/.env.example`, `.env.microservices.example` và service AI trong `compose.yml`. Mặc định LLM disabled. Khi Ollama đã khởi động/nạp model, đặt trong cấu hình private:

```dotenv
AI_LLM_PROVIDER=ollama
AI_LLM_MODEL=qwen3:4b
AI_LLM_BASE_URL=http://host.docker.internal:11434
AI_LLM_TIMEOUT_SECONDS=8
AI_RETRIEVAL_STRATEGY=lexical
AI_EMBEDDING_URL=
AI_RERANKER_URL=
```

Nếu chạy AI trực tiếp trên host, base URL Ollama là `http://127.0.0.1:11434`. Nếu thử dense trong Docker Desktop, runtime embedding phải lắng nghe trên địa chỉ host Docker truy cập được và cấu hình origin đúng; server mặc định localhost chưa tự cung cấp mạng giữa các container. Không thêm port inference vào gateway công khai.

Ollama portable hiện ở `.local/ollama/ollama.exe`, model ở `.local/ollama-models`, log trong `.local`. Model cần warmup trước bài đo; cold start có thể vượt timeout request. `AI_WRITES_ENABLED` và credential owner vẫn tuân theo runtime chung. Trợ lý hiện không tự giữ ghế/tạo đơn/thanh toán.

```powershell
& $py scripts/ai/smoke_planner.py
& $py scripts/ai/smoke_chat.py
& $py scripts/ai/smoke_rag_answer.py
```

Lệnh đầu gọi model thật; lệnh thứ hai gọi model thật qua chat API nhưng dùng DB/cache/owner fixtures riêng. Lệnh thứ ba truy xuất sách PDF đã trích xuất bằng embedding thật rồi sinh câu trả lời với citation; KB chỉ duyệt tạm trong RAM, chưa được nhóm đánh giá độ đúng. Báo cáo ghi rõ đây không phải dữ liệu suất thật hoặc test end-to-end toàn stack.

## 7. Kiểm chứng và bằng chứng

`scripts/ai/check.ps1` dành cho PostgreSQL kiểm thử local port 55432 với DB `cinema_*_test`, không kết nối DB dự án. Cần các service Python được cài và source fixture schema đã migrate. Đọc script trước khi tái sử dụng ở máy khác; không đổi URL sang DB sản xuất.

```powershell
& scripts/ai/check.ps1
Push-Location apps/web
npm run lint
npm test
npm run build
# PLAYWRIGHT_MODULE/BROWSER_EXECUTABLE có thể trỏ tới bản cài cục bộ.
node tests/ai-flow.mjs
Pop-Location
```

Output kiểm thử ở `.local/evidence`: `ai-tests.xml`, `ai-tests.log`, `ai-ui.log`, ảnh UI, `planner-pilot.json`, `full-chat-pilot.json`, EDA, hình confusion/validation và `rag-pilot-v2.json`. Test UI chặn toàn bộ XHR/fetch bằng fixtures, không ghi backend/thanh toán thật. Bộ UI tổng quát cũ còn timeout ở luồng payment; không nhận là toàn bộ E2E đã đạt.

Ma trận tương ứng yêu cầu → code → bằng chứng và các đầu ra học thuật còn thiếu ở [trạng thái thực hiện](AI_IMPLEMENTATION_STATUS.md). Không dùng biểu đồ pilot/baseline một dataset để thay bảng 5 transformer × 4 dataset.
