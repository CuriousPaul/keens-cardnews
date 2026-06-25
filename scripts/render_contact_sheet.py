#!/usr/bin/env python3
"""
render_contact_sheet.py — 배치 카드 카피를 로컬 배경 사진 위에 합성해 컨택트시트 1장(JPG) 생성.
puppeteer 없이 Pillow만 사용(검수용 프리뷰). 정밀 렌더는 build_cards.js.
사용: python3 engine/render_contact_sheet.py content/boys_batch_kr.json assets/bg <out.jpg>
"""
import sys, re, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageStat

BATCH, BGDIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CW, CH = 1080, 1350
PAD = 84
ACCENT = (232, 71, 43)      # Keens red
INK = (255, 255, 255)
INK_SOFT = (201, 210, 226)
KICKER = (143, 166, 207)
FOOTER = (140, 151, 170)
KR_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
KR_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

def F(path, size): return ImageFont.truetype(path, size)

def runs(text):
    """<span class='hl'>..</span> / <strong>..</strong> / \\n 을 (텍스트, hl?, strong?) 런으로."""
    out = []
    for line in text.split("\n"):
        segs, i = [], 0
        for m in re.finditer(r"<span class='hl'>(.*?)</span>|<strong>(.*?)</strong>", line):
            if m.start() > i: segs.append((line[i:m.start()], False, False))
            if m.group(1) is not None: segs.append((m.group(1), True, False))
            else: segs.append((m.group(2), False, True))
            i = m.end()
        if i < len(line): segs.append((line[i:], False, False))
        out.append(segs or [("", False, False)])
    return out

def wrap_runs(lines, font, maxw, draw):
    """런 라인들을 maxw 내로 단어 단위 줄바꿈(한글은 글자 단위 보조)."""
    wrapped = []
    for segs in lines:
        cur, curw = [], 0
        def width(s): return draw.textlength(s, font=font)
        for txt, hl, strong in segs:
            token, buf = "", ""
            for ch in txt:
                if width(buf + ch) > maxw and buf:
                    if curw + width(buf) > maxw and cur:
                        wrapped.append(cur); cur, curw = [], 0
                    cur.append((buf, hl, strong)); curw += width(buf); buf = ch
                else:
                    buf += ch
            if buf:
                if curw + width(buf) > maxw and cur:
                    wrapped.append(cur); cur, curw = [], 0
                cur.append((buf, hl, strong)); curw += width(buf)
        wrapped.append(cur)
    return wrapped

def draw_runs(draw, x, y, wrapped, fr, fb, base, lh):
    for line in wrapped:
        cx = x
        for txt, hl, strong in line:
            f = fb if (hl or strong) else fr
            col = ACCENT if hl else (INK if strong else base)
            draw.text((cx, y), txt, font=f, fill=col)
            cx += draw.textlength(txt, font=f)
        y += lh
    return y

def scrim(img):
    """좌측+하단 가독성 셰이딩(템플릿 ::after 근사)."""
    ov = Image.new("L", (CW, CH), 0)
    d = ImageDraw.Draw(ov)
    for yy in range(CH):  # 하단 darken
        t = yy / CH
        a = int(255 * max(0, (t - 0.40) / 0.60) ** 1.3 * 0.97)
        d.line([(0, yy), (CW, yy)], fill=a)
    base = img.convert("RGB")
    black = Image.new("RGB", (CW, CH), (3, 7, 15))
    base = Image.composite(black, base, ov)
    ov2 = Image.new("L", (CW, CH), 0); d2 = ImageDraw.Draw(ov2)
    for xx in range(CW):  # 좌측 darken
        t = xx / CW
        a = int(255 * max(0, (0.62 - t) / 0.62) * 0.80)
        d2.line([(xx, 0), (xx, CH)], fill=a)
    base = Image.composite(Image.new("RGB", (CW, CH), (5, 10, 20)), base, ov2)
    # 상단 darken — 배경 영상에 박힌 상단 로고/간판(예: 무대 행사명) 가리기
    ov3 = Image.new("L", (CW, CH), 0); d3 = ImageDraw.Draw(ov3)
    for yy in range(CH):
        t = yy / CH
        a = int(255 * max(0, (0.20 - t) / 0.20) ** 1.1 * 0.92)
        d3.line([(0, yy), (CW, yy)], fill=a)
    base = Image.composite(Image.new("RGB", (CW, CH), (3, 7, 15)), base, ov3)
    return base

def pick_dark_bgs(n):
    files = sorted(Path(BGDIR).glob("*.png")) + sorted(Path(BGDIR).glob("*.jpg"))
    scored = []
    for f in files:
        im = Image.open(f).convert("RGB").resize((216, 270))
        bottom = im.crop((0, 150, 216, 270))      # 하단 텍스트존
        scored.append((ImageStat.Stat(bottom).mean[0], f))
    scored.sort()                                  # 어두운 것 우선
    return [f for _, f in scored[:n]]

