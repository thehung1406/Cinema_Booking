# Bằng chứng AI ngày 04 tháng 11 năm 2026

Các file này là kết quả thực đã xuất để đi theo repository. 18 run baseline thuộc ma trận chính 72 run; sáu run ablation là nghiên cứu bổ sung trên cùng Bank, không tăng số dataset hay tự đổi thành 24/72.

RAG có 24 câu do AI soạn và đã dùng để chỉnh hệ thống. Giữ cả lượt lỗi và các lần sửa; không gọi đây là gold độc lập. Trước guard có 6/10 câu thiếu thông tin vẫn được trả lời; bản cuối từ chối 10/10 và trả lời 14/14 câu dự kiến có đáp án. Đây chỉ là tỷ lệ trả lời/từ chối theo kỳ vọng phát triển, chưa phải accuracy hoặc chấm groundedness. Kiểm tra source span đúng không chứng minh diễn giải đúng nghĩa.

rag-generation-final/human-review.csv còn trống điểm và tên người chấm. Đường dẫn trace_file trong run.json tương đối với thư mục đó để đọc được sau khi pull. Các đường dẫn máy xuất hiện trong metadata huấn luyện là thông tin môi trường đã đo, không phải cấu hình cần sao chép.

integration/portable-stack.json kiểm tra bản copy chỉ gồm source Git nhìn thấy, DB/credential mới và model CPU Docker tự tải; chat thực trả card từ owner API. Chưa kiểm thử trên nhiều máy vật lý hay mọi hệ điều hành. Không dùng dữ liệu/tài khoản/thanh toán thật. Review model smoke dùng Bank artifact với Bank validation trong schema DB và RabbitMQ test, không chứng minh chất lượng cảm xúc phim.

Nguồn sách trích trong KB/context: John Reich, Exploring Movie Construction and Production, Open SUNY 2017, CC BY NC SA 4.0 trừ phần ghi chú riêng. Bản tóm tắt Cinematography theo Wikibooks contributors, CC BY SA 4.0, oldid 3335736. Giữ attribution và điều kiện nguồn trong từng metadata; không thay giấy phép của nguồn gốc. PDF tải lại bằng scripts/ai/fetch_knowledge_sources.py theo URL/SHA đã khóa.

Không có raw review, model weights, private env, token hay dump DB. SHA256SUMS.json kiểm tra nội dung snapshot. Phần thiếu và các quyết định cần người thật ở docs/AI_GVHD_CHECKLIST.md và docs/AI_HUMAN_REVIEW.md.
