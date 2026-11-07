# Method

## Research question
When a new production line goes live on a data platform, how many golden runs does a centerline need before its alarms can be trusted, and how do you prove the KPIs and cleansing rules are right before anyone acts on them?

Measured answer on this dataset: one golden set copied across operating contexts false-alarmed on 21 of 30 healthy cycles; one band per context gets 0 of 30 and needs about 9 golden cycles per context (pipeline step 7). The 11-rule contract catches 95.7 % of injected defects (mean over 5 synthetic defect types) against 20 % for the 7 range rules (pipeline step 11), and the efficiency KPI is checked by hand (pipeline step 4). The resulting recipe and tool are in [SOLUTION.md](SOLUTION.md).

All numbers come from `pipeline/run.py` and `pipeline/run_extended.py` run on the full public dataset. Nothing is hand-entered or simulated. The only synthetic inputs are in unit tests and in the contract mutation test (section 10), and they are labelled.

## Data
- **Dataset:** *Condition monitoring of hydraulic systems*, N. Helwig, E. Pignanelli, A. Schütze (2015), UCI ML Repository, doi:10.24432/C5CW21. **Licence: CC BY 4.0.**
- **Size:** 2,205 load cycles of 60 s each, 17 channels at three rates: PS1–PS6 pressure (bar) and EPS1 motor power (W) at 100 Hz; FS1–FS2 volume flow (l/min) at 10 Hz; TS1–TS4 temperature, VS1 vibration, CE/CP virtual cooling efficiency/power and SE efficiency factor at 1 Hz. About 73 MB zipped, 700 MB as text. **The full set is used, with no subsetting.**
- **Labels** (per cycle): cooler (3/20/100 %), valve (73/80/90/100 %), internal pump leakage (0/1/2), accumulator pre-charge (90/100/115/130 bar), stable flag.

## Pipeline (`pipeline/hcl/`)
1. **Load** (`load.py`): read each tab-separated matrix (rows = cycles), cache as `.npy`.
2. **Common grid** (`to_10hz`): 100 Hz → mean of 10-sample blocks (a boxcar anti-alias filter, then decimate); 10 Hz is kept as is; 1 Hz → zero-order hold.
3. **Data contract** (`spec.py`): 7 rules, each a vectorised check that returns a per-cycle fail mask (sample count, transducer range, flatline, motor power range, SE dropout after start-up, steady state, energy balance).
4. **KPIs** (`kpi.py`), over the window t = 10–60 s (SE reads exactly 0 for the first 8 s of every cycle, so start-up is excluded):

   P_hyd [kW] = p [bar] · Q [l/min] / 600

   because 1 bar = 10^5 Pa and 1 l/min = 1/60 000 m³/s, so 10^5 / 60 000 / 1000 = 1/600 kW. With p = PS1 (pump outlet) and Q = FS1 (main flow), the cycle value is the mean of the instantaneous product over the window.

   η = 100 · mean(P_hyd) / mean(EPS1/1000)

   **PS1 rise time** is the 10–90 % time of the first pressure build-up, using the 2nd and 98th percentiles as the low and high levels.
5. **Golden-run centerline** (`envelope.py`): the golden set follows the spec: cooler 100 %, valve 100 %, no leakage, accumulator 130 bar, stable flag 0. That gives **10 cycles**. For each tag (PS1–PS6, EPS1, FS1, FS2) and each 0.1 s bin:

   band = median ± k · 1.4826 · MAD,  k = 4

   with a floor on the scaled MAD of 1 % of the golden robust range (2nd–98th percentile), so bins where all 10 golden cycles agree exactly don't give a zero-width band. The excursion score is the fraction of bins outside the band, plus the out-of-band area normalised by the median band width. A cycle alarms when any tag has more than 5 % of its bins outside the band.
6. **Root cause** (`model.py`): there are 7 statistics per channel (mean, std, min, max, p10, p90, linear slope) × 17 channels, plus PS1 rise time, η and P_hyd, for 122 features in total. One random forest per component (200 trees, min_samples_leaf = 2). Importances are summed back to the physical tag.

