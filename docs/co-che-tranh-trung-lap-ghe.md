# Cơ Chế Tránh Trùng Lặp Ghế (Seat Double-Booking Prevention)

## Bối cảnh & Vấn đề

Hệ thống Cinema Booking hiện tại sử dụng **Redis Soft Lock với TTL 10 phút** để giữ ghế tạm thời khi người dùng chọn ghế. Cơ chế này hoạt động tốt trong điều kiện bình thường, nhưng tồn tại **3 lỗ hổng** có thể dẫn đến tình trạng **2 người cùng đặt được 1 ghế (Double Booking)**:

Tại sao cần kết hợp cả Redis Lock và DB Optimistic Lock?

Nếu chỉ dùng Redis: Redis chạy trên RAM và có thể bị restart/crash. Nếu Redis khởi động lại trong lúc User A đang thanh toán (10 phút giữ ghế), toàn bộ lock tạm thời sẽ mất. User B có thể nhảy vào đặt và thanh toán trùng ghế với User A $\rightarrow$ Gây Double Booking.
Nếu chỉ dùng DB Optimistic Lock: Sẽ không có cơ chế "giữ ghế tạm thời" nhẹ và nhanh. Khi có nhiều người cùng xem sơ đồ ghế, họ đều thấy ghế trống và cùng tiến hành thanh toán. Đến bước cuối cùng, chỉ 1 người thành công và hàng loạt người khác bị báo lỗi thất bại $\rightarrow$ UX rất tệ và gây áp lực lớn lên Database.
$\Rightarrow$ Kết luận: Redis Lock làm lớp "khiên mềm" ở tiền tuyến (tốc độ cao, giữ chỗ tạm, phản hồi UI tức thì), còn DB Optimistic Lock làm "chốt chặn cứng" ở hậu phương (đảm bảo tính toàn vẹn dữ liệu, bền vững ngay cả khi tầng cache gặp sự cố).

### Lỗ hổng 1: `lock_seat()` không nguyên tử (Race Condition)

Hàm `lock_seat()` trong `redis_lock.py` hiện tại dùng **GET rồi SET** (2 bước tách rời). Giữa 2 bước này, request khác có thể chen vào.

```
User A: GET key → null (chưa ai lock)
                                          User B: GET key → null (chưa ai lock)
User A: SETEX key → OK ✅
                                          User B: SETEX key → OK ✅ (ghi đè User A!)
→ Cả 2 đều nghĩ mình đang giữ ghế → Double Booking ❌
```

**Fix:** Dùng `SET key value NX EX ttl` — lệnh nguyên tử của Redis, chỉ ghi nếu key chưa tồn tại.

---

### Lỗ hổng 2: Redis sập → mất toàn bộ lock

Nếu Redis restart hoặc sập giữa chừng, tất cả key biến mất. Mọi ghế đang HOLD đều trở thành AVAILABLE → User mới có thể hold lại ghế mà User cũ vẫn đang thanh toán.

Hiện tại **không có lớp bảo vệ nào ở tầng Database** cho bước HOLD. Hàm `hold_seats()` trong `seat_service.py` chỉ check DB xem ghế đã `BOOKED` chưa, **không ghi trạng thái HOLD vào DB**.

**Fix:** Ghi `status = 'HOLD'` vào bảng `seat_status` song song với Redis, dùng **Optimistic Lock (cột `version`)** để tránh 2 user cùng hold 1 ghế.

---

### Lỗ hổng 3: Unlock không nguyên tử (Unsafe Unlock)

Hàm `unlock_seat()` trong `redis_lock.py` dùng GET để check ownership rồi DELETE — 2 bước tách rời. User A có thể xóa nhầm lock của User B nếu TTL hết đúng giữa 2 bước.

```
User A: GET key → {"user_id": A} (đúng, của mình)
                                    TTL hết → key tự xóa
                                    User B: SET NX key → OK (lock mới của B)
User A: DELETE key → Xóa mất lock của B! ❌
```

**Fix:** Dùng **Lua script** để đảm bảo check + delete trong 1 lệnh nguyên tử.

---

