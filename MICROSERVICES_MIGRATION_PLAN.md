# Kế hoạch chuyển Cinema Booking sang microservices

> Ngày lập: 02/11/2026. Baseline mã nguồn: `main` / `3db6e3b`.
> Trạng thái: **M1–M10 đã triển khai/kiểm chứng và cutover local** trên nhánh `codex/microservices-foundation`. Đủ 9 service/DB riêng, root Compose; monolith/job cũ đã dừng. M0.7 đã đo/nghiệm thu tải local; SLA production cần đo trên hạ tầng đích.
> Thiết kế tham chiếu: [Cấu trúc dự án và 9 service đích](PROJECT_STRUCTURE_MICROSERVICES.md).

Kết quả mới nhất: [Reporting M10](docs/migration/reporting-phase.md), [runtime cuối](docs/runbooks/final-runtime.md), [runbook Reporting](docs/runbooks/reporting.md); [Payment M9](docs/migration/payment-phase.md), [runbook Payment](docs/runbooks/payment.md); [Booking M8](docs/migration/booking-phase.md), [runbook Booking](docs/runbooks/booking.md); [Cinema M7](docs/migration/cinema-phase.md), [runbook Cinema](docs/runbooks/cinema.md); [Catalog M6](docs/migration/catalog-phase.md), [runbook Catalog](docs/runbooks/catalog.md); [Identity M5](docs/migration/identity-phase.md), [runbook Identity](docs/runbooks/identity.md); [Review M4](docs/migration/review-phase.md), [runbook Review](docs/runbooks/review.md); [AI M3](docs/migration/ai-phase.md) và [Notification M1–M2](docs/migration/notification-phase.md) giữ kết quả đợt trước. [Baseline gateway](docs/migration/baseline.md) được giữ để đối chiếu. Reporting đã bootstrap snapshot/checksum đủ 5 nguồn và drain durable queue từ M1; xem bằng chứng M10. Các phần kế hoạch lịch sử dưới đây giữ mô tả tại từng giai đoạn.

## 1. Kết quả cần đạt

Chuyển backend FastAPI hiện tại sang 9 dịch vụ có thể build, test, migrate và triển khai riêng: Identity, Catalog, Cinema, Booking, Payment, Review, AI, Notification và Reporting. React tiếp tục là một ứng dụng, gọi qua một API Gateway. Giữ repository hiện tại và tận dụng stack Python/React/PostgreSQL.

Mỗi miền chỉ có một nơi được ghi dữ liệu. Giữ ghế, đơn và phát hành/check-in vé cùng Booking Service để xác nhận trong một transaction. Quản trị được chia về đúng service sở hữu nghiệp vụ; không có admin service được ghi tất cả database.

Chuyển lần lượt qua gateway: phần đã tách đi vào service mới, phần chưa tách vẫn dùng `Backend/`. Phương pháp này dựa trên [Strangler fig pattern của AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html). Thứ tự và công việc cụ thể bên dưới là kế hoạch riêng cho Cinema Booking.

### Giả định để lập kế hoạch

- Chưa biết nhân lực, deadline, tải và môi trường production. Lập kế hoạch theo thứ tự phụ thuộc và tiêu chí hoàn tất, chưa cam kết ngày đưa vào vận hành.
- Có thể giữ một PostgreSQL server ban đầu, nhưng database và tài khoản riêng theo service.
- Cho phép cửa sổ dừng ghi ngắn theo từng miền khi chuyển dữ liệu. Nếu cần không downtime, phải bổ sung CDC/đồng bộ delta và kiểm thử riêng trước khi ước lượng.
- VNPay thật chưa được dùng để chạy shadow test; kiểm thử bằng giả lập/sandbox phù hợp.
- Tách email trước để kiểm chứng messaging; booking/payment được tách khi cơ chế giao dịch phân tán và đối soát đã sẵn sàng.
- Chưa mở rộng thêm chức năng sản phẩm lớn trong cùng đợt tái cấu trúc; các thay đổi bắt buộc như trạng thái chờ xác nhận thanh toán vẫn nằm trong phạm vi.

## 2. Thứ tự triển khai

