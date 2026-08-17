# BackendTTCS

API FastAPI cho hệ thống đặt vé phim, dùng PostgreSQL, Redis để giữ ghế, Celery cho tác vụ nền và VNPay sandbox cho thanh toán.

## Tech stack
- FastAPI + SQLModel, Alembic migrations
- PostgreSQL (persisted volume), pgAdmin để quan sát
- Redis để lock/hold ghế
- Celery worker/beat + Flower dashboard
- VNPay sandbox (tạo URL thanh toán)
- Docker/Docker Compose cho toàn bộ dịch vụ

## Cấu trúc thư mục chính
```
BackendTTCS/
├── main.py                # Khởi tạo FastAPI, khai báo router, CORS
├── app/
│   ├── core/              # Cấu hình, kết nối DB/Redis
│   ├── models/            # SQLModel entities
│   ├── repositories/      # Tầng truy cập dữ liệu
│   ├── services/          # Nghiệp vụ (auth, film, seat, booking, payment,...)
│   ├── router/            # Định nghĩa endpoint FastAPI
│   └── schemas/           # Pydantic schemas / DTO
├── alembic/               # Migrations
├── docker-compose.yml     # Orchestrate Postgres, Redis, FastAPI, Celery, Flower
├── Dockerfile             # Image FastAPI + Alembic
├── requirements.txt       # Dependencies
└── README.md
```

## Chạy nhanh với Docker Compose
Yêu cầu: Docker + Docker Compose.

```bash
docker compose up --build          # build + chạy foreground
docker compose up -d --build       # chạy nền

docker compose logs -f fastapi     # xem log API
docker compose logs -f postgres    # xem log DB
```

Dừng / reset dữ liệu:
```bash
docker compose down                # dừng
docker compose down -v             # dừng và xóa volume (reset DB)
```

Các cổng mặc định: API 8000, PostgreSQL 5434 (host) -> 5432 (container), pgAdmin 5050, Flower 5555, Redis 6379.

## Migrations
- Tạo migration mới: `alembic revision --autogenerate -m "message"`
- Áp dụng: `alembic upgrade head`
- Rollback: `alembic downgrade -1`

## API chính
- Auth: đăng ký, đăng nhập (OAuth2 password), refresh, logout, `GET /auth/me` lấy profile.
- Films: danh sách (lọc now_showing), chi tiết phim.
- Theater & phòng chiếu: danh sách rạp, phòng chiếu theo rạp.
- Showtimes: truy vấn suất chiếu theo phim/rạp/ngày, xem chi tiết.
- Seats: lấy trạng thái ghế, hold ghế bằng Redis với TTL 10 phút, release/cancel.
- Bookings: tạo booking, xem booking của user, cập nhật trạng thái thanh toán.
- Payment: tạo URL thanh toán VNPay sandbox, confirm kết quả, xem trạng thái.

## Ghi chú
- Alembic quản lý schema; `init_db` chỉ giữ tương thích.
- Flower UI theo dõi Celery tại http://localhost:5555.
- Swagger docs: http://localhost:8000/docs, ReDoc: http://localhost:8000/redoc.


