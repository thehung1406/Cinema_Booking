# ADR 0011 — Reporting dùng projection sở hữu riêng

Status: accepted, implemented M10.

Reporting cần doanh thu, occupancy và sentiment từ nhiều owner nhưng không được giữ credential DB của các miền đó. Các event nghiệp vụ ban đầu chưa đủ thông tin để dựng lại chính xác mọi phiên bản và deletion lịch sử.

Mỗi owner giữ technical reporting export view, transactional dirty revision, fact store và outbox trong DB riêng. Capture coalesce revision thành full replacement hoặc tombstone; event mang generation, key và revision. Snapshot được đóng băng dưới REPEATABLE READ, có manifest/checksum và phân trang HTTP riêng. Stream có thể chồng snapshot: consumer chỉ nhận revision cao hơn, từ chối cùng revision khác nội dung/generation khác.

Giữ durable reporting queue từ M1. Sau bootstrap đủ nguồn, business events cũ được audit ACK; full facts cập nhật projection. Digest/count checkpoint toàn nguồn làm watermark freshness; thiếu/poison/out-of-order không được chứng nhận fresh. Request report chỉ đọc Reporting DB và hỏi quyền Identity, không gọi source để tổng hợp dữ liệu.

Đổi lại, reporting là eventual consistency, giữ tombstone và snapshot nên tăng dung lượng; operator phải theo dõi age/dirty/outbox/DLQ và có retention plan. Restore source ngược lịch sử phải freeze, phục hồi một cặp tương thích hoặc dựng lại generation/projection có đối chiếu; không tự bỏ kiểm tra revision.
