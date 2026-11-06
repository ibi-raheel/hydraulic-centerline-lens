"""Tests for calibration, physics features, uncertainty and value analysis."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from hcl import calib, mutate, physics, value
from hcl.stats import block_bootstrap_acc, bootstrap_median_ci, rule_of_three_n, wilson

ROOT = Path(__file__).resolve().parents[2]
EXT = ROOT / "public" / "data" / "extended.json"


# ---------- uncertainty ----------
def test_wilson_known_values():
    z2 = 1.959963984540054 ** 2
    p, lo, hi = wilson(0, 30)
    assert p == 0 and lo == 0 and hi == pytest.approx(z2 / (30 + z2), rel=1e-9)   # 0.1135
    p, lo, hi = wilson(5, 10)
    assert (lo, hi) == pytest.approx((0.2366, 0.7634), abs=1e-4)


def test_rule_of_three():
    assert rule_of_three_n(0.05) == 60 and rule_of_three_n(0.10) == 30 and rule_of_three_n(0.01) == 300


def test_block_bootstrap():
    assert block_bootstrap_acc(np.ones(200)) == (1.0, 1.0, 1.0)
    c = np.r_[np.ones(150), np.zeros(50)]
    m, lo, hi = block_bootstrap_acc(c, block=50)
    assert m == 0.75 and lo < 0.75 < hi
    med, lo, hi = bootstrap_median_ci(np.arange(101.0))
    assert med == 50 and lo < 50 < hi


# ---------- calibration ----------
@pytest.mark.parametrize("k", [2.0, 2.5, 3.0])
def test_envelope_false_alarm_matches_gaussian_theory(k):
    """SYNTHETIC Gaussian noise: fraction of bins with robust z > k should be 2*(1 - Phi(k))."""
    rng = np.random.default_rng(1)
    g = rng.normal(5.0, 2.0, size=(5000, 200))
    med, mad = calib.fit_robust(g, 1e-9)
    z = np.abs(rng.normal(5.0, 2.0, size=(3000, 200)) - med) / mad
    frac = calib.exceed_frac(z, [k])[:, 0].mean()
    assert frac == pytest.approx(2 * (1 - norm.cdf(k)), rel=0.08)


def test_detrend_removes_linear_temperature_effect():
    """SYNTHETIC: signal = 3 + 0.5*T + noise; after the per-bin detrend, residual z is ~N(0,1)-scaled."""
    rng = np.random.default_rng(2)
    T = rng.uniform(35, 57, 400)
    g = 3 + 0.5 * T[:, None] + rng.normal(0, 0.1, (400, 20))
    model = calib.fit_detrend(g, T)
    assert model[1] == pytest.approx(np.full(20, 0.5), abs=0.01)
    z = calib.z_detrend(g, T, model)
    assert np.median(z) == pytest.approx(0.6745, abs=0.05)


def test_alarm_from_frac_shapes():
    fr = np.zeros((2, 3, 1)); fr[1, 2, 0] = 0.3
    a = calib.alarm_from_frac(fr, [0.05, 0.5])
    assert a.shape == (3, 1, 2) and a[2, 0, 0] and not a[2, 0, 1] and not a[0].any()


# ---------- physics ----------
def test_step_fit_recovers_tau():
    """SYNTHETIC first-order step, tau = 0.25 s, 0.1 bar noise."""
    t = np.arange(300) / 100
    rng = np.random.default_rng(3)
    seg = physics.first_order(t, 147.0, 191.0, 0.25) + rng.normal(0, 0.1, 300)
    p_inf, p0, tau, rmse = physics.fit_step(seg)
    assert tau == pytest.approx(0.25, rel=0.02) and p_inf == pytest.approx(147, abs=0.1) and rmse < 0.15


def test_align_lag_subsample():
    """SYNTHETIC smooth edge delayed by 23.4 samples is recovered to within 0.2 samples."""
    i = np.arange(2000, dtype=float)
    tpl = 100 / (1 + np.exp(-(i - 900) / 4.0))
    x = 100 / (1 + np.exp(-(i - 923.4) / 4.0))
    assert physics.align_lag(x, tpl, 900) == pytest.approx(23.4, abs=0.2)
    assert physics.edge_lags(x[None], tpl, 900)[0] == pytest.approx(234.0, abs=2.0)


def test_loglog_slope_of_power_law():
    p0 = np.array([90, 100, 115, 130.0])
    assert physics.loglog_slope(p0, np.log(0.01 * p0 ** (1 / 1.4))) == pytest.approx(1 / 1.4)


# ---------- value ----------
def test_energy_hand_calc():
    # 10 kW hydraulic, eta 0.80 -> 0.75: extra = 10*(1/0.75 - 1/0.80) = 0.8333 kW; 4000 h; $0.10/kWh
    e = value.energy_table(0.80, 0.75, 10.0, 4000, 0.10)
    assert e["extra_kw"] == pytest.approx(0.833333, rel=1e-5)
    assert e["extra_kwh_yr"] == pytest.approx(3333.33, rel=1e-5)
    assert e["extra_usd_yr"] == pytest.approx(333.333, rel=1e-5)
    assert e["extra_motor_pct"] == pytest.approx(100 * (0.80 / 0.75 - 1))


def test_matched_diffs():
    prof = pd.DataFrame({"cooler": [3, 3, 100, 100], "valve": [100] * 4, "accumulator": [130] * 4,
                         "leak": [0, 1, 0, 1], "stable_flag": [0, 0, 0, 0]})
    d, cells = value.matched_diffs(prof, np.array([80.0, 77.0, 84.0, 80.0]), level=1)
    assert sorted(d.tolist()) == [-4.0, -3.0] and len(cells) == 2


# ---------- contract mutations ----------
def test_mutations_and_extra_rules():
    """SYNTHETIC: a PS1/PS2 tag swap is caught by the tag-order rule; a frozen tail by the stuck-sensor rule."""
    n = 2
    t = np.arange(6000)
    ps1 = np.where((t > 943) & (t < 1940), 147.0, 191.0) + 0.01 * np.sin(t)
    ps2 = np.where((t > 936) & (t < 1940), 125.0, 0.0) + 0.01 * np.cos(t)
    ch = {"PS1": np.tile(ps1, (n, 1)), "PS2": np.tile(ps2, (n, 1))}
    k = {"se_pct": np.array([68.0, 68.0]), "eff_pct": np.array([82.0, 82.0])}
    fit = {"slope": 0.756, "intercept": 6.0, "resid_sd": 0.45}
    f = mutate.extra_rules(ch, k, fit)
    assert not f["R8"].any() and not f["R11"].any()
    m = mutate.mutations()
    sw = {kk: v.copy() for kk, v in ch.items()}; m["tag_swap_PS1_PS2"](sw)
    assert mutate.extra_rules(sw, k, fit)["R8"].all()
    fz = {kk: v.copy() for kk, v in ch.items()}; m["flatline_PS1_last_30s"](fz)
    assert mutate.extra_rules(fz, k, fit)["R11"].all()
    ps = {f"PS{i}": np.full((1, 10), 150.0) for i in range(1, 7)}; m["unit_bar_to_psi"](ps)
    assert ps["PS3"][0, 0] == pytest.approx(2175.57, abs=0.01)


# ---------- pipeline outputs ----------
@pytest.mark.skipif(not EXT.exists(), reason="run run_extended.py first")
class TestExtendedOutputs:
    e = json.loads(EXT.read_text()) if EXT.exists() else {}

    def test_calibrated_envelope_meets_false_alarm_bound(self):
        c = self.e["calibration"]
        op = c["modes"][c["chosen"]]["operating_point"]
        assert op["false_alarm"]["k"] == 0 and op["false_alarm"]["hi"] <= 0.12
        assert c["modes"]["single_context"]["at_k4_f5"]["false_alarm"]["k"] > 10   # the uncalibrated reference fails

    def test_sample_size_curve_falls(self):
        rows = self.e["calibration"]["sample_size"]["rows"]
        fa = [r_["fa_mean"] for r_ in rows]
        assert fa == sorted(fa, reverse=True)

    def test_physics_features_lift_blocked_accuracy(self):
        m = {r_["target"]: r_ for r_ in self.e["models"]}
        for t in ("valve", "accumulator"):
            assert m[t]["with_physics"]["blocked"] > m[t]["base"]["blocked"] + 0.05

    def test_valve_lag_is_monotonic_in_valve_state(self):
        lag = self.e["physics"]["valve_lag_PS2_ms"]
        assert lag["100"]["median"] < lag["90"]["median"] < lag["80"]["median"] < lag["73"]["median"]

    def test_accumulator_tau_monotonic_and_exponent_reported(self):
        tau = self.e["physics"]["tau1_by_acc_cooler100_s"]
        assert tau["90"]["median"] < tau["100"]["median"] < tau["115"]["median"] < tau["130"]["median"]
        s = self.e["physics"]["loglog_slope"]
        assert 0 < s["lo"] <= s["value"] <= s["hi"] < 1.0

    def test_accumulator_leakage_gap_grows_with_block_size(self):
        accs = [r_["acc"] for r_ in self.e["block_sensitivity"]["accumulator"]["rows"]]
        assert accs == sorted(accs, reverse=True)

    def test_matched_leak_effect_negative_with_ci(self):
        for lv in ("leak1", "leak2"):
            e = self.e["value"][lv]["eff_pts"]
            assert e["lo"] <= e["median"] <= e["hi"] < 0 and e["n_cells"] >= 40
