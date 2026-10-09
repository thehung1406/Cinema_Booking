# Cinema Booking — DB 25 bảng, revision 007

Thiết kế này đã được triển khai vào models, repositories và API của dự án. Số lượng 25 không tính bảng quản lý migration `alembic_version`. Revision 007 thêm hai bảng lịch sử chat vào 23 bảng của revision 006; schema SQL revision 007 là nguồn chuẩn hiện tại.

## Các bảng

| Nhóm | Bảng | Mục đích |
| --- | --- | --- |
| Phim và phân loại (5) | `films`, `genres`, `film_genres`, `formats`, `film_formats` | Phim có nhiều thể loại và định dạng chiếu; lưu bằng bảng liên kết thay cho JSON trong `films` |
| Rạp và suất chiếu (6) | `theaters`, `cinema_rooms`, `seat_types`, `seats`, `showtimes`, `seat_status` | Phòng, ghế vật lý, giá theo loại ghế và trạng thái ghế theo từng suất |
| Đặt vé và thanh toán (4) | `bookings`, `booking_details`, `payments`, `tickets` | Đơn đặt, từng ghế/giá tại thời điểm đặt, từng lần thanh toán và vé kiểm soát vào rạp |
| Tài khoản và quyền (4) | `users`, `roles`, `permissions`, `role_permissions` | Mỗi người dùng thuộc một vai trò; một vai trò có nhiều quyền |
| Đánh giá và AI (4) | `reviews`, `review_sentiments`, `ai_documents`, `ai_chunks` | Giữ các chức năng đánh giá và tài liệu AI hiện có |
| Lịch sử chat (2) | `ai_conversations`, `ai_messages` | Hội thoại thuộc tài khoản, nội dung hỏi/đáp và nguồn tham khảo; xóa hội thoại sẽ xóa tin nhắn |

`booking_details` tồn tại ngay khi tạo đơn và lưu giá ghế tại thời điểm đặt. Mỗi dòng chỉ có tối đa một `tickets`; vé được phát hành khi đơn đã `PAID` và `CONFIRMED`. `ticket_code` là mã ngẫu nhiên để đưa vào QR, chuyển `ISSUED` sang `USED` một lần khi check-in. Phần hiển thị QR và màn hình quản trị phân quyền chưa được bổ sung.

`bookings` có nhiều `payments`, vì một đơn có thể thử thanh toán nhiều lần. `payments.merchant_ref` là mã riêng cho từng lần thử, còn `transaction_ref` là mã từ nhà cung cấp. Số tiền dùng `NUMERIC(12,2)`. Callback lặp không tạo thêm vé; thanh toán đến sau khi đơn hết hạn hoặc xác nhận ghế thất bại được lưu trong sổ giao dịch để đối soát, không tự phát hành vé. Chức năng hoàn tiền/đối soát thủ công cần được thực hiện riêng.

`showtimes.format_id` phải thuộc các định dạng của phim trong `film_formats`. Thời lượng phim lưu ở `duration_minutes`; các trường đọc API `genre`, `formats`, `duration`, `format`, `role` vẫn được giữ để frontend hiện tại hoạt động. JSON ở các phần AI hoặc thông tin phụ của rạp vẫn giữ nguyên.

DB bổ sung ràng buộc ghế đúng phòng, chống ghế trùng trong đơn và chống suất chiếu chồng giờ trong cùng phòng. Phim, rạp và phòng dùng `deleted_at`; lịch sử đặt vé/thanh toán được bảo vệ bằng khóa ngoại `RESTRICT`. Ghế ngừng sử dụng trả về trạng thái `UNAVAILABLE` và không được giữ/đặt.

## Nâng cấp DB hiện có

Sao lưu DB, tạm dừng API/Celery đang ghi dữ liệu, kiểm tra `DATABASE_URL` trỏ đúng DB rồi chạy từ thư mục `Backend`:

```powershell
python -m alembic upgrade head
python -m alembic check
```

Migration `006_normalized_booking_schema.py` chuyển dữ liệu thể loại, định dạng, thời lượng, vai trò và lịch sử thanh toán/vé. Các định dạng đang có trong lịch chiếu cũng được giữ. Thời lượng không chuyển đổi được sẽ làm migration dừng để sửa dữ liệu thay vì âm thầm bỏ thông tin. Ràng buộc mới cũng có thể phát hiện ghế/lịch chiếu không hợp lệ trong dữ liệu cũ; cần sửa các dòng vi phạm trước khi chạy lại. Alembic dùng transaction DDL trên PostgreSQL.

Migration 006 không hỗ trợ downgrade tự động vì có lịch sử giao dịch/vé mới. Khi cần quay về bản cũ, khôi phục bản sao lưu cùng phiên bản ứng dụng tương ứng.

Migration `007_ai_chat_history.py` chỉ tạo hai bảng chat cùng index, khóa ngoại và ràng buộc vai trò tin nhắn. Ngày 09/10/2026 đã nâng cấp DB ở `localhost:5434/BackendTTCS` từ 006 lên 007; `alembic check` không phát hiện khác biệt schema. Migration 007 hỗ trợ downgrade nhưng sẽ xóa lịch sử chat đã lưu.

## Tạo DB mới

Tạo một database PostgreSQL trống và dùng **một** trong hai cách:

1. Cấu hình `DATABASE_URL` và chạy `python -m alembic upgrade head` từ `Backend`.
2. Chạy toàn bộ `Backend/migrations/007_full_database.sql` trên DB trống bằng công cụ SQL hoặc `psql -v ON_ERROR_STOP=1 -d <database> -f migrations/007_full_database.sql`. File có đủ 25 bảng, index, trigger, quyền mẫu và revision Alembic 007; không chứa lệnh tạo database. File 006 giữ lại để tham khảo schema trước khi bổ sung chat.

