#!/usr/bin/env python3
"""
index_assets.py — 사진/영상 자산을 1회 비전 캡션 → 텍스트 인덱스(assets_index.json)로.

핵심 아이디어: "비싼 일(비전 캡션)은 자산당 딱 한 번, 자주 하는 일(선택)은 텍스트로".
- 폴더를 스캔해 새 파일만(해시 기준) 비전 모델로 태깅 → 인덱스에 append (증분).
- 카드 제작 시에는 select_assets.py 가 이 인덱스(텍스트)만 읽고 후보를 고른다 → 토큰 거의 안 듦.

실행 환경: 맥미니/Paperclip(Claude Code local). ANTHROPIC_API_KEY 가 환경에 있으면 비전 태깅,
없으면 객관 특징(PIL)만 채우고 semantic="pending_vision" 으로 남긴다(나중에 키 생기면 재실행).

사용법:
  pip install pillow anthropic
  python3 index_assets.py "<assets_dir>" [--out assets_index.json] [--video-keyframe] [--model claude-haiku-4-5-20251001]

영상(--video-keyframe): ffmpeg 로 중간 키프레임 1장 추출해 사진과 동일 스키마로 태깅.
인터뷰 영상 전사는 transcribe_interviews.py(별도)에서 처리 — 인용문 뱅크용.
"""
import os, sys, json, glob, hashlib, argparse, base64, subprocess, tempfile
from PIL import Image, ImageOps
import numpy as np

IMG_EXT = (".jpg",".jpeg",".png",".heic",".webp")
VID_EXT = (".mp4",".mov",".m4v",".avi")
BEAT_VOCAB = ["hook_intro","doubt","turn_diagnosis","method_lesson","joy_basics","checklist_text","cta","finale"]

VISION_PROMPT = (
"You are tagging a Korean K-pop / idol-academy stage or studio photo for a marketing asset index. "
"Return ONLY compact JSON with keys: "
"people (one of solo|duo|group|ensemble), "
"mood (one of joyful|intense|tender|moody|celebratory|anticipation), "
"kids (true if performers look like young children), "
"brand_visible (true if a 'KEENS' logo/backdrop is visible), "
"subject (short, e.g. stage_performance, practice, lesson, interview, backstage, award), "
"note (<=8 words, Korean ok). No prose, JSON only."
)

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

def vision_tag(path, model):
    """Call Anthropic vision. Returns dict or None if unavailable."""
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key: return None
    try:
        import anthropic
    except ImportError:
        return None
    # downscale to keep tokens low
    im=ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((768,768))
    with tempfile.NamedTemporaryFile(suffix=".jpg",delete=False) as t:
        im.save(t.name,quality=80); b=open(t.name,"rb").read()
    os.unlink(t.name)
    cl=anthropic.Anthropic(api_key=key)
    msg=cl.messages.create(model=model, max_tokens=200, messages=[{"role":"user","content":[
        {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":base64.b64encode(b).decode()}},
        {"type":"text","text":VISION_PROMPT}]}])
    txt="".join(p.text for p in msg.content if p.type=="text").strip()
    txt=txt[txt.find("{"):txt.rfind("}")+1]
    return json.loads(txt)

def video_keyframe(path):
    out=tempfile.mktemp(suffix=".jpg")
    subprocess.run(["ffmpeg","-y","-i",path,"-vf","thumbnail","-frames:v","1",out],
                   capture_output=True)
    return out if os.path.exists(out) else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("assets_dir")
    ap.add_argument("--out",default="assets_index.json")
    ap.add_argument("--model",default="claude-haiku-4-5-20251001")
    ap.add_argument("--video-keyframe",action="store_true")
    a=ap.parse_args()

    doc={"version":1,"asset_root":a.assets_dir,"beat_vocab":BEAT_VOCAB,"assets":[]}
    if os.path.exists(a.out):
        doc=json.load(open(a.out,encoding="utf-8")); doc.setdefault("assets",[])
    seen={r.get("hash") for r in doc["assets"]}

    files=[]
    for ext in IMG_EXT: files+=glob.glob(os.path.join(a.assets_dir,f"*{ext}"))+glob.glob(os.path.join(a.assets_dir,f"*{ext.upper()}"))
    if a.video_keyframe:
        for ext in VID_EXT: files+=glob.glob(os.path.join(a.assets_dir,f"*{ext}"))+glob.glob(os.path.join(a.assets_dir,f"*{ext.upper()}"))
    files=sorted(set(files))

    added=0
    for f in files:
        is_video=f.lower().endswith(VID_EXT)
        src=video_keyframe(f) if is_video else f
        if not src: continue
        h=file_hash(f)
        if h in seen: continue
        try:
            fe=feats(src)
        except Exception as e:
            print("skip(feat)",os.path.basename(f),e); continue
        sem=None
        try: sem=vision_tag(src, a.model)
        except Exception as e: print("vision-fail",os.path.basename(f),e)
        if sem:
            people=sem.get("people","group"); mood=sem.get("mood","intense")
            kids=bool(sem.get("kids",False)); brand=bool(sem.get("brand_visible",False))
            subject=sem.get("subject","stage_performance"); note=sem.get("note","")
            tag_source="vision"
        else:
            people,mood,kids,brand,subject,note = "group","intense",False,False,"stage_performance",""
            tag_source="pending_vision"
        rec={"id":os.path.splitext(os.path.basename(f))[0],"file":os.path.basename(f),
             "path_display":f,"type":"video" if is_video else "photo",
             "people":people,"mood":mood,"kids":kids,"brand_visible":brand,"subject":subject,"note":note,
             "orient":fe["orient"],"lum_overall":fe["lum_overall"],
             "dark_top_textzone":fe["dark_top_textzone"],"dark_bottom_textzone":fe["dark_bottom_textzone"],
             "redness":fe["redness"],"hash":h,
             "usable_beats":beats(people,mood,kids,brand,fe["dark_top_textzone"]),
             "tag_source":tag_source}
        doc["assets"].append(rec); seen.add(h); added+=1
        if is_video and src!=f and os.path.exists(src): os.unlink(src)
    doc["count"]=len(doc["assets"])
    json.dump(doc,open(a.out,"w"),ensure_ascii=False,indent=1)
    print(f"indexed +{added} new (total {doc['count']}) -> {a.out}")

if __name__=="__main__":
    main()
