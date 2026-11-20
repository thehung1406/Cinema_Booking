GATE: OPEN 14 (rounds used up)

# Editorial frontend rebuild — 2026-11-20

## FE pull request verification — 20/11/2026

At the user's request, the existing FE work was applied to `feat/editorial-frontend` from current `main` (`261db8f`). The latest chatbot fixes were retained. This PR includes `apps/web` and this report; unrelated backend, Compose and diagram edits remain excluded. Source edits in `D:\Cinema_Booking` were preserved as a local copy.

Fresh checks on this branch: 13 unit tests, ESLint and production build passed; 11 web contract tests passed. The built preview at port 5175 passed all 105 UI-smoke layouts, plus auth, food, payment, admin, AI and chat-booking browser workflows using isolated API fixtures. No real payment was made. Production JS is 471.38 KB before compression (146.42 KB gzip).

PR review found a new laptop-height regression: grouped admin navigation could hide its final links at 1440×768. Added a browser test that failed against the old build, then enabled vertical scrolling on the sidebar. The rebuilt preview passed the full admin workflow, including that reachability regression and the existing mobile/desktop viewport sweep.

`npm audit` reports 21 existing advisories (3 low, 3 moderate, 14 high, 1 critical). The dependency lockfile is unchanged; upgrading dependencies was not included in this packaging task. The 14 open design-skill checker findings listed below are retained and this report does not claim a passing design gate.

## Scope and design

Implemented the approved 26-page plan in apps/web. Customer pages first, then admin. Existing React/Vite/Tailwind stack, APIs, auth, route aliases, permissions, payment fulfillment rules and checkout storage contracts are retained. No application dependencies added.

Paper #F7F6F3, white surfaces, ink #20232C, CGV #C92530. Newsreader display / Hanken Grotesk text, locally hosted Latin and Vietnamese WOFF2 with OFL licenses. One layout scale, full-screen native mobile menu, poster-led editorial hero without carousel, shared buttons/cards/forms, responsive seat and admin table scrolling. Movie state is stored in ?status=all|showing|upcoming. No new backend endpoints.

## Implementation ledger

- Foundation: light tokens, fonts, shared primitives, header/menu/footer, motion layer, responsive grid and local neutral poster fallback.
- Customer pages 1–3: editorial home, URL-filtered film catalogue, light detail and existing reviews/trailer.
- Pages 4–8: schedule summary with poster, non-purple seat states, food cards, shared payment/order presentation, electronic-ticket QR styling. Financial logic unchanged.
- Pages 9–15: split login, account expandable order details, cinema retry/empty states, light AI and advanced showtime field, concise factual About, support FAQ without simulated submission, Vietnamese context-aware 404.
- Pages 16–26: light admin and grouped navigation, thumbnails/media preview, grouped permission controls, compact asynchronous operation status, advanced knowledge search, revenue comparison meters, styled reconciliation and moderation. Existing editors and CRUD controls retained.
- Vendor: copied skill motion CSS and word-highlight module/helper unchanged. A small React component mounts/unmounts the optional statement animation; a failed import leaves readable static content. No imperative kit form binding.

## Decisions and skill exceptions

- Work in the existing codex feature branch; preserve unrelated preexisting backend/docs changes. No commit, merge, push or deployment requested.
- Scope the layout to real cinema task flows. Booking, catalogue, AI, data tables, footer and short informational blocks grow naturally. Sticky summaries, region scrolling, QR values and seat/film metadata are functional UI, not marketing captions to remove.
- Keep actual movie titles even when unusually long; never invent a short title for visual checks. Missing API media uses the local fallback; no stock cinema or food imagery was presented as this client's.
- Keep all positive-trending results and filters rather than create a new route to meet an artificial section limit.
- Existing hardcoded support email is reused as a compose action. The website does not claim delivery; contact address has not been independently verified.
- No fabricated corporate counts, discounts, testimonials, loyalty features, password recovery, chart series, geolocation or payment timers.

## Verification

Baseline: npm test 13/13, lint and Vite build passed. Existing UI-smoke fixtures lacked current payment/status and ticket endpoints and reservationId; these were corrected to the unchanged application contract.

UI smoke: 105 layouts at 320/375/390/768/820/1024/1440; no overflow, undersized buttons or browser runtime errors. Covers URL filter navigation/reload, menu Escape/focus, cinema context, support without fake submit, trailer, seat hold/release, checkout, payment errors, result states, profile, AI history and reduced motion.

Food, payment, admin, AI and chat-booking workflows passed with isolated network fixtures. Web contracts: 11/11 passed through Python standard-library runpy (pytest is not installed). Additional admin viewport sweep and final build/checker outcomes will be appended below.

## Limits

No live VNPay transaction, backend concurrency or real QR scanning was performed. Separate annotation app test requires its own server at localhost:8770 and an installed Playwright browser; it is not the React moderation page and was not changed. Screenshots and browser profiles are local ignored artifacts under apps/web/.taste-skill.


## Final review and fixes

