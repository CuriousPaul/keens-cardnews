# Keens — Brand Voice & Visual Rules

## Voice
- **Honest, cold expert feedback.** Speak as a working trainer / casting insider who tells the uncomfortable truth. Contrarian, myth-busting hooks; data/experience as backup.
- Every post resolves to **one CTA: a free Level Test / Level Check.**
- **Don't:** guarantee outcomes ("무조건 합격" / "guaranteed debut"), shame appearance/weight, pressure on mental-health-sensitive topics. No hype, no emoji spam.
- **Do:** name a real fear or misconception, reframe with a sharp insight, give the next concrete step.

### Reference hooks (the proven register — @keensacademy)
- "Reddit got KPOP auditions wrong."
- "KPOP evaluators don't read your face first. They read your finish."
- "The fastest trainees share one habit." / "Your voice isn't the problem. Your breathing is."
- KO: "심사위원은 얼굴부터 안 봅니다." / "연습량이 문제가 아닙니다." / "너무 늦은 거 아닐까 — 그 생각이 진짜 문제입니다."

## Card structure (carousel, 5–7 cards)
cover (hook) → problem/insight ×3–5 → cta (Level Test). Last card always has the CTA + a line telling people to comment/DM the `dm_keyword`.

## Visual rules
- Dark cinematic **stage photo** background + bottom-left scrim for legibility.
- **White headline**, bold; wrap key words in `<span class='hl'>` for the **red accent (#E8472B)**. Keep highlighted phrases short (they wrap/break if long).
- Small-caps **kicker** label top-left; **subhead** with em-dash; footer `Keens | @handle  ···  01/0N`.
- Palette: navy/black + white text. NOT the dreamy pastel "Wonderland" look — that's the legacy @keens_seoul campaign style, which this card-news format intentionally differs from.

## Account differences
- **@keensacademy (US, English):** this card-news format is the native style. Handle `@keensacademy`.
- **Korean new account:** same US-style card-news format, Korean copy. Take only look-and-feel cues from @keens_seoul; do NOT copy its Wonderland tone. Set `--handle` to the new account once decided (currently defaults to @KEENSACADEMY — must be changed for KR).

## Product context (for CTAs/landing)
Free Level Test (entry) → paid program (e.g., 6-month package). Trainers positioned as behind today's debuted groups. Target personas: aspiring trainees (teens–20s), their parents, and K-pop audition/study-abroad seekers (KR + US).

---

## v2 — Visual themes & graphic vocabulary (absorbed from references)

Two selectable themes (set via `assets/brand.json` → `theme`):

**`stage-photo` (default)** — dark cinematic stage photo + white headline + red accent `#E8472B`. Footer `Keens | @handle ··· 0N/0N`. (Our proven @keensacademy look.)

**`editorial-gold` (premium)** — absorbed from @prompt_what's "premium editorial report" style:
- Colors: charcoal `#0E1116` · gold `#C8A24B` · cream `#F3EFE6` · off-white. Restrained — one gold accent.
- Type: Noto Sans KR (Black/Bold/Medium/Regular), big headline → clear hierarchy.
- Graphic vocabulary: **large index numbers (04/10)**, formula/structure cards, gold tick lines, ratio bars, checkboxes; invert tone on the key slide.
- No photo needed — works as a flat premium look. Use for "framework / structure / data" topics.

For expressive special cards (formula cards, bars, checkboxes), pass raw `body_html` per card (open-carrusel `wrapSlideHtml` pattern) — the wrapper still enforces 1080×1350, fonts, and brand.

## v2 — CTA standard (lead magnet)
Every final card + caption uses the **value + comment-keyword** formula:
> "[free resource/diagnosis]을 받으려면 댓글에 '[dm_keyword]'." / "Comment '[KEYWORD]' and we'll DM you the [resource]."
Evidence: a comparable post drew more comments than likes via this exact mechanic.

## v2 — Hook formula library (cover)
- Cold-truth: "심사위원은 [통념]부터 안 봅니다." / "Evaluators don't read your [X] first."
- No-X badge: "[코딩 X / 재능 X] · [outcome] [low effort/time]" — within guardrails (no guarantees).
- Name-the-fear: "'[common anxiety]' — 그 생각이 진짜 문제입니다."

## Render principles (3) — from @prompt_what's exposed project instructions
1. Compose precise layout internally; output the 1080×1350 result only (don't expose code/process).
2. One language per post (KO post = Korean only; EN post = English only) — no mixing.
3. Font safety: Hangul via Noto Sans KR / Pretendard so it never breaks (template guarantees).

## v2.2 — Scene casting rule (audience match, 필수)
배경/장면 이미지의 인물 캐스팅은 **콘텐츠의 타깃 시장에 맞춘다** (현지화이지 편향이 아님):
- **KR 세트(한국 타깃)** → 인물은 **한국인**. 공간도 한국 맥락(한국 아파트/연습실 등).
- **US/EN 세트(@keensacademy)** → 글로벌/다양한 캐스팅 허용.
- 생성 프롬프트에 타깃에 맞는 캐스팅을 명시(예: "a worried Korean mother…", "Korean teenage students…").
- 아동 이미지는 일상·교육 맥락으로 정숙하게, 얼굴 강조 최소화. 실인물·실브랜드·로고 복제 금지.
- 장면은 카드 메시지와 1:1로 맞춘다(스토리보드 참조). 텍스트 영역은 강한 하단 스크림으로 가독성 확보.
