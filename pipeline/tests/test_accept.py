"""Tests for the acceptance wrapper (pipeline/accept.py)."""
import json
from pathlib import Path

import numpy as np
import pytest

import accept as acc
from hcl.load import load_profile

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "downloads" / "raw"
CACHE = ROOT / "pipeline" / "cache"
DATA = ROOT / "public" / "data"


def test_claim_and_signature_rules():
    # zero alarms: claims follow the rule of three (30 cycles -> <=10 %, 60 -> <=5 %)
    assert acc._claim(0, 29) is None and acc._claim(0, 30) == "≤10%" and acc._claim(0, 60) == "≤5%"
    assert acc._claim(1, 100) is None
    assert acc._signature(["FS1", "PS5"]) == "leakage"
    assert acc._signature(["FS2", "PS6"]) == "accumulator"
    assert acc._signature(["PS4", "PS5"]) == "valve"
    assert acc._signature([]) is None


@pytest.mark.skipif(not (RAW / "profile.txt").exists(), reason="UCI archive not unzipped into downloads/raw")
def test_reproduces_measured_operating_point_on_real_data():
    """With the 30 healthy stable cycles as golden, the wrapper must give the published operating point."""
    x = json.loads((DATA / "extended.json").read_text())
    s = json.loads((DATA / "summary.json").read_text())
    op = x["calibration"]["modes"]["per_context"]["operating_point"]
    prof = load_profile(RAW)
    ok = (prof.valve == 100) & (prof.accumulator == 130) & (prof.stable_flag == 0)
    golden = np.where(ok & (prof.leak == 0))[0]
    assert len(golden) == op["false_alarm"]["n"] == 30

    rep = acc.accept(RAW, golden.tolist(), "cooler", op["k"], op["f"], cache=CACHE, hand_cycle=s["kpi"]["hand"]["cycle"])
    cy = rep["cycles"]

    # 0 of 30 leave-one-out false alarms
    assert sum(cy[i]["alarm"] for i in golden) == op["false_alarm"]["k"] == 0
    # all 60 leakage cycles (both levels) out of band
    for lv in (1, 2):
        ids = np.where(ok & (prof.leak == lv))[0]
        want = next(c for c in op["conditions"] if c["component"] == "leak" and c["level"] == lv)
        assert sum(cy[i]["alarm"] for i in ids) == want["k"] == len(ids) == 30
    # readiness: 10 golden per context, enough for a band, not yet enough for a <=10 % claim
    for v in rep["contexts"].values():
        assert v["n_golden"] == 10 and v["need_more"] == 0 and v["validation_alarms"] == 0
        assert v["need_for_10pct"] == 20 and v["ready_for"] is None
    # golden-count curve matches the published resampling study exactly
    want = {r["n_golden"]: (r["alarms"], r["tests"]) for r in x["calibration"]["sample_size"]["rows"]}
    assert {r["n_golden"]: (r["alarms"], r["tests"]) for r in rep["golden_curve"]} == want
    # hand check matches the KPI hand calculation (166.347 bar x 7.831 l/min / 600)
    assert rep["hand_check"]["p_hyd_kw"] == pytest.approx(s["kpi"]["hand"]["p_hyd_kw"], abs=1e-4)
    # unsteady cycles are labelled as a data problem, not a process alarm
    assert all(c["label"].startswith("DATA") for c in cy if prof.stable_flag[c["id"]] != 0)