| Mốc | Phạm vi | Đầu ra chính | Phụ thuộc |
| --- | --- | --- | --- |
| M0 | Khảo sát và baseline | Test baseline, OpenAPI, backup/restore, danh sách dependency | Không |
| M1 | Nền tảng | Gateway, service template, auth adapter, broker, outbox/inbox, CI | M0 |
| M2 | Notification | Email service và delivery store; loại đường gửi cũ | M1 |
| M3 | AI | Chat, RAG, knowledge và hội thoại có DB riêng | M1; dùng cơ chế event đã kiểm chứng ở M2 khi cần |
| M4 | Review | Review, moderation, sentiment và worker riêng | M1; thực hiện sau M3 trong kế hoạch tuần tự |
| M5 | Identity | User/RBAC/session và kiểm tra quyền xuyên service | M3–M4 đã dùng auth adapter; M1 |
| M6 | Catalog | Phim/phân loại/menu, quote đồ ăn và contract vòng đời phim | M5 |
| M7 | Cinema | Rạp/phòng/ghế/lịch/giá; giao thức mở/đóng bán | M6 |
| M8 | Booking | Ghế theo suất, đơn, món snapshot, vé và expiry độc lập | M7; payment tạm còn cùng deployment/transaction |
| M9 | Payment | VNPay, attempt, callback, saga, đối soát | M8; kiểm chứng outbox/inbox từ M2 |
| M10 | Reporting và hoàn thiện | Read model, báo cáo, dọn legacy, diễn tập vận hành | M4, M6–M9; nguồn sự kiện được chuẩn bị từ M1 |

Việc tách AI/Review trước Identity cần auth adapter gọi monolith trong thời gian chuyển tiếp. Sau M5, đổi adapter sang Identity; không cho service mới kết nối DB user cũ. Tương tự, AI dùng API đọc từ monolith cho đến khi Catalog/Cinema/Booking sẵn sàng.

M8 là bước chuyển tiếp có chủ đích: Booking được cô lập cùng phần payment legacy trong một khối triển khai và DB giao dịch tạm thời. **Chưa coi Payment là service độc lập tại M8.** M9 mới chuyển quyền sở hữu bảng `payments` và thay transaction chung bằng event/saga.

## 3. Phân công và cách theo dõi

| Vai trò | Trách nhiệm |
| --- | --- |
| Người phụ trách kiến trúc/backend | Chốt owner, API/event contract, migration, concurrency, payment và review thay đổi |
| Người phụ trách frontend | Gateway compatibility, admin, trạng thái thanh toán, E2E trên trình duyệt |
| Người phụ trách dữ liệu/vận hành | Backup/restore, credential, Compose, CI, monitoring, cutover/replay |
| Người kiểm thử | Baseline, dữ liệu kiểm thử, regression, test lỗi và bằng chứng nghiệm thu |

Một người có thể đảm nhiệm nhiều vai trò. Chưa có phân công cho cá nhân cụ thể. Chỉ đánh dấu mốc hoàn tất khi có mã nguồn, kiểm thử và bằng chứng cutover tương ứng; tạo folder/container chưa đủ.

Ước lượng lại sau M0–M2 dựa trên thời gian tách service đầu tiên. M7–M9 là phần có độ bất định cao nhất vì thay ràng buộc FK/join và transaction thanh toán. Chưa ấn định lịch theo tuần khi chưa biết nhân lực và yêu cầu downtime.

## 4. Công việc chi tiết theo mốc

### M0 — Chốt hiện trạng và khả năng khôi phục

- [x] M0.1: Ghi nhận commit, runtime/dependency, Compose, endpoint và các luồng frontend hiện có.
- [x] M0.2: Kiểm tra Alembic revision của DB đang chạy so với source head `009`; xác nhận 28 bảng nghiệp vụ trong schema áp dụng.
- [x] M0.3: Chạy backend tests, frontend unit/lint/build và browser flows trên môi trường kiểm thử; ghi rõ lỗi sẵn có, bài skip và dependency còn thiếu.
- [x] M0.4: Xuất OpenAPI và fixture request/response đã loại dữ liệu nhạy cảm; ưu tiên auth, ghế, booking, food, payment, ticket, admin và AI.
- [x] M0.5: Sao lưu DB và diễn tập restore vào DB kiểm thử riêng; ghi procedure, checksum và thời gian phục hồi đo được.
- [x] M0.6: Lập bảng FK/ORM/join/import/task liên miền, đặc biệt admin reports, `ai_tools`, payment → booking/seat/ticket và booking → food.
- [x] M0.7: Đo latency, error, khả năng xử lý tranh chấp ghế và thời gian xác nhận ở mức tải kiểm thử; chốt ngưỡng nghiệm thu hiệu năng sau khi có số đo.

