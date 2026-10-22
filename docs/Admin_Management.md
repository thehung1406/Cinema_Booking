# Admin / quản lý theo CinemaBooking_Sequence_Diagrams.vpp

Mã nguồn bổ sung các chức năng UC01–UC07, bao gồm tám kịch bản tuần tự SD01–SD07. Trang quản trị nằm ở `/admin`, dùng tài khoản và phiên đăng nhập hiện có.

## Đưa vào sử dụng

Từ thư mục `Backend`, cập nhật cơ sở dữ liệu PostgreSQL lên revision `009` trước khi chạy phiên bản backend mới:

```powershell
python -m alembic upgrade head
python -m uvicorn main:app --reload
```

Nếu chạy backend bằng Docker, từ thư mục `Backend`:

```powershell
docker compose up -d --build
docker compose exec fastapi alembic upgrade head
```

Chạy frontend từ thư mục `Frontend`:

```powershell
npm install
npm run dev
```

Đăng nhập bằng tài khoản ADMIN hoặc MANAGER đã có. Hai vai trò này được chuyển đến `/admin` sau đăng nhập. Thanh điều hướng trang đặt vé cũng có liên kết **Quản trị rạp chiếu** cho ADMIN, MANAGER và STAFF. Tài khoản demo `admin` đã được khai báo trong `Backend/seed_data.sql`; không tự tạo hoặc đổi mật khẩu tài khoản trong cơ sở dữ liệu hiện tại.

Migration `009` thêm `users.is_active`, tạo các quyền mới và cấp quyền:

| Vai trò | Quyền mặc định |
|---|---|
| ADMIN | Tất cả quyền hiện có và quyền quản trị mới |
| MANAGER | Phim, phòng/ghế, lịch chiếu, giá vé; giữ nguyên các quyền đã có |
| STAFF | Giữ nguyên quyền hiện có; có thể vào mục giá vé nếu đã có `seat_types.manage` |
| USER | Không có quyền quản trị |

Mọi thao tác được kiểm tra bằng Permission/RolePermission tại API. Vai trò trong trình duyệt không quyết định quyền truy cập. Gán vai trò cần `roles.manage`; tạo nhân viên cần đồng thời `users.manage` và `roles.manage`.

## Đối chiếu thiết kế

| Use case / Sequence | Giao diện | Xử lý chính |
|---|---|---|
| UC01 / SD01 | `/admin/films` | Tìm, thêm, sửa, xóa phim; danh mục thể loại và định dạng; Film và các liên kết lưu cùng giao dịch |
| UC02 / SD02 | `/admin/rooms`, `/admin/rooms/:id/seats` | Quản lý phòng, sức chứa, sơ đồ, vị trí và loại ghế; kiểm tra đúng phòng, trùng vị trí, vượt sức chứa |
| UC03 / SD03 | `/admin/showtimes` | Tạo/sửa/xóa và lọc lịch; kiểm tra thời lượng, thời gian phát hành, định dạng, trạng thái phòng và trùng khoảng giờ |
| UC04 / SD04 | `/admin/prices` | Tìm/thêm/sửa/xóa mức giá theo loại ghế của phòng; không cập nhật BookingDetail.price đã chốt |
| UC05 / SD05 | `/admin/employees`, `/admin/roles` | Thêm/sửa hồ sơ, tìm tài khoản, khóa/mở tài khoản, gán vai trò, gán quyền cho vai trò |
| UC06 / SD06a–b | `/admin/documents` | Nhập văn bản hoặc `.txt`/`.md`, xử lý chunk/embedding, xem nội dung, sửa, xóa, duyệt/thu hồi duyệt đúng phiên bản |
| UC07 / SD07 | `/admin/reports` | Lọc thời gian/phim/rạp, tổng hợp doanh thu, vé, sử dụng ghế và cảm xúc; xuất CSV |

Các API mới đặt dưới `/admin`; phân quyền dùng thêm API `/access-control` hiện có. `/admin/session` trả về quyền hiệu lực để giao diện hiển thị đúng các mục được cấp.

## Các ràng buộc nghiệp vụ

- Suất chiếu dùng giờ Việt Nam, bắt đầu ở tương lai và kết thúc trong cùng ngày. Khoảng chiếu phải đủ thời lượng phim. Các suất liền kề được phép, khoảng giao nhau bị từ chối. Khóa hàng CinemaRoom trong giao dịch ghi giúp hai người lập lịch không thể cùng tạo lịch trùng.
- Thêm ghế khóa hàng phòng trước khi đếm sức chứa. Vị trí chuẩn hóa thành chữ hoa, ví dụ `A1`; SeatType phải thuộc đúng phòng.
- Không sửa/xóa suất đã có đơn; không sửa/xóa ghế có đơn hoặc trạng thái HOLD/BOOKED. Không xóa phim/phòng đã có lịch chiếu. Phòng không được giảm sức chứa xuống dưới số ghế hiện có. Các ràng buộc này được trả về dưới dạng lỗi có thể xem trên biểu mẫu.
- Không tự đổi vai trò, tự khóa tài khoản hoặc sửa quyền của vai trò đang sử dụng. Tài khoản bị khóa bị từ chối ở đăng nhập, xác thực API và xác thực tùy chọn, kể cả với access token đã cấp.
- Tài liệu mới hoặc nội dung cập nhật luôn ở trạng thái chưa duyệt. Lưu và duyệt kiểm tra `updated_at`; duyệt còn kiểm tra phiên bản cùng trạng thái xử lý chunk. Thay đổi sau khi mở màn hình duyệt sẽ khiến thao tác duyệt cũ bị từ chối. Retrieval tiếp tục chỉ dùng tài liệu đã duyệt, đang hiệu lực và đúng phiên bản embedding.
- Nhập tài liệu hỗ trợ văn bản UTF-8, tối đa 200 KB khi chọn tệp. Nội dung hiển thị dưới dạng văn bản; không render HTML từ tài liệu.

