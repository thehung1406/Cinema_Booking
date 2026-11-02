# M8 — Booking và payment legacy, kiểm chứng local

Ngày: 02/11/2026. Nhánh `codex/microservices-foundation`. M8.1–M8.7 đã triển khai và cutover local. Chưa commit/push; giữ nguyên các thay đổi có sẵn ngoài phạm vi.

## Phần đã tách

Booking có image/API `8087`, PostgreSQL `booking_001`, expiry worker và outbox relay riêng. Runtime chỉ import ORM của miền mình và schema/auth/messaging dùng chung; không có bảng/mirror user, film, theater, room, physical seat, showtime, Review hoặc AI. Identity contacts/introspection và Catalog quote dùng HTTP. Cinema chuyển publication origin trực tiếp sang Booking. Source AI/Review/reporting đọc Booking qua private facades, không query archive.

**Payment legacy vẫn cùng deployment/DB và transaction Booking–seat–ticket–outbox.** Gateway domain payment hiện là alias đến Booking API, không phải Payment Service độc lập M9.

Hold có reservation UUID, user/show/sales version, nhóm ghế và deadline cố định; thêm/retry ghế không kéo dài thời gian. Multi-seat hold nguyên tử, lock gate rồi ghế theo ID; một user/show có tối đa một reservation ACTIVE/CHECKOUT. Checkout seal danh sách ghế, chặn release qua seat API và unique một đơn/reservation. User-scoped idempotency key/fingerprint replay đúng response đã commit, từ chối body khác; frontend giữ body/key khi mất response và retry được sau reload.

Checkout lưu version/amount/currency/deadline cùng snapshot phim/ghế/giá/món/components/customer và digest bất biến. Giá client không quyết định tiền. CheckoutCreated/BookingExpired public events không có contact/token, đi cùng transaction. Confirmed/private-email events giữ contract cũ. Callback, expiry, cancellation và check-in dùng cùng thứ tự lock. Paid provider evidence được giữ nếu xác nhận thất bại; callback muộn không cấp vé hoặc lấy hold của reservation mới. Tạo URL lặp lại dùng pending attempt hiện có.

## Dữ liệu và chuyển chạy

Trước cửa sổ: **0 live hold, 0 pending order, 0 tác vụ Cinema chưa kết thúc, 0 suất mở bán**. Dừng source API/relay, Cinema API/worker, old Celery worker/beat. Source `015` được backup/restore khớp checksum **36 bảng**; nâng `015 → 016` thử thành công trên DB restore mới rồi mới nâng ứng dụng. `016` thêm Booking ownership/fences; giữ source maintenance và target writer false khi copy.

Đã stream/đối chiếu SHA-256 toàn bộ cột gốc của **11 bảng**, giữ sequence high-water:

| Bảng | Bản ghi |
| --- | ---: |
| booking_sales_configurations | 8 |
| booking_sales_gates | 8 |
| bookings | 2 |
| booking_details | 3 |
| booking_food_items | 0 |
| payments | 2 |
| tickets | 2 |
| seat_status | 40 |
| outbox_events | 0 |
| inbox_events | 0 |
| message_replay_audits | 0 |

Trong transaction copy có khóa, tạm tắt user triggers của allowlist để load trạng thái BOOKED lịch sử; derive **2 reservation và 2 immutable checkout**, kiểm chứng lại mọi cột gốc rồi bật lại trước commit. Sau copy có **0 trigger bị disable**. Một reservation CONFIRMED, một EXPIRED; idempotency không được seed giả cho đơn cũ. Null expires_at gốc vẫn null; deadline checkout lịch sử dùng booking_date + 10 phút, đúng fallback cũ. Tiền paid/confirmed vẫn **320.000 đồng**.

Target trước mở ghi được backup/restore tại `booking_001`, khớp checksum **15 bảng**. Hai lịch sử đơn trước/sau khớp mọi trường, gồm số tiền, ghế/giá/nhãn và customer snapshot. Sau đó chuyển source Booking owner terminal service, bật target API/worker/relay, chuyển Cinema origin và gateway booking/payment. Identity + Booking là required domains; các miền đã tách trước giữ cấu hình. Verify-only sau cutover vẫn khớp đủ 11 bảng, không copy lại hoặc đổi facts gốc.

Source expiry schedule bị bỏ; old worker/beat/relay giữ dừng. Gọi stale cleanup task thực tế trả migrated/0/0, không xử lý Booking archive. Reset riêng env Booking về monolith vẫn nhận 410 ở guard; raw UPDATE ở **7 bảng có dữ liệu** bị chặn bởi đúng ownership trigger, và cả **11 archive triggers** đều enabled. Bốn bảng rỗng không cần insert dữ liệu giả để smoke chốt.