**Nghiệm thu:** có báo cáo baseline lặp lại được, DB test độc lập, bản restore hoạt động và danh sách lỗi ban đầu. Nếu có lỗi bán trùng ghế/thanh toán ở baseline thì khắc phục trước khi đổi ranh giới giao dịch.

**Đầu ra:** `docs/migration/baseline.md`, OpenAPI/fixtures, `docs/runbooks/backup-restore.md`, ma trận dependency. Các đường dẫn này là đầu ra dự kiến, chưa được tạo bởi tài liệu kế hoạch này.

### M1 — Xây nền tảng dùng cho từng đợt tách

- [x] M1.1: Tạo các ADR: owner của 28 bảng, thứ tự tách, auth/introspection, broker, hợp đồng event, quote, sales lifecycle và payment compensation.
- [x] M1.2: Thêm gateway chuyển `/api` về monolith; giữ response, slash/redirect, query/callback và quy tắc reviews trước films tổng quát.
- [x] M1.3: Tạo service template tối thiểu: settings, DB riêng, Alembic, Dockerfile, health/readiness, structured logs, timeout và tests.
- [x] M1.4: Tạo auth adapter nội bộ; khi Identity chưa tách, monolith xác minh token, active và quyền. Service nội bộ cần credential, không nhận user header tự khai báo.
- [x] M1.5: Bổ sung broker integration events theo ADR; kế hoạch hiện chọn RabbitMQ. Giữ Celery cho job theo miền khi phù hợp.
- [x] M1.6: Thêm outbox producer và inbox consumer mẫu với business update cùng local transaction; kiểm tra broker confirm, ACK, retry, dead-letter và replay.
- [x] M1.7: Chuẩn hóa event ID, aggregate version, correlation/causation ID; schema trong `contracts/`. Không chia sẻ ORM nghiệp vụ.
- [x] M1.8: Thiết lập CI kiểm tra theo thành phần thay đổi; service test, migration test và contract compatibility là bước bắt buộc của PR liên quan.
- [x] M1.9: Tạo registry route/owner, công tắc route theo miền và checklist cutover. Quyền ghi được chuyển cùng ownership, không chỉ chuyển traffic đọc.
- [x] M1.10: Thiết kế bộ dữ liệu khởi tạo/report snapshot và mốc replay; ghi nhận các sự kiện nghiệp vụ cần phát từ monolith trong thời gian chuyển tiếp.

**Nghiệm thu:** toàn luồng hiện tại qua gateway vẫn đạt baseline; business commit không làm mất event khi broker lỗi; consumer nhận lặp không lặp thay đổi DB; xác thực không phụ thuộc truy cập DB xuyên service.

**Quay lui:** đổi gateway về endpoint monolith trước khi thay owner dữ liệu; giữ migration kỹ thuật tương thích ngược. Không xóa outbox còn event chưa xử lý.

### M2 — Tách Notification Service

- [x] M2.1: Định nghĩa `BookingConfirmed.v1` và payload gửi thư riêng có dữ liệu tối thiểu; tách quyền truy cập dữ liệu liên hệ khỏi topic báo cáo.
- [x] M2.2: Ghi event xác nhận cùng transaction booking/payment hiện tại; thay gọi gửi email trực tiếp bằng outbox.
- [x] M2.3: Tạo DB notification cho delivery job/attempt, inbox unique và retry/backoff; dựng email template từ snapshot đơn/vé/món.
- [x] M2.4: Di chuyển `send_payment_success_email_task` và email utility; expiry worker vẫn ở miền booking.
- [x] M2.5: Chuyển gửi email sang consumer mới và tắt producer/task gửi cũ; kiểm tra không còn hai đường gửi đang hoạt động.
- [x] M2.6: Thêm theo dõi delivery failure/dead-letter và runbook gửi lại có audit.

**Nghiệm thu:** thanh toán/vé vẫn thành công khi SMTP dừng; event không mất khi worker chết; sự kiện trùng không tạo hai delivery job. Ghi nhận giới hạn SMTP: sự cố ngay sau provider nhận thư có thể gây thư lặp nếu provider không hỗ trợ dedup.

**Quay lui:** giữ một consumer gửi chủ động; đối chiếu delivery ID trước khi chuyển lại worker cũ. Không bật lại toàn bộ đường gửi cũ để gửi lại đơn đã xử lý.

### M3 — Tách AI Service

