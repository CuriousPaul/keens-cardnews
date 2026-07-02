#!/usr/bin/env python3
"""
tl_video_search.py — [PoC/실험] TwelveLabs로 영상 beat 검색 → 키프레임 회수 → perf_keyframes 스키마 합류.

배경: Dropbox MCP는 인덱싱을 안 하고, 우리 영상 처리(수동 ffmpeg 키프레임)는 스케일이 안 난다.
TwelveLabs(Marengo 검색 + Pegasus 분석)로 "어느 영상 몇 초에 원하는 장면이 있나"를 자연어로 찾아,
그 타임코드에서 키프레임을 뽑아 기존 select_assets.py가 읽는 인덱스로 흡수한다. 설계=docs/TwelveLabs_PoC_설계.md.

전제(에이전트가 선행): Dropbox download_link로 후보 영상을 로컬에 받아 manifest를 만든다.
  manifest.json = [[name, ns_path, local_path], ...]

파이프라인:
  1) TwelveLabs 인덱스 확보(없으면 생성; Marengo+Pegasus)
  2) manifest의 각 영상 업로드·인덱싱(완료 폴링) → {tl_video_id: (name, ns_path, local_path)} 매핑 저장
  3) beat별 자연어 쿼리로 search → top 결과(video_id, start, end, score)
  4) 결과 구간 중앙 프레임을 로컬 영상에서 ffmpeg로 추출(assets/perf_keyframes/tl_*.jpg)
  5) perf_keyframes_index.json 스키마로 append(source="twelvelabs_moment", tl_score/query 포함)

사용:
  export TL_API_KEY=...            # TwelveLabs API 키(회사 계정)
  pip install twelvelabs pillow numpy
  # 검증만(키/네트워크 없이 입력·ffmpeg·매핑 로직 점검):
  python3 tl_video_search.py manifest.json --dry-run
  # 실제 실행:
  python3 tl_video_search.py manifest.json --index-name keens-poc \
      --out ../references/perf_keyframes_index.json --assets-dir ../assets/perf_keyframes --top 2

주의:
  - SDK 메서드/모델 버전명은 배포 시점마다 다를 수 있어 상단 상수로 뺐다(❗확인: docs.twelvelabs.io).
  - 미성년(학생) 영상 반출은 약관/법무 게이트 통과 후에만. 결과에 아동 보이면 kids=True로 사람 확인.
"""
import os, sys, json, argparse, subprocess, hashlib
from pathlib import Path

# ── beat → 자연어 쿼리 (docs/TwelveLabs_PoC_설계.md §4, 튜닝 대상) ──────────────
BEAT_QUERIES = {
    "hook_intro":     "solo dancer alone on a dark stage, dramatic spotlight, moody, cinematic",
    "doubt":          "single performer mid-motion, tense, low light",
    "turn_diagnosis": "instructor demonstrating or correcting a dance move, focused",
    "method_lesson":  "two dancers practicing together, teaching moment",
    "joy_basics":     "dancers smiling, energetic, bright, celebratory",
    "checklist_text": "wide stage shot with dark empty upper area",
    "cta":            "group finishing pose, bright lights, triumphant, stage backdrop",
    "finale":         "full ensemble bow or celebration on stage",
}
# ❗SDK 버전에 따라 확인: 모델(엔진)명·옵션. docs.twelvelabs.io 최신 값으로 교체.
MARENGO_MODEL = "marengo2.7"
PEGASUS_MODEL = "pegasus1.2"
MODEL_OPTIONS = ["visual", "audio"]

def feats(path):
    """추출 프레임의 객관 특징(기존 인덱스 스키마와 동일)."""
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
    """로컬 영상의 t초 프레임 1장(장변 1440) 추출."""
    Path(out_jpg).parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t_sec),
                        "-i", local_video, "-frames:v", "1",
                        "-vf", "scale='min(1440,iw)':-2", out_jpg], capture_output=True)
    return os.path.exists(out_jpg) and os.path.getsize(out_jpg) > 5000

# ── TwelveLabs (SDK 호출은 여기 격리 — 버전 바뀌면 이 함수들만 수정) ──────────
def tl_client(api_key):
    from twelvelabs import TwelveLabs
    return TwelveLabs(api_key=api_key)

def ensure_index(client, name):
    """이름으로 인덱스 조회, 없으면 생성(Marengo+Pegasus)."""
    try:
        for ix in client.index.list():
            if getattr(ix, "name", None) == name:
                return ix.id
    except Exception as e:
        print("[warn] index.list 실패(무시하고 생성 시도):", e)
    models = [{"name": MARENGO_MODEL, "options": MODEL_OPTIONS},
              {"name": PEGASUS_MODEL, "options": MODEL_OPTIONS}]
    ix = client.index.create(name=name, models=models)
    return ix.id

def upload_video(client, index_id, local_path):
    """영상 업로드·인덱싱 완료까지 폴링 → tl_video_id 반환."""
    task = client.task.create(index_id=index_id, file=local_path)
    task.wait_for_done(sleep_interval=5)   # ❗SDK에 따라 poll 방식 상이
    vid = getattr(task, "video_id", None) or getattr(task, "id", None)
    return vid

