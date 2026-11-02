# Backup và restore để bắt đầu chuyển đổi

Script hiện dành cho Windows/PowerShell, Docker PostgreSQL đang dùng của dự án. Không có thao tác drop DB hoặc ghi đè DB đang có. Bản dump có dữ liệu nhạy cảm nên chỉ lưu tại thư mục `tmp/` bị ignore, không đưa vào Git/log/PR.

## Điều kiện

1. PostgreSQL container hoạt động; mặc định tên `postgres`.
2. **Writer ứng dụng/worker phải dừng hoặc ở chế độ chỉ đọc** trong lúc chụp và so sánh checksum. Script không tự dừng dịch vụ của người dùng.
3. Có đủ dung lượng cho dump và một database khôi phục mới. Không chạy script trên production mà chưa chốt cửa sổ bảo trì và quyền truy cập phù hợp.

## Thực hiện từ repository root

```powershell
./scripts/migration/backup-restore.ps1
```

Script dùng user/database từ môi trường của container, không in password. Thứ tự:

1. `pg_dump` custom format, không owner/ACL, ra file tạm trong container.
2. Copy về `tmp/db-backups/cinema-baseline-<timestamp>-<random>.dump`.
3. `createdb` với tên `cinema_restore_test_<timestamp>_<random>` mới; lỗi nếu có trùng, không xóa DB cũ.
4. `pg_restore --exit-on-error` vào DB test.
5. So sánh revision, số bảng, row count và checksum nội dung từng bảng theo thứ tự ổn định.
6. Ghi SHA256 dump, DB test và metadata vào `tmp/db-backups/latest-manifest.json`.

Nếu checksum lệch, dừng chuyển đổi và kiểm tra writer có thay đổi dữ liệu trong lúc chụp hay không. Không coi dump chỉ tồn tại trên đĩa là bằng chứng restore thành công.

## Thử migration trên bản restore

Đổi `DATABASE_URL` **chỉ trong tiến trình thử nghiệm** để trỏ tới DB `cinema_restore_test_...`; chạy Alembic bằng cùng phiên bản source/dependency dự kiến triển khai. Xác nhận revision và các ràng buộc liên quan, không đổi file `.env` ứng dụng sang DB test.

Ở lần kiểm chứng 02/11/2026, DB gốc ở `008`, có 29 bảng gồm 28 bảng nghiệp vụ + `alembic_version`; restore/checksum 29 bảng đạt, và bản restore nâng `008 → 009` thành công. Bản dump/manifest cụ thể nằm trên máy, không commit dữ liệu.

## Quay lui khi nâng hoặc cutover lỗi

- Gateway lỗi khi chưa đổi owner: quay frontend proxy về backend trực tiếp theo [gateway README](../../gateway/README.md); không restore dữ liệu đã có giao dịch mới.
- Migration lỗi: kiểm tra transaction Alembic và trạng thái DB; dùng bản restore mới để chẩn đoán. Không chạy `pg_restore --clean` vào DB ứng dụng như một bước tự động.
- Sau chuyển owner và đã có ghi mới: đối soát/sync ngược hoặc sửa tiến theo runbook của miền trước khi đổi writer.
- Dọn DB test/dump là thao tác riêng sau thời hạn giữ bản sao; script này không tự dọn để còn bằng chứng kiểm chứng.
