#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_stats.py — 시드 짝 비교 통계검정 / 효과크기 / 정시성 산출
AutoTram 논문(대전 2호선 TSP) Table 5·6 보강용.

사용법
------
1) 통계검정 (Table 5·6에 p값·효과크기 열 추가)
   python3 seed_stats.py paired --input results.csv --baseline 고정식 --out table5_stats.csv

   입력 CSV는 아래 둘 중 아무 형식이나 가능(자동 판별):
     [long ] strategy,seed,metric,value
     [wide ] strategy,seed,tram_speed,cycle_time,car_speed,...

2) 정시성 지표 (스케줄 준수 편차·정시 도착률)
   python3 seed_stats.py punctuality --input arrivals.csv --headway 480 --out punctuality.csv

   입력 CSV: strategy,seed,run_id,station_id,sched_time,actual_time
     (sched_time 이 없으면 --headway 로 계획 시각을 생성)

3) 파이프라인 점검용 합성 데이터(논문 게재 평균·표준편차 재현)
   python3 seed_stats.py demo

출력
----
· CSV (기계 판독용)
· 콘솔에 논문 표에 그대로 붙일 수 있는 문자열 (예: "28.37±0.40 (+5.9%, p=0.003, d=3.1)")
"""
import argparse, sys, math
import numpy as np
import pandas as pd
from scipy import stats

# 값이 클수록 좋은 지표 / 작을수록 좋은 지표 (부호 해석용)
HIGHER_BETTER = {"tram_speed", "car_speed", "bus_speed", "throughput", "표정속도", "평균속도"}


# ----------------------------------------------------------------------
def load_long(path):
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    need = {"strategy", "seed"}
    if not need.issubset(set(cols)):
        sys.exit(f"[오류] CSV에 strategy, seed 열이 필요합니다. 현재 열: {list(df.columns)}")
    df = df.rename(columns={cols["strategy"]: "strategy", cols["seed"]: "seed"})
    if "metric" in cols and "value" in cols:                       # long
        return df.rename(columns={cols["metric"]: "metric", cols["value"]: "value"})[
            ["strategy", "seed", "metric", "value"]]
    idv = ["strategy", "seed"]                                      # wide -> long
    val = [c for c in df.columns if c not in idv]
    return df.melt(id_vars=idv, value_vars=val, var_name="metric", value_name="value")


def paired_stats(a, b, metric=""):
    """a=기준(baseline), b=처리(treatment). 시드 순서가 짝지어져 있다고 가정."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = len(a)
    d = b - a
    out = {
        "n_pairs": n,
        "baseline_mean": a.mean(), "baseline_sd": a.std(ddof=1),
        "treat_mean": b.mean(),    "treat_sd": b.std(ddof=1),
        "diff_mean": d.mean(),     "diff_sd": d.std(ddof=1),
        "pct_change": (d.mean() / a.mean() * 100) if a.mean() else np.nan,
    }
    if n < 2 or np.allclose(d, d[0]):
        out.update(t_stat=np.nan, p_ttest=np.nan, cohen_dz=np.nan,
                   ci95_low=np.nan, ci95_high=np.nan, p_wilcoxon=np.nan,
                   wilcoxon_p_floor=np.nan, note="분산 0 또는 표본 부족")
        return out

    t, p = stats.ttest_rel(b, a)
    dz = d.mean() / d.std(ddof=1)
    se = d.std(ddof=1) / math.sqrt(n)
    tc = stats.t.ppf(0.975, n - 1)
    out.update(t_stat=t, p_ttest=p, cohen_dz=dz,
               ci95_low=d.mean() - tc * se, ci95_high=d.mean() + tc * se)

    # Wilcoxon 부호순위 — n이 작으면 도달 가능한 최소 p값이 0.05를 넘을 수 있음
    try:
        w, pw = stats.wilcoxon(b, a, zero_method="wilcox", alternative="two-sided",
                               mode="exact" if n <= 25 else "auto")
    except Exception:
        w, pw = np.nan, np.nan
    floor = 2.0 / (2 ** n)                       # 양측 최소 달성 p값
    out.update(p_wilcoxon=pw, wilcoxon_p_floor=floor,
               note=("Wilcoxon 최소 달성 p=%.4f > 0.05 — 시드 %d개로는 비모수검정으로 "
                     "유의성 주장 불가(시드 확대 필요)" % (floor, n)) if floor > 0.05 else "")
    return out