7. **Calibrated centerline** (`calib.py`). The reference set is every stable cycle with all three components healthy: **30 cycles, 10 at each cooler level** (3/20/100 %). Robust score per bin z = |x − centre| / max(1.4826·MAD, floor); a cycle alarms at (k, f) when on any tag more than a fraction f of bins have z > k. Three references are compared:
   - *single context* (the original build): one envelope from the 10 cooler-100 % cycles, applied to every cycle;
   - *per context*: one envelope per cooler level from that level's 10 healthy cycles;
   - *pooled + temperature detrend*: all 30 healthy cycles after removing, bin by bin, a least-squares linear trend in cycle-mean oil temperature TS1 (x = a + b·T).
   False alarms are scored **leave-one-out over all 30 healthy cycles**. k is swept over {2, 2.5, 3, 3.5, 4, 5, 6, 7, 8} and f over {1, 2, 5, 10, 15, 20} %. Detection is measured on the 8 single-fault conditions (valve 90/80/73, leak 1/2, accumulator 115/100/90) over **all cooler levels**, stable cycles only (n = 30–39 each). The operating point maximises mean detection subject to a Wilson 95 % upper bound on false alarms of at most 12 % (that is, 0 alarms in 30).
   Wilson interval: (p + z²/2n ± z·√(p(1−p)/n + z²/4n²)) / (1 + z²/n), z = 1.96. Rule of three: 0 alarms in n cycles bounds the rate below 3/n at about 95 %.
8. **Physics features** (`physics.py`). PS1 has five set-point steps at t = 9.43, 19.03, 29.14, 39.08, 49.07 s (steepest point of the golden median). After each step a first-order response is fitted over 3 s at 100 Hz with `scipy.optimize.curve_fit`:

   p(t) = p∞ + (p₀ − p∞)·e^(−t/τ),  τ = R_h·C

   For a gas-charged accumulator with polytropic exponent n and pre-charge p₀, the capacitance at operating pressure p is

   C_acc = dV/dp = V₀·p₀^(1/n) / (n·p^(1+1/n))

   so at fixed p, τ ∝ p₀^(1/n), and the slope of ln τ against ln p₀ should lie between 1/1.4 = 0.714 (adiabatic) and 1 (isothermal). The check uses the 9.43 s step on stable cycles at cooler 100 % only (TS1 35.6–36.3 °C), so no viscosity correction is needed.
   **Valve switching lag**: the PS2 pressure edge at the 9.4 s switch (and at the other four steps) is aligned to the golden-run median edge by least-squares template matching (minimum SSE over integer lags, the SSE form of cross-correlation), with a parabola through the three SSE values around the minimum for sub-sample resolution; also PS1 at the 9.43 s edge. 11 features in total (5 τ, 6 lags). PS4 was not used: its golden median is flat to within 0.09 bar, so it has no edge to align.
9. **Uncertainty and leakage sensitivity.** Accuracy CIs: bootstrap over contiguous 50-cycle blocks of the out-of-fold predictions (2,000 resamples), which keeps the correlation between neighbouring cycles. Block-size sensitivity: blocked GroupKFold(5) with block = 1, 10, 25, 50, 100, 200 cycles.
10. **Value** (`value.py`). Matched effect of leakage: within each cell of identical cooler, valve and accumulator state (stable cycles; 48 cells have both leak 0 and leak 1/2), the difference of median η; median over cells with a bootstrap 95 % CI. For the same delivered hydraulic work W, extra motor energy is W·(1/η_leak − 1/η_ok), a relative increase of η_ok/η_leak − 1. Scaled per 10 kW of delivered hydraulic power at 4,000 h/yr (two shifts) and 9.64 ¢/kWh (U.S. EIA, *Electric Power Monthly*, Table 5.6.A, industrial sector, U.S. total, August 2026, preliminary; accessed 2026-11-06).
11. **Contract mutation test** (`mutate.py`, SYNTHETIC corruptions of 150 real clean cycles): bar→psi unit swap, PS1/PS2 tag swap, PS1 shifted by 1 s, PS1 offset drift 0 → 10 bar over the cycle (the drift fault type studied on this rig by Helwig & Schütze 2015), PS1 frozen for the last 30 s. Four physics rules were added: R8 tag order median(PS1) ≥ median(PS2); R9 PS1 falling edge minus PS2 rising edge at the 9.4 s switch within 0.10–0.35 s; R10 |SE − (0.756·η + 5.69)| ≤ 4 residual SD; R11 no run of ≥ 2 s with zero change in PS1.

