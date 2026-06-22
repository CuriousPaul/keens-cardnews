# Keens 카드뉴스 — 노코드 발행 연동 가이드

> 카드 공장(`build_cards.js`)은 도구 중립입니다. 이 문서는 **노코드 도구(Make·Zapier·Buffer·Later)** 로 발행/인게이지먼트를 붙이는 방법입니다. n8n 없이 동작합니다.

---

## 0. 전체 그림

```
build_cards.js ──► out/<acct>/
                     ├─ <post_id>/01.png … 0N.png      (카드 이미지)
                     ├─ publish_manifest.json          (기계 판독용 전체 정보)
                     └─ publish_schedule.csv           (노코드 도구가 읽는 평면표)
                          │
        ┌─────────────────┼───────────────────────────┐
   [이미지 호스팅]     [예약 발행]                 [댓글→DM]
   Drive/S3/CDN  →   Buffer · Later · Make    →   ManyChat (키워드=dm_keyword)
```

핵심 인수인계 문서는 **`publish_schedule.csv`** 한 장입니다. 컬럼: `post_id, status, scheduled_date, dm_keyword, card_count, caption, image_urls`(파이프 ` | ` 구분).

---

## 1. 먼저: 이미지 호스팅 (노코드의 유일한 전제)

노코드 IG 발행 도구는 이미지를 **공개 URL**로 받습니다. 카드 PNG를 아래 중 하나에 올리고, 빌드 시 `--base-url`을 그 위치로 지정하면 CSV의 `image_urls`가 자동으로 맞춰집니다.

| 호스팅 | 난이도 | 비고 |
|---|---|---|
| Google Drive(공개 폴더) | 낮음 | 이미 연결돼 있음. 폴더 공개 → 링크 패턴 사용 |
| Cloudinary | 낮음 | 무료 티어, 이미지 CDN에 최적 |
| AWS S3 / Cloudflare R2 | 중간 | 정적 호스팅, 안정적 |
| Bunny / 기타 CDN | 중간 | 대량 발행 시 비용 효율 |

```bash
node build_cards.js us_batch.json out/us mvp/bg_fixed \
  --base-url https://cdn.yourhost.com/keens/us \
  --start 2026-06-22 --cadence 1 --skip-weekends
```
→ 이후 `out/us/<post_id>/` 폴더를 호스팅 위치에 그대로 업로드(또는 동기화)하면 끝.

---

## 2. 예약 발행 — 두 가지 노코드 경로

### 경로 A — Buffer / Later (가장 간단, 추천)
1. `publish_schedule.csv`를 Google Sheet로 올린다(또는 그대로 사용).
2. Later: **Bulk import** 또는 Google Sheet 연동으로 행을 가져온다. `image_urls`의 여러 URL → 캐러셀, `caption` → 본문, `scheduled_date` → 예약 시각.
3. Buffer: Google Sheet를 소스로 하는 자동화(또는 Make 경유)로 큐에 적재.
4. 검수 후 승인 → 예약 발행. (초기엔 사람이 큐를 한 번 훑고, 안정되면 자동 승인)

### 경로 B — Make / Zapier (완전 자동)
1. 트리거: **Google Sheets → 새 행** (status=`ready`).
2. 액션 옵션 ①: **Buffer/Later 모듈**로 게시물 생성(가장 쉬움).
3. 액션 옵션 ②: **Instagram Graph API** 직접 호출(3단계) —
   - 카드별 이미지 컨테이너 생성(`/media`, `is_carousel_item=true`)
   - 캐러셀 컨테이너 생성(`/media`, `media_type=CAROUSEL`, children=컨테이너ID들)
   - `/media_publish`로 발행
4. 성공 시 시트의 `status`를 `posted`로 갱신(Make가 행 업데이트).

> 상태 흐름: `ready → scheduled → posted`. 도구가 이 컬럼만 갱신하면 됩니다.

---

## 3. 댓글 → DM 인게이지먼트 (ManyChat, 노코드)

이 부분은 원래부터 노코드입니다.
1. ManyChat의 **Instagram → Comment 키워드 트리거**를 만든다.
2. 키워드 = 각 게시물의 **`dm_keyword`**(예: `LEVELCHECK` / `레벨테스트`).
3. 트리거 플로우: 자동 DM → 레벨 테스트 안내 → 랜딩 링크(6개월 패키지 등).
4. 게시 캡션에 "댓글/DM에 '`dm_keyword`'를 남겨주세요"가 들어가도록(콘텐츠 엔진이 이미 생성) 유지.

선택: 의도 분류(관심/문의/안티)를 넣고 싶으면 Make 한 스텝(Claude/AI 모듈)으로 분기 후 ManyChat 호출. 없어도 키워드 트리거만으로 충분히 동작.

---

## 4. 운영 루프(주간)

1. 콘텐츠 엔진이 다음 주 배치 JSON 생성(주제·카피·캡션·dm_keyword·한·영).
2. `build_cards.js` 실행 → 카드 + CSV/매니페스트.
3. 카드 호스팅에 업로드(동기화 자동화 1회 세팅).
4. 시트 검수(초기) → Buffer/Make가 예약 발행.
5. ManyChat이 댓글 키워드로 DM 퍼널 가동.
6. 결과(도달·DM·전환)를 시트에 누적 → 다음 배치 개선.

---

## 5. 지금 상태 / 빠진 것

- ✅ 빌드 엔진(`build_cards.js`), 매니페스트/CSV, 카드 렌더 — 완료, 도구 중립.
- ⚠️ `us_batch.json` 등 현재 배치에는 **`caption` 필드가 비어 있음** → 콘텐츠 엔진이 게시물별 캡션(+해시태그)을 채우면 CSV에 자동 반영(샘플 단건 JSON엔 이미 캡션 있음).
- ⚠️ **이미지 호스팅 위치 1개 선택** 필요(1장 참고) → `--base-url` 지정.
- ⚠️ Buffer/Later/Make 중 **실제 사용할 도구 1개 확정** 후 계정 연결.

세 가지만 정하면 사람이 'CSV 검수 → 승인'만 하는 반자동, 이후 완전 자동으로 단계 전환할 수 있습니다.
