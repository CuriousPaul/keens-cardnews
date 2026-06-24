#!/usr/bin/env python3
"""
select_assets.py — assets_index.json(텍스트)만 읽어 카드 비트별 배경 후보를 고른다.
비전/이미지 로드 없음 → 토큰 거의 0. keens-cardnews 파이프라인의 "배경 선택" 단계.

사용법:
  # 한 비트에 대한 후보 top 5
  python3 select_assets.py assets_index.json --beat hook_intro --top 5

  # 7장 카드 비트 시퀀스에 대해 중복 없이 한 장씩 배정 → compose_scenes.py --map 문자열 출력
  python3 select_assets.py assets_index.json \
     --sequence hook_intro,doubt,turn_diagnosis,method_lesson,joy_basics,checklist_text,cta \
     --root "/Users/nemo/Paperclip/Keens Academy/assets/셀렉 사진 (민수 픽)" --emit-map

필터: --kids / --brand / --prefer-dark (텍스트 가독 우선)
"""
import json, argparse, sys

def score(rec, beat, prefer_dark):
    if beat not in rec.get("usable_beats",[]): return -1
    s=10.0
    # mood/people fit bonuses per beat
    fit={
      "hook_intro":{"mood":{"moody":3,"intense":2,"anticipation":2},"people":{"solo":3}},
      "doubt":{"mood":{"moody":3,"intense":2},"people":{"solo":2,"duo":1}},
      "turn_diagnosis":{"mood":{"intense":2,"tender":2},"people":{"solo":2,"duo":2}},
      "method_lesson":{"mood":{"tender":2,"intense":1},"people":{"group":2,"duo":2}},
      "joy_basics":{"mood":{"joyful":3,"celebratory":2},"people":{"group":2}},
      "checklist_text":{"mood":{"anticipation":3},"people":{"ensemble":2}},
      "cta":{"mood":{"celebratory":3},"people":{"group":1,"ensemble":1}},
      "finale":{"mood":{"celebratory":3},"people":{"ensemble":3,"group":1}},
    }.get(beat,{})
    s+=fit.get("mood",{}).get(rec.get("mood"),0)
    s+=fit.get("people",{}).get(rec.get("people"),0)
    if rec.get("brand_visible"): s+= 4 if beat in ("cta","checklist_text") else 0.5
    if rec.get("kids") and beat=="joy_basics": s+=2
    if rec.get("orient")=="portrait": s+=1            # 4:5 카드에 세로가 덜 잘림
    if prefer_dark and rec.get("dark_top_textzone"): s+=2
    if prefer_dark and rec.get("dark_bottom_textzone"): s+=1
    return s

def candidates(assets, beat, kids, brand, prefer_dark):
    rows=[]
    for r in assets:
        if kids and not r.get("kids"): continue
        if brand and not r.get("brand_visible"): continue
        sc=score(r,beat,prefer_dark)
        if sc>=0: rows.append((sc,r))
    rows.sort(key=lambda x:(-x[0], x[1]["file"]))
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("index"); ap.add_argument("--beat"); ap.add_argument("--sequence")
    ap.add_argument("--top",type=int,default=5)
    ap.add_argument("--kids",action="store_true"); ap.add_argument("--brand",action="store_true")
    ap.add_argument("--prefer-dark",action="store_true",default=True)
    ap.add_argument("--root",default=""); ap.add_argument("--emit-map",action="store_true")
    ap.add_argument("--exclude",default="",help="comma-separated filenames to skip (avoid reusing across sets)")
    a=ap.parse_args()
    doc=json.load(open(a.index,encoding="utf-8")); assets=doc["assets"]
    excl={x.strip() for x in a.exclude.split(",") if x.strip()}
    if excl: assets=[r for r in assets if r["file"] not in excl]

    if a.sequence:
        beats=[b.strip() for b in a.sequence.split(",") if b.strip()]
        used=set(); chosen=[]
        for beat in beats:
            picked=None
            for sc,r in candidates(assets,beat,a.kids,a.brand,a.prefer_dark):
                if r["file"] in used: continue
                picked=r; used.add(r["file"]); break
            chosen.append((beat,picked))
        if a.emit_map:
            parts=[]
            for i,(beat,r) in enumerate(chosen):
                if r: parts.append(f"{i}:{a.root.rstrip('/')+'/' if a.root else ''}{r['file']}")
            print(",".join(parts))
        else:
            for i,(beat,r) in enumerate(chosen):
                print(f"C{i+1:>2} {beat:<14} -> {r['file'] if r else 'NONE':<16} "
                      f"{r['people']+'/'+r['mood'] if r else ''}")
        return

    if a.beat:
        for sc,r in candidates(assets,a.beat,a.kids,a.brand,a.prefer_dark)[:a.top]:
            print(f"{sc:5.1f}  {r['file']:<16} {r['people']}/{r['mood']} "
                  f"kids={int(r['kids'])} brand={int(r['brand_visible'])} "
                  f"dark_top={int(bool(r['dark_top_textzone']))} beats={','.join(r['usable_beats'])}")
        return
    print("specify --beat or --sequence", file=sys.stderr)

if __name__=="__main__":
    main()
