# Cinema assistant refresh

Kind: cinema/place; existing customer application, scoped assistant interface.

The user chose the wide cinema-assistant direction: a ticket icon and two-line launcher, a spacious conversation panel, prominent welcome and suggestions, a persistent composer, and full-screen mobile chat. Reuse the approved charcoal/red/amber palette and local Hanken Grotesk. No additional dependency or image is needed.

Approaches: retain the existing wide dialog and refine its hierarchy (selected); a compact corner chat saves space but constrains sources and in-chat booking. A separate chat page would add navigation without serving this request.

The launcher reads “Hỏi trợ lý” with a quieter film/screening/ticket description. The header retains “Trợ lý Cinema”, with a ticket mark and a short capability line. Welcome suggestions gain a short explanation. Messages have clearer sender and content spacing. Sources, real showtimes and booking remain available. The composer has a visible label and keyboard hint. No invented online status or response-time claim.

Desktop dialog: up to 840px wide, bounded by the viewport; mobile through 640px: full screen with safe-area padding. History and filters remain explicit tools; their contents scroll without hiding the composer. Existing flow-safe launcher placement remains. Opening uses a short entrance; hover/press are subtle; reduced motion disables animation.

Keep all API calls, authentication, context, history, sources, reservation, checkout, idempotency and payment behavior unchanged. Staff routes retain the light palette. Existing home hero/moment already satisfy the site's established motion direction; this task does not rebuild those sections or introduce marketing screen heights inside chat.

Acceptance: usable at 320px, short mobile screens, tablet and desktop; 44px controls, visible keyboard focus and named controls; Escape restores launcher focus; sources and booking still work; browser checks, lint, unit tests, build and visual inspection on production output.
