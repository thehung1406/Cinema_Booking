# Payment boundary v1

Payment owns its PostgreSQL ledger, checkout registry, append-only provider results,
fulfillment acknowledgements, reconciliation cases and outbox/inbox. Runtime has
no Booking DB URL, Booking ORM import, cross-database FK or seat/ticket write.
The privileged frozen-copy command is a separate migration profile.

`GET Booking /internal/v1/checkouts/{booking_id}` requires `X-Service-Key` and
returns booking/version/reservation, digest, amount/currency/deadline, user_id,
payment_method/date and current order/payment status. No customer contact data.
Payment validates the authenticated user against this fresh server fact before
creating/reusing an attempt. A pending attempt is reused; a failed attempt may be
replaced while checkout remains payable. Any PAID attempt prevents another URL.
Signature creation/expiry dates remain stable for an existing attempt.

`/payment/vnpay-url`, GET/POST `vnpay-return`, GET/POST `vnpay-ipn` and authenticated
`/payment/status/{booking_id}` retain their paths through the gateway. Amount is
server-derived. Merchant/ref/HMAC-SHA512 and integer provider amount are checked.
Invalid signatures create no financial result. Valid signed amount mismatches
retain collected evidence and create a case, while IPN reports code 04.
Deduplication normalizes financial fields, so bank/return-only extra fields do
not create another capture. PAID never transitions to FAILED/CANCELLED.

Payment's result transaction saves provider evidence, PAID, fulfillment PENDING,
cases and `PaymentCaptured.v1` together. Callback acknowledgement never waits for
Booking or RabbitMQ. Publisher confirms precede outbox PUBLISHED; consumer ACK
follows local commit. Stable event IDs and inbox payload hashes detect duplicates
and reject the reuse of an event ID with different contents.

| Event | Producer | Aggregate | Data schema |
| --- | --- | --- | --- |
| PaymentCaptured.v1 | payment | payment:{id}, version 1 | ../events/v1/PaymentCaptured.schema.json |
| PaymentBookingResult.v1 | booking | payment:{id}, version 1 | ../events/v1/PaymentBookingResult.schema.json |

Booking locks its sales gate, reservation/order and sorted seats. Inbox, payment
receipt, order/reservation, BOOKED seats, tickets, BookingConfirmed, private email
request and result outbox commit together. Exactly one CONFIRMED receipt is
allowed per checkout version. Late/duplicate/mismatched payments receive a sealed
REJECTED outcome and no new tickets. Money remains PAID even for an EXPIRED or
CANCELLED Booking, and newer reservations are never released or consumed.

`GET Booking /internal/v1/payment-results/{payment_id}` returns the sealed result
using the same private credential. Reconciliation can recover a lost result over
HTTP without holding a financial/seat lock during the network call. Its recovery
inbox identity is distinct and deterministic; a later real ACK remains harmless.

`fulfillment_status` is AWAITING_PAYMENT, FAILED, PROCESSING, ISSUED or
REQUIRES_REVIEW. `provider_status=PAID` alone never means a ticket exists.
`requires_review` can coexist with ISSUED when an extra payment needs handling.
Return carries `booking:null`; personal order details and ticket codes require
the existing authenticated Booking endpoints. The UI renders only those codes.

`GET /admin/payment-reconciliation` and audited POST `/{case_id}/retry` require
`reports.view`. Lists include the booking/payment IDs, expected money and provider
references. Retry preserves the same capture ID; it cannot issue an artificial
provider result, close a money case or refund a customer.

Public RabbitMQ queues: `booking.payment.v1` (PaymentCaptured) and
`payment.booking.v1` (CheckoutCreated, BookingExpired, PaymentBookingResult).
Both have durable DLQs via `cinema.saga.dead.v1`. Booking consumer can read only
its queue. Payment worker/relay can access only Payment DB and the public vhost;
only Payment API receives the merchant signing key.
