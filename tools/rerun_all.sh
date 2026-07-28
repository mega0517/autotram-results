#!/usr/bin/env bash
# rerun_all.sh — 논문 A Table 5·6·7 전체를 현재 코드 상태로 재실행 (시드 7개)
#
# 실행 위치: ub24 의 ~/MyVISSIM
# 사용법:    bash rerun_all.sh
# 소요:      9개 실행 × 7시드. --jobs 28 기준 실행당 수 분.
#
# ⚠ 중요: tag 는 --actuated / --actuated-all 을 반영하지 않는다(고정식과 감응식이 같은
#         "daejeon" tag 를 쓴다). 그래서 실행마다 --out 을 다르게 준다. 이 규칙을 어기면
#         이전 결과가 조용히 덮어써진다 — Table 6 고정식 데이터를 그렇게 잃었다.

set -eu
SEEDS="${SEEDS:-7}"          # 42..48
JOBS="${JOBS:-28}"
ROOT="${ROOT:-$HOME/v4_out}"
RUN="python3 tools/run_experiment.py --scenario daejeon --seeds $SEEDS --jobs $JOBS"

mkdir -p "$ROOT"
cd "$HOME/MyVISSIM"

echo "=========================================================="
echo " 논문 A 재실행 — 시드 $SEEDS 개, jobs $JOBS, 출력 $ROOT"
echo "=========================================================="

step () {  # step <이름> <추가플래그...>
  local name="$1"; shift
  local out="$ROOT/$name"
  if [ -d "$out" ] && [ -f "$out/experiment_summary.csv" ]; then
    echo "[건너뜀] $name (이미 있음)"; return
  fi
  echo ""
  echo "---------- [$name] $* ----------"
  $RUN "$@" --out "$out"
}

# Table 5 · Table 6 기준행
step fixed                                                          # 고정식 (플래그 없음)
step actuated_all   --actuated-all                                  # 자유 감응식(전 교차로)
step coord          --actuated-all --coordination                   # 연동 + 부분 우선

# Table 7 — 보행자 감응 (자유 감응식 계열)
step act_ped        --actuated-all --ped-actuation                  # 왕복 집단(상시)
step act_ped_pv60   --actuated-all --ped-actuation --ped-vph 60
step act_ped_pv240  --actuated-all --ped-actuation --ped-vph 240

# Table 7 — 보행자 감응 (연동 + 부분 우선 계열)
step coord_ped      --actuated-all --coordination --ped-actuation
step coord_ped_pv60 --actuated-all --coordination --ped-actuation --ped-vph 60
step coord_ped_pv240 --actuated-all --coordination --ped-actuation --ped-vph 240

echo ""
echo "=========================================================="
echo " 완료. 결과 저장소로 옮기고 push:"
echo ""
echo "   cd ~/autotram-results"
echo "   mkdir -p results/v4"
echo "   for d in $ROOT/*/; do n=\$(basename \"\$d\"); mkdir -p results/v4/\$n; cp \$d/*.csv results/v4/\$n/; done"
echo "   git add -A && git commit -m 'v4: full rerun, 7 seeds, 9 configs' && git push"
echo "=========================================================="
