# M10 — Reporting và runtime cuối

Ngày kiểm chứng local: 02–03/11/2026, nhánh `codex/microservices-foundation`. Hoàn tất 9/9 owner, root `compose.yml`, web `apps/web`, pipeline offline `pipelines/ml`. Monolith và job cũ đã dừng, restart policy `no`; container/volume lịch sử vẫn giữ để phục hồi. Không xóa dữ liệu nguồn.

## Reporting

Reporting có DB riêng (`reporting_001`), projection theo `(source, kind, key)`, generation và revision từng entity; snapshot HTTP riêng của 5 owner Booking/Payment/Catalog/Cinema/Review. Trigger ghi dirty revision cùng transaction nghiệp vụ. Capture worker của mỗi owner chỉ dùng DB của chính owner, tạo full replacement/tombstone và public outbox trong một transaction. Consumer dùng inbox, ACK sau commit. Không join xuyên database hoặc gọi owner trên request báo cáo.

Bootstrap đã xác nhận checksum của **33 facts**: Booking 19, Payment 2, Catalog 4, Cinema 8, Review 0. Queue `reporting.bootstrap.v1` được giữ từ M1 và được drain, không thay queue hay purge để bỏ backlog. Các event nghiệp vụ cũ được ghi audit inbox sau khi snapshot đủ 5 nguồn; projection dùng full facts có version. Checkpoint digest/count chứng minh toàn bộ nguồn, không dùng `MAX(id)` hoặc timestamp làm cursor.

`/admin/reports` và `/admin/reports.csv` qua gateway yêu cầu `reports.view` từ Identity. CSV xử lý công thức ô, dùng BOM UTF-8. Web hiển thị `as_of`, watermark từng nguồn và cảnh báo stale. Thay đổi projection làm mất verified watermark cho đến khi digest checkpoint khớp; broker ngừng hơn 60 giây làm báo cáo stale nhưng giữ dữ liệu đã biết.

Semantics đã đối chiếu: ngày chiếu theo Việt Nam; doanh thu gồm món, chỉ một accepted payment đúng booking/checkout version/amount/currency; không nhân theo số attempts; ticket ISSUED/USED, ghế BOOKED và denominator theo ACTIVE seats của current published config; nhãn phim Catalog hiện tại; sentiment được duyệt, không xóa, đúng version và khoảng ngày cập nhật review. Các trường hợp tombstone, out-of-order, duplicate/conflict, snapshot-stream overlap, generation mismatch, poison và checkpoint thiếu fact có test.

## Chuyển đổi và diễn tập

- So sánh **36 response API** trước/sau: dữ liệu nghiệp vụ giữ nguyên; bỏ metadata thời điểm đồng bộ khỏi phép so sánh báo cáo.
- Hai lịch sử đơn giữ nguyên: **2 payment (1 PAID, 1 FAILED), 2 vé hợp lệ, doanh thu 320.000 VND**; không thêm order/payment/ticket thật phục vụ drill. Không có hold/order pending/reconciliation case còn mở.
- Backup/restore checksum tất cả bảng của 8 DB owner trước nâng cấp, DB nguồn và Reporting target. Thứ tự revision/table count: Identity `001`/6; Notification `001`/6; AI `001`/5; Review `001`/6; Catalog `002`/11; Cinema `001`/8; Booking `002`/17; Payment `001`/9; legacy `016`/36; Reporting `001`/6. Tất cả bảng khớp checksum. Report trên bản restore trả lại 320.000 VND/1 booking/2 tickets.
- Schema cuối: Booking `booking_003`, Payment `payment_002`, Catalog `catalog_003`, Cinema `cinema_002`, Review `review_002`; Identity/Notification/AI không đổi revision.
- Identity API ngừng: báo cáo bảo vệ trả 503, public films còn 200, gateway readiness 503. Khôi phục xong truy cập bình thường.
- AI API ngừng: AI lỗi riêng, lịch sử booking và gateway lõi còn 200.
- RabbitMQ ngừng hơn ngưỡng freshness: báo cáo giữ số liệu, stale hiện rõ, các luồng lõi đọc còn hoạt động. Khởi động lại: cả 5 nguồn được verified, queue drain.
- Poison event đi durable DLQ; replay được audit, sửa envelope với **cùng event ID**, consumer commit trước ACK. Fact hiện có không thay đổi; duplicate replay không nhân số liệu. Sau drill các queue/DLQ rỗng.
- `audit_runtime.py` xác nhận 9 DB/API/migrate, không credential DB chéo owner, không broad env_file, JWT signing chỉ Identity, merchant secret chỉ Payment API, SMTP secret chỉ Notification dispatcher. AI/Review đọc owner APIs, gateway tắt legacy fallback.

Bằng chứng riêng chứa dump/session/config chỉ nằm trong ignored `tmp/m10-*`, không commit lên Git. Script diễn tập có trong `scripts/migration/smoke_final_outages.py` và `smoke_reporting_dlq.py`; chúng dùng local owner/operator credential, không tự cấp quyền public.

## Kiểm thử và hiệu năng

Regression sau tách router: **436 passed, 1 skipped, 0 failures**, không còn danh sách lỗi legacy được miễn trừ. Skip là kiểm tra Docker Compose khi test container không có Docker CLI; kiểm tra tương ứng chạy trên host. Gateway host 76 passed. Frontend 10 passed, lint/build đạt; browser flows payment, món và admin đạt trên web Nginx mới. Worker inference kiểm chứng bằng fixture test riêng; không cần model production để chạy smoke.

Benchmark tách khỏi CI mặc định, PostgreSQL test độc lập, RabbitMQ và consumer thật; API qua ASGI, Identity/provider giả lập. Không gửi callback tiền thật, không đo mạng/đối tác production.

| Tải | Kết quả local | Ngưỡng nghiệm thu local |
| --- | --- | --- |
| 16 contender cùng 2 ghế | 1 thắng, 15 conflict; p95/max 259,32 ms | max ≤ 2.500 ms, đúng 1 winner |
| 8 callback hợp lệ đến Booking ACK | p50 84,59 ms; p95 1.623,25 ms, gồm cold start | p95 ≤ 2.500 ms |
| 100 report request, 8 client, 1.000 đơn/2.000 vé | p95 925,61 ms; 11,79 req/s; 0 lỗi | p95 ≤ 2.000 ms, 0 lỗi |

M0.7 hoàn tất ở mức tải local trên. Đây không phải SLA production; cần capacity test trên hạ tầng và workload đích trước triển khai thật.

## Giới hạn vận hành còn lại

M1–M10 và cutover local đã hoàn tất. Deploy production, thời hạn lưu backup thực tế, secret rotation/monitoring theo hạ tầng, merchant/SMTP thật và SLA sản xuất thuộc cấu hình vận hành môi trường đích. `model-store/` local đang rỗng và sentiment backend tắt: chưa có model production được cung cấp/đánh giá, không tự sinh nhãn hoặc train từ dữ liệu chưa duyệt. Không có tuyên bố đã thực hiện refund/settlement với VNPay thật. Legacy archive giữ tối thiểu 30 ngày và chỉ dọn trong đợt riêng sau phê duyệt lưu trữ.
