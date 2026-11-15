# Function Calling và vòng lặp ReAct cho Cinema Booking

## Quyết định

Ưu tiên hoàn tất [đặt vé và tra đơn trong chat](2026-11-15-chat-booking.md). Sau đó thử **native function calling và vòng lặp ReAct** trên một nhóm câu hỏi tra cứu cần nhiều bước. Để **LangGraph** cho giai đoạn có tiêu chí nghiệm thu bắt buộc dùng framework hoặc có nhu cầu thực tế lưu tiến trình và tiếp tục một workflow đang dở. AI Service hiện có planner trả JSON, tool tra cứu có kiểm tra tham số và trạng thái hội thoại. Các phần đó đủ để thử vòng lặp ngắn bằng Python.

| Hạng mục | Vai trò trong dự án |
|---|---|
| Function calling | Mô hình đề xuất hàm và tham số qua cơ chế `tools` của API. AI Service xác thực và thực thi. Adapter Responses API và Ollama chuyển lời gọi về cùng định dạng cho vòng lặp. JSON có cấu trúc là phương án dự phòng nếu endpoint từ chối hoặc model trả về thiếu lời gọi tool. |
| Agent Loop theo ReAct | Mô hình nhận kết quả từng tool rồi quyết định bước đọc tiếp theo. Giới hạn trong một lượt chat và dùng dữ kiện từ Booking Service để hiển thị kết quả. |
| LangGraph | Có thể điều phối vòng lặp bằng các node `decide`, `execute` và `respond` khi cần framework. Dùng lại cùng tool, ràng buộc và bộ kiểm thử nếu chuyển sang `StateGraph`. |

### Cách điều phối vòng lặp

| Phương án | Ai quản lý các bước | Khi phù hợp |
|---|---|---|
| Vòng lặp Python trong AI Service | Hàm chạy agent giữ kết quả tool trong bộ nhớ của request, gọi mô hình ở bước tiếp và kiểm tra deadline, số bước, điều kiện dừng. | Tra cứu ngắn trong một lượt chat, tối đa ba tool. |
| LangGraph | `StateGraph` điều phối các node dùng chung state và đi theo cạnh có điều kiện. Có thể cấu hình checkpointer và interrupt để tạm dừng, lưu tiến trình và tiếp tục sau. | Có yêu cầu đồ án dùng LangGraph hoặc workflow phải tiếp tục qua nhiều lượt hay sau khi tiến trình gián đoạn. |

Hai phương án dùng cùng API mô hình và API nghiệp vụ. Với cùng model, prompt và tool, có thể chạy cùng ca demo theo cùng hợp đồng trả lời.

## Thử nghiệm đề xuất

Câu demo “Tìm các suất tối nay của phim X tại rạp Y. Nếu suất đầu còn đủ hai ghế thì báo giá từng loại. Nếu không đủ thì kiểm tra suất tiếp theo.” Dùng hai bộ dữ liệu giống nhau về lịch và khác nhau về số ghế trống ở suất đầu. Một lượt phải đi đến tool tra giá, lượt kia phải kiểm tra ghế suất kế.

- Giới hạn thử nghiệm ở câu tra cứu nhiều bước có yêu cầu kiểm tra theo kết quả, với phim, rạp và ngày đã xác định qua bộ phân giải hiện tại. Chọn nhánh thử nghiệm trước khi gọi planner JSON để tránh chạy hai planner trên luồng thành công. Câu hỏi một bước, RAG và các thao tác xác nhận đặt vé tiếp tục vào tuyến tương ứng của chúng.
- Dùng endpoint và model đang cấu hình. Gửi danh sách `tools` và chạy tuần tự một tool mỗi bước. Công bố ba tool đọc `get_showtimes`, `get_seat_availability`, `get_ticket_prices`. Dùng ngữ cảnh đã kiểm tra cho việc tìm suất. Hai tool theo mã suất chỉ nhận ID mà backend đã trả về trong lượt hiện tại.
- Gửi lại kết quả đã lọc theo giao thức của provider. Responses API dùng `function_call_output` với `call_id` và `store: false`. Ollama dùng message `tool` với `tool_name`. Nếu chuyển sang JSON có cấu trúc, truyền các kết quả đã nhận để model chọn bước tiếp theo. Dùng thứ tự suất từ Booking Service, dữ liệu số ghế từ API đếm ghế và giá từ tool hiện có. Dựng câu trả lời từ dữ liệu đã xác minh, kèm thời điểm tra cứu khi hiển thị ghế trống.
- Tối đa ba lần gọi tool và dùng deadline 16 giây hiện có cho cả đọc dữ liệu và gọi mô hình trong nhánh thử nghiệm. Chặn tool lạ, tham số ngoài schema và lời gọi lặp với cùng tham số. Nếu không thể hoàn tất, hiển thị phần đã tra được và nêu phần còn thiếu. Khi chưa có dữ kiện và còn thời gian, dùng luồng tra cứu hiện có. Giữ ghế, tạo đơn, thanh toán và dữ liệu đơn cá nhân nằm ngoài danh sách tool của vòng lặp này.

## Cách quyết định có đưa vào chatbot

1. **Kiểm tra khả năng chạy thật.** Dùng endpoint và model đã cấu hình để xác minh native Function Calling. Với model chỉ hỗ trợ JSON có cấu trúc, xác minh vòng lặp chọn tool dựa trên kết quả thật của bước trước. Ghi tên tool, giao thức, thời gian và lý do dừng để đối chiếu.
2. **Kiểm thử nhánh.** Cả hai bộ dữ liệu demo phải dẫn đến đúng tool tiếp theo. Chạy thêm ca suất tiếp theo không còn, ID ngoài danh sách, tool lạ, lặp tool, timeout và LLM API không khả dụng. Kiểm tra hợp đồng trả lời hiện có và chạy lại ca RAG, tra suất một bước và đặt vé.
3. **So với luồng hiện tại.** Chạy cùng các câu tiếng Việt với dữ liệu cố định. Ghi kết quả hoàn tất, số lượt gọi mô hình và thời gian phản hồi. Chỉ bật cho nhóm câu thử nghiệm khi mô hình thực tế chọn đúng cả hai nhánh, dữ kiện hiển thị khớp kết quả tool, và phản hồi nằm trong deadline. Nếu chưa đạt, giữ luồng hiện tại cho nhóm câu đó và ghi rõ điểm thất bại của thử nghiệm.

### Tài liệu đối chiếu

- [Function calling trong Responses API](https://developers.openai.com/api/docs/guides/function-calling)
- [Tool calling trong Ollama](https://docs.ollama.com/capabilities/tool-calling)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
