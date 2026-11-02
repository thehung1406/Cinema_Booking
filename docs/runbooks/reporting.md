# Reporting — backfill, freshness và phục hồi

Đường chạy chuẩn: [runtime cuối](final-runtime.md), [contract](../../contracts/internal/reporting.v1.md), [ADR](../adr/0011-reporting-owned-projection.md). Root runtime chỉ Reporting DB được truy cập bởi Reporting; capture của mỗi owner truy cập own DB của owner đó.

## Chẩn đoán

API `/admin/reports` yêu cầu `reports.view`; CSV dùng cùng bộ lọc/quyền. Kiểm tra `stale`, `as_of`, `watermarks` từng nguồn. Một thay đổi entity làm nguồn mất verified cho đến checkpoint đầy đủ, thường mỗi 10 giây; quá 60 giây mặc định báo stale. Source không có dữ liệu vẫn có checkpoint count 0 và phải verified. Nếu Identity lỗi, protected report fail closed; nếu broker lỗi, projection cũ vẫn đọc được kèm stale.

Kiểm tra health 5 source APIs, 5 `*-report-source`, `reporting-worker`, RabbitMQ và DLQ. Endpoint nội bộ `/internal/v1/reporting/state` cần service key, trả generation/pending; không ghi key/DSN vào log. Dirty revision và outbox tồn tại bền vững qua restart; không reset bảng/checkpoint để làm dashboard xanh.

Source trigger ghi dirty trong business transaction. Materializer khóa từng dirty key, đọc export view, tạo full replacement hoặc tombstone và outbox cùng transaction. Intermediate versions có thể coalesce; consumer không cộng delta nên replay không nhân doanh thu. Capture checkpoint chỉ khi không còn dirty chưa materialize và fact outbox chưa publish. Consumer so sánh toàn bộ count/digest, không coi event đến cuối queue là bằng chứng đủ dữ liệu.

## Backfill/repair snapshot

1. Freeze Reporting consumer (`reporting-worker`), đặt `REPORTING_WRITES_ENABLED=false`; giữ durable queue. Đối với generation không đổi có thể để owner/capture chạy, snapshot và events chồng nhau an toàn. Với restore ngược lịch sử phải freeze cả source writer/capture trước.
2. Backup Reporting và source liên quan, ghi generation/revision/checkpoint/count, xác nhận intended repair. Dừng các job có khả năng tự restart source writer nếu đang restore.
3. Chạy bootstrap CLI theo runtime runbook, `--source booking` (hoặc source cần sửa) / mặc định tất cả. Manifest phân trang bất biến, checksum đầy đủ. Bootstrap giữ revision mới hơn đã nhận; không dùng nó để ép dữ liệu cũ đè dữ liệu mới. Không chỉnh một fact cùng version sang payload khác.
4. Đối chiếu business totals với owner. Bật writer/worker; đợi đủ matching checkpoint rồi mới xác nhận fresh. Theo dõi DLQ/backlog đến drain.

Source generation mismatch bị từ chối có chủ đích. Khi DB nguồn được dựng lại/restore không tương thích, chọn paired backups tương thích hoặc dựng Reporting DB/projection mới có generation được xác nhận và full snapshot/stream của tất cả nguồn. Chặn traffic báo cáo trong lúc hoán đổi DB. Retain DB cũ và audit mọi thao tác; không đổi generation trong một hàng để bỏ qua guard, không purge queue hoặc xóa inbox khi tiền/vé đã phát sinh.

## DLQ replay

`reporting.dead.v1` lưu poison từ queue `reporting.bootstrap.v1` qua policy DLX. Consumer không có quyền publish lại hoặc xóa queue. Operator đọc envelope/reason, kiểm tra owner payload/generation/revision, sửa lỗi code/config hoặc envelope có bằng chứng, ghi ReplayAudit actor/reason. Replay **giữ event_id gốc**. Chờ inbox `reporting.facts.v1` commit rồi mới ACK bản dead delivery; gửi duplicate phải không đổi projection. Event cùng entity/version nhưng khác payload tiếp tục bị từ chối; muốn thay đổi nghiệp vụ phải sửa ở owner và phát revision mới.

`scripts/migration/smoke_reporting_dlq.py` minh họa đúng luồng trên bằng fact kỹ thuật hiện có, không tạo đơn/tiền/vé. Script cần operator AMQP credential chỉ trong job riêng; không đưa credential đó vào Reporting API/consumer runtime. `scripts/migration/smoke_final_outages.py` kiểm chứng stale và recovery. Không purge DLQ còn chưa xử lý để lấy kết quả queue rỗng.

## Retention

Tombstone/revision phải giữ ít nhất bằng replay/backup horizon để không sống lại dữ liệu xóa. Snapshot rows giữ đến khi backup/checkpoint/replay nghiệm thu; hiện chưa có job tự xóa. Trước khi thêm retention job, chốt thời hạn restore và audit, theo dõi dung lượng; không xóa history/inbox còn trong horizon. Legacy archive dọn riêng theo runtime runbook.
