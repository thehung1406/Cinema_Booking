# Vận hành và chuyển dữ liệu AI

> Tài liệu lưu bằng chứng cutover lịch sử. Ứng dụng monolith và các overlay đã xóa ở đợt [dọn source](../migration/backend-removal.md); lệnh lịch sử cần source tại [commit 7d31b45](https://github.com/thehung1406/Cinema_Booking/tree/7d31b452d6ae0b05b8fa946759c5945c9805733e). Vận hành hiện tại dùng root `compose.yml` và [runbook runtime](../runbooks/final-runtime.md).

> Runbook này lưu quy trình cutover tại mốc lịch sử. Runtime hiện hành dùng root `compose.yml`: xem [runbook cuối](final-runtime.md) và [M10](../migration/reporting-phase.md). Không khởi động source/overlay cũ trên dữ liệu đã bàn giao.

Máy đã hoàn tất M6 dùng bộ **bảy Compose file** trong [runbook Catalog](catalog.md), giữ credential/cờ cutover hiện có. Các bước dưới đây mô tả mốc trước đó.

Máy đã hoàn tất M5 phải dùng bộ **sáu Compose file** và auth origins trong [runbook Identity](identity.md), giữ credential/cờ cutover hiện có. Các bước phía dưới mô tả mốc chuyển miền trước đó.

Đây là trình tự M3. Máy đã hoàn tất M4 phải dùng bộ năm Compose file trong [runbook Review](review.md) khi khởi động, để giữ cả hai tuyến AI/Review.

## Bộ lệnh local

Chạy từ repository root. Giữ credential đã sinh; không xóa `.env.microservices` khi còn volume DB/broker.

```powershell
python scripts/dev/prepare_messaging.py
$aiCompose = @('--env-file', '.env.microservices', '-f', 'Backend/docker-compose.yml', '-f', 'docker-compose.microservices.yml', '-f', 'docker-compose.notifications.yml', '-f', 'docker-compose.ai-service.yml')
docker compose @aiCompose build fastapi gateway ai-service ai-migrate ai-backfill
```

`prepare_messaging.py` bổ sung credential AI thiếu và giữ giá trị đã có. Không dùng `--test` để chuẩn bị môi trường ứng dụng.

## Cutover lần đầu, kể cả DB AI rỗng

1. Mặc định trong `.env.microservices`: `AI_STORAGE_OWNER=monolith`, `AI_WRITES_ENABLED=false`, `AI_GATEWAY_DOMAINS=[]`. Chuẩn bị backup nguồn có restore/checksum bằng [runbook backup](backup-restore.md); dừng mọi writer nguồn gồm API, relay và worker/scheduler đang hoạt động lúc backup. Thử `010 → 011` trên bản restore trước khi nâng nguồn. Không thay `.env` ứng dụng để trỏ vào DB restore.
2. `docker compose @aiCompose up -d --no-build fastapi gateway outbox-relay ai-service`. Nguồn đạt `011`, target đạt `ai_001`; AI writer mới vẫn tắt. Khôi phục các worker/scheduler vốn hoạt động trước bảo trì bằng đúng cấu hình Notification events.
3. Freeze nguồn bằng CLI dưới đây. Nó lấy khóa exclusive trên hàng ownership, đợi các transaction AI đang giữ khóa share hoàn tất. Chat cũ kiểm tra lại khóa trước khi ghi nếu đã nhả transaction để chờ model.

```powershell
docker compose @aiCompose exec -T fastapi python -m app.worker.ai_ownership maintenance --reason 'M3 freeze before verified copy'
docker compose @aiCompose --profile migration run --rm ai-backfill
```

4. Job xác nhận private source owner là `maintenance` và target writes=false; chụp snapshot read-only repeatable-read, giữ nguyên ID/UUID/version/context/timestamp/metadata/embedding, so count/SHA256 từng bảng trước commit target. Bản ghi được stream theo lô 500. Sequence giữ cả high-water mark nguồn kể cả ID đã xóa. Chỉ cho phép đích rỗng hoặc đã giống hệt; khác dữ liệu thì dừng, không truncate/ghi đè. Manifest ở `tmp/ai-migration/latest.json` bị ignore. Có thể backup/restore target bằng `./scripts/migration/backup-restore.ps1 -Container backend-ai-db-1` khi writes vẫn false; lưu riêng manifest nguồn/đích vì script ghi `latest-manifest.json`.
5. Chỉ sau khi đối chiếu đạt, chuyển nguồn sang trạng thái terminal:

```powershell
docker compose @aiCompose exec -T fastapi python -m app.worker.ai_ownership service --reason 'AI copy checksum verified; hand over writer'
```

6. Sửa ba cờ trong `.env.microservices`: `AI_STORAGE_OWNER=service`, `AI_WRITES_ENABLED=true`, `AI_GATEWAY_DOMAINS=["ai"]`. Nếu đã cấu hình model/rate/TTL ở `Backend/.env`, chuyển riêng bốn khóa `AI_MODEL_URL`, `AI_MODEL_TIMEOUT_SECONDS`, `AI_REQUESTS_PER_MINUTE`, `AI_CONTEXT_TTL_SECONDS` sang file này; không cấp toàn bộ env legacy cho runtime AI.

```powershell
docker compose @aiCompose up -d --no-build fastapi gateway ai-service
.venv/Scripts/python.exe scripts/migration/smoke_gateway.py --ai http://127.0.0.1:8082
```

Kiểm tra `/health/ready` cổng 8080/8082, auth/user scope, admin documents và UI qua `/api`. Không tạo thanh toán hoặc gửi thư khách để smoke. HTTP smoke dùng `.venv` có httpx; có thể chạy bằng Python khác đã cài httpx.

## Quyền ghi và vận hành sau chuyển

`domain_ownership` và `domain_ownership_audits` nằm tại nguồn. Trạng thái bền vững `service` thắng cấu hình env `monolith`; khởi động lại backend thiếu overlay không mở lại writer cũ. Hạ schema `011` bị chặn khi miền đang frozen/transferred. Legacy AI/API quản lý tài liệu trả 410 sau chuyển; gateway chặn private facade với 404. CLI nhập knowledge cũ cũng bị chặn ở hàm ghi.

Bốn bảng legacy được giữ làm bản lưu, không phải store đang hoạt động. Không chạy SQL/operator script sửa chúng. Chưa thu hồi DDL/DML ở cấp PostgreSQL superuser legacy; quyền operator DB và việc dọn archive là công việc vận hành riêng.

AI outage không làm gateway readiness thất bại mặc định. Các request AI trả 502/504 theo lỗi kết nối/timeout, không tự fallback về nguồn cũ. Phim/menu/booking đi tuyến của chúng; auth/read facade lỗi thì AI fail-closed. `GATEWAY_REQUIRED_DOMAINS` chỉ đặt khi thực sự muốn outage của miền đó chặn readiness toàn gateway.

Sau chuyển tiếp tục dùng đủ bốn overlay khi `up`, để giữ tuyến AI và Notification events. Lịch sử/tài liệu nằm ở DB AI; importer mới thuộc owner AI. Auth vẫn phụ thuộc Identity adapter của monolith cho tới M5. Việc purge dữ liệu theo lifecycle user xuyên service cần được xây cùng Identity; hiện không có public delete-user API được chuyển ở M3.

## Lỗi và quay lui

- Trước chuyển terminal: giữ target writes=false, sửa lỗi copy rồi chạy lại. Nếu hủy cutover, xác nhận target chưa nhận ghi, trả nguồn `maintenance → monolith` bằng CLI có reason và giữ gateway ở monolith.
- Sau chuyển terminal: không đổi route/writer về archive. Giữ/sửa tiến AI service; khi cần khóa thêm hãy đặt target writes=false và recreate AI service. Quay lui dữ liệu cần quy trình đối soát và đồng bộ ngược được kiểm chứng riêng; CLI cố ý từ chối mở lại nguồn.
- Không tự restore đè DB, purge lịch sử hoặc xóa volume để xử lý lỗi. Dùng bản restore mới để điều tra.