- [x] M3.1: Di chuyển chat, RAG, knowledge, conversation/message và schema liên quan vào service; tạo DB/Alembic riêng cho 4 bảng AI.
- [x] M3.2: Thay truy vấn trực tiếp trong `ai_tools.py` bằng typed HTTP client chỉ đọc. Trước khi các miền tách, client gọi API tương thích của monolith.
- [x] M3.3: Tách cấu hình/Redis namespace của context, rate limit và model endpoint; không để request AI giữ connection/lock DB booking.
- [x] M3.4: Backfill hội thoại/tài liệu/chunk, giữ UUID/ID/timestamp/version; kiểm tra quyền sở hữu lịch sử chat.
- [x] M3.5: Chuyển `/ai/*` và `/admin/documents*`; giữ kiểm tra phê duyệt đúng phiên bản và hiệu lực tài liệu.
- [x] M3.6: Sửa phần báo cáo/admin hoặc caller còn đọc bảng đã chuyển; chỉ dùng API/projection cần thiết.

**Nghiệm thu:** chatbot/lịch sử/duyệt tài liệu hoạt động với user đúng quyền; model timeout trả lỗi có kiểm soát; AI dừng không làm lỗi đặt vé.

Bằng chứng M3: [báo cáo kiểm thử/cutover local](docs/migration/ai-phase.md), [runbook ownership/copy/rollback](docs/runbooks/ai.md). Bốn bảng nguồn local rỗng; chuyển dữ liệu không rỗng được kiểm chứng trên DB test riêng.

### M4 — Tách Review Service

- [x] M4.1: Di chuyển reviews, review_sentiments, review API/service và sentiment worker; worker chỉ ghi DB review.
- [x] M4.2: Tạo API kiểm tra phim qua monolith/catalog adapter; phân quyền kiểm duyệt qua auth adapter.
- [x] M4.3: Backfill giữ review ID, uniqueness user–film, content_version, moderation/deletion và model version.
- [x] M4.4: Chuyển review routes trước rule `/films/{id}`; thay các caller sentiment/ranking trong AI và admin bằng API/projection.
- [x] M4.5: Thêm `ReviewChanged`/`ReviewSentimentUpdated`, inbox/outbox khi cần; retry không ghi kết quả của phiên bản nội dung cũ.
- [x] M4.6: Kiểm tra báo cáo cảm xúc cũ còn dùng dữ liệu gì; cung cấp API read thay cho join review DB trong giai đoạn chuyển tiếp.

**Nghiệm thu:** moderation, sửa/xóa/retry và ranking giữ hành vi; replay không nhân số lượng; worker ML độc lập tài nguyên với giữ ghế/thanh toán.

Bằng chứng M4: [báo cáo Review](docs/migration/review-phase.md), [runbook](docs/runbooks/review.md). Source local không có review cũ cần chép; copy dữ liệu không rỗng/sequence đã kiểm thử riêng. Outage Review kiểm chứng bằng mô phỏng; thao tác diễn tập dừng container bị automatic approval review chặn.

### M5 — Tách Identity Service

- [x] M5.1: Di chuyển users, roles, permissions, role_permissions và phần quản trị nhân viên/tài khoản.
- [x] M5.2: Chốt token contract và rotation; triển khai active/permission introspection cho hành động nhạy cảm. Không dựa hoàn toàn vào claim role cũ.
- [x] M5.3: Chuyển refresh/revocation store có chiến lược TTL hoặc đăng nhập lại có kiểm soát; kiểm tra logout/khóa tài khoản có hiệu lực theo contract.
- [x] M5.4: Đổi auth adapter của monolith, AI và Review sang Identity; loại truy vấn user/RBAC DB chung.
- [x] M5.5: Refactor relationship/FK/caller trong DB legacy trước cutover: user ID ngoài miền thành tham chiếu nghiệp vụ; dữ liệu tên/email cần thiết lấy qua snapshot hoặc API phù hợp.
- [x] M5.6: Chuyển `/auth/*`, `/access-control/*`, `/admin/session`, `/admin/employees*`; tắt writer user/RBAC cũ.
- [x] M5.7: Test token giả/hết hạn/sai loại, tự nâng quyền, user bị khóa, đổi quyền và đọc đơn/chat của người khác.

**Nghiệm thu:** tài khoản mới đăng ký ở Identity có thể đặt vé/viết review/chat mà không cần bản user ghi thủ công vào DB cũ; FK cũ không cản luồng mới. Mọi service bảo vệ dữ liệu kiểm tra danh tính/quyền theo contract.