## Kiểm chứng

- Full Docker regression: **396 passed, 6 lỗi frontend source-contract đã có từ baseline, 1 skip**, không có lỗi mới. Host gateway/Docker Compose: **72 passed**. Skip là Docker CLI không có trong test container.
- Real PostgreSQL/migrations: giữ nhiều ghế với thứ tự đảo, chỉ một bên thắng và không partial hold; hai checkout cạnh tranh cùng/different key không tạo hai đơn; fixed deadline và sealed checkout/giá/customer/payment facts bất biến. Expiry cạnh tranh callback giữ PAID evidence, không cấp vé muộn và không lấy hold mới. Callback trùng/check-in dùng một lần; lỗi sau validate provider rollback seats/tickets/events rồi retry đúng một lần.
- Copy thử dữ liệu nguồn thật qua schema reflect: tiền/timestamp null/deadline fallback, ticket codes, payment refs và event ID/payload/status giữ nguyên; high-water 3.000.000, verify/rerun idempotent, divergent overwrite bị từ chối. Historical bootstrap lỗi rollback toàn bộ; sửa dữ liệu fixture rồi copy lại đạt.
- HTTP integration: source AI giá, Review verified purchase/candidates và báo cáo đọc owner mới; SQL listener xác nhận không SELECT/JOIN source Booking/projection/payment/ticket tables trong những luồng đó. Booking sở hữu riêng không cần bảng user/film/physical Cinema/Review/AI; model registries cũng tách.
- Quote integration với Catalog API/DB thật trong test: đặt combo bằng quote server, sửa giá/tên menu sau đó không đổi checkout/history. Confirmation/history vẫn chạy khi cấm mọi Catalog call. Signed IPN/Return, mismatch amount/ownership, ticket permissions và privacy reservation ID được kiểm tra bằng dữ liệu test riêng.
- Frontend **8 unit tests**, lint/build đạt. Headless Chrome food flow giữ mixed combo/drink totals, responsive/expiry/validation và giả lập server đã xử lý nhưng response mất; sau reload gửi lại đúng body/key cũ. Mọi fetch/XHR trong browser fixture bị intercept, không tới backend/VNPay thật.
- Live **36 response đọc trước/sau khớp** sau khi bỏ as_of và field reservation_id null mới. Public seat/available-count qua gateway trả header booking; Vite proxy cũng đến owner mới. Protected routes thiếu bearer 401, private gateway path 404, private checkout thiếu key 401. Cinema đọc gate version/epoch/closed state từ Booking. Hai lịch sử đơn thật được đối chiếu trực tiếp qua repository mới; tài khoản admin smoke có 0 đơn riêng và phiên kỹ thuật đã xóa finally.
- Runtime API/DB/gateway health đạt; expiry/relay/Cinema worker đang chạy (không có HTTP health endpoint riêng). Booking API chỉ có DB riêng, không JWT signing/SMTP/source DB; expiry/relay không nhận VNPay key. Merchant/hash/frontend/provider settings mới khớp chính xác cấu hình source cũ, không in giá trị. Không tạo user/hold/order/payment/ticket giả hoặc gửi email khách để smoke DB ứng dụng.

## Bằng chứng và giới hạn

Artifacts ignored/local: `tmp/m8-tests-final-complete.log`, `tmp/m8-host-checks.log`, `tmp/microservices-tests.xml`, `tmp/m8-frontend-*.log`, `tmp/m8-food-browser.log`, `tmp/m8-food-ui/`, `tmp/booking-before.json`, `booking-after.json`, `booking-history-before.json`, `booking-history-after.json`, `booking-contract-comparison.json`, `tmp/booking-migration/latest.json`, `verified-after-cutover.json`, `tmp/db-backups/booking-source-before-016.json`, `booking-target-before-writes.json` và dump tương ứng. Dump/order responses có dữ liệu ứng dụng, không commit chúng.

Không diễn tập thanh toán/refund VNPay thật hoặc kill container giữa callback live; các race/failure/outage dùng môi trường isolated/mocked. Chưa có Payment store/consumer/saga độc lập; contract checkout và events chuẩn bị cho M9. M0.7 production load/SLA, HA/TLS, retention idempotency/events, sáu lỗi frontend cũ và Reporting Service vẫn mở. Giữ archive bị fence; không downgrade/restore source để mở lại writer sau handoff.

**7/9 miền có writer/store độc lập: Notification, AI, Review, Identity, Catalog, Cinema, Booking.** Tiếp theo **M9 — Payment**. [Runbook](../runbooks/booking.md), [contract](../../contracts/internal/booking.v1.md), [ADR](../adr/0009-booking-store-and-immutable-checkout.md).
