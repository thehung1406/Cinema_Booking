# Đặt vé, chọn combo và tra đơn trong chat Cinema Booking

Khách đăng nhập có thể tìm suất, chọn và giữ ghế, thêm combo, xác nhận tạo đơn trong chat, rồi mở màn hình thanh toán hiện có. Khi quay lại chat, khách có thể tra đơn của mình và mở vé từ màn hình kết quả thanh toán.

## 1. Tìm suất và chọn ghế

- Định tuyến yêu cầu như “Đặt hai vé phim hài tối nay” sang luồng gợi ý suất. Hỏi lại nếu thiếu điều kiện để tìm. Câu hỏi hướng dẫn như “Tôi đặt vé như thế nào?” đi qua RAG.
- Thêm nút **Đặt trong chat** trên thẻ suất. Dùng API suất và ghế hiện có để hiển thị phim, rạp, giờ chiếu, giá và tình trạng ghế. Cho phép chọn từ 1 đến 20 ghế.
- Hỗ trợ `suất thứ 2`, `suất thứ hai`, `ghế A5 A6` và `suất thứ hai, ghế A5 A6`. Đối chiếu số thứ tự với danh sách suất gần nhất và tên ghế với danh sách của suất đã chọn. Báo rõ khi sai số thứ tự, trùng ghế hoặc ghế không thể chọn. Lệnh chữ cập nhật lựa chọn. Nút **Giữ ghế** gửi cả nhóm ghế trong một yêu cầu.

## 2. Giữ ghế, chọn combo và tạo đơn

Thêm ba tuyến có schema riêng dưới `/api/ai/booking`. AI Service xác thực phiên, lấy danh tính khách từ phiên và chuyển tiếp bearer token đến Booking Service theo đường dẫn cố định. Booking Service xác minh quyền sở hữu, thời hạn, tình trạng ghế và giá.

| Tuyến | Dữ liệu và hành vi |
|---|---|
| `POST /hold` | Nhận mã suất và mã ghế. Gọi `POST /seats/hold`, trả thông tin giữ ghế và thời hạn từ Booking Service. |
| `POST /release` | Nhận mã suất, mã giữ ghế và mã ghế. Gọi `POST /seats/release` khi khách bấm **Đổi ghế** hoặc **Hủy giữ ghế**. |
| `POST /checkout` | Nhận mã suất, mã giữ ghế, ghế, món, số lượng, tổng đã hiển thị và header `Idempotency-Key`. Lấy `userId` từ phiên, tạo đơn `Online` qua `POST /bookings`, trả mã đơn và hạn thanh toán. |

- Sau khi giữ ghế, tải `/api/food-items`. Khách có thể chọn bỏng, nước hoặc combo bằng nút và có thể **Bỏ qua**. Trước khi xác nhận, hiển thị phim, rạp, suất, ghế, các món, tiền vé, tiền món, tổng tiền và thời gian giữ còn lại.
- Đồng bộ ghế sau khi giữ hoặc trả ghế. Nếu đã có ghế của khách ở cùng suất, cho khách xem lại tập ghế đang giữ. Khi hết hạn hoặc xung đột, tải lại để chọn ghế. Khi giá đổi, cập nhật tổng và yêu cầu xác nhận lại.
- Chỉ gọi tool tạo đơn khi khách bấm **Xác nhận đặt vé**. Dùng `checkoutAttempt` lưu nội dung và khóa trước khi gửi. Khi mất phản hồi, gửi lại đúng nội dung và khóa, kể cả sau khi tải lại trang. Tạm khóa sửa đơn và trả ghế trong lúc chưa rõ kết quả. Khi thành công, mở `/payment/{bookingId}` để khách thanh toán. Booking Service xử lý hết hạn nếu khách bỏ dở.

## 3. Tra đơn và vé của tôi

- Thêm một tool đọc `get_my_booking` trong AI Service cho các yêu cầu như “Cho tôi xem vé vừa mua”, “Đơn #123 thế nào?” và “Tôi đã trả tiền, sao chưa thấy vé?”. Điều hướng các mẫu này trước khi gọi mô hình. Khi có mã đơn rõ ràng, dùng `GET /bookings/{booking_id}`. Khi khách hỏi đơn gần nhất hoặc chưa nêu mã, dùng `GET /bookings?limit=1` theo thứ tự của Booking Service và hiển thị mã đơn được chọn. Nếu chưa có đơn, trả thông báo tương ứng.
- Sau khi Booking Service xác nhận quyền sở hữu, đọc `GET /payment/status/{booking_id}` bằng cùng bearer token. Dùng `fulfillment_status` để phân biệt `AWAITING_PAYMENT` (chờ thanh toán), `PROCESSING` (đã ghi nhận tiền, đang cấp vé), `REQUIRES_REVIEW` (cần đối soát), `FAILED` (thanh toán thất bại) và `ISSUED` (đã phát hành). Khi đơn đã hết hạn hoặc bị hủy, hiển thị trạng thái đơn cùng trạng thái thanh toán nếu có. Khi Payment Service lỗi, hiển thị phần tóm tắt đơn và báo chưa xác minh được thanh toán.
- Sinh câu trả lời và thẻ đơn trực tiếp từ dữ liệu đã kiểm tra. Tóm tắt gồm mã đơn, phim, suất, số vé, tổng tiền và trạng thái. Chỉ hiển thị nút **Xem vé** khi đã phát hành. Nút mở `/payment-result?bookingId={booking_id}` để màn hình hiện có tự xác thực, tải vé và hiển thị QR. Thông tin chi tiết của đơn và vé chỉ xuất hiện trong lượt tra cứu hiện tại. Lịch sử tải lại hiển thị một thông báo ngắn yêu cầu tra lại để xem trạng thái mới.
- Không tìm thấy đơn và mã thuộc về tài khoản khác dùng cùng thông báo “Không tìm thấy đơn trong tài khoản của bạn”. Bổ sung `AI_PAYMENT_ORIGIN` với giá trị mặc định `http://payment-service:8088`, dùng cùng kiểm tra origin cố định như các dịch vụ hiện có. Giới hạn dữ liệu trả về và nhật ký ở các trường cần cho tra cứu. Tool này chỉ dùng API đọc của khách, không gọi API tạo thanh toán.

## Nghiệm thu

- Kiểm thử trên giao diện chat với dữ liệu cô lập. Đặt hai vé bằng lệnh chữ, chọn combo bằng nút, kiểm tra tổng, xác nhận và mở đúng trang thanh toán. Chạy thêm đường chọn suất và ghế bằng nút trên mobile và ca bỏ qua đồ ăn.
- Kiểm thử xác thực và đồng thời. Khách khác không dùng được mã giữ ghế hoặc mã đơn của nhau. Hai khách tranh cùng ghế chỉ có một bên giữ được. Ghế hết hạn và giá combo đổi đều yêu cầu xem lại. Bấm xác nhận hai lần hoặc thử lại sau khi mất phản hồi chỉ tạo một đơn.
- Kiểm thử tra đơn theo ID và đơn gần nhất, tài khoản chưa có đơn, mã không thuộc khách, từng trạng thái thanh toán và Payment Service tạm lỗi. Xác nhận trạng thái đã trả tiền nhưng đang xử lý không hiển thị nút **Xem vé**. Khi đã cấp, nút mở đúng đơn và QR chỉ xuất hiện trên trang vé đã xác thực.
- Chạy hồi quy bộ AI, Booking, combo và thanh toán. Dùng cổng thanh toán giả lập trong ca nghiệm thu đầu cuối. Triển khai qua gateway và cấu hình quyền ghi hiện có. Thay đổi này không yêu cầu migration.
