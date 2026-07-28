# MyVISSIM — 대전 도시철도 2호선 트램 우선신호 연구

이 저장소는 **자체 구현 미시교통 시뮬레이션 엔진(MyVISSIM)** 과 NVIDIA Isaac Sim 연동 계층이다.
상용 PTV VISSIM이 아니라 Wiedemann 99 계열 구성요소를 연구 목적으로 재구현한 독립 코드다.
현재 이 코드로 **KCI 논문 2편**을 작성 중이며, 남은 작업은 대부분 "시뮬레이션 재실행 + 결과 반영"이다.

---

## 1. 지금 해야 할 일 (우선순위 순)

### T1. Table 6 고정식 데이터 복구 — 최우선
논문 A의 Table 6 기준행(승용차 37.24±0.29, 버스 30.76±0.61) 데이터가 **디스크에서 소실**되었다.
원인은 아래 §3의 "tag 덮어쓰기 함정". 재실행이 유일한 방법이다.

```bash
python3 tools/run_experiment.py --scenario daejeon --seeds 5 --out out_csv_fixed_late
```
플래그를 주지 않으면 고정식이다. `--out`을 기존과 다르게 주는 것이 핵심.

### T2. 시드 46 발산 재현 여부 확인 — 최우선
```bash
python3 tools/run_experiment.py --scenario daejeon --actuated-all --seeds 5 --out out_csv_act_late
```
확인할 것: `out_csv_act_late/vehicles_daejeon_s46.csv` 에서 `origin=road_loopA_r0` 인 승용차의
완주 대수와 `travel_s` 대 `depart_s` 회귀 기울기. 기울기가 +20 s/1000s 를 넘으면 발산이 재현된 것이다.
정상이면 논문 A의 Table 5를 이 실행 결과로 교체한다.

### T3. 시드 확대 (여유가 되면)
`--seeds 7` 로 재실행. n=5는 Wilcoxon 양측 최소 달성 p가 0.0625여서 비모수검정으로
유의성 주장이 **수학적으로 불가능**하다. n=7이면 0.0156.

### T4. E7 실험 — 논문 B의 관건
`isaac/run_isaac_demo.py` 에 패치 3건을 적용한 뒤 9~15런 실행.
상세는 저장소에 함께 둔 `E7_실험계획.md` 참조. 요점만:
- **패치 ①** `--seed` 인자 추가. 현재 `main()` 의 daejeon 분기에서 `build()` 에 seed가 전달되지 않는다.
  `scenarios/daejeon_tram.build()` 가 seed 인자를 받는지 먼저 확인할 것.
- **패치 ②** 프레임 단위 지표 CSV 로깅 (`E7_LOG` 환경변수). 현재 콘솔 print만 있다.
- **패치 ③** 정거장 정지위치를 json으로 기록 (정위치 정차 오차 산출용).
그 뒤 `bash run_e7.sh` → `python3 e7_metrics.py --dir ~/e7_out --out e7_results.csv`

### T5. Δt 수렴성 실험 (논문 B, 저비용·고효과)
포화 방출 차두시간을 Δt = 0.1 / 0.05 / 1/60 / 0.01 s 에서 측정해 곡선으로 제시.
현재는 0.1 s(1.96 s)와 1/60 s(1.91 s) 2점 비교뿐이라 "수렴성 확인"으로 격상하면 방어력이 크게 오른다.
`tests/run_tests.py` 의 `test_saturation_headway_plausible()` 를 파라미터화하면 된다.

---

## 2. 실행 방법

### 교통 시뮬레이션 (논문 A)
```bash
python3 tools/run_experiment.py --scenario daejeon [플래그] --seeds N --out <디렉터리>
```
| 신호 운영전략 | 플래그 |
|---|---|
| 고정식 | (없음) |
| 감응식 (실교통 구간만) | `--actuated` |
| 전 교차로 감응식 | `--actuated-all` |
| 연동 감응식 | `--actuated-all --coordination` |
| 보행자 감응 | `--ped-actuation` / `--ped-vph 60` |

