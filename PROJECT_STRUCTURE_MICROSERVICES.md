# Cinema Booking — Cấu trúc microservices hiện hành

Ngày cập nhật: 03/11/2026. Đã hoàn tất M1–M10 và bỏ thư mục ứng dụng monolith. Inventory lịch sử được giữ trong Git tại [commit 7d31b45](https://github.com/thehung1406/Cinema_Booking/blob/7d31b452d6ae0b05b8fa946759c5945c9805733e/PROJECT_STRUCTURE_MICROSERVICES.md). [Kế hoạch](MICROSERVICES_MIGRATION_PLAN.md), [kết quả M10](docs/migration/reporting-phase.md), [đợt dọn source](docs/migration/backend-removal.md).

## Cây dự án

```text
apps/web/                         React/Vite, Nginx SPA + /api proxy
gateway/                         FastAPI HTTPgateway/composition
services/
  identity-service/               User, RBAC và login sessions
  catalog-service/                Phim, phân loại, menu và food quotes
  cinema-service/                 Rạp/phòng/ghế/lịch và sales publication
  booking-service/                Reservation, checkout, đơn và ticket/check-in
  payment-service/                VNPay, ledger, saga và reconciliation
  review-service/                 Review/moderation/sentiment, inference worker
  ai-service/                     Chat, RAG, knowledge và history
  notification-service/           Delivery inbox/job, retry và SMTP dispatcher
  reporting-service/              Projection, snapshot/checkpoint, báo cáo JSON/CSV
packages/python-platform/         Envelope/auth client/outbox/inbox/report transport
pipelines/ml/                     Train/evaluate/data preparation offline
pipelines/tests/                  Test dataset/review gate và normalization
model-store/                      Artifact được duyệt; ignored, mount read-only
tests/contracts/                  Web contract, source/build boundary và SQL fence
tests/integration/                Gateway/owner flows, food quote, broker/SMTP
tests/fixtures/source-schema/    Frozen Alembic DDL 001–016 dùng cho transfer tests
infra/compose/                    Test image + DB/broker độc lập
infra/broker/                     RabbitMQ topology/permissions
scripts/dev/                      Scaffold, credential setup và runtime audit
scripts/migration/                Export owner contracts, backup/restore và drills
contracts/                        Public/private API, event và schema contracts
docs/                             ADR, evidence và runbooks
compose.yml                       Runtime chính, project name backend giữ volume cũ
```

Compose project name `backend` là namespace Docker đã dùng để đặt tên volume/container; nó không yêu cầu thư mục ứng dụng cùng tên. Không đổi namespace tùy tiện trên môi trường có dữ liệu.

## Ranh giới service

| Owner | API local | Dữ liệu và việc được ghi |
| --- | --- | --- |
| Notification | 8081 | Inbox, delivery jobs/attempts; dispatcher giữ SMTP credential |
| AI | 8082 | Conversation/message và curated knowledge; chỉ đọc nghiệp vụ qua HTTP |
| Review | 8083 | Review, moderation và sentiment theo version/generation |
| Identity | 8084 | Account/password, RBAC và revocable sessions; giữ JWT signing keys |
| Catalog | 8085 | Film/genre/format, food/menu/quote và schedule references |
| Cinema | 8086 | Theater/room/physical seat/showtime và publication operation |
| Booking | 8087 | Hold/reservation, immutable checkout, booking, ticket và check-in |
| Payment | 8088 | Payment attempt/provider evidence, outbox/result inbox và đối soát |
| Reporting | 8089 | Full-fact projection/tombstone, source state và reporting inbox |

Mỗi service có DB/tài khoản riêng, Alembic và package riêng. `main.py` khởi tạo app/lifespan/middleware; `router/` giữ endpoint và HTTP dependency. Business logic không được đưa vào package kỹ thuật chung hoặc import ORM của owner khác.

## Luồng chính

Web gọi gateway 8080. Identity cấp/kiểm tra session và quyền hiện hành. Cinema đóng bán/drain, nhận Catalog binding rồi publish sales version cho Booking; Booking ACK trước mở bán. Booking giữ ghế và đơn trong transaction riêng, chụp giá/món vào checkout. Payment xác minh VNPay, ghi bằng chứng tiền và outbox cùng transaction; Booking nhận capture, xác nhận ghế/cấp vé rồi trả kết quả. Callback trùng/đến muộn được dedup/đối soát, không lấy ghế của reservation mới. Notification nhận private email snapshot sau xác nhận, gửi SMTP ngoài transaction.

Reporting bootstrap từ 5 frozen owner HTTP snapshots và nhận full facts/checkpoints qua RabbitMQ. Request báo cáo chỉ đọc Reporting DB và hỏi quyền Identity; `as_of`, watermark và stale thể hiện eventual consistency. Mỗi capture worker chỉ có DSN của chính owner đó.

AI/Review đọc Catalog/Cinema/Booking/Identity/Review bằng private fixed-origin APIs theo nhu cầu. API không train model. Review inference worker có image/dependency ML riêng, chỉ nhận artifact đã duyệt read-only; local backend sentiment đang tắt khi chưa có model.

## Vận hành và kiểm thử

[Runbook runtime](docs/runbooks/final-runtime.md) hướng dẫn migrate, Identity bootstrap trên DB rỗng, Reporting bootstrap trước khi bật consumer, health và phục hồi. Root Compose chạy runtime, các overlay chuyển tiếp đã bỏ. Web tại http://127.0.0.1:5173, gateway tại http://127.0.0.1:8080/api.

`infra/compose/Dockerfile.tests` cài 9 owner packages và dependencies kiểm thử; job `service-tests` không chứa ứng dụng cũ. Source DDL fixture chỉ khởi tạo PostgreSQL test để xác minh copy/checksum/sequence/fence; không nằm trong runtime. OpenAPI/schema/import snapshots lịch sử giữ nguyên, exporter hiện hành chỉ import owner contracts. [Ma trận test đã chuyển/nghỉ dùng](docs/migration/retired-monolith-tests.json) giải thích thay đổi số lượng test.

Database/backup nguồn vẫn giữ archive theo thời hạn; xóa code không xóa dữ liệu hay volume. Secret local bị ignore và không vào image/PR. Production provider/SMTP, TLS/monitoring, model đã đánh giá và capacity/SLA thực tế được cấu hình trên môi trường đích.
