"""Data contract: each rule is a vectorised check returning a boolean 'fail' mask per cycle."""
import numpy as np

RULES = [
    {"id": "R1", "name": "Sample count matches declared rate",
     "rule": "n_samples == 60 s * rate (6000 / 600 / 60)"},
    {"id": "R2", "name": "Pressure within transducer range",
     "rule": "0 <= PS1..PS6 <= 200 bar"},
    {"id": "R3", "name": "No flatlined pressure channel",
     "rule": "std(PS1) > 0.5 bar within cycle"},
    {"id": "R4", "name": "Motor power physically plausible",
     "rule": "1.5 kW <= EPS1 <= 3.5 kW"},
    {"id": "R5", "name": "Efficiency factor dropout",
     "rule": "SE == 0 for t >= 10 s (outside the known 8 s start-up zero)"},
    {"id": "R6", "name": "Steady state reached",
     "rule": "stable_flag == 0"},
    {"id": "R7", "name": "Hydraulic power below motor power",
     "rule": "P_hyd < P_motor (energy balance)"},
]


def run_rules(ch, profile, kpis):
    n = profile.shape[0]
    rate = {"PS1": 6000, "EPS1": 6000, "FS1": 600, "SE": 60}
    out = {}
    out["R1"] = np.zeros(n, bool) | any(ch[t].shape[1] != rate[t] for t in rate)
    ps = np.stack([ch[f"PS{i}"] for i in range(1, 7)])
    out["R2"] = ((ps < 0) | (ps > 200)).any(axis=(0, 2))
    out["R3"] = ch["PS1"].std(axis=1) <= 0.5
    out["R4"] = ((ch["EPS1"] < 1500) | (ch["EPS1"] > 3500)).any(axis=1)
    out["R5"] = (ch["SE"][:, 10:] == 0).any(axis=1)
    out["R6"] = profile["stable_flag"].to_numpy() != 0
    out["R7"] = kpis["p_hyd_kw"] >= kpis["p_motor_kw"]
    return out