Independent reviewer found one important handoff issue: choosing the first film discarded the cinema passed from the cinema page. Added a browser assertion, observed it fail (empty selection instead of theater 1), then preserved that incoming selection until the existing by-film lookup validates availability. Subsequent film changes still reset dependent choices.

Vite on Windows crashed while watching the checker's locked Chrome profile database. Added an explicit watch ignore for .taste-skill, keeping visual QA artifacts out of HMR.

The admin workflow viewport sweep passed 54 page/viewport combinations across nine admin routes at 320/390/768/820/1024/1440. Payment reconciliation remains covered by the dedicated payment workflow.


Final application checks: lint, production build and 13 unit tests pass after the review fix. The expanded customer browser suite passes all 105 layouts after the cinema handoff regression assertion; 11 web contracts remain green. There are no deferred important review findings.

Skill checker status: initial consistency probe was incomplete when Vite stopped on a locked browser profile; watch ignore fixes that crash. The separate layout checker then raised its own TypeError (r.sections is not iterable / undefined map) against the React layout; vendor scripts were not edited. The first gate run on / returned GATE: FAIL 19: it saw the real API-unavailable state (backend is not running), plus static-document assumptions such as a .wrap container, direct body/header/main structure, one-line logo and full-screen footer. These are not evidence of a passing visual gate. Functional and viewport assertions use isolated fixtures, not invented application data. A static /about gate and performance result follow below.


The second gate (/about) reported GATE: FAIL 26 (round 2/3). It includes static structure/full-screen section/photo requirements that conflict with the explicitly approved React/task-layout exceptions. It also identified two actionable integration issues: the floating assistant could cross footer links, and the direct React moment mount lacked the kit's mounted-status marker. Reserved footer link space and recorded the marker only after the actual module mount; added a browser assertion that the module mounted. About's phone hero now fills the available first screen. Matching About/footer links use the same secondary button treatment. No vendor script was changed.

Performance must be measured on the built preview. A first dev-server run counted Vite's source modules (4.5 MiB) and failed transfer/JS budgets; this is retained as a dev diagnostic, not a production score.


Production performance (/about, 1440 and 390, one cold measurement each): 0 FAIL, 4 WARN. LCP/FCP are sub-second on this host and CLS is 0.000; these are local measurements, not field metrics. Font families/files and bytes pass, with no broken requests or unmounted modules. JS is 470 KB before compression (146 KB gzip); the report retains its budget warnings.

Fixed a real checker observation as well: reserved space beside footer links for the floating assistant launcher. The skill statement module now records its successful mounted status, matching the kit's loader protocol. About's first mobile screen fills the viewport; no stock imagery or corporate statistics were invented for it.


## Final skill gate

GATE: OPEN 14 (rounds used up)

No waivers were added and no vendor checker files were changed. All open findings below are retained for review; this is not a PASS claim. The approved application exceptions cover text-led About when no client imagery exists, natural-height informational content/footer, React root wrappers, and the shared container class instead of the kit static-document recipe.

