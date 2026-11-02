# Booking M8 — reservations, checkout and temporary payment

Booking owns seat_status, bookings, booking_details, booking_food_items, tickets, reservations, checkout_snapshots, booking_idempotency and the local sales projection/gate. **Legacy VNPay payments remain in the same database/deployment and transaction.** Enabling the gateway's payment route here does not make Payment an independent service.

Runtime imports only owned ORM models, shared messaging/auth infrastructure and wire schemas. Identity contacts/introspection and Catalog food quotes use fixed-origin private HTTP APIs. Cinema publishes through [sales v1](cinema-sales.v1.md) directly to Booking. No source/Cinema/Catalog/Identity/AI/Review database credential or ORM is required.

## Reservations

Public seat URLs and existing response fields remain compatible. Hold/availability responses add `reservation_id`; availability exposes it only to the authenticated holder. Hold/release bodies may supply that ID to reject an old tab's action after a reservation was replaced. Anonymous readers never receive another holder's ID or user ID.

One user/show has at most one ACTIVE/CHECKOUT reservation. A first hold creates a UUID with a fixed 600-second deadline; adding/retrying seats does not extend it. The seat set is mutable only while ACTIVE. Requests reject duplicates, invalid/inactive seats and more than 20 seats. Multi-seat updates are atomic, using the show gate and ascending seat IDs. A failed request keeps none of its newly requested seats.

Checkout seals the exact selected seat set. Holds in CHECKOUT cannot be released through the seat API; cancel the pending order through the authorized order flow. CONFIRMED/EXPIRED/RELEASED reservations cannot be resurrected. Source projection gates still implement close/drain/import/ACK/open, so an existing holder may checkout after close while new/extended holds are rejected.

## Create order and idempotency

`POST /bookings` accepts the existing body, optional `reservationId`, and `Idempotency-Key` (1–128 printable ASCII characters). The key is scoped by authenticated user. A transaction advisory lock serializes that key; the immutable request fingerprint covers user/show/reservation, sorted seats/food quantities, Decimal total and method. Same key/body replays the committed original response; same key/different body is 409. A reservation has at most one order, including when callers use different keys. Compatibility callers without a key receive a reservation-scoped fallback key; the server can infer the sole active reservation when its ID is absent.

The server takes seat/price/film/room facts from the exact local sales version and obtains a validated Catalog food quote. Client seat prices are ignored; a mismatched total is rejected. The deadline is checked again after dependent calls and is never extended. Order, price/component snapshots, checkout, idempotency response and `CheckoutCreated.v1` outbox commit together.

The frontend keeps the first request body/key in session storage scoped to user/show/reservation. An unknown result (network/5xx) offers retry of that same request, including after reload. Known validation errors can clear an uncommitted attempt so the user can correct the basket. A successful retry returns the same booking ID.

## Immutable checkout and the M9 boundary

Each order has booking version 1, currency VND, immutable amount/deadline, reservation and sales version references, and a SHA-256 checksum over its complete local checkout snapshot. Customer, ticket-price and food/component facts are copied at creation. SQL guards protect checkout rows, financial/order identity, deadlines, sealed reservation seats, paid results and old sales configurations. History and provider confirmation use local facts even when Catalog/Cinema are unavailable.

`GET /internal/v1/checkouts/{booking_id}` requires the service key and returns booking ID/version, reservation ID, amount (Decimal string), currency, deadline, digest and current booking/payment status. It omits customer/food/film details. A future M9 Payment consumer should consume `CheckoutCreated.v1`, deduplicate by event ID and checkout version, retrieve/validate this private contract, and persist its attempt/provider evidence and events transactionally. **No separate Payment event consumer/saga is activated in M8.**

Public outbox facts `CheckoutCreated.v1` and `BookingExpired.v1` contain:

```json
{
  "booking_id": 123,
  "booking_version": 1,
  "reservation_id": "00000000-0000-4000-8000-000000000001",
  "amount": "150000.00",
  "currency": "VND",
  "deadline": "2026-11-02T14:10:00+00:00",
  "showtime_id": 456,
  "sales_version": 2
}
```

These contain no contact/token fields. Stable UUID5 event IDs and aggregate versions support replay/deduplication. Existing `BookingConfirmed.v1` and private `BookingConfirmationEmailRequested.v1` remain compatible; only the private notification destination contains the allowed email snapshot.

## VNPay, expiry and tickets

All modifying flows take gate → reservation/booking → seats in ID order → ticket locks. No Redis lock/cache authorizes ownership in this block. Expiry and callback serialize through the same PostgreSQL gate; check-in also locks the owning order first. Expiry is a dedicated Booking worker, not the source Celery scheduler.

VNPay paths/signature checks/merchant references/amount checks and Return/IPN shapes stay compatible. Repeated URL creation reuses the current pending attempt. Confirmation updates attempt, owned same-reservation holds, order, tickets and outbox in one transaction. A duplicate callback does not reissue tickets/events. A validated paid provider result survives a failed confirmation for reconciliation. A late result retains PAID on the attempt but cannot issue tickets for an expired order or consume another reservation's new hold. Do not interpret attempt PAID as proof that Booking issued tickets.

## Private read facades

`/internal/v1/booking-read/{report,verified,candidates,context,tool}` supply source Reporting/Review/AI adapters. Report facts use local paid-attempt/order/ticket evidence and published seat slots; the source adapter adds current Catalog labels and Review sentiment by HTTP. `/legacy-email` drains an explicitly queued old task into the existing deterministic notification event ID; it never sends SMTP itself. All private paths require the service credential and are blocked at the public gateway.
