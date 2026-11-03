# 02. Warframe Enemy Scaling & Status Effects (Post-Jade Shadows Spec)

워프레임의 적 스케일링 수식과 상태이상 메커니즘은 업데이트 36(제이드 섀도우, 2024년 6월 개편) 기준 방어력 상한(Cap) 및 속성 체계 개편을 반영한다.

---

## 1. 적 레벨 스케일링 공식 (Enemy Scaling)

기준 레벨($L_{\text{base}}$)과 현재 레벨($L$)에 따른 스케일링 계수 ($f$):
$$t = \frac{L - L_{\text{base}}}{L_{\text{current}} - L_{\text{base}}}$$

### 1.1. 체력 및 실드 스케일링
$$\text{Health Multiplier} = 1 + 0.015 \times (L - L_{\text{base}})^{2.0} \quad (\text{단, 고레벨 구간은 부드러운 다항식 적용})$$
$$\text{Shield Multiplier} = 1 + 0.02 \times (L - L_{\text{base}})^{1.75}$$

### 1.2. 방어력 개편 (Update 36: Armor Cap at 2,700)
- 과거 지수적 방어력 증가가 **최대 방어력 2,700**에서 캡(Cap)으로 고정됨.
- 적 방어력 피해 감소 공식 (wiki.warframe.com/w/Armor, 2,700 이하 선형):
  $$\text{DR}_{\text{Armor}} = 0.9 \times \frac{\text{Armor}}{2700}$$
- 방어력 2,700 도달 시 90%, 1,350이면 45%. 예외적으로 2,700을 넘으면 $\text{Armor}/(\text{Armor}+300)$. 이 식은 원래 Tenno용이다.
- 강철의 길(Steel Path) 보정: 적 기본 체력/방어력/실드 $+150\%$ (계수 $2.5\times$).

---

## 2. 상태이상 메커니즘 (Status Effects)

### 2.1. 바이러스 (Viral)
- 1스택: 체력에 가해지는 피해 $+100\%$
- 2~10스택: 스택당 $+25\%$ 추가
- 최대 10스택: 체력 피해 $+325\%$ 증폭 (배수 $4.25\times$)
- **특수 제약 (Acolyte / Demolyst)**: 최대 4스택($+175\%$, 배수 $2.75\times$)으로 고정 제한.

### 2.2. 절단 (Slash DoT - Bleed)
- 방어력(Armor DR)을 완전히 무시하는 **트루 데미지(True Damage)**.
- 틱당 피해 공식:
  $$\text{Tick Damage} = 0.35 \times B \times M_{\text{base}} \times (M_{\text{faction}})^2 \times CM_{\text{avg}} \times M_{\text{body\_mod}}$$
- 지속 시간: 6초간 총 6회 틱 (기본 1초 간격).

### 2.3. 화염 (Heat DoT - Ignite)
- 첫 번째 틱 적중 시 적 방어력 $50\%$ 즉시 삭감 (지속시간 내 유지).
- 틱당 피해 공식:
  $$\text{Tick Damage} = 0.5 \times B \times M_{\text{base}} \times (1 + \text{HeatMod}) \times (M_{\text{faction}})^2 \times CM_{\text{avg}}$$
- 모든 화염 프로크는 단일 인스턴스로 중첩되며 지속 시간이 리셋됨 (무한 누적 가능).

### 2.4. 부식 (Corrosive)
- 1스택: 적 방어력 $-26\%$
- 2~10스택: 스택당 $-6\%$ 추가 삭감
- 기본 10스택: 방어력 $-80\%$ 삭감
- **에메랄드 집정관 파편(Emerald Archon Shard) 보정**:
  - 파편 1개당 부식 최대 스택 $+2$ 또는 $+3$ (타우포지드).
  - 2개 장착 시 최대 14스택 도달 $\rightarrow$ **방어력 100% 완전 영구 삭감** 달성.

### 2.5. 자성 (Magnetic)
- 실드 및 **오버가드(Overguard)** 대상 피해 증폭:
  - 1스택 $+100\%$, 추가 스택당 $+25\%$, 최대 10스택 $+325\%$ 피해 증폭.
  - 오버가드 파괴 시 주변에 대상 최대 실드/오버가드 비례 전기 폭발 피해 방출.

### 2.6. 폭발 (Blast - Update 36 리워크)
- 대상에게 타격 시 1스택마다 폭발 타이머 작동 (10스택 도달 시 또는 6초 후 폭발).
- 폭발 피해: 누적된 피해의 $100\%$를 반경 5m 내 광역 피해로 방출.