def fmt_cell(r, metric=""):
    """논문 표에 붙일 문자열."""
    s = f"{r['treat_mean']:.2f}±{r['treat_sd']:.2f}"
    if not np.isnan(r["pct_change"]):
        s += f" ({r['pct_change']:+.1f}%"
        if not np.isnan(r["p_ttest"]):
            s += f", p={r['p_ttest']:.3f}" if r["p_ttest"] >= 0.001 else ", p<0.001"
        if not np.isnan(r["cohen_dz"]):
            s += f", d={r['cohen_dz']:.1f}"
        s += ")"
    return s


def cmd_paired(args):
    df = load_long(args.input)
    base = args.baseline
    strategies = [s for s in df["strategy"].unique() if s != base]
    if base not in set(df["strategy"]):
        sys.exit(f"[오류] baseline '{base}' 없음. 가능한 값: {sorted(df['strategy'].unique())}")

    rows = []
    for metric in df["metric"].unique():
        m = df[df["metric"] == metric]
        b = m[m["strategy"] == base].sort_values("seed")
        for st in strategies:
            t = m[m["strategy"] == st].sort_values("seed")
            common = sorted(set(b["seed"]) & set(t["seed"]))
            if len(common) < 2:
                continue
            bv = b[b["seed"].isin(common)].sort_values("seed")["value"].values
            tv = t[t["seed"].isin(common)].sort_values("seed")["value"].values
            r = paired_stats(bv, tv, metric)
            r.update(metric=metric, baseline=base, strategy=st, cell=fmt_cell(r, metric))
            rows.append(r)

    res = pd.DataFrame(rows)
    order = ["metric", "baseline", "strategy", "n_pairs", "baseline_mean", "baseline_sd",
             "treat_mean", "treat_sd", "diff_mean", "pct_change", "ci95_low", "ci95_high",
             "t_stat", "p_ttest", "p_wilcoxon", "wilcoxon_p_floor", "cohen_dz", "cell", "note"]
    res = res[[c for c in order if c in res.columns]]
    res.to_csv(args.out, index=False, encoding="utf-8-sig")

    print(f"\n=== 시드 짝 비교 결과 (baseline = {base}) ===")
    for _, r in res.iterrows():
        star = "***" if r["p_ttest"] < .001 else "**" if r["p_ttest"] < .01 else "*" if r["p_ttest"] < .05 else "n.s."
        print(f"  [{r['metric']:<14}] {r['strategy']:<12} "
              f"{r['baseline_mean']:8.2f} → {r['treat_mean']:8.2f}  "
              f"Δ={r['diff_mean']:+7.2f} ({r['pct_change']:+5.1f}%)  "
              f"95%CI[{r['ci95_low']:+.2f},{r['ci95_high']:+.2f}]  "
              f"p={r['p_ttest']:.4f} {star}  d={r['cohen_dz']:+.2f}")
        if r["note"]:
            print(f"       └ {r['note']}")
    print(f"\n논문 표 삽입용 문자열:")
    for _, r in res.iterrows():
        print(f"  {r['metric']:<14} | {r['strategy']:<12} | {r['cell']}")
    print(f"\n저장: {args.out}")


