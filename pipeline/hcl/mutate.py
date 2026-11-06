"""Mutation testing for the data contract (SYNTHETIC corruptions applied to real cycles).

Each mutation reproduces a common delivery defect; offset drift follows the sensor-fault types
studied on this rig by Helwig & Schuetze (2015). The added rules R8-R11 are physics checks:
  R8  tag order:      median(PS1) >= median(PS2)   (pump outlet is upstream of the valve)
  R9  time alignment: PS1 falling edge - PS2 rising edge at the 9.4 s switch in [0.10, 0.35] s
  R10 KPI consistency: |SE - (a*eta + b)| <= 4 residual SD, coefficients frozen from the accepted data
  R11 stuck sensor:   no run of >= 200 samples (2 s) with zero change in PS1
"""
import numpy as np

PSI_PER_BAR = 14.5037738


def mutations():
    def psi(ch):
        for i in range(1, 7):
            ch[f"PS{i}"] = ch[f"PS{i}"] * PSI_PER_BAR
    def swap(ch):
        ch["PS1"], ch["PS2"] = ch["PS2"].copy(), ch["PS1"].copy()
    def shift(ch):
        ch["PS1"] = np.roll(ch["PS1"], 100, axis=1)
    def drift(ch):
        ch["PS1"] = ch["PS1"] + np.linspace(0, 10.0, ch["PS1"].shape[1])[None, :]
    def freeze(ch):
        x = ch["PS1"]; x[:, 3000:] = x[:, 2999:3000]
    return {"unit_bar_to_psi": psi, "tag_swap_PS1_PS2": swap, "misalign_PS1_1s": shift,
            "offset_drift_PS1_0to10bar": drift, "flatline_PS1_last_30s": freeze}


def edge_time(x, thr, a, b, up):
    seg = x[a:b]
    i = int(np.argmax(seg >= thr)) if up else int(np.argmax(seg <= thr))
    if (seg[i] >= thr) != up and (seg[i] <= thr) == up:
        return np.nan
    j = a + i
    y0, y1 = x[j - 1], x[j]
    return (j - 1 + (thr - y0) / (y1 - y0 if y1 != y0 else 1.0)) / 100.0


def extra_rules(ch, kpis, fit):
    n = ch["PS1"].shape[0]
    out = {}
    out["R8"] = np.median(ch["PS1"], axis=1) < np.median(ch["PS2"], axis=1)
    t1 = np.array([edge_time(ch["PS1"][i], 170, 850, 1300, up=False) for i in range(n)])
    t2 = np.array([edge_time(ch["PS2"][i], 60, 800, 1200, up=True) for i in range(n)])
    d = t1 - t2
    out["R9"] = ~((d >= 0.10) & (d <= 0.35))
    resid = kpis["se_pct"] - (fit["slope"] * kpis["eff_pct"] + fit["intercept"])
    out["R10"] = np.abs(resid) > 4 * fit["resid_sd"]
    x = ch["PS1"]
    same = np.diff(x, axis=1) == 0
    longest = np.zeros(n, int)
    for i in range(n):
        s = same[i].astype(np.int8)
        if s.any():
            edges = np.diff(np.r_[0, s, 0])
            longest[i] = int((np.where(edges == -1)[0] - np.where(edges == 1)[0]).max())
    out["R11"] = longest >= 200
    return out
