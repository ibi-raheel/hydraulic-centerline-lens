"""Golden-run acceptance check for one line's extract. A thin wrapper over hcl/: no new maths.

Give it the extract, the cycles you call golden and the operating-context column. It returns
  (a) per-cycle data-contract result (R1-R7 range rules + R8-R11 physics rules),
  (b) per-context readiness: golden count, leave-one-out validation alarms, Wilson bound, what claim it supports,
  (c) one label per cycle: "DATA: fix the extract" | "IN BAND" | "OUT OF BAND: investigate", with the tags out of band
      and a signature hint,
  (d) hydraulic efficiency per cycle, plus the hand-check line for one golden cycle (the last, unless --hand is given).

Usage:
  .venv/bin/python -I pipeline/accept.py downloads/raw --golden golden.txt --context cooler \
      --k 3 --f 0.2 --out report.json [--cache pipeline/cache]
golden.txt holds one 0-based cycle (row) index per line.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np

from hcl.load import RATES, load_channel, load_profile, to_10hz
from hcl.kpi import cycle_kpis
from hcl.spec import run_rules
from hcl import calib, mutate, physics
from hcl.stats import wilson, rule_of_three_n

ENV_TAGS = ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2"]
NEEDED = ENV_TAGS + ["SE"]
MIN_GOLDEN = 9          # measured: 0 alarms in 900 held-out tests at 9 golden cycles per context
RULE_SHORT = {"R1": "sample count", "R2": "pressure range", "R3": "flatline", "R4": "motor power range",
              "R5": "SE dropout", "R6": "steady state", "R7": "energy balance", "R8": "tag order",
              "R9": "edge alignment", "R10": "KPI consistency", "R11": "stuck sensor"}
HAND_T = 30             # s, the instant used for the hand check (as in run.py)
PS2_WINDOW = (880, 1000)  # first PS2 switching edge, ~9.4 s (as in run_extended.py)


def _signature(tags_out):
    """Which component the out-of-band tags point at, from where each fault showed up on the rig:
    pump leakage moves main flow FS1; a low accumulator moves FS2 without FS1; a slow valve moves only pressures."""
    s = set(tags_out)
    if "FS1" in s:
        return "leakage"
    if "FS2" in s:
        return "accumulator"
    if s:
        return "valve"
    return None


HINTS = {"leakage": "leakage signature: main flow FS1 out of band",
         "accumulator": "low accumulator signature: FS2 out of band, FS1 in",
         "valve": "pressures only: check valve switching (PS2 edge lag)"}


def _claim(alarms, n):
    if alarms:
        return None
    if n >= rule_of_three_n(0.05):
        return "≤5%"
    if n >= rule_of_three_n(0.10):
        return "≤10%"
    return None


def accept(raw_dir, golden_ids, context_col="cooler", k=3.0, f=0.2, cache=None, curve=True, hand_cycle=None):
    raw_dir = Path(raw_dir)
    ch = {t: load_channel(raw_dir, t, cache) for t in NEEDED}
    prof = load_profile(raw_dir)
    n = len(prof)
    golden = np.zeros(n, bool)
    golden[np.asarray(golden_ids, int)] = True
    ctx = prof[context_col].to_numpy()

    # (a) contract: 7 range rules + 4 physics rules. R10's SE-vs-eta fit is taken over the whole extract, as in run.py.
    kp = cycle_kpis(ch["PS1"], ch["FS1"], ch["EPS1"], ch["SE"])
    eff, se = kp["eff_pct"], kp["se_pct"]
    slope, icpt = np.linalg.lstsq(np.column_stack([eff, np.ones(n)]), se, rcond=None)[0]
    fit = {"slope": float(slope), "intercept": float(icpt), "resid_sd": float((se - (slope * eff + icpt)).std())}
    fails = {**run_rules(ch, prof, kp), **mutate.extra_rules(ch, kp, fit)}
    rule_ids = list(fails)
    F = np.stack([fails[r] for r in rule_ids], axis=1)
    contract = {int(i): [rule_ids[j] for j in np.where(F[i])[0]] for i in range(n) if F[i].any()}

    # (b)+(c) per-context golden band, same scoring as calib.score_contexts("per_context"); golden cycles leave-one-out
    sig = {t: to_10hz(ch[t], RATES[t]).astype(np.float64) for t in ENV_TAGS}
    fr = calib.score_contexts(sig, ctx, None, golden, [k], "per_context")[:, :, 0]   # (tags, n)
    has_band = np.isin(ctx, np.unique(ctx[golden]))
    out_tags = fr > f
    alarm = out_tags.any(axis=0) & has_band

    # valve hint: PS2 switching-edge lag against the context's golden median trace
    ps2 = ch["PS2"].astype(np.float64)
    lag = np.full(n, np.nan)
    lag_ref = {}
    for c in np.unique(ctx[golden]):
        g = golden & (ctx == c)
        tpl = np.median(ps2[g], axis=0)
        a, b = PS2_WINDOW
        e = a + int(np.argmax(np.abs(np.diff(tpl[a:b]))))
        m = ctx == c
        lag[m] = physics.edge_lags(ps2[m], tpl, e)
        lag_ref[c] = float(np.median(lag[g]))

    contexts = {}
    for c in np.unique(ctx):
        g = np.where(golden & (ctx == c))[0]
        a_ = int(alarm[g].sum())
        _, _, hi = wilson(a_, len(g)) if len(g) else (None, None, 1.0)
        contexts[str(c)] = {"n_golden": int(len(g)), "need_more": max(0, MIN_GOLDEN - len(g)),
                            "validation_alarms": a_, "validation_n": int(len(g)), "wilson_hi": round(float(hi), 4),
                            "need_for_10pct": max(0, rule_of_three_n(0.10) - len(g)) if a_ == 0 else None,
                            "need_for_5pct": max(0, rule_of_three_n(0.05) - len(g)) if a_ == 0 else None,
                            "ready_for": _claim(a_, len(g))}

    cycles = []
    for i in range(n):
        tags = [t for ti, t in enumerate(ENV_TAGS) if out_tags[ti, i]] if has_band[i] else []
        hint = None
        if i in contract:
            label = "DATA: fix the extract"
        elif not has_band[i]:
            label = "NO BAND: no golden cycles in this context"
        elif alarm[i]:
            label = "OUT OF BAND: investigate"
            sig_ = _signature(tags)
            hint = HINTS[sig_]
            if sig_ == "valve" and np.isfinite(lag[i]):
                hint += f", {lag[i] - lag_ref[ctx[i]]:+.0f} ms vs golden median"
        else:
            label = "IN BAND"
        cycles.append({"id": i, "context": ctx[i].item(), "golden": bool(golden[i]), "label": label,
                       "failed_rules": contract.get(i, []), "alarm": bool(alarm[i]), "tags_out": tags,
                       "signature": _signature(tags) if alarm[i] and i not in contract else None, "signature_hint": hint, "ps2_lag_ms": None if not np.isfinite(lag[i]) else round(float(lag[i]), 1),
                       "eta_pct": round(float(eff[i]), 2)})

    # (d) hand check: one instant of one golden cycle, eta = (p*Q/600) / P_motor
    h = int(np.where(golden)[0][-1]) if hand_cycle is None else int(hand_cycle)
    i10 = HAND_T * 10
    p = float(ch["PS1"][h, i10 * 10:(i10 + 1) * 10].mean())
    q = float(ch["FS1"][h, i10])
    w = float(ch["EPS1"][h, i10 * 10:(i10 + 1) * 10].mean())
    hand = {"cycle": h, "t_s": HAND_T, "p_bar": round(p, 3), "q_lpm": round(q, 3), "p_motor_w": round(w, 1),
            "p_hyd_kw": round(p * q / 600, 4),
            "line": f"{p:.3f} bar x {q:.3f} l/min / 600 = {p * q / 600:.4f} kW; / {w / 1000:.3f} kW motor = {100 * p * q / 600 / (w / 1000):.2f} %"}

    report = {"k": k, "f": f, "context_col": context_col, "n_cycles": n, "n_golden": int(golden.sum()),
              "contract": {str(i): v for i, v in contract.items()}, "contexts": contexts, "cycles": cycles, "hand_check": hand}
    if curve:
        ns = [m for m in (3, 5, 7, 9) if m < min(v["n_golden"] for v in contexts.values() if v["n_golden"])]
        ss = calib.sample_size_per_context(sig, ctx, golden, k, f, ns) if ns else {}
        report["golden_curve"] = [{"n_golden": m, "fa_mean": round(v[0], 4), "alarms": v[3], "tests": v[4]} for m, v in ss.items()]
    return report


def summary_lines(rep, show=3):
    out = []
    for c, v in rep["contexts"].items():
        if v["n_golden"] == 0:
            out.append(f"context {c}: no golden cycles, no band")
            continue
        s = f"context {c}: {v['n_golden']} golden"
        s += ", ready" if v["need_more"] == 0 else f", need {v['need_more']} more"
        s += f"; {v['validation_alarms']}/{v['validation_n']} validation alarms (Wilson upper {100 * v['wilson_hi']:.1f}%)"
        if v["ready_for"]:
            s += f", supports a {v['ready_for']} false-alarm claim"
        elif v["need_for_10pct"] is not None:
            s += f", {v['need_for_10pct']} more alarm-free cycles for ≤10%"
        out.append(s)
    for want in ("OUT OF BAND: investigate", "DATA: fix the extract"):
        for cy in [c for c in rep["cycles"] if c["label"] == want][:show]:
            extra = " ".join(cy["tags_out"]) + (f", {cy['signature_hint']}" if cy["signature_hint"] else "") if want.startswith("OUT") \
                else "failed " + ", ".join(f"{r} ({RULE_SHORT[r]})" for r in cy["failed_rules"])
            out.append(f"cycle {cy['id']}: {want.split(':')[0]}, {extra}")
    out.append("hand check: " + rep["hand_check"]["line"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir", type=Path)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--context", default="cooler")
    ap.add_argument("--k", type=float, default=3.0)
    ap.add_argument("--f", type=float, default=0.2)
    ap.add_argument("--out", type=Path, default=Path("report.json"))
    ap.add_argument("--cache", type=Path, default=None, help="npy cache for this extract (optional)")
    ap.add_argument("--hand", type=int, default=None, help="cycle for the hand check (default: last golden cycle)")
    ap.add_argument("--no-curve", action="store_true", help="skip the golden-count resampling curve")
    a = ap.parse_args(argv)
    ids = [int(x) for x in a.golden.read_text().split() if x.strip()]
    rep = accept(a.raw_dir, ids, a.context, a.k, a.f, a.cache, curve=not a.no_curve, hand_cycle=a.hand)
    a.out.write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print("\n".join(summary_lines(rep)))


if __name__ == "__main__":
    main()