## Validation
| Check | Result |
|---|---|
| Hand calc of P_hyd at one instant (cycle 1790, t = 30 s) | 166.347 bar × 7.831 l/min / 600 = 2.171 kW, reproduced in a test |
| Cycle-mean P_hyd and η recomputed by a plain Python loop (no numpy) | matches the pipeline within 0.5 % (test) |
| Formula check with round numbers | 150 bar × 8 l/min = 2.000 kW exactly (test) |
| Label counts vs dataset documentation | all 5 label columns match exactly |
| Derived η vs the rig's own SE channel | r = 0.9991, SE ≈ 0.756·η + 5.69, residual SD 0.45 pts. SE's formula is undocumented, so this shows the two agree; it does not show they are identical. η median 82.3 % vs SE median 68.1 % |
| Energy balance P_hyd < P_motor | 0 violations in 2,205 cycles |
| Envelope statistics on Gaussian noise | a ±3σ MAD band excludes about 0.27 % of samples, as theory predicts (test) |
| Golden-envelope false alarms, leave-one-out | original: 1 of 10 golden cycles alarms. On all 30 healthy cycles the original envelope alarms on 21 (70 %, 95 % CI 52–83 %). Calibrated per-context envelope: 0 of 30 (95 % upper bound 11.4 %) |
| Wilson interval | wilson(0, 30) upper = z²/(30 + z²) = 0.1135 and wilson(5, 10) = 0.237–0.763 (test) |
| Robust envelope tail rate on Gaussian noise | fraction of z > k matches 2(1 − Φ(k)) within 8 % at k = 2, 2.5, 3 (test) |
| Step-response fit | recovers τ = 0.25 s on a synthetic first-order step with 0.1 bar noise within 2 % (test). On real data: 0 fit failures in 11,025 fits, median RMSE 0.09–0.16 bar |
| Sub-sample edge alignment | recovers a 23.4-sample delay on a synthetic edge within 0.2 samples (test) |
| Energy hand calc | 10 kW, η 0.80 → 0.75: 10·(1/0.75 − 1/0.80) = 0.833 kW, × 4,000 h = 3,333 kWh, × $0.10 = $333 (test) |
| Classifiers vs majority-class baseline | every component beats the baseline by more than 20 pts on blocked CV (test) |
| Classifiers vs published results, like for like | The papers used random splits, so the comparable numbers are the shuffled scores: valve 98.5 % vs 100 % (Helwig et al. 2015); accumulator 98.8 % vs 90.4 % (Helwig et al. 2015) and 99.65 % (Schneider et al. 2017). The blocked score is the deployment number. A published leakage figure is not reported here because it was not verified from the source |

### Why blocked cross-validation
The rig steps through the condition grid in order, and adjacent cycles are near-duplicates. A shuffled K-fold therefore puts the neighbours of every test cycle in the training set. The pipeline reports both scores: GroupKFold(5) over contiguous 50-cycle blocks (the less optimistic number, though not leakage-free: see the block-size curve) and a shuffled KFold(5). The gap between them estimates the leakage.

## Results (measured)
Blocked CV with 95 % block-bootstrap CI. "+ physics" adds the 11 physics features to the 122; "physics only" uses the 11 alone.

