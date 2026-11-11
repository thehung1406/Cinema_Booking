# Chạy AI sau khi pull dự án trên máy khác

Công cụ gán nhãn AI và UI 100 câu pilot có profile Docker riêng, không cần venv/GPU trên host: [AI_ASSISTED_LABELING.md](AI_ASSISTED_LABELING.md).

Không cần sao chép `.local`, `.env.microservices`, tài khoản, volume DB hoặc đường dẫn `C:/code` từ máy tác giả. Model và dữ liệu lớn không nằm trong Git; repository chứa cấu hình khóa phiên bản và lệnh tải lại. Các kết quả đã đo để đọc báo cáo nằm trong `docs/reports/evidence`, tách khỏi cache dùng khi chạy.

## Khởi chạy chatbot trên máy mới

Cần Git, Python 3.11/3.12 và Docker có Docker Compose. Windows/macOS dùng Docker Desktop với Linux containers; Linux dùng Docker Engine và Compose. **CPU là mặc định**, không bắt buộc NVIDIA/CUDA hay Ollama cài trên máy. Nên dành khoảng 12 GB RAM cho Docker khi chạy đồng thời các DB/API và model 4B; đây là mức dự trù, chưa phải cấu hình tối thiểu đã đo trên nhiều loại máy. Lần đầu cần internet và vài GB để tải image/model.

Từ thư mục repository vừa pull:

```text
python scripts/ai/local_stack.py prepare
python scripts/ai/local_stack.py up
python scripts/ai/local_stack.py status
```

`prepare` tạo credential ngẫu nhiên riêng trên máy mới trong file bị Git bỏ qua. Nếu đã có cấu hình, script giữ nguyên; không tự đổi password/volume. `up` build từ source, chạy các owner phục vụ AI, Ollama trong mạng Docker và tự tải `qwen3:4b`. Model phải khớp digest trong `pipelines/configs/chat_runtime.lock.json`, sau đó mới cho AI Service khởi động. Không phụ thuộc `host.docker.internal`, ổ C hoặc GPU của tác giả.

Lần đầu tải model có thể lâu. Xem `python scripts/ai/local_stack.py status` và log `ollama-init`; nếu digest không khớp, hệ thống dừng bước khởi tạo thay vì tự chấp nhận model khác. Giữ nguyên project name `cinema-ai-demo` giữa các lần chạy để dùng đúng volume của lần trước. Không đổi project để tìm lại dữ liệu cũ.

Mở http://127.0.0.1:5173 sau khi gateway sẵn sàng. Trên DB mới rỗng, tạo admin **của chính máy mới**:

```text
python scripts/ai/local_stack.py admin
python scripts/ai/local_stack.py references
python scripts/ai/local_stack.py demo
```

`admin` hỏi username/email/name/password trong terminal, chỉ hoạt động với Identity rỗng. `references` bổ sung idempotent hai thể loại và định dạng 2D qua CLI của Catalog, không sửa tài khoản hay phim đang có. `demo` hỏi đăng nhập admin rồi tạo phim/rạp/12 ghế/suất ngày mai đến ba ngày sau, đều ghi rõ **DEMO**. Không tạo thanh toán giả. Người dùng tự chọn ghế trên giao diện; chatbot chỉ tư vấn và dẫn đến màn hình đó.

Ví dụ thử: “Tối mai tôi muốn xem phim hài, hai người, tổng dưới 200k”. Trên máy CPU chậm, model có thể vượt timeout 20 giây; hệ thống ghi mode fallback/dependency và vẫn có luồng tra cứu xác định, không báo thành công model giả. Tốc độ GPU trong báo cáo không phải cam kết tốc độ CPU của máy khác.

Tắt nhưng giữ dữ liệu: `python scripts/ai/local_stack.py stop`. Không dùng `down -v` để xử lý lỗi. Các cổng mặc định 5173/8080/8082–8087 cần chưa bị ứng dụng khác chiếm.

