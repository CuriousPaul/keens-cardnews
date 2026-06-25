---
name: keens-cardnews
description: >-
  Generate Keens Instagram card-news carousels end to end — synthetic-consumer research,
  copy, background prep, and rendered cards plus a ready-to-publish manifest. Use this
  whenever the Growth Manager (or marketing agent) needs to produce weekly Instagram
  content for the Keens accounts (@keensacademy US / Korean account), create a batch of
  carousel "card news" posts, write idol-audition/training copy in the Keens voice, render
  carousel images, or prepare a publishing schedule/manifest. Trigger on requests like
  "make next week's Keens carousels", "generate card news", "produce IG posts for Keens",
  even if they don't say the word "skill" or "card news" explicitly.
---

# Keens Card-News Pipeline

Produce Instagram **carousel "card news"** for Keens (엔터테인먼트/아이돌 트레이닝) — from idea to rendered cards plus a publishing manifest that an external no-code tool (Make/Buffer/Later + ManyChat) picks up. This skill owns the **"card factory + content engine."** It does **not** post to Instagram itself; publishing and comment→DM stay external.

## Heartbeat model

You run in short heartbeat windows. A full weekly batch may not finish in one window, so work **incrementally and idempotently**:
- Treat each Issue (e.g. "Generate next week's Keens card batch") as the unit of work.
- After each step, write intermediate files to the working folder and note progress on the Issue, so a later heartbeat can resume without redoing finished work.
- Only mark the Issue done once cards + `publish_manifest.json` exist and a human-review gate (below) is satisfied.

## The pipeline (4 steps)

```
1. Content engine (Claude)   → batch JSON (topics, copy, captions, dm_keyword; KO/EN)
2. Background prep (Python)   → 1080x1350 dark cinematic backgrounds from the photo pool
3. Card build (Node)          → carousel PNGs per post + publish_manifest.json + CSV
4. Hand off (external)        → Make/Buffer/Later publish; ManyChat runs comment→DM
```

### Step 1 — Content engine
Read `references/content_engine_prompts.md` and run the 3-stage chain (synthetic-consumer research → topic/angle → per-card copy) to produce a **batch JSON**. Follow the brand voice in `references/brand_and_voice.md` (honest, cold-expert feedback; data-backed; always resolves to a free Level Test CTA). Generate **KO and EN** as needed per target account.

Batch JSON shape (one object per post in `posts[]`):
```json
{
  "voice": "...", "dm_keyword": "LEVELCHECK",
  "posts": [{
    "post_id": "US-01-reddit", "lang": "en", "total": 5,
    "cards": [
      {"kicker":"KPOP AUDITION","headline":"Reddit got\nKPOP auditions <span class='hl'>wrong.</span>","subhead":"Age, skill, visuals — <strong>what agencies actually read.</strong>"},
      {"kicker":"YOUR MOVE","headline":"Get your <span class='hl'>Level Check.</span>","subhead":"...","cta":"Free Level Check"}
    ],
    "caption": "full caption + hashtags",
    "dm_keyword": "LEVELCHECK"
  }]
}
```
Card fields: `kicker` (top label), `headline` (bold; wrap key words in `<span class='hl'>` for the red accent — keep highlighted phrases short or they break across lines), `subhead` (use `<strong>` for emphasis), optional `stat` (big number) and `cta` (button on the final card). **Always include captions + a `dm_keyword`** — the no-code publisher and ManyChat depend on them.

**Batch container & card-schema aliases (important):** the batch may be either `{ "posts": [...] }` **or a bare top-level array** `[ {post}, ... ]` — `build_cards.js` accepts both. Cards may use the visual fields above **or** the semantic schema `{ "type", "title", "body", "badge", "button", "footnote" }`; the template aliases them (`badge→kicker`, `title→headline`, `body→subhead`, `button→cta`, plus `footnote`). Mixing is fine, but **never assume the semantic fields render on their own** — they only work because `card_template_keens.html` maps them. If you fork the template, keep that mapping.

**Length guard (auto-checked, enforce in copy):** headline line ≤16 chars, body/subhead ≤120 chars.

**Glyph guard:** the CTA arrow uses `→` (U+2192). Do **not** use `➜` (U+279C) / `➔` (U+2794) / `➤` (U+27A4) — those are **absent from Noto Sans CJK** and render as tofu (□) under headless Chromium / Pillow. Stick to `→ › » ▶ ✓` if you need a glyph.

### Step 2 — Background prep
The card look = white text over a **dark cinematic stage photo**. Process the Keens photo pool into card-ready backgrounds:
```bash
python3 scripts/prep_backgrounds.py <PHOTO_POOL_DIR> <OUT_BG_DIR> --keep 24
```
This applies **EXIF rotation** (critical — without it portrait shots render lying sideways), center-crops to 4:5, tones toward navy, and auto-selects photos whose lower-left text zone is dark enough for legibility. Re-run whenever new photos are added.

