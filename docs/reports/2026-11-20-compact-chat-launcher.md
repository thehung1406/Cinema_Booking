GATE: OFF (no build active)

Cinema/place; small follow-up to the user-selected assistant. The user explicitly requested a compact launcher that expands on hover. The existing palette, icon, accessible name and chat behavior are reused. No new assets, copy, dependency or assumed fact.

The launcher rests at 72px wide and expands to 280px on fine-pointer hover or visible keyboard focus. It contracts when the pointer leaves. Touch opens the chat with one tap. Reduced motion switches dimensions immediately without transitions. The user's explicit expanding-control request takes precedence over the skill's generic prohibition on resizing hover controls.

Production build and lint passed. AI browser suite passed with width assertions for compact, hover and pointer-leave states, existing responsive/focus/reduced-motion/history/source checks, and no browser errors. Compact and expanded screenshots were visually inspected; the icon is fully contained. The local Docker web was rebuilt for port 5173.

The skill gate reports OFF because the preceding design build is closed; no fresh full-page checker pass is claimed. The preceding 25 open page findings and five waivers remain documented in 2026-11-20-cinema-assistant-refresh.md. No physical touch device or live payment tested. Changes are local and have not been pushed.
