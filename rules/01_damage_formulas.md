# 01. Warframe Damage Formulas & Buckets

워프레임의 총 데미지 계산은 서로 다른 **곱연산 버킷(Multiplicative Buckets)**과 버킷 내부의 **합연산(Additive) 요소**들로 구성된다.

---

## 1. 데미지 버킷 분류 (Damage Buckets)

### Bucket 1: Base Damage ($B$)
무기의 기본 스펙 및 인카논 진화에 의해 제공되는 기초 피해량.
$$B = \text{Base Weapon Damage} + \text{Incarnon Perk Base Damage}$$

### Bucket 2: Additive Base Damage Multiplier ($M_{\text{base}}$)
서레이션(Serration), 프라이머리 머시리스(Primary Merciless), 갈바니즈드 앱티튜드(GunCO) 등의 합연산 버킷.
$$M_{\text{base}} = 1 + \sum \text{Base Damage Mods (Serration + Merciless + GunCO)}$$
> **주의 (GunCO 예외)**: 대부분의 직격 투사체/히트스캔 무기에는 합연산 적용되지만, 일부 폭발 범위 피해나 특수 무기는 적용되지 않거나 독자적인 곱연산 버그/특성을 가짐(`is_multiplicative_gunco` 플래그 관리 필요).

### Bucket 3: Elemental Damage Multiplier ($M_{\text{elem}}$)
모드로 추가된 모든 속성(단일 속성 90%, 60/60 모드, 리벤 속성 등)의 합산 비율.
$$M_{\text{elem}} = 1 + \sum \text{Elemental Mod Percentages}$$
- 복합 속성(예: 독 + 냉기 = 바이러스, 화염 + 전기 = 방사능) 결합 시 모드 슬롯 순서(좌상단 -> 우하단)를 엄격히 준수.

#### 속성 합성 순서 (wiki.warframe.com/w/Damage)
- 슬롯을 좌상단에서 우하단 순서로 읽어 기본 속성(화염·냉기·전기·독성)이 처음 나온 위치를 정하고, 그 순서대로 두 개씩 묶는다.
- 예: 1번 화염, 4번 냉기, 5번 독성이면 화염+냉기=폭발, 독성은 단독으로 남는다.
- 같은 속성을 다시 끼우면 첫 위치에 합쳐진다.
- 무기 고유 기본 속성과 베일런스 보너스는 맨 마지막에 놓이고, 남은 속성과 합성된다. 같은 속성의 모드가 있으면 그 모드 위치로 당겨진다. 고유 속성이 둘이면 HCET(화염>냉기>전기>독성) 순서다.
- 무기 고유 복합 속성은 그대로 유지되고, 모드 속성은 그와 별개로 합성된다.
- 리벤은 마지막에 표기된 속성이 우선한다.
- 조합: 화염+냉기=폭발, 화염+전기=방사능, 화염+독성=가스, 냉기+전기=자성, 냉기+독성=바이러스, 전기+독성=부식.
- 아스널 타입별 줄은 발사체 1발 기준이고, 총계만 멀티샷을 포함한다.

### Bucket 4: Faction Damage Multiplier ($M_{\text{faction}}$)
베인(Bane), 익스펠(Expel), 클린스(Cleanse), 스마이트(Smite) 모드 및 라이노 로어(Rhino Roar) 버프.
$$M_{\text{faction}} = 1 + \text{Faction Mod} + \text{Roar Buff}$$
- **직격 피해 시**: $M_{\text{faction}}$ 단일 적용
- **상태이상 지속 피해(DoT: Slash, Heat, Toxin, Gas, Electric) 시**:
  $$\text{DoT Tick} \propto (M_{\text{faction}})^2 \quad (\text{Double Dipping})$$

### Bucket 5: Multishot ($MS$)
1회 격발당 발사되는 탄환 수.
- 탄환 수 $N = \lfloor MS \rfloor$, 확률 $(MS - \lfloor MS \rfloor)$ 로 $N + 1$ 발 발사.
- 평균 기댓값 연산 시에는 $MS$ 자체를 선형 곱연산으로 처리.

### Bucket 6: Body Part Multiplier ($M_{\text{body}}$)
- 기본 약점 배수: 대부분 $3.0\times$ (머머·테크로트 등 일부 약 $1.5\times$)
- 약점 피해 보너스(WP)와 헤드샷 보너스(HS, 데드헤드 등):
  $$M_{\text{body}} = (\text{Base} + 1.5 \times \sum \text{WP}) \times (1 + \sum \text{HS})$$
  비헤드샷 약점은 $\text{Base} + \sum \text{WP}$.
- 치명타 헤드샷은 치명타 배수에 $2\times$가 적용된다.

### 조건부 버프와 절대값 보너스
- 아케인 머시리스·데드헤드·덱스터리티, 갈바나이즈드 처치 스택 피해는 $M_{\text{base}}$에 합연산한다. 아스널 패널 값에는 전투 스택이 빠져 있으므로 풀스택 계산에서 별도로 더한다.
- 물리 모드는 무기의 해당 물리 비율만큼 $M_{\text{elem}}$ 괄호에 들어간다: $\text{Dist}_i \times \text{Bonus}_i$.
- 상태이상 피해(엘리멘탈리스트), 지면 강타 피해(사이즈믹 웨이브), 마무리 일격 피해는 직접 피해 $M_{\text{base}}$에 넣지 않는다.
- 치명타: $CC = \text{Base} \times (1 + \text{Relative} + \text{BloodRush} \times (\text{Combo} - 1)) + \text{Flat}$, $CM = \text{Base} \times (1 + \text{Relative}) + \text{Flat}$.
- 콘디션 오버로드: 상태이상 종류당 $M_{\text{base}}$에 합연산 ($+80\% \times n$).
- 아스널 총계에는 멀티샷이 포함되고 팩션·치명타는 빠져 있다.

---

## 2. 치명타 티어 수식 (Critical Tiers)

치명타 확률 $CC$에 따른 티어 $T = \lfloor CC \rfloor$:
- $CC < 1.0$: 흰색 타격 ($1 - CC$), 노란색 치명타 ($CC$)
- $1.0 \le CC < 2.0$: 노란색 치명타 ($2 - CC$), 주황색 치명타 ($CC - 1$)
- $2.0 \le CC < 3.0$: 주황색 치명타 ($3 - CC$), 빨간색 치명타 ($CC - 2$)
- $CC \ge 3.0$: 빨간색 치명타 티어 ($T$)

### 치명타 배수 ($CM_{\text{effective}}$)
- **최소 보장 배수 (`Min Roll`)**:
  $$CM_{\text{min}} = 1 + \lfloor CC \rfloor \times (CM - 1)$$
- **평균 기대 배수 (`Expected Value`)**:
  $$CM_{\text{avg}} = 1 + CC \times (CM - 1)$$

---

## 3. 최종 기대 직격 타격 데미지 공식

$$\text{Expected Hit} = B \times M_{\text{base}} \times M_{\text{elem}} \times M_{\text{faction}} \times CM_{\text{avg}} \times M_{\text{body}}$$
$$\text{Average Burst DPS} = \text{Expected Hit} \times MS \times \text{FireRate}$$
$$\text{Sustained DPS} = \text{Burst DPS} \times \frac{\text{MagazineSize}}{\text{MagazineSize} + (\text{FireRate} \times \text{ReloadTime})}$$
