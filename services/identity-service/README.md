# Cinema Identity Service

Owner của users, roles, permissions, role_permissions và login_sessions. PostgreSQL/tài khoản DB riêng; không import ứng dụng cũ hay đọc DB miền khác. API giữ các tuyến auth/access-control/admin employees/session; private Principal v1 và profile API phục vụ các service khác.

Chạy local bằng root `compose.yml` theo [runbook runtime](../../docs/runbooks/final-runtime.md). Admin đầu tiên của DB rỗng dùng `python -m identity_service.bootstrap`. Health: `http://127.0.0.1:8084/health/ready`. Migrate riêng: `alembic upgrade head` trong thư mục service với `IDENTITY_DATABASE_URL`. Writer mặc định tắt; backfill copy user/RBAC/password hash/ID/sequence chỉ khi cả hai bên đã freeze.

[Token/session contract](../../contracts/internal/identity.v1.md): HS256 key ring chỉ ở Identity, issuer/audience/type/session validation, current active/RBAC introspection mỗi request, logout/khóa tài khoản thu hồi phiên trong DB. Không cần Redis auth; legacy sessions phải đăng nhập lại sau cutover. Signing key, profile/password/token không được log/commit. [ADR](../../docs/adr/0006-identity-tokens-and-session-store.md).

Regression dùng riêng PostgreSQL/Redis/RabbitMQ test, không dữ liệu ứng dụng:

```powershell
python scripts/dev/prepare_messaging.py --test
docker compose -p cinema-migration-tests -f infra/compose/compose.migration-tests.yml run --build --rm service-tests
```

Kiểm thử bao gồm transfer schema legacy thật/sequence, token giả/hết hạn/sai issuer/audience/type, rotation, logout/active/permission updates, auth outage, legacy DB fence và tài khoản mới dùng Booking/Review/AI mà không mirror user vào source. [Kết quả M5](../../docs/migration/identity-phase.md).
