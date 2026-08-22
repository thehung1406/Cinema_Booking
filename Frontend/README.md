# 🎬 Cinema Booking — Frontend Web Application

Giao diện Web Ứng dụng Đặt vé Xem phim Trực tuyến xây dựng bằng **React 18 / 19**, **Vite**, **React Router 7**, **TailwindCSS** và **Axios Client**.

---

## 🛠️ Công Nghệ Sử Dụng (Frontend Tech Stack)

| Phân hệ / Thư viện | Phiên bản | Mục đích sử dụng |
|:---|:---|:---|
| **React** | 18 / 19 | Thư viện UI xây dựng Single Page Application (SPA) |
| **Vite** | 6.x | Build tool & Dev Server hiệu năng cao hỗ trợ Fast HMR |
| **React Router** | 7.x | Định tuyến & điều hướng trang client-side linh hoạt |
| **TailwindCSS** | 4.x | Styling giao diện người dùng hiện đại, responsive |
| **Axios** | 1.8.x | HTTP client kết nối REST API Backend kèm Interceptors |
| **React Icons** | 5.x | Bộ biểu tượng giao diện trực quan |

---

## 📁 Cấu Trúc Thư Mục Frontend (`Frontend/`)

```text
Frontend/
├── public/                                 # Tài nguyên tĩnh (Favicon, Logo...)
│   ├── CGV incon.png
│   └── vite.svg
├── src/
│   ├── assets/                             # Assets ảnh, vector
│   ├── components/                         # React UI Components
│   │   ├── About.jsx                       # Trang giới thiệu hệ thống rạp
│   │   ├── CinemaList.jsx                  # Danh sách cụm rạp & bộ lọc tỉnh/thành phố
│   │   ├── Contact.jsx                     # Trang thông tin liên hệ & hỗ trợ
│   │   ├── HomePage.jsx                    # Layout bọc chính (Header, Outlet, Footer)
│   │   ├── LoginPage.jsx                   # Giao diện Đăng nhập & Đăng ký tài khoản
│   │   ├── MainHomePage.jsx                # Trang chủ: Banner carousel, phim đang/sắp chiếu
│   │   ├── Movie.jsx                       # Danh sách phim & bộ lọc thể loại
│   │   ├── MovieDetail.jsx                 # Chi tiết phim, trailer modal & đặt vé nhanh
│   │   ├── NotFound.jsx                    # Trang thông báo lỗi 404 Not Found
│   │   ├── PaymentPage.jsx                 # Giao diện chọn phương thức thanh toán & xác nhận
│   │   ├── SeatSelection.jsx               # Sơ đồ chọn ghế xem phim real-time (Redis lock 10 phút)
│   │   ├── TicketBooking.jsx               # Luồng chọn phim ➔ Lọc rạp ➔ Chọn suất chiếu
│   │   ├── UserInfor.jsx                   # Quản lý hồ sơ cá nhân & đổi mật khẩu
│   │   └── VNPayReturn.jsx                 # Xử lý kết quả trả về từ cổng thanh toán VNPay
│   ├── config/
│   │   └── api.js                          # Cấu hình Axios instance & Bearer Token Interceptor
│   ├── services/
│   │   ├── authStorage.js                  # Quản lý Auth Session & Token trong LocalStorage
│   │   └── filmService.js                  # Service tập trung gọi API phim (tối ưu hóa dữ liệu)
│   ├── utils/
│   │   └── filmUtils.js                    # Helper phân loại phim đang/sắp chiếu & format ngày giờ
│   ├── tests/
│   │   └── authStorage.test.mjs            # Unit test cho auth storage client
│   ├── App.css                             # Custom styles
│   ├── App.jsx                             # Cấu hình danh sách Routes (React Router)
│   ├── index.css                           # TailwindCSS base directives
│   └── main.jsx                            # Entrypoint render React DOM
├── .env.example                            # Mẫu biến môi trường Frontend
├── .gitignore
├── eslint.config.js                        # Cấu hình Linting ESLint
├── index.html                              # HTML template gốc
├── package.json                            # Danh sách dependencies & scripts
└── vite.config.js                          # Cấu hình Vite & Reverse Proxy API
```

---

