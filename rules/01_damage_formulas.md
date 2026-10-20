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
- 기본 헤드샷 배수: $3.0\times$ (업데이트 32 이후 표준)
- 치명타 헤드샷 특수 보너스: 헤드샷 상태에서 치명타 발생 시 치명타 피해량이 추가로 $3.0\times$ 증폭됨.
  $$\text{Headshot Crit Damage} = \text{Hit} \times 3.0 \times \left(1 + \text{CritTier} \times (\text{CritMult} \times 1.0 - 1)\right) \times \dots$$
  (실질적으로 $\text{CritMult}$가 2회 곱해지는 효과)

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