Máy có NVIDIA và Docker GPU runtime có thể thêm `--gpu` khi chạy lệnh `up`. Đây là tùy chọn tăng tốc; không cần cho lệnh CPU. Hướng dẫn nền tảng: [Ollama Docker](https://docs.ollama.com/docker).

## Phạm vi profile và hệ thống đầy đủ

`compose.ai-local.yml` là profile phát triển chatbot/chọn ghế. Nó chạy Identity, Catalog, Cinema, Booking, Review, AI, gateway, web và Cinema worker. Nó chưa bật Payment/Reporting/Notification; cấu hình mới giữ writer tài chính và sentiment production tắt. Không nhận profile này là toàn bộ luồng thanh toán/báo cáo đã sẵn sàng.

Để chạy toàn bộ dự án, dùng quy trình khởi tạo chín owner, snapshot Reporting và cấu hình Payment/Notification ở [runtime đầy đủ](runbooks/final-runtime.md), rồi ghép `compose.ai-local.yml` để thêm Ollama nếu cần. Không dùng quy trình DB rỗng để ghi đè dữ liệu đã có.

Root Compose vẫn mặc định project `backend`, dùng đúng tên volume `backend_*` như trước. Volume/network nay theo project của Compose để bản kiểm thử mới có thể chạy tách biệt bằng `--project-name`; dữ liệu đang dùng phải giữ đúng project cũ.

## Tái tạo nghiên cứu và KB

Đây là phần tùy chọn, độc lập với việc chạy chatbot. Không bắt buộc máy bạn phải huấn luyện lại tất cả mô hình mới mở được ứng dụng.

```text
python scripts/ai/bootstrap_research.py --device cpu
```

Script tạo `.venv-ai-research` mới bằng Python 3.11/3.12, cài Torch 2.10 CPU, các thư viện nghiên cứu và owner package cần cho replay. NVIDIA phù hợp có thể chọn `--device cu128`; không tự phát hiện rồi ép cài CUDA. PhoBERT cần Java 17 và VnCoreNLP: Windows dùng `prepare_segmenter.py --include-java`, Linux/macOS cài Java 17 theo hệ điều hành rồi tải segmenter theo manifest khóa. Xem `python scripts/ai/prepare_segmenter.py --help`.

Kích hoạt môi trường vừa tạo. Trên Windows: `.venv-ai-research\Scripts\Activate.ps1`; trên Linux/macOS: `source .venv-ai-research/bin/activate`. Đặt PYTHONPATH gồm root và `pipelines`:

```powershell
# PowerShell, từ root repository
$env:PYTHONPATH="$(Get-Location);$(Join-Path (Get-Location) 'pipelines')"
```

```sh
# Linux/macOS, từ root repository
export PYTHONPATH="$PWD:$PWD/pipelines"
```

```text
python scripts/ai/fetch_knowledge_sources.py
python scripts/ai/fetch_uts2017.py
python scripts/ai/prepare_public_movie_reviews.py --output .local/annotations/cinema-public-v1
python -m ml.blind_annotation prepare --input .local/annotations/cinema-public-v1/cinema-pending.jsonl --output .local/annotations/cinema-double-blind-v1
```

PDF được tải bằng URL/SHA trong source manifest; Bank dùng revision cố định; corpus phim dùng commit đã khóa. Các lệnh từ chối ghi đè thư mục dữ liệu/gán nhãn hiện có. Sau khi tải, dùng `prepare_knowledge.py` để trích từng nguồn thành draft và `export_knowledge.py`/`evaluate_rag.py` để replay theo [runbook AI](AI_RUNBOOK.md). Không tự duyệt KB live.

Ví dụ train một model trên dữ liệu Bank đã kiểm tra:

```text
python -m ml.benchmark train --config pipelines/configs/ai_research.advisor-v3.json --dataset uts2017-bank --model visobert --output pipelines/ml/runs/my-bank-baseline
```

Checkpoint/tokenizer tải từ các revision trong config. CPU có thể rất chậm khi fine tune; không nhận thời gian GPU đã đo làm dự báo CPU. Ba bộ primary còn thiếu nhãn/quyền vẫn bị chặn, không tự tạo kết quả. Mô hình Bank chưa được duyệt để phân tích review phim production.

Quy tắc và công cụ gán nhãn/chấm RAG: [AI_HUMAN_REVIEW.md](AI_HUMAN_REVIEW.md). Không sao chép credential hay ký tên người duyệt thay thành viên.

## Những file sẽ đi theo khi nhóm tự commit

Báo cáo Word đã có sẵn để đọc. Nếu muốn dựng lại từ snapshot trong repository: cài `scripts/ai/requirements-report.txt` trong môi trường riêng rồi chạy `python scripts/ai/build_advisor_report.py` từ root. Builder dùng bằng chứng đã xuất trong `docs/reports/evidence/2026-11-04`; không cần đường dẫn runtime tài liệu riêng của tác giả.

Kiểm tra giao diện tự động trên runtime demo là tùy chọn. Trong `apps/web` chạy `npm ci` rồi `npx playwright install chromium --only-shell`; Playwright đã khai báo trong package/lock, không cần module tại `.local/browser`. Đặt `CINEMA_PORTABLE_DEMO_TEST=1`, `CINEMA_DEMO_CREDENTIALS` trỏ đến file JSON credential demo riêng bị Git bỏ qua, và `UI_BASE_URL` nếu đổi cổng; chạy `npm run test:ai:portable`. Test đăng nhập, hỏi model, xem card và mở trang ghế, không tạo đơn/thanh toán. Không dùng tài khoản hoặc lịch chiếu thật để chạy kịch bản demo.

Source, Compose bổ sung, cấu hình mẫu/lock, công cụ tải dữ liệu/model, tài liệu và snapshot bằng chứng gọn có thể đưa vào Git. `.env*` riêng, `.local`, `.venv-ai-research`, raw review và weights vẫn bị bỏ qua. Nhãn thật nhóm tạo cần được chuyển giao riêng theo điều kiện dữ liệu; tuyệt đối không coi chúng là đã có trên Git chỉ vì code nhập dữ liệu có trên Git.

Chưa có commit hoặc push do trợ lý thực hiện. Kiểm tra `git status` và chọn các thay đổi sau khi nhóm xem lại.
