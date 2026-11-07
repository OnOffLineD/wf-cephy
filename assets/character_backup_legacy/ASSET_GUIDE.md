# 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)

WF-Companion의 데스크톱 펫은 **다중 레이어 2D 합성 렌더러 (`LayeredPetRenderer`)**를 통해 살아 숨쉬는 애니메이션(실시간 립싱크 뻐끔거림, 눈 깜빡임, 감정별 표정, 상하 부유 바운스)을 실시간으로 렌더링합니다.

나노바나나(NanoBanana), 미드저니, 포토샵 등으로 새로운 의인화 오디스 일러스트를 제작하여 아래 폴더에 넣기만 하면 **코드 수정 없이 즉시 반영**됩니다.

---

## 1. 📐 에셋 기본 규격

- **권장 캔버스 크기**: `256 x 256` px (정사각형)
- **포맷**: 투명 배경 PNG (`RGBA`, 알파 채널 필수)
- **위치 정렬 기준**: 모든 레이어는 **동일한 256x256 캔버스 중심**에 위치해야 합니다. (눈, 입, 손 등을 따로 오려낼 때 위치를 옮기지 말고, 원래 얼굴/몸 위치 그대로 투명 캔버스에 저장)

---

## 2. 📂 디렉터리 및 파일 명명 규칙

`assets/character/layers/` 아래 6개 폴더에 나누어 저장합니다:

```text
assets/character/layers/
├── body/                  # [1단계] 기본 몸체 및 머리 형태
│   ├── body_idle.png      # 기본 유휴 몸체 (필수 기본값)
│   ├── body_glitch.png    # 글리치 붉은 노이즈 몸체 (선택)
│   └── body_thinking.png  # 생각하는 포즈 몸체 (선택)
│
├── eyes/                  # [2단계] 눈 표정
│   ├── eye_idle.png       # 기본 뜬 눈 (필수)
│   ├── eye_blink.png      # 눈 감은 상태 (눈 깜빡임 애니메이션용 필수)
│   ├── eye_happy.png      # 활짝 웃는 반달 눈 (^ ^)
│   ├── eye_glitch.png     # 붉은 안광 / 날카로운 눈
│   ├── eye_worried.png    # 걱정스러운 / 처진 눈
│   └── eye_tactical.png   # 냉철한 전술 스캐너 눈
│
├── brows/                 # [3단계] 눈썹 (복합 감정 조합용)
│   ├── brow_idle.png      # 평온한 기본 눈썹
│   ├── brow_angry.png     # 화난 / 찌푸린 눈썹
│   └── brow_worried.png   # 억울한 / 팔자 눈썹
│
├── mouth/                 # [4단계] 입모양 (실시간 립싱크용)
│   ├── mouth_idle.png        # 평소 다문 입
│   ├── mouth_open_small.png  # 발화 립싱크 1단계 (작게 벌린 입)
│   ├── mouth_open_big.png    # 발화 립싱크 2단계 (크게 벌린 입)
│   └── mouth_smile.png       # 미소 지은 입
│
├── hands/                 # [5단계] 손 동작
│   ├── hand_idle.png      # 기본 양손
│   ├── hand_happy.png     # 만세 / 박수 치는 손
│   └── hand_tactical.png  # 경례 / 지시하는 손
│
└── vfx/                   # [6단계] 보조 감정 효과 (이펙트)
    ├── vfx_blush.png      # 발그레한 핑크빛 홍조
    ├── vfx_sweat.png      # 삐질 당황한 푸른 땀방울
    └── vfx_sparks.png     # 찌릿한 글리치 전기 스파크
```

---

## 3. 🍌 나노바나나 (NanoBanana) 생성 프롬프트 템플릿 추천

귀여운 오디스 의인화 캐릭터를 생성할 때 활용할 수 있는 프롬프트 예시:

> **베이스 캐릭터 생성 프롬프트 (Base Prompt)**:
> `masterpiece, best quality, cute chibi cephalon ordis from warframe, humanized ordis, cute white and cyan mechanical armor, floating holographic diamond on forehead, glowing cyan eyes, expressive face, clean white background, transparent background, 2d game sprite, high resolution`

> **파츠 분리 팁**:
> 1. 기본 일러스트 1장을 마음에 들게 생성한 뒤,
> 2. `Inpainting`(부분 수정) 또는 포토샵 레이어 분리 도구를 사용하여 눈, 입, 손 부위만 투명하게 지우거나 따로 저장하면 가장 자연스럽게 위치가 맞습니다!

---

## 4. 🛡️ 자동 폴백 (안전망)
- 만약 특정 파츠 파일이 없더라도 에러가 발생하지 않으며, `body_idle.png` $\rightarrow$ 상위 폴더 `idle.png` $\rightarrow$ 내장 벡터 렌더러 순서로 자동 대체됩니다.
