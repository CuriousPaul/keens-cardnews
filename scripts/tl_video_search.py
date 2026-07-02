#!/usr/bin/env python3
"""
tl_video_search.py — [검증됨 2026-07-02] TwelveLabs 영상 → 카드 소재 자동화.
Marengo(검색) + Pegasus(자동 태깅/캡션) + 선명도 선별을 한 흐름으로 통합.

무엇을 하나:
  1) 인덱스(marengo3.0 + pegasus1.2)에 영상 업로드
  2) [Pegasus] 영상당 1회 분석 → 우리 스키마(people/mood/brand_visible/subject/kids) 자동 채움
     + 카드 캡션/제목/해시태그 자동 생성 (→ captions 사이드카)
  3) [Marengo] beat별 자연어 검색 → 관련 구간(start~end)
  4) [선명도] 구간 안에서 여러 프레임 샘플링 → Laplacian 최고 선명 프레임 선택(중앙 1컷 아님)
  5) perf_keyframes 스키마로 append (라벨은 Pegasus가 채운 값, tag_source="twelvelabs_pegasus")

교훈 반영: 모델명 marengo3.0/pegasus1.2, 업로드=open(path,'rb'), 검색 group_by='clip'+query_text,
SearchItem.video_id/.start/.end/.rank(score는 구성에 따라 비어 rank 사용), 대용량은 720p 다운스케일 업로드(키프레임은 원본).

전제: Dropbox download_link로 받은 로컬 영상 manifest = [[name, ns_path, local_path], ...] (성인/약관통과 소스).
사용:
  export TL_API_KEY=... ; pip install twelvelabs pillow numpy
  python3 tl_video_search.py manifest.json --dry-run
  python3 tl_video_search.py manifest.json --index-name keens --top 1 --no-pegasus   # 검색만
  python3 tl_video_search.py manifest.json --index-name keens --top 1                 # 검색+Pegasus태깅
"""
import os, sys, json, argparse, subprocess, hashlib, tempfile, re
from pathlib import Path

BEAT_QUERIES = {
    "hook_intro":     "solo dancer alone on stage, dramatic spotlight, moody, cinematic",
    "doubt":          "single performer mid-motion, tense, low light",
    "turn_diagnosis": "instructor demonstrating or correcting a dance move",
    "method_lesson":  "two dancers performing together in sync",
    "joy_basics":     "dancers energetic and celebratory, bright",
    "checklist_text": "wide stage shot with dark empty upper area",
    "cta":            "group finishing pose, triumphant, arms raised, bright lights",
    "finale":         "full group ensemble performing together on stage",
}
SEARCH_MODEL, PEGASUS_MODEL, MODEL_OPTIONS = "marengo3.0", "pegasus1.2", ["visual", "audio"]

# ── 프레임 특징 / 선명도 ────────────────────────────────────────────────
def _np():
    import numpy as np; return np
def feats(path):
    from PIL import Image, ImageOps; np = _np()
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); w, h = im.size
    a = np.asarray(im.resize((64, 80))).astype(float)
    lum = 0.299*a[:,:,0] + 0.587*a[:,:,1] + 0.114*a[:,:,2]
    return {"w": w, "h": h, "orient": "portrait" if h >= w else "landscape",
            "lum_overall": round(float(lum.mean()), 1),
            "dark_top_textzone": bool(lum[:14,:].mean() < 70),
            "dark_bottom_textzone": bool(lum[49:,:].mean() < 70),
            "redness": round(float((a[:,:,0]-a[:,:,2]).mean()), 1)}
def _sharp_top(path):
    from PIL import Image, ImageOps; np = _np()
    from numpy.lib.stride_tricks import sliding_window_view as sw
    a = np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("L").resize((320,180)), float)
    k = np.array([[0,1,0],[1,-4,1],[0,1,0]], float)
    sharp = float((sw(a,(3,3))*k).sum((-1,-2)).var())
    return sharp, float(a[:int(180*0.18),:].mean())
