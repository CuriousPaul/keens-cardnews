#!/usr/bin/env python3
"""
tl_video_search.py — [PoC, 검증됨 2026-07-02] TwelveLabs로 영상 beat 검색 → 키프레임 회수 → perf_keyframes 스키마 합류.

배경: Dropbox MCP는 인덱싱을 안 하고, 우리 영상 처리(수동 ffmpeg 키프레임)는 스케일이 안 난다.
TwelveLabs(Marengo 검색)로 "어느 영상 몇 초에 원하는 장면이 있나"를 자연어로 찾아, 그 타임코드에서
키프레임을 뽑아 기존 select_assets.py가 읽는 인덱스로 흡수한다. 설계=docs/TwelveLabs_PoC_설계.md.

✅ 실측 검증(강사 퍼포먼스 3개, SDK twelvelabs==1.2.8, API v1.3):
   marengo3.0로 인덱싱 → beat 자연어 쿼리가 의미적으로 정확한 순간 반환(solo→솔로, ensemble→finale, 팔든포즈→cta).
   교훈(하드코딩됨): 모델명=marengo3.0, 업로드는 video_file=open(path,'rb') (경로 문자열은 'video_file_broken' 에러),
   검색은 group_by='clip'+query_text, SearchItem.id=video_id / .clips=순간들.

전제(에이전트 선행): Dropbox download_link로 후보 영상을 로컬에 받아 manifest 생성.
  manifest.json = [[name, ns_path, local_path], ...]   (성인 강사 영상만 — 미성년 게이트 통과 전 학생 영상 금지)

사용:
  export TL_API_KEY=...          ;  pip install twelvelabs pillow numpy
  python3 tl_video_search.py manifest.json --dry-run                      # API 없이 입력/ffmpeg 점검
  python3 tl_video_search.py manifest.json --index-name keens-poc --top 2 # 실제
"""
import os, sys, json, argparse, subprocess, hashlib
from pathlib import Path

# ── beat → 자연어 쿼리 (튜닝 대상) ──────────────────────────────────────
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
SEARCH_MODEL = "marengo3.0"          # ← v1.3 유효값: marengo3.0 / pegasus1.2 (2.7 아님)
MODEL_OPTIONS = ["visual", "audio"]

def feats(path):
    from PIL import Image, ImageOps
    import numpy as np
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); w, h = im.size
    a = np.asarray(im.resize((64, 80))).astype(float)
    lum = 0.299*a[:,:,0] + 0.587*a[:,:,1] + 0.114*a[:,:,2]
    return {"w": w, "h": h, "orient": "portrait" if h >= w else "landscape",
            "lum_overall": round(float(lum.mean()), 1),
            "dark_top_textzone": bool(lum[:14,:].mean() < 70),
            "dark_bottom_textzone": bool(lum[49:,:].mean() < 70),
            "redness": round(float((a[:,:,0]-a[:,:,2]).mean()), 1)}

def extract_frame(local_video, t_sec, out_jpg):
    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t_sec), "-i", local_video,
                    "-frames:v", "1", "-vf", "scale='min(1440,iw)':-2", out_jpg], capture_output=True)
    return os.path.exists(out_jpg) and os.path.getsize(out_jpg) > 5000

# ── TwelveLabs SDK 1.x (검증된 호출) ───────────────────────────────────
def tl_client(api_key):
    from twelvelabs import TwelveLabs
    return TwelveLabs(api_key=api_key)

def ensure_index(client, name):
    for ix in client.indexes.list():
        if getattr(ix, "index_name", None) == name:
            return ix.id
    ix = client.indexes.create(index_name=name,
            models=[{"model_name": SEARCH_MODEL, "model_options": MODEL_OPTIONS}])
    return ix.id

def upload_video(client, index_id, local_path):
    """⚠️ video_file 은 반드시 열린 파일 핸들(open('rb')). 경로 문자열은 거부됨."""
    with open(local_path, "rb") as fh:
        task = client.tasks.create(index_id=index_id, video_file=fh)
    client.tasks.wait_for_done(task_id=task.id, sleep_interval=5)
    return client.tasks.retrieve(task_id=task.id).video_id