def search_beat(client, index_id, query_text, top):
    """beat 쿼리로 검색 → [{video_id,start,end,score}] (상위 top)."""
    res = client.search.query(index_id=index_id, query_text=query_text,
                              options=["visual"])   # ❗SDK에 따라 query={'text':...}
    out = []
    for r in list(res)[:top]:
        out.append({"video_id": getattr(r, "video_id", None),
                    "start": float(getattr(r, "start", 0.0)),
                    "end": float(getattr(r, "end", 0.0)),
                    "score": float(getattr(r, "score", 0.0))})
    return out

# ── 인덱스 파일 입출력 ────────────────────────────────────────────────
def load_index(out_path):
    if os.path.exists(out_path):
        d = json.load(open(out_path, encoding="utf-8")); d.setdefault("assets", []); return d
    return {"version": 1, "source": "mixed", "asset_dir": "assets/perf_keyframes",
            "beat_vocab": list(BEAT_QUERIES.keys()),
            "note": "TwelveLabs moment 키프레임 포함(source=twelvelabs_moment).",
            "count": 0, "assets": []}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help='[[name, ns_path, local_path], ...] JSON')
    ap.add_argument("--index-name", default="keens-poc")
    ap.add_argument("--out", default="../references/perf_keyframes_index.json")
    ap.add_argument("--assets-dir", default="../assets/perf_keyframes")
    ap.add_argument("--beats", default=",".join(BEAT_QUERIES),
                    help="검색할 beat(콤마구분). 기본=전체")
    ap.add_argument("--top", type=int, default=2, help="beat당 상위 결과 수")
    ap.add_argument("--dry-run", action="store_true", help="API 없이 입력·매핑·ffmpeg만 점검")
    a = ap.parse_args()

    man = json.load(open(a.manifest, encoding="utf-8"))
    beats = [b.strip() for b in a.beats.split(",") if b.strip() in BEAT_QUERIES]
    missing = [row[2] for row in man if not os.path.exists(row[2])]
    print(f"영상 {len(man)}개, beat {len(beats)}개. 로컬 누락: {missing or '없음'}")

    if a.dry_run:
        print("[dry-run] beat 쿼리:")
        for b in beats: print(f"  - {b}: {BEAT_QUERIES[b]}")
        # ffmpeg/PIL 점검: 첫 영상 5초 프레임 시험 추출
        if man and not missing:
            ok = extract_frame(man[0][2], 5, "/tmp/_tl_probe.jpg")
            print("[dry-run] ffmpeg 프레임 추출:", "OK" if ok else "실패",
                  ("(" + json.dumps(feats("/tmp/_tl_probe.jpg"), ensure_ascii=False) + ")") if ok else "")
        print("[dry-run] 완료 — TL_API_KEY 설정 후 --dry-run 없이 실행하면 실제 인덱싱/검색.")
        return

    key = os.environ.get("TL_API_KEY")
    if not key: sys.exit("TL_API_KEY 환경변수가 없습니다.")
    client = tl_client(key)
    index_id = ensure_index(client, a.index_name)
    print("index_id:", index_id)

    # 업로드·매핑
    vid_map = {}  # tl_video_id -> (name, ns_path, local_path)
    for name, ns_path, local in man:
        if not os.path.exists(local): continue
        vid = upload_video(client, index_id, local)
        if vid: vid_map[vid] = (name, ns_path, local)
        print("indexed:", name, "->", vid)

    # 검색 → 키프레임 회수 → append
    doc = load_index(a.out)
    seen = {r.get("hash") for r in doc["assets"]}
    added = 0
    for beat in beats:
        for hit in search_beat(client, index_id, BEAT_QUERIES[beat], a.top):
            meta = vid_map.get(hit["video_id"])
            if not meta: continue   # 이번에 안 올린 영상 결과는 스킵
            name, ns_path, local = meta
            t = round((hit["start"] + hit["end"]) / 2, 1)
            stem = f"tl_{Path(name).stem}_{beat}_{int(t)}"
            jpg = os.path.join(a.assets_dir, stem + ".jpg")
            if not extract_frame(local, t, jpg):
                print("[warn] 프레임 실패:", stem); continue
            fe = feats(jpg)
            h = hashlib.md5(open(jpg, "rb").read(65536)).hexdigest()[:10]
            if h in seen: continue
            doc["assets"].append({
                "id": stem, "file": stem + ".jpg", "source": "twelvelabs_moment",
                "type": "video_keyframe", "path_rel": f"assets/perf_keyframes/{stem}.jpg",
                "src_video_ns": ns_path, "t_sec": t,
                "people": "group", "mood": "intense", "kids": False, "brand_visible": False,
                "subject": "stage_performance", "note": f"TL:{beat}",
                **{k: fe[k] for k in ("orient","lum_overall","dark_top_textzone","dark_bottom_textzone","redness")},
                "hash": h, "usable_beats": [beat],          # TL 시맨틱 매칭 기반(heuristic 아님)
                "tl_query": BEAT_QUERIES[beat], "tl_score": round(hit["score"], 2),
                "tag_source": "twelvelabs_moment"})
            seen.add(h); added += 1
            print(f"  {beat} <- {name} @ {t}s (score {hit['score']:.1f}) -> {stem}.jpg")
    doc["count"] = len(doc["assets"])
    json.dump(doc, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"append +{added} (total {doc['count']}) -> {a.out}  "
          f"※ people/mood/kids/brand는 컨택트시트로 사람 확인·보정 권장(특히 kids).")

if __name__ == "__main__":
    main()