Bằng chứng M5: [báo cáo Identity](docs/migration/identity-phase.md), [runbook](docs/runbooks/identity.md), [token/session contract](contracts/internal/identity.v1.md). Đã copy/đối chiếu 5 tài khoản và RBAC local, gỡ FK user liên miền, khóa writer cũ, chuyển auth của monolith/AI/Review/Notification. Session PostgreSQL và đăng nhập lại có kiểm soát theo ADR 0006 thay Redis auth.

### M6 — Tách Catalog Service

- [x] M6.1: Di chuyển films, genres, formats, film_genres, film_formats, food_items và combo_items.
- [x] M6.2: Tách `FoodService.quote` khỏi phần lưu snapshot: quote thuộc Catalog, `booking_food_items` tiếp tục thuộc miền Booking.
- [x] M6.3: Triển khai quote có ID/version/deadline, chính sách giữ giá và validation món/combo; tiền dùng Decimal.
- [x] M6.4: Refactor FK/relationship ngoài miền trong showtime/review/booking và caller admin; giữ film ID và snapshot lịch sử cần thiết.
- [x] M6.5: Chốt lifecycle phim/định dạng đã dùng bởi lịch/đơn: không hard-delete ID đã được công bố/sử dụng; thay bằng ngừng hoạt động có quy trình. Không dùng một HTTP kiểm tra tham chiếu rồi xóa nếu còn race với tạo lịch.
- [x] M6.6: Chuyển film/menu API và `/admin/films*`; chuyển phần catalog tương ứng trong `/admin/catalog` về gateway aggregation.
- [x] M6.7: Test lịch sử giá và thành phần combo không đổi khi sửa menu; giá client không quyết định tổng đơn.

**Nghiệm thu:** tạo phim mới dùng được trong lịch chiếu; quote mới dùng được trong booking legacy; không cần ghi lại film/menu gốc vào DB monolith để vượt FK. Khóa/xóa phim không để tạo lịch tham chiếu ID đã mất.

Bằng chứng M6: [báo cáo Catalog](docs/migration/catalog-phase.md), [runbook](docs/runbooks/catalog.md), [quote/lifecycle contract](contracts/internal/catalog.v1.md). Đã đối chiếu bảy bảng và tám tham chiếu lịch, chuyển gateway/aggregation, khóa source writer và gỡ FK/join Catalog ngoài miền. Grant chưa phải sales_version; tham chiếu sau lỗi source được giữ để đối soát, confirm/release tự động thuộc M7.

### M7 — Tách Cinema Service

- [x] M7.1: Di chuyển theaters, cinema_rooms, seats, seat_types và showtimes; constraint nội miền được giữ.
- [x] M7.2: Thay composite FK showtime–film/format bằng contract catalog có version và lifecycle đã chốt; validation thời lượng/định dạng vẫn bắt buộc.
- [x] M7.3: Xây `sales_version`: snapshot suất, phim, phòng, ghế và giá công bố cho booking; import đủ và ACK trước khi nhận hold.
- [x] M7.4: Thực hiện đóng nhận hold mới → xử lý hold/đơn đang có → sửa cấu hình → công bố phiên bản mới. Không sửa ghế/phòng/lịch tức thời qua cache trễ.
- [x] M7.5: Chuyển endpoint rạp/phòng/lịch/loại ghế và admin phòng/ghế/lịch/giá; `/seats` availability vẫn thuộc Booking.
- [x] M7.6: Thay join booking/seat vật lý/lịch ở caller bằng cấu hình bán vé và snapshot; dọn FK ngoài miền sau khi workflow thay thế đã kiểm thử.
- [x] M7.7: Test tạo lịch đồng thời, thêm ghế vượt sức chứa, khóa ghế có hold, đóng/mở bán lỗi giữa chừng và sửa giá trong lúc checkout.

**Nghiệm thu:** không lịch trùng, không bán từ phiên bản cấu hình thiếu dữ liệu; đã đóng bán thì hold mới bị từ chối; trạng thái tác vụ admin phản ánh hoàn tất thực tế của workflow.

Bằng chứng M7: [báo cáo Cinema](docs/migration/cinema-phase.md), [runbook](docs/runbooks/cinema.md), [sales contract](contracts/internal/cinema-sales.v1.md). Đã đối chiếu năm bảng, tám publication/ACK và chuyển gateway local; giữ đóng tám suất đã qua giờ. Các số liệu load/SLA M0.7 vẫn mở.