def best_frame(local, t_center, out_jpg, radius=3.0, n=7):
    """구간에서 n프레임 샘플→선명도 상위3 중 상단 가장 어두운 컷 저장. 반환 t."""
    np = _np(); cands = []
    for dt in np.linspace(-radius, radius, n):
        t = max(0.2, round(float(t_center)+float(dt), 1)); tmp = tempfile.mktemp(suffix=".jpg")
        subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",str(t),"-i",local,"-frames:v","1",
                        "-vf","scale='min(1440,iw)':-2",tmp], capture_output=True)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 5000:
            s, top = _sharp_top(tmp); cands.append((s, top, t, tmp))
    if not cands: return None
    cands.sort(key=lambda x: -x[0]); best = min(cands[:3], key=lambda x: x[1])
    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    import shutil; shutil.move(best[3], out_jpg)
    for _s, _t, _tt, p in cands:            # 미선택 임시 프레임 정리
        if p != best[3] and os.path.exists(p): os.remove(p)
    return best[2]

# ── TwelveLabs SDK 1.x ─────────────────────────────────────────────────
def tl_client(api_key):
    from twelvelabs import TwelveLabs; return TwelveLabs(api_key=api_key)
def ensure_index(client, name, with_pegasus):
    for ix in client.indexes.list():
        if getattr(ix, "index_name", None) == name: return ix.id
    models = [{"model_name": SEARCH_MODEL, "model_options": MODEL_OPTIONS}]
    if with_pegasus: models.append({"model_name": PEGASUS_MODEL, "model_options": MODEL_OPTIONS})
    return client.indexes.create(index_name=name, models=models).id
def upload_video(client, index_id, local_path):
    with open(local_path, "rb") as fh:
        task = client.tasks.create(index_id=index_id, video_file=fh)
    client.tasks.wait_for_done(task_id=task.id, sleep_interval=5)
    return client.tasks.retrieve(task_id=task.id).video_id
def search_beat(client, index_id, query_text, top):
    pager = client.search.query(index_id=index_id, search_options=["visual"],
                                query_text=query_text, group_by="clip", page_limit=top)
    out = []
    for it in list(pager)[:top]:
        out.append({"video_id": getattr(it, "video_id", None),
                    "start": float(getattr(it, "start", 0)), "end": float(getattr(it, "end", 0)),
                    "rank": getattr(it, "rank", None)})
    return out

