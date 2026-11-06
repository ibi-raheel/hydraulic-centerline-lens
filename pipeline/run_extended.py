"""Calibration, physics features, uncertainty and value analysis (run after run.py).
Usage: python -I run_extended.py <raw_dir> <out_dir>   -> <out_dir>/extended.json"""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, cross_val_predict

from hcl.load import RATES, load_channel, load_profile, to_10hz
from hcl.kpi import cycle_kpis, rise_time_s
from hcl.model import build_features, blocked_groups, evaluate, confusion
from hcl.spec import run_rules
from hcl import calib, physics, value, mutate
from hcl.stats import wilson, rule_of_three_n, block_bootstrap_acc, bootstrap_median_ci

ENV_TAGS = ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2"]
KS = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0]
FS = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20]
CONDS = [("valve", [90, 80, 73]), ("leak", [1, 2]), ("accumulator", [115, 100, 90])]
HEALTHY = {"valve": 100, "leak": 0, "accumulator": 130}
BLOCK_SIZES = [1, 10, 25, 50, 100, 200]
PRICE_USD_KWH = 0.0964   # EIA Electric Power Monthly Table 5.6.A, US industrial average, Aug 2026 (preliminary)
PRICE_SRC = "U.S. EIA, Electric Power Monthly, Table 5.6.A: average retail price, industrial sector, U.S. total, August 2026 (preliminary), 9.64 cents/kWh; accessed 2026-11-06"
DUTY_H = 4000            # two-shift operation, ~16 h x 250 days