# ----------------------------------------------------------------------
def cmd_punctuality(args):
    """정거장 도착시각 로그 → 스케줄 준수 편차 / 정시 도착률."""
    df = pd.read_csv(args.input)
    low = {c.lower(): c for c in df.columns}
    for k in ("strategy", "seed", "actual_time"):
        if k not in low:
            sys.exit(f"[오류] '{k}' 열이 필요합니다. 현재 열: {list(df.columns)}")
    df = df.rename(columns={low[k]: k for k in low})

    if "sched_time" not in df.columns:
        if "run_id" not in df.columns or "station_id" not in df.columns:
            sys.exit("[오류] sched_time이 없으면 run_id, station_id 열이 필요합니다.")
        # 각 (strategy, seed, station) 의 첫 편성 도착시각을 기준으로 등간격 배차 계획 생성
        g = df.sort_values("actual_time").groupby(["strategy", "seed", "station_id"])
        df["_first"] = g["actual_time"].transform("first")
        df["_rank"] = g["actual_time"].rank(method="first") - 1
        df["sched_time"] = df["_first"] + df["_rank"] * args.headway

    df["dev"] = df["actual_time"] - df["sched_time"]

    rows = []
    for (st, sd), g in df.groupby(["strategy", "seed"]):
        dev = g["dev"].values
        rows.append(dict(strategy=st, seed=sd, n_obs=len(dev),
                         mean_dev=dev.mean(), sd_dev=dev.std(ddof=1) if len(dev) > 1 else np.nan,
                         p95_abs_dev=np.percentile(np.abs(dev), 95),
                         on_time_rate=np.mean(np.abs(dev) <= args.tolerance) * 100,
                         early_rate=np.mean(dev < -args.tolerance) * 100,
                         late_rate=np.mean(dev > args.tolerance) * 100))
    per_seed = pd.DataFrame(rows)
    per_seed.to_csv(args.out, index=False, encoding="utf-8-sig")

    print(f"\n=== 정시성 (허용오차 ±{args.tolerance:.0f} s, 계획 배차 {args.headway:.0f} s) ===")
    agg = per_seed.groupby("strategy").agg(
        준수편차SD_평균=("sd_dev", "mean"), 준수편차SD_표준편차=("sd_dev", "std"),
        정시도착률_평균=("on_time_rate", "mean"), 정시도착률_표준편차=("on_time_rate", "std"),
        지연률=("late_rate", "mean"))
    print(agg.round(2).to_string())
    print(f"\n저장: {args.out}")
    print("→ 이 결과를 seed_stats.py paired 의 입력(long 형식)으로 넘기면 정시성에도 p값을 붙일 수 있습니다.")


# ----------------------------------------------------------------------
def cmd_demo(args):
    """논문 게재 평균·표준편차를 재현하는 합성 시드 데이터로 파이프라인 점검.
       ※ 합성 데이터입니다. 논문에 인용하지 마십시오."""
    rng = np.random.default_rng(20260727)
    spec = {  # metric: (고정식 mean/sd, 자유감응 mean/sd, 연동+부분우선 mean/sd)
        "tram_speed":  ((26.79, 0.27), (28.37, 0.40), (28.13, 0.33)),
        "cycle_time":  ((4533, 46),    (4282, 61),    (4319, 52)),
        "tram_stops":  ((47.5, 1.1),   (41.1, 0.4),   (41.3, 0.2)),
        "car_speed":   ((37.24, 0.29), (34.94, 0.35), (36.25, 0.28)),
        "bus_speed":   ((30.76, 0.61), (29.15, 0.33), (30.49, 0.63)),
    }
    names = ["고정식", "자유감응식", "연동+부분우선"]
    seeds = [42, 43, 44, 45, 46]
    rows = []
    for metric, trio in spec.items():
        # 시드 공통 성분(짝 구조 재현) + 전략별 잔차
        common = rng.standard_normal(len(seeds))
        for name, (mu, sd) in zip(names, trio):
            resid = rng.standard_normal(len(seeds))
            z = 0.75 * common + 0.66 * resid
            z = (z - z.mean()) / z.std(ddof=1)
            for s, v in zip(seeds, mu + sd * z):
                rows.append(dict(strategy=name, seed=s, metric=metric, value=round(float(v), 4)))
    pd.DataFrame(rows).to_csv("demo_results.csv", index=False, encoding="utf-8-sig")
    print("합성 데이터 생성: demo_results.csv  (※ 검증용 — 논문 인용 금지)")

    class A: pass
    a = A(); a.input = "demo_results.csv"; a.baseline = "고정식"; a.out = "demo_stats.csv"
    cmd_paired(a)


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="시드 짝 비교 통계검정 / 정시성 산출")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("paired", help="paired t-test / Wilcoxon / Cohen's d / 95% CI")
    p1.add_argument("--input", required=True)
    p1.add_argument("--baseline", default="고정식")
    p1.add_argument("--out", default="paired_stats.csv")
    p1.set_defaults(func=cmd_paired)

    p2 = sub.add_parser("punctuality", help="스케줄 준수 편차 / 정시 도착률")
    p2.add_argument("--input", required=True)
    p2.add_argument("--headway", type=float, default=480.0, help="계획 배차간격(초), 기본 480=8분")
    p2.add_argument("--tolerance", type=float, default=60.0, help="정시 판정 허용오차(초)")
    p2.add_argument("--out", default="punctuality.csv")
    p2.set_defaults(func=cmd_punctuality)

    p3 = sub.add_parser("demo", help="합성 데이터로 파이프라인 점검")
    p3.set_defaults(func=cmd_demo)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
