# Catalog v1

Public contract: [OpenAPI](../openapi/catalog.v1.json). Gateway routes films/menu/admin films to Catalog, keeping Review routes before the general films rule. Film list/detail and menu retain the existing response shapes and slash redirects. `GET /admin/catalog` is composed in the gateway: Catalog supplies genres/formats/films, legacy Cinema supplies theaters/rooms. Both owners independently check the same bearer with Identity; incomplete/unauthorized results are never returned as a successful partial catalog.

Catalog owns seven tables: films, genres, formats, film_genres, film_formats, food_items, combo_items. Its additional tables are schedule_bindings and food_quotes. No runtime connection to another owner's DB is allowed.

## Film and format lifecycle

Film and format IDs are permanent business references; public delete soft-retires a film and does not hard-delete its row or published IDs. Films with schedule references cannot be retired through the current API. A film update may change display metadata, but cannot remove a referenced format, shrink release dates around an active reference, or exceed its scheduled duration.

Before saving a new/changed schedule, Cinema's legacy writer requests an immutable binding with a fresh UUID and full film/format/date/time facts. Catalog locks the Film row in the same transaction used for retirement and metadata edits, checks active/release/duration/format, and saves the binding/snapshot before returning. The source stores that binding ID and snapshot, then commits its own room-conflict/hold/order checks. No user-supplied binding ID, film snapshot or price is accepted by the public schedule/booking inputs.

Grant versus retire/edit races are serialized on the Catalog Film lock. The source has no Catalog FK and cannot mirror a film to pass validation. Its persistent ownership trigger rejects frozen schedule writes, missing service-mode binding/snapshot, and schedule changes that reuse the previous binding. Source room locks still serialize overlapping schedules.

A binding retry with the same ID and facts returns the originally granted snapshot; reusing that ID for different facts returns 409. Display edits do not mutate past bindings or booking history. Booking copies the schedule's film snapshot; historical order/confirmation labels come from published facts, including during Catalog maintenance/outage. Reports preserve current film labels through a Catalog batch API while aggregating money once per film.

Bindings are conservative references, not proof that the source schedule committed. Common invalid room/time/conflict requests are rejected before requesting a grant, then rechecked under source locks. If a race/timeout/ambiguous commit follows a grant, its reference is retained and may block retirement/format/date changes even if no source schedule is visible. Do not expire/delete such references automatically: an in-flight source writer could still commit. Inspect/reconcile before any release; automated confirmation/release/close-sales workflow belongs with Cinema M7. Existing/canceled historical references are also retained. A 409 leaves the film intact and does not report a completed retirement.

## Food quotes and money

`FoodService.quote` now calls Catalog; Booking keeps ownership of booking_food_items. Quote input is only item IDs and integer quantities (1–20, at most 50 selections, no duplicates). Only active items and complete, active, non-nested combos can be quoted. Catalog computes money with Decimal/Numeric(12,2); client prices do not determine the total. Current menu administration uses the existing `films.manage` Catalog permission, including new `/admin/food-items` routes.

Each quote has UUID `id`, immutable revision `version=1`, VND currency, server-computed total, full line/name/price/component snapshot, item catalog versions, and an aware UTC `expires_at`. Default validity is 120 seconds (configurable 30–600). Menu edits and quote construction serialize on one Catalog transaction advisory lock. Each menu edit increments the edited item's version; a fresh quote gets a new ID. Already issued quotes remain unchanged and retain their original price/components until expiry, including if the menu changes or an item is subsequently deactivated.

Legacy booking requests a fresh quote server-to-server, validates returned IDs/quantities/total/currency and deadline, compares the client's overall total to server seat prices plus the quote, and checks expiry again before saving food snapshots. The booking stores quote ID/revision/deadline. A quote never extends the seat hold or supplies an authoritative seat price. Empty food selection needs no Catalog quote. Expired/invalid selections return 400/409/422; dependency failures return 503 through the legacy adapter. Confirmation/history/email use stored snapshots, not a fresh quote or current menu. Quotes are retained as audit facts; no automatic row deletion is introduced in M6.

## Private API

All paths require a configured `X-Service-Key` (minimum 32 characters). Gateway blocks `/internal`; API/service credentials are never supplied by the browser. Auth uses current Identity introspection for admin/public quote actions, with no signing key in Catalog.

| Method/path | Input | Result |
| --- | --- | --- |
| POST `/internal/v1/films/batch` | `{ids:[...],include_retired:false}`, max 200 | Typed film facts, catalog_version, genres/formats/IDs; missing IDs omitted |
| POST `/internal/v1/films/search` | `{q,skip,limit,now_showing}` | Active film facts; literal escaped title search, max 200 |
| POST `/internal/v1/films/matches` | `{message}` | Case/accent-folded active title matches for the AI facade |
| POST `/internal/v1/schedule-bindings` | `{id,film_id,format_id,show_date,start_time,end_time}` | `{id,film_version,film_snapshot}` |
| POST `/internal/v1/food-quotes` | `{selections:[{food_item_id,quantity}]}` | Immutable quote above |
| GET `/internal/v1/food-quotes/{id}` | — | Original quote; 404 missing, 409 expired |
| GET `/internal/v1/migration/state` | — | `{writes_enabled}` |

HTTP adapters use a 5-second timeout and fail closed; transferred source archive tables are never fallback reads. AI search text is sent in JSON bodies, not URL queries. No payload/token/header logging. Runtime Catalog has only its DB credential and internal auth credential; backfill is a separate privileged job with temporary access to the source. Local HTTP is private Compose traffic; production TLS/mTLS/HA remain deployment work.
