#!/usr/bin/env python3
"""
transcribe_interviews.py — 학부모/학생 인터뷰 영상·오디오 → 전사 + 인용문 뱅크(quotes.json).

목적: 진짜 증언을 카피·캡션 소스로. "수치·사실 날조 금지" 원칙에 맞는 1차 자료.
파이프라인(자산 인덱싱과 동일 철학 — 비싼 일 1회):
  영상/오디오 → (ffmpeg) 오디오 추출 → (whisper) 한국어 전사 → transcripts/<name>.txt + .json(세그먼트)
  → (선택, ANTHROPIC_API_KEY 있으면) LLM이 카드용 후보 인용문 추출 → quotes.json

맥미니/Paperclip에서 실행. 전사는 로컬 whisper 권장(오프라인·무비용).

설치:
  pip install -U openai-whisper   # 또는 faster-whisper
  (ffmpeg 필요: brew install ffmpeg)
  pip install anthropic           # 인용문 추출 단계용(선택)

사용법:
  python3 transcribe_interviews.py "<videos_dir>" --out-dir interviews_out [--model small] [--extract-quotes]

산출물:
  interviews_out/transcripts/<name>.txt      전체 전사
  interviews_out/transcripts/<name>.json     {start,end,text} 세그먼트
  interviews_out/quotes.json                 [{source, quote, theme, persona_hint}]  (--extract-quotes 시)
"""
import os, sys, json, glob, argparse, subprocess, tempfile

AUD=(".mp3",".wav",".m4a",".aac",".flac")
VID=(".mp4",".mov",".m4v",".avi",".mkv")

QUOTE_PROMPT = (
"다음은 아이돌 트레이닝 학원(Keens) 학부모/학생 인터뷰 전사다. "
"인스타 카드뉴스 카피로 쓸 만한 '진짜 목소리' 인용문을 최대 8개 뽑아라. "
"각 인용문은 화자의 실제 표현을 거의 그대로(짧게 다듬기 허용), 감정·고민·전환점이 드러나는 것 우선. "
"JSON 배열만 출력: [{\"quote\":\"...\",\"theme\":\"불안|기대|전환|만족|진단\",\"persona_hint\":\"한 줄\"}]. 다른 말 금지."
)

def extract_audio(path):
    out=tempfile.mktemp(suffix=".wav")
    r=subprocess.run(["ffmpeg","-y","-i",path,"-ac","1","-ar","16000",out],capture_output=True)
    return out if os.path.exists(out) else None

def transcribe(path, model):
    import whisper
    m=whisper.load_model(model)
    res=m.transcribe(path, language="ko", verbose=False)
    segs=[{"start":round(s["start"],2),"end":round(s["end"],2),"text":s["text"].strip()} for s in res.get("segments",[])]
    return res.get("text","").strip(), segs

def extract_quotes(text, source):
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    cl=anthropic.Anthropic(api_key=key)
    msg=cl.messages.create(model="claude-haiku-4-5-20251001",max_tokens=800,
        messages=[{"role":"user","content":QUOTE_PROMPT+"\n\n---\n"+text[:8000]}])
    t="".join(p.text for p in msg.content if p.type=="text").strip()
    t=t[t.find("["):t.rfind("]")+1]
    arr=json.loads(t)
    for q in arr: q["source"]=source
    return arr

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("videos_dir")
    ap.add_argument("--out-dir",default="interviews_out")
    ap.add_argument("--model",default="small")
    ap.add_argument("--extract-quotes",action="store_true")
    a=ap.parse_args()
    tdir=os.path.join(a.out_dir,"transcripts"); os.makedirs(tdir,exist_ok=True)
    files=[]
    for ext in AUD+VID:
        files+=glob.glob(os.path.join(a.videos_dir,f"*{ext}"))+glob.glob(os.path.join(a.videos_dir,f"*{ext.upper()}"))
    files=sorted(set(files))
    if not files:
        print("no audio/video in",a.videos_dir); return
    all_quotes=[]
    for f in files:
        name=os.path.splitext(os.path.basename(f))[0]
        txt_path=os.path.join(tdir,name+".txt")
        if os.path.exists(txt_path):
            print("skip (done)",name); text=open(txt_path,encoding="utf-8").read()
        else:
            src = extract_audio(f) if f.lower().endswith(VID) else f
            if not src: print("skip(audio-fail)",name); continue
            try:
                text,segs=transcribe(src,a.model)
            except Exception as e:
                print("transcribe-fail",name,e); continue
            open(txt_path,"w",encoding="utf-8").write(text)
            json.dump(segs,open(os.path.join(tdir,name+".json"),"w"),ensure_ascii=False,indent=1)
            if src!=f and os.path.exists(src): os.unlink(src)
            print("transcribed",name,f"({len(text)} chars)")
        if a.extract_quotes:
            try:
                q=extract_quotes(text,name)
                if q: all_quotes+=q; print("  quotes +",len(q))
            except Exception as e:
                print("  quote-fail",name,e)
    if a.extract_quotes:
        json.dump(all_quotes,open(os.path.join(a.out_dir,"quotes.json"),"w"),ensure_ascii=False,indent=1)
        print("quotes ->",os.path.join(a.out_dir,"quotes.json"),"(",len(all_quotes),")")

if __name__=="__main__":
    main()