| Component | Blocked CV (122 features) | Blocked + physics | Physics only (11) | Shuffled CV | Majority |
|---|---|---|---|---|---|
| Cooler | 99.4 % (98.6–100) | 99.4 % (98.6–100) | 96.7 % | 99.9 % | 33.6 % |
| Valve | 91.1 % (87.4–94.4) | **99.6 % (98.8–100)** | 99.7 % (99.2–100) | 98.5 % | 51.0 % |
| Pump leakage | 96.5 % (92.0–99.5) | 96.6 % (92.0–99.7) | 76.7 % | 99.7 % | 55.4 % |
| Accumulator | 77.4 % (69.9–84.7) | **89.5 % (83.3–95.2)** | **91.8 % (86.8–96.1)** | 98.8 % | 36.6 % |

**Physics features close most of the gap on the blocked split (50-cycle blocks).** In a spot-check at 100- and 200-cycle blocks the valve gain held, but the accumulator score fell well below 89.5 %, so the accumulator figure is specific to 50-cycle blocks.
- **Valve switching lag**, measured on the PS2 edge against the golden median: 3 ms (100 %), 73 ms (90 %), 176 ms (80 %), 302 ms (73 %), each with a bootstrap CI under ±1 ms. The forest's top two features become the PS2 and PS1 edge lags, and valve accuracy on blocked CV goes from 91.1 % to 99.6 %. This also closes the refuted PRD hypothesis: valve lag lives in the timing of the switching edge, not in PS1 rise time at cycle start.
- **Accumulator time constant** at the 9.43 s step (cooler 100 %): τ = 0.242, 0.265, 0.286, 0.300 s for 90, 100, 115, 130 bar, monotonic as the gas law predicts. The fitted exponent, slope of ln τ against ln p₀, is **0.579 (95 % CI 0.573–0.585)**, below the adiabatic bound of 0.714. A pure-accumulator model does not explain the magnitude. A constant compliance in parallel (hose and line, τ = R(C_line + K·p₀^(1/n))) fits the four levels within 3.7 ms RMSE (n = 1.4, non-accumulator part 0.056 s, about 19 % of τ at 130 bar). That is consistent with a diluted exponent, but four points cannot prove it. τ is the top accumulator feature, and accumulator accuracy on blocked CV goes from 77.4 % to 89.5 %. The 11 physics features alone do better still (91.8 %): with 133 features the forest also splits on whole-cycle statistics that drift with time and do not transfer across blocks.
- Unflattering result: at cooler 3 % (hot oil, about 57 °C) and 130 bar, 39 of 120 stable cycles give a degenerate fit (τ < 0.01 s: the step no longer looks first-order), and the rest sit at about 0.266 s against 0.300 s at cooler 100 %. The "0 fit failures" figure counts converged fits, not physically sensible ones. This cell is a likely cause of the remaining accumulator errors (not yet verified), and a fit-quality gate is the next fix.

**Leakage sensitivity.** Accumulator blocked accuracy against block size: 99.1 % (1), 96.4 % (10), 91.9 % (25), 77.4 % (50), 58.2 % (100), 47.2 % (200). The gap to shuffled CV grows monotonically from 0 to 52 points. At 100–200 cycles, part of the drop is extrapolation to condition combinations never seen in training, not only leakage. Valve is not monotonic: 98.9, 95.5, 84.9, 91.1, 91.4, 88.8 %. The 21-point accumulator gap at block 50 therefore sits in the middle of a curve. It is not a single number to quote alone.

**Calibrated centerline.**
| Reference | Operating point | False alarms on healthy (LOO, n = 30) | Mean detection, 8 fault conditions |
|---|---|---|---|
| Single context (original, k = 4, f = 5 %) | uncalibrated | 21/30 = 70 % (52–83 %); 10/10 at cooler 3 % and 20 % | 97 % (meaningless at this false-alarm rate) |
| Pooled + TS1 detrend | best k = 4, f = 2 % | 10/30 (19–51 %): every cooler-20 % cycle | 81 % |
| **Per context** | **k = 3, f = 20 %** | **0/30 (upper bound 11.4 %)** | **74 %** |

