#!/usr/bin/env python3
"""
prep_backgrounds.py — 카드 배경용 사진 전처리

원본 스테이지 사진(가로/세로 혼재) → 1080x1350(4:5) 카드 배경으로 정리.
  1) EXIF 회전 적용 (세로 촬영 사진이 눕는 문제 방지 — 반드시 필요)
  2) 4:5 센터 크롭 + 리사이즈
  3) 살짝 어둡게 + 네이비 톤 통일(브랜드 팔레트)
  4) 텍스트 영역(좌하단)이 충분히 어두운 사진을 자동 선별 (흰 글씨 가독성)

사용법:
  pip install pillow            # HEIC 원본이면: pip install pillow-heif
  python3 prep_backgrounds.py <src_dir> <out_dir> [--keep 24] [--all]

옵션:
  --keep N    텍스트영역이 어두운 상위 N장만 저장 (기본 24)
  --all       선별 없이 전부 저장
"""
import sys, os, glob, argparse
from PIL import Image, ImageEnhance, ImageOps
try:
    import pillow_heif  # 선택: HEIC 지원
    pillow_heif.register_heif_opener()
except Exception:
    pass

TW, TH = 1080, 1350
NAVY = (11, 22, 38)

def process(src_dir, out_dir, keep, take_all):
    os.makedirs(out_dir, exist_ok=True)
    exts = ('*.jpg','*.JPG','*.jpeg','*.JPEG','*.png','*.PNG','*.webp','*.heic','*.HEIC')
    files = []
    for e in exts: files += glob.glob(os.path.join(src_dir, e))
    files = sorted(set(files))
    navy = Image.new('RGB', (TW, TH), NAVY)
    scored = []
    for f in files:
        try:
            im = Image.open(f); im.draft('RGB', (2000, 2000))
            im = ImageOps.exif_transpose(im).convert('RGB')   # EXIF 회전 적용
        except Exception as ex:
            print('skip', f, ex); continue
        w, h = im.size; tar = TW / TH
        cw = int(h * tar)
        if cw <= w:
            x = (w - cw)//2; im = im.crop((x, 0, x+cw, h))
        else:
            ch = int(w / tar); y = (h - ch)//2; im = im.crop((0, y, w, y+ch))
        im = im.resize((TW, TH))
        zone = im.crop((0, int(TH*0.55), int(TW*0.62), TH)).convert('L')
        lum = sum(zone.getdata()) / (zone.size[0]*zone.size[1])
        scored.append((lum, f, im))
    scored.sort(key=lambda t: t[0])           # 어두운 텍스트영역 우선
    chosen = scored if take_all else scored[:keep]
    for i, (lum, f, im) in enumerate(chosen, 1):
        im = ImageEnhance.Brightness(im).enhance(0.82)
        im = Image.blend(im, navy, 0.18)
        im.save(os.path.join(out_dir, f'bg_{i:02d}.png'))
    print(f'processed {len(scored)} -> saved {len(chosen)} to {out_dir}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src_dir'); ap.add_argument('out_dir')
    ap.add_argument('--keep', type=int, default=24)
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    process(a.src_dir, a.out_dir, a.keep, a.all)
