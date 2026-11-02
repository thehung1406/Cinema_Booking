# Kết quả M6 — Catalog Service, 02/11/2026

Nhánh `codex/microservices-foundation`, tiếp nối [M5 Identity](identity-phase.md). Đã triển khai/cutover local; chưa commit/push hoặc chạy workflow GitHub.

## Phạm vi hoàn tất

- Catalog có DB/credential, image, Alembic `catalog_001`, health và API riêng. Sở hữu films, genres, formats, film_genres, film_formats, food_items, combo_items; hai bảng hỗ trợ là food_quotes và schedule_bindings. Không import Backend hoặc truy cập DB miền khác trong runtime.
- Phim/list/detail/admin và menu đã chuyển gateway; giữ ưu tiên tuyến Review. `/admin/catalog` được tổng hợp thật tại gateway từ Catalog và legacy Cinema, cả hai owner xác thực cùng bearer qua Identity. Không trả partial success khi một owner lỗi/từ chối quyền.
- Quote server có UUID/revision/deadline, snapshot tên/giá/thành phần/version, VND và Decimal/Numeric. Mặc định 120 giây; menu edit/quote cùng lock transaction. Booking giữ booking_food_items, so sánh tổng client với giá ghế + quote server, kiểm tra deadline lại khi lưu và ghi quote ID/revision/deadline vào đơn. Sửa/ngừng món không sửa quote/đơn đã tạo; không kéo dài hold.
- Source `014` điền film snapshot vào schedules/bookings trước khi bỏ external FK/relationship. Lịch, lịch sử đơn và confirmation/email đọc published facts; report lấy nhãn phim hiện hành qua Catalog API; facade AI/Review dùng typed Catalog API thay truy vấn archive. Report vẫn gộp theo film ID, tiền/ngày/sentiment và semantics nhãn phim hiện hành không thay.
- Film/format IDs không hard-delete qua API. Catalog cùng lock Film để cấp immutable schedule reference và sửa/retire, kiểm tra format/date/duration. Source lưu grant/snapshot rồi kiểm tra room/conflict/hold/order bằng lock nguồn; không mirror film/format để vượt FK. Source guard chặn legacy Catalog writes, lịch trong maintenance, thiếu snapshot/binding hoặc sửa lịch dùng lại binding cũ.
- Copy giữ ID/Decimal/timestamp/deletion/relationships/sequence high-water, count/SHA256 cả bảy bảng và mọi schedule reference. Writer/fence chuyển cùng route, không chỉ chuyển API đọc. Legacy writer vẫn 410 sau reset env.

## Dữ liệu và cutover local

Inventory nguồn ở `013`: **4 phim, 7 món/combo, 8 suất chiếu, 2 booking**, không có HOLD còn hiệu lực. Dừng source API/relay, backup và restore khớp checksum **34 bảng**. Thử migration `013 → 014` trên restore: mọi schedule/booking có film snapshot, schedule có binding ID và không còn external Catalog FK; sau đó mới nâng nguồn.

Đã freeze Catalog/schedule và copy/đối chiếu:

| Dữ liệu | Số bản ghi |
| --- | ---: |
| genres | 7 |
| formats | 6 |
| films | 4 |
| film_genres | 10 |
| film_formats | 12 |
| food_items | 7 |
| combo_items | 6 |
| schedule_bindings | 8 |

Target backup/restore khớp checksum **10 bảng** tại `catalog_001` trước mở ghi. Source hiện `014`, Catalog owner terminal `service`, target writer bật. Gateway domains ai/review/identity/catalog; Identity vẫn required domain, Catalog optional để callback/history đã có snapshot không bị phụ thuộc Catalog readiness. Các store AI/Review/Identity/Notification không đổi revision.

Bằng chứng local bị ignore: `tmp/db-backups/catalog-source-before-014.json`, `catalog-target-before-writes.json`, `tmp/catalog-migration/latest.json`, `tmp/catalog-before.json`, `tmp/catalog-after.json`, `tmp/m6-tests-final.log`, `tmp/microservices-tests.xml`. Dump chứa dữ liệu ứng dụng và chỉ lưu local.

## Kiểm chứng