기타: `--warmup`, `--duration`(기본 3600), `--road-vph`(기본 1800), `--jobs`(기본 4)
출력: `<out>/experiment_summary.csv`, `vehicles_<tag>_s<seed>.csv`, `traveltimes_*`, `queues_*`

### Isaac Sim 공동 시뮬레이션 (논문 B)
```bash
python3 isaac/run_isaac_demo.py --scenario daejeon \
  --driver alpamayo --ego-vehicle tram \
  [--actuated] [--coordination] \
  --replan 1.0 --smoke <frames> --headless \
  --alpamayo-host <user@a100서버>
```
Alpamayo-R1(10B) 추론은 원격 A100에서 수행되며 SSH 기반 JSONL 스트림으로 연결된다.
렌더러(RTX 4090)와 10B 모델을 한 GPU에 함께 올릴 수 없기 때문이다.

---

## 3. 반드시 알아야 할 함정 3가지

### ⚠ 함정 1 — tag가 신호전략을 반영하지 않는다 (파일 덮어쓰기)
`tools/run_experiment.py` 의 tag 생성 로직:
```python
mode = "actuated-all" if args.actuated_all else ("actuated" if args.actuated else "fixed")
if args.coordination:  mode += "+coord";  args.tag += "_coord"    # ← tag 변경
# --actuated / --actuated-all 은 mode만 바꾸고 tag는 "daejeon" 그대로
```
즉 **고정식과 감응식이 같은 `daejeon` tag를 쓴다.** 같은 `--out` 에 순서대로 실행하면
앞선 결과가 조용히 사라진다. Table 6 고정식 데이터가 이렇게 소실됐다.
→ **실행마다 `--out` 을 다르게 주거나, tag 생성에 mode를 반영하도록 고칠 것.**

### ⚠ 함정 2 — 표준편차가 ddof=0 (모표준편차)
`run_experiment.py` 말미:
```python
sd = (sum((x - m) ** 2 for x in vals) / len(vals)) ** 0.5
```
n=5 표본에서는 표본표준편차(ddof=1)가 통례다. 논문에 실린 ± 값이 전부 모표준편차이므로
심사에서 지적될 수 있다. 통계 재분석은 모두 ddof=1 기준으로 되어 있다.

### ⚠ 함정 3 — Isaac 데모에 seed 인자가 없다
`isaac/run_isaac_demo.py` 212행의 `build(seed=42)` 는 `corridor` 시나리오 전용이다.
`daejeon` 분기의 `build()` 호출에는 seed가 전달되지 않는다. E7은 시드 비교 실험이므로
이 패치 없이는 실험 자체가 성립하지 않는다.

---

## 4. 이미 규명된 사실 (다시 조사하지 말 것)

- **포화 방출 차두시간**: Δt=0.1 s에서 1.96 s/대 → **1,837 ≈ 1,840대/시/차로**.
  원고에 있던 "약 1,880대/시"는 오류다. 3600/1.91(60 Hz 측정값)=1,885이므로
  Ⅴ장 값이 Ⅱ장에 잘못 옮겨진 것. 이미 원고에서 1,840으로 수정 완료.
- **시드 46 발산**: `out_csv/actuated_all` 의 시드 46에서 역방향 본선(`origin=road_loopA_r0`)이
  과포화 발산했다. 통행시간이 112.9→341.6→415.6→510.4 s로 단조 증가하고 5,300 s 이후 완주 0.
  회귀 기울기 +159 s/1000s (r=0.453, p=7e-65) vs 정상 시드 −1.6~+0.3.
  **같은 시드의 고정식은 정상**이고 **트램도 정상**(28.42 km/h). 25건 전수 스크리닝 중 이 1건뿐이며,
  **후기 코드(`out_csv_coord/daejeon`)의 시드 46은 정상**이므로 코드 수정으로 이미 해소된 것으로 보인다.
  → 이 발산 때문에 Table 5의 "승용차 −5.7%"가 paired t-test p=0.063으로 **비유의**다.
    시드 46 제외 시 −3.5%, p=0.004.
