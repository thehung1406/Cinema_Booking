# Các bước nhóm cần đọc và xác nhận

**Trạng thái mới:** 100 câu pilot đã được bạn hoàn tất và đánh giá; không cần làm lại hoặc đọc tiếp cả 600 để kết thúc bước này. [Kết quả](reports/AI_FILM_HUMAN_PILOT_2026-11-04.md) còn cho thấy bất đồng đáng kể; chưa đủ để coi 426 nhãn AI là gold. Phiếu bất đồng theo ID đã xuất, chưa giả điền người thứ hai hay phân loại lỗi. Quy trình hai người bên dưới là phương án đánh giá đầy đủ, không phải thông báo bạn còn nợ thêm 600 câu ngay lúc này.

Code, dữ liệu chờ duyệt và công cụ đã được chuẩn bị trên máy. File này chỉ yêu cầu những quyết định cần con người; không yêu cầu nhóm tự tải lại review phim hay tự viết pipeline.

**Cập nhật phương án giảm đọc tay:** đang triển khai [pilot AI gán nhãn và 100 câu người kiểm tra](AI_ASSISTED_LABELING.md). 36 quyết định đã làm được giữ nguyên. Phần 600 câu/hai pass dưới đây là phương án gán nhãn độc lập đầy đủ trước đó, không bắt buộc phải đọc hết để chạy pilot mới. 100 câu mới chưa mặc nhiên đủ để nghiệm thu cuối.

## Gán nhãn phim: bắt đầu bằng hai người

Đã chọn **600 nhận xét thật** từ ViMovieABSA, bỏ trùng văn bản chính xác. Lấy 200 câu trong mỗi nhóm nhãn gợi ý của nhà phát hành để có đủ ứng viên neutral, đồng thời trải trên năm nguồn nền tảng. Đây là mẫu phát triển có chủ đích, **không phải phân bố tự nhiên** và không phải nhãn chuẩn. Nguồn/giấy phép ở [danh mục dữ liệu](AI_DATA_SOURCES.md).

- Người A mở http://127.0.0.1:8767 trên máy này.
- Người B mở http://127.0.0.1:8768 trên máy này, vào lượt khác hoặc trình duyệt khác nếu cần.
- Mỗi người nhập tên hoặc mã thành viên riêng, tự đọc cùng 600 câu được xáo thứ tự khác nhau. Không trao đổi đáp án trước khi hoàn thành. Hai lượt không hiển thị nhãn gợi ý hay nhãn của người còn lại.
- Nếu làm trên hai máy, tải cùng revision corpus và chạy cùng lệnh chuẩn bị để có cùng 600 ID; mỗi người thực hiện pass của mình. Sau đó chuyển riêng hai file confirmed về cùng thư mục để đối chiếu, giữ nguyên nội dung/ID. Không cần đưa raw review hay credential vào Git.
- Nếu trang chưa chạy, từ thư mục dự án chạy `scripts/ai/start_annotation.ps1 -Pass A` hoặc `-Pass B`.

Chọn **positive** khi nhận xét chủ yếu khen bộ phim hoặc trải nghiệm nội dung phim; **negative** khi chủ yếu chê; **neutral** khi chỉ mô tả, hỏi thông tin hoặc không bộc lộ đánh giá tích cực/tiêu cực rõ. Không tự coi một câu vừa khen vừa chê là neutral: xem kết luận chung và ghi chú. Giữ nguyên tiếng lóng, không dấu và emoji khi đọc. Cần xét phủ định, mỉa mai và đối tượng đang được đánh giá.

Nếu nhận xét chỉ nói về người bình luận, dịch vụ ngoài phim, không hiểu được hoặc thiếu bối cảnh, dùng **Để lại chờ xử lý**. Chưa chắc thì để chờ, không ép thành neutral. Những câu này cần được nhóm quyết định loại hoặc bổ sung ngữ cảnh trước khi chốt dataset. Hiện thao tác bỏ qua chưa lưu ghi chú thành quyết định loại dữ liệu.

Ví dụ minh họa do AI viết để giải thích quy tắc, **không đưa vào benchmark**: “Phim cuốn, muốn xem lại” là positive; “Kịch bản rời rạc, xem rất chán” là negative; “Phim dài 120 phút” là neutral. Mỉa mai như “Hay quá, ngủ từ đầu đến cuối” cần đọc toàn câu.

Kết quả lưu riêng, tự tiếp tục sau khi mở lại:

```text
.local/annotations/cinema-double-blind-v1/pass-A-confirmed.jsonl
.local/annotations/cinema-double-blind-v1/pass-B-confirmed.jsonl
```