- FAIL nav              div.site-app > header.site-header > div.shell.header-row > a.brand "CGV Cinema booking"  [1440, 390] — nav link wraps to a second line
- FAIL no-visual        main#main-content > section.shell.about-hero "Phim, rạp và buổi xem của bạn"  [1440, 390] — no picture, effect or mock in this section; a feature section needs a visual
- FAIL no-visual        main#main-content > section.shell.page-section:nth-of-type(2) "Buổi xem phim của bạn"  [1440, 390] — no picture, effect or mock in this section; a feature section needs a visual
- FAIL copy-fact        main#main-content > section.shell.about-hero > div > h1 "Phim, rạp và buổi xem của bạn"  [1440] — the first screen holds no number, price, date, place, platform or genre
- FAIL section-height   div#root > div > div.site-app > footer.site-footer "CGVCinema bookingPhim bạn muốn xem.Buổ  [1440] — the section is 272px tall (0.3 screens), 628px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2)
- FAIL section-height   main#main-content > section.shell.page-section:nth-of-type(2) "Buổi xem phim của bạnTừ bộ   [1440] — the section is 489px tall (0.5 screens), 411px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2)
- FAIL one-section      footer.site-footer > div.shell > div.footer-top > a.brand "CGVCinema booking"  [1440] — the screen at scroll 1661px (the top of section 4) shows 272px of section 4 and the heading of section 4 whole and the content of 2 sections, over 24px each beside section 3: a screen shows one section (another may peek
- FAIL one-section      main#main-content > section.shell.page-section:nth-of-type(2) "Buổi xem phim của bạnTừ bộ   [1440] — the screen at scroll 89px (the top of section 1) shows 89px of section 2 and the content of 2 sections, over 24px each beside section 1: a screen shows one section (another may peek 8px, 24px WARN) (SR-4)
- FAIL container-edges  main#main-content > section.shell.about-hero "CGV Cinema BookingPhim, rạp và buổi xem "  [1440] — the content of section 1 runs 120px from the left and 420px from the right (read from its outermost blocks: no .wrap): the page's container starts at 96px; 120 and 420px are not one margin (one container, equal margins,
- FAIL container-edges  div#root > div > div.site-app > header.site-header "CGVCinema bookingPhimRạp chiếuVề CGVHỗ  [1440] — the nav's content runs 120px from the left and 120px from the right (read from its outermost blocks: no .wrap): the page's container starts at 96px (one container, equal margins, 2px either way) (SR-6)
- FAIL container-edges  main#main-content > section.shell.page-section:nth-of-type(2) "Buổi xem phim của bạnTừ bộ   [1440] — the content of section 2 runs 120px from the left and 120px from the right (read from its outermost blocks: no .wrap): the page's container starts at 96px (one container, equal margins, 2px either way) (SR-6)
- FAIL container-edges  div#root "Đến nội dung chínhCGVCinema bookingPhimR"  [1440] — a <div> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6)
- FAIL container-edges  div.site-app > footer.site-footer > div.shell > div.footer-bottom "© 2026 CGV Cinema Booki  [1440] — a box over half the container wide runs 120-1320px, not on the container's lines at 96-1344px (SR-6)
- FAIL container        page  [1440, 390] — no .wrap

Production perf WARN details: JS parsed 472.1 KiB, and host CPU load 33/68%, each reported at both widths. Total transfer 265–269 KiB; four local font files total 92.8 KiB. No additional performance FAILs.

Final handoff: changes remain uncommitted on codex/chat-booking-react. Existing unrelated work is preserved. Dev preview is available at http://127.0.0.1:5173 and production preview at http://127.0.0.1:4173; catalogue/booking pages require the project backend. /about and /contact can be viewed without it. No live payment, backend concurrency, separate annotation service, or real QR scanner was checked.


## Follow-up: account form motion and password parity

Registration now requires at least 8 Unicode characters, with a 72 UTF-8 byte maximum, matching identity-service's RegisterRequest/EmployeeCreate schema. Native minlength, instructions, and submit validation agree; login minimum length remains unchanged. Existing authentication endpoints, automatic login, and redirect behavior are preserved.

The account form enters with an 8px/240ms transition on mode changes; sidebar text and poster settle once on page load. Field focus and error entry provide local feedback without layout-height animation or repeating decoration. Mode changes preserve controlled input values and focus the new heading; reduced motion disables these animations.

Verification: new isolated npm run test:auth covers 7/8 character boundaries, Unicode and 72-byte limits, server failure/retry, auto-login, mode focus/data preservation, login rules and reduced motion. Desktop/mobile layout and snapshots cover 1440/1024/768/390/320. Lint/build and 13 unit tests passed. No real registration was sent. Gate returned GATE: OFF (no build active); no visual-gate pass is claimed for this follow-up.


## Follow-up: user motion and running local demo

Added a 240ms page entrance and 360ms heading entrance on customer navigation, 200ms dialog/menu motion and 180ms seat-selection feedback. Existing kit hover behavior remains. No scroll observers or recurring card animation were added; reduced motion disables these additions. Query filters and polling do not replay route motion. Existing UI regression: 105 layouts pass, plus auth regression, lint/build and 13 unit tests.

Started the existing final Compose runtime and retained all old DB volumes, data and offline archive containers. All nine APIs/owner DBs and gateway are healthy; runtime audit verifies nine independent domains and no foreign DB credentials. Web was built and started as its Nginx container at http://127.0.0.1:5173. The previous standalone Vite process on that port was stopped only after confirming its exact workspace command line. Production preview at 4173 was also rebuilt.

Created dedicated fe_admin (ADMIN, 11 permissions) and fe_user (USER) test accounts without altering existing accounts. Random test passwords are stored only in ignored .local/runtime/fe-demo-access.json and delivered to the requesting user, not committed here.

Provisioned catalog/cinema data through authenticated owner APIs: six explicitly labeled fictional DEMO films (four now showing, two upcoming), six local SVG demo poster assets, one demo theater/12-seat room, and 24 showtimes (current films today and next three days; upcoming films from release day). Existing menu contains seven food/combo entries. Rerunning demo extension preserved the same film/showtime IDs; no duplicate rows. No legacy film dates were rewritten and no paid orders, tickets or financial ledger rows were fabricated.

Live browser verification used actual FE/API/DB: both roles logged in via the form; nine admin pages including reports/reconciliation opened; customer navigated film → schedule → hold seat → food → release seat, and a USER was denied admin access. Desktop/mobile fit, no page errors. The held seat was released; no booking or payment was created. Local screenshots live under ignored .local/evidence/live-*.png. Fictional posters are demo assets, not promotional images of released films.

Restart existing runtime: docker compose --env-file .env.microservices -f compose.yml up -d. Do not use down -v or remove-orphans; old data/archive are intentionally preserved. The database split is internal to Compose; the unrelated host PostgreSQL on port 5432 was not changed.

Skill gate returned GATE: OFF (no active build); no gate PASS claim. Real VNPay payment/provider callbacks and model-dependent AI responses were not exercised in this handoff.
