GATE: OPEN 19 (rounds used up)

# Customer cinema theme — 2026-11-20

Implemented the approved dark cinema design for ordinary customers in the existing React/Vite application. The selected palette is charcoal `#101117`, surface `#1B1D27`, warm white `#FAF6EE`, CGV red `#D92D3A`, and amber `#F4B85A`. The primary red with white text has 4.79:1 contrast. Local Hanken Grotesk supplies Vietnamese text and headings.

## Pull request integration and real poster follow-up

The PR is based on `main` at `846f0ac`, after the earlier frontend refresh and chatbot fixes were merged. It carries only the customer-theme changes, their browser regression assertions, this report, and ten authentic film poster assets with source attribution in `apps/web/public/posters/sources.json`. The current chatbot showtime-selection logic and scrollable admin sidebar are retained from `main`. The implementation and original QA notes below describe the earlier local phase.

The user subsequently requested real films and posters for local testing. The local catalogue now references these poster paths and real film metadata. Fourteen local test screenings were created for 20–23 November 2026. These database changes, account credentials, import scripts, and private QA artifacts are not part of the PR. The PR does not seed or modify a database on checkout. Screening dates and prices are local test data, not a commercial cinema feed; the poster manifest records the artwork sources and rights holders.

Fresh verification on the PR branch: 13/13 unit tests, lint, production build, and all seven browser suites (UI smoke, authentication, food, payment, AI, chat booking, admin) passed against the production preview. UI smoke covered 105 layouts. Poster manifest/JPEG checks, staged credential checks, and `git diff --check` passed. Independent read-only review found no important regressions. Minor note retained: the recommendation percentage uses the muted card text colour rather than the success green; it remains readable. Existing npm dependencies were unchanged; `npm ci` reported 21 dependency advisories. Full backend CI and live payment checks were not rerun locally for this frontend-only PR.

## Implementation

- A route-level customer theme covers the shared shell, films, details/reviews/trailer, cinemas, schedule/seat/food/checkout/result, authentication, account/orders, information/support/404, and AI/chat booking. Router-native matching keeps admin and moderation light, including encoded, uppercase and repeated-slash URLs.
- A sharp poster leads the home hero, followed by the existing showing, positive-trending and upcoming film sections. Shared cards have dark surfaces, inset posters and aligned actions. No catalogue items, endpoints, routes, prices or testimonials were invented.
- The hero stages its copy and settles its poster once in approximately one second. Existing hover/press motion remains; the word-highlight moment uses amber. Transactional feedback remains immediate and reduced motion rests. No animation dependency, autoplay, canvas or WebGL was added.
- Dark forms include distinct disabled and focused states. Seat types, selected/held/booked states and errors have readable colours and existing labels/borders. Payment QR areas remain black on white. All booking, reservation, idempotency, authentication and payment logic is unchanged.
- Loading and error states reserve the first screen before films arrive, preventing the footer from jumping. Recommendation filters have visible labels. The assistant launcher follows the footer on phones/tablets so it cannot cover titles or actions; desktop retains the floating launcher. Tablet heroes stack the copy above the poster.
- Task input was archived locally before editing. Existing uncommitted changes were preserved; service/config/admin source files match that input. Work remains on the existing `codex/chat-booking-react` checkout without committing, merging, pushing or deploying.

## Verification

The new customer-theme assertion was observed failing against the old interface. Seven browser suites then passed: UI smoke, authentication, food, payment, AI, chat booking and admin. UI smoke covers 105 layouts across 320/375/390/768/820/1024/1440px, URL filters, retry/empty states, missing posters, long titles, keyboard/focus/Escape, reduced motion, booking holds and backend reconciliation, login return, and payment result states. Tests intercept backend/payment requests; no real purchase occurs.

An independent review identified three additional regressions. Each was reproduced with a failing browser assertion before fixing it: encoded/repeated-slash staff routes receiving the customer theme, disabled controls retaining enabled colours, and a hovered selected chat seat losing its selected fill. The final seven-suite run passed after those fixes, including admin and the added regression cases.

Final production build, lint and 13/13 unit tests passed. UI smoke again passed all 105 layouts after the loading-height, filter-label and launcher-placement assertions were observed failing and then fixed. AI and chat-booking suites also passed after the responsive launcher change. Production screenshots at 1440x900, 1024x768, 820x1180, 768x1024 and 390x844 are under `apps/web/.taste-skill/cinema-dark/`. Fixture screenshots include seats, authentication, orders, assistant and payment states.

## Design decisions and remaining limits

- Kind remains cinema/place. The user-selected dark palette and warm illumination override the skill's generic light-only place treatment. Real application forms, film lists and footer use natural content height; they are not stretched into marketing screens. The existing React shell and container system are retained.
- Voice: concise Vietnamese about films, screenings, seats and orders. Existing names, contact information and backend film text are preserved. No new brand name or marketing facts were assumed.
- All artwork comes from existing API image URLs. The live catalogue currently contains six labelled DEMO SVG posters; some older films already use Unsplash URLs. No new stand-in photographs or generated comparison-board artwork was added to the application. Actual poster/key art quality remains a data dependency; no separate landscape/backdrop field exists.
- Minor review note retained: the unmodified motion kit zooms an image to 1.03 while the existing card-body hover uses 1.025. Both are within the skill's 1.02–1.03 range.
- No live VNPay charge, concurrent multi-account reservation load, email delivery or physical QR scanner was tested. Canonical production domain and share image remain outside this change. No vendor kit or checker files were edited.

