# Catalog — vận hành và cutover M6

Chạy từ repository root bằng **bảy Compose file**, giữ `.env.microservices` hiện có. Không sinh credential mới cho volume cũ hoặc đưa dump/key vào Git/log. M5 phải ổn định trước khi chuyển Catalog.

```powershell
python scripts/dev/prepare_messaging.py
$catalogCompose = @('--env-file','.env.microservices',
  '-f','Backend/docker-compose.yml','-f','docker-compose.microservices.yml',
  '-f','docker-compose.notifications.yml','-f','docker-compose.ai-service.yml',
  '-f','docker-compose.reviews.yml','-f','docker-compose.identity.yml',
  '-f','docker-compose.catalog.yml')
docker compose @catalogCompose config --quiet
docker compose @catalogCompose build catalog-service gateway
```

Máy đã cutover giữ `CATALOG_STORAGE_OWNER=service`, `CATALOG_WRITES_ENABLED=true`, `SERVICE_GATEWAY_DOMAINS=["ai","review","identity","catalog"]`, `SERVICE_GATEWAY_REQUIRED_DOMAINS=["identity"]` và các cờ Identity/AI/Review hiện có. Khởi động:

```powershell
docker compose @catalogCompose up -d fastapi outbox-relay gateway catalog-service identity-service ai-service review-service notification-api
```

Identity là required domain của gateway readiness. Catalog là optional domain: khi Catalog lỗi, quote/phim mới/admin references/report có thể lỗi, còn provider callback, đơn/vé và các snapshot đã công bố vẫn cần phục vụ. Không đổi gateway về monolith hoặc bật writer archive để xử lý outage.

## Chuẩn bị và chuyển từ M5

1. Inventory Catalog tables, schedule references, active holds và caller còn join film/menu. Giữ route ai/review/identity, writer Catalog mới false. Chụp các contract phim/menu/admin để đối chiếu sau chuyển.
2. Trong cửa sổ backup, dừng source API/relay cùng mọi writer nguồn khác. Chạy `./scripts/migration/backup-restore.ps1`, lưu manifest `tmp/db-backups/catalog-source-before-014.json`. Thử `013 → 014` trên DB restore bằng URL override chỉ trong tiến trình. Xác nhận mọi schedule/booking có film snapshot, schedule có binding ID và không còn FK từ miền khác tới Catalog.
3. Nâng nguồn `014`, khởi động lại source API/relay bằng source mới. Migration điền snapshots trước khi bỏ FK; thêm DB guards cho Catalog/schedule. Tạo target `catalog_001` với writer false, không seed/mirror dữ liệu thủ công.

```powershell
docker compose @catalogCompose up -d catalog-db catalog-migrate catalog-service
docker compose @catalogCompose exec -T fastapi python -m app.worker.ai_ownership maintenance --domain catalog --reason 'M6 freeze catalog and schedule references'
docker compose @catalogCompose --profile migration run --rm catalog-backfill
```

Freeze đợi legacy writer/schedule transaction giữ ownership lock kết thúc. Khi maintenance, chặn ghi Catalog và lịch, chặn quote/hold mới; confirmation/history của đơn có snapshot tiếp tục không cần Catalog. Copy kiểm tra cả source maintenance và target writer false, giữ ID/Decimal/timestamp/deletion/relationships/sequence high-water, đồng thời chuyển **mọi schedule reference**. Manifest `tmp/catalog-migration/latest.json` chỉ chứa count/checksum. Target khác nguồn hoặc đã có quote bị từ chối overwrite.

4. Backup/restore target trước mở ghi bằng `./scripts/migration/backup-restore.ps1 -Container backend-catalog-db-1`; lưu manifest `catalog-target-before-writes.json`. Đối chiếu 7 bảng cùng bindings và cả backup/restore mới chuyển owner.

```powershell
docker compose @catalogCompose exec -T fastapi python -m app.worker.ai_ownership service --domain catalog --reason 'M6 catalog and schedule-reference checksums verified'
```

5. Cập nhật env owner/writer/domains như trên, giữ mọi credential/cờ đã có. Gateway phải dùng image mới có aggregation:

```powershell
docker compose @catalogCompose up -d --no-deps catalog-service fastapi gateway
```

6. So sánh list/detail phim, menu, admin catalog; kiểm tra ưu tiên review route, auth/admin, private route bị chặn, source writer vẫn 410 khi reset env. Dùng DB test riêng để tạo phim/định dạng/món/quote/lịch/đơn và callback giả lập; không tạo dữ liệu giả hoặc gửi thư khách trên DB ứng dụng chỉ để smoke.

## Quote, lifecycle và lỗi

[Catalog v1](../../contracts/internal/catalog.v1.md) là contract vận hành. Quote mặc định 120 giây; đổi giá/menu không sửa quote/đơn cũ hoặc kéo dài hold ghế. Booking xin quote server-to-server, từ chối tổng tiền khác server và quote hết hạn lúc lưu snapshot. Menu edit cần `films.manage`. Không sửa trực tiếp bảng menu ngoài service để bỏ qua lock/version.

Film có lịch/tham chiếu chờ sẽ từ chối retirement hoặc sửa format/date/duration không tương thích. Binding còn tồn tại không đồng nghĩa lịch nguồn đã commit. Với lỗi sau grant: kiểm tra UUID trong source schedule, transaction/job đang chạy, manifest và lịch sử thao tác trước khi đối soát. Không tự xóa binding theo TTL; không bỏ FK nội miền để ép sửa. Workflow confirm/release tự động/đóng bán thuộc M7. M6 giữ tham chiếu an toàn và báo 409 thay vì báo đã xóa/sửa xong.

Catalog outage: giữ owner service, khôi phục store/API, kiểm tra schema/credential/Identity origin. Adapter lỗi 503; gateway public proxy có thể trả 502/504 và aggregation trả 503. Lịch sử đơn/callback dùng snapshot; không đọc archive để thay giá/film facts. Worker SMTP/Review/AI không cần credential DB Catalog.

Owner `service` là terminal. Sau khi target nhận ghi, quay lui cần đồng bộ/đối soát Catalog, quote, bindings và snapshots trước khi đổi writer; ưu tiên sửa tiến. Không downgrade 014 hoặc restore source cũ vào DB ứng dụng. Không xóa archive/bindings/quotes trong đợt này. M0.7/load/SLA, HA/TLS và sales lifecycle M7 vẫn mở.


Cập nhật M7: Cinema đã tách store/writer và thay đường schedule legacy bằng sales version/ACK. Catalog hiện `catalog_002` có confirm/release và closure tombstone; các bước M6 ở trên là bằng chứng lịch sử. Vận hành mới nhất dùng tám overlay và [báo cáo Cinema](../migration/cinema-phase.md).
