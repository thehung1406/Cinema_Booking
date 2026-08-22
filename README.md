# 🎬 Cinema Booking System

Hệ thống Đặt vé Xem phim Trực tuyến Fullstack xây dựng theo kiến trúc **Monorepo** kết hợp **FastAPI** (Backend) + **React Vite** (Frontend) + **PostgreSQL 15** + **Redis 7** + **Celery Worker** + **Cổng thanh toán VNPay**.

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

| Phân hệ | Công nghệ | Mục đích sử dụng |
|:---|:---|:---|
| **Backend** | Python 3.12, FastAPI, SQLModel / SQLAlchemy, Pydantic, Alembic | Xây dựng RESTful API tốc độ cao, quản lý DB & Migrations |
| **Frontend** | React 18 / 19, Vite, React Router 7, Axios, TailwindCSS | Giao diện Single Page Application (SPA) hiện đại, responsive |
| **Database & Cache** | PostgreSQL 15, Redis 7 | Cơ sở dữ liệu chính & Khóa phân tán giữ ghế (Redis Lock TTL 10 phút) |
| **Background Tasks** | Celery Worker, Celery Beat, Flower UI Dashboard | Tác vụ nền dọn dẹp ghế quá hạn & gửi email vé |
| **Payment Gateway** | VNPay Sandbox (HMAC SHA512) | Cổng thanh toán trực tuyến bảo mật cao |
| **DevOps & Container** | Docker, Docker Compose, Git Workflow | Đóng gói và triển khai đồng bộ 7 container dịch vụ |

---

## 📁 Cấu Trúc Dự Án (Monorepo Structure)

