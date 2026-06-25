# Dropbox 자산 연동 (카드뉴스 배경 소스)

킨즈 사진·영상 라이브러리가 Dropbox(팀: Counter Culture, `keens_edu@c-3.co`)에 있다. 카드 제작 시
**로컬 셀렉 사진**으로 부족하면 Dropbox에서 추가 자산을 끌어온다. 이 문서는 그 연동 런북이다.

## 0. 무엇이 어디에 (요약 — 상세: `dropbox_catalog.json`)
| 폴더 | ns_path | 역할 |
|---|---|---|
| 출시영상/02. 활용 가능 이미지 | `ns:5805398736//02. 활용 가능 이미지` | **정지사진 풀 1순위(712장)**. DSC 강의·BTS·인터뷰. `사진`(266)·`룩 강의사진`(228)·`퍼포머 with 아티스트`(101) |
| 킨즈 서울/5. 마컴물 | `ns:3283520483//5. 마컴물` | 마케팅 **영상**(릴스/피드 330개) + `*이미지 단장` 완성 PNG ~110장 |
| 킨즈 서울/99. 킨즈 퍼포먼스 | `ns:3283520483//99. 킨즈 퍼포먼스` | 강사 **퍼포먼스 영상** 8개 → 다크 무대샷 키프레임(hook/finale/cta 보강) |
| 킨즈 서울/브랜드 이미지 | `ns:3283520483//브랜드 이미지` | 브랜드 다이어그램 소형 이미지 |
| 킨즈 서울/스텝픽 | `ns:3283520483//스텝픽` | ⚠️ 아이돌 안무 **모니터링 영상**(일부 외부사용불가) — 카드 소재 **사용 금지** |

> ns_path의 `ns:<id>//` 접두사는 **절대 제거하지 않는다**. MCP 도구에 그대로 넘긴다.

## 1. MCP 도구 (Dropbox)
- `search(query, path, file_categories=["IMAGE"], max_results)` — 폴더 범위 검색(파일명/내용). DSC 사진은 `query:"DSC"`.
- `list_folder(path, recursive)` — 폴더 탐색. 큰 폴더는 `recursive:false`로 children부터.
- `download_link(entries=[file_id|ns_path], expiration_in_sec)` — **단일사용** 임시 URL(최대 25개/콜).
  ⚠️ URL은 HEAD/Range 포함 첫 요청에 소모됨 → preflight 금지, 받으면 바로 `curl -L -o`로 1회 GET.
- `get_file_content` — PDF/문서 텍스트 추출용(이미지 픽셀 아님).

## 2. 인덱싱 (자산당 1회, 증분)
이미지 픽셀은 MCP로 직접 못 읽으므로 **다운로드 → 로컬 PIL 특징 → 텍스트 인덱스** 순.

```
1) 대상 file_id 수집:   search(path=<폴더 ns_path>, file_categories=["IMAGE"], query="DSC")
2) download_link(file_id ≤25)  →  curl -s -L -o cache/<name> <download_url>
3) manifest.json = [[name, file_id, ns_path, local_path], ...]
4) python3 scripts/index_dropbox_assets.py manifest.json --out references/dropbox_assets_index.json
     → 객관특징(orient/lum/textzone/redness) 채움, tag_source="pending_vision"
5) 시맨틱 태깅: pending 자산을 컨택트시트(render_contact_sheet.py)로 한 번에 보고
   people/mood/subject/kids/brand_visible 판정 → tags.json → --apply-tags 로 승급
```

인덱스 스키마는 로컬 `assets_index.json`과 동일 + `file_id`·`ns_path`·`source:"dropbox"` 추가.
→ 로컬/Dropbox 인덱스를 동일 `select_assets.py`로 함께 쓸 수 있음.

## 3. 카드 제작 시 배경 선택 → 가져오기
**선택은 인덱스(텍스트)로, 다운로드는 선택분만.** 순서가 핵심 — emit-map(파일명 only)만으로는
다운로드를 못 하므로, 먼저 `--emit-download-list`로 선택분의 `file_id`/`ns_path`를 받아 내려받은 뒤
같은 시퀀스로 `--emit-map`을 만든다(둘은 결정적이라 동일 자산을 가리킴).

```bash
SEQ="hook_intro,doubt,turn_diagnosis,method_lesson,joy_basics,checklist_text,cta"
# (1) 선택분의 [file, file_id, ns_path] 받기 (미충족 비트는 stderr 경고)
DL=$(python3 scripts/select_assets.py references/dropbox_assets_index.json --sequence "$SEQ" --emit-download-list)
# (2) 에이전트: DL의 file_id들을 Dropbox MCP download_link(≤25)로 단일사용 URL 발급 →
#     curl -s -L -o cache/<file> <download_url>   (preflight 금지, 1회 GET)
# (3) 같은 시퀀스로 compose 입력 맵 생성 (--root=cache) → 합성 → 렌더
MAP=$(python3 scripts/select_assets.py references/dropbox_assets_index.json --sequence "$SEQ" --emit-map --root cache)
python3 scripts/compose_scenes.py <batch.json> /tmp/none <out_bg> <out_json> --map "$MAP"
node scripts/build_cards.js <out_json> <out> <out_bg> --template scripts/card_template_keens.html ...
```
⚠️ **미충족 비트 처리:** select가 채우지 못한 비트(현재 인덱스는 cta/finale)는 stderr에 경고가 뜨고
emit-map에서 **그 인덱스가 빠진다** → 해당 카드는 배경 없이 렌더됨. cta/finale은 99.킨즈퍼포먼스
키프레임을 인덱싱해 채우거나 AI 장면(SKILL.md 3b)으로 보강한 뒤 합성할 것.
미성년 제외가 필요하면 `--no-kids`, KEENS 백드롭만 원하면 `--brand`.

## 4. 현재 인덱스 상태 (2026-06-25)
- `references/dropbox_assets_index.json` — **249장**(02/사진, vision_claude_v1 태깅).
  - 특성: 댄스 연습·BTS·인터뷰(성인 남성, 밝은 흰 스튜디오) 위주. solo 155 / duo 92 / group 2. mood: intense 173·anticipation 29·tender 23·moody 19·joyful 5. **전부 landscape** → 4:5 카드는 중앙 크롭(인물 중심 확인).
  - 비트 커버리지: turn_diagnosis 195, doubt 190, hook_intro 144, method_lesson 78, checklist_text 29, joy_basics 5. **cta·finale=0**(brand_visible·celebratory·ensemble 샷 부재).
  - kids:true 0 / brand_visible 0.
  - → **cta/finale와 다크 무대샷은 `99. 킨즈 퍼포먼스` 영상 키프레임으로 보강**(ffmpeg로 한 컷 추출 → index_dropbox_assets.py manifest에 local_path로 추가 → 비전 태깅).
- 미인덱싱(증분 대상): 02/사진 잔여 ~17장(전사 누락분), `룩 강의사진`(228)·`퍼포머 with 아티스트`(101)·`두번째 데이트 강의사진`(87). 위 2절 루프 반복.

## 5. 가드레일 (브랜드 규칙 준수)
- `스텝픽` 등 **외부사용불가/타사 IP** 영상은 카드·광고 소재 금지.
- 미성년자 이미지: 정숙·건강 프레임만, 외모 평가성 카피 금지(`kids:true` 태깅으로 추적).
- USP 성과표현(아티스트명 등)은 게시 전 사실·승인 확인(PROJECT_INSTRUCTIONS §1).
