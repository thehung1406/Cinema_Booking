# Bỏng, nước và combo

Luồng khách hàng: chọn suất chiếu → giữ ghế → chọn bỏng, nước hoặc combo → tạo đơn → thanh toán chung qua VNPay → xem vé và đồ ăn trong lịch sử. Có thể chọn “Bỏ qua, chỉ mua vé”. Bước chọn món không gia hạn thời gian giữ ghế; giao diện kiểm tra lại trạng thái ghế mỗi 15 giây và chặn khi hết hạn.

`GET /food-items` trả các món đang bán và thành phần combo. `POST /bookings` nhận thêm `foodItems: [{food_item_id, quantity}]`; trường này mặc định là danh sách rỗng để tương thích khách hàng cũ. Máy chủ tính tổng từ giá vé và giá món trong cơ sở dữ liệu, từ chối ID không còn bán, combo không đủ thành phần đang bán, dòng trùng, số lượng ngoài 1–20 và tổng tiền sai. Giá combo là giá bán của combo; không cộng thêm giá thành phần.

Migration `008` thêm `food_items`, `combo_items`, `booking_food_items` (tổng 28 bảng nghiệp vụ). Đơn lưu tên món, đơn giá, số lượng và tên/số lượng thành phần combo tại thời điểm mua. Chỉnh sửa thực đơn sau đó không thay đổi đơn cũ. Toàn bộ vé và món được lưu trong cùng transaction. VNPay thu `Booking.total_amount`; chưa thanh toán không phát hành vé. Chi tiết đơn, lịch sử và email xác nhận đều có đồ ăn.

Thực đơn seed và giá là **dữ liệu mẫu**, gồm 2 loại bỏng, 2 loại nước và 3 combo. Danh mục được cấu hình trong cơ sở dữ liệu; chưa có màn hình quản trị thực đơn hoặc quản lý tồn kho theo rạp.

## Khởi chạy

Chạy PostgreSQL/Redis và dịch vụ backend theo cấu hình hiện có, sau đó từ thư mục `Backend`:

```powershell
python -m alembic upgrade head
```

Với Docker:

```powershell
docker compose exec fastapi alembic upgrade head
```

`python scripts/export_database_schema.py` tạo `migrations/008_full_database.sql` cho **cơ sở dữ liệu mới**, có thực đơn mẫu. Với dữ liệu đã có, dùng Alembic.

## Sơ đồ

File: [CinemaBooking_Sequence_Diagrams_Food_Combos.vpp](diagrams/CinemaBooking_Sequence_Diagrams_Food_Combos.vpp).

- Thêm `SD12f - Chọn bỏng, nước và combo`, gồm tải thực đơn, chọn số lượng, tính tạm tiền, tiếp tục/bỏ qua và ghế hết hạn.
- Cập nhật `SD12b` với giá vé + đồ ăn, lưu snapshot cùng transaction và ký URL VNPay theo tổng tiền.
- Cập nhật `SD14` với đồ ăn và thành phần combo trong chi tiết đơn.
- File nguồn được giữ nguyên. Các sơ đồ lớp/ERD cũ trong VPP vẫn là schema trước phần đồ ăn; schema mới được mô tả trong migration và SQL `008`.

Bản giao giữ nguyên thông tin phiên bản của VPP nguồn. Visual Paradigm 17.3 trên máy cũ hơn phiên bản nguồn; ảnh kiểm tra được xuất bằng bộ render này trên bản sao riêng. Bản đánh giá của Visual Paradigm thêm watermark vào ảnh xuất. Không thay đổi file giao qua bộ render cũ.

## Kiểm tra

- Lint/build và 7 test frontend đạt.
- 38 test trên PostgreSQL riêng đạt: 15 test đồ ăn/API và 23 test schema/thanh toán hiện có, gồm giá server, snapshot, rollback, hết hạn và thanh toán tổng tiền.
- Test trình duyệt toàn ứng dụng đạt 37 bố cục; test riêng đồ ăn đạt 3 kích thước 375/768/1440, mua combo kèm nước lẻ, bỏ qua, menu lỗi, thử lại khi tổng tiền không khớp và ghế hết hạn. Các request thanh toán được mock, không gửi tới cổng thật.
- Suite backend đầy đủ có 6 kiểm tra chuỗi source cũ không khớp giao diện mới được pull từ `origin/main` (booking/film/payment contract); ghi nhận riêng, không thay đổi code để đáp ứng các chuỗi cũ.
- Migration đã chạy và kiểm tra trên PostgreSQL riêng; cần chạy migration cho cơ sở dữ liệu ứng dụng trước khi sử dụng tính năng.

Test trình duyệt: `npm run test:food` và `npm run test:ui`, cần Vite đang chạy. Có thể đặt `PLAYWRIGHT_MODULE`, `BROWSER_EXECUTABLE`, `UI_SCREENSHOT_DIR` theo môi trường. Test PostgreSQL: đặt `TEST_POSTGRES_URL` tới cơ sở dữ liệu riêng có chữ `test` trong tên và đã chạy Alembic.
