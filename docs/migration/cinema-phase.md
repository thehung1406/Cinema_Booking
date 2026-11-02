# M7 — Cinema Service, kiểm chứng local

Ngày: 02/11/2026. Nhánh `codex/microservices-foundation`. M7.1–M7.7 đã triển khai và cutover local. Không commit/push trong đợt này.

## Thay đổi

Cinema có DB/API/worker riêng cho theaters, cinema_rooms, seats, seat_types, showtimes; thêm publications và durable operations. Giữ FK nội miền, thêm ràng buộc sức chứa/loại ghế cùng phòng và exclusion constraint chống trùng lịch. Dữ liệu mới trong Cinema không cần mirror về nguồn.

Booking có hai bảng projection riêng `booking_sales_configurations`/`booking_sales_gates`; không dùng lại năm bảng Cinema làm replica. Booking và seat_status lưu `sales_version`. Gỡ FK và quan hệ ORM ngoài miền từ bookings/booking_details/seat_status tới lịch/ghế vật lý. Lịch sử đơn, xác nhận thanh toán/vé, AI giá/availability, Review verified-purchase và adapter báo cáo dùng publication cục bộ. Lịch sử nhiều đơn đọc theo batch.

Admin thay cấu hình qua tác vụ `202`: đóng hold mới → chờ hold/checkout → apply và tạo publication trong một commit → import/ACK chính xác → mở lại → hoàn tất lifecycle Catalog. Epoch ngăn lệnh cũ; publication bất biến; worker có session advisory lock và tiếp tục phase đã lưu sau crash/lỗi mạng. Giá/lịch/ghế của đơn cũ không đổi. Failed giữ bán đóng và hiển thị thông báo, không báo đã lưu. UI có panel theo dõi và nút đóng/mở nhận hold.

Catalog `catalog_002` bổ sung RESERVED/CONFIRMED/RELEASED và closure tombstone. Hủy reference đến trước request bind cũng chặn bind đến muộn; không resurrect hoặc tự giải phóng bằng TTL. Tham chiếu chưa apply bị thu hồi qua phase COMPENSATING rồi mới giải phóng room operation.

Gateway chuyển Cinema public/admin routes sang `8086`, tổng hợp `/admin/catalog` từ Cinema + Catalog với cùng bearer authorization; `/seats`, Booking, tickets, payment vẫn thuộc nguồn. Cinema không là required domain cho global readiness, để callback/history đã có cấu hình không phụ thuộc Cinema API.

## Cutover và dữ liệu

Đã pause writer, sao lưu/restore source `014` khớp checksum **34 bảng**, Catalog `catalog_001` **10 bảng**. Rehearsal nâng revision thành công trên hai DB restore mới, sau đó nâng DB ứng dụng nguồn `015` và Catalog `catalog_002`. Cinema tạo store `cinema_001` với writer false.

Freeze Cinema nguồn, kiểm tra **0 live hold, 0 pending checkout còn hiệu lực**, rồi stream copy và SHA-256 đối chiếu đủ năm bảng, giữ ID, Decimal, Catalog snapshots và sequence high-water:

| Dữ liệu | Bản ghi |
| --- | ---: |
| theaters | 3 |
| cinema_rooms | 4 |
| seat_types | 10 |
| seats | 80 |
| showtimes | 8 |

Đã tạo **8 publication phiên bản 1**, cả 8 có ACK tại Booking, 8 bootstrap operation DONE, 8 Catalog reference CONFIRMED. Cả 8 suất có ngày **06–07/09/2026**, trước ngày cutover, nên giữ CLOSED; không tạo lịch tương lai giả để mở bán trên dữ liệu ứng dụng. Hai đơn hiện có có version hợp lệ, số tiền paid/confirmed tổng **320.000 đồng** được giữ nguyên.

Trước mở ghi: backup/restore target `cinema_001` khớp checksum **8 bảng**, source `015` đã có projection khớp **36 bảng**. Sau đó chuyển owner Cinema terminal `service`, bật writer/API/worker và gateway domain cinema. Lượt verify checksum sau cutover vẫn khớp cả năm bảng, không copy lại. Runtime Cinema API/worker chỉ có `CINEMA_DATABASE_URL`, không có DB nguồn/Catalog/Identity signing/VNPay/SMTP secrets.

## Kết quả kiểm chứng