## Kiến trúc phòng thủ đề xuất: 3 lớp bảo vệ

```
┌─────────────────────────────────────────────────────────────┐
│  Lớp 1: Redis Atomic Lock (SET NX EX)                      │
│  ├── Chặn 99% tranh chấp, tốc độ < 1ms                    │
│  ├── TTL tự release sau 10 phút                            │
│  └── Lua script unlock đảm bảo ownership                   │
├─────────────────────────────────────────────────────────────┤
│  Lớp 2: DB Optimistic Lock (version column)                │
│  ├── Phòng khi Redis sập hoặc race condition               │
│  ├── UPDATE ... WHERE status='AVAILABLE' AND version=?     │
│  └── UNIQUE constraint (showtime_id, seat_id) chặn INSERT  │
├─────────────────────────────────────────────────────────────┤
│  Lớp 3: Celery Cleanup + Lazy Check                        │
│  ├── Celery Beat mỗi 60s: dọn HOLD quá hạn trong DB       │
│  └── Lazy check: query ghế → nếu HOLD hết hạn → AVAILABLE │
└─────────────────────────────────────────────────────────────┘
```

---

## Chi tiết thay đổi

### Lớp 1 — Redis Atomic Lock

#### `Backend/app/utils/redis_lock.py`

**1.1. Sửa `lock_seat()` — dùng `SET NX EX` nguyên tử:**

```diff
 def lock_seat(showtime_id, seat_id, user_id, ttl=600):
     key = _get_lock_key(showtime_id, seat_id)
     lock_data = json.dumps({"user_id": user_id, ...})

-    existing_lock = redis_client.get(key)
-    if existing_lock:
-        lock_data_existing = json.loads(existing_lock)
-        if lock_data_existing["user_id"] != user_id:
-            return False
-    redis_client.setex(key, ttl, lock_data)
-    return True

+    # Thử lock nguyên tử (chỉ thành công nếu key chưa tồn tại)
+    success = redis_client.set(key, lock_data, nx=True, ex=ttl)
+    if success:
+        return True
+
+    # Key đã tồn tại — kiểm tra có phải cùng user không
+    existing = redis_client.get(key)
+    if existing:
+        existing_data = json.loads(existing)
+        if existing_data.get("user_id") == user_id:
+            # Cùng user → gia hạn TTL
+            redis_client.setex(key, ttl, lock_data)
+            return True
+    return False
```

**1.2. Sửa `unlock_seat()` — dùng Lua script nguyên tử:**

```diff
+UNLOCK_LUA = """
+local data = redis.call("GET", KEYS[1])
+if data then
+    local lock = cjson.decode(data)
+    if lock["user_id"] == tonumber(ARGV[1]) then
+        return redis.call("DEL", KEYS[1])
+    end
+end
+return 0
+"""

 def unlock_seat(showtime_id, seat_id, user_id=None):
     key = _get_lock_key(showtime_id, seat_id)
-    if user_id is not None:
-        existing_lock = redis_client.get(key)
-        if existing_lock:
-            lock_data = json.loads(existing_lock)
-            if lock_data.get("user_id") != user_id:
-                return False
-    deleted = redis_client.delete(key)

+    if user_id is not None:
+        deleted = redis_client.eval(UNLOCK_LUA, 1, key, user_id)
+    else:
+        deleted = redis_client.delete(key)
     return deleted > 0
```

---

### Lớp 2 — DB Optimistic Lock

#### `Backend/app/models/seat_status.py`

Thêm cột `version` cho Optimistic Locking:

```diff
 class SeatStatus(SQLModel, table=True):
     ...
     status: str = Field(default="AVAILABLE", max_length=20)
+    version: int = Field(default=0)
```

> **Lưu ý:** Cần tạo Alembic migration cho cột `version` mới:
> `alembic revision --autogenerate -m "add version column to seat_status for optimistic locking"`

---

#### `Backend/app/repositories/seat_repo.py`

Thêm hàm `hold_seat_optimistic()` — ghi HOLD vào DB với Optimistic Lock:

