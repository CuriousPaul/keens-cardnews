#!/usr/bin/env python3
"""
compose_scenes.py — 장면 이미지를 카드 배경으로 합성 준비 (강한 스크림 내장)

생성한 장면 이미지(Higgsfield 등) → 카드별 배경(1080x1350, 텍스트 가독성 스크림 포함)으로
처리하고, 배치 JSON의 각 카드에 bg 경로를 주입한다. 이후 build_cards.js로 렌더.

입력 장면 폴더 규칙: 카드 순서대로 card01.png, card02.png … (확장자 무관, 정렬순).
                    또는 --map 으로 "카드index:파일경로" 매핑.

사용법:
  pip install pillow
  python3 compose_scenes.py <batch.json> <scenes_dir> <out_bg_dir> <out_json>
    [--scrim 0.92] [--brightness 0.86] [--skip "9,10"]

  # 그다음:
  node build_cards.js <out_json> out/<acct> <out_bg_dir> --template card_template_keens.html ...
  (build_cards 는 카드에 이미 bg가 있으면 그대로 사용)

옵션:
  --scrim       하단 스크림 강도 0~1 (기본 0.92). 밝은 장면일수록 높게.
  --brightness  장면 밝기 배수 (기본 0.86).
  --skip        장면 합성 제외할 카드 번호(쉼표). 예 "9" = 9장은 원래 테마(플랫) 유지.
  --map         "0:/path/a.png,5:/path/b.png" 처럼 카드index(0-based)→파일 직접 지정.
"""
import sys, os, json, glob, argparse
from PIL import Image, ImageOps, ImageEnhance

TW, TH = 1080, 1350

def build_scrim(strength):
    grad = Image.new('L', (1, TH), 0)
    for y in range(TH):
        t = y / TH
        grad.putpixel((0, y), int(max(0, ((t - 0.32) / 0.68)) ** 1.25 * (strength * 255)))
    return grad.resize((TW, TH))

def process(src, scrim, brightness):
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')  # EXIF 회전 필수
    w, h = im.size; tar = TW / TH; cw = int(h * tar)
    if cw <= w:
        x = (w - cw) // 2; im = im.crop((x, 0, x + cw, h))
    else:
        ch = int(w / tar); y = (h - ch) // 2; im = im.crop((0, y, w, y + ch))
    im = im.resize((TW, TH))
    im = ImageEnhance.Brightness(im).enhance(brightness)
    black = Image.new('RGB', (TW, TH), (5, 6, 11))
    return Image.composite(black, im, scrim)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('batch_json'); ap.add_argument('scenes_dir')
    ap.add_argument('out_bg_dir'); ap.add_argument('out_json')
    ap.add_argument('--scrim', type=float, default=0.92)
    ap.add_argument('--brightness', type=float, default=0.86)
    ap.add_argument('--skip', default='')
    ap.add_argument('--map', default='')
    a = ap.parse_args()

    d = json.load(open(a.batch_json, encoding='utf-8'))
    cards = d['cards']; n = len(cards)
    skip = {int(x)-1 for x in a.skip.split(',') if x.strip()}  # card numbers -> 0-based
    os.makedirs(a.out_bg_dir, exist_ok=True)
    scrim = build_scrim(a.scrim)

    # resolve scene source per card
    src_by_idx = {}
    if a.map:
        for pair in a.map.split(','):
            i, p = pair.split(':', 1); src_by_idx[int(i)] = p
    else:
        files = sorted(glob.glob(os.path.join(a.scenes_dir, '*')))
        # match card01..cardNN by name if present, else positional
        named = {}
        for f in files:
            base = os.path.basename(f).lower()
            for k in range(n):
                if f"card{k+1:02d}" in base or f"card{k+1}" in base:
                    named[k] = f
        if named:
            src_by_idx = named
        else:
            for k in range(min(n, len(files))): src_by_idx[k] = files[k]

    done = 0
    for idx in range(n):
        if idx in skip or idx not in src_by_idx:
            continue
        out = os.path.join(a.out_bg_dir, f"card{idx+1:02d}.png")
        process(src_by_idx[idx], scrim, a.brightness).save(out)
        cards[idx]['bg'] = "file://" + os.path.abspath(out)
        done += 1

    json.dump(d, open(a.out_json, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"composed {done}/{n} cards with scenes -> {a.out_json}")
    print(f"backgrounds in {a.out_bg_dir}; now render with build_cards.js")

if __name__ == '__main__':
    main()