- Docker regression: **383 passed, 6 lỗi frontend source-contract đã có từ baseline, 1 skip**, không có lỗi mới. Host gateway/Docker Compose: **71 passed**. Skip là Docker CLI không có trong test container. Test mock payment cập nhật đối số version theo contract mới; không bỏ qua lỗi mới.
- PostgreSQL: chạy migration thật và thử copy năm bảng từ schema nguồn thật; giữ checksum/Decimal/snapshot và sequence high-water 3.000.000, rerun verify/idempotent, từ chối overwrite divergent. Race thêm ghế vượt sức chứa và tạo lịch trùng: chỉ một writer thành công.
- Gate race hold/close và checkout/import: hold mới không thể qua close; import không thể vượt hold/checkout đang sống. Existing hold checkout sau close vẫn dùng giá/version cũ. Đơn/giá/ghế đã bán và publication không bị sửa; late callback đơn hết hạn không ăn mất hold phiên bản mới.
- Lỗi/missing ACK không mở bán; retry dùng cùng publication/digest/epoch. Bootstrap mất ACK mở bán tiếp tục đúng epoch, không replay close cũ. Ghế được thanh toán trong khi chờ disable làm tác vụ FAILED và giữ bán đóng. Rejected Catalog bind được seal/compensate; closure đến trước bind ngăn request đến muộn.
- Integration qua private HTTP API: tạo rạp/phòng/type/ghế/lịch mới chỉ tại Cinema DB, bind tại Catalog, công bố tới Booking, hold/checkout, outbox/ticket/payment giả lập ở DB test, đổi giá chờ checkout rồi publish version 2. Source không cần row showtime/seat tương ứng. SQL listener kiểm tra callback/history không SELECT/JOIN năm bảng archive; mô phỏng Cinema API lỗi không làm hỏng callback/history.
- Frontend: **7 unit tests**, lint/build đạt; browser fixture headless Chrome kiểm tra admin workflows, mobile, quyền và `202 → WAITING → DONE`, không hiện giá đã đổi/đã lưu khi mới nhận việc. Browser fixture chặn mọi fetch/XHR, không ghi DB live.
- Live so sánh **36 response** trước/sau: **28 không đổi** sau khi bỏ `as_of` và field version/state mới, đối chiếu danh sách theo ID. Tám response seat map chỉ đổi trạng thái: **318 AVAILABLE → UNAVAILABLE**, **2 BOOKED → BOOKED**, giữ nguyên mọi ID/nhãn/giá/thuộc tính còn lại vì lịch đã qua giờ. Public/admin references, prices, show detail, report, Review/AI/history endpoints vẫn đọc được.
- Phiên kỹ thuật ngắn hạn trên tài khoản admin có sẵn được xóa cuối smoke; admin không có đơn riêng. Đã đọc trực tiếp **hai lịch sử đơn hiện có** qua repository mới và đối chiếu số tiền/nhãn ghế/giá với archive đã freeze. Không tạo user/lịch/hold/đơn/payment/review giả trên DB ứng dụng, không gửi email khách để smoke.
- Source env reset về monolith vẫn nhận 410 ở guard; raw UPDATE cả năm bảng archive bị DB chặn. Không còn FK Booking/seat tới source showtimes/seats. Private gateway path 404, admin thiếu bearer 401, Cinema private thiếu key 401; public Cinema routes trả service header `cinema`. Các API/database cùng Cinema worker đang chạy; worker không có HTTP health endpoint nên không gọi là healthchecked API.

## Bằng chứng và giới hạn

Các artifact có dữ liệu/secret-adjacent chỉ lưu local ignored: `tmp/m7-tests-verified.log`, `tmp/microservices-tests.xml`, `tmp/m7-host-checks.log`, `tmp/m7-admin-browser.log`, `tmp/m7-admin-ui/`, `tmp/cinema-before.json`, `tmp/cinema-after.json`, `tmp/cinema-contract-comparison.json`, `tmp/cinema-migration/latest.json`, `verified-after-cutover.json`, `tmp/db-backups/cinema-source-before-015.json`, `cinema-catalog-before-002.json`, `cinema-target-before-writes.json`, `cinema-source-projections-ready.json` và dump tương ứng. Không commit chúng.

M0.7 production load/SLA, HA/TLS, sáu lỗi frontend cũ và Reporting Service vẫn mở. Focused concurrency không thay thế load test. Không diễn tập VNPay thật hoặc dừng Cinema container giữa callback live; outage/lost ACK dùng isolated/mocked boundaries. Hold/reservation ID, create-order idempotency và đồng bộ nhiều ghế/expiry chuyên biệt thuộc M8; Payment tiếp tục cùng transaction Booking/seat/ticket, chưa tách saga M9. Không xóa archive hoặc downgrade sau khi owner đã service.

**6/9 miền có writer/store độc lập: Notification, AI, Review, Identity, Catalog, Cinema.** Tiếp theo **M8 — Booking**, giữ payment legacy cùng khối giao dịch ở bước này. [Runbook](../runbooks/cinema.md), [contract](../../contracts/internal/cinema-sales.v1.md), [ADR](../adr/0008-cinema-versioned-sales-gate.md).


Cập nhật M8: Booking/payment legacy đã chuyển sang store riêng; Cinema publication origin là Booking `8087`. Vận hành hiện tại dùng chín overlay, giữ source expiry/relay dừng. Xem [Booking M8](booking-phase.md).
