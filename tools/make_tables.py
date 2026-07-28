#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_tables.py — 재실행 결과 → 논문 A Table 5·6·7 자동 생성 (통계검정 포함)

사용법:
    python3 make_tables.py --dir results/v4 --out tables_v4

입력: <dir>/<실행이름>/experiment_summary.csv
  필요한 실행 이름: fixed, actuated_all, coord,
                    act_ped, act_ped_pv60, act_ped_pv240,
                    coord_ped, coord_ped_pv60, coord_ped_pv240

출력:
  <out>.md   — 논문에 그대로 붙일 마크다운 표 + 본문 수치 문장
  <out>.csv  — 기계 판독용 전체 지표
"""
import argparse, math, os, sys
import numpy as np
import pandas as pd
from scipy import stats

METRICS = [
    ("tram_avg_kmh",      "트램 표정속도 (km/h)",     2, True),
    ("tram_avg_travel_s", "트램 순환시간 (s)",        0, False),
    ("tram_avg_stops",    "트램 정지횟수 (회/순환)",  1, False),
    ("car_avg_kmh",       "승용차 평균속도 (km/h)",   2, True),
    ("car_avg_stops",     "승용차 정지 (회)",         2, False),
    ("bus_avg_kmh",       "버스 평균속도 (km/h)",     2, True),
]
STATION_STOPS = 40.0   # 정거장 정차 횟수 (신호 정지 환산용)


def load(d, name):
    p = os.path.join(d, name, "experiment_summary.csv")
    if not os.path.exists(p):
        return None
    x = pd.read_csv(p)
    x = x[~x["seed"].isin(["mean", "std"])].copy()
    for c in x.columns:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    return x.sort_values("seed").reset_index(drop=True)


def paired(base, treat, key):
    """시드를 짝지어 검정. 공통 시드만 사용."""
    s = sorted(set(base["seed"]) & set(treat["seed"]))
    x = base.set_index("seed").loc[s, key].values.astype(float)
    y = treat.set_index("seed").loc[s, key].values.astype(float)
    d = y - x
    n = len(d)
    out = dict(n=n, base=x.mean(), base_sd=x.std(ddof=1),
               treat=y.mean(), treat_sd=y.std(ddof=1),
               diff=d.mean(), pct=100 * d.mean() / x.mean() if x.mean() else np.nan)
    if n < 2 or np.allclose(d, d[0]):
        out.update(p=np.nan, pw=np.nan, dz=np.nan, lo=np.nan, hi=np.nan)
        return out
    _, p = stats.ttest_rel(y, x)
    se = d.std(ddof=1) / math.sqrt(n)
    tc = stats.t.ppf(0.975, n - 1)
    try:
        _, pw = stats.wilcoxon(y, x, alternative="two-sided", method="exact")
    except Exception:
        pw = np.nan
    out.update(p=p, pw=pw, dz=d.mean() / d.std(ddof=1),
               lo=d.mean() - tc * se, hi=d.mean() + tc * se)
    return out


def pstr(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def fm(v, dp):
    return "-" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.{dp}f}"


def cell(r, dp, with_stats=True):
    s = f"{fm(r['treat'], dp)}±{fm(r['treat_sd'], dp)}"
    if with_stats and not np.isnan(r["pct"]):
        s += f" ({r['pct']:+.1f}%"
        if not np.isnan(r["p"]):
            s += f", p={pstr(r['p'])}" if r["p"] >= 0.001 else ", p<0.001"
        s += ")"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", default="tables_v4")
    a = ap.parse_args()
    D = os.path.expanduser(a.dir)

    NEED = ["fixed", "actuated_all", "coord", "act_ped", "act_ped_pv60",
            "act_ped_pv240", "coord_ped", "coord_ped_pv60", "coord_ped_pv240"]
    R = {n: load(D, n) for n in NEED}
    missing = [n for n, v in R.items() if v is None]
    if R["fixed"] is None:
        sys.exit(f"[오류] {D}/fixed/experiment_summary.csv 가 없습니다.")
    if missing:
        print(f"[경고] 없는 실행: {missing} — 해당 표는 건너뜁니다.\n")

    L, rows = [], []
    seeds = sorted(R["fixed"]["seed"].astype(int))
    L.append(f"# 논문 A 표 재작성안 (시드 {len(seeds)}개: {seeds[0]}~{seeds[-1]})\n")
    L.append("± 는 표본표준편차(ddof=1). p는 시드 짝 paired t-test. "
             "Wilcoxon 최소 달성 p는 n=5에서 0.0625, n=7에서 0.0156이다.\n")

    # ---------------- Table 5
    if R["actuated_all"] is not None:
        L.append("\n## Table 5. 노선 수준 비교 (고정식 → 전 교차로 감응식)\n")
        L.append("| 지표 | 고정식 | 전 교차로 감응식 | 변화 | 95% CI | p | d |")
        L.append("|---|---|---|---|---|---|---|")
        for k, lab, dp, _ in METRICS:
            if k not in R["fixed"].columns or k not in R["actuated_all"].columns:
                continue
            r = paired(R["fixed"], R["actuated_all"], k)
            rows.append(dict(table="T5", metric=lab, **r))
            L.append(f"| {lab} | {fm(r['base'],dp)}±{fm(r['base_sd'],dp)} | "
                     f"{fm(r['treat'],dp)}±{fm(r['treat_sd'],dp)} | {r['pct']:+.1f}% | "
                     f"[{fm(r['lo'],dp)}, {fm(r['hi'],dp)}] | "
                     f"{pstr(r['p'])} | "
                     f"{r['dz']:+.1f} |")
        f_st = R["fixed"]["tram_avg_stops"].mean() - STATION_STOPS
        a_st = R["actuated_all"]["tram_avg_stops"].mean() - STATION_STOPS
        L.append(f"\n* 신호 정지: 고정식 {f_st:.2f}회 → 감응식 {a_st:.2f}회 "
                 f"(**{100*(f_st-a_st)/f_st:.1f}% 감소**). 정거장 정차 {STATION_STOPS:.0f}회 제외.")
        cyc = R["fixed"]["tram_avg_travel_s"].mean() - R["actuated_all"]["tram_avg_travel_s"].mean()
        L.append(f"* 순환시간 단축 {cyc:.0f} s (약 {cyc/60:.1f}분) → 첨두 8분 배차 기준 약 "
                 f"{cyc/480:.1f}편성의 차량소요 절감.")

    # ---------------- Table 6
    if R["coord"] is not None and R["actuated_all"] is not None:
        L.append("\n\n## Table 6. 신호 운영전략별 노선·구간 성능\n")
        L.append("| 지표 | 고정식 | 자유 감응식 | 연동+부분 우선 |")
        L.append("|---|---|---|---|")
        for k, lab, dp, _ in METRICS:
            if k not in R["fixed"].columns:
                continue
            ra = paired(R["fixed"], R["actuated_all"], k)
            rc = paired(R["fixed"], R["coord"], k)
            rows.append(dict(table="T6-act", metric=lab, **ra))
            rows.append(dict(table="T6-coord", metric=lab, **rc))
            L.append(f"| {lab} | {fm(ra['base'],dp)}±{fm(ra['base_sd'],dp)} | "
                     f"{cell(ra,dp)} | {cell(rc,dp)} |")
        ta = paired(R["fixed"], R["actuated_all"], "tram_avg_kmh")["pct"]
        tc = paired(R["fixed"], R["coord"], "tram_avg_kmh")["pct"]
        ca = paired(R["fixed"], R["actuated_all"], "car_avg_kmh")["pct"]
        cc = paired(R["fixed"], R["coord"], "car_avg_kmh")["pct"]
        if ta:
            L.append(f"\n* 연동+부분 우선은 자유 감응식이 제공하는 트램 편익의 **{100*tc/ta:.0f}%**"
                     f"(표정속도 {tc:+.1f}% vs {ta:+.1f}%)를 유지하면서 "
                     f"승용차 손실을 {ca:+.1f}% → {cc:+.1f}% 로 완화하였다.")

    # ---------------- Table 7
    PED = [("없음 (버튼 없음)", "actuated_all", "coord"),
           ("포아송 60 인/h", "act_ped_pv60", "coord_ped_pv60"),
           ("포아송 240 인/h", "act_ped_pv240", "coord_ped_pv240"),
           ("왕복 집단 (상시)", "act_ped", "coord_ped")]
    if any(R[b] is not None for _, b, _ in PED):
        L.append("\n\n## Table 7. 보행자 감응의 용량 비용 — 승용차 평균속도 (km/h)\n")
        L.append("| 횡단 보행 수요 | 자유 감응식 | 연동+부분 우선 |")
        L.append("|---|---|---|")
        base_a = R["actuated_all"]["car_avg_kmh"].mean() if R["actuated_all"] is not None else np.nan
        base_c = R["coord"]["car_avg_kmh"].mean() if R["coord"] is not None else np.nan
        for lab, ka, kc in PED:
            def one(key, base):
                if R.get(key) is None:
                    return "-"
                v = R[key]["car_avg_kmh"]
                s = f"{v.mean():.2f}±{v.std(ddof=1):.2f}"
                if not np.isnan(base) and base:
                    s += f" ({100*(v.mean()-base)/base:+.1f}%)"
                return s
            L.append(f"| {lab} | {one(ka, base_a)} | {one(kc, base_c)} |")
        L.append("\n* 괄호는 보행 수요가 없는 같은 전략 대비 변화율(상대 %). "
                 "%p 가 아니라 상대 % 이다.")
        for lab, ka, kc in PED:
            if R.get(ka) is not None and "tram_avg_travel_s" in R[ka]:
                L.append(f"* 트램 순환시간 ({lab}): 자유 감응식 "
                         f"{R[ka]['tram_avg_travel_s'].mean():,.0f} s"
                         + (f" / 연동+부분 우선 {R[kc]['tram_avg_travel_s'].mean():,.0f} s"
                            if R.get(kc) is not None else ""))

    # ---------------- 발산 점검 (자동)
    L.append("\n\n## 과포화 발산 점검\n")
    L.append("역방향 본선(`origin=road_loopA_r0`) 승용차의 `travel_s` 를 `depart_s` 에 회귀시킨 "
             "기울기. **+20 s/1000s 를 넘으면 발산**이며 해당 시드는 평균을 오염시킨다.\n")
    L.append("| 실행 | 시드 | 완주 | 평균 km/h | 기울기 s/1000s | 판정 |")
    L.append("|---|---|---|---|---|---|")
    diverged = []
    for n in NEED:
        if R[n] is None:
            continue
        for sd_ in sorted(R[n]["seed"].astype(int)):
            vp = None
            for tag in ("daejeon", "daejeon_coord", "daejeon_ped", "daejeon_coord_ped",
                        "daejeon_ped_pv60", "daejeon_coord_ped_pv60",
                        "daejeon_ped_pv240", "daejeon_coord_ped_pv240"):
                cand = os.path.join(D, n, f"vehicles_{tag}_s{sd_}.csv")
                if os.path.exists(cand):
                    vp = cand
                    break
            if vp is None:
                continue
            t = pd.read_csv(vp)
            c = t[(t["kind"] == "car") & (t["origin"] == "road_loopA_r0")]
            if len(c) < 10:
                continue
            lr = stats.linregress(c["depart_s"], c["travel_s"])
            sl = lr.slope * 1000
            bad = sl > 20
            if bad:
                diverged.append((n, sd_, sl))
            L.append(f"| {n} | {sd_} | {len(c)} | {c['avg_kmh'].mean():.2f} | "
                     f"{sl:+.1f} | {'**★ 발산**' if bad else '정상'} |")
    if diverged:
        L.append(f"\n**⚠ 발산 {len(diverged)}건**: "
                 + ", ".join(f"{n}/시드{s}" for n, s, _ in diverged)
                 + ". 해당 시드를 제외한 값도 함께 계산해 본문에 병기하거나, "
                 "시드를 교체해 재실행할 것.")
    else:
        L.append("\n발산 없음 — 모든 시드가 정상 범위다.")

    md = "\n".join(L)
    open(a.out + ".md", "w", encoding="utf-8").write(md)
    if rows:
        pd.DataFrame(rows).to_csv(a.out + ".csv", index=False, encoding="utf-8-sig")
    print(md)
    print(f"\n\n저장: {a.out}.md, {a.out}.csv")


if __name__ == "__main__":
    main()
