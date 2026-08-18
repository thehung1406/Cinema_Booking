# 🎬 Cinema Booking — Frontend Web Application

Giao diện Web Ứng dụng Đặt vé Xem phim Trực tuyến xây dựng bằng **React (Vite)**, **React Router**, **TailwindCSS** và **Axios Client**.

---

## 🛠️ Công Nghệ Sử Dụng (Frontend Tech Stack)

| Công nghệ | Phiên bản / Chi tiết | Mục đích sử dụng |
|:---|:---|:---|
| **React** | 18 / 19 | Thư viện UI xây dựng Single Page Application (SPA) |
| **Vite** | 6.x | Build tool & Dev Server tốc độ cao, hỗ trợ HMR |
| **React Router** | 7.x | Quản lý định tuyến và điều hướng trang (Client-side Routing) |
| **TailwindCSS** | 4.x | Styling giao diện người dùng hiện đại, responsive |
| **Axios** | 1.8.x | HTTP Client gọi REST API Backend kèm Interceptors |
| **React Icons** | 5.x | Bộ biểu tượng giao diện (FontAwesome, Lucide...) |

---

## 📁 Cấu Trúc Thư Mục Frontend (`Frontend/`)

```text
Frontend/
├── public/                                 # Tài nguyên tĩnh (Favicon, Logo, Images)
│   ├── CGV incon.png
│   └── vite.svg
├── src/
│   ├── assets/                             # Assets ảnh, vector SVG
│   ├── components/                         # React UI Components
│   │   ├── CinemaList.jsx                  # [MOD-03] Danh sách cụm rạp & bộ lọc thành phố
│   │   ├── LoginPage.jsx                   # [MOD-01] Đăng nhập & Đăng ký tài khoản
│   │   ├── MainHomePage.jsx                # Header, Navbar & trạng thái người dùng
│   │   ├── Movie.jsx                       # [MOD-02] Danh sách phim & lọc thể loại
│   │   ├── MovieDetail.jsx                 # [MOD-02] Chi tiết phim, trailer modal & lịch chiếu
│   │   ├── TicketBooking.jsx               # [MOD-03/04] Đặt vé & lọc rạp theo phim
│   │   └── UserInfor.jsx                   # [MOD-01] Quản lý thông tin tài khoản
│   ├── config/
│   │   └── api.js                          # Cấu hình Axios instance & Bearer Token Interceptor
│   ├── App.css                             # Custom styles
│   ├── App.jsx                             # Cấu hình Routes (React Router)
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

## 🚀 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng (Quick Start)

### 1. Yêu cầu hệ thống
- **Node.js** >= 18.x
- **npm** >= 9.x hoặc **yarn** / **pnpm**

---

### 2. Thiết lập Biến môi trường
Tạo file `.env` từ mẫu `.env.example`:

```bash
# Trên Windows PowerShell / CMD
cp .env.example .env

# Hoặc trên Linux/macOS
cp .env.example .env
```

Nội dung `.env`:
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PROXY_PATH=/api
VITE_APP_NAME="Cinema Booking"
VITE_APP_VERSION=1.0.0
```

---

### 3. Cài đặt Dependencies & Chạy Development Server

```bash
# 1. Di chuyển vào thư mục Frontend
cd Frontend

# 2. Cài đặt các gói thư viện
npm install

# 3. Khởi chạy máy chủ phát triển
npm run dev
```

Ứng dụng sẽ chạy tại địa chỉ: **`http://localhost:5173`**

---

### 4. Build Production Bundle

```bash
# Build mã nguồn tối ưu cho môi trường Production
npm run build

# Chạy thử bản build Production cục bộ
npm run preview
```

---

## 🌐 Bảng Định Tuyến Trang (Routing Table)

| Đường dẫn (URL) | Component Phụ Trách | Chức năng / Nghiệp vụ |
|:---|:---|:---|
| `/` | `MainHomePage` | Trang chủ hiển thị banner phim hot, phim đang chiếu |
| `/movie` | `Movie` | Danh sách toàn bộ phim đang chiếu & sắp chiếu |
| `/MovieDetail/:id` | `MovieDetail` | Xem thông tin chi tiết phim, thể loại, trailer và đặt vé |
| `/cinema` | `CinemaList` | Danh sách cụm rạp CGV, lọc theo tỉnh / thành phố |
| `/TicketBooking` | `TicketBooking` | Luồng chọn phim ➔ Lọc rạp ➔ Chọn ngày & Suất chiếu |
| `/loginPage` | `LoginPage` | Giao diện Đăng nhập / Đăng ký tài khoản |
| `/userInfo` | `UserInfor` | Quản lý thông tin cá nhân & đổi mật khẩu |

---

## 🔌 Cơ Chế Giao Tiếp API (API Integration)

- Mọi tương tác gọi dữ liệu với Backend đều đi qua instance **`api`** tại [src/config/api.js](file:///d:/Cinema_Booking/Frontend/src/config/api.js).
- **Vite Reverse Proxy**: Trong môi trường development, các request gửi tới `/api/*` sẽ được Vite tự động chuyển tiếp tới `http://localhost:8000/*` để tránh lỗi CORS.
- **Request Interceptor**: Tự động đính kèm `Authorization: Bearer <token>` từ `localStorage` vào mỗi request.
- **Response Interceptor**: Tự động bắt mã lỗi HTTP `401 Unauthorized` để xóa session hết hạn và điều hướng về trang đăng nhập (`/LoginPage`).