```text
Cinema_Booking/
├── Backend/                                # Phân hệ Backend FastAPI
│   ├── alembic/                            # Quản lý Database Migrations
│   │   ├── versions/
│   │   │   ├── 001_initial_migration.py    # Schema khởi tạo (theaters, rooms, films, users...)
│   │   │   ├── 002_optimize_indexes_types_cascade.py # Composite index & Numeric types
│   │   │   ├── 003_add_seat_type_table.py  # Bảng seat_types & chuẩn hóa giá ghế
│   │   │   └── 004_add_version_to_seat_status.py # Thêm version cho Optimistic Concurrency Control (OCC)
│   │   └── env.py
│   ├── app/
│   │   ├── core/                           # Cấu hình cốt lõi (Config, DB Engine, Redis)
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── redis.py
│   │   ├── models/                         # Database Models (SQLModel)
│   │   │   ├── booking.py                  # Model bookings & booking_seats
│   │   │   ├── cinema_room.py              # Model phòng chiếu
│   │   │   ├── film.py                     # Model phim
│   │   │   ├── payment.py                  # Model giao dịch thanh toán
│   │   │   ├── seat.py                     # Model ghế vật lý
│   │   │   ├── seat_status.py              # Model trạng thái ghế (OCC versioning)
│   │   │   ├── seat_type.py                # Model loại ghế & giá
│   │   │   ├── showtime.py                 # Model suất chiếu
│   │   │   ├── theater.py                  # Model cụm rạp
│   │   │   └── user.py                     # Model người dùng & vai trò
│   │   ├── repositories/                   # Tầng truy vấn Database (Data Access Layer)
│   │   │   ├── auth_repo.py, booking_repo.py, cinema_room_repo.py
│   │   │   ├── film_repo.py, payment_repo.py, seat_repo.py
│   │   │   ├── seat_type_repo.py, showtime_repo.py, theater_repo.py
│   │   ├── router/                         # API Endpoints (Controllers)
│   │   │   ├── auth.py                     # /auth (login, register, me, logout, refresh)
│   │   │   ├── booking.py                  # /bookings (tạo đơn đặt vé, lịch sử vé)
│   │   │   ├── cinema_room.py              # /cinema_rooms (phòng chiếu theo rạp)
│   │   │   ├── film.py                     # /films (danh sách phim, chi tiết)
│   │   │   ├── payment.py                  # /payment (tạo URL VNPay, verify chữ ký, IPN)
│   │   │   ├── seat.py                     # /seats (sơ đồ ghế bảo mật, hold, release, cancel-hold)
│   │   │   ├── seat_type.py                # /seat-types (quản lý loại ghế)
│   │   │   ├── showtime.py                 # /showtimes (lịch chiếu theo rạp & ngày)
│   │   │   └── theater.py                  # /theater (danh sách rạp, lọc theo phim)
│   │   ├── schemas/                        # DTO / Pydantic Request & Response Schemas
│   │   ├── services/                       # Business Logic Layer (Auth, Booking, Seat Lock, Payment...)
│   │   ├── utils/                          # Bảo mật, dependencies (get_optional_current_user), Redis Lock
│   │   └── worker/                         # Celery Worker Tasks (Dọn ghế hết hạn & gửi email vé)
│   ├── tests/                              # Unit & Contract Tests (45 tests)
│   ├── alembic.ini
│   ├── docker-compose.yml                  # Điều phối 7 containers (App, DB, Redis, Celery...)
│   ├── Dockerfile
│   ├── main.py                             # Entrypoint FastAPI
│   ├── requirements.txt
│   └── README.md
├── Frontend/                               # Phân hệ Frontend React + Vite
│   ├── public/                             # Tài nguyên tĩnh
│   ├── src/
│   │   ├── assets/
│   │   ├── components/                     # React UI Components
│   │   │   ├── About.jsx                   # Giới thiệu rạp
│   │   │   ├── CinemaList.jsx              # Danh sách cụm rạp & bộ lọc tỉnh/thành phố
│   │   │   ├── Contact.jsx                 # Trang thông tin liên hệ
│   │   │   ├── HomePage.jsx                # Layout chính (Header, Outlet, Footer)
│   │   │   ├── LoginPage.jsx               # Đăng nhập & Đăng ký tài khoản
│   │   │   ├── MainHomePage.jsx            # Banner carousel, danh sách phim đang/sắp chiếu
│   │   │   ├── Movie.jsx                   # Danh sách phim & lọc thể loại
│   │   │   ├── MovieDetail.jsx             # Chi tiết phim, trailer modal & đặt vé
│   │   │   ├── NotFound.jsx                # Trang 404
│   │   │   ├── PaymentPage.jsx             # Xác nhận đơn đặt vé & thanh toán VNPay
│   │   │   ├── SeatSelection.jsx           # Sơ đồ chọn ghế real-time (Redis lock 10 phút)
│   │   │   ├── TicketBooking.jsx           # Đặt vé & lọc rạp theo phim
│   │   │   ├── UserInfor.jsx               # Quản lý tài khoản cá nhân
│   │   │   └── VNPayReturn.jsx             # Tiếp nhận kết quả thanh toán VNPay
│   │   ├── config/
│   │   │   └── api.js                      # Axios instance + Bearer token interceptor
│   │   ├── services/                       # authStorage.js, filmService.js
│   │   ├── utils/                          # filmUtils.js
│   │   ├── tests/                          # authStorage.test.mjs
│   │   ├── App.css, App.jsx, index.css, main.jsx
│   ├── .env.example
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── .gitignore                              # Root gitignore
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Dự Án (Quick Start)

### 1. Yêu cầu môi trường
- **Docker & Docker Compose** (khuyến nghị)
- **Node.js** >= 18.x
- **Python** >= 3.11 (nếu chạy local không dùng Docker)

---

### 2. Khởi chạy toàn bộ hệ thống với Docker Compose (Khuyến nghị)

```bash
# 1. Di chuyển vào thư mục Backend
cd Backend

# 2. Khởi tạo file biến môi trường
cp .env.example .env

# 3. Khởi chạy 7 container (FastAPI, PostgreSQL, Redis, Celery Worker, Celery Beat, Flower, PgAdmin)
docker compose up -d --build

# 4. Chạy Database Migrations mới nhất
docker compose exec fastapi alembic upgrade head
```

---

### 3. Khởi chạy Frontend (React + Vite)

```bash
# Mở một terminal mới và di chuyển vào Frontend
cd Frontend

# 1. Tạo file môi trường từ mẫu
cp .env.example .env