At the calibrated per-context point (Wilson CI, n = 30–39 per condition): leakage 1 and 2 are caught 30/30 (89–100 %); accumulator 100 and 90 bar 30/30 and 39/39; accumulator 115 bar 23/30 = 77 % (59–88 %); valve 90/80/73 % only 33–47 %. The envelope is a leakage and accumulator detector. Valve degradation is better caught by the edge-lag feature above. Oil temperature alone does not explain the cooler state: the TS1 detrend still alarms on every cooler-20 % cycle, so the reference has to be per operating context. Healthy-component cycles that have not reached steady state alarm 232/233 times, so the contract's steady-state gate (R6) must run before scoring.

**How many golden cycles a client must collect** (per-context envelope at k = 3, f = 20 %; fit on n random healthy cycles per context and test on the held-out rest, 300 draws): n = 3 → 99.9 % false alarms; n = 5 → 24 % (0–53 %); n = 7 → 2.9 % (0–17 %); n = 9 → 0 of 900 held-out tests (these are resamples of the same 30 cycles, so not 900 independent tests, and k and f were chosen on the same cycles). On this data the envelope stabilises at about 7–9 cycles per context. To claim a false-alarm rate with confidence, the rule of three asks for 30 alarm-free validation cycles per context to claim ≤ 10 % and 60 to claim ≤ 5 %.

**Money and lead time.**
- Matched over 48 cells: weak leakage costs **−3.2 efficiency points (95 % CI −3.35 to −3.02)** and severe leakage **−5.0 points (−5.13 to −4.85)**. The raw medians (83.6 → 79.9 → 78.1 %) mix in the other components. Delivered P_hyd also falls (−0.067 and −0.102 kW matched) because leakage bypasses flow, while motor power rises slightly (+0.011 and +0.024 kW).
- For the same hydraulic work, that is **+3.9 % motor energy (weak) and +6.4 % (severe)**. Per 10 kW of delivered hydraulic power at 4,000 h/yr and 9.64 ¢/kWh: weak about 1,890 kWh, **$182/yr (173–192)**; severe about 3,060 kWh, **$295/yr (284–301)**. Honest scale: the energy cost is real but modest. A 100 kW press line pays about $3k/yr at severe leakage. The stronger argument is lead time: weak leakage is recognised by the blocked-CV classifier with 91.3 % recall (88.4–93.5 %, n = 492) and by the calibrated envelope in 30/30 stable cycles, so the weak stage is recognisable. The dataset holds fixed leakage levels, not a progression over time, so any lead time in a plant is an inference.

**Contract mutation test** (synthetic corruptions of 150 real cycles). The original 7 rules catch 1 of 5 defect types (unit swap only; 20 % overall). With the 4 physics rules: unit swap 100 %, tag swap 100 %, 1 s misalignment 100 %, frozen sensor 100 %, offset drift 0 → 10 bar 79 % (R10 only). Overall 95.7 %. On the 2,205 real cycles the new rules fail 0 (R8), 1 (R9), 10 (R10, 0.45 %) and 0 (R11) times. Caveat: the new rules were written after seeing which defects slipped through. This shows they work; it is not an independent test.

- On accumulator, shuffled CV overstates accuracy by 21 points at 50-cycle blocks (0–52 points across block sizes, see Leakage sensitivity). That is the main leakage finding.
- Golden-run envelopes leave a distinct signature for each fault (single-fault cycles, cooler 100 %, stable, n = 10–19 each). Valve lag moves only PS4–PS6 out of band; pump leakage moves FS1, FS2 and PS4–PS6, and at severe leakage also PS3 and EPS1; low accumulator pre-charge moves PS4 and FS2, and at 100/90 bar also PS5–PS6. Alarm rates (n = 10–19, original envelope, no CIs; the calibrated table above gives Wilson CIs at n = 30–39): valve 90 % → 40 %, valve 80/73 % → 100 %, leakage 1/2 → 100 %, accumulator 115 bar → 90 %, accumulator 100/90 bar → 100 %.
- Hydraulic efficiency falls with pump leakage: median η is 83.6 % with no leakage, 79.9 % with weak leakage and 78.1 % with severe leakage.
- PS1 rise time does **not** separate valve states (median 0.67–0.71 s). The PRD's hypothesis that valve lag shows up as PS1 rise time is not supported. PS1 rise time is instead the top feature for accumulator pre-charge, which is physically sensible: the pre-charge sets how fast the line pressure builds.