## 🌐 Bảng Định Tuyến Trang (Routing Table)

| Đường dẫn (URL) | Component | Chức năng / Nghiệp vụ |
|:---|:---|:---|
| `/` | `MainHomePage` | Trang chủ hiển thị banner phim nổi bật, phim đang chiếu & sắp chiếu |
| `/movie` | `Movie` | Danh sách toàn bộ phim đang chiếu & sắp chiếu |
| `/movie/:id` | `MovieDetail` | Chi tiết phim, trailer, thể loại và đặt vé |
| `/cinema` | `CinemaList` | Danh sách cụm rạp, lọc theo tỉnh / thành phố |
| `/ticket-booking` | `TicketBooking` | Luồng chọn phim ➔ Lọc rạp ➔ Chọn ngày & Suất chiếu |
| `/seat-selection/:showtimeId` | `SeatSelection` | Sơ đồ chọn ghế tương tác, giữ ghế thời gian thực |
| `/payment/:bookingId` | `PaymentPage` | Xác nhận đơn đặt vé & chuyển hướng cổng thanh toán VNPay |
| `/payment-result` | `VNPayReturn` | Tiếp nhận và hiển thị kết quả giao dịch thanh toán VNPay |
| `/user-info` | `UserInfor` | Quản lý thông tin tài khoản cá nhân & đổi mật khẩu |
| `/login` | `LoginPage` | Đăng nhập & Đăng ký tài khoản |
| `/contact` | `Contact` | Trang liên hệ & hỗ trợ người dùng |
| `/about` | `About` | Giới thiệu về hệ thống rạp chiếu |
| `*` | `NotFound` | Trang báo lỗi đường dẫn không tồn tại (404) |

---

## 🎯 Luồng Trải Nghiệm Đặt Vé (User Booking Journey)

```text
[Trang Chủ / Danh Sách Phim]
          │
          ▼
[Chi Tiết Phim & Chọn Suất Chiếu (/ticket-booking)]
          │
          ▼
[Sơ Đồ Chọn Ghế Real-time (/seat-selection/:showtimeId)]
  - Khóa giữ ghế 10 phút qua Redis Lock
  - Ẩn ID người dùng khác, hiển thị is_held_by_me
          │
          ▼
[Xác Nhận Đơn Hàng & Thanh Toán (/payment/:bookingId)]
          │
          ▼
[Cổng Thanh Toán VNPay Sandbox]
          │
          ▼
[Xác Nhận & Hiển Thị Kết Quả Đặt Vé (/payment-result)]
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### 1. Yêu cầu hệ thống
- **Node.js** >= 18.x
- **npm** >= 9.x hoặc **yarn** / **pnpm**

---

### 2. Thiết lập Biến môi trường
Tạo file `.env` từ mẫu `.env.example`:

```bash
cd Frontend
cp .env.example .env
```

Nội dung file `.env`:
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROXY_PATH=/api
VITE_APP_NAME="Cinema Booking"
VITE_APP_VERSION=1.0.0
```

---

### 3. Cài đặt Dependencies & Khởi chạy Development Server

```bash
# 1. Cài đặt các gói thư viện phụ thuộc
npm install

# 2. Khởi chạy máy chủ phát triển
npm run dev
```

Ứng dụng sẽ khả dụng tại địa chỉ: **`http://localhost:5173`**

---

### 4. Build Production

```bash
# Build mã nguồn tối ưu cho môi trường Production
npm run build

# Chạy thử bản build Production cục bộ
npm run preview
```

---

## 🔌 Cơ Chế Giao Tiếp API (API Integration)

- Toàn bộ request gọi REST API Backend đi qua instance **`api`** tại [src/config/api.js](file:///d:/Cinema_Booking/Frontend/src/config/api.js).
- **Vite Reverse Proxy**: Tự động định tuyến `/api/*` tới `http://localhost:8000/*` trong môi trường dev, loại bỏ vấn đề CORS.
- **Request Interceptor**: Tự động đính kèm `Authorization: Bearer <token>` nếu người dùng đã đăng nhập.
- **Response Interceptor**: Tự động bắt lỗi HTTP `401 Unauthorized` để dọn dẹp session đã hết hạn và điều hướng tới trang đăng nhập.
