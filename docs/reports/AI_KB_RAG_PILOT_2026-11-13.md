# Kết quả thử KB và RAG trên 24 câu mới

Ngày 13/11/2026. Bộ thử do AI soạn và giữ cố định trước khi chạy. Đáp án là dự thảo đối chiếu nguồn, phiếu chấm người đang trống. Có 16 câu dự kiến trả lời được, 6 câu thiếu dữ kiện và 2 câu mơ hồ.

## Cách chạy

So sánh BM25 và BM25 + đồ thị Neo4j trên cùng ba tài liệu, cùng Qwen3:4b và tối đa ba đoạn truy xuất. Corpus được bật tạm trong môi trường kiểm thử. Lượt sinh này đo mô hình với đoạn nguồn, gồm cả câu chính sách. AI Service khi chạy chatbot thật có thể dùng luồng riêng theo phạm vi.

[Danh mục nguồn](../../pipelines/knowledge/sources.json) · [Bộ câu hỏi và mốc dẫn chứng dạng JSONL](../../pipelines/knowledge/rag-development-v3.jsonl) · [Hướng dẫn tái lập](../AI_GRAPH_DEMO.md).

## Số đo

| Chỉ số | BM25 | BM25 + graph |
| --- | ---: | ---: |
| Recall@3 trên 16 câu có đáp án | 0,625 | 0,719 |
| MRR@3 trên 16 câu có đáp án | 0,573 | 0,594 |
| nDCG@3 trên 16 câu có đáp án | 0,522 | 0,577 |
| Độ trễ truy xuất trung vị (ms) | 26,4 | 46,2 |
| Lượt sinh hoàn tất | 24/24 | 24/24 |
| Có câu trả lời ở nhóm có đáp án | 16/16 | 16/16 |
| Có câu trả lời ở nhóm thiếu dữ kiện hoặc mơ hồ | 8/8 | 8/8 |

Tỷ lệ có văn bản đầu ra được tính tự động. Điểm đúng, đủ căn cứ và dẫn nguồn cần đọc từng câu. Độ trễ là số đo của lượt chạy trên máy demo.

| Nhóm có đáp án | Số câu | Recall@3 BM25 | Recall@3 BM25 + graph |
| --- | ---: | ---: | ---: |
| Cần hai nguồn | 4 | 0,500 | 0,625 |
| Một nguồn | 6 | 0,667 | 0,667 |
| Anh–Việt | 3 | 0,333 | 0,667 |
| Hướng dẫn đặt vé | 3 | 1,000 | 1,000 |

## Ca đã đối chiếu

- **Q12.** Thêm graph đưa đoạn tóm tắt tiếng Việt vào nhóm truy xuất đầu. Qwen trả lời đúng hai phương tiện ghi hình là phim và kỹ thuật số. BM25 trả đoạn sách về định nghĩa và film stock, thiếu phần ghi hình kỹ thuật số.
- **Q03.** Thêm graph tìm được cả đoạn sách về dolly và đoạn tóm tắt về bộ lọc, tỷ lệ khung hình. Câu sinh trả lời đúng phần tỷ lệ khung hình, còn phần dolly lặp lại câu hỏi và bỏ sót ý làm lộ một chi tiết trong cảnh.
- **Q17 và Q20.** Hai cấu hình lấy đoạn về quy trình đặt vé hoặc danh sách kỹ thuật quay nhưng bỏ ngỏ số vé tối đa và tải trọng slider. Đây là ca có trích dẫn nhưng đoạn nguồn thiếu dữ kiện cần hỏi.
- **Q23.** Câu hỏi thiếu mục tiêu cảnh quay. Lượt BM25 gợi ý cận cảnh cho cảnh cảm xúc khi người dùng chưa nêu ý muốn thể hiện.

## Kiểm tra đồ thị

Đọc bản phát hành thực trong Neo4j và đối chiếu với tệp nhập. Có **5/5 phát biểu** khớp vị trí dẫn chứng và phiên bản nguồn, trên 3 khái niệm. Tìm thấy 0 đường dẫn bằng chứng trùng trong bản này. Đây là kiểm tra cấu trúc và vị trí nguồn trên phần graph hiện có.

## Đáp án dự thảo và nguồn đối chiếu