def _parse_json(text):
    text = re.sub(r"^```[a-z]*|```$", "", (text or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, re.S)
    try: return json.loads(m.group(0)) if m else {}
    except Exception: return {}
def pegasus_tags(client, video_id):
    """영상 1회 분석 → 우리 스키마 라벨 + 캡션/해시태그."""
    schema = ('아래 JSON만 출력(이 영상 기준): {"people":"solo|duo|group|ensemble",'
              '"mood":"joyful|intense|tender|moody|celebratory|anticipation","brand_visible":true|false,'
              '"subject":"stage_performance|practice|lesson|interview|backstage","kids":true|false}')
    cap = ('K-pop 아카데미 인스타 카드뉴스용 JSON만: {"title":"1줄","hashtags":["5개"],"summary":"1문장"} 한국어.')
    def A(p):
        r = client.analyze(model_name=PEGASUS_MODEL, video_id=video_id, prompt=p)
        return getattr(r, "data", None) or str(r)
    tags = _parse_json(A(schema)); caption = _parse_json(A(cap))
    return tags, caption

def load_index(out_path):
    if os.path.exists(out_path):
        d = json.load(open(out_path, encoding="utf-8")); d.setdefault("assets", []); return d
    return {"version": 1, "source": "mixed", "asset_dir": "assets/perf_keyframes",
            "beat_vocab": list(BEAT_QUERIES.keys()), "count": 0, "assets": []}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest"); ap.add_argument("--index-name", default="keens")
    ap.add_argument("--out", default="../references/perf_keyframes_index.json")
    ap.add_argument("--assets-dir", default="../assets/perf_keyframes")
    ap.add_argument("--captions-out", default="../references/tl_captions.json")
    ap.add_argument("--beats", default=",".join(BEAT_QUERIES))
    ap.add_argument("--top", type=int, default=1)
    ap.add_argument("--no-pegasus", action="store_true", help="Pegasus 태깅/캡션 끄고 검색만")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    man = json.load(open(a.manifest, encoding="utf-8"))
    beats = [b.strip() for b in a.beats.split(",") if b.strip() in BEAT_QUERIES]
    missing = [r[2] for r in man if not os.path.exists(r[2])]
    print(f"영상 {len(man)}개, beat {len(beats)}개, Pegasus={'off' if a.no_pegasus else 'on'}. 누락: {missing or '없음'}")
    if a.dry_run:
        for b in beats: print(f"  - {b}: {BEAT_QUERIES[b]}")
        if man and not missing:
            t = best_frame(man[0][2], 5, "/tmp/_tl_probe.jpg", radius=2.5, n=5)
            print("[dry-run] best_frame t=", t, feats("/tmp/_tl_probe.jpg") if t else "실패")
        print("[dry-run] 완료."); return
    key = os.environ.get("TL_API_KEY"); assert key, "TL_API_KEY 없음"
    client = tl_client(key)
    index_id = ensure_index(client, a.index_name, not a.no_pegasus); print("index_id:", index_id)

    vid_meta = {}   # video_id -> {name, ns, local, tags}
    captions = {}
    for name, ns_path, local in man:
        if not os.path.exists(local): continue
        vid = upload_video(client, index_id, local)
        tags = {}
        if not a.no_pegasus:
            tags, cap = pegasus_tags(client, vid); captions[ns_path] = cap
            print(f"indexed+tagged: {name} -> {vid}  {tags}  | {cap.get('title','')}")
        else:
            print(f"indexed: {name} -> {vid}")
        vid_meta[vid] = {"name": name, "ns": ns_path, "local": local, "tags": tags}

    doc = load_index(a.out); seen = {r.get("hash") for r in doc["assets"]}; added = 0
    for beat in beats:
        for hit in search_beat(client, index_id, BEAT_QUERIES[beat], a.top):
            m = vid_meta.get(hit["video_id"]);
            if not m: continue
            tc = round((hit["start"] + hit["end"]) / 2, 1)
            stem = f"tl_{Path(m['name']).stem}_{beat}_{int(tc)}"
            jpg = os.path.join(a.assets_dir, stem + ".jpg")
            t = best_frame(m["local"], tc, jpg, radius=3.0, n=7)
            if t is None: print("[warn] frame fail", stem); continue
            fe = feats(jpg); h = hashlib.md5(open(jpg, "rb").read(65536)).hexdigest()[:10]
            if h in seen: continue
            tg = m["tags"]
            doc["assets"].append({
                "id": stem, "file": stem + ".jpg", "source": "twelvelabs_moment", "type": "video_keyframe",
                "path_rel": f"assets/perf_keyframes/{stem}.jpg", "src_video_ns": m["ns"], "t_sec": t,
                "moment_start": round(hit["start"], 1), "moment_end": round(hit["end"], 1),  # Phase2 클립 자르기용
                "people": tg.get("people", "group"), "mood": tg.get("mood", "intense"),
                "kids": bool(tg.get("kids", False)), "brand_visible": bool(tg.get("brand_visible", False)),
                "subject": tg.get("subject", "stage_performance"), "note": f"TL:{beat}",
                **{k: fe[k] for k in ("orient","lum_overall","dark_top_textzone","dark_bottom_textzone","redness")},
                "hash": h, "usable_beats": [beat], "tl_query": BEAT_QUERIES[beat],
                "tl_rank": hit["rank"], "tag_source": "twelvelabs_pegasus" if not a.no_pegasus else "twelvelabs_moment"})
            seen.add(h); added += 1
            print(f"  {beat} <- {m['name']} @ {t}s ({tg.get('people','?')}/{tg.get('mood','?')}) -> {stem}.jpg")
    doc["count"] = len(doc["assets"]); json.dump(doc, open(a.out, "w"), ensure_ascii=False, indent=1)
    if captions: json.dump(captions, open(a.captions_out, "w"), ensure_ascii=False, indent=1)
    print(f"append +{added} (total {doc['count']}) -> {a.out}"
          + (f"  | captions -> {a.captions_out}" if captions else "")
          + "  ※ kids=True 자산은 게시 전 사람 최종확인.")

if __name__ == "__main__":
    main()
