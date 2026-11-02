# Booking Service

API 8087 sở hữu reservation, immutable checkout, đơn, ghế theo suất, vé/check-in và sales configuration nhận từ Cinema. PostgreSQL riêng tại `booking_003`, expiry worker và outbox relay riêng. Không có ORM/DB credential của Identity/Catalog/Cinema; thông tin liên hệ và quote được đọc từ owner API, sau đó chụp vào checkout.

Payment đã tách sang DB/API riêng ở M9. Booking nhận `PaymentCaptured.v1`, xác nhận ghế/cấp vé trong transaction riêng và phát `PaymentBookingResult.v1`; gateway payment routes đi Payment API 8088. Bảng/payment helper giai đoạn M8 còn phục vụ transfer/test lịch sử và được ownership fence chặn ghi sau bàn giao. Runtime Booking không nhận merchant secret.

Chạy root `compose.yml` theo [runtime cuối](../../docs/runbooks/final-runtime.md). Initializer chỉ tự bật ranh giới Payment khi ledger legacy rỗng; DB không rỗng phải thực hiện handoff có đối chiếu, không seed hoặc ghi đè. Mỗi migrate/API/worker/capture chỉ nhận credential theo vai trò.

[Contract](../../contracts/internal/booking.v1.md), [cutover lịch sử](../../docs/runbooks/booking.md), [evidence M8](../../docs/migration/booking-phase.md), [Payment M9](../../docs/migration/payment-phase.md), [ADR](../../docs/adr/0009-booking-store-and-immutable-checkout.md).

Kiểm tra đầy đủ: `python scripts/dev/prepare_messaging.py --test`, rồi `docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm service-tests`. Bao gồm migrations/constraints, lịch sử copy/checksum/sequence, hold/checkout/expiry/callback races, saga/outbox và HTTP qua gateway tới owner APIs.
