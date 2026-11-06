"""Offline pipeline: raw UCI matrices -> static JSON for the UI.
Usage: python -I run.py <raw_dir> <out_dir>"""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from hcl.load import RATES, UNITS, load_channel, load_profile, to_10hz
from hcl.kpi import cycle_kpis, rise_time_s, hydraulic_power_kw
from hcl.spec import RULES, run_rules
from hcl.envelope import fit_envelope, excursion
from hcl.model import build_features, evaluate, confusion

ENV_TAGS = ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2"]
K = 4.0
ALARM_FRAC = 0.05
HAND_CYCLE = 1790   # a golden cycle (0-based row index)
HAND_T = 30.0       # seconds


def r(x, n=3):
    return float(round(float(x), n))


def main(raw, out):
    t0 = time.time()
    cache = Path(__file__).resolve().parent / "cache"
    ch = {t: load_channel(raw, t, cache) for t in RATES}
    prof = load_profile(raw)
    n = len(prof)
    k = cycle_kpis(ch["PS1"], ch["FS1"], ch["EPS1"], ch["SE"])

    # ---------- spec ----------
    fails = run_rules(ch, prof, k)
    spec = [{**rule, "fail": int(fails[rule["id"]].sum()), "pass": int(n - fails[rule["id"]].sum()),
             "examples": np.where(fails[rule["id"]])[0][:8].tolist()} for rule in RULES]
    labels = {c: {str(kk): int(v) for kk, v in prof[c].value_counts().sort_index().items()} for c in prof.columns}
    documented = {"cooler": {"3": 732, "20": 732, "100": 741}, "valve": {"73": 360, "80": 360, "90": 360, "100": 1125},
                  "leak": {"0": 1221, "1": 492, "2": 492}, "accumulator": {"90": 808, "100": 399, "115": 399, "130": 599},
                  "stable_flag": {"0": 1449, "1": 756}}

    # ---------- KPI hand calc ----------
    i10 = int(HAND_T * 10)
    p_win = ch["PS1"][HAND_CYCLE, i10 * 10:(i10 + 1) * 10]
    p_inst = float(p_win.mean()); q_inst = float(ch["FS1"][HAND_CYCLE, i10])
    w_inst = float(ch["EPS1"][HAND_CYCLE, i10 * 10:(i10 + 1) * 10].mean())
    hand = {"cycle": HAND_CYCLE, "t_s": HAND_T, "p_bar": r(p_inst), "q_lpm": r(q_inst), "p_motor_w": r(w_inst, 1),
            "p_hyd_kw": r(p_inst * q_inst / 600, 4), "eff_pct": r(100 * (p_inst * q_inst / 600) / (w_inst / 1000), 2),
            "cycle_p_hyd_kw": r(k["p_hyd_kw"][HAND_CYCLE], 4), "cycle_p_motor_kw": r(k["p_motor_kw"][HAND_CYCLE], 4),
            "cycle_eff_pct": r(k["eff_pct"][HAND_CYCLE], 2), "cycle_se_pct": r(k["se_pct"][HAND_CYCLE], 2)}
    eff, se = k["eff_pct"], k["se_pct"]
    A = np.column_stack([eff, np.ones(n)])
    slope, icpt = np.linalg.lstsq(A, se, rcond=None)[0]
    resid = se - (slope * eff + icpt)
    corr = float(np.corrcoef(eff, se)[0, 1])
    kpi_points = [{"i": i, "eff": r(eff[i], 2), "se": r(se[i], 2), "valve": int(prof.valve[i]), "leak": int(prof.leak[i]),
                   "acc": int(prof.accumulator[i]), "cooler": int(prof.cooler[i])} for i in range(n)]
    eff_by_leak = {str(l): r(np.median(eff[prof.leak == l]), 2) for l in (0, 1, 2)}

    # ---------- golden envelope ----------
    golden = ((prof.cooler == 100) & (prof.valve == 100) & (prof.leak == 0) &
              (prof.accumulator == 130) & (prof.stable_flag == 0)).to_numpy()
    gidx = np.where(golden)[0]
    g10 = {t: to_10hz(ch[t], RATES[t]) for t in ENV_TAGS}
    floors = {t: 0.01 * (np.percentile(g10[t][gidx], 98) - np.percentile(g10[t][gidx], 2)) + 1e-3 for t in ENV_TAGS}
    env = {}
    for t in ENV_TAGS:
        c, lo, hi = fit_envelope(g10[t][gidx], K, floors[t])
        env[t] = (c, lo, hi)
    # leave-one-out false alarm on golden cycles
    loo_alarm = 0
    for j in gidx:
        rest = gidx[gidx != j]
        worst = 0.0
        for t in ENV_TAGS:
            _, lo, hi = fit_envelope(g10[t][rest], K, floors[t])
            f, _ = excursion(g10[t][j], lo, hi)
            worst = max(worst, float(f[0]))
        loo_alarm += worst > ALARM_FRAC
    # excursion for every cycle
    frac = {t: excursion(g10[t], env[t][1], env[t][2])[0] for t in ENV_TAGS}
    area = {t: excursion(g10[t], env[t][1], env[t][2])[1] for t in ENV_TAGS}
    worst_frac = np.max(np.stack([frac[t] for t in ENV_TAGS]), axis=0)
    alarm = worst_frac > ALARM_FRAC
    # detection by single-fault condition (cooler 100, stable, only one component degraded)
    base = (prof.cooler == 100) & (prof.stable_flag == 0)
    conds = []
    for comp, healthy, levels in [("valve", 100, [90, 80, 73]), ("leak", 0, [1, 2]), ("accumulator", 130, [115, 100, 90])]:
        others = {"valve": 100, "leak": 0, "accumulator": 130}
        for lv in levels:
            m = base.copy()
            for o, hv in others.items():
                m &= (prof[o] == (lv if o == comp else hv))
            m = m.to_numpy()
            if m.sum() == 0:
                continue
            tag_rate = {t: r((frac[t][m] > ALARM_FRAC).mean(), 3) for t in ENV_TAGS}
            conds.append({"component": comp, "level": lv, "n": int(m.sum()), "alarm_rate": r(alarm[m].mean(), 3),
                          "top_tag": max(tag_rate, key=tag_rate.get), "tag_rate": tag_rate})
    # example cycles for overlay: golden + one per single-fault condition
    examples = {"golden": int(gidx[0])}
    for c_ in conds:
        m = (base & (prof.valve == (c_["level"] if c_["component"] == "valve" else 100)) &
             (prof.leak == (c_["level"] if c_["component"] == "leak" else 0)) &
             (prof.accumulator == (c_["level"] if c_["component"] == "accumulator" else 130))).to_numpy()
        examples[f"{c_['component']}={c_['level']}"] = int(np.where(m)[0][0])
    ex_ids = sorted(set(examples.values()))
    step = 5  # ship every 5th 10 Hz bin (2 Hz) to keep JSON small
    envelope = {"tags": ENV_TAGS, "units": {t: UNITS[t] for t in ENV_TAGS}, "t": [r(x / 10, 1) for x in range(0, 600, step)],
                "k": K, "alarm_frac": ALARM_FRAC, "n_golden": int(golden.sum()), "golden_ids": gidx.tolist(),
                "loo_false_alarm": int(loo_alarm), "band": {}, "cycles": {}, "examples": examples, "conditions": conds,
                "overall_alarm_rate_nongolden": r(alarm[~golden].mean(), 3)}
    for t in ENV_TAGS:
        c, lo, hi = env[t]
        envelope["band"][t] = {"c": [r(v, 3) for v in c[::step]], "lo": [r(v, 3) for v in lo[::step]], "hi": [r(v, 3) for v in hi[::step]]}
    for i in ex_ids:
        envelope["cycles"][str(i)] = {"label": {kk: int(prof[kk][i]) for kk in prof.columns},
                                      "trace": {t: [r(v, 3) for v in g10[t][i][::step]] for t in ENV_TAGS},
                                      "frac": {t: r(frac[t][i], 4) for t in ENV_TAGS},
                                      "area": {t: r(area[t][i], 4) for t in ENV_TAGS}}

    # ---------- root cause models ----------
    rise = np.array([rise_time_s(ch["PS1"][i]) for i in range(n)])
    X, names = build_features(ch, {"PS1.rise_time": rise, "KPI.eff": eff, "KPI.p_hyd": k["p_hyd_kw"]})
    published = {"cooler": "100% (Helwig et al. 2015)", "valve": "100% (Helwig et al. 2015)",
                 "leak": "not quoted here", "accumulator": "90.4% (Helwig et al. 2015); 99.65% (Schneider et al. 2017)"}
    models = []
    for target in ["cooler", "valve", "leak", "accumulator"]:
        y = prof[target].to_numpy()
        res = evaluate(X, y)
        tag_imp = {}
        for nm, v in zip(names, res["importance"]):
            tg = nm.split(".")[0]
            tag_imp[tg] = tag_imp.get(tg, 0) + float(v)
        top_feats = sorted(zip(names, res["importance"]), key=lambda z: -z[1])[:6]
        models.append({"target": target, "classes": res["classes"], "acc_blocked": r(res["acc_blocked"], 4),
                       "acc_random": r(res["acc_random"], 4), "acc_majority": r(res["acc_majority"], 4),
                       "published": published[target],
                       "confusion": confusion(y, res["pred_blocked"], res["classes"]).tolist(),
                       "tag_importance": {kk: r(v, 4) for kk, v in sorted(tag_imp.items(), key=lambda z: -z[1])},
                       "top_features": [{"name": a, "imp": r(b, 4)} for a, b in top_feats]})
    rise_by_valve = {str(v): r(np.median(rise[prof.valve == v]), 3) for v in (100, 90, 80, 73)}

    summary = {"n_cycles": n, "n_channels": len(RATES), "rates": RATES, "units": UNITS, "labels": labels,
               "labels_match_doc": labels == documented, "spec": spec,
               "kpi": {"hand": hand, "fit": {"slope": r(slope, 4), "intercept": r(icpt, 3), "r": r(corr, 4),
                                            "resid_sd": r(resid.std(), 3)},
                       "eff_median": r(np.median(eff), 2), "se_median": r(np.median(se), 2),
                       "eff_by_leak": eff_by_leak},
               "rise_by_valve": rise_by_valve, "models": models, "runtime_s": r(time.time() - t0, 1)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "envelope.json").write_text(json.dumps(envelope))
    (out / "kpi_points.json").write_text(json.dumps(kpi_points))
    print(json.dumps({kk: summary[kk] for kk in ("labels_match_doc", "kpi", "rise_by_valve", "runtime_s")}, indent=1))
    print([(s["id"], s["fail"]) for s in spec])
    print([(m["target"], m["acc_blocked"], m["acc_random"], m["acc_majority"], list(m["tag_importance"])[:3]) for m in models])
    print("golden", envelope["n_golden"], "loo FA", loo_alarm, "nongolden alarm", envelope["overall_alarm_rate_nongolden"])
    for c_ in conds:
        print(c_["component"], c_["level"], c_["n"], c_["alarm_rate"], c_["top_tag"])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