## Assumptions and limitations
- The calibrated reference has 10 healthy cycles per context. 0 of 30 false alarms bounds the rate only below 11.4 %. Proving 5 % needs about 60 alarm-free cycles per context.
- The operating point was chosen on the same 30 healthy cycles it is scored on (leave-one-out keeps each test cycle out of its own envelope, but k and f were selected on them). Expect a slightly higher rate on new data.
- The condition grid is confounded with time (oil temperature and warm-up drift). Envelope alarms on non-golden cycles (99.4 %) include cooler-state and thermal effects, not only component faults.
- Original detection rates rest on 10–19 cycles each (cooler 100 % only). The calibrated rates use all cooler levels, 30–39 cycles each, with Wilson CIs.
- Energy figures assume a fixed duty (4,000 h/yr) and the national average industrial price. A site's tariff and duty cycle scale them linearly.
- The meaning of SE is not documented. The comparison is correlation, not identity.
- The boxcar decimation attenuates content above about 5 Hz. Pressure ripple above that is not analysed.
- No synthetic data enters the measured results. The only synthetic inputs are in unit tests (injected flatline and dropout, synthetic step and edge signals) and in the contract mutation test (section 11, corruptions injected into real cycles), and they are labelled as such.

## Reproduce
```bash
uv venv .venv && uv pip install --python .venv/bin/python numpy pandas scipy scikit-learn pytest
# download and unzip the UCI archive into downloads/raw/
OMP_NUM_THREADS=2 .venv/bin/python -I pipeline/run.py downloads/raw public/data            # ~20 s
OMP_NUM_THREADS=2 .venv/bin/python -I pipeline/run_extended.py downloads/raw public/data   # ~2.5 min -> extended.json
.venv/bin/python -m pytest -q pipeline/tests
OMP_NUM_THREADS=2 .venv/bin/python -I pipeline/accept.py downloads/raw --golden golden.txt --context cooler --out report.json   # acceptance report, see SOLUTION.md
```

## Week 1 on a production line (built only from the numbers above)
1. **Day 1: run the contract.** All 11 rules on the delivered extract, before any KPI. The 4 physics rules (tag order, edge alignment, η–SE consistency, stuck sensor) catch the defect types the range checks miss. Gate on steady state before anything is scored.
2. **Days 1–3: collect golden cycles per operating context**, not one golden set. At least 9 healthy steady-state cycles per context before the envelope is used, and 30 alarm-free validation cycles per context before quoting a false-alarm rate of 10 % or less (60 for 5 %).
3. **Candidates for recommendation mode** (judged on this rig's blocked CV, to be re-checked on the line's own data): cooler (99.4 % blocked), pump leakage (96.5 %; weak leakage recall 91 %), valve once the edge-lag feature is in (99.6 %).
4. **Not yet:** accumulator. It is at 89.5 % (83–95 %) blocked even with the physics features, below the others, and its step fits degrade in one thermal context (cooler 3 %, 130 bar); whether that cell drives the remaining errors is not yet verified. Run it in shadow mode while more cycles per context are collected.
5. **The KPI for the plant manager:** hydraulic efficiency η = P_hyd/P_motor, hand-checkable from two sensors. On this rig a 3-point drop matched weak leakage and about 4 % more motor energy for the same work; the severe stage was a 5-point drop. The dataset has no leakage progression over time, so lead time in a plant is inferred, not measured.