### Step 3 — Card build
```bash
npm i puppeteer        # first run only; Mac mini (Apple Silicon) runs bundled Chromium fine
node scripts/build_cards.js <BATCH_JSON> <OUT_DIR> <BG_DIR> \
  --template scripts/card_template_keens.html \
  --base-url <PUBLIC_HOST_URL> --handle <@account> --start <YYYY-MM-DD> --skip-weekends
```
Outputs per post: `OUT_DIR/<post_id>/01.png…0N.png`, plus `publish_manifest.json` and `publish_schedule.csv`. The CSV/manifest is the **hand-off contract** (post_id, status, scheduled_date, dm_keyword, caption, image_urls). Set `--handle` per account (US `@keensacademy`; Korean account once its handle is set).

### Step 3b — Scene backgrounds (v2.2, high-impact for persona/emotional sets)
Instead of flat/abstract backgrounds, put a real scene behind each card. Map cards to scenes per `references/scene_storyboard.md`, generate them with an image model (e.g. Higgsfield, model `recraft-v4-1` for people scenes / `soul_location` for empty stages), then composite:
```bash
python3 scripts/compose_scenes.py <BATCH_JSON> <SCENES_DIR> <OUT_BG_DIR> <COMPOSED_JSON> --skip 9
node scripts/build_cards.js <COMPOSED_JSON> out/<acct> <OUT_BG_DIR> --template scripts/card_template_keens.html ...
```
`compose_scenes.py` does EXIF-fix + 4:5 crop + strong bottom scrim (text legibility) and injects per-card `bg`.
**Casting rule (required):** scene people must match the target market — KR set → Korean people & contexts; US set → global casting (see `references/brand_and_voice.md` v2.2). Write generation prompts accordingly (e.g. "a worried Korean mother…", "Korean teenage students…").

### Step 3c — Real-photo backgrounds via asset index (recommended for KR — no "AI look")
Practitioner feedback: parents react negatively to an obvious "AI" feel, so for KR sets **prefer real photos from the Keens library** over AI-generated scenes (see `references/ASSET_INDEX_README.md`). Scanning hundreds of photos every run is token-expensive, so the library is **indexed once** (vision-caption -> text) and then queried as text.

1. Index the library (one-time + incremental — only new files are vision-tagged):
   ```bash
   python3 scripts/index_assets.py "<ASSET_DIR>" --out assets_index.json [--video-keyframe]
   ```
2. Pick one photo per card beat (text-only, ~0 vision tokens) and emit a compose map:
   ```bash
   MAP=$(python3 scripts/select_assets.py assets_index.json \
     --sequence hook_intro,doubt,turn_diagnosis,method_lesson,joy_basics,checklist_text,cta \
     --root "<ASSET_DIR>" --emit-map)
   python3 scripts/compose_scenes.py <BATCH_JSON> /tmp/none <OUT_BG_DIR> <COMPOSED_JSON> --map "$MAP"
   node scripts/build_cards.js <COMPOSED_JSON> out/<acct> <OUT_BG_DIR> --template scripts/card_template_keens.html ...
   ```
Beat vocab: hook_intro, doubt, turn_diagnosis, method_lesson, joy_basics, checklist_text, cta, finale. Filters: `--kids --brand --prefer-dark`. Use AI scene generation (3b) **only to fill beats the library lacks**. For an A/B test (AI vs real), keep copy/layout/theme identical and swap only `bg`.

### Step 3e — Dropbox asset library (team library via MCP)
When the local pool is thin, pull from the **Dropbox** library (team: Counter Culture). Full runbook in `references/dropbox_assets.md`; folder map in `references/dropbox_catalog.json`. Same index schema as 3c, so `select_assets.py` works across local + Dropbox indexes.
```bash
SEQ="hook_intro,doubt,turn_diagnosis,method_lesson,joy_basics,checklist_text,cta"
# (1) get chosen [file,file_id,ns_path] (unfilled beats warn to stderr)
DL=$(python3 scripts/select_assets.py references/dropbox_assets_index.json --sequence "$SEQ" --emit-download-list)
# (2) agent: download_link(file_ids ≤25, single-use) → curl -L -o cache/<file>
# (3) same sequence → emit-map (root=cache) → compose → render
MAP=$(python3 scripts/select_assets.py references/dropbox_assets_index.json --sequence "$SEQ" --emit-map --root cache)
python3 scripts/compose_scenes.py <BATCH_JSON> /tmp/none <OUT_BG_DIR> <COMPOSED_JSON> --map "$MAP"
```
⚠️ select가 못 채운 비트(현 인덱스 cta/finale)는 emit-map에서 빠져 **배경 없는 카드**가 됨 → 99.킨즈퍼포먼스 키프레임/AI장면(3b)으로 보강. `--no-kids`(미성년 제외)/`--brand`(KEENS 백드롭) 필터 지원.
Indexing new files: `download_link`(≤25 single-use) → `curl` → `scripts/index_dropbox_assets.py manifest.json` → contact sheet로 태깅 → `--apply-tags`(people+mood 둘 다 있어야 vision 승급, kids는 사람 확인 플래그). 사진 풀 1순위=`출시영상/02. 활용 가능 이미지`(712장). ⚠️`스텝픽`(아이돌 안무 모니터링·외부사용불가)은 소재 금지.