### M8 — Cô lập Booking và chuẩn bị tách Payment

- [x] M8.1: Gom seat_status, bookings, booking_details, booking_food_items, tickets và nghiệp vụ expiry vào module/khối Booking rõ ràng.
- [x] M8.2: Bổ sung reservation/hold ID gắn với đơn, idempotency key tạo đơn và cập nhật nguyên tử nhiều ghế theo thứ tự lock ổn định.
- [x] M8.3: Dùng snapshot sales và quote catalog, không đọc DB Cinema/Catalog; refactor lịch sử đơn để không phụ thuộc join dữ liệu gốc ngoài miền.
- [x] M8.4: Tạo checkout snapshot bất biến có booking version, amount/currency/deadline; thiết kế consumer payment và event từ booking.
- [x] M8.5: Chuẩn bị image/schema migration cho khối booking/payment legacy. Chuyển khối này sang DB giao dịch riêng nếu còn nằm DB legacy, giữ transaction payment–seat–ticket hiện tại trong bước này.
- [x] M8.6: Gateway `/seats*`, `/bookings*`, `/tickets*` và `/payment/*` trỏ đúng khối tạm; không tuyên bố đã tách Payment riêng.
- [x] M8.7: Tắt expiry scheduler cũ khi scheduler mới nhận nhiệm vụ; test expiry cạnh tranh payment/check-in và giữ nhiều ghế.

**Nghiệm thu:** booking không import ORM Identity/Catalog/Cinema/AI/Review; khối booking/payment legacy tự vận hành, test concurrency và E2E đạt baseline. Dữ liệu của từng miền đã tách trước đó không còn được truy vấn trực tiếp.

Bằng chứng M8: [báo cáo Booking](docs/migration/booking-phase.md), [runbook](docs/runbooks/booking.md), [checkout/reservation contract](contracts/internal/booking.v1.md). Đã chuyển khối Booking/payment legacy sang store riêng, giữ snapshot/idempotency/expiry và tắt source scheduler/relay; Payment chưa là service độc lập.

### M9 — Tách Payment Service và hoàn thiện luồng phân tán

- [x] M9.1: Tạo DB payment riêng cho attempts, provider result, outbox/inbox và hồ sơ đối soát; giữ merchant_ref unique và lịch sử giao dịch.
- [x] M9.2: Payment lấy checkout snapshot có xác thực từ Booking; không nhận tổng tiền tin cậy từ frontend; idempotency và nhiều attempts có chính sách rõ.
- [x] M9.3: Chuyển VNPay URL/return/IPN/status về Payment; giữ URL callback tương thích và toàn bộ kiểm tra chữ ký/ref/merchant/amount.
- [x] M9.4: Payment ghi provider result và event cùng transaction; Booking inbox dedup rồi xác nhận đơn + BOOKED + vé + outbox trong một transaction local.
- [x] M9.5: Trường hợp hold/đơn hết hạn: giữ payment PAID, không cấp vé, tạo kết quả từ chối xác nhận và hồ sơ xử lý tiền. Chưa tự refund nếu chưa xây và kiểm chứng tích hợp hoàn tiền.
- [x] M9.6: Frontend phân biệt “provider đã thu tiền”, “đang xác nhận vé”, “đã có vé”, “cần hỗ trợ/đối soát”; không suy ra vé đã cấp từ trang return.
- [x] M9.7: Job đối soát tìm PAID chưa CONFIRMED, event kẹt, số tiền khác và attempt trùng; có cảnh báo và runbook xử lý.
- [x] M9.8: Cutover một owner duy nhất cho callback/payment attempts; loại mọi import/ghi trực tiếp payment → booking/seat/ticket.
- [x] M9.9: Test return/IPN trùng/đảo thứ tự, timeout sau commit, broker dừng, consumer chết trước ACK, PAID sau expiry và tiền thu hai lần ở hai attempt.

**Nghiệm thu:** không bán trùng ghế/phát vé trùng, không mất kết quả provider, không tự chuyển PAID thành FAILED để che lỗi xác nhận; mọi khoản tiền không có vé xuất hiện trong hàng đối soát. Email chỉ đi sau BookingConfirmed.

Bằng chứng M9: [báo cáo Payment](docs/migration/payment-phase.md), [runbook](docs/runbooks/payment.md), [contract](contracts/internal/payment.v1.md). Đã copy/verify hai giao dịch, giữ 320.000đ và hai vé; legacy callback bị fence, các service local healthy. Tích hợp provider/refund thật và ngưỡng load production chưa thuộc nghiệm thu local.