- Regression Docker: **354 passed, 6 lỗi source-contract cũ, 1 skip**, không có lỗi mới. Host Docker Compose/gateway checks: **63 passed**. Skip vẫn là container test không có Docker CLI. Hai assertion FK Catalog cũ được thay bằng kiểm tra validation/retirement tại owner; thêm test riêng chứng minh external IDs mới không cần mirror và DB guard chặn writer cũ.
- Source schema thật được phản chiếu để thử copy phim/menu/combo/bindings không rỗng, Decimal chính xác, sequence high-water 100000, rerun idempotent/verify và từ chối divergent overwrite. Target migration đã chạy độc lập.
- Concurrent bind/retire trên PostgreSQL: không thể cùng thành công. Grant kiểm tra sai format/date/duration, replay giữ snapshot gốc, ID dùng cho facts khác bị từ chối; sửa title không sửa grant, bỏ format/thu hẹp ngày/tăng duration không phù hợp bị chặn.
- Quote giữ giá/combo cũ sau menu edit; quote mới dùng giá/thành phần/version mới. Duplicate, quantity sai, inactive component/combo, hết hạn và client price giả được kiểm tra. Quote đã hết hạn bị chặn lúc Booking lưu snapshot.
- Phim, định dạng và món **chỉ trong Catalog DB** dùng được qua legacy schedule → hold → Booking → IPN giả lập → email outbox/report. Không tạo row film/format/food ở source để vượt FK. SQL listener chứng minh không SELECT/JOIN Catalog archive trong các luồng này. Đổi title/giá sau đó không đổi lịch sử đơn; callback/history chạy bằng snapshots ngay cả khi mô phỏng Catalog maintenance/offline. AI search và Review film facade đọc owner mới.
- Gateway aggregation kiểm tra đủ owner response, authorization, header tự khai user/service bị loại và outage/invalid/denied không partial success. Live so sánh **7 response** trước/sau chuyển (4 film details, film list, menu, admin catalog): các giá trị/hợp đồng cũ khớp khi đối chiếu theo ID; list phim dùng thứ tự ID ổn định, admin có thể nhận thêm version/computed fields. Live protected booking/AI history, admin report và Review moderation đọc được sau chuyển bằng phiên kỹ thuật ngắn hạn của tài khoản có sẵn, đã xóa phiên sau smoke. Không tạo phim/món/lịch/đơn/review/payment giả hoặc gửi thư khách trên DB ứng dụng.
- Gateway, Catalog, source và các service đã tách healthy. Runtime Catalog không có DB nguồn/signing/payment/SMTP credentials; consumer không có DB credential Catalog. Source env rollback vẫn bị DB ownership fence chặn. Outage kiểm chứng bằng mô phỏng; không tuyên bố đã diễn tập dừng container Catalog hoặc browser checkout thật.

## Giới hạn và bước tiếp theo

Binding là tham chiếu cấu hình, chưa phải M7 sales_version/ACK/mở–đóng bán. Nếu source write lỗi sau grant, tham chiếu được giữ an toàn, có thể chặn retirement/format/date edit; cần đối soát, không tự expire/xóa khi một writer còn có thể commit. Quy trình confirm/release tự động thuộc Cinema M7. Public retirement hiện từ chối phim đã có tham chiếu, giống giới hạn bảo vệ lịch/đơn; không báo hoàn tất tác vụ chưa thực hiện.

Menu admin mới dùng quyền Catalog `films.manage`; không thêm màn hình menu mới trong đợt này. Quote retention, Reporting snapshot/events/checkpoint, M0.7 load/concurrency/SLA, sáu lỗi frontend source-contract cũ và HA/TLS production vẫn mở. Không đổi ranh giới transaction payment/seat/ticket trong M6.

**5/9 miền có writer/store độc lập: Notification, AI, Review, Identity, Catalog.** M6.1–M6.7 hoàn tất trong phạm vi local ở trên. Tiếp theo **M7 Cinema**. [Runbook Catalog](../runbooks/catalog.md), [contract](../../contracts/internal/catalog.v1.md), [ADR](../adr/0007-catalog-quotes-and-schedule-references.md).


Cập nhật M7: Cinema đã tách store/writer và thay đường schedule legacy bằng sales version/ACK. Catalog hiện `catalog_002` có confirm/release và closure tombstone; các bước M6 ở trên là bằng chứng lịch sử. Vận hành mới nhất dùng tám overlay và [báo cáo Cinema](cinema-phase.md).
