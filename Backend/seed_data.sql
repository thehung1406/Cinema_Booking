-- ==============================================================================
-- CINEMA BOOKING SAMPLE SEED DATA (PostgreSQL)
-- Database: cinema_booking
-- Password for all seed users: password123
-- (Bcrypt hash: $2b$12$e8x5G7mR0f7.w40YmHlA1.zLqN34/E5K2w7h0q5i3pG1i4eS3n0q2)
-- ==============================================================================

-- 1. USERS
-- ==============================================================================
INSERT INTO users (id, username, password, email, phone, full_name, avatar, role, created_at)
VALUES
(1, 'admin', '$2b$12$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'admin@cinemabooking.com', '0901234567', 'System Administrator', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=300&q=80', 'ADMIN', NOW()),
(2, 'nguyenvana', '$2b$12$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'nguyenvana@gmail.com', '0912345678', 'Nguyễn Văn A', 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=300&q=80', 'USER', NOW()),
(3, 'tranthib', '$2b$12$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'tranthib@gmail.com', '0987654321', 'Trần Thị B', 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=300&q=80', 'USER', NOW())
ON CONFLICT (id) DO NOTHING;

-- 2. THEATERS
-- ==============================================================================
INSERT INTO theaters (id, name, address, city, image, rating, technologies, special)
VALUES
(1, 'CGV Vincom Landmark 81', 'Tầng B1, Vincom Center Landmark 81, 720A Điện Biên Phủ, P. 22, Q. Bình Thạnh', 'TP. Hồ Chí Minh', 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80', 4.8, '{"imax": true, "4dx": true, "dolby_atmos": true}', 'IMAX Laser'),
(2, 'CGV Crescent Mall', 'Tầng 5, Crescent Mall, 101 Tôn Dật Tiên, P. Tân Phú, Quận 7', 'TP. Hồ Chí Minh', 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?auto=format&fit=crop&w=600&q=80', 4.6, '{"gold_class": true, "starium": true}', 'Gold Class'),
(3, 'BHD Star Bitexco', 'Tầng 3 & 4, Bitexco Financial Tower, 2 Hải Triều, Bến Nghé, Quận 1', 'TP. Hồ Chí Minh', 'https://images.unsplash.com/photo-1574267432553-4b4628081c31?auto=format&fit=crop&w=600&q=80', 4.5, '{"3d": true, "first_class": true}', 'First Class')
ON CONFLICT (id) DO NOTHING;

-- 3. CINEMA ROOMS
-- ==============================================================================
INSERT INTO cinema_rooms (id, theater_id, name, capacity, room_type)
VALUES
(1, 1, 'Cinema 01 (IMAX)', 40, 'IMAX'),
(2, 1, 'Cinema 02 (Standard)', 40, '2D/3D Standard'),
(3, 2, 'Cinema 01 (Gold Class)', 24, 'Gold Class'),
(4, 3, 'Cinema 01 (Prime)', 40, 'Standard')
ON CONFLICT (id) DO NOTHING;

-- 4. SEAT TYPES (Per Room)
-- ==============================================================================
INSERT INTO seat_types (id, room_id, name, base_price)
VALUES
-- Room 1 (IMAX)
(1, 1, 'Standard', 130000.00),
(2, 1, 'VIP', 160000.00),
(3, 1, 'Couple', 300000.00),
-- Room 2 (Standard)
(4, 2, 'Standard', 90000.00),
(5, 2, 'VIP', 110000.00),
(6, 2, 'Couple', 220000.00),
-- Room 3 (Gold Class)
(7, 3, 'VIP', 250000.00),
(8, 3, 'Couple', 500000.00),
-- Room 4 (Prime)
(9, 4, 'Standard', 85000.00),
(10, 4, 'VIP', 105000.00)
ON CONFLICT (id) DO NOTHING;

-- 5. SEATS (Room 1 & Room 2: 40 seats each - Rows A to D, Cols 1 to 10)
-- ==============================================================================
-- Room 1: Row A, B = Standard (id:1), Row C = VIP (id:2), Row D = Couple (id:3)
INSERT INTO seats (room_id, seat_type_id, seat_name) VALUES
(1, 1, 'A01'), (1, 1, 'A02'), (1, 1, 'A03'), (1, 1, 'A04'), (1, 1, 'A05'), (1, 1, 'A06'), (1, 1, 'A07'), (1, 1, 'A08'), (1, 1, 'A09'), (1, 1, 'A10'),
(1, 1, 'B01'), (1, 1, 'B02'), (1, 1, 'B03'), (1, 1, 'B04'), (1, 1, 'B05'), (1, 1, 'B06'), (1, 1, 'B07'), (1, 1, 'B08'), (1, 1, 'B09'), (1, 1, 'B10'),
(1, 2, 'C01'), (1, 2, 'C02'), (1, 2, 'C03'), (1, 2, 'C04'), (1, 2, 'C05'), (1, 2, 'C06'), (1, 2, 'C07'), (1, 2, 'C08'), (1, 2, 'C09'), (1, 2, 'C10'),
(1, 3, 'D01'), (1, 3, 'D02'), (1, 3, 'D03'), (1, 3, 'D04'), (1, 3, 'D05'), (1, 3, 'D06'), (1, 3, 'D07'), (1, 3, 'D08'), (1, 3, 'D09'), (1, 3, 'D10');

-- Room 2: Row A, B = Standard (id:4), Row C = VIP (id:5), Row D = Couple (id:6)
INSERT INTO seats (room_id, seat_type_id, seat_name) VALUES
(2, 4, 'A01'), (2, 4, 'A02'), (2, 4, 'A03'), (2, 4, 'A04'), (2, 4, 'A05'), (2, 4, 'A06'), (2, 4, 'A07'), (2, 4, 'A08'), (2, 4, 'A09'), (2, 4, 'A10'),
(2, 4, 'B01'), (2, 4, 'B02'), (2, 4, 'B03'), (2, 4, 'B04'), (2, 4, 'B05'), (2, 4, 'B06'), (2, 4, 'B07'), (2, 4, 'B08'), (2, 4, 'B09'), (2, 4, 'B10'),
(2, 5, 'C01'), (2, 5, 'C02'), (2, 5, 'C03'), (2, 5, 'C04'), (2, 5, 'C05'), (2, 5, 'C06'), (2, 5, 'C07'), (2, 5, 'C08'), (2, 5, 'C09'), (2, 5, 'C10'),
(2, 6, 'D01'), (2, 6, 'D02'), (2, 6, 'D03'), (2, 6, 'D04'), (2, 6, 'D05'), (2, 6, 'D06'), (2, 6, 'D07'), (2, 6, 'D08'), (2, 6, 'D09'), (2, 6, 'D10');

-- 6. FILMS
-- ==============================================================================
INSERT INTO films (id, title, image, rating, duration, genre, language, subtitle, formats, release_date, end_date, description, trailer)
VALUES
(
  1, 
  'Dune: Hành Tinh Cát - Phần 2', 
  'https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=80', 
  'T16', 
  '166 phút', 
  'Hành động, Khoa học viễn tưởng, Phiêu lưu', 
  'Tiếng Anh', 
  'Phụ đề Tiếng Việt', 
  '{"2D": true, "IMAX": true}', 
  CURRENT_DATE - INTERVAL '10 days', 
  CURRENT_DATE + INTERVAL '30 days', 
  'Hành trình của Paul Atreides khi anh hợp nhất với Chani và người Fremen để trả thù những kẻ đã hủy hoại gia đình mình.', 
  'https://www.youtube.com/watch?v=Way9Dexny3w'
),
(
  2, 
  'Mai', 
  'https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=600&q=80', 
  'T18', 
  '131 phút', 
  'Tâm lý, Tình cảm', 
  'Tiếng Việt', 
  'Phụ đề Tiếng Anh', 
  '{"2D": true}', 
  CURRENT_DATE - INTERVAL '5 days', 
  CURRENT_DATE + INTERVAL '25 days', 
  'Câu chuyện về cuộc đời của Mai, một người phụ nữ massage chịu nhiều định kiến xã hội, và chuyện tình dang dở với Dương.', 
  'https://www.youtube.com/watch?v=cM7d76_V1H8'
),
(
  3, 
  'Kung Fu Panda 4', 
  'https://images.unsplash.com/photo-1579546929518-9e396f3cc809?auto=format&fit=crop&w=600&q=80', 
  'P', 
  '94 phút', 
  'Hoạt hình, Hành động, Hài hước', 
  'Tiếng Anh / Lồng tiếng', 
  'Phụ đề Tiếng Việt', 
  '{"2D": true, "3D": true}', 
  CURRENT_DATE, 
  CURRENT_DATE + INTERVAL '40 days', 
  'Po phải tìm kiếm và huấn luyện một Thần Long Đại Hiệp mới trong khi đối mặt với phù thủy độc ác Tắc Kè Bông.', 
  'https://www.youtube.com/watch?v=_inKs4eeHiI'
),
(
  4, 
  'Godzilla x Kong: Đế Chế Mới', 
  'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=600&q=80', 
  'T13', 
  '115 phút', 
  'Hành động, Khoa học viễn tưởng', 
  'Tiếng Anh', 
  'Phụ đề Tiếng Việt', 
  '{"2D": true, "IMAX": true, "3D": true}', 
  CURRENT_DATE - INTERVAL '2 days', 
  CURRENT_DATE + INTERVAL '35 days', 
  'Hai quái thú huyền thoại Godzilla và Kong buộc phải bắt tay nhau chống lại mối đe dọa khổng lồ ẩn sâu trong Trái Đất Rỗng.', 
  'https://www.youtube.com/watch?v=lV1OOlGwExg'
)
ON CONFLICT (id) DO NOTHING;

-- 7. SHOWTIMES
-- ==============================================================================
INSERT INTO showtimes (id, film_id, room_id, show_date, start_time, end_time, format, status)
VALUES
(1, 1, 1, CURRENT_DATE, '09:30:00', '12:16:00', 'IMAX 2D', 'ACTIVE'),
(2, 1, 1, CURRENT_DATE, '14:00:00', '16:46:00', 'IMAX 2D', 'ACTIVE'),
(3, 1, 1, CURRENT_DATE, '19:30:00', '22:16:00', 'IMAX 2D', 'ACTIVE'),
(4, 2, 2, CURRENT_DATE, '10:00:00', '12:11:00', '2D Standard', 'ACTIVE'),
(5, 2, 2, CURRENT_DATE, '15:30:00', '17:41:00', '2D Standard', 'ACTIVE'),
(6, 3, 2, CURRENT_DATE, '18:00:00', '19:34:00', '2D Standard', 'ACTIVE'),
(7, 4, 1, CURRENT_DATE + INTERVAL '1 day', '13:00:00', '14:55:00', 'IMAX 3D', 'ACTIVE'),
(8, 4, 1, CURRENT_DATE + INTERVAL '1 day', '19:00:00', '20:55:00', 'IMAX 3D', 'ACTIVE')
ON CONFLICT (id) DO NOTHING;

-- 8. SEAT STATUS (Khởi tạo trạng thái ghế cho Showtime 1)
-- ==============================================================================
-- Ghế cho Showtime 1 (Room 1): Ghế C05, C06 đã BOOKED, các ghế khác AVAILABLE
INSERT INTO seat_status (seat_id, showtime_id, status, version, created_at, updated_at)
SELECT s.id, 1, 
       CASE 
         WHEN s.seat_name IN ('C05', 'C06') THEN 'BOOKED'
         ELSE 'AVAILABLE'
       END,
       0, NOW(), NOW()
FROM seats s
WHERE s.room_id = 1
ON CONFLICT (showtime_id, seat_id) DO NOTHING;

-- 9. BOOKING & BOOKING DETAILS (Mẫu 1 đơn đặt vé đã hoàn tất)
-- ==============================================================================
INSERT INTO bookings (id, user_id, showtime_id, booking_date, total_amount, payment_method, payment_status, booking_status, created_at)
VALUES
(1, 2, 1, NOW() - INTERVAL '2 hours', 320000.00, 'VNPAY', 'SUCCESS', 'CONFIRMED', NOW() - INTERVAL '2 hours')
ON CONFLICT (id) DO NOTHING;

-- Chi tiết vé cho 2 ghế C05 và C06 của Showtime 1
INSERT INTO booking_details (booking_id, seat_id, price)
SELECT 1, s.id, 160000.00
FROM seats s
WHERE s.room_id = 1 AND s.seat_name IN ('C05', 'C06')
ON CONFLICT DO NOTHING;

-- Reset Sequences cho các bảng để tránh trùng ID khi insert mới
SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM users));
SELECT setval('theaters_id_seq', (SELECT COALESCE(MAX(id), 1) FROM theaters));
SELECT setval('cinema_rooms_id_seq', (SELECT COALESCE(MAX(id), 1) FROM cinema_rooms));
SELECT setval('seat_types_id_seq', (SELECT COALESCE(MAX(id), 1) FROM seat_types));
SELECT setval('seats_id_seq', (SELECT COALESCE(MAX(id), 1) FROM seats));
SELECT setval('films_id_seq', (SELECT COALESCE(MAX(id), 1) FROM films));
SELECT setval('showtimes_id_seq', (SELECT COALESCE(MAX(id), 1) FROM showtimes));
SELECT setval('seat_status_id_seq', (SELECT COALESCE(MAX(id), 1) FROM seat_status));
SELECT setval('bookings_id_seq', (SELECT COALESCE(MAX(id), 1) FROM bookings));
SELECT setval('booking_details_id_seq', (SELECT COALESCE(MAX(id), 1) FROM booking_details));
