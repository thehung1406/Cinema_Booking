# Rà bảy câu bị bỏ sót trong RAG — 13/11/2026

## Truy xuất và sinh câu trả lời

Đối chiếu cùng bộ 24 câu phát triển, cùng tài liệu, Qwen3:4B và ngân sách tối đa ba đoạn truy xuất mỗi lượt. Hai cấu hình sau sửa cùng dùng bước mở rộng từ khóa Anh–Việt và tách các ý hỏi rõ ràng. Điểm Recall@3 đo mức tìm được các đoạn nguồn dự kiến trong 16 câu có đáp án. Tỷ lệ có câu trả lời đo trạng thái phản hồi.

| Cấu hình | Recall@3 trước → sau | Có câu trả lời trong 16 câu có đáp án, trước → sau | Có khẳng định trong 8 câu thiếu dữ kiện hoặc mơ hồ, trước → sau |
| --- | ---: | ---: | ---: |
| BM25 | 0,625 → 0,906 | 7/16 → 14/16 | 0/8 → 0/8 |
| BM25 + Neo4j | 0,719 → 1,000 | 9/16 → 16/16 | 0/8 → 0/8 |

Sau sửa, BM25 vẫn bỏ sót Q03 và Q12. Graph bổ sung căn cứ giúp cả hai câu có câu trả lời. Trạng thái có câu trả lời chưa chấm mức đúng hay đầy đủ. Ví dụ Q08 vẫn nêu được tác dụng của key light nhưng chưa giải thích fill light bù sáng vào vùng tối. Một số đáp án vẫn dùng tiếng Anh của nguồn gốc.

## Đối chiếu bảy câu với nguồn

| Ca | Nguyên nhân ở lượt trước | Đối chiếu BM25 + Neo4j sau sửa |
| --- | --- | --- |
| Q01 | Chỉ lấy được ý về slider trong bản tóm tắt. | Tìm trang 63 cho định nghĩa pan và bản tóm tắt cho cần cẩu. Câu trả lời nêu cả hai ý. |
| Q02 | Lấy định nghĩa cinematography, thiếu đoạn sách về ê-kíp. | Tìm đúng đoạn trang 62 và bản tóm tắt. Câu trả lời nêu các ê-kíp máy quay, ánh sáng, điện và hai dạng ghi hình là phim và kỹ thuật số. |
| Q04 | Graph lấy ví dụ dolly liên quan chuyển động máy quay, trong khi ý thứ nhất hỏi over-the-shoulder. | Tìm trang 64 và đoạn về cảm xúc. Câu trả lời nói khán giả thấy vai, mặt và cổ của nhân vật, nhưng diễn đạt chưa trực tiếp vị trí nhìn qua vai. |
| Q06 | Không tìm được đoạn tiếng Anh về hiệu ứng góc máy cao từ mô tả tiếng Việt. | Tìm và trả lời đúng high angle, máy ở trên tầm mắt nhìn xuống, tạo cảm giác nhân vật nhỏ bé và yếu thế. |
| Q07 | Cụm tiếng Việt “từ đầu đến chân” không khớp cụm tiếng Anh trong sách. | Tìm và trả lời đúng wide shot, dẫn trang 62. |
| Q10 | Tên *Chinatown* và câu giải thích về ánh sáng, bóng tối bị tách thành hai đoạn căn cứ. | Dẫn đoạn liền nhau có tên phim và phần giải thích về ánh sáng, bóng tối trong neo-noir. |
| Q13 | Từ khóa tiếng Anh về khung hình và bộ lọc không khớp bản tóm tắt tiếng Việt. | Tìm bản tóm tắt và trả lời đúng tỷ lệ khung hình. |

Thay đổi nằm ở [truy xuất tri thức](../../services/ai-service/src/ai_service/knowledge_retrieval.py), [tạo đoạn căn cứ](../../services/ai-service/src/ai_service/grounding.py) và [sinh câu trả lời](../../services/ai-service/src/ai_service/llm.py). Từ tương đương hỗ trợ xếp hạng. Tài liệu đã duyệt vẫn là căn cứ của câu trả lời. Khi một câu hỏi yêu cầu rõ sách hoặc bản tóm tắt, bước sinh chỉ xét đoạn từ loại tài liệu đó.

## Kiểm chứng Knowledge Graph

- Chạy Neo4j với 1, 2 và 3 nguồn thực, lần lượt có 2, 4 và 5 phát biểu đã nạp. Không có cạnh phát biểu trùng trong các lượt này. Nguồn thứ tư mô phỏng kích hoạt cả ba trạng thái mâu thuẫn, alias đa nghĩa và bằng chứng chờ xác minh. Kết quả bốn lượt nhập (`.local/knowledge/graph/evaluation-2026-11-13/graph-source-quality-final.json`).
- Chạy API với kho tài liệu thử riêng và Neo4j thật. Bản nháp và lần công bố lỗi giữ nguyên bản đang phục vụ. Công bố thành công làm truy vấn trả bản mới. Khôi phục đưa truy vấn về bản cũ. Thu hồi sách loại sách khỏi danh sách nguồn truy xuất. Trace vòng đời và ca truy xuất hai nguồn (`.local/knowledge/graph/evaluation-2026-11-13/graph-coverage-and-update-final.json`).

## Tệp kết quả

- BM25 (`.local/knowledge/graph/evaluation-2026-11-13/bm25-coverage-final/run.json`) · BM25 + Neo4j (`.local/knowledge/graph/evaluation-2026-11-13/bm25-graph-coverage-final/run.json`) · Chạy qua API của demo (`.local/knowledge/graph/evaluation-2026-11-13/live-coverage-final.json`).
- Phiếu chấm BM25 (`.local/knowledge/graph/evaluation-2026-11-13/bm25-coverage-final/human-review.csv`) · Phiếu chấm BM25 + Neo4j (`.local/knowledge/graph/evaluation-2026-11-13/bm25-graph-coverage-final/human-review.csv`).

Bộ 24 câu đã được dùng để sửa hệ thống. Lượt đánh giá độc lập cần câu hỏi mới do người soạn và xác nhận nguồn trước khi chạy, rồi chấm mức đúng, đủ và dẫn nguồn trên các câu trả lời đã lưu. [Hướng dẫn chấm RAG](../AI_HUMAN_REVIEW.md#chấm-câu-trả-lời-rag).

[Tổng hợp số liệu đi kèm mã nguồn](evidence/2026-11-13/knowledge-graph-summary.json) · [Cách tái lập các lượt kiểm tra](../AI_GRAPH_DEMO.md).