### M10 — Reporting, cấu trúc cuối và vận hành

- [x] M10.1: Dựng DB read model, event consumer, inbox, watermark và API/CSV báo cáo.
- [x] M10.2: Backfill từ snapshot có mốc; đồng bộ event từ checkpoint, tránh khoảng trống giữa snapshot và stream. Phát hiện update/delete/version cũ.
- [x] M10.3: Đối chiếu semantics báo cáo cũ: ngày chiếu/giờ Việt Nam, doanh thu gồm món, không nhân do nhiều attempts, vé hợp lệ và sentiment đúng phiên bản.
- [x] M10.4: Chuyển `/admin/reports` và hiển thị thời điểm cập nhật dữ liệu; bỏ join báo cáo xuyên DB gốc.
- [x] M10.5: Chuyển `Frontend/` sang `apps/web/`, tách pipeline ML khỏi runtime request, cập nhật tài liệu/lệnh CI và Compose cuối.
- [x] M10.6: Kiểm tra credential: mỗi service chỉ truy cập DB được sở hữu; không còn signing/payment/SMTP secrets trong frontend hoặc service không liên quan.
- [x] M10.7: Diễn tập restore, broker outage, DLQ replay, auth outage, AI outage và đối soát sau phục hồi.
- [x] M10.8: Tắt monolith/route/job cũ sau nghiệm thu; giữ dữ liệu legacy chỉ đọc theo thời hạn, rồi mới có đợt dọn riêng.

**Nghiệm thu:** 9 service và gateway có build/test/migration riêng; React hoạt động qua gateway; báo cáo đối chiếu đúng; dừng `Backend` legacy không làm mất chức năng; không SQL/import ORM xuyên owner.

**Bằng chứng M10/M0.7:** [báo cáo Reporting](docs/migration/reporting-phase.md), [runtime](docs/runbooks/final-runtime.md), [contract](contracts/internal/reporting.v1.md). 33 facts có checksum, 36 response và 2 lịch sử đơn giữ nguyên; backup/restore 10 DB; diễn tập outage/DLQ và đo tải local đạt. Legacy giữ archive tối thiểu 30 ngày, không xóa trong mốc này. Model sentiment production chưa được cung cấp, backend local tắt; deployment/provider thật và SLA production thuộc môi trường đích.

## 5. Quy trình chuyển dữ liệu bắt buộc ở M3–M10

| Bước | Việc phải làm | Bằng chứng |
| --- | --- | --- |
| Chuẩn bị | Inventory FK/ORM/query/task/callback, tạo schema mới và contract thay thế | Checklist dependency hết chỗ chưa rõ |
| Sao chép | Snapshot/backfill, giữ ID, decimal, timezone, UUID và sequence | Count/checksum, mẫu đối chiếu và báo cáo lỗi |
| Thử đọc | Compare response/shadow read bằng dữ liệu an toàn | Diff contract; không shadow tác vụ có tác dụng phụ |
| Dừng ghi | Chặn writer miền cũ, đợi transaction đang chạy, chuyển delta cuối | Writer freeze được xác nhận |
| Chuyển owner | Đổi route/caller/job/credential và bật writer mới | Chỉ một writer; smoke test và metrics đạt ngưỡng |
| Theo dõi | Quan sát lag, lỗi, đối soát và dữ liệu liên quan | Nhật ký cutover có checkpoint |
| Kết thúc | Legacy chỉ đọc; gỡ dependency sau đối chiếu | Không còn caller/task ghi vào owner cũ |

Trước khi có ghi ở DB mới, có thể quay route về owner cũ nếu chưa thay đổi không tương thích. Sau khi DB mới nhận ghi, quay lui phải đồng bộ dữ liệu ngược hoặc sửa tiến; không đổi route về bản DB cũ đang thiếu dữ liệu.

Mọi mốc cần phương án sửa các FK ở cả hai phía và ORM relationship đang trỏ vào bảng đã di chuyển. Chỉ copy bảng hoặc đổi `DATABASE_URL` không hoàn tất việc tách service.

## 6. Các điều kiện không được bỏ qua

