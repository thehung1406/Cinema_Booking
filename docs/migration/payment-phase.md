# M9 — Payment Service và giao dịch phân tán

Hoàn tất triển khai và cutover **local ngày 02/11/2026** trên nhánh
`codex/microservices-foundation`. **8/9 miền có DB riêng**; Reporting còn ở backend
nguồn và là M10.

## Kết quả

Payment8088 sở hữu attempts, checkout registry, provider results bất biến,
fulfillment, đối soát và outbox/inbox trong PostgreSQL riêng. API lấy checkout có
xác thực từ Booking, kiểm tra chủ đơn và tính tiền trên server. Attempt PENDING
được dùng lại với ngày ký ổn định; attempt thất bại có thể thử lại khi checkout
còn hiệu lực. Có bất kỳ PAID nào thì không tạo thêm URL thu tiền.

URL/return/IPN/status và màn hình đối soát đi qua gateway về Payment. Callback ghi
kết quả provider và capture event cùng transaction, không đợi Booking/broker.
Booking nhận event qua inbox, khóa gate/reservation/order/ghế và commit receipt,
BOOKED, vé, outbox xác nhận/email/result cùng transaction riêng. Một checkout chỉ
có một receipt được chấp nhận. Khoản thu sau expiry hoặc attempt trùng vẫn PAID,
không lấy ghế mới/phát vé thêm và có hồ sơ đối soát. Chưa tự refund.

Frontend phân biệt chờ thanh toán, đã thu tiền/đang xác nhận, đã cấp vé và cần hỗ
trợ/đối soát. Trang return không dựng QR từ query hay thông tin tổng đơn; chỉ dùng
ticket_code thực từ Booking sau xác thực. Guest signed return không lấy dữ liệu
vé riêng tư. Nếu có vé nhưng phát hiện khoản thu thêm, UI vẫn hiển thị cảnh báo.
Admin đối soát yêu cầu reports.view, có tiền/tham chiếu và retry kèm lý do audit.

Worker sửa ACK mất qua private HTTP, phát hiện PAID chưa xác nhận/event BLOCKED,
ghi hồ sơ bền vững và log khi số hồ sơ thay đổi. Retry dùng lại event ID và không
đóng hồ sơ tiền hay giả lập hoàn tiền. Runtime Payment không import Booking ORM
hoặc nhận Booking DB URL. Các process worker/relay mới không có merchant key;
Booking API/migration được xóa merchant key qua overlay.

## Dữ liệu và cutover

| Hạng mục | Trước → sau |
| --- | --- |
| Booking revision | booking_001 → booking_002 |
| Payment revision | payment_001, DB mới |
| Backend nguồn | giữ revision 016 và các ownership fence M8 |
| Đơn / payment attempts / vé | 2 / 2 / 2, giữ nguyên |
| Tổng attempt PAID | 320000.00 VND, giữ nguyên |
| Checkout registry / transfer provider results | 2 / 2 |
| Historical accepted receipt / fulfillment | 1 CONFIRMED |
| Active holds / pending orders / open money cases | 0 / 0 / 0 |
| Capture/email mới từ backfill | 0 |

Đã dừng writers, backup/restore và so checksum đủ 15 bảng Booking trước thay đổi.
Nâng booking_002 trên bản khôi phục trước: 2 vé và 320000.00 vẫn đúng. Sau đó nâng
DB local, freeze Payment owner, copy hai giao dịch trong snapshot repeatable-read,
đối chiếu mọi cột payment cũ cùng registry và sequence high-water. Checksum payment
gốc: `fbd7d3ad0400c194b24921989494087ab209a188f92abc22b3dc4ed683b9fb40`.

Backup/restore target Payment001 so đủ 9 bảng và Booking002 so đủ 17 bảng trước
khi mở writers. Các manifest riêng nằm trong ignored `tmp/db-backups/`:

- `m9-booking-before-manifest.json` — restore `cinema_restore_test_20261102_215208_32481810`.
- `m9-payment-target-manifest.json` — restore `cinema_restore_test_20261102_215457_afe2508a`.
- `m9-booking-boundary-manifest.json` — restore `cinema_restore_test_20261102_215459_a9572a99`.

Manifest copy/verify riêng nằm trong ignored `tmp/payment-migration/`. Dumps,
credential, session tạm và snapshot chứa PII không được đưa vào Git/tài liệu.

Booking-side Payment owner đã chuyển terminal `service`. Callback Booking cũ trả
410; update bảng payments archive bị DB từ chối; thử reset env về legacy vẫn bị
durable owner chặn. Gateway yêu cầu readiness Identity/Booking/Payment. Hai queue
saga đang có một consumer mỗi queue, không có backlog/DLQ; các relay/worker sạch
lỗi. Expiry/relay cũ trên backend nguồn vẫn dừng.

Smoke chỉ đọc: hai snapshot lịch sử đơn trùng hoàn toàn; 36 endpoint bodies giữ
nguyên ngoài trường as_of của báo cáo thay đổi theo đồng hồ. Status giao dịch cũ
đúng PAID/ISSUED với 2 vé và FAILED với 0 vé; không được retry các đơn cũ. Đã kiểm
tra auth, private gateway path, callback chữ ký sai và health. Các session kỹ thuật
trên user có sẵn được xóa sau smoke; không tạo đơn/thu tiền/gửi mail thật để thử.

## Kiểm chứng

- Toàn bộ môi trường DB/broker riêng: **412 passed, 6 lỗi legacy đã ghi nhận,
  1 skip; 0 lỗi mới**, 419 cases. Script regression vẫn chặn mọi lỗi ngoài đúng
  sáu lỗi source-contract frontend cũ; không sửa whitelist để né lỗi M9.
- Gateway/Compose trên host sau bổ sung routing M9: **75 passed**.
- Kiểm thử lại phần admin reconciliation cuối: **2 passed**, gồm dữ liệu tiền/đơn,
  từ chối lý do trắng và audit retry.
- Frontend: **10 unit tests**, lint/build qua. Payment browser flow qua 375/1440px
  (processing/review/issued, ticket code thật, guest privacy, tránh thu thêm, audit
  retry); food flow qua ba kích thước và retry sau mất create response. Đã xem ảnh
  render để kiểm tra QR/layout. Vite còn cảnh báo kích thước bundle hiện hữu.
- Tests sử dụng migration PostgreSQL thật và hai store riêng: return/IPN
  trùng/đảo thứ tự, mất phản hồi sau commit, callback/consumer song song, rollback
  sau insert vé, commit trước ACK rồi redelivery, hai attempt PAID, PAID sau expiry
  có hold mới, amount mismatch, kết quả tới sau thất bại, immutable evidence,
  worker process thật, poison event vào DLQ, checkout event đảo thứ tự và ACK repair.
- Diễn tập dừng **RabbitMQ test thật**: callback đã ký vẫn commit đúng một provider
  result và giữ PAID + BLOCKED outbox. Khởi động lại broker và retry giao cùng
  capture ID thành công. Script tự xóa schema Payment tạm; bằng chứng metadata tại
  ignored `tmp/m9-broker-outage-result.json`. Không tác động broker/provider live.
- Ten-overlay config đã kiểm tra DB/secret isolation, upstream Payment8088,
  Booking consumer credential và required readiness. Mỗi API mới có DB riêng.

## Phần còn lại

M10: Reporting read model, bootstrap/checkpoint, dọn archive và cấu trúc cuối,
credential audit toàn hệ thống, vận hành và các diễn tập cuối. M0.7 về tải/ngưỡng
latency/SLA vẫn mở; chưa có xác nhận provider/refund production hay hệ thống paging
bên ngoài. Kết quả này là nghiệm thu local, không cam kết SLA production.

[Runbook](../runbooks/payment.md) · [Contract](../../contracts/internal/payment.v1.md)
· [ADR](../adr/0010-payment-saga.md).
