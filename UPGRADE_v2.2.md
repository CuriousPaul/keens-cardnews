# keens-cardnews — v2.1 / v2.2 Upgrade (story + scenes + casting)

Consolidates the iteration learnings into the skill.

## v2.1 — Storytelling layer (in references/content_engine_prompts.md §6–7)
- **10-beat structure**: 도입(hook) → 궁금증(open loop) → 문제정의 → 관점전환① → 관점전환② → 핵심 → 적용 → 결정적 깨달음 → 실행 체크리스트 → 마무리 CTA.
- **Persona-driven story** (biggest story-score lever): use a real/synthetic target interview → name the exact pain scene + secret fear ("this is me"), then weave the USP tuned to *that persona's values*, and a CTA matching their psychology. (A generic-topic version scored ~4/10 on story; the persona version with USP woven scored higher.)
- **Truthfulness rule**: never fabricate numbers/studies/rankings; if no data, use principle/index, not fake stats.
- **Language lock**: one language per post; Korean labels for KR (도입/핵심/전환/실행/마무리), no English UI words.
- **Lead-magnet CTA**: value + comment keyword → DM (drives the funnel; verified high comment rate on references).
- **Theme selector**: `editorial-gold` (charcoal+gold, data/structure topics) vs `stage-photo` vs scene-composite.

## v2.2 — Scene backgrounds + audience casting
- **Scene per card** (not flat): `scripts/compose_scenes.py` processes generated scenes (EXIF + 4:5 crop + strong bottom scrim) and injects per-card `bg`; render with `build_cards.js`. Storyboard map in `references/scene_storyboard.md`.
- **Casting rule (required)**: scene people match the target market — **KR set → Korean people/contexts**, **US set → global**. Put casting in the generation prompt. (brand_and_voice.md v2.2)
- **Image models** (via Higgsfield or similar): `recraft-v4-1` for people scenes (4:5 native), `soul_location` for empty environments.
- **Readability**: bright scenes need a stronger scrim — `compose_scenes.py --scrim 0.92+`.

## Asset-fetch note (environment-specific)
This design loop runs in a sandbox that can't download URLs; generated scenes must arrive as local files (browser download → folder, or zip-in-one-click). In production (Mac mini / Paperclip) downloads are unrestricted → fully hands-off generate→download→composite→build.

## Files
- `scripts/compose_scenes.py` — scene → card bg compositor (NEW)
- `scripts/build_cards.js`, `prep_backgrounds.py`, `card_template_keens.html`
- `references/content_engine_prompts.md` (§6 v2.1, §7 v2.1), `brand_and_voice.md` (v2 themes + v2.2 casting), `scene_storyboard.md` (example), `nocode_publishing.md`
- `assets/brand.json`