def search_beat(client, index_id, query_text, top):
    """group_by='clip' → SearchItem(.id=video_id, .start/.end, .clips=[{score,confidence,start,end}])."""
    pager = client.search.query(index_id=index_id, search_options=["visual"],
                                query_text=query_text, group_by="clip", page_limit=top)
    out = []
    for item in list(pager)[:top]:
        clips = getattr(item, "clips", None) or []
        best = clips[0] if clips else item
        out.append({"video_id": getattr(item, "id", None),
                    "start": float(getattr(best, "start", getattr(item, "start", 0))),
                    "end": float(getattr(best, "end", getattr(item, "end", 0))),
                    "score": float(getattr(best, "score", 0.0)),
                    "confidence": getattr(best, "confidence", None)})
    return out

def load_index(out_path):
    if os.path.exists(out_path):
        d = json.load(open(out_path, encoding="utf-8")); d.setdefault("assets", []); return d
    return {"version": 1, "source": "mixed", "asset_dir": "assets/perf_keyframes",
            "beat_vocab": list(BEAT_QUERIES.keys()),
            "note": "TwelveLabs moment 키프레임 포함(source=twelvelabs_moment).", "count": 0, "assets": []}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help='[[name, ns_path, local_path], ...] JSON')
    ap.add_argument("--index-name", default="keens-poc")
    ap.add_argument("--out", default="../references/perf_keyframes_index.json")
    ap.add_argument("--assets-dir", default="../assets/perf_keyframes")
    ap.add_argument("--beats", default=",".join(BEAT_QUERIES))
    ap.add_argument("--top", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    man = json.load(open(a.manifest, encoding="utf-8"))
    beats = [b.strip() for b in a.beats.split(",") if b.strip() in BEAT_QUERIES]
    missing = [r[2] for r in man if not os.path.exists(r[2])]
    print(f"영상 {len(man)}개, beat {len(beats)}개. 로컬 누락: {missing or '없음'}")
    if a.dry_run:
        for b in beats: print(f"  - {b}: {BEAT_QUERIES[b]}")
        if man and not missing and extract_frame(man[0][2], 5, "/tmp/_tl_probe.jpg"):
            print("[dry-run] ffmpeg OK:", json.dumps(feats("/tmp/_tl_probe.jpg"), ensure_ascii=False))
        print("[dry-run] 완료 — TL_API_KEY 설정 후 --dry-run 빼고 실행."); return

    key = os.environ.get("TL_API_KEY")
    if not key: sys.exit("TL_API_KEY 없음.")
    client = tl_client(key)
    index_id = ensure_index(client, a.index_name); print("index_id:", index_id)

    vid_map = {}
    for name, ns_path, local in man:
        if not os.path.exists(local): continue
        vid = upload_video(client, index_id, local)
        if vid: vid_map[vid] = (name, ns_path, local)
        print("indexed:", name, "->", vid)

    doc = load_index(a.out); seen = {r.get("hash") for r in doc["assets"]}; added = 0
    for beat in beats:
        for hit in search_beat(client, index_id, BEAT_QUERIES[beat], a.top):
            meta = vid_map.get(hit["video_id"])
            if not meta: continue
            name, ns_path, local = meta
            t = round((hit["start"] + hit["end"]) / 2, 1)
            stem = f"tl_{Path(name).stem}_{beat}_{int(t)}"
            jpg = os.path.join(a.assets_dir, stem + ".jpg")
            if not extract_frame(local, t, jpg):
                print("[warn] frame fail:", stem); continue
            fe = feats(jpg); h = hashlib.md5(open(jpg, "rb").read(65536)).hexdigest()[:10]
            if h in seen: continue
            doc["assets"].append({
                "id": stem, "file": stem + ".jpg", "source": "twelvelabs_moment", "type": "video_keyframe",
                "path_rel": f"assets/perf_keyframes/{stem}.jpg", "src_video_ns": ns_path, "t_sec": t,
                "people": "group", "mood": "intense", "kids": False, "brand_visible": False,
                "subject": "stage_performance", "note": f"TL:{beat}",
                **{k: fe[k] for k in ("orient","lum_overall","dark_top_textzone","dark_bottom_textzone","redness")},
                "hash": h, "usable_beats": [beat], "tl_query": BEAT_QUERIES[beat],
                "tl_score": round(hit["score"], 2), "tl_confidence": hit["confidence"],
                "tag_source": "twelvelabs_moment"})
            seen.add(h); added += 1
            print(f"  {beat} <- {name} @ {t}s (score {hit['score']:.1f}/{hit['confidence']}) -> {stem}.jpg")
    doc["count"] = len(doc["assets"])
    json.dump(doc, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"append +{added} (total {doc['count']}) -> {a.out}  "
          f"※ people/mood/kids/brand는 컨택트시트로 사람 확인·보정 권장(특히 kids).")

if __name__ == "__main__":
    main()
