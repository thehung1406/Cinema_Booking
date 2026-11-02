# ADR 0004 — Chính sách nhất quán để tách các miền còn lại

Ngày: 02/11/2026. Trạng thái: quyết định thiết kế cho M6–M10; các workflow tương ứng chưa triển khai ở đợt Notification.

- **Owner dữ liệu:** giữ ánh xạ 28 bảng trong tài liệu cấu trúc; từng bảng có một writer. Admin chia về owner, reporting dùng projection. Không duy trì FK/ORM xuyên database sau cutover.
- **Quote đồ ăn:** Catalog cấp quote có ID, version, snapshot giá/thành phần và deadline. Giữ giá đến khi quote hết hạn. Booking lưu snapshot và tính tổng bằng Decimal; quote không kéo dài hold ghế.
- **Suất/ghế/giá:** Cinema công bố `sales_version` bất biến; Booking nhận đủ dữ liệu và ACK trước mở bán. Sửa lịch/ghế/phòng đang bán đi qua đóng hold mới, xử lý đơn/hold hiện hữu, rồi công bố phiên bản mới. Không quyết định bán từ projection trễ.
- **Đơn và vé:** giữ availability, booking và issue/check-in ticket cùng Booking Service. Khi chưa hoàn thiện saga vẫn giữ payment legacy trong cùng deployment/transaction tạm.
- **Tách Payment:** checkout snapshot có amount/currency/version/deadline; Payment ghi provider fact và outbox, Booking xác nhận ghế/đơn/vé local với inbox. Callback/event lặp phải idempotent.
- **Thu tiền nhưng không có vé:** không ghi đè PAID thành FAILED. Không cấp lại ghế đã bán; tạo hồ sơ đối soát/hoàn tiền. Giai đoạn đầu xử lý hoàn thủ công, chỉ tự động khi có API refund đã kiểm chứng.
- **Reporting:** snapshot/replay có business key và aggregate version, không dùng max timestamp/event UUID làm checkpoint commit-safe. Giữ cách tính doanh thu/ngày chiếu/giờ Việt Nam hiện tại; thay semantics là thay đổi sản phẩm riêng.

Các ngưỡng tải/latency mục tiêu của M0.7 còn cần đo/chốt trước khi đổi transaction booking/payment. ADR này không xác nhận các workflow M6–M10 đã vận hành.
