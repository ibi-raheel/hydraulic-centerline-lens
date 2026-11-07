# The golden-run acceptance recipe

**Question.** When a new production line goes live on a data platform, how many golden runs does a centerline need before its alarms can be trusted, and how do you prove the KPIs and cleansing rules are right before anyone acts on them?

**Answer, measured on 2,205 real cycles of a hydraulic test rig.** Copying one golden set across operating conditions gave 70 % false alarms (21 of 30 healthy cycles). About 9 golden cycles per condition fixed it (0 of 30) and still caught all 60 leakage cycles. Four physics checks caught 96 % of injected data defects, against 20 % for range checks.

Every number below comes from `public/data/summary.json` and `public/data/extended.json`, produced by the pipeline in this repository. Equations and validation are in [METHOD.md](METHOD.md).

## The recipe (5 steps)

1. **Contract first.** Run all 11 rules on the extract before any KPI: 7 range rules plus 4 physics rules (tag order, edge alignment, KPI consistency, stuck sensor). Gate on steady state: unsteady healthy cycles alarmed 232 of 233 times. A cycle that fails is labelled "fix the data", not a process alarm.
2. **Hand-check one KPI with the plant engineer.** η = (p·Q/600) / P_motor, worked for one instant and recomputed independently. Only then publish it.
3. **One golden set per operating context, never one global set.** Collect at least 9 healthy steady-state cycles per context before the band goes live. Below 7, expect false alarms.
4. **Earn the false-alarm claim.** You need 30 alarm-free validation cycles per context to say 10 % or less, and 60 to say 5 % or less. Report the Wilson upper bound, not just "0 alarms".
5. **Score models on contiguous blocks, not shuffled splits.** Only models that hold up on blocked CV go into recommendation mode. The rest run in shadow mode.

## Decision rules and the measured thresholds behind them

| Decision | Rule | Measured on this rig |
| --- | --- | --- |
| Is the extract fit to score? | All 11 contract rules pass, steady state reached | Range rules alone caught 1 of 5 injected defect types (20 %); all 11 caught 95.7 %. The 4 physics rules fail on only 11 of 2,205 real cycles. |
| Is the KPI right? | Hand calculation equals the pipeline value | 166.347 bar × 7.831 l/min / 600 = 2.171 kW (cycle 1790, t = 30 s); η tracks the rig's own efficiency channel at r = 0.9991 |
| One band or several? | One band per operating context | One golden set: 21/30 false alarms (70 %, CI 52–83 %). Per context: 0/30 (95 % upper bound 11.4 %) |
| Enough golden cycles? | ≥ 9 per context | False alarms 99.9 % at 3, 24 % at 5, 2.9 % at 7, 0 in 900 held-out tests at 9 |
| Can we quote a false-alarm rate? | 0 alarms in ≥ 30 validation cycles per context for ≤ 10 %, ≥ 60 for ≤ 5 % | Rule of three: 30 and 60 |
| What does the band catch? | Out of band on any tag (more than 20 % of bins at z > 3) | Leakage 30/30 at both levels; accumulator 100 bar 30/30, 90 bar 39/39, 115 bar 23/30; valve only 33–47 %, so valve goes to the edge-lag feature |
| Recommendation mode or shadow? | Holds up on blocked CV | Accumulator: shuffled CV 98.8 %, blocked 77.4 %, 89.5 % with physics features (50-cycle blocks), so it stays in shadow. Valve with the edge-lag feature: 91.1 % → 99.6 %. Cooler and leakage hold up. |
| Why it matters | Efficiency drop maps to energy | Weak pump leakage costs 3.2 efficiency points (95 % CI −3.35 to −3.02), +3.9 % motor energy for the same hydraulic work |

**Caveats that travel with these numbers.** k and f were tuned on the same 30 healthy cycles, so expect a slightly higher false-alarm rate on new data. The 900 tests are resamples of those 30 cycles, not independent tests. The 4 physics rules were written after seeing which defects slipped through. The 89.5 % accumulator figure is specific to 50-cycle blocks.

## The tool: `pipeline/accept.py`

A thin wrapper over the existing pipeline (`hcl/`); it adds no new maths. Give it a line's extract, the cycles you call golden and the context column.

```bash
.venv/bin/python -I pipeline/accept.py downloads/raw --golden golden.txt --context cooler \
    --k 3 --f 0.2 --out report.json            # optional: --cache pipeline/cache --hand 1790
```

- **Input:** the folder layout of the public dataset (`PS1..PS6.txt`, `EPS1.txt`, `FS1.txt`, `FS2.txt`, `SE.txt`, `profile.txt` with the context column and the steady-state flag). Rows are cycles. `golden.txt` holds one 0-based cycle index per line.
- **Output (`report.json`):**
  - `contract`: the failed rule ids for each cycle (R1–R7 range rules, R8–R11 physics rules);
  - `contexts`: for each context, `n_golden`, `need_more` (to reach 9), `validation_alarms` (leave-one-out on the golden cycles), `wilson_hi`, how many more alarm-free cycles a ≤ 10 % or ≤ 5 % claim needs, and `ready_for`;
  - `cycles`: one label per cycle, `DATA: fix the extract`, `IN BAND` or `OUT OF BAND: investigate`, with the tags out of band, a signature hint (main flow FS1 out → leakage; FS2 out with FS1 in → low accumulator; pressures only → check the valve's PS2 edge lag, reported in ms against the golden median), and η per cycle;
  - `hand_check`: the worked line η = (p·Q/600) / P_motor for one instant of a golden cycle;
  - `golden_curve`: false alarms against golden count per context, by resampling the declared golden cycles.

Real output on this rig, with the 30 healthy steady-state cycles as golden:

```
context 3: 10 golden, ready; 0/10 validation alarms (Wilson upper 27.8%), 20 more alarm-free cycles for ≤10%
cycle 282: OUT OF BAND, PS5 PS6 FS1 FS2, leakage signature: main flow FS1 out of band
cycle 634: DATA, failed R9 (edge alignment)
```

`pipeline/tests/test_accept.py` runs it on the real data and checks that it reproduces the published operating point: 0/30 false alarms, 30/30 on both leakage levels, the golden-count curve and the KPI hand calculation.

## Week 1 on a real line

This was built on public test-rig data. On a real line the same recipe runs on that line's historian extract.

- **Day 1:** run the 11-rule contract on one line's extract before any KPI, including the steady-state gate. List every cycle that fails as "fix the data" and agree the cleansing rules with the data architect.
- **Day 2:** hand-check the line's headline KPI with the plant engineer: one instant worked on paper, then the same number recomputed independently. Agree what an operating context is on this line (product, recipe, speed or shift).
- **Days 2–3:** pick golden cycles per context with the plant, at least 9 healthy steady-state cycles each. Run the tool's readiness report to see which contexts still need more.
- **Day 4:** run the per-context centerline over the line's history in recommendation mode only. Log every alarm as "data", "in band" or "out of band" with its tags, and count false alarms on held-out healthy cycles with a Wilson bound.
- **Day 5:** hand over the one-page recipe for that line: golden counts per context, the measured false-alarm bound, how many more clean cycles a 10 % or 5 % claim needs, which models pass blocked validation and can go to recommendation mode, and which stay in shadow mode.
