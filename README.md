# 🎬 Cinema Booking System

Hệ thống Đặt vé Xem phim Trực tuyến Fullstack xây dựng theo kiến trúc **Monorepo** kết hợp **FastAPI** (Backend) + **React Vite** (Frontend) + **PostgreSQL 15** + **Redis 7** + **Celery Worker**.

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

| Phân hệ | Công nghệ |
|:---|:---|
| **Backend** | Python 3.12, FastAPI, SQLModel / SQLAlchemy, Pydantic, Alembic |
| **Frontend** | React 18, Vite, React Router, Axios, CSS Modules / Vanilla CSS |
| **Database & Cache** | PostgreSQL 15, Redis 7 (Token Blacklist & Real-time Seat Lock) |
| **Background Tasks** | Celery Worker, Celery Beat, Flower UI Dashboard |
| **DevOps & Container** | Docker, Docker Compose, Git Workflow |

---

## 📁 Cấu Trúc Dự Án Hiện Tại (Repository Structure)

```text
Cinema_Booking/
├── Backend/                                # Backend FastAPI Project
│   ├── alembic/                            # Quản lý Database Migrations
│   │   ├── versions/
│   │   │   ├── 001_initial_migration.py    # Khởi tạo schema ban đầu
│   │   │   ├── 002_optimize_indexes_types_cascade.py # Composite index & Numeric
│   │   │   └── 003_add_seat_type_table.py  # Bảng seat_types & normalize giá ghế
│   │   └── env.py
│   ├── app/
│   │   ├── core/                           # Cấu hình cốt lõi (Config, DB Engine, Redis)
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── redis.py
│   │   ├── models/                         # Database Models (SQLModel)
│   │   │   └── user.py                     # Model bảng users
│   │   ├── repositories/                   # Tầng truy vấn Database (Data Access)
│   │   │   └── auth_repo.py
│   │   ├── router/                         # API Endpoints (Controllers)
│   │   │   └── auth.py                     # Router /auth (login, register, me, logout)
│   │   ├── schemas/                        # DTO / Pydantic Request & Response
│   │   │   └── auth.py
│   │   ├── services/                       # Business Logic Layer
│   │   │   └── auth_service.py
│   │   └── utils/                          # Tiện ích bảo mật & dependencies
│   │       ├── dependencies.py             # Auth middleware (get_current_user, require_staff)
│   │       ├── enum.py                     # Enum phân quyền (UserRole)
│   │       └── security.py                 # Bcrypt password hashing & JWT utils
│   ├── .dockerignore
│   ├── .gitignore
│   ├── alembic.ini                         # Cấu hình kết nối Alembic
│   ├── docker-compose.yml                  # Điều phối 7 containers (App, DB, Redis, Celery...)
│   ├── Dockerfile
│   ├── main.py                             # Entrypoint khởi chạy ứng dụng FastAPI
│   ├── requirements.txt                    # Danh sách thư viện Python
│   └── test_main.http                      # HTTP request template để test API nhanh
├── Frontend/                               # Frontend React + Vite Project
│   ├── public/
│   │   ├── CGV incon.png
│   │   └── vite.svg
│   ├── src/
│   │   ├── assets/
│   │   ├── components/                     # React UI Components
│   │   │   ├── LoginPage.jsx               # Giao diện Đăng nhập / Đăng ký
│   │   │   ├── MainHomePage.jsx            # Header/Navbar & Auth state
│   │   │   └── UserInfor.jsx               # Quản lý tài khoản & đổi mật khẩu
│   │   ├── config/
│   │   │   └── api.js                      # Axios instance + Bearer token interceptor
│   │   ├── App.css
│   │   ├── App.jsx                         # Cấu hình Router Frontend
│   │   ├── index.css
│   │   └── main.jsx                        # Entrypoint render React DOM
│   ├── eslint.config.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .gitignore                              # Root gitignore bao quát cả Monorepo
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Dự Án (Quick Start)

### 1. Yêu cầu môi trường
- **Docker & Docker Compose** (khuyến nghị)
- **Node.js** >= 18.x
- **Python** >= 3.11 (nếu chạy không dùng Docker)

---

### 2. Khởi chạy Backend với Docker (Khuyến nghị)

```bash
# Di chuyển vào thư mục Backend
cd Backend

# Khởi chạy toàn bộ dịch vụ (FastAPI, PostgreSQL, Redis, Celery, PgAdmin)
docker compose up -d --build

# Chạy Database Migrations mới nhất
docker compose exec fastapi alembic upgrade head
```

---

### 3. Khởi chạy Backend thủ công (Local Python)

```bash
cd Backend

# 1. Tạo và kích hoạt môi trường ảo
python -m venv .venv
.venv\Scripts\activate   # Trên Windows
# source .venv/bin/activate # Trên Linux/macOS

# 2. Cài đặt thư viện
pip install -r requirements.txt

# 3. Chạy migrations database
alembic upgrade head

# 4. Khởi động server FastAPI
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### 4. Khởi chạy Frontend (React + Vite)

```bash
# Mở một terminal mới và di chuyển vào Frontend
cd Frontend

# 1. Cài đặt các gói phụ thuộc
npm install

# 2. Chạy môi trường phát triển (Dev server)
npm run dev
# Truy cập tại: http://localhost:5173
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

## 📋 Danh Sách Module & Tiến Độ Hiện Tại

| Mã Module | Tên Module | Trạng thái trên `main` |
|:---:|:---|:---:|
| `MOD-01` | **Quản lý Xác thực & Tài khoản (Auth & User)** | ✅ **Đã hoàn thành** |
| `MOD-02` | **Quản lý Phim & Danh mục (Movie Management)** | ⏳ Đang tích hợp |
| `MOD-03` | **Quản lý Cụm Rạp & Phòng Chiếu (Theaters & Rooms)** | ⏳ Đang tích hợp |
| `MOD-04` | **Quản lý Suất Chiếu (Showtimes Scheduling)** | ⏳ Đang tích hợp |
| `MOD-05` | **Quản lý Loại Ghế & Giữ Ghế Real-time (Seats & Redis Lock)** | ⏳ Đang tích hợp |
| `MOD-06` | **Quản lý Đặt Vé & Đơn Hàng (Booking Management)** | ⏳ Đang tích hợp |
| `MOD-07` | **Tích hợp Cổng Thanh Toán VNPay (Payment Gateway)** | ⏳ Đang tích hợp |
| `MOD-08` | **Xử lý Nền & Gửi Email Vé (Celery & Background Tasks)** | ⏳ Đang tích hợp |
| `MOD-09` | **Giao diện Cổng Thông Tin & Trang Tĩnh (Portal & UI)** | ⏳ Đang tích hợp |
| `MOD-10` | **Hạ Tầng, Database & DevOps (Infra & Database)** | ✅ **Đã hoàn thành** |