| Mã | Nhóm | Câu hỏi | Ý cần có | Nguồn |
| --- | --- | --- | --- | --- |
| Q01 | Cần hai nguồn | Nếu muốn lia máy tại chỗ thì pan hoạt động thế nào, và bản tóm tắt tiếng Việt nhắc tới dụng cụ nào cùng với slider? | Pan xoay máy ngang trong khi vị trí máy giữ nguyên. Bản tóm tắt liệt kê cần cẩu cùng slider. | Open SUNY, trang PDF 63 / Wikibooks (bản tóm tắt Việt), đoạn «slider và cần cẩu» |
| Q02 | Cần hai nguồn | Trong cinematography, người phụ trách hình ảnh quản lý các ê-kíp kỹ thuật nào theo sách, và bản tóm tắt nêu hai phương tiện ghi hình nào? | Theo sách, cinematographer phụ trách các ê-kíp máy quay, ánh sáng và điện. Bản tóm tắt nêu ghi hình bằng phim hoặc kỹ thuật số. | Open SUNY, trang PDF 62 / Wikibooks (bản tóm tắt Việt), đoạn «bằng phim hoặc kỹ thuật số» |
| Q03 | Cần hai nguồn | Ngoài chuyện máy quay di chuyển, sách dùng dolly để làm lộ điều gì trong một cảnh? Bản tóm tắt liệt kê yếu tố nào cùng với bộ lọc? | Dolly có thể làm lộ một chi tiết hoặc yếu tố trong cảnh. Bản tóm tắt đề cập tỷ lệ khung hình cùng với bộ lọc. | Open SUNY, trang PDF 63 / Wikibooks (bản tóm tắt Việt), đoạn «Bộ lọc và tỷ lệ khung hình» |
| Q04 | Cần hai nguồn | Nếu dùng over-the-shoulder, khán giả nhìn từ vị trí nào theo sách? Khi thêm chuyển động máy quay, bản tóm tắt nói có thể góp phần thể hiện điều gì? | Khán giả nhìn qua vai một nhân vật, theo góc nhìn của nhân vật đó. Bản tóm tắt nói chuyển động máy quay có thể góp phần thể hiện cảm xúc. | Open SUNY, trang PDF 64 / Wikibooks (bản tóm tắt Việt), đoạn «góp phần thể hiện cảm xúc» |
| Q05 | Một nguồn | Pan và tilt khác nhau như thế nào khi chân máy giữ nguyên vị trí? | Pan xoay máy ngang sang hai bên. Tilt hướng máy lên hoặc xuống. Cả hai giữ vị trí máy quay. | Open SUNY, trang PDF 63 |
| Q06 | Một nguồn | Tôi muốn nhân vật trông nhỏ bé và yếu thế. Sách nói góc máy nào thường tạo được cảm giác đó? | Dùng góc máy cao, đặt máy trên tầm mắt và hướng nhìn xuống để nhân vật trông nhỏ bé hoặc yếu hơn. | Open SUNY, trang PDF 62 |
| Q07 | Một nguồn | Trong đoạn từ vựng góc quay, cỡ cảnh nào lấy nhân vật từ đầu đến chân? | Wide shot, tức cảnh rộng hoặc toàn cảnh, cho thấy nhân vật từ đầu đến chân. | Open SUNY, trang PDF 62 |
| Q08 | Một nguồn | Trong sơ đồ chiếu sáng, key light và fill light làm hai việc khác nhau thế nào? | Key light cung cấp ánh sáng chính cho đối tượng hoặc khu vực. Fill light bù vào các vùng bóng, và tăng fill làm giảm bóng tối trong cảnh. | Open SUNY, trang PDF 66 |
| Q09 | Một nguồn | Trong point-of-view shot, khán giả có thấy vai và một bên đầu của nhân vật ở tiền cảnh không? | Không. Point-of-view shot cho thấy điều nhân vật nhìn thấy, theo góc nhìn ngôi thứ nhất và không có vai hoặc bên đầu ở tiền cảnh. | Open SUNY, trang PDF 64 |
| Q10 | Một nguồn | Ở mục phim xem thêm, sách lấy Chinatown làm ví dụ về cách dùng yếu tố hình ảnh nào? | Chinatown được nêu như ví dụ về cách dùng ánh sáng và bóng tối trong neo-noir. | Open SUNY, trang PDF 67 |
| Q11 | Anh–Việt | In the book, what is the shot that frames one person from the waist up called? | Sách gọi là medium shot hoặc mid shot, tức cảnh trung lấy nhân vật từ thắt lưng trở lên. | Open SUNY, trang PDF 63 |
| Q12 | Anh–Việt | Does the Vietnamese cinematography summary mention both film and digital capture? | Có. Bản tóm tắt nêu rằng cinematography tạo hình ảnh chuyển động bằng phim hoặc bằng kỹ thuật số. | Wikibooks (bản tóm tắt Việt), đoạn «bằng phim hoặc kỹ thuật số» |
| Q13 | Anh–Việt | According to the Vietnamese summary, what framing-related topic is mentioned alongside filters? | Bản tóm tắt đề cập tỷ lệ khung hình, tiếng Anh là aspect ratio, cùng với bộ lọc. | Wikibooks (bản tóm tắt Việt), đoạn «Bộ lọc và tỷ lệ khung hình» |
| Q14 | Hướng dẫn đặt vé | Sau khi chọn ghế, nếu không mua bỏng nước thì tôi có thể tiếp tục xem lại đơn và thanh toán không? | Có. Bỏng và nước là lựa chọn tùy ý. Sau bước chọn ghế, khách xem lại đơn rồi tiếp tục thanh toán. | Hướng dẫn đặt vé, đoạn «bỏng, nước nếu muốn» |
| Q15 | Hướng dẫn đặt vé | Nếu thanh toán gặp trục trặc, tôi có thể xem trạng thái ở đâu trước khi liên hệ hỗ trợ? | Kiểm tra trạng thái ở màn hình thanh toán. Có thể liên hệ bộ phận hỗ trợ nếu vẫn gặp vấn đề. | Hướng dẫn đặt vé, đoạn «xem trạng thái tại màn hình thanh toán» |
| Q16 | Hướng dẫn đặt vé | Thành phần nào của Cinema Booking được dùng để kiểm tra lại tình trạng ghế lúc tôi chọn ghế? | Hệ thống kiểm tra lại tình trạng ghế qua Booking Service lúc khách chọn ghế. | Hướng dẫn đặt vé, đoạn «kiểm tra lại tình trạng ghế với Booking Service» |
| Q17 | Thiếu căn cứ | Một đơn đặt trực tuyến được mua tối đa bao nhiêu vé? | Nêu rằng hướng dẫn hiện có không công bố số vé tối đa mỗi đơn. Không đoán con số. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q18 | Thiếu căn cứ | Sau khi đã xác nhận đơn, hệ thống có cho đổi phương thức thanh toán không? | Nêu rằng hướng dẫn chưa xác nhận khả năng đổi phương thức sau khi xác nhận đơn. Không hứa thực hiện được. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q19 | Thiếu căn cứ | Cinema Booking có gửi hóa đơn điện tử qua email sau khi thanh toán không? | Nêu rằng KB chưa có quy định về hóa đơn điện tử qua email. Không đánh đồng vé với hóa đơn. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q20 | Thiếu căn cứ | Slider trong bản tóm tắt chịu tải tối đa bao nhiêu kg? | Bản tóm tắt chỉ liệt kê slider và không có thông số tải trọng. Không đưa ra số kg. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q21 | Thiếu căn cứ | Sách có ghi khi thực hiện pan nên xoay máy chính xác bao nhiêu độ mỗi giây không? | Sách giải thích cách pan nhưng không đưa ra tốc độ góc chính xác trong phần liên quan. Không đoán thông số. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q22 | Thiếu căn cứ | Sách có chỉ định một giá trị ISO bắt buộc cho mọi cảnh quay trong rạp không? | Không đủ căn cứ để xác nhận một ISO bắt buộc chung. Không gán một giá trị ISO cụ thể cho sách. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q23 | Mơ hồ | Tôi nên chọn góc máy nào cho cảnh này? | Hỏi thêm mục tiêu, tình huống hoặc hiệu ứng mong muốn của cảnh trước khi đề xuất một góc cụ thể. | Thiếu dữ kiện hoặc ngữ cảnh |
| Q24 | Mơ hồ | Ghế đó của tôi chưa? | Hỏi người dùng đang nói tới ghế/suất nào và đã làm đến bước nào. Không xác nhận quyền giữ ghế từ câu hỏi thiếu ngữ cảnh. | Thiếu dữ kiện hoặc ngữ cảnh |

## Phiếu chấm và dữ liệu lần chạy

- Phiếu BM25 (`.local/knowledge/graph/evaluation-2026-11-13/bm25/human-review.csv`)
- Phiếu BM25 + graph (`.local/knowledge/graph/evaluation-2026-11-13/bm25-graph/human-review.csv`)
- Số liệu và các đoạn truy xuất (`.local/knowledge/graph/evaluation-2026-11-13/retrieval.json`)
- Kết quả đối chiếu graph (`.local/knowledge/graph/evaluation-2026-11-13/graph-anchors.json`)

Khi chấm, đối chiếu với đáp án dự thảo và đoạn nguồn, rồi điền người chấm cùng điểm 0–2 vào các cột được quy định. Các cột câu hỏi, câu trả lời và mã kiểm tra trace được giữ để công cụ đối soát.

[Tổng hợp số liệu đi kèm mã nguồn](evidence/2026-11-13/knowledge-graph-summary.json) · [Cách tái lập các lượt kiểm tra](../AI_GRAPH_DEMO.md).
