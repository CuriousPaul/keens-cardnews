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

## 6. 퍼포먼스 키프레임 — cta/finale/hook 보강 (`perf_keyframes_index.json`)
02/사진은 다크 무대샷이 없어 **cta·finale=0**. 이를 `99. 킨즈 퍼포먼스/영상 소스 모음/강사 퍼포먼스 영상`
의 ffmpeg 키프레임으로 채웠다. 인덱스 `references/perf_keyframes_index.json`(재현정보 `src_video_ns`+`t_sec`).
⚠️ **실제 JPG(`assets/perf_keyframes/`)는 공개 repo에서 제외**(무대·관객 이미지 비공개). 첫 실행 시
`scripts/materialize_keyframes.py --list-needed` → 필요한 원본을 Dropbox `download_link`로 받아 mapping.json →
`--extract`로 프레임 재생성해 로컬에 채운 뒤 사용.
다운로드 불필요 — 항상 로컬. 재현 정보(`src_video_ns`,`t_sec`) 포함.

- **30컷**(영상 7개): 1차 17컷(darkness-only) + **HQ 13컷**(Impurities 4K 2개, 선명도 Laplacian 필터로 모션블러·산만컷 제거 → 시네마틱·선명). `sharpness` 필드 포함. 제이릭 **세로 4컷**=4:5 최적, KEENS 백드롭 1컷=cta.
- 품질 메모: 1차 17컷은 압축 영상이라 일부 흐릿/산만 → 발행엔 **HQ(hq_*) 우선** 권장. 보류: Unforgiven 560MB 미추출(필요시 추가).
- ⚠️ 5.마컴물 '이미지 단장' 110장은 **완성 크리에이티브(로고+카피 박힘)라 배경 불가**(검토 완료) — 무텍스트 원본 소스 별도 확보 필요.

**조합 선택 패턴(권장):** 본문 비트(doubt/turn/method/joy/checklist)는 02/사진(Dropbox 다운로드),
무대 비트(hook_intro/cta/finale)는 퍼포먼스 키프레임(로컬)에서 각각 select → 카드별 bg를 합쳐 compose.
```bash
# 무대 비트: 로컬 키프레임 (다운로드 없음)
python3 scripts/select_assets.py references/perf_keyframes_index.json --sequence hook_intro,cta,finale --emit-map --root assets/perf_keyframes
# 본문 비트: 02/사진 (emit-download-list → download_link → cache)
python3 scripts/select_assets.py references/dropbox_assets_index.json --sequence doubt,turn_diagnosis,method_lesson,checklist_text --emit-download-list
```
키프레임 갱신/추가: download_link(영상)→`ffmpeg -ss <t> -i v.mp4 -frames:v 1 -vf scale=1280:-2 out.jpg`→비전 태깅→인덱스 append.

## 7. Paperclip 구현 체크리스트 (나중에 에이전트에서 실행)
스킬 파일은 GitHub로 배포됨. **런타임에서 추가로 필요한 것:**
1. **Dropbox MCP 커넥터를 "Keens Content Maker" 에이전트에 연결** — 02/사진(249) 같은 Dropbox 소스는
   런타임에 `search`/`list_folder`/`download_link` MCP 호출로 받아온다. 에이전트 환경에 Dropbox MCP가
   없으면 본문 비트 배경 수집이 실패. (서버: `https://mcp.dropbox.com/mcp`, 팀 Counter Culture)
2. **퍼포먼스 키프레임은 첫 실행 때 materialize** — 이미지가 repo에 없으므로 `materialize_keyframes.py`로 Dropbox 원본에서 1회 재생성(이후 로컬 캐시). 즉 hook/cta/finale도 Dropbox 접근이 최초 1회 필요.
   즉 Dropbox 미연결 상태에서도 무대 비트 카드는 만들 수 있음(본문 비트만 02/사진 의존).
3. **렌더 의존성**: `npm i puppeteer`, `pip install pillow numpy`(+키프레임 추가 추출 시 `ffmpeg`). NEW_MACHINE_SETUP 참고.
4. **선택 워크플로**: 무대 비트=`perf_keyframes_index.json`(--root assets/perf_keyframes), 본문 비트=`dropbox_assets_index.json`(--emit-download-list→download_link→cache). §3·§6 참조.
5. **단일사용 URL 주의**: download_link는 1회 GET. preflight 금지, 받으면 즉시 curl.
6. **증분 인덱싱 위치**: 새 자산은 맥(Paperclip 러너)에서 download_link→ffmpeg/PIL→index_dropbox_assets.py로 추가.

## 5. 가드레일 (브랜드 규칙 준수)
- `스텝픽` 등 **외부사용불가/타사 IP** 영상은 카드·광고 소재 금지.
- 미성년자 이미지: 정숙·건강 프레임만, 외모 평가성 카피 금지(`kids:true` 태깅으로 추적).
- USP 성과표현(아티스트명 등)은 게시 전 사실·승인 확인(PROJECT_INSTRUCTIONS §1).
