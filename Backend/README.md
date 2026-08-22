# 🎬 Cinema Booking System — Backend API

Backend RESTful API cho Hệ thống Đặt vé Xem phim Trực tuyến xây dựng trên nền tảng **FastAPI**, **SQLModel / SQLAlchemy**, **PostgreSQL 15**, **Redis 7**, **Celery Worker** và tích hợp cổng thanh toán **VNPay**.

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

| Phân hệ | Công nghệ / Thư viện | Mục đích sử dụng |
|:---|:---|:---|
| **Framework** | FastAPI, Pydantic v2 | Xây dựng RESTful API tốc độ cao, validation tự động |
| **ORM / Data Access** | SQLModel, SQLAlchemy 2.x | Tương tác cơ sở dữ liệu PostgreSQL |
| **Database Migration** | Alembic | Quản lý phiên bản và lịch sử thay đổi schema DB |
| **Database** | PostgreSQL 15 | Cơ sở dữ liệu quan hệ lưu trữ dữ liệu chính |
| **Cache & Distributed Lock** | Redis 7 | Quản lý Token Blacklist & Khóa phân tán giữ ghế (TTL 10 phút) |
| **Background Tasks** | Celery 5.x, Redis Broker | Xử lý giải phóng ghế hết hạn, gửi email thông báo vé |
| **Monitoring Dashboard** | Flower | Giám sát trạng thái và tiến độ Celery worker |
| **Payment Gateway** | VNPay Sandbox (HMAC SHA512) | Thanh toán trực tuyến an toàn |
| **Security & Auth** | Passlib (Bcrypt), Python-Jose (JWT) | Mã hóa mật khẩu và xác thực người dùng |
| **Testing** | Pytest, AnyIO | Contract tests & Unit tests toàn diện |

---

## 📁 Cấu Trúc Thư Mục (`Backend/`)

