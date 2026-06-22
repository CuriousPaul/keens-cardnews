# keens-cardnews — v2 Upgrade (reference absorption)

Patch absorbing patterns from the reference library (open-carrusel, @prompt_what).

## Changes
1. **Template (`scripts/card_template_keens.html`)**
   - `body_html` per-card field → free HTML cards wrapped by the shared template (open-carrusel `wrapSlideHtml` pattern). Wrapper still enforces 1080×1350 + fonts + brand.
   - `theme` support: `stage-photo` (default) and `editorial-gold` (charcoal+gold+cream).
   - `brand` injection: `accent`, `handle`, `brandName` overridable per batch (brand.json pattern).
2. **`assets/brand.json`** — externalized account + theme tokens (us / kr / editorial-gold).
3. **`references/content_engine_prompts.md` §6** — render 3-principles, new card types (`perspective_shift`, `checklist`), lead-magnet CTA standard, hook-formula library, theme selection.
4. **`references/brand_and_voice.md`** — v2 themes + graphic vocabulary, CTA lead-magnet standard, hook library, render principles.

## How to use the new bits (in a batch JSON)
```json
{ "post_id":"KR-07", "lang":"ko", "total":5, "theme":"editorial-gold",
  "brand": { "handle":"@KEENS_KR", "accent":"#C8A24B" },
  "cards": [
    {"kicker":"...", "headline":"...", "subhead":"..."},
    {"kicker":"공식", "body_html":"<div style='...'>수입 − 지출 = 저축</div>"},
    {"kicker":"당신의 차례", "headline":"...", "cta":"무료 레벨 테스트"}
  ] }
```
`build_cards.js` is unchanged — it passes the whole post to the template, which reads `theme`/`brand`/`body_html`.

## Verified
Rendered an editorial-gold test (charcoal+gold, body_html formula card, @KEENS_KR handle) — all correct.

## IP note
Themes/structure/principles are absorbed as *patterns*. All copy and visuals are regenerated as original Keens content; no source slides/photos/text are reproduced.
