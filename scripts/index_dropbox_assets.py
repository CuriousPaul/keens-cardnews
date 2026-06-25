#!/usr/bin/env python3
"""
index_dropbox_assets.py — Dropbox MCP 소스 자산을 assets_index.json 스키마로 인덱싱.

설계: 비전/원본 다운로드는 자산당 1회. 이후 select_assets.py 가 텍스트 인덱스만 읽음.
Dropbox 원본 픽셀은 MCP로 직접 못 읽으므로, "에이전트가 download_link로 받은 로컬 파일"을
이 스크립트에 manifest로 넘긴다. 객관 특징(PIL)을 채우고 semantic은 pending_vision 으로 남긴다
(에이전트가 컨택트시트를 보고 people/mood/subject/brand/kids 를 채우면 tag_source=vision_* 로 승급).

워크플로 (keens-cardnews 파이프라인의 "Dropbox 배경 수집" 단계):
  1) (에이전트) Dropbox MCP search/list_folder 로 대상 폴더의 file_id 수집
       예: 카탈로그 references/dropbox_catalog.json 의 ns_path 참고
  2) (에이전트) download_link(file_id 배치 ≤25) → 단일사용 URL → curl 로 로컬 캐시에 저장
       manifest.json = [[name, file_id, ns_path, local_path], ...]
  3) python3 index_dropbox_assets.py manifest.json --out references/dropbox_assets_index.json
  4) (에이전트) tag_source=pending_vision 항목을 컨택트시트로 보고 시맨틱 태깅 → --apply-tags 로 반영
  5) select_assets.py 로 비트별 선택 → 선택분만 캐시에서 compose_scenes --map 입력

증분: hash(앞 64KB md5) 로 중복 판정. 같은 자산 재실행 시 skip.

사용:
  python3 index_dropbox_assets.py manifest.json [--out references/dropbox_assets_index.json]
      [--root-ns 5805398736] [--root-path "ns:5805398736//02. 활용 가능 이미지/사진"]
  # 시맨틱 태그 일괄 반영(JSON: {"DSC04628":{"people":"solo","mood":"moody","subject":"interview","note":"..","kids":false,"brand_visible":false}})
  python3 index_dropbox_assets.py --apply-tags tags.json --out references/dropbox_assets_index.json
"""
import os, sys, json, hashlib, argparse
from PIL import Image, ImageOps
import numpy as np

BEAT_VOCAB = ["hook_intro","doubt","turn_diagnosis","method_lesson","joy_basics","checklist_text","cta","finale"]

