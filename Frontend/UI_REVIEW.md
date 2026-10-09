# Cải thiện giao diện Cinema Booking

## Khảo sát trước khi sửa

Frontend dùng React 19, Vite 6, Tailwind 4; icon Lucide và React Icons đã có sẵn. Các route nằm trong `src/App.jsx`; API qua `src/config/api.js`; phiên đăng nhập qua `src/services/authStorage.js`. Không thay đổi các hợp đồng này.

Các vấn đề ưu tiên được xác định từ mã hiện tại:

- MainHomePage có `m-20`, class sai `ursor-pointer`, poster cao cố định và carousel ẩn bằng opacity nhưng vẫn nhận tương tác.
- Header chưa thể hiện trang đang chọn; menu mobile có link khuyến mãi chưa có route và tài khoản chiếm nhiều chỗ.
- Các trang dùng màu nhấn xanh/đỏ, button và khoảng cách không thống nhất; nhiều nút thiếu nhãn hoặc nhỏ hơn 44px.
- Đổi ngày đặt vé có thể khôi phục phim từ URL, giữ suất chiếu cũ; lỗi tải suất chiếu bị hiển thị như không có lịch chiếu.
- Sơ đồ ghế chưa có vùng cuộn riêng; ghế đang giữ và đã đặt cùng màu; cập nhật ghế thiếu trạng thái xử lý.
- PaymentPage tự tính thời hạn 10 phút từ bookingDate rồi gửi cập nhật FAILED. BookingDetailResponse chưa trả thời điểm hết hạn để frontend có thể hiển thị chính xác.
- VNPayReturn coi đơn chưa thanh toán hoặc lỗi xác minh là thất bại, đồng thời thông báo gửi email/giải phóng ghế mà chưa có xác nhận tương ứng.
- UserInfor đọc trường snake_case trong khi GET /bookings trả camelCase, gán trạng thái hoàn tất khi thiếu dữ liệu.

## Thay đổi

- Hệ thống giao diện chung trong `src/index.css`, với đỏ CGV, vùng giới thiệu nền tối, nội dung sáng, font hệ thống hỗ trợ tiếng Việt, focus rõ và reduced motion.
- Thành phần dùng chung: Button, FormField, PageState, Poster, BookingSteps, MovieCard, BookingSummary. Poster có ảnh thay thế cục bộ, không gọi dịch vụ ảnh bên ngoài.
- Cải thiện toàn bộ trang chủ, danh sách/chi tiết phim, lịch chiếu, chọn ghế, thanh toán/kết quả, đăng nhập và tài khoản. Bộ lọc phim được giữ; tìm theo tên sử dụng title thật từ API.
- Carousel điều khiển thủ công, chỉ render slide đang chọn. Khi không có phim, có nội dung thay thế và đường dẫn khám phá phim.
- Ghế trống, đang chọn, đang giữ, đã đặt và loại ghế có chú thích riêng. Giữ/hủy ghế và tạo đơn giữ nguyên endpoint/payload; khóa thao tác khi yêu cầu đang xử lý, cập nhật trạng thái ghế mỗi 15 giây và cho phép cập nhật thủ công. Thời điểm giữ ghế lấy từ hold_expired_at.
- Thanh toán chỉ dựa vào phản hồi backend, không dùng bộ đếm tự suy đoán hoặc tự chuyển đơn thành FAILED. Kết quả phân biệt đang xác minh, thành công, thất bại, chờ xác nhận và chưa xác minh được. Lỗi kết nối VNPay giữ nguyên thông tin đơn để thử lại.
- Trợ lý có nút đóng và hỗ trợ Escape; nút mở nằm ngoài vùng nội dung trên mobile và trong luồng đặt vé/thanh toán.

## Kiểm tra

Trước thay đổi: build, lint và 3 test authStorage đạt. Sau thay đổi: build, lint, 7 test đơn vị và kiểm tra trình duyệt đạt; không ghi nhận lỗi build/lint từ trước.