def r(x, n=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(round(float(x), n))


def wl(k, n):
    p, lo, hi = wilson(int(k), int(n))
    return {"k": int(k), "n": int(n), "rate": r(p), "lo": r(lo), "hi": r(hi)}


def blocked_pred(X, y, block, seed=0):
    clf = RandomForestClassifier(n_estimators=200, n_jobs=2, random_state=seed, min_samples_leaf=2)
    return cross_val_predict(clf, X, y, groups=blocked_groups(len(y), block), cv=GroupKFold(5))


def main(raw, out):
    t0 = time.time()
    cache = Path(__file__).resolve().parent / "cache"
    ch = {t: load_channel(raw, t, cache) for t in RATES}
    prof = load_profile(raw)
    n = len(prof)
    k = cycle_kpis(ch["PS1"], ch["FS1"], ch["EPS1"], ch["SE"])
    summary = json.loads((out / "summary.json").read_text())
    res = {}

    # ================= 1. calibrated centerline =================
    sig = {t: to_10hz(ch[t], RATES[t]).astype(np.float64) for t in ENV_TAGS}
    ctx = prof.cooler.to_numpy()
    temp = ch["TS1"].mean(axis=1).astype(np.float64)
    comp_ok = ((prof.valve == 100) & (prof.leak == 0) & (prof.accumulator == 130)).to_numpy()
    stable = (prof.stable_flag == 0).to_numpy()
    healthy = comp_ok & stable
    hidx = np.where(healthy)[0]
    cond_masks = []
    for comp, levels in CONDS:
        for lv in levels:
            m = stable.copy()
            for o, hv in HEALTHY.items():
                m &= (prof[o] == (lv if o == comp else hv)).to_numpy()
            cond_masks.append((comp, lv, m))
    calib_out = {"n_healthy": int(healthy.sum()), "healthy_by_cooler": {str(c): int((healthy & (ctx == c)).sum()) for c in (3, 20, 100)},
                 "ks": KS, "fs": FS, "modes": {}}
    for mode in ["single_context", "per_context", "pooled_detrend"]:
        fr = calib.score_contexts(sig, ctx, temp, healthy, KS, mode)
        al = calib.alarm_from_frac(fr, FS)             # (n, nk, nf)
        fa = al[healthy].sum(axis=0)                     # (nk, nf)
        det = np.stack([al[m].mean(axis=0) for _, _, m in cond_masks])  # (ncond, nk, nf)
        mean_det = det.mean(axis=0)
        grid = [{"k": KS[a], "f": FS[b], "fa": int(fa[a, b]), "fa_hi": r(wilson(int(fa[a, b]), len(hidx))[2]),
                 "det_mean": r(mean_det[a, b])} for a in range(len(KS)) for b in range(len(FS))]
        ok = [(a, b) for a in range(len(KS)) for b in range(len(FS)) if wilson(int(fa[a, b]), len(hidx))[2] <= 0.12]
        if ok:
            a, b = max(ok, key=lambda ab: (mean_det[ab], KS[ab[0]]))
        else:
            a, b = min(((a, b) for a in range(len(KS)) for b in range(len(FS))), key=lambda ab: (fa[ab], -mean_det[ab]))
        unstable_ok = comp_ok & ~stable
        nongolden = ~healthy
        ia, ib = KS.index(4.0), FS.index(0.05)
        calib_out["modes"][mode] = {
            "grid": grid,
            "operating_point": {"k": KS[a], "f": FS[b], "false_alarm": wl(fa[a, b], len(hidx)),
                                "detection_mean": r(mean_det[a, b]),
                                "conditions": [{"component": c, "level": lv, **wl(al[m][:, a, b].sum(), m.sum()),
                                                "by_cooler": {str(cc): wl(al[m & (ctx == cc)][:, a, b].sum(), (m & (ctx == cc)).sum()) for cc in (3, 20, 100)}}
                                               for (c, lv, m) in cond_masks],
                                "alarm_rate_nongolden": r(al[nongolden][:, a, b].mean()),
                                "alarm_rate_healthy_unstable": wl(al[unstable_ok][:, a, b].sum(), unstable_ok.sum())},
            "at_k4_f5": {"false_alarm": wl(fa[ia, ib], len(hidx)), "detection_mean": r(mean_det[ia, ib]),
                         "alarm_rate_nongolden": r(al[nongolden][:, ia, ib].mean()),
                         "alarm_rate_healthy_unstable": wl(al[unstable_ok][:, ia, ib].sum(), unstable_ok.sum()),
                         "fa_by_cooler": {str(cc): wl(al[healthy & (ctx == cc)][:, ia, ib].sum(), (healthy & (ctx == cc)).sum()) for cc in (3, 20, 100)}},
        }
        print(mode, "op", KS[a], FS[b], "FA", int(fa[a, b]), "/", len(hidx), "det", round(float(mean_det[a, b]), 3),
              "| k4f5 FA", int(fa[ia, ib]), "det", round(float(mean_det[ia, ib]), 3))
    # choose the deployable mode: best detection at its calibrated point
    # deployable = meets the false-alarm bound (Wilson upper <= 12 %, i.e. 0 alarms in 30), then best detection
    ok_modes = [m_ for m_ in ("per_context", "pooled_detrend") if calib_out["modes"][m_]["operating_point"]["false_alarm"]["hi"] <= 0.12]
    best = max(ok_modes, key=lambda m_: calib_out["modes"][m_]["operating_point"]["detection_mean"]) if ok_modes else None
    calib_out["chosen"] = best
    op = calib_out["modes"][best or "per_context"]["operating_point"]
    ss = calib.sample_size_per_context(sig, ctx, healthy, op["k"], op["f"], [3, 5, 7, 9])
    calib_out["sample_size"] = {"mode": best or "per_context", "k": op["k"], "f": op["f"],
                                "rows": [{"n_golden": nn, "fa_mean": r(v[0]), "fa_p2_5": r(v[1]), "fa_p97_5": r(v[2]),
                                          "alarms": v[3], "tests": v[4]} for nn, v in ss.items()],
                                "rule_of_three": {"for_10pct": rule_of_three_n(0.10), "for_5pct": rule_of_three_n(0.05),
                                                  "for_1pct": rule_of_three_n(0.01)}}
    res["calibration"] = calib_out
    print("sample size", ss)

    # ================= 2. physics features =================
    ps1 = ch["PS1"].astype(np.float64)
    taus, rmse = physics.step_taus(ps1)
    gold = np.where(healthy & (ctx == 100))[0]
    tpl2 = np.median(ch["PS2"][gold].astype(np.float64), axis=0)
    tpl1 = np.median(ps1[gold], axis=0)
    e2 = [a + int(np.argmax(np.abs(np.diff(tpl2[a:b])))) for a, b in [(880, 1000)] + physics.STEP_WINDOWS[1:]]
    e1 = 900 + int(np.argmax(np.abs(np.diff(tpl1[900:1000]))))
    lag2 = np.column_stack([physics.edge_lags(ch["PS2"], tpl2, c) for c in e2])
    lag1 = physics.edge_lags(ch["PS1"], tpl1, e1)
    ps4_range = float(np.ptp(np.median(ch["PS4"][gold], axis=0)))
    phys = {**{f"PHY.tau{s+1}": taus[:, s] for s in range(5)},
            **{f"PHY.lag_PS2_e{s+1}_ms": lag2[:, s] for s in range(5)}, "PHY.lag_PS1_e1_ms": lag1}
    P = np.column_stack(list(phys.values()))
    P = np.where(np.isfinite(P), P, np.nanmedian(P, axis=0))
    # gas-law check on the 9.4 s relaxation: stable cycles in ONE thermal context (cooler 100 %, TS1 35.6-36.3 C),
    # so no viscosity correction is needed; tau ~ p0^(1/n) predicts a log-log slope in [1/1.4, 1].
    acc = prof.accumulator.to_numpy()
    levels = [90, 100, 115, 130]
    st = stable & (ctx == 100) & np.isfinite(taus[:, 0])
    groups = {a_: taus[st & (acc == a_), 0] for a_ in levels}
    tau_by = {str(a_): bootstrap_median_ci(groups[a_], n_boot=2000) for a_ in levels}
    meds = np.array([tau_by[str(a_)][0] for a_ in levels])
    slope = physics.loglog_slope(np.array(levels, float), np.log(meds))
    rng = np.random.default_rng(0)
    bs = [physics.loglog_slope(np.array(levels, float), np.log([np.median(rng.choice(groups[a_], len(groups[a_]))) for a_ in levels]))
          for _ in range(2000)]
    tau_raw_by = {str(a_): r(np.median(taus[stable & (acc == a_), 0]), 4) for a_ in levels}
    tau_cell = {str(a_): {str(c_): r(np.median(taus[stable & (acc == a_) & (ctx == c_), 0]), 4) for c_ in (3, 20, 100)} for a_ in levels}
    temp_cell = {str(c_): r(np.median(temp[stable & (ctx == c_)]), 1) for c_ in (3, 20, 100)}
    # parallel line compliance: tau = R*(C_line + K*p0^(1/n)) -> linear in p0^(1/n)
    comp_fit = {}
    for nn in (1.0, 1.4):
        xx = np.array(levels, float) ** (1 / nn)
        A = np.column_stack([np.ones(4), xx])
        coef, *_ = np.linalg.lstsq(A, meds, rcond=None)
        comp_fit[str(nn)] = {"intercept_s": r(coef[0], 4), "rmse_ms": r(1000 * np.sqrt(np.mean((A @ coef - meds) ** 2)), 2)}
    valve = prof.valve.to_numpy()
    lag_by_valve = {str(v): bootstrap_median_ci(lag2[stable & (valve == v), 0], n_boot=2000) for v in (100, 90, 80, 73)}
    lag_by_acc = {str(a_): r(np.median(lag2[stable & (acc == a_), 0]), 1) for a_ in levels}
    tau_by_valve = {str(v): r(np.median(taus[stable & (valve == v), 0]), 4) for v in (100, 90, 80, 73)}
    res["physics"] = {
        "step_edges_s": [r(e / 100, 2) for e in physics.step_edges(tpl1)],
        "fit_rmse_bar_median": [r(np.nanmedian(rmse[:, s]), 3) for s in range(5)],
        "fit_failures": int(np.isnan(taus).sum()),
        "tau1_by_acc_raw_s": tau_raw_by,
        "tau1_by_acc_cooler100_s": {kk: {"median": r(v[0]), "lo": r(v[1]), "hi": r(v[2]), "n": int(len(groups[int(kk)]))} for kk, v in tau_by.items()},
        "tau1_by_acc_and_cooler_s": tau_cell, "ts1_by_cooler_degC": temp_cell,
        "loglog_slope": {"value": r(slope, 3), "lo": r(np.percentile(bs, 2.5), 3), "hi": r(np.percentile(bs, 97.5), 3),
                         "bounds": {"adiabatic_1_over_1.4": 0.714, "isothermal_1": 1.0}},
        "line_compliance_fit": comp_fit,
        "tau1_by_valve_s": tau_by_valve,
        "valve_lag_PS2_ms": {kk: {"median": r(v[0], 1), "lo": r(v[1], 1), "hi": r(v[2], 1)} for kk, v in lag_by_valve.items()},
        "valve_lag_by_acc_ms": lag_by_acc,
        "ps4_golden_range_bar": r(ps4_range, 3),
        "features": list(phys),
    }
    print(json.dumps(res["physics"], indent=0)[:2500])

    # ================= 3. models with CIs, physics features, block-size sensitivity =================
    rise = np.array([rise_time_s(ps1[i]) for i in range(n)])
    X, names = build_features(ch, {"PS1.rise_time": rise, "KPI.eff": k["eff_pct"], "KPI.p_hyd": k["p_hyd_kw"]})
    XP = np.hstack([X, P])
    names_p = names + list(phys)
    models = []
    for target in ["cooler", "valve", "leak", "accumulator"]:
        y = prof[target].to_numpy()
        base = evaluate(X, y)
        aug = evaluate(XP, y)
        ponly = blocked_pred(P, y, 50)
        top = sorted(zip(names_p, aug["importance"]), key=lambda z: -z[1])[:6]
        row = {"target": target, "classes": base["classes"]}
        for key, rr in [("base", base), ("with_physics", aug)]:
            mb = block_bootstrap_acc(rr["pred_blocked"] == y)
            row[key] = {"blocked": r(mb[0]), "blocked_lo": r(mb[1]), "blocked_hi": r(mb[2]), "shuffled": r(rr["acc_random"]),
                        "confusion": confusion(y, rr["pred_blocked"], rr["classes"]).tolist()}
        mp = block_bootstrap_acc(ponly == y)
        row["physics_only"] = {"n_features": P.shape[1], "blocked": r(mp[0]), "blocked_lo": r(mp[1]), "blocked_hi": r(mp[2])}
        row["top_features_with_physics"] = [{"name": a_, "imp": r(b_)} for a_, b_ in top]
        models.append(row)
        print(target, row["base"]["blocked"], row["with_physics"]["blocked"], row["physics_only"]["blocked"], [t["name"] for t in row["top_features_with_physics"][:3]])
    res["models"] = models
    sens = {}
    for target in ["accumulator", "valve"]:
        y = prof[target].to_numpy()
        shuffled = next(m for m in summary["models"] if m["target"] == target)["acc_random"]
        rows = []
        for bsz in BLOCK_SIZES:
            acc_b = float((blocked_pred(X, y, bsz) == y).mean())
            rows.append({"block": bsz, "acc": r(acc_b), "gap_vs_shuffled_pts": r(100 * (shuffled - acc_b), 2)})
        sens[target] = {"shuffled": shuffled, "rows": rows}
        print("block sens", target, [(x_["block"], x_["acc"]) for x_ in rows])
    res["block_sensitivity"] = sens
    # weak-leak recall (lead time): blocked confusion of the base leak model
    lk = next(m for m in models if m["target"] == "leak")["base"]["confusion"]
    res["leak_recall"] = {str(c): wl(lk[i][i], sum(lk[i])) for i, c in enumerate([0, 1, 2])}

    # ================= 4. value =================
    eff = k["eff_pct"]
    val = {}
    for lv in (1, 2):
        val[f"leak{lv}"] = {"eff_pts": value.effect_with_ci(prof, eff, lv), "motor_kw": value.effect_with_ci(prof, k["p_motor_kw"], lv),
                            "p_hyd_kw": value.effect_with_ci(prof, k["p_hyd_kw"], lv)}
    eta_ok = float(np.median(eff[(prof.leak == 0).to_numpy() & stable])) / 100
    tables = {}
    for lv in (1, 2):
        e = val[f"leak{lv}"]["eff_pts"]
        tables[f"leak{lv}"] = {kk: {q: r(v_, 3) for q, v_ in value.energy_table(eta_ok, eta_ok + e[kk] / 100, 10.0, DUTY_H, PRICE_USD_KWH).items()}
                               for kk in ("median", "lo", "hi")}
    val.update({"eta_ok": r(eta_ok), "duty_h_per_yr": DUTY_H, "price_usd_kwh": PRICE_USD_KWH, "price_source": PRICE_SRC,
                "per_installed_hydraulic_kw": 10.0, "energy": tables,
                "raw_median_eff_by_leak": summary["kpi"]["eff_by_leak"],
                "p_hyd_median_by_leak": {str(l_): r(np.median(k["p_hyd_kw"][(prof.leak == l_).to_numpy()]), 3) for l_ in (0, 1, 2)}})
    for kk in val:
        if isinstance(val[kk], dict) and "eff_pts" in val[kk]:
            for q in val[kk]:
                val[kk][q] = {a_: r(b_, 4) if isinstance(b_, float) else b_ for a_, b_ in val[kk][q].items()}
    res["value"] = val
    print("value", json.dumps(val)[:1200])

    # ================= 5. contract mutation testing (SYNTHETIC mutations of real cycles) =================
    base_fail = run_rules(ch, prof, k)
    fit = summary["kpi"]["fit"]
    extra_fail = mutate.extra_rules(ch, k, fit)
    fp_new = {rid: int(m_.sum()) for rid, m_ in extra_fail.items()}
    clean = stable & ~np.any(np.stack(list(base_fail.values()) + list(extra_fail.values())), axis=0)
    sample = np.where(clean)[0][::7][:150]
    muts = []
    for name, fn in mutate.mutations().items():
        chm = {t: ch[t][sample].astype(np.float64).copy() for t in ("PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "SE")}
        fn(chm)
        km = cycle_kpis(chm["PS1"], chm["FS1"], chm["EPS1"], chm["SE"])
        pm = prof.iloc[sample].reset_index(drop=True)
        f7 = run_rules(chm, pm, km)
        f4 = mutate.extra_rules(chm, km, fit)
        any7 = np.any(np.stack(list(f7.values())), axis=0)
        any11 = any7 | np.any(np.stack(list(f4.values())), axis=0)
        muts.append({"mutation": name, "n": len(sample), "caught_7_rules": r(any7.mean(), 3), "caught_11_rules": r(any11.mean(), 3),
                     "by_rule": {rid: r(m_.mean(), 3) for rid, m_ in {**f7, **f4}.items() if m_.any()}})
    res["mutations"] = {"synthetic": True, "sample_n": int(len(sample)), "new_rule_fails_on_real_data": fp_new, "rows": muts,
                        "caught_7": r(np.mean([m_["caught_7_rules"] for m_ in muts]), 3),
                        "caught_11": r(np.mean([m_["caught_11_rules"] for m_ in muts]), 3)}
    print("mutations", json.dumps(res["mutations"]))
    res["runtime_s"] = r(time.time() - t0, 1)
    (out / "extended.json").write_text(json.dumps(res, indent=1))
    print("runtime", res["runtime_s"])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
