import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hcl.envelope import MAD_SCALE, excursion, fit_envelope
from hcl.kpi import cycle_kpis, hydraulic_power_kw, rise_time_s
from hcl.load import to_10hz
from hcl.model import blocked_groups, channel_features, confusion
from hcl.spec import run_rules

ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "public" / "data" / "summary.json"


def test_hydraulic_power_hand_calc():
    # 150 bar * 8 l/min: 150e5 Pa * 8/60000 m3/s = 2000 W
    assert hydraulic_power_kw(150, 8) == pytest.approx(2.0, rel=1e-12)
    assert hydraulic_power_kw(100, 60) == pytest.approx(10.0)


def test_cycle_kpis_constant_signals():
    n = 3
    ps1 = np.full((n, 6000), 160.0); fs1 = np.full((n, 600), 7.5)
    eps1 = np.full((n, 6000), 2500.0); se = np.full((n, 60), 70.0)
    k = cycle_kpis(ps1, fs1, eps1, se)
    assert k["p_hyd_kw"] == pytest.approx(np.full(n, 2.0))
    assert k["eff_pct"] == pytest.approx(np.full(n, 80.0))
    assert k["se_pct"] == pytest.approx(np.full(n, 70.0))


def test_resample_rates():
    x100 = np.arange(12000, dtype=float).reshape(2, 6000)
    y = to_10hz(x100, 100)
    assert y.shape == (2, 600) and y[0, 0] == pytest.approx(4.5)
    x1 = np.arange(120, dtype=float).reshape(2, 60)
    assert to_10hz(x1, 1).shape == (2, 600) and (to_10hz(x1, 1)[0, :10] == 0).all()
    with pytest.raises(ValueError):
        to_10hz(x1, 3)


def test_rise_time_known_ramp():
    # flat 100 bar for 1 s, linear ramp to 200 bar over 1 s, hold: 10-90 % rise = 0.8 s
    x = np.concatenate([np.full(100, 100.0), np.linspace(100, 200, 101)[1:], np.full(400, 200.0)])
    assert rise_time_s(x, rate=100) == pytest.approx(0.8, abs=0.02)


def test_envelope_false_alarm_rate_on_gaussian():
    rng = np.random.default_rng(0)
    g = rng.normal(0, 1, size=(400, 200))
    c, lo, hi = fit_envelope(g, k=3.0)
    assert np.allclose(c, 0, atol=0.2)
    # 1.4826*MAD ~ sigma, so +/-3 sigma band should exclude ~0.27 % of fresh samples
    frac, _ = excursion(rng.normal(0, 1, size=(400, 200)), lo, hi)
    assert 0.0005 < frac.mean() < 0.006
    assert MAD_SCALE == pytest.approx(1 / 0.6745, rel=1e-3)


def test_excursion_detects_offset():
    lo, hi = np.full(100, -1.0), np.full(100, 1.0)
    x = np.zeros(100); x[50:] = 2.0
    frac, area = excursion(x, lo, hi)
    assert frac[0] == pytest.approx(0.5)
    assert area[0] == pytest.approx(0.5 * 1.0 / 2.0)


def test_spec_rules_flag_injected_faults():
    # SYNTHETIC: two clean cycles, then inject a flatline and an SE dropout
    n = 3
    ch = {f"PS{i}": np.tile(np.linspace(140, 160, 6000), (n, 1)) for i in range(1, 7)}
    ch["EPS1"] = np.full((n, 6000), 2400.0); ch["FS1"] = np.full((n, 600), 8.0); ch["SE"] = np.full((n, 60), 68.0)
    ch["PS1"][1] = 150.0
    ch["SE"][2, 30] = 0.0
    prof = pd.DataFrame({"stable_flag": [0, 0, 1]})
    k = cycle_kpis(ch["PS1"], ch["FS1"], ch["EPS1"], ch["SE"])
    f = run_rules(ch, prof, k)
    assert f["R3"].tolist() == [False, True, False]
    assert f["R5"].tolist() == [False, False, True]
    assert f["R6"].tolist() == [False, False, True]
    assert not f["R7"].any()


def test_features_and_helpers():
    x = np.tile(np.linspace(0, 1, 60), (2, 1))
    f = channel_features(x)
    assert f.shape == (2, 7) and f[0, 6] == pytest.approx(1.0)
    assert blocked_groups(120, 50).tolist()[49:51] == [0, 1]
    m = confusion(np.array([1, 1, 2]), np.array([1, 2, 2]), [1, 2])
    assert m.tolist() == [[1, 1], [0, 1]]


@pytest.mark.skipif(not SUMMARY.exists(), reason="run pipeline first")
class TestPipelineOutputs:
    s = json.loads(SUMMARY.read_text()) if SUMMARY.exists() else {}

    def test_labels_match_documentation(self):
        assert self.s["labels_match_doc"] is True
        assert self.s["n_cycles"] == 2205

    def test_hand_calc_reproduces_pipeline_formula(self):
        h = self.s["kpi"]["hand"]
        assert h["p_bar"] * h["q_lpm"] / 600 == pytest.approx(h["p_hyd_kw"], rel=0.005)
        # hydraulic efficiency must be physically below 100 %
        assert 0 < h["cycle_eff_pct"] < 100

    def test_efficiency_tracks_rig_se_channel(self):
        assert self.s["kpi"]["fit"]["r"] > 0.95

    def test_models_beat_majority_baseline(self):
        for m in self.s["models"]:
            assert m["acc_blocked"] > m["acc_majority"] + 0.2
            assert m["acc_random"] >= m["acc_blocked"] - 0.01  # leakage only inflates


CACHE = Path(__file__).resolve().parents[1] / "cache"


@pytest.mark.skipif(not (CACHE / "PS1.npy").exists() or not SUMMARY.exists(), reason="needs cached raw data")
def test_cycle_power_by_plain_loop_matches_pipeline():
    """Independent hand calc: loop over the 500 10-Hz samples in t = 10..60 s with no numpy vectorisation."""
    s = json.loads(SUMMARY.read_text())["kpi"]["hand"]
    i = s["cycle"]
    ps1 = np.load(CACHE / "PS1.npy")[i].tolist(); fs1 = np.load(CACHE / "FS1.npy")[i].tolist()
    eps1 = np.load(CACHE / "EPS1.npy")[i].tolist()
    p_sum = w_sum = 0.0
    for j in range(100, 600):
        p = sum(ps1[j * 10:(j + 1) * 10]) / 10
        w = sum(eps1[j * 10:(j + 1) * 10]) / 10
        p_sum += p * fs1[j] / 600
        w_sum += w / 1000
    assert p_sum / 500 == pytest.approx(s["cycle_p_hyd_kw"], rel=0.005)
    assert 100 * p_sum / w_sum == pytest.approx(s["cycle_eff_pct"], rel=0.005)