```text
Backend/
├── alembic/                                # Quản lý Database Migrations
│   ├── versions/
│   │   ├── 001_initial_migration.py        # Schema ban đầu (users, films, theaters, rooms...)
│   │   ├── 002_optimize_indexes_types_cascade.py # Composite indexes & kiểu dữ liệu
│   │   ├── 003_add_seat_type_table.py      # Bảng seat_types & phân loại giá ghế
│   │   └── 004_add_version_to_seat_status.py # Bổ sung trường version cho Optimistic Concurrency Control (OCC)
│   └── env.py
├── app/
│   ├── core/                               # Cấu hình lõi (Database, Redis, Settings)
│   │   ├── config.py                       # Biến môi trường & cấu hình bảo mật
│   │   ├── database.py                     # Database Engine & Session Generator
│   │   └── redis.py                        # Redis Client kết nối Cache/Lock
│   ├── models/                             # SQLModel Entities (Bảng Database)
│   │   ├── booking.py                      # Bảng bookings & booking_seats
│   │   ├── cinema_room.py                  # Bảng cinema_rooms (phòng chiếu)
│   │   ├── film.py                         # Bảng films (phim chiếu)
│   │   ├── payment.py                      # Bảng payments (giao dịch thanh toán)
│   │   ├── seat.py                         # Bảng seats (thông tin ghế vật lý)
│   │   ├── seat_status.py                  # Bảng seat_status (trạng thái HOLD/BOOKED kèm version OCC)
│   │   ├── seat_type.py                    # Bảng seat_types (loại ghế & giá gốc)
│   │   ├── showtime.py                     # Bảng showtimes (suất chiếu)
│   │   ├── theater.py                      # Bảng theaters (cụm rạp)
│   │   └── user.py                         # Bảng users & vai trò
│   ├── repositories/                       # Tầng truy cập dữ liệu (Data Access Layer)
│   │   ├── auth_repo.py                    # Truy vấn tài khoản & refresh token
│   │   ├── booking_repo.py                 # Tạo đơn đặt vé, liên kết ghế & booking
│   │   ├── cinema_room_repo.py             # Truy vấn phòng chiếu
│   │   ├── film_repo.py                    # Truy vấn phim, lọc phim đang/sắp chiếu
│   │   ├── payment_repo.py                 # Lưu vết giao dịch thanh toán
│   │   ├── seat_repo.py                    # Khóa ghế Optimistic Concurrency & kiểm tra trạng thái
│   │   ├── seat_type_repo.py               # Truy vấn loại ghế & giá
│   │   ├── showtime_repo.py                # Truy vấn suất chiếu theo rạp, phim, ngày
│   │   └── theater_repo.py                 # Truy vấn cụm rạp & rạp theo phim
│   ├── router/                             # API Endpoints (Controllers)
│   │   ├── auth.py                         # /auth (login, register, me, logout, refresh)
│   │   ├── booking.py                      # /bookings (tạo đơn đặt vé, lịch sử đặt vé)
│   │   ├── cinema_room.py                  # /cinema_rooms (danh sách phòng chiếu)
│   │   ├── film.py                         # /films (danh sách phim, chi tiết)
│   │   ├── payment.py                      # /payment (tạo link VNPay, verify chữ ký, IPN, xem trạng thái)
│   │   ├── seat.py                         # /seats (sơ đồ ghế bảo mật, hold, release, cancel-hold)
│   │   ├── seat_type.py                    # /seat-types (quản lý loại ghế)
│   │   ├── showtime.py                     # /showtimes (lịch chiếu phim theo rạp & ngày)
│   │   └── theater.py                      # /theater (danh sách cụm rạp)
│   ├── schemas/                            # DTO / Pydantic Request & Response Schemas
│   │   ├── auth.py, booking.py, cinema_room.py, film.py
│   │   ├── payment.py, seat.py, seat_type.py, showtime.py, theater.py
│   ├── services/                           # Tầng nghiệp vụ xử lý logic (Business Layer)
│   │   ├── auth_service.py
│   │   ├── booking_service.py              # Kiểm tra quyền sở hữu ghế hold trước khi đặt vé
│   │   ├── cinema_room_service.py
│   │   ├── film_service.py
│   │   ├── payment_service.py              # Xử lý giao dịch VNPay, chuyển HOLD sang BOOKED an toàn
│   │   ├── seat_service.py                 # Điều phối khóa 2 lớp (Redis Lock + DB Backup)
│   │   ├── seat_type_service.py
│   │   ├── showtime_service.py
│   │   └── theater_service.py
│   ├── utils/                              # Tiện ích bảo mật, Enums & Dependencies
│   │   ├── dependencies.py                 # get_current_user, get_optional_current_user, require_staff
│   │   ├── enum.py                         # UserRole, SeatStatusEnum, PaymentStatus, BookingStatus
│   │   ├── redis_lock.py                   # Quản lý khóa phân tán Redis (Atomic SET NX, Lua Scripts)
│   │   └── security.py                     # Hashing bcrypt & JWT generator
│   └── worker/                             # Celery Worker Tasks
│       ├── celery_app.py                   # Cấu hình Celery & Redis Broker
│       └── tasks.py                        # Task giải phóng ghế quá hạn & gửi email vé
├── tests/                                  # Unit & Contract Test Suite
│   ├── test_auth_contract.py               # Contract test cho Auth & Token
│   ├── test_booking_flow_contract.py       # Contract test cho luồng Booking
│   ├── test_film_contract.py               # Contract test cho Phim & chống N+1
│   ├── test_payment_contract.py            # Contract test cho VNPay & chữ ký bảo mật
│   ├── test_seat_lock_contract.py          # Contract test cho Khóa ghế, OCC & ẩn ID bảo mật (#34)
│   └── test_theater_contract.py            # Contract test cho Rạp & Phòng
├── alembic.ini                             # Cấu hình kết nối Alembic
├── docker-compose.yml                      # Điều phối 7 containers môi trường hoàn chỉnh
├── Dockerfile                              # Docker image cho FastAPI Backend
├── main.py                                 # Entrypoint chính của ứng dụng FastAPI
├── requirements.txt                        # Danh sách thư viện Python
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Khởi chạy bằng Docker Compose (Khuyến nghị)

```bash
# 1. Di chuyển vào thư mục Backend
cd Backend

# 2. Tạo file biến môi trường từ mẫu
cp .env.example .env

# 3. Khởi chạy toàn bộ hệ thống (FastAPI, PostgreSQL, Redis, Celery Worker, Celery Beat, Flower, PgAdmin)
docker compose up -d --build

# 4. Áp dụng toàn bộ Database Migrations
docker compose exec fastapi alembic upgrade head
```

### 2. Khởi chạy thủ công (Local Python Development)

Yêu cầu máy cục bộ đã chạy PostgreSQL và Redis:

```bash
cd Backend

