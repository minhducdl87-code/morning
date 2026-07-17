# Design Guidelines

## Product posture

The web experience is **Morning Glance Dashboard**: a light editorial utility for busy Vietnamese readers who want to scan the daily briefing in 5–10 minutes. It should feel like a calm Windows 11 morning-news board, not an admin dashboard or a long report.

- Use a neutral light canvas, white story surfaces, dark ink, and one teal action color.
- Use `Newsreader` for headlines and `DM Sans` for controls and body copy.
- Warm color is reserved for hot or trending signals.
- Prefer clear editorial hierarchy over equal card grids.
- Avoid emoji icons, neon effects, decorative gradients, invented metrics, and exposed design/debug controls.

## Information architecture

The default surface has two regions:

1. **Archive rail** — recent days, topic shortcuts, weekly archive, and monthly archive.
2. **News dashboard** — ranked stories arranged as hero, primary, secondary, headline, and compact cards.

The dashboard is the product home at every width. Opening a story must not replace or reorder the board: it opens a **closed-by-default right-side reader sheet** above the dashboard. Closing the sheet restores focus to the originating story card.

## Editorial ranking and card hierarchy

Story order comes from the editorial data order and remains stable after read-state changes.

The six above-the-fold slots are presentation-diversified after ranking: when at least three topics provide enough stories, no topic occupies more than two of those slots. With fewer topics, the remaining slots are filled in ranked order. This keeps the briefing visually and editorially broad without changing the underlying data or the lead-story priority.

- **Hero**: the first and most important story; one dominant visual, large headline, and short summary.
- **Primary**: the next two stories; strong image or topic visual, headline, and brief summary.
- **Secondary**: supporting stories with image/topic visual and headline.
- **Headline**: dense scan rows for additional priority stories.
- **Compact**: remaining stories in a responsive card grid.
- Search results use compact cards and preserve the same source, topic, and read-state semantics.

On desktop, the lead row uses an approximately `60 / 40` split between the hero and the two-story primary stack. Supporting sections must fill their available width: three ranked secondary cards stay in a three-column grid, while compact/search grids may expand to four columns on wide monitors. Never leave a synthetic fourth slot beside three secondary stories.

Image-less primary cards use a narrow topic-color marker rather than reserving thumbnail space. Primary cards with verified images keep the more visual `39 / 61` split at every desktop tier.

Do not promote stories based on whether they are read. A click marks only that story as read and opens its reader sheet.

## Story visuals

Use the supplied story image when one exists. When it does not, render a compact topic fallback rather than a broken image, invented thumbnail, or oversized fake artwork:

- topic-specific background color;
- uppercase topic label;
- a narrow topic marker on primary cards and a short labelled band on secondary cards;
- a restrained monogram only on the hero, where typography is the intended visual;
- sufficient text contrast at every card size.

Hero overlay text uses explicit light colors and must remain unchanged after a story is marked read. Light-mode secondary text must meet WCAG AA against its surface; do not lower the contrast of an entire card to communicate read state. Read cards use a softer surface, no elevation, and a demoted action color while preserving readable metadata and headlines.

The fallback is functional identity, not decorative artwork. Keep it consistent across hero, primary, and secondary cards.

## Reader contract

The reader is always a right-side sheet, including mobile. It starts closed, overlays the dashboard, and contains one selected story.

- Historical cards without `detail` show `desc` as **“Tóm tắt nhanh”**, disclose that only a summary is stored, and link to the original source.
- Generated cards with `detail` show it as **“Tóm lược mở rộng”**. It adds context or impact but is not the source article.
- Never present `desc` or `detail` as full original content.
- Previous/next controls stay in a persistent footer outside the scrollable article body.
- Changing stories resets article scroll and preserves keyboard focus on the navigation control used.

## Responsive contract

Layout follows the browser's **CSS viewport width** (`window.innerWidth`), not device detection or monitor inches.

| CSS viewport | Dashboard contract | Archive | Reader |
|---|---|---|---|
| `<=600px` | One-column hero, primary, secondary, and compact cards | Drawer | Full-width right-side sheet |
| `601–900px` | Hero above a two-column primary/secondary/compact grid | Drawer | Full-width right-side sheet |
| `901–1180px` | Hero + primary stack; two-column supporting grids | Drawer | Right-side sheet |
| `1181–1799px` | Persistent rail; hero + primary stack; three-column supporting grids | Rail | Right-side sheet |
| `1800–2047px` | Wider hero; four-column supporting grids | Rail | Right-side sheet |
| `>=2048px` | Expanded dashboard capped at `2160px` | Wider rail | Right-side sheet |

Desktop remains the default whenever the CSS viewport is wider than `1180px`. The dashboard must not collapse into a mobile-width canvas on a desktop viewport, and no breakpoint may introduce horizontal overflow.

## Interaction and accessibility

- At `<=1180px`, navigation, topic, filter, reader, and toolbar controls expose at least a `44px` touch target.
- Archive drawer and reader sheet use `inert` plus `aria-hidden` on background regions while open.
- `Tab` remains inside the active overlay; `Escape` closes it; focus returns to the opener.
- Every story card has an accessible name, visible keyboard focus, selected state, and read-state that does not rely on color alone.
- Search filters the current dashboard as the user types; `/` focuses search when the user is not editing text.
- Respect `prefers-reduced-motion` and keep transitions brief and contextual.

## State coverage

- Initial loading uses a dashboard-shaped skeleton and sets `aria-busy` on the archive and feed regions.
- A failed `cards.json` request is a blocking error with a visible retry action; never silently promote archive data as today's briefing.
- Empty search/filter results offer a one-click reset to the full briefing and restore focus to search.
- “Mark all read” reports the remaining count, then disables itself with the label “Đã đọc tất cả”.
- Copy-link feedback is visible and announced without replacing the focused button.
- Active archive links use `aria-current="page"`; topic controls use `aria-pressed` in addition to their visual treatment.

## Theme ownership

The app owns its tokens and theme behavior locally. Do not load the shared report theme into this product surface. The default is light; the optional dark theme must preserve the same editorial ranking and contrast hierarchy and is stored under `morning-desk:theme`.

## Verification

Verify at `390`, `600`, `601`, `900`, `901`, `1180`, `1181`, `1366`, `1800`, `1920`, `2048`, and `2560px` with browser zoom at `100%` and device emulation disabled.

Confirm:

- expected hero/primary/supporting grid hierarchy;
- no horizontal overflow;
- stable editorial ranking after marking a story read;
- topic visual fallback when an image is absent;
- archive drawer accessibility below `1181px`;
- reader closed on load and opened only as a right-side sheet;
- reader focus containment, focus restoration, and stable previous/next footer.

Use `npm run test:ui` for responsive regression checks. Before handoff or deployment, run `npm run test:dist`; production build and smoke tests must pass.
