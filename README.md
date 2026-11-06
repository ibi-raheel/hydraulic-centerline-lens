# Hydraulic Centerline Lens

An acceptance kit for plant sensor data. It turns a raw multi-rate extract from a real hydraulic test rig into hand-checked KPIs, golden-run centerlines and per-component root-cause models.

**Live demo:** DEMO_URL_PLACEHOLDER

## The problem
When a team delivers KPIs and models on top of plant data, someone has to show that the numbers are right: that the formula is the right one, that bad cycles are filtered out, and that a "golden run" really is golden. Usually that check is reviewer judgment. This project makes it executable: the spec is a test suite, and every KPI traces back to an equation.

## What it does
1. **Data contract**: 7 rules (range, flatline, dropout, steady state, energy balance) with pass/fail counts over 2,205 cycles.
2. **KPI validation**: hydraulic power P = p·Q/600 is worked by hand for one cycle and recomputed independently. The derived efficiency tracks the rig's own efficiency channel at r = 0.999.
3. **Golden-run centerline**: median ± 4·MAD envelopes per tag from the 10 golden cycles. Each fault leaves its own pattern of tags outside the band.
4. **Root cause**: one random forest per component, scored with blocked cross-validation and compared against majority-class and published baselines.

## How it works
- `pipeline/hcl/`: loader and resampling to a common 10 Hz grid, spec rules, KPIs, robust envelopes, features and models (numpy, pandas, scikit-learn).
- `pipeline/run.py`: runs the full pipeline offline (about 20 s) and writes static JSON to `public/data/`.
- `pipeline/tests/`: 13 pytest tests, including hand calculations and checks on the outputs.
- The front end is Vite + React and reads only the precomputed JSON, so it needs no API keys.
- See [METHOD.md](METHOD.md) for the equations, validation and limitations.

## Run locally
```bash
npm install
npm run dev
# pipeline (optional): see METHOD.md "Reproduce"
```

## Data
Real measurements from *Condition monitoring of hydraulic systems* by N. Helwig, E. Pignanelli and A. Schütze (2015), UCI Machine Learning Repository, doi:10.24432/C5CW21, licensed **CC BY 4.0**. The full dataset is used (2,205 cycles × 17 channels). No synthetic data enters the results.

---
Built by Ibi Raheel, mechanical engineer building AI tools. More work at [ibiraheel.com](https://ibiraheel.com).
