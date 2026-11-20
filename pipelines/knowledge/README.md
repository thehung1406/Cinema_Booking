# Knowledge base dùng chung

Sau khi pull nhánh chứa gói này (hoặc `main` sau khi PR được merge), từ thư mục gốc chạy:

```text
python scripts/ai/restore_knowledge.py --check
python scripts/ai/restore_knowledge.py
```

Chỉ cần Python 3.11/3.12, chưa cần Docker, model hay thư viện bổ sung. Lệnh đầu kiểm SHA-256 của gói trên Git; lệnh sau chép đúng tám tệp vào `.local/knowledge`, nơi các công cụ hiện có đọc dữ liệu. Chạy lại không làm thay đổi tệp đã khớp. Nếu tệp cũ khác nội dung, lệnh dừng trước khi ghi bất kỳ tệp nào. Xem lại bản cũ rồi dùng `--overwrite` nếu muốn thay bằng snapshot; hoặc dùng `--output .local/knowledge-shared` để giữ riêng bản đang làm.

## Nội dung đã đưa vào Git

| Vị trí | Nội dung |
| --- | --- |
| `sources.json`, `booking-guide.md`, `cinematography-summary.md` | Danh mục nguồn, tác giả, quyền sử dụng và hai nguồn văn bản |
| `snapshot/raw/exploring-movie-construction.pdf` | PDF Open SUNY nguyên bản, khoảng 11 MB, SHA-256 khóa trong `sources.json` |
| `snapshot/film-book.json` | Sách đã trích xuất, 84 khối văn bản có số trang PDF |
| `snapshot/booking-guide.json` | Hướng dẫn đặt vé theo bản `draft-2-20261120`, 10 khối văn bản |
| `snapshot/cinematography-summary.json` | Bản tóm tắt tiếng Việt, 3 khối văn bản |
| `snapshot/*.extraction.json` | Checksum, số khối và cảnh báo khi trích xuất |
| `graph-curation.v1.json`, `snapshot/graph/demo.cypher` | Năm phát biểu có đoạn bằng chứng, kèm bản Cypher có thể nạp lại |
| `snapshot/manifest.json` | Phiên bản tài liệu, ID graph release, kích thước và SHA-256 từng tệp |
| `pilot-questions.jsonl`, `rag-development-v2/v3.jsonl`, `rag-reference-20.jsonl` | Các tập câu hỏi phát triển/tham chiếu; không phải tập nghiệm thu đã được người chấm độc lập duyệt |

Snapshot ngày 20/11/2026 gồm ba tài liệu, đều `approved=false`. Không có tài khoản, hội thoại, mật khẩu, `.env`, database dump hay model weights trong gói này. Các thư mục `.local` riêng vẫn bị Git bỏ qua.

## Nạp vào chatbot trên máy mới

Khôi phục tệp không tự nạp vào database. Khởi tạo ứng dụng và tài khoản quản trị theo [hướng dẫn máy mới](../../docs/AI_PORTABLE_SETUP.md). Với **KB mới, chưa có ba nguồn này**, PowerShell chạy từ root:

```powershell
$kbCompose = @('--project-name', 'cinema-ai-demo', '--env-file', '.env.microservices', '-f', 'compose.yml', '-f', 'compose.ai-local.yml')
foreach ($kbName in @('film-book.json', 'cinematography-summary.json', 'booking-guide.json')) {
    docker compose @kbCompose cp ".local/knowledge/$kbName" "ai-service:/tmp/$kbName"
    if ($LASTEXITCODE -ne 0) { throw "Cannot copy $kbName" }
    docker compose @kbCompose exec -T ai-service python -m ai_service.import_knowledge "/tmp/$kbName"
    if ($LASTEXITCODE -ne 0) { throw "Cannot import $kbName" }
}
```

Giữ đúng project name và bộ tệp Compose của máy đang dùng; ví dụ trên dành cho profile `cinema-ai-demo`. AI Service phải đang chạy, đã migrate và bật `AI_WRITES_ENABLED`. CLI dùng môi trường sẵn có trong container nên không cần cài bộ nghiên cứu nặng trên máy.

Mở **Quản trị → Tài liệu** (`/admin/documents`), kiểm tra nội dung/nguồn rồi duyệt từng tài liệu bằng tài khoản có quyền `knowledge.manage`. Chatbot chỉ truy vấn tài liệu được duyệt và đã đến ngày hiệu lực. Lệnh nhập không tự duyệt hay sao chép quyết định duyệt từ máy tác giả.

Nếu KB đã có nguồn, dùng quy trình tạo phiên bản tại [runbook KB](../../docs/AI_RUNBOOK.md#5-kb-đa-nguồn-và-sách-pdf), không dùng lệnh nhập mới để thay bản đã công bố. Muốn bật Neo4j, làm theo [hướng dẫn graph](../../docs/AI_GRAPH_DEMO.md); sau restore không cần tải/trích xuất lại tài liệu. Bản Cypher trong snapshot được tạo từ đúng ba tài liệu trên, ID release nằm trong `snapshot/manifest.json`. Graph là tùy chọn; truy xuất văn bản vẫn dùng PostgreSQL.

Không phải bản sao database đang chạy trên máy tác giả. Các thay đổi chỉ tồn tại trong quản trị/database, trạng thái duyệt và lịch sử phiên bản chưa được xuất vào snapshot này. Giá, ghế, suất chiếu và đơn hàng phải lấy từ các dịch vụ nghiệp vụ của máy mới.

## Nguồn và quyền sử dụng

- **Exploring Movie Construction and Production** — John Reich / Open SUNY Textbooks, 2017. PDF gốc được giữ nguyên, gồm thông tin tác giả/quyền sử dụng trong sách. Quyền được ghi trong manifest: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), trừ phần có ghi khác. [Trang nhà xuất bản](https://milnepublishing.geneseo.edu/exploring-movie-construction-and-production/). JSON là văn bản trích từ PDF, đã chuẩn hóa Unicode, khoảng trắng và ngắt dòng, giữ số trang; chưa OCR. Gói phục vụ nghiên cứu/đồ án phi thương mại theo metadata nguồn.
- **Cinematography** — Wikibooks contributors, [bản oldid 3335736](https://en.wikibooks.org/w/index.php?title=Movie_Making_Manual/Cinematography&oldid=3335736). Bản tiếng Việt do trợ lý AI của dự án dịch rút gọn, không phải toàn văn, theo [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Hướng dẫn đặt vé** — do dự án Cinema Booking biên soạn, chờ người phụ trách xác nhận chính sách.

Giữ thông tin tác giả, nguồn, giấy phép và mô tả thay đổi khi chia sẻ lại. Chi tiết và checksum PDF ở [sources.json](sources.json). Tài liệu bản nháp không thay thế chính sách kinh doanh được phê duyệt.

## Tái tạo hoặc cập nhật dữ liệu

Dùng `prepare_knowledge.py` theo runbook để tạo bản mới từ nguồn, rồi `build_knowledge_graph.py` để tạo graph tương ứng; giữ đồng bộ phiên bản/đoạn nguồn trong curation. Cập nhật tệp snapshot và các kích thước/SHA-256 trong manifest cùng một PR, chạy `restore_knowledge.py --check` và kiểm tra nhập/chunk trước khi chia sẻ. Các con số đo trong báo cáo ngày 13/11 dùng corpus cũ; không coi đó là kết quả đo lại trên snapshot 20/11.