Kiểm tra trình duyệt tại 375px, 768px, 1440px gồm 36 trường hợp bố cục, không tràn ngang và không lỗi JavaScript. Kiểm tra menu mobile, carousel, tìm phim, poster lỗi, trailer/Escape, vùng cuộn ghế, vùng chạm nút, payload giữ/hủy ghế và tạo booking, đăng nhập quay lại chọn ghế, đối chiếu ghế theo backend, lỗi VNPay, các trạng thái kết quả, lưu hồ sơ, thử lại API, không có dữ liệu, trợ lý, focus và reduced motion.

Chạy trong Frontend:

```powershell
npm test
npm run lint
npm run build
```

`npm run test:ui` cần Vite đang chạy và Playwright có sẵn từ môi trường ngoài dự án. Không thêm dependency ứng dụng. Có thể cấu hình:

```powershell
$env:PLAYWRIGHT_MODULE = 'đường dẫn tới thư mục package playwright có sẵn'
$env:BROWSER_EXECUTABLE = 'đường dẫn tới trình duyệt Chromium/Edge/Chrome có sẵn'
$env:UI_BASE_URL = 'http://127.0.0.1:5173'
$env:UI_SCREENSHOT_DIR = 'thư mục lưu ảnh chụp tùy chọn'
npm run test:ui
```

## Giới hạn xác minh

- Trong lần kiểm tra giao diện ban đầu, backend localhost:8000 chưa hoạt động. Đã kiểm tra giao diện lỗi thực tế; luồng tương tác và bố cục còn lại dùng fixture theo schema trong bài kiểm tra trình duyệt. Mọi fetch/XHR trong bài kiểm tra này đều bị chặn. Ứng dụng không chứa mock hoặc dữ liệu thay thế cho API thật.
- Sau yêu cầu khởi chạy backend, đã chạy và kiểm tra FastAPI, PostgreSQL, Redis, Celery worker/beat với dữ liệu local. Database được cập nhật từ migration 004 lên 005 bằng cơ chế startup hiện có. Container được đồng bộ main.py từ mã nguồn hiện tại vì tệp trong image cũ chưa đăng ký các router đánh giá. Không sửa mã nguồn backend.
- Đã tạo riêng suất chiếu kiểm thử #9: Kung Fu Panda 4, phòng 2, ngày 09/10/2026 lúc 18:00, dựa trên suất #6 và loại ghế/giá trong database; không đổi các lịch cũ. Đã tạo tài khoản USER kiểm thử, đăng nhập qua giao diện, giữ/hủy ghế A01, tạo đơn #2 tổng 90.000đ với trạng thái PENDING do backend trả về, kiểm tra trang thanh toán, trạng thái chờ xác nhận và lịch sử đơn. Backend tạo URL sandbox.vnpayment.vn thành công; không mở cổng thanh toán và không phát sinh thanh toán thật. Không có lỗi JavaScript hoặc tràn ngang ở bước thanh toán 375px.
- Chạy bộ pytest mở rộng: 135 đạt, 6 thất bại. Sáu lỗi là các kiểm tra đọc chuỗi trong mã frontend yêu cầu cấu trúc cũ (searchParams.get, handleBooking(e, movie.id), filmService trong từng trang, secondsLeft/VNPAY_RESPONSE_MESSAGES). Đây là sai khác xuất hiện sau lần tách component và bỏ đếm ngược suy đoán, không phải lỗi đã tồn tại trước thay đổi. Các hành vi điều hướng/API liên quan đã được kiểm tra bằng trình duyệt, gồm cả backend thật; chưa cập nhật các kiểm tra nằm trong Backend để giữ giới hạn không sửa backend.
- Chưa xác minh hoàn tất giao dịch VNPay end-to-end, giữ ghế đồng thời giữa nhiều tài khoản, email vé và quét QR tại rạp với hệ thống thật.
- API booking chưa trả thời hạn thanh toán nên không hiển thị đếm ngược thanh toán. API ghế có hold_expired_at nên hiển thị thời điểm giữ ghế.
- Quy tắc đăng ký Gmail hiện có được giữ nguyên; chưa có API cho khôi phục mật khẩu, ghi nhớ phiên tùy chọn hoặc đăng ký nhận tin nên không hiển thị các thao tác chưa hoạt động.
- Backend, route, API config, auth storage và dependency ứng dụng được giữ nguyên; các tài liệu người dùng trong docs không bị chỉnh sửa.
