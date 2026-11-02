# Cinema → Booking sales v1

Cinema owns theaters, rooms, physical seats, seat types/prices and showtimes. Booking owns availability/holds, orders, payment legacy and tickets. Booking never joins the five archived Cinema tables after ownership transfer.

Private APIs require `X-Service-Key` and are blocked at the public gateway. Origins are fixed configuration. Runtime Cinema connects only to its own PostgreSQL database. The one-shot migration profile alone receives the source credential.

## Publication protocol

For each showtime, Cinema assigns an increasing `sales_version`. The complete snapshot contains Catalog binding UUID and film version/format facts, room/theater facts, local date/times, status, declared seat count and every seat ID/name/type/status/Decimal price. Duplicate IDs/names, truncated seat maps, unsupported format facts, invalid intervals and capacity violations are rejected. See [JSON schemas](../cinema-sales/v1/import.schema.json).

Digest: SHA-256 of the validated model's JSON representation, recursively sorted keys, UTF-8, unescaped Unicode and compact separators. Decimal prices use their JSON strings. Producers persist the complete payload and digest; retries reuse that exact payload/version.

| Booking private route | Body | Required response |
| --- | --- | --- |
| `POST /internal/v1/sales/{id}/close` | `epoch` | Same epoch, `is_open=false` |
| `GET /internal/v1/sales/{id}/state` | Optional `seat_id` query | Epoch/version/open state; live hold, pending checkout, history, seat reference counts and booked IDs |
| `POST /internal/v1/sales/{id}/import` | `epoch`, `snapshot`, `digest` | Exact showtime/version/digest/epoch and `acknowledged=true` |
| `POST /internal/v1/sales/{id}/open` | `epoch`, `sales_version`, `digest` | Exact version/digest/epoch and `is_open=true` |

Epoch is monotonic across actions. Repeated commands are accepted only for the same action and immutable facts. A delayed open/import cannot overtake a newer close. Import is atomic, requires a closed gate and refuses new versions while live holds or unexpired pending checkouts remain. Open requires the acknowledged current configuration, future start, active room/show and sellable seats.

The Booking gate row serializes close/import/open against new holds and checkout. Closing disallows new/extended holds but allows existing valid holders to complete checkout at their published version/price. Import preserves schedule facts once any order exists and preserves booked seat identities. Old configurations and BookingDetail prices are immutable. Paid seats remain occupied across later versions. Payment callbacks, ticketing and order history use the order's local snapshot even when Cinema is unavailable.

## Durable administrative changes

Room/seat/showtime/price changes return HTTP `202` with `operation_id`, status, phase and message. This means accepted, not applied. `GET /admin/cinema-operations` and `GET /admin/cinema-operations/{id}` expose permission-filtered progress. Creation and reads check live Identity permissions; an accepted job continues independently of the caller's login session and stores only the actor ID.

Phases: `CLOSING → DRAINING → APPLYING → PUBLISHING → CATALOG_FINALIZE → DONE`. Status may be `PENDING`, `WAITING`, `RETRY`, `DONE` or `FAILED`. A room has one active operation; room moves lock both rooms in ID order. A per-operation PostgreSQL session advisory lock spans phase commits and prevents two workers from executing the same job. Worker crash releases that lock; persisted payload/epochs resume processing. Mutation and publication creation commit together.

Changes wait for holds/checkout; booked/referenced seats cannot be removed or disabled, and shows with order history cannot be moved/retimed/deleted. Database exclusion and capacity guards also reject concurrent invalid raw writes. A failed change leaves affected sales closed; only a new explicit open/publish may recover selling after checking the current configuration.

## Catalog references

Binding states are `RESERVED`, `CONFIRMED`, `RELEASED`. Cinema confirms with `cinema-showtime:{id}` after publication. A replaced/deleted reference is released after the local change is sealed. Rejected unapplied changes enter durable `COMPENSATING`, release with `cinema-operation:{uuid}`, then become `FAILED`. Catalog persists closure tombstones even if release arrives before a delayed bind; released IDs cannot bind or confirm again. Grants and closures serialize on the binding ID, and film mutation/grants serialize on the film row. No TTL automatically releases a reference.

## Public routing

Cinema: `/theaters*`, `/cinema-rooms*`, `/showtimes*`, `/seat-types*`, admin rooms/seats/showtimes/prices/operations/theaters. New theater/room creation is immediate because no published configuration references a new entity. `POST /admin/showtimes/{id}/sales/{close|open|publish}` uses the same durable job flow. Public schedule lists expose open sales; detail/history snapshots remain readable for closed/past shows.

`/seats*`, `/bookings*`, `/tickets*`, `/payment/*` remain in the source Booking/payment deployment. Gateway `/admin/catalog` aggregates Cinema and Catalog with the same bearer authorization and rejects incomplete responses. Cinema is optional for global gateway readiness so an outage does not suppress already-published Booking/payment/history operations.
