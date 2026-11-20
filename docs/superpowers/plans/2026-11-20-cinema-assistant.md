# Cinema Assistant Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refine the existing assistant and launcher in the approved wide cinema direction.

**Architecture:** Keep AIAssistant's state and event handlers. Update presentation markup and component styles; customer colours remain scoped in customer-theme.css.

**Tech Stack:** React, existing Lucide icons, CSS, Playwright browser suites.

**Spec:** docs/superpowers/specs/2026-11-20-cinema-assistant-design.md

## Constraints and review focus

- No dependencies, backend changes, invented status or booking/payment changes.
- Preserve light staff routes, accessible names, Escape/focus behavior and reduced motion.
- Check long conversation text, full history/filter sidebar, mobile safe areas, short screen composer access and in-chat booking seats.

## Task 1: Assistant presentation

- [x] Extend the existing AI suite with viewport/composer checks and optional welcome screenshots; observe the wide-dialog assertion fail.
- [x] Update AIAssistant.jsx presentation: ticket mark, launcher copy, header/welcome hierarchy, explanatory suggestion text and labelled composer.
- [x] Update AIAssistant.css and customer-theme.css for spacing, launcher, conversation styles, viewport boundaries and motion.
- [x] Run AI/chat-booking/UI suites, unit tests, lint and build; inspect screenshots and run skill checks on the build.
- [x] Request read-only review, resolve material issues and report remaining limits. Keep changes reviewable in this worktree.

Review fixes: the empty conversation opened 236px down at 320x568; the transcript effect now distinguishes welcome from actual conversations and preserves history restoration. The visible composer label now matches its accessible name. Both fresh-opening and label assertions pass. The reduced-motion hover regression was observed as a -1px transform, then fixed by limiting hover movement to no-preference. Native dialog entrance is awaited in layout tests instead of taking measurements mid-animation.
