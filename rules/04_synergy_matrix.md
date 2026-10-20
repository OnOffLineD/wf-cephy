# 04. Warframe External Synergy & Level-Cap Matrix

워프레임의 고점 및 레벨캡(Lv.9999) 클리어는 무기 8슬롯 모딩을 넘어선 **외부 시너지 레이어(External Synergy Layers)**의 결합으로 완성된다.

---

## 1. 헬민스 주입 어빌리티 (Helminth Subsumed Abilities)

### 1.1. 방어력/실드 무력화 (Armor Strip)
- **Pillage (Hildryn)**: 위력 328%(부식 투영 오라 채용 시 268%)에서 1회 시전으로 적 방어력 및 실드 100% 영구 제거 + 아군 실드/오버실드 대량 충전.
- **Tharros Strike (Styanax)**: 위력 200%에서 전방 좁은 부채꼴 범위 방어력 및 실드 100% 영구 제거 + 체력 회복.
- **Terrify (Nekros)**: 위력 167%에서 적 방어력 100% 영구 삭감 + CC(공포).

### 1.2. 화력 증폭 버프
- **Rhino Roar**: 최종 데미지에 곱연산되는 Faction 버킷($M_{\text{faction}}$). 모든 DoT 틱 데미지가 제곱($\text{Roar}^2$)으로 증폭됨.
- **Mirage Eclipse**: 무기 기본 피해량과 곱연산되는 고유 배수.
- **Grendel Nourish**: 모든 공격에 바이러스 속성 추가 + 피격 시 바이러스 광역 폭발 + 에너지 획득량 2~3배 증폭.
- **Xaku Xata's Whisper**: 보이드(Void) 속성 탄환 추가 생성 (투사체 무기 적중 횟수 재증폭 및 상태이상 추가).

---

## 2. 합성 집정관 파편 (Archon Shards Synergy)

- **Emerald (부식 스택 상한)**:
  - 일반 +2스택, 타우포지드 +3스택.
  - 2개 장착 시 부식 14스택 도달 $\rightarrow$ 헬민스 없이 부식 무기만으로 적 방어력 100% 영구 삭감.
- **Violet (보라색 파편)**:
  - 근접 치명타 피해 +37.5% (최대 에너지 500 초과 시 +75%, 타우포지드 +112.5%).
  - 또는 오브 획득 시 헬스/에너지 균형 회복 $\rightarrow$ 워프레임 `Equilibrium` 모드 슬롯을 대체 압축.
- **Topaz (황옥 파편)**:
  - 화염 상태이상 처치 시 보조무기 치명타 확률 영구 증가 (최대 +75%, 타우포지드 +112.5%).
- **Crimson (적색 파편)**:
  - 어빌리티 위력 +10%(타우포지드 +15%) 또는 주/보조무기 치명타 피해 +25%(타우포지드 +37.5%).

---

## 3. 동반자 프라이밍 & 갈바니즈드 GunCO 연계

### 3.1. 동반자 상태이상 프라이머 (Companion Primer)
- **Nautilus + Verglas**:
  - `Cordon`으로 30m 내 적을 1점으로 응집.
  - 고연사 상태이상 무기(`Verglas`, `Helstrum`)로 바이러스, 냉기, 방사능, 전기 등 4~5개 상태이상을 0.5초 내 사전 주입.
- **Hound (Synergized Proselytize + Akaten)**:
  - 자성, 방사능, 관통 등 다양한 복합 속성 강제 부여.
- **Panzer Vulpaphyla**:
  - 바이러스 포자를 전 맵에 지속 살포하여 상시 바이러스 10스택 유지.

### 3.2. 갈바니즈드 앱티튜드/샷/새비 (GunCO) 수학
$$\text{Damage Bonus} = +80\% \times (\text{적에게 부여된 유효 상태이상 종류 수})$$
- 동반자가 4개 상태이상 사전 프라이밍 + 무기 본체가 2개 상태이상 부여 $\rightarrow$ 총 6개 속성:
  $$\text{Bonus} = 6 \times 80\% = +480\% \text{ Base Damage}$$
- 서레이션(+165%) 모드 슬롯을 완전히 대체하여 치명타나 속성 모드로 압축 가능.

---

## 4. 포커스 학파 (Focus Schools)

- **Unairu**:
  - `Caustic Strike`: 100% 방어력 삭감 파동 방출.
  - `Poise`: 전이 후 40초간 완전 넉다운 면역 $\rightarrow$ 워프레임 `Primed Sure Footed` 슬롯 절약.
- **Madurai**:
  - `Void Strike`: 보이드 데미지 최대 +1000% 증폭.
  - `Sling Strength`: 2회 슬링 시 위력 +40% 일시 공급 (스냅샷 어빌리티 최적화).
- **Zenurik**:
  - `Wellspring`: 에너지 재생 초당 +5 및 어빌리티 위력 +20%.
- **Vazarin**:
  - `Protective Sling`: 5초간 무적 및 50% 체력 회복 $\rightarrow$ 레벨캡 비상 탈출기.