## Final measurements

- Production performance at 1440 and 390, three cold-load measurements each: **0 FAIL, 4 WARN**. CLS is **0.000** on both sizes, reduced from the initial desktop 0.312. No WebGL contexts, broken requests or unmounted modules; one font family, two local font files. The retained warnings concern roughly 473 KiB parsed JavaScript and the natural-size heuristic on the existing vector DEMO posters. These are local CPU measurements with the current data, not field metrics.
- Rendered-page copy lint: **0 FAIL, 0 WARN**. No new copy facts, brand names, prices, contacts or photographs were assumed.
- Full five-width consistency ran; after real label, loading and overlay fixes the gate's final quick checks retained the findings listed below. Most require static marketing structure: a full-screen footer, full-screen empty recommendation state, varied catalogue cards, fixed grid splits and a direct body/header/main hierarchy rather than React wrappers. Actual customer viewport tests pass. The gate is **OPEN**, not PASS.
- The separate layout checker raised `TypeError: r.sections is not iterable` after `Cannot read properties of undefined (reading 'map')`, reproducing the previously recorded React-page checker error. Its vendor code was not changed.
- Four narrow waivers cover the native CSS hero entrance, `.shell` container naming, the actual featured film title, and the honest empty recommendation list. Their exact reasons and every remaining gate finding follow below.

## Final gate output — all open findings and waivers

