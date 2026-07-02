#!/usr/bin/env python3
"""
materialize_keyframes.py — 인덱스의 키프레임을 Dropbox 원본에서 재생성.

왜: 공개 repo에 실제 촬영 프레임(무대·관객)을 커밋하지 않으려고 assets/perf_keyframes/*.jpg 는 .gitignore.
    대신 인덱스(perf_keyframes_index.json)에 `src_video_ns`+`t_sec`(재현정보)이 있으니,
    David 맥북 등에서 첫 실행 때 원본 영상을 받아 그 프레임을 그대로 뽑아 로컬에 채운다(self-heal).

워크플로(에이전트 주도 — Dropbox MCP 필요):
  1) 무엇이 없는지·어떤 원본이 필요한지 조회:
       python3 materialize_keyframes.py --list-needed --index ../references/perf_keyframes_index.json
     → 없는 프레임이 참조하는 '고유 src_video_ns' 목록 출력.
  2) (에이전트) 그 src_video_ns 들을 Dropbox download_link 로 받아 로컬에 저장하고,
       mapping.json = { "<src_video_ns>": "<로컬 영상경로>", ... } 작성.
  3) 프레임 추출·채움:
       python3 materialize_keyframes.py --extract mapping.json --index ../references/perf_keyframes_index.json --assets-dir ../assets/perf_keyframes
     → 없는 프레임만 t_sec 에서 ffmpeg 로 재생성(결정적 재현). 이미 있는 건 건너뜀.

주의: 성인/약관통과 소스만. kids=true 자산은 사용 전 사람 확인.
"""
import os, sys, json, argparse, subprocess
from pathlib import Path

def missing_records(doc, assets_dir):
    out = []
    for a in doc.get("assets", []):
        f = a.get("file"); ns = a.get("src_video_ns"); t = a.get("t_sec")
        if not (f and ns and t is not None):
            continue
        if not os.path.exists(os.path.join(assets_dir, f)):
            out.append(a)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="../references/perf_keyframes_index.json")
    ap.add_argument("--assets-dir", default="../assets/perf_keyframes")
    ap.add_argument("--list-needed", action="store_true")
    ap.add_argument("--extract", metavar="MAPPING_JSON",
                    help='{ "<src_video_ns>": "<로컬 영상경로>", ... }')
    a = ap.parse_args()
    doc = json.load(open(a.index, encoding="utf-8"))
    miss = missing_records(doc, a.assets_dir)

    if a.list_needed or not a.extract:
        by_src = {}
        for r in miss:
            by_src.setdefault(r["src_video_ns"], []).append({"file": r["file"], "t_sec": r["t_sec"]})
        print(json.dumps({"missing_frames": len(miss),
                          "needed_sources": [{"src_video_ns": k, "frames": v} for k, v in by_src.items()]},
                         ensure_ascii=False, indent=1))
        if not a.extract:
            print(f"\n[안내] 위 needed_sources 를 Dropbox download_link 로 받아 mapping.json 작성 후 "
                  f"--extract 로 재생성. (없는 프레임 {len(miss)}개)", file=sys.stderr)
        return

    mapping = json.load(open(a.extract, encoding="utf-8"))
    Path(a.assets_dir).mkdir(parents=True, exist_ok=True)
    done = 0; skip = 0
    for r in miss:
        vid = mapping.get(r["src_video_ns"])
        if not vid or not os.path.exists(vid):
            skip += 1; continue
        out = os.path.join(a.assets_dir, r["file"])
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(r["t_sec"]),
                        "-i", vid, "-frames:v", "1", "-vf", "scale='min(1440,iw)':-2", out],
                       capture_output=True)
        if os.path.exists(out) and os.path.getsize(out) > 5000:
            done += 1
        else:
            skip += 1; print("[warn] 추출 실패:", r["file"], file=sys.stderr)
    print(f"materialized {done} frame(s), skipped {skip} (원본 매핑 없음/실패). -> {a.assets_dir}")

if __name__ == "__main__":
    main()