- **데이터 출처 매핑**:
  - Table 5 고정식 = `out_csv/fixed` (daejeon) / 전교차로감응식 = `out_csv/actuated_all` (daejeon)
  - Table 6 자유감응식 = `out_csv_coord/summary_act.csv` (= daejeon tag)
  - Table 6 연동+부분우선 = `out_csv_coord` 의 `daejeon_coord`
  - Table 7 = `out_csv_coord` 의 `daejeon_ped`, `daejeon_coord_ped`, `*_pv60`, `*_pv240`
  - **Table 6 고정식 = 없음** (§1 T1)
- **정시성 산출 불가**: 현재 로그에 정거장 통과 시각이 없다. 정시성 지표를 논문에 넣으려면
  엔진의 정거장 정차 처리부에서 `(station_id, tram_id, arrival_time)` 을 CSV로 남겨야 한다.

---

## 5. 논문 현황

| | 논문 A | 논문 B |
|---|---|---|
| 제목 | 미시교통시뮬레이션 기반 노면전차 우선신호 감응식 제어의 효과 분석: 대전 도시철도 2호선 사례 | 권한 분리 기반 교통–3차원 공동 시뮬레이션 설계 패턴과 궤도계 차량으로의 적용 |
| 투고처 | 한국ITS학회 논문지 (연 6회, 2·4·6·8·10·12월 말) | 한국시뮬레이션학회 논문지 (계간) |
| 목표 | 2026-10-31 발간호 → 8월 초·중순 투고 | E7 완료 후 |
| 완성도 | 약 96% | 약 45% |
| 파일 | `paper_A_v3_ITS.docx` | `paper_B_초안_v2.docx` |
| 규정 | 분량 6쪽 기준(초과 시 추가게재료), 국문초록 600자, 영문 300단어, 주제어 5개, 심사 초심 3주 | 최근 호 논문 8~14쪽 |
| 잔여 | T1·T2 결과 반영, 분량 방침 결정, 기관 이메일 교체 | T4(E7), T5, 그림 4점 신규 작성 |

**논문 B의 프레이밍을 절대 바꾸지 말 것.** 한국시뮬레이션학회 논문지는 최근 2개 호 17편 중
교통·자율주행 논문이 0편이고 DEVS·국방 M&S·제조 시뮬레이션이 주류다. 따라서 이 논문은
"트램 논문"이 아니라 **"공동 시뮬레이션 방법론 논문"** 으로 읽혀야 한다.
기여는 ⑴ 권한 분리 설계 패턴 ⑵ 시간해상도 불변성 검증 ⑶ 궤도계 차량용 레일 거버너이고,
트램은 적용 사례로 배치되어 있다.

참고문헌 26건은 전건 검증되어 `참고문헌_검증표.xlsx` 에 근거 URL과 함께 정리되어 있다.
**새 참고문헌을 추가할 때는 반드시 실제 페이지에서 확인하고, 확인 못 한 필드는 추측하지 말 것.**

---

## 6. 작업 규칙

- 시뮬레이션 재실행 시 **`--out` 을 항상 새 디렉터리로** 지정한다 (§3 함정 1).
- 통계는 **ddof=1**(표본표준편차)로 계산한다.
- 논문 수치를 고칠 때는 **본문·초록·결론·표 셀을 모두** 확인한다. 과거에 표 셀 하나가 누락된 적이 있다.
- 결과를 논문에 반영하기 전에 **시드별 원자료로 paired t-test** 를 돌려 유의성을 확인한다.
- 장시간 실행은 tmux 안에서 한다.
