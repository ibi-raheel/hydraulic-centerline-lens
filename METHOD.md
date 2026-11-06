# Method

All numbers in the UI come from `pipeline/run.py` run on the full public dataset. Nothing is hand-entered or simulated.

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
| Golden-envelope false alarms, leave-one-out | 1 of 10 golden cycles alarms |
| Classifiers vs majority-class baseline | every component beats the baseline by more than 20 pts on blocked CV (test) |
| Classifiers vs published results | cooler and valve: Helwig et al. report 100 %. Accumulator: 90.4 % (Helwig et al. 2015) and 99.65 % (Schneider et al. 2017) |

### Why blocked cross-validation
The rig steps through the condition grid in order, and adjacent cycles are near-duplicates. A shuffled K-fold therefore puts the neighbours of every test cycle in the training set. The pipeline reports both scores: GroupKFold(5) over contiguous 50-cycle blocks (the honest number) and a shuffled KFold(5). The gap between them measures the leakage.

## Results (measured)
| Component | Blocked CV | Shuffled CV | Majority | Top tags |
|---|---|---|---|---|
| Cooler | 99.4 % | 99.9 % | 33.6 % | CE, CP, TS4 |
| Valve | 91.1 % | 98.5 % | 51.0 % | PS2, SE, FS1 |
| Pump leakage | 96.5 % | 99.7 % | 55.4 % | SE, FS1, η |
| Accumulator | 77.4 % | 98.8 % | 36.6 % | PS1 (rise time is the single top feature), FS2, TS2 |

- On accumulator, shuffled CV overstates accuracy by 21 points. That is the main leakage finding.
- Golden-run envelopes leave a distinct signature for each fault (single-fault cycles, cooler 100 %, stable, n = 10–19 each). Valve lag moves only PS4–PS6 out of band; pump leakage moves FS1, FS2 and PS4–PS6, and at severe leakage also PS3 and EPS1; low accumulator pre-charge moves PS4 and FS2, and at 100/90 bar also PS5–PS6. Alarm rates: valve 90 % → 40 %, valve 80/73 % → 100 %, leakage 1/2 → 100 %, accumulator 115 bar → 90 %, accumulator 100/90 bar → 100 %.
- Hydraulic efficiency falls with pump leakage: median η is 83.6 % with no leakage, 79.9 % with weak leakage and 78.1 % with severe leakage.
- PS1 rise time does **not** separate valve states (median 0.67–0.71 s). The PRD's hypothesis that valve lag shows up as PS1 rise time is not supported. PS1 rise time is instead the top feature for accumulator pre-charge, which is physically sensible: the pre-charge sets how fast the line pressure builds.

## Assumptions and limitations
- The golden set has only 10 cycles (the strict spec), so the envelope is coarse. One leave-one-out false alarm in 10 is not a precise false-alarm rate.
- The condition grid is confounded with time (oil temperature and warm-up drift). Envelope alarms on non-golden cycles (99.4 %) include cooler-state and thermal effects, not only component faults.
- Detection rates by condition rest on 10–19 cycles each.
- The meaning of SE is not documented. The comparison is correlation, not identity.
- The boxcar decimation attenuates content above about 5 Hz. Pressure ripple above that is not analysed.
- No synthetic data enters the results. The only synthetic inputs are in unit tests (injected flatline and dropout), and they are labelled as such.

## Reproduce
```bash
uv venv .venv && uv pip install --python .venv/bin/python numpy pandas scipy scikit-learn pytest
# download and unzip the UCI archive into downloads/raw/
OMP_NUM_THREADS=2 .venv/bin/python -I pipeline/run.py downloads/raw public/data   # ~20 s
.venv/bin/python -m pytest -q pipeline/tests
```