### Step 4 — Hand off (external, do not post from here)
Read `references/nocode_publishing.md`. Sync `OUT_DIR/` to the public host so `image_urls` resolve, then let **Buffer/Later/Make** read the CSV and publish on `scheduled_date`. **ManyChat** keyword = each post's `dm_keyword` drives the comment→DM funnel to the Level Test landing.

### Step 3d — QC before marking done (do this every batch)
A clean-looking preview is **not** proof of a publishable render. Before declaring done:
1. **Render through the real path.** Build at least the first post with `build_cards.js` (Step 3) and open a PNG — a quick Pillow/HTML preview can mask field-mapping or font gaps that only surface in the official renderer.
2. **Length guard** — confirm headline lines ≤16 / body ≤120 (see Step 1).
3. **Glyph check** — no tofu (□); CTA arrow is `→`, not `➜` (see Step 1).
4. **Brand/guardrails** — no guarantee language ("무조건/합격/데뷔"), no minor-sensitive pressure (looks/weight), unverified USP claims (대표원장/SM 등) confirmed or omitted, synthetic stats stated as rank/sign only.
5. **Casting match** — scene/photo people match the segment (e.g. boys set → boy footage, not female/ensemble stock).

**Quick visual preview (no Chromium):** `python3 scripts/render_contact_sheet.py <BATCH_JSON> <BG_DIR> <OUT.jpg>` tiles all cards into one contact-sheet JPG over the chosen backgrounds — handy for copy/layout review and for extracting frames from video backgrounds. It shims the semantic→visual aliases, so **treat it as preview only**; the publish artifact still comes from `build_cards.js`.

## Human-review gate (early phase)
Don't auto-publish at first. Leave manifest `status: ready`, post a preview/summary on the Issue, and let a human flip approved posts before the external tool publishes. As reject rate stabilizes, allow auto-flow per post type (avoid flipping everything at once).

## Configuration (set once, store in Paperclip secrets/config)
- `ANTHROPIC_API_KEY` — content engine.
- `PHOTO_POOL_DIR` — source stage photos. `BG_DIR` — processed backgrounds.
- `ASSET_DIR` — real photo/video library (e.g. Keens 셀렉 사진). `ASSETS_INDEX` — `assets_index.json` (text, version-controlled with the skill).
- `PUBLIC_HOST_URL` — where cards are hosted (Drive public / Cloudinary / S3) → `--base-url`.
- Per-account `--handle`. Publishing/ManyChat tokens live in the external tools, not here.

## Report back on the Issue
When a batch is built, summarize: # posts, languages, scheduled dates, output folder, manifest path, and anything needing human decision (e.g. captions to confirm, low-contrast cards). Keep it short and actionable.

## Bundled resources
- `scripts/build_cards.js` — render engine (batch JSON + bg → cards + manifest/CSV).
- `scripts/prep_backgrounds.py` — photo → card-ready backgrounds (EXIF-safe).
- `scripts/index_assets.py` — one-time/incremental asset indexer (vision-caption → `assets_index.json`).
- `scripts/select_assets.py` — beat→photo selector (text-only) → compose `--map`. Works on local **and** Dropbox indexes.
- `scripts/index_dropbox_assets.py` — Dropbox-download → PIL features → index (`--apply-tags` for vision승급).
- `references/ASSET_INDEX_README.md` — asset-index architecture, schema & usage.
- `references/dropbox_assets.md` — Dropbox MCP 연동 런북(검색→다운로드→인덱싱→선택→가져오기).
- `references/dropbox_catalog.json` — Dropbox 자산 폴더 지도(ns_path·개수·역할).
- `references/dropbox_assets_index.json` — Dropbox 소스 인덱스(POC 20장, 02/사진).
- `scripts/card_template_keens.html` — card design (brand tokens, KO/EN, `bg` slot, scrim, semantic-field aliases).
- `scripts/render_contact_sheet.py` — Pillow contact-sheet preview (all cards → one JPG; preview only, not publish).
- `references/content_engine_prompts.md` — the 3-stage copy engine.
- `references/brand_and_voice.md` — voice, do/don'ts, visual rules, account differences.
- `references/nocode_publishing.md` — Make/Buffer/Later + ManyChat hand-off.
- `examples/` — a sample batch JSON and rendered card for reference.