def feats(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w,h = im.size
    arr = np.asarray(im.resize((64,80))).astype(float)
    lum = 0.299*arr[:,:,0]+0.587*arr[:,:,1]+0.114*arr[:,:,2]
    bottom=float(lum[int(80*0.62):,:].mean()); top=float(lum[:int(80*0.18),:].mean())
    return {"w":w,"h":h,"orient":"portrait" if h>=w else "landscape",
            "lum_overall":round(float(lum.mean()),1),
            "dark_top_textzone":bool(top<70),"dark_bottom_textzone":bool(bottom<70),
            "redness":round(float((arr[:,:,0]-arr[:,:,2]).mean()),1)}

def file_hash(path, n=65536):
    return hashlib.md5(open(path,"rb").read(n)).hexdigest()[:10]

def beats(people, mood, kids, brand, dark_top):
    b=set()
    if people=="solo" and mood in ("moody","intense","anticipation"): b.add("hook_intro")
    if people in ("solo","duo") and mood in ("moody","intense"): b.add("doubt")
    if people in ("solo","duo") and mood in ("intense","tender"): b.add("turn_diagnosis")
    if people in ("duo","group") and mood in ("intense","tender"): b.add("method_lesson")
    if mood in ("joyful","celebratory"): b.add("joy_basics")
    if dark_top or mood=="anticipation" or brand: b.add("checklist_text")
    if brand or mood=="celebratory": b.add("cta")
    if people=="ensemble" or mood=="celebratory": b.add("finale")
    return sorted(b)

def load_doc(out, root_ns, root_path):
    if os.path.exists(out):
        d=json.load(open(out,encoding="utf-8")); d.setdefault("assets",[]); return d
    return {"version":1,"source":"dropbox","asset_root_ns":root_ns,"asset_root_path":root_path,
            "beat_vocab":BEAT_VOCAB,
            "note":"Dropbox MCP 소스 인덱스. 로드시 download_link(file_id/ns_path)로 단일사용 URL 발급→다운로드. ns 접두사 제거 금지.",
            "count":0,"assets":[]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="?", help="[[name,file_id,ns_path,local_path],...] JSON")
    ap.add_argument("--out", default="references/dropbox_assets_index.json")
    ap.add_argument("--root-ns", default="")
    ap.add_argument("--root-path", default="")
    ap.add_argument("--apply-tags", help="시맨틱 태그 JSON을 기존 인덱스에 반영(id 키)")
    a=ap.parse_args()

    if a.apply_tags:
        doc=json.load(open(a.out,encoding="utf-8"))
        tags=json.load(open(a.apply_tags,encoding="utf-8"))
        n=0; partial=0; kids_flag=[]
        for r in doc["assets"]:
            t=tags.get(r["id"])
            if not t: continue
            r.update({k:t[k] for k in ("people","mood","subject","note") if k in t})
            if "kids" in t: r["kids"]=bool(t["kids"])
            if "brand_visible" in t: r["brand_visible"]=bool(t["brand_visible"])
            # 시맨틱 핵심(people+mood)이 다 들어와야만 vision 승급 + 비트 재계산.
            # 부분 태그는 필드만 반영하고 pending 유지(미검토값이 사람검토로 둔갑하는 것 방지).
            if t.get("people") and t.get("mood"):
                r["usable_beats"]=beats(r["people"],r["mood"],r.get("kids",False),r.get("brand_visible",False),r["dark_top_textzone"])
                r["tag_source"]="vision_review_v1"; n+=1
            else:
                r.setdefault("tag_source","pending_vision"); partial+=1
            if r.get("kids"): kids_flag.append(r["id"])
        json.dump(doc,open(a.out,"w"),ensure_ascii=False,indent=1)
        msg=f"applied: {n} promoted(vision_review_v1), {partial} partial(pending 유지) -> {a.out}"
        if kids_flag: msg+=f"\n[guardrail] kids:true 자산 {len(kids_flag)}건 — 광고/CTA 사용 전 사람 최종확인 필수: {', '.join(kids_flag[:10])}{' …' if len(kids_flag)>10 else ''}"
        print(msg); return

    if not a.manifest:
        print("manifest 또는 --apply-tags 필요", file=sys.stderr); sys.exit(1)
    man=json.load(open(a.manifest,encoding="utf-8"))
    doc=load_doc(a.out, a.root_ns, a.root_path)
    seen={r.get("hash") for r in doc["assets"]}
    added=0
    for row in man:
        name,fid,ns,local = row[0],row[1],row[2],row[3]
        if not os.path.exists(local):
            print("skip(missing)",name); continue
        h=file_hash(local)
        if h in seen: continue
        try: fe=feats(local)
        except Exception as e:
            print("skip(feat)",name,e); continue
        rec={"id":os.path.splitext(name)[0],"file":name,"file_id":fid,"ns_path":ns,
             "source":"dropbox","type":"photo",
             "people":"group","mood":"intense","kids":False,"brand_visible":False,
             "subject":"stage_performance","note":"",
             "orient":fe["orient"],"lum_overall":fe["lum_overall"],
             "dark_top_textzone":fe["dark_top_textzone"],"dark_bottom_textzone":fe["dark_bottom_textzone"],
             "redness":fe["redness"],"hash":h,
             "usable_beats":beats("group","intense",False,False,fe["dark_top_textzone"]),
             "tag_source":"pending_vision"}
        doc["assets"].append(rec); seen.add(h); added+=1
    doc["count"]=len(doc["assets"])
    json.dump(doc,open(a.out,"w"),ensure_ascii=False,indent=1)
    print(f"indexed +{added} new (total {doc['count']}) -> {a.out}  (pending_vision은 컨택트시트로 태깅 후 --apply-tags)")

if __name__=="__main__":
    main()
