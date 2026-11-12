# Kiểm tra căn cứ của trợ lý Cinema Booking — 13/11/2026

## Thay đổi trong project

- AI Service kiểm tra dữ kiện được hỏi trước khi đưa các đoạn đã duyệt cho Qwen. Với cấu hình demo dùng Qwen, trợ lý chọn một trong ba phản hồi gồm trả lời có dẫn chứng, báo thiếu căn cứ hoặc hỏi lại. Khi Qwen gặp lỗi, trợ lý báo chưa thể kiểm tra. [Luồng xử lý trong chat](../../services/ai-service/src/ai_service/chat.py) · [Kiểm tra dữ kiện](../../services/ai-service/src/ai_service/grounding.py).
- Khi trả lời chính sách, trợ lý hiển thị đúng đoạn nguồn đã được chọn. Khi trả lời kiến thức điện ảnh, trợ lý kiểm tra mã đoạn dẫn chứng, loại câu lặp lại câu hỏi và loại số mới không xuất hiện trong đoạn dẫn. Với hai câu hỏi tách rõ, mỗi câu cần có căn cứ riêng. Giao diện hiển thị các nguồn được trích dẫn. [Mã sinh câu trả lời](../../services/ai-service/src/ai_service/llm.py).

## Đối chiếu trên demo

Gửi cùng chín câu qua đường dẫn của giao diện demo, đăng nhập tài khoản khách, với AI Service, Neo4j và Qwen3:4B đang chạy. Q14 là ca kiểm tra bổ sung để xác nhận câu hỏi đặt vé có tài liệu vẫn nhận được câu trả lời.

| Ca | Trước khi sửa | Sau khi sửa |
| --- | --- | --- |
| Q03, hỏi về dolly và bộ lọc | Lặp lại ý hỏi về dolly, trả lời được ý về tỷ lệ khung hình | Trả lời hai ý với hai nguồn. Phần dolly vẫn hiển thị tiếng Anh. |
| Q17–Q22, sáu câu thiếu dữ kiện | 6/6 có trạng thái trả lời, kèm đoạn liên quan nhưng thiếu dữ kiện được hỏi | 6/6 báo thiếu căn cứ, không đính kèm nguồn. |
| Q23–Q24, hai câu thiếu ngữ cảnh | 2/2 có trạng thái trả lời | 2/2 hỏi lại mục tiêu cảnh quay hoặc ghế, suất và bước đặt vé. |
| Q14, bỏ qua mua bỏng nước | | Trích đoạn hướng dẫn xác nhận đây là bước tùy chọn. |

Tệp ghi phản hồi qua demo trước và sau ở live-before-guard.json (`.local/knowledge/graph/evaluation-2026-11-13/live-before-guard.json`) và live-grounding-verified.json (`.local/knowledge/graph/evaluation-2026-11-13/live-grounding-verified.json`). Có thêm bản chạy lại Neo4j + Qwen (`.local/knowledge/graph/evaluation-2026-11-13/graph-generation-guard.json`) ghi hai đoạn dẫn và truy vấn Cypher cho ca dùng sách Open SUNY và bản tóm tắt Wikibooks.

## Chạy lại bộ 24 câu phát triển

Các tỷ lệ dưới đây đếm phản hồi có nội dung khẳng định. Câu hỏi lại và câu báo thiếu căn cứ được tính là không khẳng định. Nhãn dự kiến do AI soạn trong giai đoạn phát triển.

| Cấu hình | Nhóm 8 câu thiếu căn cứ hoặc mơ hồ, có khẳng định | Nhóm 16 câu dự kiến có đáp án, có khẳng định |
| --- | ---: | ---: |
| BM25 trước | 8/8 | 16/16 |
| BM25 sau | 0/8 | 7/16 |
| BM25 + graph trước | 8/8 | 16/16 |
| BM25 + graph sau | 0/8 | 9/16 |

Trợ lý dừng đúng ở các ca thiếu dữ kiện trong bộ thử. Độ bao phủ câu trả lời giảm. Ví dụ, với graph, Q04 vẫn thiếu một ý về góc nhìn qua vai trong lượt sinh, còn Q13 chưa trả lời được câu về tỷ lệ khung hình. Cần đối chiếu các đoạn đã lấy và đoạn đưa vào Qwen cho từng ca, rồi chấm độc lập độ đúng, độ đầy đủ và dẫn nguồn.

- Lượt BM25 sau khi sửa (`.local/knowledge/graph/evaluation-2026-11-13/bm25-release-guard/run.json`)
- Lượt BM25 + graph sau khi sửa (`.local/knowledge/graph/evaluation-2026-11-13/bm25-graph-release-guard/run.json`)
- [Lượt trước khi sửa và đáp án phát triển](AI_KB_RAG_PILOT_2026-11-13.md)

[Tổng hợp số liệu đi kèm mã nguồn](evidence/2026-11-13/knowledge-graph-summary.json) · [Cách tái lập các lượt kiểm tra](../AI_GRAPH_DEMO.md).