Sau hai lượt, chạy trong môi trường Python AI đã cài:

```powershell
$env:PYTHONPATH="$(Get-Location);$(Join-Path (Get-Location) 'pipelines')"
.local/ai-venv/Scripts/python.exe -m ml.blind_annotation reconcile `
  --input .local/annotations/cinema-double-blind-v1/pass-A-confirmed.jsonl `
  --second .local/annotations/cinema-double-blind-v1/pass-B-confirmed.jsonl `
  --output .local/annotations/cinema-double-blind-v1/reconciliation-1
```

`agreement.json` có số đã được cả hai xác nhận, tỷ lệ đồng thuận và Cohen κ **trước phân xử**. Thiếu dữ liệu thì κ là null; không thay bằng 0. Cùng tên người ở hai lượt bị từ chối. Công cụ ghi lại tên do người thao tác cung cấp, không xác thực danh tính ngoài đời.

Những câu khác nhãn nằm trong `adjudication-pending.jsonl`. Người thứ ba đọc lại và ghi lý do, chạy công cụ gán nhãn với file này làm đầu vào và một file đầu ra mới. Công cụ yêu cầu tên khác hai người đầu và lý do quyết định. Sau đó thêm `--adjudicated <file-kết-quả-người-thứ-ba>` khi tạo snapshot reconciliation mới. `accepted.jsonl` chỉ chứa nhãn đồng thuận hoặc quyết định phân xử thật. Vẫn phải kiểm tra chất lượng, nhóm gần trùng và tách train/validation/test trước khi huấn luyện.

600 câu này không thay thế mục tiêu dữ liệu phim đủ lớn. Sau khi kiểm tra quy tắc và mức đồng thuận, dùng cùng quy trình cho phần còn lại trong 7.935 ứng viên. Không nhập nhãn gợi ý thành gold để làm đầy dataset.

## Chấm câu trả lời RAG

Bộ `pipelines/knowledge/rag-development-v2.jsonl` có 24 câu phát triển do AI soạn: 14 câu dự kiến có đáp án và 10 câu dự kiến thiếu thông tin. Đây là kiểm tra phát triển, chưa phải gold độc lập. Mỗi lượt chạy xuất `run.json`, thư mục `traces` và `human-review.csv`; trace có đầy đủ chunks, điểm, context, OUT và trang nguồn.

Mở `human-review.csv`, đọc câu hỏi, câu trả lời và nguồn; đối chiếu nội dung trong trace/PDF. Nhập tên người chấm và các cột sau bằng **0 = sai/không đạt, 1 = đạt một phần, 2 = đạt đầy đủ**:

| Cột | Người chấm cần xem |
| --- | --- |
| correctness | Có trả lời đúng và trực tiếp câu hỏi không? Từ chối một câu có đủ bằng chứng cũng bị mất điểm. |
| groundedness | Mọi phát biểu có được nội dung context hỗ trợ không? Không thêm chính sách hay thông tin ngoài nguồn. |
| citation | ID dẫn đúng đoạn, đúng nguồn và trang, thực sự hỗ trợ phát biểu không? |
| refusal | Khi thiếu bằng chứng có từ chối phù hợp, không đoán số phút/phần trăm/số điện thoại không? |

Dùng `N/A` cho tiêu chí thật sự không áp dụng, kèm ghi chú; correctness luôn phải có điểm. Không sửa cột câu hỏi, câu trả lời hoặc checksum. Hệ thống chưa tự điền điểm của người chấm. Lệnh `scripts/ai/score_rag_human_review.py` kiểm tra checksum rồi tổng hợp điểm thực đã nhập.

Để có đánh giá độc lập, nhóm cần soạn thêm câu mới chưa dùng để chỉnh prompt/truy xuất và tự xác định nguồn liên quan. Chấm lại các câu AI này không biến chúng thành tập held out độc lập.

## Duyệt KB

Người phụ trách nghiệp vụ cần xác nhận hướng dẫn đặt vé có đúng với hệ thống và chính sách nhóm muốn công bố. Người phụ trách nội dung kiểm tra nguồn sách/tóm tắt, attribution, điều kiện sử dụng và trang trích. Danh mục nguồn và file PDF đã có; quyết định duyệt hiện còn trống. Các bản chạy nghiên cứu chỉ bật draft trong bộ nhớ thử, không tự duyệt KB đang phục vụ người dùng.

## Tình trạng ban đầu

Hai lượt gán nhãn đều có 600 câu pending và 0 câu được người xác nhận tại thời điểm chuẩn bị. Báo cáo đồng thuận ban đầu có κ = null. Đó là trạng thái chưa làm, không phải kết quả đánh giá chất lượng bằng 0.