```python
@staticmethod
def hold_seat_optimistic(
    db: Session,
    showtime_id: int,
    seat_id: int,
    user_id: int,
    hold_minutes: int = 10
) -> SeatStatus:
    """
    Giữ ghế trong DB với Optimistic Lock.
    Chỉ thành công nếu ghế đang AVAILABLE + version khớp.
    """
    now = datetime.now(timezone.utc)
    expired_at = now + timedelta(minutes=hold_minutes)

    seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)

    if not seat_status:
        # Chưa có record → INSERT mới
        # UNIQUE constraint (showtime_id, seat_id) sẽ chặn nếu bị trùng
        new_status = SeatStatus(
            showtime_id=showtime_id,
            seat_id=seat_id,
            status=SeatStatusEnum.HOLD,
            hold_by_user_id=user_id,
            hold_expired_at=expired_at,
            version=1,
        )
        db.add(new_status)
        db.flush()
        return new_status

    # Đã có record → Optimistic Lock: chỉ update nếu version khớp
    current_version = seat_status.version

    # Cho phép hold nếu: AVAILABLE hoặc HOLD đã hết hạn
    if seat_status.status == SeatStatusEnum.BOOKED:
        raise HTTPException(400, "Ghế đã được đặt")

    if (seat_status.status == SeatStatusEnum.HOLD
            and seat_status.hold_expired_at
            and seat_status.hold_expired_at > now
            and seat_status.hold_by_user_id != user_id):
        raise HTTPException(400, "Ghế đang được giữ bởi người khác")

    result = db.exec(
        update(SeatStatus)
        .where(
            SeatStatus.id == seat_status.id,
            SeatStatus.version == current_version,   # ← Optimistic guard
        )
        .values(
            status=SeatStatusEnum.HOLD,
            hold_by_user_id=user_id,
            hold_expired_at=expired_at,
            version=current_version + 1,
            updated_at=now,
        )
    )

    if result.rowcount == 0:
        raise HTTPException(409, "Ghế vừa bị người khác chọn, vui lòng thử lại")

    db.flush()
    db.refresh(seat_status)
    return seat_status
```

Thêm hàm `book_seat_optimistic()` — chuyển HOLD → BOOKED với guard:

```python
@staticmethod
def book_seat_optimistic(
    db: Session,
    showtime_id: int,
    seat_id: int,
    user_id: int,
) -> SeatStatus:
    """Chuyển ghế từ HOLD → BOOKED chỉ khi đúng user đang giữ."""
    seat_status = SeatRepository.get_seat_status(db, showtime_id, seat_id)

    if not seat_status:
        raise HTTPException(400, "Ghế chưa được giữ")

    current_version = seat_status.version

    result = db.exec(
        update(SeatStatus)
        .where(
            SeatStatus.id == seat_status.id,
            SeatStatus.status == SeatStatusEnum.HOLD,
            SeatStatus.hold_by_user_id == user_id,
            SeatStatus.version == current_version,
        )
        .values(
            status=SeatStatusEnum.BOOKED,
            hold_expired_at=None,
            version=current_version + 1,
            updated_at=datetime.now(timezone.utc),
        )
    )

    if result.rowcount == 0:
        raise HTTPException(409, "Ghế đã bị thay đổi, vui lòng thử lại")

    db.flush()
    db.refresh(seat_status)
    return seat_status
```

---

#### `Backend/app/services/seat_service.py`

Cập nhật `hold_seats()` — ghi cả Redis + DB:

```diff
 for seat_id in seat_ids:
     # ... (validate seat, check BOOKED) ...

     # Lock ghế trong Redis
     lock_success = SeatLockManager.lock_seat(...)

     if not lock_success:
         raise HTTPException(400, "Không thể giữ ghế")

+    # Ghi HOLD vào DB (Optimistic Lock — lớp phòng thủ thứ 2)
+    try:
+        SeatRepository.hold_seat_optimistic(
+            db=db, showtime_id=showtime_id,
+            seat_id=seat_id, user_id=user_id,
+            hold_minutes=hold_minutes
+        )
+    except HTTPException:
+        # DB từ chối → rollback Redis lock
+        SeatLockManager.unlock_seat(showtime_id, seat_id, user_id)
+        raise
```