# 2. Cài đặt các gói phụ thuộc
npm install

# 3. Chạy môi trường phát triển (Dev server)
npm run dev
# Truy cập giao diện tại: http://localhost:5173
```

---

## 🔐 Điểm Nhấn Kỹ Thuật Nổi Bật

1. **Khóa Ghế 2 Lớp Chống Trùng Lặp**:
   - **Lớp 1 (Redis Lock)**: Đảm bảo tính tức thời bằng `SET NX EX 600` (TTL 10 phút) và các Lua script nguyên tử.
   - **Lớp 2 (Database OCC)**: Kiểm soát đồng thời lạc quan với trường `version` trong bảng `seat_status`.
2. **Bảo Mật Quyền Riêng Tư Trạng Thái Ghế (Issue #34)**:
   - Endpoint `GET /seats/showtime/{id}` hỗ trợ `get_optional_current_user`, không để lộ `hold_by_user_id` công khai và trả về `is_held_by_me` an toàn.
3. **Thanh Toán Trực Tuyến VNPay**:
   - Tích hợp chuẩn mã hóa ký số **HMAC SHA512**, xác thực chữ ký bảo mật ở cả Return URL và IPN webhook.

---

## 🧪 Chạy Kiểm Thử (Testing)

### Backend Tests (45 Tests Pytest)
```bash
# Chạy từ thư mục gốc Monorepo
python -m pytest Backend/tests

# Hoặc từ thư mục Backend
cd Backend
pytest -v
```

### Frontend Tests & Linting
```bash
cd Frontend
npm run lint
```

---

## 🌐 Danh Sách Cổng Dịch Vụ (Port Mappings)

| Dịch vụ | URL / Địa chỉ | Tài khoản mặc định |
|:---|:---|:---|
| **Frontend Web** | `http://localhost:5173` | - |
| **FastAPI Backend** | `http://localhost:8000` | - |
| **Swagger API Docs** | `http://localhost:8000/docs` | - |
| **ReDoc API Docs** | `http://localhost:8000/redoc` | - |
| **PgAdmin 4** | `http://localhost:5050` | `admin@gmail.com` / `admin123` |
| **Flower (Celery Monitor)** | `http://localhost:5555` | - |
| **PostgreSQL Database** | `localhost:5434` *(host)* / `5432` | `postgres` / `pass123` |
| **Redis Cache** | `localhost:6379` | - |

---

## 📋 Danh Sách Module & Tiến Độ

| Mã Module | Tên Module | Trạng thái |
|:---:|:---|:---:|
| `MOD-01` | **Quản lý Xác thực & Tài khoản (Auth & User)** | ✅ **Đã hoàn thành** |
| `MOD-02` | **Quản lý Phim & Danh mục (Movie Management - Fix N+1)** | ✅ **Đã hoàn thành** |
| `MOD-03` | **Quản lý Cụm Rạp & Phòng Chiếu (Theaters & Rooms)** | ✅ **Đã hoàn thành** |
| `MOD-04` | **Quản lý Suất Chiếu (Showtimes Scheduling)** | ✅ **Đã hoàn thành** |
| `MOD-05` | **Quản lý Loại Ghế & Giữ Ghế Real-time (Seats, Redis Lock & Privacy #34)** | ✅ **Đã hoàn thành** |
| `MOD-06` | **Quản lý Đặt Vé & Đơn Hàng (Booking Flow Context & Routing)** | ✅ **Đã hoàn thành** |
| `MOD-07` | **Tích hợp Cổng Thanh Toán VNPay (Payment Gateway & HMAC SHA512)** | ✅ **Đã hoàn thành** |
| `MOD-08` | **Xử lý Nền & Gửi Email Vé (Celery & Background Tasks)** | ✅ **Đã hoàn thành** |
| `MOD-09` | **Giao diện Cổng Thông Tin & Luồng Đặt Vé (UI/UX SPA React)** | ✅ **Đã hoàn thành** |
| `MOD-10` | **Hạ Tầng, Database & DevOps (Docker Compose, Alembic OCC)** | ✅ **Đã hoàn thành** |
