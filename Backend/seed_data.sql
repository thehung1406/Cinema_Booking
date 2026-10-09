BEGIN;
-- ==============================================================================
-- CINEMA BOOKING SAMPLE SEED DATA (PostgreSQL)
-- Schema: 006 (23 application tables). Run on a fresh/demo database only.
-- Password for all seed users: password123
-- ==============================================================================

-- 1. USERS
-- ==============================================================================
INSERT INTO users (id, username, password, email, phone, full_name, avatar, role_id, created_at)
VALUES
(1, 'admin', '$2b$12$2S4VyfOvSb6QjXAM6D5G1eVGbmbIk0/ulMtfHakbgl1bDvQYsFYIi', 'admin@cinemabooking.com', '0901234567', 'System Administrator', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=300&q=80', (SELECT id FROM roles WHERE code='ADMIN'), NOW()),
(2, 'nguyenvana', '$2b$12$2S4VyfOvSb6QjXAM6D5G1eVGbmbIk0/ulMtfHakbgl1bDvQYsFYIi', 'nguyenvana@gmail.com', '0912345678', 'Nguyễn Văn A', 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=300&q=80', (SELECT id FROM roles WHERE code='USER'), NOW()),
(3, 'tranthib', '$2b$12$2S4VyfOvSb6QjXAM6D5G1eVGbmbIk0/ulMtfHakbgl1bDvQYsFYIi', 'tranthib@gmail.com', '0987654321', 'Trần Thị B', 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=300&q=80', (SELECT id FROM roles WHERE code='USER'), NOW())
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
INSERT INTO cinema_rooms (id, theater_id, name, capacity, room_type, status)
VALUES
(1, 1, 'Cinema 01 (IMAX)', 40, 'IMAX', 'ACTIVE'),
(2, 1, 'Cinema 02 (Standard)', 40, '2D/3D Standard', 'ACTIVE'),
(3, 2, 'Cinema 01 (Gold Class)', 24, 'Gold Class', 'ACTIVE'),
(4, 3, 'Cinema 01 (Prime)', 40, 'Standard', 'ACTIVE')
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
INSERT INTO seats (room_id, seat_type_id, seat_name, status) VALUES
(1, 1, 'A01', 'ACTIVE'), (1, 1, 'A02', 'ACTIVE'), (1, 1, 'A03', 'ACTIVE'), (1, 1, 'A04', 'ACTIVE'), (1, 1, 'A05', 'ACTIVE'), (1, 1, 'A06', 'ACTIVE'), (1, 1, 'A07', 'ACTIVE'), (1, 1, 'A08', 'ACTIVE'), (1, 1, 'A09', 'ACTIVE'), (1, 1, 'A10', 'ACTIVE'),
(1, 1, 'B01', 'ACTIVE'), (1, 1, 'B02', 'ACTIVE'), (1, 1, 'B03', 'ACTIVE'), (1, 1, 'B04', 'ACTIVE'), (1, 1, 'B05', 'ACTIVE'), (1, 1, 'B06', 'ACTIVE'), (1, 1, 'B07', 'ACTIVE'), (1, 1, 'B08', 'ACTIVE'), (1, 1, 'B09', 'ACTIVE'), (1, 1, 'B10', 'ACTIVE'),
(1, 2, 'C01', 'ACTIVE'), (1, 2, 'C02', 'ACTIVE'), (1, 2, 'C03', 'ACTIVE'), (1, 2, 'C04', 'ACTIVE'), (1, 2, 'C05', 'ACTIVE'), (1, 2, 'C06', 'ACTIVE'), (1, 2, 'C07', 'ACTIVE'), (1, 2, 'C08', 'ACTIVE'), (1, 2, 'C09', 'ACTIVE'), (1, 2, 'C10', 'ACTIVE'),
(1, 3, 'D01', 'ACTIVE'), (1, 3, 'D02', 'ACTIVE'), (1, 3, 'D03', 'ACTIVE'), (1, 3, 'D04', 'ACTIVE'), (1, 3, 'D05', 'ACTIVE'), (1, 3, 'D06', 'ACTIVE'), (1, 3, 'D07', 'ACTIVE'), (1, 3, 'D08', 'ACTIVE'), (1, 3, 'D09', 'ACTIVE'), (1, 3, 'D10', 'ACTIVE') ON CONFLICT (room_id, seat_name) DO NOTHING;

-- Room 2: Row A, B = Standard (id:4), Row C = VIP (id:5), Row D = Couple (id:6)
INSERT INTO seats (room_id, seat_type_id, seat_name, status) VALUES
(2, 4, 'A01', 'ACTIVE'), (2, 4, 'A02', 'ACTIVE'), (2, 4, 'A03', 'ACTIVE'), (2, 4, 'A04', 'ACTIVE'), (2, 4, 'A05', 'ACTIVE'), (2, 4, 'A06', 'ACTIVE'), (2, 4, 'A07', 'ACTIVE'), (2, 4, 'A08', 'ACTIVE'), (2, 4, 'A09', 'ACTIVE'), (2, 4, 'A10', 'ACTIVE'),
(2, 4, 'B01', 'ACTIVE'), (2, 4, 'B02', 'ACTIVE'), (2, 4, 'B03', 'ACTIVE'), (2, 4, 'B04', 'ACTIVE'), (2, 4, 'B05', 'ACTIVE'), (2, 4, 'B06', 'ACTIVE'), (2, 4, 'B07', 'ACTIVE'), (2, 4, 'B08', 'ACTIVE'), (2, 4, 'B09', 'ACTIVE'), (2, 4, 'B10', 'ACTIVE'),
(2, 5, 'C01', 'ACTIVE'), (2, 5, 'C02', 'ACTIVE'), (2, 5, 'C03', 'ACTIVE'), (2, 5, 'C04', 'ACTIVE'), (2, 5, 'C05', 'ACTIVE'), (2, 5, 'C06', 'ACTIVE'), (2, 5, 'C07', 'ACTIVE'), (2, 5, 'C08', 'ACTIVE'), (2, 5, 'C09', 'ACTIVE'), (2, 5, 'C10', 'ACTIVE'),
(2, 6, 'D01', 'ACTIVE'), (2, 6, 'D02', 'ACTIVE'), (2, 6, 'D03', 'ACTIVE'), (2, 6, 'D04', 'ACTIVE'), (2, 6, 'D05', 'ACTIVE'), (2, 6, 'D06', 'ACTIVE'), (2, 6, 'D07', 'ACTIVE'), (2, 6, 'D08', 'ACTIVE'), (2, 6, 'D09', 'ACTIVE'), (2, 6, 'D10', 'ACTIVE') ON CONFLICT (room_id, seat_name) DO NOTHING;

-- 6. FILMS
-- ==============================================================================
INSERT INTO films (id, title, image, rating, duration_minutes, language, subtitle, release_date, end_date, description, trailer)
VALUES
(
  1, 
  'Dune: Hành Tinh Cát - Phần 2', 
  'https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=80', 
  'T16', 
  166,
  'Tiếng Anh',
  'Phụ đề Tiếng Việt', 
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
  131,
  'Tiếng Việt',
  'Phụ đề Tiếng Anh', 
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
  94,
  'Tiếng Anh / Lồng tiếng',
  'Phụ đề Tiếng Việt', 
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
  115,
  'Tiếng Anh',
  'Phụ đề Tiếng Việt', 
  CURRENT_DATE - INTERVAL '2 days', 
  CURRENT_DATE + INTERVAL '35 days', 
  'Hai quái thú huyền thoại Godzilla và Kong buộc phải bắt tay nhau chống lại mối đe dọa khổng lồ ẩn sâu trong Trái Đất Rỗng.', 
  'https://www.youtube.com/watch?v=lV1OOlGwExg'
)
ON CONFLICT (id) DO NOTHING;

-- Normalized genres and formats; seed after alembic upgrade head.
INSERT INTO genres(name) VALUES ('Hoạt hình') ON CONFLICT (name) DO NOTHING;
INSERT INTO genres(name) VALUES ('Hài hước') ON CONFLICT (name) DO NOTHING;
INSERT INTO genres(name) VALUES ('Hành động') ON CONFLICT (name) DO NOTHING;
INSERT INTO genres(name) VALUES ('Khoa học viễn tưởng') ON CONFLICT (name) DO NOTHING;
INSERT INTO genres(name) VALUES ('Phiêu lưu') ON CONFLICT (name) DO NOTHING;
INSERT INTO genres(name) VALUES ('Tâm lý') ON CONFLICT (name) DO NOTHING;
INSERT INTO genres(name) VALUES ('Tình cảm') ON CONFLICT (name) DO NOTHING;
INSERT INTO formats(code,name) VALUES ('2D','2D') ON CONFLICT (code) DO NOTHING;
INSERT INTO formats(code,name) VALUES ('2D STANDARD','2D Standard') ON CONFLICT (code) DO NOTHING;
INSERT INTO formats(code,name) VALUES ('3D','3D') ON CONFLICT (code) DO NOTHING;
INSERT INTO formats(code,name) VALUES ('IMAX','IMAX') ON CONFLICT (code) DO NOTHING;
INSERT INTO formats(code,name) VALUES ('IMAX 2D','IMAX 2D') ON CONFLICT (code) DO NOTHING;
INSERT INTO formats(code,name) VALUES ('IMAX 3D','IMAX 3D') ON CONFLICT (code) DO NOTHING;
INSERT INTO film_genres SELECT 1, id FROM genres WHERE name='Hành động' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 1, id FROM genres WHERE name='Khoa học viễn tưởng' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 1, id FROM genres WHERE name='Phiêu lưu' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 1, id FROM formats WHERE code='2D' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 1, id FROM formats WHERE code='IMAX' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 2, id FROM genres WHERE name='Tâm lý' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 2, id FROM genres WHERE name='Tình cảm' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 2, id FROM formats WHERE code='2D' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 3, id FROM genres WHERE name='Hoạt hình' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 3, id FROM genres WHERE name='Hành động' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 3, id FROM genres WHERE name='Hài hước' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 3, id FROM formats WHERE code='2D' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 3, id FROM formats WHERE code='3D' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 4, id FROM genres WHERE name='Hành động' ON CONFLICT DO NOTHING;
INSERT INTO film_genres SELECT 4, id FROM genres WHERE name='Khoa học viễn tưởng' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 4, id FROM formats WHERE code='2D' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 4, id FROM formats WHERE code='IMAX' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 4, id FROM formats WHERE code='3D' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 1, id FROM formats WHERE code='IMAX 2D' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 2, id FROM formats WHERE code='2D STANDARD' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 3, id FROM formats WHERE code='2D STANDARD' ON CONFLICT DO NOTHING;
INSERT INTO film_formats SELECT 4, id FROM formats WHERE code='IMAX 3D' ON CONFLICT DO NOTHING;

-- 7. SHOWTIMES
-- ==============================================================================
INSERT INTO showtimes (id, film_id, room_id, show_date, start_time, end_time, format_id, status)
VALUES
(1, 1, 1, CURRENT_DATE, '09:30:00', '12:16:00', (SELECT id FROM formats WHERE code='IMAX 2D'), 'ACTIVE'),
(2, 1, 1, CURRENT_DATE, '14:00:00', '16:46:00', (SELECT id FROM formats WHERE code='IMAX 2D'), 'ACTIVE'),
(3, 1, 1, CURRENT_DATE, '19:30:00', '22:16:00', (SELECT id FROM formats WHERE code='IMAX 2D'), 'ACTIVE'),
(4, 2, 2, CURRENT_DATE, '10:00:00', '12:11:00', (SELECT id FROM formats WHERE code='2D STANDARD'), 'ACTIVE'),
(5, 2, 2, CURRENT_DATE, '15:30:00', '17:41:00', (SELECT id FROM formats WHERE code='2D STANDARD'), 'ACTIVE'),
(6, 3, 2, CURRENT_DATE, '18:00:00', '19:34:00', (SELECT id FROM formats WHERE code='2D STANDARD'), 'ACTIVE'),
(7, 4, 1, CURRENT_DATE + INTERVAL '1 day', '13:00:00', '14:55:00', (SELECT id FROM formats WHERE code='IMAX 3D'), 'ACTIVE'),
(8, 4, 1, CURRENT_DATE + INTERVAL '1 day', '19:00:00', '20:55:00', (SELECT id FROM formats WHERE code='IMAX 3D'), 'ACTIVE')
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
(1, 2, 1, NOW() - INTERVAL '2 hours', 320000.00, 'VNPAY', 'PAID', 'CONFIRMED', NOW() - INTERVAL '2 hours')
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


-- Historical sample transaction and two independently checkable tickets.
INSERT INTO payments(booking_id,provider,payment_method,merchant_ref,amount,currency,status,paid_at,created_at,updated_at)
SELECT b.id,'VNPAY','VNPAY','seed-booking-' || b.id, b.total_amount,'VND','PAID',b.booking_date,b.created_at,b.created_at
FROM bookings b WHERE b.id=1 ON CONFLICT (merchant_ref) DO NOTHING;
INSERT INTO tickets(booking_detail_id,ticket_code,status,issued_at)
SELECT d.id,md5(random()::text || clock_timestamp()::text || d.id::text),'ISSUED',b.booking_date
FROM booking_details d JOIN bookings b ON b.id=d.booking_id
WHERE b.id=1 AND b.payment_status='PAID' ON CONFLICT (booking_detail_id) DO NOTHING;

COMMIT;
