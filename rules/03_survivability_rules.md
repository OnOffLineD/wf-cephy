# 03. Warframe Survivability & Shield Gating Rules

워프레임의 생존력은 단순 수치(Health/Armor)와 메커니즘(피해 감소 DR, 실드 게이팅, 무적)의 결합으로 결정된다.

---

## 1. 실효 체력 (Effective Health Points - EHP)

### 1.1. 다중 피해 감소 중첩 공식
$$\text{Total EHP} = \frac{\text{Health}}{(1 - \text{DR}_{\text{Armor}}) \times (1 - \text{DR}_{\text{Ability}}) \times (1 - \text{DR}_{\text{Adaptation}})}$$

- **방어력 피해 감소 ($\text{DR}_{\text{Armor}}$)**:
  $$\text{DR}_{\text{Armor}} = \frac{\text{Armor}}{\text{Armor} + 300}$$
- **어댑테이션 ($\text{DR}_{\text{Adaptation}}$)**:
  피해 속성별 최대 90% 감쇄 (최대 중첩 시 $0.1$ 배수).
- **어빌리티 피해 감소 ($\text{DR}_{\text{Ability}}$)**:
  - **Nova (Null Star)**: 활성 입자 1개당 피해 감소 5% (최대 90% 캡 $\rightarrow$ 지속시간 300% 이상에서 18개 입자 유지 시 달성).
  - **Mesa (Shatter Shield)**: 사격 공격 95% 감쇄 (위력 119% 이상 시 최대).
  - **Mirage (Eclipse)**: 최대 75% 피해 감쇄.
  - **Gara (Splinter Storm)**: 최대 90% 피해 감쇄 (위력 129% 이상).
  - **Citrine (Preserving Shell)**: 적 처치/어시스트로 최대 90% DR 유지.

---

## 2. 적 공격력 스케일링과 단순 체력 모딩의 한계

### 2.1. 적 공격력 스케일링 수식
$$\text{Enemy Damage} = \text{Base Damage} \times \left(1 + (\text{Current Level} - \text{Base Level})^{1.55} \times 0.015\right)$$

- **강철의 길 Lv.200 헤비거너**: 1발당 유효 피해량 약 $1,500 \sim 3,500$.
- **Lv.1000+**: 1발당 수십만 데미지로 증가하여 아무리 체력과 방어력을 높여도 1~2발 내 즉사.
- **Lv.9999 (레벨캡)**: 단일 타격 데미지가 $10^7$을 초과하므로 EHP 방식의 생존은 수학적으로 불가능하며, **실드 게이팅(Shield Gating)** 또는 **피해 무효화(Mesmer Skin, 무적)**만이 유효함.

---

## 3. 실드 게이팅 메커니즘 (Post-Abyss of Dagath Spec)

### 3.1. 무적 시간 스케일링
실드가 소진될 때, 소진 직전의 실드량($S$)에 비례하여 무적 시간이 선형적으로 부여됨:
$$\text{Invulnerability Duration (s)} = \min\left(2.5, \; 0.33 + \frac{S}{1150} \times (2.5 - 0.33)\right)$$
- 최소 보장 무적 시간: $0.33$초
- 최대 무적 시간 ($S \ge 1,150$): $2.5$초

### 3.2. 카탈라이징 실즈 (Catalyzing Shields) 사이클
- 최대 실드를 $80\%$ 감소시키는 대신, 최대 실드가 낮아져도 **실드가 100% 충전되기만 하면 항상 $1.33$초의 고정 무적 시간**을 보장함.
- **순환 메커니즘**:
  1. 실드가 깨져 1.33초 무적 발동.
  2. 무적 시간 동안 브리프 레스피트(Brief Respite) 또는 어거(Augur) 세트 모드가 장착된 상태에서 에너지를 소비하여 어빌리티 시전.
  3. 시전 즉시 소모 에너지의 $150\% \sim 250\%$가 실드로 전환되어 최대 실드를 즉시 100% 재충전.
  4. 무적 지속이 끝나기 전에 실드 게이팅 조건이 즉시 리셋되어 무한 생존 사이클 완성.