## Cách tính báo cáo

- Doanh thu, số đơn, vé và tỷ lệ ghế lọc theo **ngày chiếu**. Doanh thu lấy tổng đơn, gồm đồ ăn; chỉ lấy Booking PAID + CONFIRMED có Payment PAID đúng số tiền. Dùng kiểm tra tồn tại Payment nên nhiều lần thử thanh toán không nhân doanh thu.
- Vé bán gồm Ticket ISSUED/USED của các đơn hợp lệ. Ghế đã bán cần SeatStatus BOOKED và vé hợp lệ tương ứng. Mẫu số là tổng lượt ghế hiện đang ACTIVE của các suất trong phạm vi, không gồm suất CANCELLED; đây không phải ảnh chụp sức chứa lịch sử.
- Cảm xúc lọc theo thời điểm cập nhật Review trong khoảng ngày Việt Nam. Chỉ đánh giá approved, chưa xóa và kết quả succeeded đúng content_version mới đóng góp vào các nhóm tích cực/trung lập/tiêu cực. Độ phủ = số đánh giá có kết quả hợp lệ / tổng đánh giá approved trong phạm vi.
- Review thuộc phim, không thuộc rạp. Khi chọn rạp, báo cáo lấy đánh giá của các phim có lịch chiếu ở rạp đó trong phạm vi; không diễn giải là đánh giá riêng của rạp.
- Khoảng báo cáo tối đa 367 ngày, bao gồm hai đầu. Không có dữ liệu trả về 0. Báo cáo chỉ đọc dữ liệu giao dịch.

## Kiểm tra

```powershell
python -m pytest Backend/tests/test_admin_management.py -q
python -m pytest Backend/tests/test_admin_postgres.py -q
```

Kiểm thử PostgreSQL yêu cầu `TEST_POSTGRES_URL` trỏ đến cơ sở dữ liệu kiểm thử có chữ `test` trong tên. Kiểm thử tự tạo schema tạm riêng, chạy hai giao dịch đồng thời và dọn schema đó. Không đặt biến này thành URL cơ sở dữ liệu đang sử dụng.

Từ thư mục `Frontend`:

```powershell
npm run lint
npm test
npm run build
npm run test:admin
```

`test:admin` cần Playwright và một frontend đang chạy; có thể đặt `PLAYWRIGHT_MODULE`, `BROWSER_EXECUTABLE`, `UI_BASE_URL`, `UI_SCREENSHOT_DIR` tương tự các bài kiểm thử giao diện hiện có. Mọi API trong bài kiểm thử trình duyệt dùng dữ liệu riêng bị chặn tại trình duyệt, không ghi vào backend thật.

Tại thời điểm triển khai: 11 kiểm thử API quản trị, các luồng trình duyệt, lint/build và 7 unit test frontend đã qua. Toàn bộ backend có 159 bài qua, 34 bài bỏ qua do thiếu dịch vụ/cấu hình kiểm thử và sáu bài kiểm thử cũ thất bại do kiểm tra các tên biến/lời gọi cũ trong component đặt vé, phim và thanh toán. Cả sáu lỗi này đã được tái hiện trên bản HEAD gốc, trước thay đổi admin. Kiểm thử khóa hàng đồng thời thực tế chưa được chạy.

Khi khắc phục đăng nhập trên máy hiện tại, đã bật Docker/PostgreSQL/Redis và cập nhật cơ sở dữ liệu từ `005` lên `009`, sau khi lưu bản sao lưu trong `tmp/db-backups`. Migration `006` bổ sung nhận diện đúng đơn vị thời lượng cũ bị hỏng mã hóa thành `ph??t`; đã kiểm tra trực tiếp trên PostgreSQL với phút, giờ, dạng `2:05`, giá trị trống và việc từ chối đơn vị không hợp lệ. Docker Compose gắn thêm `main.py` để nạp các router mới và kiểm tra sức khỏe bằng Python có sẵn trong image. API đăng nhập, hồ sơ, quyền quản trị, danh sách phim và danh mục đều trả về thành công; đã xác nhận đăng nhập qua trình duyệt và mở `/admin/films`.
