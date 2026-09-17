# Hướng dẫn rà soát dữ liệu AI

## Nguồn và phạm vi

`Backend/ml/data/drafts/sentiment_100.jsonl` có 100 câu tiếng Việt do AI soạn, không thu thập bình luận khách hàng. `label` đang để null; `suggested_label` chỉ để tham khảo, không phải nhãn chuẩn. `chat_30.jsonl` có 30 câu nghiệp vụ và chứng cứ nháp, chưa phải 100–150 câu kiểm thử độc lập theo mục tiêu kế hoạch.

Trước khi huấn luyện, bổ sung bình luận phim từ nguồn được phép sử dụng, ghi URL/mã nguồn, ngày thu thập, điều kiện sử dụng, quyền phân phối và cờ synthetic. Giữ nội dung tự nhiên, loại dữ liệu quảng cáo, trùng và thông tin cá nhân không cần thiết. Dữ liệu mẫu hiện có không chứng minh độ bao phủ thực tế.

## Nhãn cảm xúc

| Nhãn | Quy tắc |
| --- | --- |
| positive | Kết luận tốt về phim hoặc khuyến khích xem |
| negative | Kết luận không tốt, thất vọng hoặc không khuyến khích xem |
| neutral | Mô tả thông tin về phim, không thể hiện rõ đánh giá |

Câu hỗn hợp theo kết luận tổng thể nếu rõ. Mỉa mai, phủ định và câu thiếu bối cảnh phải ghi chú để hai người đối chiếu, không ép vào neutral. Nhận xét chỉ về rạp, nhân viên, thanh toán hoặc dịch vụ phải tách khỏi tập phim. Không suy ra nhãn từ số sao hoặc trạng thái mua vé.

Hai thành viên gán độc lập ít nhất 20%: điền `label`/`reviewer` và `second_label`/`second_reviewer`. Khi bất đồng, ghi lý do và nhãn thống nhất trong `annotation_note`. Đánh dấu tags như negation, slang, sarcasm, mixed, no-diacritics, wrong-target. Chỉ đổi `review_status=approved` sau rà soát. Các trường source/license/group_id/reviewer bắt buộc; không đổi hàng loạt cờ duyệt để bỏ qua công việc này.

`group_id` dùng chung cho cùng phim/nguồn/nhóm diễn đạt lại mà cần giữ ở một tập. Script bổ sung gom gần trùng bằng SequenceMatcher >=0.88; đây là kiểm tra văn bản cơ sở, chưa phát hiện đầy đủ trùng ngữ nghĩa. Người rà soát phải nhóm các câu diễn đạt lại thủ công. Dữ liệu lớn nên tách theo phim/thời gian nếu phù hợp.

## Hội thoại và tài liệu

Mỗi dòng hội thoại cần `question`, `evidence` (các mục có id/text/title), `evidence_ids` đúng, `group_id` theo nhóm tình huống, nguồn và người duyệt. Những câu giá/lịch/ghế trong bản nháp chưa có snapshot thực nên chưa đủ để làm mục tiêu huấn luyện. Bổ sung snapshot đã loại thông tin cá nhân, thời điểm tra cứu, context cần có và kết quả đúng. Mã chứng cứ rỗng chỉ đúng khi thực sự thiếu căn cứ, ngoài phạm vi hoặc phải hỏi lại.

Mục tiêu LoRA hiện tại là chọn chứng cứ từ hội thoại; phần hỏi lại/định tuyến/công cụ do backend thực hiện. Nếu mở rộng sang mô hình tự định tuyến hay sinh lời đáp, cần thay hợp đồng, bổ sung dữ liệu và đánh giá riêng trước khi triển khai.

Tài liệu `knowledge.json` mặc định `approved=false`. Người phụ trách nghiệp vụ đối chiếu nội dung với code và chính sách đã công bố, thêm `reviewer`, ngày hiệu lực, phiên bản rồi duyệt từng tài liệu. Không dùng mẫu hội thoại, bình luận hoặc giá/ghế đã cũ làm chính sách.

## Chia tập

Chia sau khi làm sạch và giải quyết bất đồng. `python -m ml.data ...` phân nhóm 70/15/15 với seed 42, lưu checksum. Các thành viên không đọc tập test để chọn tham số. Tập test phải có con người kiểm tra, độc lập theo nhóm, đa dạng câu khó. Chỉ chạy đánh giá cuối sau khi đã chốt model/threshold bằng validation. Bộ nháp và metric trên dữ liệu giả không được báo cáo là chất lượng sản phẩm.
