# Cinema Catalog Service

Owner films/genres/formats/film_genres/film_formats/food_items/combo_items, cùng immutable food_quotes và schedule_bindings. PostgreSQL/credential, image, Alembic `catalog_001` và health riêng; runtime không import Backend hoặc kết nối store miền khác.

Public film/menu/admin giữ contract cũ. Auth quyền hiện hành qua Identity. Quote lưu Decimal giá/thành phần/deadline, không sửa đơn cũ khi menu thay đổi. Film ID không hard-delete; cùng lock Film kiểm tra/grant lịch và retirement/sửa metadata để tránh race. [Contract](../../contracts/internal/catalog.v1.md), [ADR](../../docs/adr/0007-catalog-quotes-and-schedule-references.md).

Chạy local bằng bộ **bảy overlay** trong [runbook M6](../../docs/runbooks/catalog.md). Health: `http://127.0.0.1:8085/health/ready`. Từ thư mục service với `CATALOG_DATABASE_URL`, migration riêng là `alembic upgrade head`. Writer mặc định tắt; dùng one-shot migration profile để copy dữ liệu đã freeze, không nhập/mirror ORM/catalog rows thủ công vào DB legacy.

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm backend-test
```

Tests dùng DB/broker/Redis riêng, gồm real source transfer, grant/retire race, quote expiry/Decimal/combo changes, gateway aggregation và phim/format/món mới dùng được ở legacy Booking/Cinema mà không mirror về source. Bindings không tự hết hạn khi source write lỗi; xem quy tắc đối soát trong runbook. [Báo cáo M6](../../docs/migration/catalog-phase.md).


Cập nhật M7: Cinema đã tách store/writer và thay đường schedule legacy bằng sales version/ACK. Catalog hiện `catalog_002` có confirm/release và closure tombstone; các bước M6 ở trên là bằng chứng lịch sử. Vận hành mới nhất dùng tám overlay và [báo cáo Cinema](../../docs/migration/cinema-phase.md).