| Điều kiện | Mốc kiểm chứng |
| --- | --- |
| Bản backup có thể restore và test baseline phân biệt lỗi cũ/mới | M0 |
| Ghi nghiệp vụ và event không mất nhau; replay không lặp tác dụng DB | M1–M2, lặp lại với handler thực tế ở M9 |
| Tài khoản khóa/thu hồi quyền không tiếp tục dùng API nhạy cảm ngoài thời hạn contract | M1, M5 |
| Tạo entity mới không cần chép dữ liệu gốc vào DB cũ để thỏa FK | M3–M7 |
| Không thay đổi snapshot giá/ghế/lịch đã dùng cho đơn | M6–M8 |
| Không bán trùng khi Redis/broker lỗi hoặc worker chạy đồng thời | M7–M9 |
| Khoản tiền đã thu nhưng không có vé luôn được phát hiện/đối soát | M9 |
| Báo cáo replay/backfill không nhân doanh thu hoặc cảm xúc | M10 |

Service mới fail giữa cutover thì dừng đợt chuyển miền đó, giữ trạng thái writer rõ ràng và dùng runbook tương ứng. Chỉ chuyển tiếp sau khi điều kiện nghiệm thu đạt; không tăng số service đang chuyển đồng thời để bù tiến độ.

## 7. Đợt công việc đầu tiên để bắt đầu triển khai

Phạm vi đợt đầu là **M0 + gateway tương thích trong M1**, tạo nền cho các mốc sau.

| PR dự kiến | Công việc | Kiểm chứng |
| --- | --- | --- |
| `codex/microservices-baseline` | Baseline, OpenAPI/fixtures, dependency map, runbook restore, ADR ownership | Tài liệu có evidence; test DB riêng; chưa chuyển owner |
| `codex/microservices-gateway` | Gateway `/api` → backend, cấu hình local, timeout, trace ID, callback pass-through | Auth/ghế/booking/food/payment/admin qua gateway; thứ tự review route đúng |
| `codex/microservices-contracts` | Service template, auth adapter nội bộ, version/error/event conventions và CI phù hợp | Không nhận user header giả; template migrate/test độc lập |
| `codex/microservices-messaging` | Broker, producer outbox/consumer inbox, retry/DLQ, replay test | Crash/duplicate/rollback được kiểm chứng bằng test thực tế |
| `codex/notification-service` | Service nghiệp vụ đầu tiên; cutover email có delivery store | SMTP lỗi không làm hỏng vé; một đường gửi đang hoạt động |

Tên trên là gợi ý nhánh/PR, chưa được tạo. Có thể chia nhỏ PR theo độ lớn thực tế, nhưng PR sau phụ thuộc contract hoặc schema phải bắt đầu từ trạng thái đã tích hợp của PR trước.

## 8. Cách đánh giá tiến độ

Mỗi PR ghi: vấn đề và hành vi sau thay đổi, owner DB trước/sau, API/event thay đổi, migration/backfill, kiểm thử đã chạy, giới hạn còn lại và cách quay lui. Theo dõi bằng task ID trong tài liệu này và liên kết PR/evidence khi có.

Ba chỉ số tiến độ chính: số miền đã có writer độc lập, số dependency DB/ORM xuyên miền còn lại và số luồng nghiệp vụ qua gateway đã kiểm chứng. Số folder/container tạo được chỉ là thông tin phụ.

Kế hoạch chỉ hoàn tất khi người dùng vẫn đăng nhập, tra phim/rạp, chọn ghế/món, thanh toán, nhận/xem/check-in vé và dùng các chức năng admin/review/AI qua hệ thống mới; đồng thời có thể dừng legacy an toàn.

## 9. Tài liệu tham chiếu

- [Kiến trúc và inventory hiện tại của Cinema Booking](PROJECT_STRUCTURE_MICROSERVICES.md): 224 tệp trên Git, 90 tổ hợp method/path và 28 bảng tại baseline khảo sát.
- [AWS — Strangler fig pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html): chuyển từng phần qua proxy và adapter.
- [Microsoft — Data considerations for microservices](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/data-considerations): dữ liệu do từng service sở hữu; có thể chung máy DB nhưng tách store/quyền truy cập.
- [AWS — Transactional outbox pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html): state/event cùng transaction và xử lý duplicate ở consumer.

Checkbox đã đánh dấu có bằng chứng trong báo cáo baseline; các mục còn mở và tên nhánh/PR dự kiến vẫn là kế hoạch. M1.8 hiện có CI gateway/frontend/regression và kiểm tra source contracts; sẽ mở rộng khi có service nghiệp vụ mới.
