"""Matched effect of pump leakage on efficiency, and its energy translation.

Extra motor energy for the same delivered hydraulic work W:
    E_extra = W * (1/eta_leak - 1/eta_ok)
so the relative increase in motor energy is eta_ok/eta_leak - 1.
"""
import numpy as np
import pandas as pd

from .stats import bootstrap_median_ci


def matched_diffs(prof, values, comp="leak", ref=0, level=1, keys=("cooler", "valve", "accumulator")):
    """Within each cell of identical other-component states (stable cycles only), the difference
    median(value | comp=level) - median(value | comp=ref). Returns array over matched cells."""
    df = prof.assign(v=values)
    df = df[df.stable_flag == 0]
    g = df.groupby(list(keys) + [comp])["v"].median().unstack(comp)
    g = g.dropna(subset=[ref, level])
    return (g[level] - g[ref]).to_numpy(), g.index.tolist()


def extra_energy_fraction(eta_ok, eta_leak):
    return eta_ok / eta_leak - 1.0


def energy_table(eta_ok, eta_leak, p_hyd_kw, hours, price_usd_kwh):
    frac = extra_energy_fraction(eta_ok, eta_leak)
    motor_ok = p_hyd_kw / eta_ok
    extra_kw = p_hyd_kw * (1 / eta_leak - 1 / eta_ok)
    kwh = extra_kw * hours
    return {"extra_motor_pct": 100 * frac, "motor_kw_ok": motor_ok, "extra_kw": extra_kw,
            "extra_kwh_yr": kwh, "extra_usd_yr": kwh * price_usd_kwh}


def effect_with_ci(prof, values, level, seed=0):
    d, cells = matched_diffs(prof, values, level=level)
    med, lo, hi = bootstrap_median_ci(d, seed=seed)
    return {"n_cells": len(d), "median": med, "lo": lo, "hi": hi}