```text
gate: rounds used up; 19 FAIL open (page unchanged since the last run)
  FAIL row-gap          main#main-content > section.shell.page-section:nth-of-type(3) > div.movie-grid > article.m  [1440]
       fills 49% of its grid row and leaves 51% of it empty on the right
       fix: fill the row at this width: span the columns, or stack the split
  FAIL card-layout      main#main-content > section.shell.page-section:nth-of-type(2) > div.movie-grid "P DEMO - C  [1440, 390]
       4 of 4 cards drawn one way (one panel, ground, placement and fragment): copies of one card
       fix: a card layout at most twice on a page: build the other sections another way
  FAIL empty-area       main#main-content > div.community-band "Phim được đánh giá tích cực"  [1440]
       51% of the section is empty: 32px above its first content, 64px under its last (p.bg-gray-50.border), 29% beside content that covers under half the container, in its 418px of rows (WARN over 35%, FAIL over 50%)
       fix: fill the section: a picture or a second column beside the words, or more of its own content; the section stays one or two screens tall (T-height)
  FAIL section-height   div#root > div.customer-theme > div.site-app > footer.site-footer "CGVCinema bookingPhim b  [1440]
       the section is 281px tall (0.3 screens), 619px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2)
       fix: set the section to one screen or two (height: calc(var(--h,1) * 100vh), --h 1 or 2) and cut or split its content to fit
  FAIL section-height   main#main-content > div.community-band "Phim được đánh giá tích cựcPhản hồi cộng"  [1440]
       the section is 418px tall (0.5 screens), 482px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2)
       fix: set the section to one screen or two (height: calc(var(--h,1) * 100vh), --h 1 or 2) and cut or split its content to fit
  FAIL one-section      div.community-band > div.shell > section.positive-films.page-section > h2.mb-4 "Phim được   [1440]
       the screen at scroll 1800px (stride 2) shows 418px of section 3 and the heading of section 3 whole and the content of 2 sections, over 24px each beside section 4: a screen shows one section (another may peek 8px, 24px WA
       fix: make each section exactly one screen or two, so a screen shows one section and no neighbour peeks
  FAIL one-section      footer.site-footer > div.shell > div.footer-top > a.brand "CGVCinema booking"  [1440]
       the screen at scroll 3460px (the top of section 6) shows 281px of section 6 and the heading of section 6 whole and the content of 2 sections, over 24px each beside section 5: a screen shows one section (another may peek
       fix: make each section exactly one screen or two, so a screen shows one section and no neighbour peeks
  FAIL one-section      main#main-content > div.community-band "Phim được đánh giá tích cựcPhản hồi cộng"  [1440]
       a <div> sits directly in <main>: every part of <main> is a <section> (SR-4)
       fix: put every block of <main> in a <section>, and give a band its own section instead of a ground inside one
  FAIL one-section      div.community-band > div.shell > section.positive-films.page-section > p.bg-gray-50.border  [1440]
       a band: a box 83% of the section wide on a ground of its own that holds only text: the section's own ground is the band (SR-4)
       fix: put every block of <main> in a <section>, and give a band its own section instead of a ground inside one
  FAIL one-heading      section.shell.page-section:nth-of-type(3) > div.section-heading > div > h2 "Phim sắp chiếu  [1440]
       headings of two sections show whole on one screen at 11 of 70 scroll positions (15.7%; at scroll 1550, 1600, 1650, 1700px), here with "Phim được đánh giá tích cực": at most 3% on a desktop (SR-5)
       fix: make the sections one screen tall so their headings sit a screen apart and two never share one
  FAIL container-edges  div#root > div.customer-theme > div.site-app > header.site-header "CGVCinema bookingPhimRạ  [1440]
       the nav's content runs 120px from the left and 120px from the right (read from its outermost blocks: no .wrap): the page's container starts at 96px (one container, equal margins, 2px either way) (SR-6)
       fix: use one container on every section and the nav (.wrap): one margin left and right, 64-120px on a desktop, 16-24px on a phone
  FAIL container-edges  main#main-content > section.shell.page-section:nth-of-type(2) "Lịch phimPhim đang chiếuXem  [1440]
       the content of section 2 runs 120px from the left and 120px from the right (read from its outermost blocks: no .wrap): the page's container starts at 96px (one container, equal margins, 2px either way) (and 1 more like i
       fix: use one container on every section and the nav (.wrap): one margin left and right, 64-120px on a desktop, 16-24px on a phone
  FAIL container-edges  div#root "Đến nội dung chínhCGVCinema bookingPhimR"  [1440]
       a <div> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6)
       fix: build the page as header.nav, a main of sections (each one in-flow .wrap plus background layers) and footer.closing
  FAIL container-edges  main#main-content > section.hero.editorial-hero "Phim tại CGVDEMO - Chuyến đi vui vẻHoạt "  [1440]
       the section needs exactly one in-flow child .wrap (it has 1 in-flow child, 0 .wrap) (and 5 more like it: "Lịch phimPhim đang chiếu", "Phim được đánh giá tích ", "Sắp ra mắtPhim sắp chiếu") (SR-6)
       fix: build the page as header.nav, a main of sections (each one in-flow .wrap plus background layers) and footer.closing
  FAIL container-edges  div.community-band > div.shell > section.positive-films.page-section > p.bg-gray-50.border  [1440]
       1 text block starts on a left line at x 145, 49px from the container's left: text starts on the container's left, or on one split line (x 626, 732, 838) (SR-6)
       fix: start the text on the container's left, or on the one split line every split shares
  FAIL container-edges  section.hero.editorial-hero > div.shell.hero-content > div.hero-copy > p.eyebrow "Phim tại  [1440]
       10 text blocks start on a left line at x 120, 24px from the container's left: text starts on the container's left, or on one split line (x 626, 732, 838) (also "DEMO - Chuyến đi vui vẻ", "Hoạt hình · 90 phút", "Phim được
       fix: start the text on the container's left, or on the one split line every split shares
  FAIL container-edges  div.site-app > footer.site-footer > div.shell > div.footer-bottom "© 2026 CGV Cinema Booki  [1440]
       a box over half the container wide runs 120-1320px, not on the container's lines at 96-1344px (SR-6)
       fix: run the picture or box from the container's left line to its right line, or put it in a row or a split
  FAIL row-lines        main#main-content > section.shell.page-section:nth-of-type(3) > div.movie-grid "PDEMO - Ng  [1440]
       a row of 2 items: its last item ends at 708px, the container's right line at 1320px (2px either way) (SR-7)
       fix: start the row's first item on the container's left line and end its last on the right line, every item one height
  FAIL split-pair       main#main-content > section.hero.editorial-hero > div.shell.hero-content "Phim tại CGVDEMO  [1440]
       the split's columns are off the page's one pair of lines: its right column starts at x 900, on none of the split lines 732 (k=6) (SR-8)
       fix: start every split's right column on one shared line (wrap.left + k x (width + 24) / 12, k 5, 6 or 7; 6 on a place page) and end the left one 24px before it
  WAIVED no-visual main#main-content > div.community-band "Phim được đánh giá tích cực": This is a functional film recommendation list with real filters and an honest empty state when the backend has no qualifying reviews and screenings. The approved plan preserves API data and does not fabricate recommendation cards or decorative proof.
  WAIVED copy-headline section.hero.editorial-hero > div.shell.hero-content > div.hero-copy > h1 "DEMO : The approved cinema application hero names the featured film from the live catalogue, just as the selected palette preview does. Replacing the actual film title with a marketing category heading would change the approved content.
  WAIVED hero-enter main#main-content > section.hero.editorial-hero: The approved React implementation uses a data-enter hero with staged native CSS copy and poster animations, including reduced motion. The kit m-enter JavaScript text-masking hook is not mounted over React-owned text.
  WAIVED container page: The existing application uses one shared .shell container for the header, sections and footer, with equal edges verified in screenshots. The missing .wrap class name is not an additional container system.
  19 WARN (not blocking), first: scroll-reveal main#main-content > section.editorial-mo; no-visual main#main-content > section.shell.page-s; copy-headings div.movie-grid > article.movie-card.card; copy-buttons div.site-app > header.site-header > div.; copy-actions div.site-app > header.site-header > div.
Stop fixing: put these open FAILs and the waivers in your report, then finish.
GATE: OPEN 19 (rounds used up)
```