def render_card(card, idx, total, bg_path):
    img = Image.open(bg_path).convert("RGB").resize((CW, CH))
    img = scrim(img)
    d = ImageDraw.Draw(img)
    f_kick = F(KR_B, 30); f_head = F(KR_B, 78); f_sub = F(KR_R, 36); f_sub_b = F(KR_B, 36)
    f_foot = F(KR_B, 26); f_stat = F(KR_B, 28); f_cta = F(KR_B, 40)
    maxw = CW - PAD * 2

    kicker = card.get("kicker") or card.get("badge")
    if kicker:
        d.text((PAD, PAD), kicker, font=f_kick, fill=KICKER)

    # 하단에서 위로 쌓기: footer 위 공간에 block
    y_bottom = CH - 150
    blocks = []
    head = card.get("headline") or card.get("title")
    body = card.get("body")
    stat = card.get("stat")
    # 높이 계산 위해 wrap 먼저
    head_w = wrap_runs(runs(head), f_head, maxw, d) if head else []
    body_w = wrap_runs(runs(body), f_sub, maxw, d) if body else []
    ARROW = "→"   # U+279C(➜)는 Noto CJK 미지원→두부. U+2192(→)는 지원됨.
    h_lh, b_lh = 90, 52
    total_h = (len(head_w) * h_lh if head_w else 0) + (len(body_w) * b_lh if body_w else 0)
    if stat: total_h += 44
    if card.get("button"): total_h += 92
    if card.get("footnote"): total_h += 50   # footnote도 흐름에 포함(버튼 겹침 방지)
    y = y_bottom - total_h
    if stat:
        d.text((PAD, y), stat, font=f_stat, fill=ACCENT); y += 44
    if head_w:
        y = draw_runs(d, PAD, y, head_w, f_head, f_head, INK, h_lh)
        y += 8
    if body_w:
        y = draw_runs(d, PAD, y, body_w, f_sub, f_sub_b, INK_SOFT, b_lh)
    if card.get("button"):
        label = ARROW + "  " + card["button"]
        tw = d.textlength(label, font=f_cta)
        by = y + 14
        d.rounded_rectangle([PAD, by, PAD + tw + 80, by + 78], radius=14, fill=ACCENT)
        d.text((PAD + 40, by + 16), label, font=f_cta, fill=INK)
        y = by + 78
    if card.get("footnote"):
        d.text((PAD, y + 16), card["footnote"], font=F(KR_R, 26), fill=FOOTER)

    # 푸터
    d.text((PAD, CH - 96), "Keens", font=F(KR_B, 28), fill=INK)
    wm = d.textlength("Keens", font=F(KR_B, 28))
    d.text((PAD + wm + 16, CH - 94), "|  @KEENS_KR", font=f_foot, fill=FOOTER)
    pg = f"{idx:02d} / {total:02d}"
    d.text((CW - PAD - d.textlength(pg, font=f_foot), CH - 94), pg, font=f_foot, fill=FOOTER)
    return img

def main():
    posts = json.loads(Path(BATCH).read_text(encoding="utf-8"))
    main_post = posts[0]
    cards = list(main_post["cards"])
    TYPE_KO = {"cover": "커버", "problem": "문제", "insight": "인사이트",
               "perspective_shift": "관점전환", "cta": "CTA"}
    labels = [f"{i+1:02d} {TYPE_KO.get(c.get('type'), '카드')}" for i, c in enumerate(cards)]
    # 변형 커버 추가
    var = posts[1]["cards"][0] if len(posts) > 1 else None
    items = list(zip(cards, labels))
    n = len(items) + (1 if var else 0)
    bgs = pick_dark_bgs(n)
    total = len(cards)
    rendered = []
    for i, (c, lab) in enumerate(items):
        rendered.append((render_card(c, i + 1, total, bgs[i]), lab))
    if var:
        rendered.append((render_card(var, 1, total, bgs[-1]), "01b 변형커버"))

    # 개별 카드 PNG 저장 (argv[4] = cards_dir 주면): 01.png..0N.png + 01b_cover.png
    if len(sys.argv) > 4:
        cards_dir = Path(sys.argv[4]); cards_dir.mkdir(parents=True, exist_ok=True)
        for i in range(len(cards)):
            rendered[i][0].save(cards_dir / f"{i+1:02d}.png")
        if var:
            rendered[-1][0].save(cards_dir / "01b_cover.png")
        print("cards →", cards_dir, len(list(cards_dir.glob('*.png'))), "PNG")

    # 컨택트시트: 4열
    cols = 4
    thumb_w = 520; thumb_h = int(thumb_w * CH / CW)
    gap = 28; lab_h = 40
    rows = (len(rendered) + cols - 1) // cols
    SW = cols * thumb_w + (cols + 1) * gap
    SH = rows * (thumb_h + lab_h) + (rows + 1) * gap + 70
    sheet = Image.new("RGB", (SW, SH), (18, 22, 28))
    sd = ImageDraw.Draw(sheet)
    sd.text((gap, 24), f"Keens 카드뉴스 검수 컨택트시트 — {Path(BATCH).stem} (배경={Path(BGDIR).name})",
            font=F(KR_B, 30), fill=(255, 255, 255))
    for k, (im, lab) in enumerate(rendered):
        r, c = divmod(k, cols)
        x = gap + c * (thumb_w + gap)
        yy = 70 + gap + r * (thumb_h + lab_h + gap)
        sheet.paste(im.resize((thumb_w, thumb_h)), (x, yy))
        sd.text((x + 4, yy + thumb_h + 8), lab, font=F(KR_B, 24), fill=(201, 210, 226))
    sheet.save(OUT, "JPEG", quality=90)
    print("saved", OUT, sheet.size)

if __name__ == "__main__":
    main()
