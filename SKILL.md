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

### Step 4 — Hand off (external, do not post from here)
Read `references/nocode_publishing.md`. Sync `OUT_DIR/` to the public host so `image_urls` resolve, then let **Buffer/Later/Make** read the CSV and publish on `scheduled_date`. **ManyChat** keyword = each post's `dm_keyword` drives the comment→DM funnel to the Level Test landing.

## Human-review gate (early phase)
Don't auto-publish at first. Leave manifest `status: ready`, post a preview/summary on the Issue, and let a human flip approved posts before the external tool publishes. As reject rate stabilizes, allow auto-flow per post type (avoid flipping everything at once).

## Configuration (set once, store in Paperclip secrets/config)
- `ANTHROPIC_API_KEY` — content engine.
- `PHOTO_POOL_DIR` — source stage photos. `BG_DIR` — processed backgrounds.
- `PUBLIC_HOST_URL` — where cards are hosted (Drive public / Cloudinary / S3) → `--base-url`.
- Per-account `--handle`. Publishing/ManyChat tokens live in the external tools, not here.

## Report back on the Issue
When a batch is built, summarize: # posts, languages, scheduled dates, output folder, manifest path, and anything needing human decision (e.g. captions to confirm, low-contrast cards). Keep it short and actionable.

## Bundled resources
- `scripts/build_cards.js` — render engine (batch JSON + bg → cards + manifest/CSV).
- `scripts/prep_backgrounds.py` — photo → card-ready backgrounds (EXIF-safe).
- `scripts/card_template_keens.html` — card design (brand tokens, KO/EN, `bg` slot, scrim).
- `references/content_engine_prompts.md` — the 3-stage copy engine.
- `references/brand_and_voice.md` — voice, do/don'ts, visual rules, account differences.
- `references/nocode_publishing.md` — Make/Buffer/Later + ManyChat hand-off.
- `examples/` — a sample batch JSON and rendered card for reference.