# 1. Tạo và kích hoạt môi trường ảo
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell/CMD
# source .venv/bin/activate # Linux/macOS

# 2. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 3. Cập nhật cấu hình DB và Redis trong file .env
cp .env.example .env

# 4. Áp dụng Database Migrations
alembic upgrade head

# 5. Khởi động server FastAPI với auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Khởi chạy Celery Worker (ở terminal riêng nếu chạy local):
```bash
celery -A app.worker.celery_app.celery_app worker --loglevel=info -P solo
```

---

## 🔐 Cơ Chế Kỹ Thuật Nổi Bật

### 1. Khóa Ghế Tránh Trùng Lặp 2 Lớp (Dual-layer Seat Locking)
- **Lớp 1 (Redis Distributed Lock)**: Sử dụng lệnh nguyên tử `SET key val NX EX 600` cùng các Lua script kiểm tra sở hữu để gia hạn hoặc hủy giữ ghế với TTL 10 phút.
- **Lớp 2 (Database Optimistic Concurrency Control - OCC)**: Bảng `seat_status` có cột `version`. Mọi thao tác cập nhật trạng thái (`HOLD` -> `BOOKED` hoặc hủy giữ) đều kiểm tra phiên bản `version` và người giữ hợp lệ, loại bỏ hoàn toàn race condition khi nhiều người dùng cùng chọn một ghế.

### 2. Bảo Mật Trạng Thái Ghế Công Khai (Issue #34)
- Endpoint công khai `GET /seats/showtime/{showtime_id}` sử dụng dependency `get_optional_current_user`.
- Hệ thống **hoàn toàn không trả về `hold_by_user_id`** ra public response, thay vào đó trả về trường boolean `is_held_by_me` tương ứng với tài khoản đang đăng nhập, bảo vệ thông tin riêng tư của người dùng.

### 3. Tích Hợp Cổng Thanh Toán VNPay
- Tạo URL thanh toán Sandbox với mã hóa và ký điện tử an toàn **HMAC SHA512**.
- Xác minh chữ ký `vnp_SecureHash` chặt chẽ tại Return URL và IPN webhook trước khi cập nhật trạng thái đơn hàng và chuyển ghế sang `BOOKED`.

---

## 📡 Danh Sách API Endpoints Chính

| Phương thức | Endpoint | Mô tả | Quyền truy cập |
|:---|:---|:---|:---|
| **POST** | `/auth/register` | Đăng ký tài khoản mới | Công khai |
| **POST** | `/auth/login` | Đăng nhập nhận Access & Refresh Token | Công khai |
| **GET** | `/auth/me` | Lấy thông tin tài khoản hiện tại | Đăng nhập |
| **POST** | `/auth/logout` | Đăng xuất, đưa token vào Redis blacklist | Đăng nhập |
| **GET** | `/films` | Danh sách phim (hỗ trợ lọc `now_showing`) | Công khai |
| **GET** | `/films/{id}` | Xem chi tiết phim | Công khai |
| **GET** | `/theater` | Danh sách cụm rạp, lọc theo phim | Công khai |
| **GET** | `/showtimes` | Lịch chiếu phim theo rạp & ngày | Công khai |
| **GET** | `/seats/showtime/{id}` | Sơ đồ & trạng thái ghế (có `is_held_by_me`) | Công khai / Tùy chọn Auth |
| **POST** | `/seats/hold` | Giữ ghế xem phim (TTL 10 phút) | Đăng nhập |
| **POST** | `/seats/release` | Hủy giữ ghế đã chọn | Đăng nhập |
| **POST** | `/bookings` | Tạo đơn đặt vé từ các ghế đang HOLD hợp lệ | Đăng nhập |
| **GET** | `/bookings/my-bookings`| Danh sách vé đã đặt của người dùng | Đăng nhập |
| **POST** | `/payment/create-payment-url` | Sinh URL thanh toán VNPay | Đăng nhập |
| **GET** | `/payment/vnpay-return` | Xác thực kết quả thanh toán từ VNPay | Công khai |

---

## 🧪 Chạy Kiểm Thử (Testing)

```bash
# Chạy toàn bộ 45 contract & unit tests
pytest

# Chạy có hiển thị chi tiết từng test case
pytest -v
```