Không chạy file tạo schema đầy đủ trên DB có bảng sẵn. Sau khi tạo schema, có thể chạy `Backend/seed_data.sql` cho DB demo. Seed không dành cho dữ liệu thật; các tài khoản mẫu dùng mật khẩu công khai `password123`. Schema/migration tự tạo vai trò và quyền, không tự tạo tài khoản admin.

Khi thay đổi models/triggers, xuất lại file SQL bằng `python scripts/export_database_schema.py` từ `Backend`. Không dùng `SQLModel.metadata.create_all()` để thay migration vì các trigger kiểm tra nghiệp vụ được cài qua migration/file SQL.

## API và quyền

| API | Yêu cầu |
| --- | --- |
| `GET /tickets/booking/{booking_id}` | Chủ đơn đăng nhập |
| `POST /tickets/{ticket_code}/check-in` | `tickets.check_in` |
| `GET /access-control/roles` | `roles.manage` |
| `GET /access-control/permissions` | `roles.manage` |
| `GET /access-control/roles/{role_id}/permissions` | `roles.manage` |
| `PUT /access-control/users/{user_id}/role` với `{"role_id": 1}` | `users.manage` |
| `PUT /access-control/roles/{role_id}/permissions` với `{"permission_ids": [1,2]}` | `roles.manage` |
| `GET /ai/conversations` | Đăng nhập; chỉ hội thoại của mình |
| `GET /ai/conversations/{id}` | Chủ hội thoại; tin nhắn có phân trang |
| `DELETE /ai/conversations/{id}` | Chủ hội thoại; xóa toàn bộ tin nhắn trong hội thoại |

Các ID trong ví dụ chỉ minh họa; lấy ID thực tế từ API. Quyền được đọc từ DB ở mỗi yêu cầu. Vai trò `USER` không có quyền quản trị; `STAFF` và `MANAGER` có `tickets.check_in`, `reviews.moderate`, `seat_types.manage`; `ADMIN` có thêm `users.manage`, `roles.manage`. Đăng ký tài khoản luôn gán vai trò `USER`.

VNPay sử dụng mã lần thanh toán làm `vnp_TxnRef`; callback cũ dạng ID booking được backfill thành `merchant_ref` tương ứng để tiếp tục đối chiếu. Cần chạy API và worker cùng phiên bản ứng dụng; API chat yêu cầu schema 007.

## Kiểm chứng trước khi bổ sung chat (revision 006)

- PostgreSQL 18 riêng: nâng cấp từ revision 005 với seed cũ; giữ 4 phim, 8 suất chiếu và phát hành 2 vé lịch sử cho đơn đã thanh toán.
- Tạo DB mới bằng cả Alembic và file SQL đầy đủ; cả hai có 23 bảng ứng dụng. `alembic check` không phát hiện khác biệt schema.
- Seed mới chạy hai lần trên DB demo không tạo bản ghi trùng.
- Backend: 163 tests đạt, bao gồm kiểm tra thực tế trên PostgreSQL về khóa ngoại, lịch chồng, ghế, callback thanh toán, vé và phân quyền. Có 3 cảnh báo Pydantic từ schema cũ.
- Frontend: `npm run build` đạt.

## Kiểm chứng lịch sử chat (revision 007, 09/10/2026)

- DB đang chạy nâng cấp từ 006 lên 007; `alembic check` không phát hiện khác biệt schema.
- File `007_full_database.sql` tạo được DB thử mới với 25 bảng ứng dụng trên PostgreSQL 15.
- Backend: 171 tests đạt trên DB thử riêng, gồm lưu hỏi/đáp và nguồn, phân trang, quyền sở hữu, khôi phục khi cache hết hạn, rollback khi lưu lỗi, xung đột ghi đồng thời, khóa ngoại, ràng buộc role và cascade xóa tin nhắn. Python cục bộ cần thêm `tmp/test-dependencies` vào `PYTHONPATH` để dùng bcrypt 4.1.2 đã có trong workspace.
- Kiểm tra HTTP trực tiếp trên API Docker đang chạy: xác thực, lưu và tải lại lịch sử, tiếp tục sau khi xóa context Redis, chặn tài khoản khác và xóa hội thoại đều đạt. Tài khoản và dữ liệu kiểm thử đã được dọn sạch.
- Sau khi ghép vào giao diện mới trên `main`: 42 tests AI backend, lint toàn bộ frontend, build và 7 tests frontend đạt. Kiểm tra trình duyệt với fixture cô lập đạt 37 trường hợp bố cục tại 375px, 768px và 1440px; kiểm tra thêm mở lịch sử, tải tin nhắn cũ, tiếp tục chat, tải lại trang, xóa hội thoại và phục hồi focus để đóng bằng Escape. Không có lỗi JavaScript trong trình duyệt.

Để chạy test PostgreSQL, tạo DB thử riêng có tên chứa `test`, migrate đến head và đặt `TEST_POSTGRES_URL` trước khi chạy `python -m pytest -q` trong `Backend`. Mỗi test dùng transaction rollback; không trỏ biến này vào DB thật. Không đặt biến này thì các bài kiểm tra PostgreSQL sẽ được bỏ qua. Redis/VNPay/email được thay bằng test doubles trong kiểm tra tích hợp, chưa kiểm tra giao dịch với cổng thanh toán thực tế.
