# Hydraulic Centerline Lens

**The question.** When a new production line goes live on a data platform, how many golden runs does a centerline need before its alarms can be trusted, and how do you prove the KPIs and cleansing rules are right before anyone acts on them?

**The answer, measured on 2,205 real cycles.** Copying one golden set across operating conditions gave 70 % false alarms (21 of 30 healthy cycles). About 9 golden cycles per condition fixed it (0 of 30) and still caught all 60 leakage cycles. On injected data defects, adding four physics checks to the range checks lifted the catch rate from 20 % to 96 %.

**The solution.** A one-page acceptance recipe and a small tool, `pipeline/accept.py`: give it a line's extract and the cycles you call golden, and it checks the data against 11 rules, says how many more golden cycles each context needs, and labels every cycle "fix the data", "in band" or "out of band". See **[SOLUTION.md](SOLUTION.md)** for the playbook, the decision thresholds, the week-1 plan and how to run it.

**Live demo:** DEMO_URL_PLACEHOLDER

It runs on a raw multi-rate extract from a real hydraulic test rig and produces hand-checked KPIs, golden-run centerlines and per-component root-cause models.

## The problem
When a team delivers KPIs and models on top of plant data, someone has to show that the numbers are right: that the formula is the right one, that bad cycles are filtered out, and that a "golden run" really is golden. Usually that check is reviewer judgment. This project makes it executable: the spec is a test suite, and every KPI traces back to an equation.

## Key results (measured on 2,205 real cycles)
- **Pump leakage costs efficiency, measured in matched cells:** −3.2 points weak (95 % CI −3.35 to −3.02) and −5.0 points severe (−5.13 to −4.85), which is +3.9 % and +6.4 % motor energy for the same hydraulic work. The KPI η = p·Q/600 / P_motor is worked by hand and tracks the rig's own efficiency channel at r = 0.999.
- **Blocked validation separates the models a plant can trust:** blocked CV (contiguous 50-cycle blocks) with 95 % CIs gives cooler 99.4 % (98.6–100) and pump leakage 96.5 % (92.0–99.5). Accumulator is 77.4 % (69.9–84.7), which shuffled CV overstates as 98.8 %. The gap grows from 0 to 52 points as the validation block grows from 1 to 200 cycles; at the largest blocks part of that drop is extrapolation to unseen condition combinations, not only leakage.
- **Physics features close most of the gap on the two weak targets (blocked CV, 50-cycle blocks):** valve switching lag measured on the PS2 edge (3 / 73 / 176 / 302 ms for valve 100 / 90 / 80 / 73 %) lifts valve from 91.1 % to 99.6 % on blocked CV. The accumulator's first-order time constant (τ = 0.242 → 0.300 s from 90 to 130 bar pre-charge) lifts accumulator from 77.4 % to 89.5 %; the 11 physics features alone reach 91.8 % (86.8–96.1). Accumulator is still the weakest model. In a spot-check at 100- and 200-cycle blocks the valve gain held, but the accumulator score fell well below 89.5 %, so treat that figure as a 50-cycle-block number.
- **Calibrated golden-run centerline:** the original single-context envelope false-alarmed on 21 of 30 healthy cycles. One envelope per operating context, with k and f calibrated, gets 0 of 30 (95 % upper bound 11.4 %; k and f were chosen on these same 30 cycles, so expect a somewhat higher rate on new data). At that point it catches 100 % of leakage cycles and of 100/90 bar pre-charge cycles, but only 77 % at 115 bar and 33–47 % of valve faults (mean detection 74 %). On these 30 cycles the envelope stabilises at 7–9 golden cycles per context; quoting a false-alarm rate of 5 % or less needs 60 alarm-free cycles per context.
- **The data contract now catches real defect types:** in a labelled synthetic mutation test, the 7 range rules caught 1 of 5 defect types. 4 physics rules (tag order, edge alignment, η–SE consistency, stuck sensor) raise the catch rate to 96 %, while failing on 11 of 2,205 real cycles. The 4 rules were written after seeing which defects slipped through, so this is not an independent test.

## What it does
1. **Data contract**: 11 rules (range, flatline, dropout, steady state, energy balance, tag order, time alignment, KPI consistency, stuck sensor) with pass/fail counts and a mutation test.
2. **KPI validation**: hydraulic power P = p·Q/600 is worked by hand for one cycle and recomputed independently.
3. **Golden-run centerline**: robust median ± k·MAD envelopes per operating context, with a calibrated operating point, Wilson confidence intervals and a golden sample-size study.
4. **Root cause**: one random forest per component on summary and physics features (step-response τ, switching-edge lag), scored with blocked cross-validation and block-bootstrap CIs, and compared like for like with published results.

## How it works
- `pipeline/hcl/`: loader and resampling to a common 10 Hz grid, spec rules, KPIs, envelopes and calibration, physics features, statistics, value analysis, mutations (numpy, pandas, scipy, scikit-learn).
- `pipeline/run.py` (about 20 s) and `pipeline/run_extended.py` (about 2.5 min) run the full pipeline offline and write static JSON to `public/data/`.
- `pipeline/accept.py`: the acceptance tool, a thin wrapper over `hcl/` (see SOLUTION.md).
- `pipeline/tests/`: 36 pytest tests, including hand calculations, synthetic recoveries (labelled) and checks on the outputs.
- The front end is Vite + React and reads only the precomputed JSON, so it needs no API keys.
- See [METHOD.md](METHOD.md) for the equations, validation, limitations and a week-1 deployment plan.

## Run locally
```bash
npm install
npm run dev
# pipeline (optional): see METHOD.md "Reproduce"
```

## Data
Real measurements from *Condition monitoring of hydraulic systems* by N. Helwig, E. Pignanelli and A. Schütze (2015), UCI ML Repository, doi:10.24432/C5CW21, licensed **CC BY 4.0**. The full dataset is used (2,205 cycles × 17 channels). Apart from the labelled synthetic mutation test of the data contract (corruptions injected into real cycles) and synthetic signals in unit tests, no synthetic data enters the results.

---
Built by Ibi Raheel, mechanical engineer building AI tools. More work at [ibiraheel.com](https://ibiraheel.com).
