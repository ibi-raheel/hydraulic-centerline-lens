import type { Data } from '../data'

// Each line of the recipe and the number behind it, all from the measured results.
function recipe(d: Data): [string, string][] {
  const ss = d.x.calibration.sample_size
  const r7 = ss.rows.find(r => r.n_golden === 7)
  const r9 = ss.rows.find(r => r.n_golden === 9)
  const acc = d.x.models.find(m => m.target === 'accumulator')!
  const gap = Math.round((d.x.block_sensitivity.accumulator.shuffled - acc.base.blocked) * 100)
  return [
    ['Run the data contract first: 11 rules, steady state gated.', `injected defects caught: ${Math.round(d.x.mutations.caught_7 * 100)} % by the 7 range rules, ${(d.x.mutations.caught_11 * 100).toFixed(1)} % by all 11`],
    ['Hand-check one KPI before you publish it.', `${d.s.kpi.hand.p_bar} bar × ${d.s.kpi.hand.q_lpm} l/min / 600 = ${d.s.kpi.hand.p_hyd_kw.toFixed(3)} kW`],
    ['One golden set per operating context, at least 9 cycles each.', `false alarms ${r7 ? (r7.fa_mean * 100).toFixed(1) : '–'} % at 7, ${r9 ? `${r9.alarms} in ${r9.tests.toLocaleString()} tests` : '–'} at 9`],
    ['30 alarm-free validation cycles per context to claim ≤10 % false alarms, 60 for ≤5 %.', `rule of three: ${ss.rule_of_three.for_10pct} and ${ss.rule_of_three.for_5pct} cycles`],
    ['Score models on contiguous blocks. Only what holds up goes live; the rest runs in shadow.', `shuffled splits overstated the accumulator model by ${gap} points`],
  ]
}

export function SolutionStep({ d }: { d: Data }) {
  return (
    <div className="solution">
      <ol className="recipe">
        {recipe(d).map(([rule, why], i) => (
          <li key={i}>
            <span className="recipe-n mono" aria-hidden="true">{i + 1}</span>
            <div><b>{rule}</b><span className="recipe-why mono">{why}</span></div>
          </li>
        ))}
      </ol>
      <figure className="term">
        <figcaption className="chart-title">The tool: your extract and the cycles you call golden in, a verdict per context and per cycle out</figcaption>
        <pre className="mono"><code>
          <span className="term-cmd">$ python -I pipeline/accept.py extract/ --golden golden.txt --context cooler</span>
          <span>context 3: 10 golden, ready; 0/10 validation alarms (Wilson upper 27.8%), 20 more alarm-free cycles for ≤10%</span>
          <span className="term-out">cycle 282: OUT OF BAND, PS5 PS6 FS1 FS2, leakage signature: main flow FS1 out of band</span>
          <span className="term-data">cycle 634: DATA, failed R9 (edge alignment)</span>
        </code></pre>
        <p className="fine">Real output on this rig (abridged), with the {d.x.calibration.n_healthy} healthy cycles as golden. The steps, thresholds and a week-one plan are in SOLUTION.md in the repository.</p>
      </figure>
    </div>
  )
}
