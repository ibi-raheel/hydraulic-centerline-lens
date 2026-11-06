"""Per-cycle KPIs. Units: p in bar, Q in l/min, power in kW.

P_hyd [kW] = p [bar] * Q [l/min] / 600
  (1 bar = 1e5 Pa, 1 l/min = 1/60000 m^3/s  ->  1e5/60000/1000 = 1/600 kW)
"""
import numpy as np

from .load import to_10hz


def hydraulic_power_kw(p_bar, q_lpm):
    return np.asarray(p_bar) * np.asarray(q_lpm) / 600.0


def cycle_kpis(ps1, fs1, eps1, se):
    """Return dict of per-cycle arrays. ps1/eps1 at 100 Hz, fs1 at 10 Hz, se at 1 Hz.
    Window: t = 10..60 s, after start-up transients (SE reads 0 for the first 8 s of every cycle)."""
    p10 = to_10hz(ps1, 100)[:, 100:]
    q10 = fs1[:, 100:]
    w10 = to_10hz(eps1, 100)[:, 100:] / 1000.0
    p_hyd = hydraulic_power_kw(p10, q10).mean(axis=1)
    p_motor = w10.mean(axis=1)
    eff = 100.0 * p_hyd / p_motor
    se_mean = se[:, 10:].mean(axis=1)
    return {"p_hyd_kw": p_hyd, "p_motor_kw": p_motor, "eff_pct": eff, "se_pct": se_mean,
            "ps1_mean_bar": p10.mean(axis=1), "fs1_mean_lpm": q10.mean(axis=1)}


def rise_time_s(ps1_row, rate=100):
    """10-90 % rise time of the first pressure build-up in a cycle (seconds)."""
    x = np.asarray(ps1_row, dtype=float)
    lo, hi = np.percentile(x, 2), np.percentile(x, 98)
    a, b = lo + 0.1 * (hi - lo), lo + 0.9 * (hi - lo)
    i_a = int(np.argmax(x >= a))
    after = x[i_a:]
    i_b = i_a + int(np.argmax(after >= b))
    return (i_b - i_a) / rate