Cập nhật `get_seats_by_showtime()` — thêm Lazy Check cho HOLD hết hạn:

```diff
 # Ghế đang HOLD trong Redis → hiển thị HOLD
 if seat.id in redis_lock_map:
     ...
     continue

+# Lazy Check: DB có HOLD nhưng đã hết hạn → coi là AVAILABLE
+db_status = hold_map.get(seat.id)
+if db_status and db_status.status == "HOLD":
+    if db_status.hold_expired_at and db_status.hold_expired_at < now:
+        # Hết hạn → coi như AVAILABLE
+        result.append({..., "status": "AVAILABLE"})
+        continue

 # Ghế trống
 result.append({..., "status": "AVAILABLE"})
```

---

### Lớp 3 — Celery Cleanup

#### `Backend/app/worker/tasks.py`

Bổ sung vào task `cleanup_expired_bookings` — dọn ghế HOLD hết hạn trong DB:

```diff
 @celery_app.task
 def cleanup_expired_bookings():
     with Session(engine) as session:
         # --- Phần 1: Hủy booking PENDING quá 10p (đã có) ---
         ...

+        # --- Phần 2: Release ghế HOLD quá hạn trong DB ---
+        now = datetime.utcnow()
+        expired_holds = session.exec(
+            select(SeatStatus).where(
+                SeatStatus.status == SeatStatusEnum.HOLD,
+                SeatStatus.hold_expired_at <= now
+            )
+        ).all()
+
+        hold_count = 0
+        for seat_status in expired_holds:
+            seat_status.status = SeatStatusEnum.AVAILABLE
+            seat_status.hold_by_user_id = None
+            seat_status.hold_expired_at = None
+            seat_status.version = seat_status.version + 1
+            hold_count += 1
+
+        session.commit()
+        logger.info(f"Released {hold_count} expired seat holds from DB")

-        return {"expired_bookings": count}
+        return {"expired_bookings": count, "released_holds": hold_count}
```

---

## Cách release ghế khi hết 10 phút

| Tầng | Ai release? | Độ trễ | Vai trò |
|:---|:---|:---|:---|
| **Redis** | TTL tự xóa | 0 giây (chính xác) | Lớp chính, xử lý 99% trường hợp |
| **DB (Lazy)** | Kiểm tra khi query | 0 giây | Backup khi Redis sập, trả kết quả đúng tức thì |
| **DB (Celery)** | Cronjob mỗi 60s | Tối đa 60s | Dọn record rác, giữ DB sạch |

---

## Verification Plan

### Automated Tests

```bash
# Compile check
python -m compileall -q Backend

# Test hiện có
pytest Backend/tests/

# Migration
alembic upgrade head
```

### Manual Verification

1. **Test nguyên tử Redis:** Mở 2 terminal, gọi API hold cùng 1 ghế cùng lúc → chỉ 1 request thành công.
2. **Test Redis sập:** Dừng Redis container (`docker compose stop redis`), thử hold ghế → DB Optimistic Lock phải chặn double hold.
3. **Test TTL hết hạn:** Hold ghế, đợi 10 phút (hoặc giảm TTL test xuống 30s), kiểm tra ghế tự chuyển về AVAILABLE.
4. **Test Celery cleanup:** Kiểm tra log Celery Beat có `Released X expired seat holds from DB`.

---

## Tổng kết files cần thay đổi

| File | Thay đổi | Mục đích |
|:---|:---|:---|
| `redis_lock.py` | `SET NX EX` + Lua unlock | Fix race condition Redis |
| `seat_status.py` | Thêm cột `version` | Hỗ trợ Optimistic Lock |
| `seat_repo.py` | Thêm `hold_seat_optimistic()`, `book_seat_optimistic()` | DB guard cho HOLD và BOOK |
| `seat_service.py` | Ghi HOLD cả Redis + DB, Lazy Check | 2 lớp bảo vệ + release tức thì |
| `tasks.py` | Dọn HOLD hết hạn trong DB | Giữ DB sạch |
| `alembic/versions/...` | Migration thêm cột `version` | Schema DB |
