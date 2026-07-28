# autotram-results

대전 도시철도 2호선 트램 우선신호 연구 — 결과·원고·도구 저장소.
엔진 코드는 별도 저장소(`~/MyVISSIM`)에 있으며, 여기에는 산출물만 둔다.

## 구조

```
results/    시뮬레이션 결과 CSV
  fixed_late/    고정식 5시드 (2026-07-28 재실행)
  act_late/      전 교차로 감응식 5시드 (2026-07-28 재실행)
paper/      원고
tools/      실행·분석 스크립트
analysis/   분석표 (xlsx)
docs/       프로젝트 컨텍스트
```

## paper/

| 파일 | 내용 |
|---|---|
| `paper_A_v3_ITS.docx` | 논문 A — 한국ITS학회 논문지 투고본 (16쪽, 표 7·그림 6·참고문헌 26) |
| `paper_B_초안_v2.docx` | 논문 B — 한국시뮬레이션학회 논문지 초안 (6쪽) |

⚠ 논문 A의 Ⅳ장 수치는 구버전입니다. 2026-07-28 재실행 결과와 대조하면
표정속도 +5.9%→+6.7%, 신호정지 85%→88.9%, 승용차 −5.7%→−8.2%로 전부 달라졌습니다.
Table 4·5·6·7 전면 재작성이 필요합니다.

## tools/

| 파일 | 용도 |
|---|---|
| `rerun_all.sh` | 논문 A Table 5·6·7 전체 재실행 (9개 실행 × 7시드) |
| `make_tables.py` | 결과 → 논문 표 자동 생성 + 통계검정 + 발산 점검 |
| `seed_stats.py` | 범용 시드 짝 비교 (paired t-test / Wilcoxon / Cohen's d / 정시성) |

```bash
cd ~/MyVISSIM && bash tools/rerun_all.sh
python3 tools/make_tables.py --dir results/v4 --out tables_v4
```

## analysis/

| 파일 | 내용 |
|---|---|
| `트램논문_갭분석표.xlsx` | 조치 항목 33건 · 5시트 |
| `통계검정_결과.xlsx` | 통계검정·발산진단·출처추적 · 7시트 |
| `참고문헌_검증표.xlsx` | 참고문헌 26건 검증 내역 + 근거 URL |

## docs/CLAUDE.md

Claude Code용 프로젝트 컨텍스트. `~/MyVISSIM/CLAUDE.md` 로 복사해 사용.
남은 과제 T1~T5, ⚠함정 3가지, 이미 규명된 사실이 정리되어 있다.

## ⚠ 알려진 함정

1. **tag 덮어쓰기** — `tools/run_experiment.py`의 tag는 `--actuated` 계열을 반영하지 않는다.
   같은 `--out`에 재실행하면 이전 결과가 조용히 사라진다. 실행마다 `--out`을 다르게 줄 것.
2. **ddof=0** — `run_experiment.py`의 표준편차는 모표준편차다. n=5 표본에서는 ddof=1이 통례.
3. **Isaac 데모에 seed 인자 없음** — `isaac/run_isaac_demo.py`의 daejeon 분기는 seed를 받지 않는다.
