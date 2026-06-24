# 자산 인덱싱 (Asset Index) — 사진·영상 라이브러리를 Paperclip 워크플로우에 붙이는 법

## 왜 인덱싱인가
에이전트가 카드를 만들 때마다 사진 수백 장을 열어보고 고르면 **비전 토큰이 폭발하고 느려진다.**
해결책은 RAG와 같다: **비싼 일(이미지 보고 태깅)은 자산당 딱 한 번**, 그 결과를 가벼운 텍스트
인덱스(`assets_index.json`)에 저장. 이후 카드 제작 때는 **텍스트만 읽어 후보를 고르고, 최종 1~2장만
실제 로드**한다. 신규 촬영분이 들어와도 추가분만 태깅(증분)하므로 비용이 누적되지 않는다.

```
[1회/증분]  index_assets.py  : 폴더 스캔 → 신규만 비전 캡션 → assets_index.json (append)
[매 제작]   select_assets.py : 인덱스(텍스트)만 읽어 카드 비트별 사진 선택 → compose_scenes --map
            compose_scenes.py → build_cards.js : 선택된 실사만 합성·렌더
```

## 파일
- `index_assets.py` — 증분 인덱서. ANTHROPIC_API_KEY 있으면 Haiku 비전으로 태깅, 없으면 객관 특징만
  채우고 `tag_source=pending_vision`(키 생기면 재실행). `--video-keyframe`로 영상도 키프레임 1장 태깅.
- `select_assets.py` — 비트→사진 선택(토큰 거의 0). `--beat` 단건 / `--sequence`로 카드 7장 중복 없이
  배정 / `--emit-map`으로 compose_scenes.py 입력 문자열 출력. 필터 `--kids --brand --prefer-dark`.
- `assets_index.json` — POC: 셀렉 사진(민수 픽) 110장 인덱스(아래 스키마).

## 인덱스 스키마(한 자산 1줄)
```
id, file, path_display, type(photo|video),
people(solo|duo|group|ensemble), mood(joyful|intense|tender|moody|celebratory|anticipation),
kids(bool), brand_visible(bool: KEENS 백드롭), subject(stage_performance|practice|lesson|interview|…),
orient, lum_overall, dark_top_textzone, dark_bottom_textzone(텍스트 가독 영역),
redness, hash(증분 중복판정), usable_beats[], tag_source(vision|vision_review_v1|pending_vision)
```
`usable_beats` 어휘: hook_intro, doubt, turn_diagnosis, method_lesson, joy_basics, checklist_text, cta, finale.

## 카드 10/7-beat ↔ usable_beats 매핑(예)
도입=hook_intro · 궁금증/관점전환=doubt/turn_diagnosis · Keens방식=method_lesson ·
한 사람/기본기=joy_basics · 체크리스트=checklist_text(어두운 텍스트존·브랜드 우선) · CTA=cta(브랜드/피날레).

## 맥미니 / Paperclip 연동
에이전트는 맥미니에서 Claude Code(local)로 돌아 로컬 파일에 직접 접근한다.
1. 원본 라이브러리(사진·영상)를 맥미니 경로에 둔다 (예: `…/Keens Academy/assets/`).
2. (1회/증분) `python3 index_assets.py "<assets_dir>" --out assets_index.json [--video-keyframe]`
3. keens-cardnews 스킬의 "배경 선택" 단계에서:
   ```
   MAP=$(python3 select_assets.py assets_index.json --sequence <비트시퀀스> --root "<assets_dir>" --emit-map)
   python3 compose_scenes.py <batch.json> /tmp/none <out_bg> <out_json> --map "$MAP"
   node build_cards.js <out_json> <out> <out_bg> ...
   ```
→ Higgsfield AI 생성 없이 **자사 실사만으로 카드 양산**(손상원님 피드백과 일치). AI 장면은 실사가
부족한 비트의 보강용으로만 병행.

## 영상·학부모 인터뷰 (다음 단계)
- 인터뷰 영상은 음성 전사 → **실제 증언 인용문 뱅크**로. "수치·사실 날조 금지" 원칙에 맞는 진짜 카피/캡션 소스.
- 영상 키프레임은 사진과 동일 스키마로 인덱싱, 원본 클립은 Reels 재사용을 위해 메타만 보관.
- (별도 스크립트 `transcribe_interviews.py` 권장 — Whisper/transcription → quotes.json)

## POC 결과(110장)
people: solo 51 / group 37 / duo 12 / ensemble 10 · mood: intense 55 / joyful 20 / tender 11 / moody 10 / anticipation 8 / celebratory 6 · KEENS 브랜드 2 · 아이들 13.
비트 커버리지: 전 비트 충족(checklist 75, turn 47, doubt 46, hook 37, method 28, joy 26, finale 13, cta 8).
자동 선택→합성→렌더 7장 정상(가독성 OK, C6 KEENS 백드롭 자동 선택). 샘플: `v23B_auto_sheet.png`.

## 주의
- 비전 태깅 모델 출력은 가끔 흔들린다 → `tag_source` 표시로 추적, 광고 핵심 소재는 사람이 최종 확인.
- 사진 속 미성년자 이미지: 정숙·건강한 프레임만, 외모 평가성 카피 금지(브랜드 규칙).
- 인덱스는 텍스트라 Git/스킬에 함께 버전관리 가능. 원본 대용량은 맥미니 로컬/호스팅에.
