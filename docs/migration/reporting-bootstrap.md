# Thiết kế bootstrap Reporting và lưu sự kiện chuyển tiếp

## Đã có trong đợt M1–M2

- Public vhost có durable queue `reporting.bootstrap.v1` bind `cinema.events.v1` với `#`. Publisher mandatory không được đánh dấu thành công nếu không có queue nhận.
- Mỗi xác nhận mới trong events mode ghi `BookingConfirmed.v1` cùng transaction với đơn/ghế/vé. Event có payment ID, booking ID, film/showtime/theater ID, ngày chiếu, số ghế, tiền dạng decimal string và tên phim/rạp.
- Private email event ở vhost khác; không đưa contact hoặc ticket secret vào queue báo cáo.
- Source inventory và các contract đã xuất trong `contracts/` phục vụ so sánh trước khi đổi caller.

## Dữ liệu snapshot cần xây trước M10

| Owner | Dữ liệu tối thiểu cho báo cáo | Khóa upsert |
| --- | --- | --- |
| Booking | Đơn, giá vé/món snapshot, trạng thái xác nhận/hết hạn, vé và check-in | booking ID, ticket ID, version |
| Payment | Attempt/provider result, amount/currency, đối soát | payment ID, version; không cộng doanh thu theo số attempt |
| Cinema | Suất/phòng/rạp, ghế ACTIVE và cấu hình bán theo version | showtime ID + sales version, seat ID |
| Catalog | Phim, phân loại, thực đơn/dimension công khai | entity ID + version |
| Review | Review moderation/deletion/content version, sentiment đúng phiên bản | review ID + content version/model version |

Snapshot không lấy mật khẩu, token, email/điện thoại hoặc nội dung hội thoại. Giữ đúng semantics báo cáo hiện tại: doanh thu gồm món, chỉ PAID + CONFIRMED với payment hợp lệ; mẫu số sử dụng ghế hiện là ghế ACTIVE theo suất trong phạm vi, không tự đổi sang sức chứa lịch sử.

## Trình tự chuyển

1. Trước bootstrap thật, hoàn thiện các emitter còn thiếu: BookingCreated/Expired, TicketCheckedIn, thay đổi catalog/cinema/review/sentiment. Version phải được tăng và lưu trong cùng transaction với event ở từng owner.
2. Giữ queue bootstrap và outbox chưa tiêu thụ trong toàn cửa sổ; không ACK hoặc xóa chỉ để giảm backlog. Theo dõi dung lượng và thời hạn giữ.
3. Chụp snapshot nhất quán tại từng owner, kèm version của từng entity và manifest kiểm tra. Không có snapshot transaction chung cho tất cả database.
4. Nạp projection bằng upsert theo business key/version, rồi replay phần sự kiện giữ lại có khoảng chồng với snapshot. Cùng ID/version xử lý lặp không cộng doanh thu lần nữa; event cũ không ghi đè trạng thái mới.
5. Đối soát booking/payment/ticket và các tổng theo ngày/phim/rạp; xử lý khoảng thiếu version trước đổi `/admin/reports`. Chỉ ACK queue khi projection + inbox/checkpoint commit.

Không dùng `MAX(created_at)` hoặc event UUID như mốc commit: giao dịch chậm có thể commit sau nhưng mang timestamp cũ. Không diễn giải channel delivery tag RabbitMQ thành cursor bền vững xuyên kết nối.

## Giới hạn hiện tại

Queue hiện mới có confirmation events từ thời điểm bật events mode, không có toàn bộ lịch sử và các thay đổi check-in/review. Chưa có Reporting Service hoặc công cụ xuất/nạp snapshot dữ liệu thật. Đây là thiết kế và cơ chế lưu event chuyển tiếp; chỉ chuyển báo cáo khi các bước trên được thực hiện và kiểm chứng ở M10.
