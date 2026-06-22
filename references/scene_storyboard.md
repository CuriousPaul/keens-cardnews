# 장면 스토리보드 — 학부모 세트(V22-KR-parent), 카드별 배경

> 각 카드 텍스트 뒤에 깔 '실제 장면' 배경. 모델 Recraft 4.1, 4:5(1080×1350), 텍스트가 앉는 영역은 어둡게.
> 인물은 합성 일반인(특정 실인물 아님), 아동은 일상·교육 맥락으로 정숙하게, 로고/텍스트/실브랜드 없음.

| 카드 | 화면 문구(요지) | 장면 | 생성 프롬프트 키 |
|---|---|---|---|
| 1 도입 | 밤마다 검색해 본 적 있으신가요 | **밤에 소파에서 폰 보는 엄마(걱정)** | worried mother late 30s, phone glow, dark living room, lower-third dark for text |
| 2 처음엔 | 한때겠지 했는데 안 식음 | **거울 앞에서 춤추는 아이(회상, 뒤/측면)** | preteen practicing dance at bedroom mirror, warm lamp, motion blur, bottom dark |
| 3 솔직한 마음 | '아이돌' 앞에선 멈칫 | **창밖 보며 생각에 잠긴 부모(실루엣)** | parent silhouette by window at dusk, pensive, muted grade, dark lower area |
| 4 가장 답답한 것 | 제3자의 냉정한 평가 | **노트북으로 아이 영상 돌려보는 부모** | parent reviewing a child's dance video on laptop at night, over-shoulder, dark |
| 5 관점 전환 | 등록이 아니라 진단 | **상담 테이블, 마주 앉은 두 사람(손/서류 위주)** | calm consultation table, two people across, hands and documents, soft light |
| 6 Keens 방식 | 현재 수준부터 솔직하게 | **트레이너가 태블릿 보며 피드백** | young trainer giving honest feedback with a tablet in a studio, warm light |
| 7 투명함 | 강사·커리큘럼·반 인원 공개 | **밝은 연습실, 소수 정예 클래스 전경** | bright mirrored studio, small class, a few students, transparent open space |
| 8 아이를 먼저 | 상품이 아니라 한 사람으로 | **연습 끝나고 웃는 아이 + 트레이너(따뜻)** | warm candid: smiling kid with trainer after practice, supportive mood |
| 9 무료 진단(체크리스트) | 강점/보완/이 길이 맞는지 | **어두운 무대 위 핀스팟(미니멀, 여백)** 또는 플랫 | dark stage spotlight, minimal, lots of negative space (텍스트 가독 우선) |
| 10 마무리 CTA | 등록보다 진단이 먼저 | **무대 앞에 선 아이의 뒷모습(희망)** | child seen from behind facing a softly lit stage, hopeful, lower area dark |

## 운영(합성까지)
A) **지금 바로 보기:** 위 장면들을 Higgsfield로 생성 → 위젯에서 다운로드 → `keens photo/scenes/`에 `card01.png`…`card10.png`로 저장. 그러면 내가 로컬 파일을 읽어 카드에 합성해 완성본을 보여줄 수 있음(샌드박스는 URL 다운로드 불가, 로컬 파일은 OK).
B) **무인 운영(맥미니/Paperclip):** Higgsfield 스킬로 카드별 장면 생성 → 다운로드 → `assets/bg_source/`(카드 순서대로) → `build_cards.js`가 카드별 `bg`로 배정. keens-cardnews + Higgsfield 스킬을 한 Routine에 묶으면 "장면 생성→합성→발행" 무인 연결.

## 톤 가이드
다큐멘터리·에디토리얼 질감, 차분한 무드 그레이딩(학부모 신뢰 톤), 과한 채도·HDR 금지. 아동은 일상/교육 맥락, 얼굴 강조 최소화. 텍스트 영역(주로 하단·좌하단)은 항상 어둡게.
