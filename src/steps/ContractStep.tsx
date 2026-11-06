import type { Data } from '../data'
import { pct } from '../data'
import { Details, Key } from './common'

const MUT: Record<string, string> = {
  unit_bar_to_psi: 'Pressure logged in psi, not bar',
  tag_swap_PS1_PS2: 'PS1 and PS2 tags swapped',
  misalign_PS1_1s: 'PS1 shifted by 1 s',
  offset_drift_PS1_0to10bar: 'PS1 drifts 0 → 10 bar',
  flatline_PS1_last_30s: 'PS1 frozen for the last 30 s',
}

const PHYS_RULES = [
  { id: 'R8', name: 'Tag order', rule: 'median(PS1) ≥ median(PS2)' },
  { id: 'R9', name: 'Edge alignment', rule: 'PS1 falling edge − PS2 rising edge at the 9.4 s switch within 0.10–0.35 s' },
  { id: 'R10', name: 'η–SE consistency', rule: '|SE − (0.756·η + 5.69)| ≤ 4 residual SD' },
  { id: 'R11', name: 'Stuck sensor', rule: 'no run of ≥ 2 s with zero change in PS1' },
]

export function ContractStep({ d }: { d: Data }) {
  const m = d.x.mutations
  const n = d.s.n_cycles
  return (
    <div>
      <div className="viz-head">
        <Key kind="muted">7 range rules</Key>
        <Key kind="blue">+ 4 physics rules</Key>
        <span className="viz-note">Defects injected into {m.sample_n} real cycles (synthetic)</span>
      </div>
      <div className="mut" role="table" aria-label="Share of corrupted cycles caught, by defect type">
        {m.rows.map(r => (
          <div className="mut-row" role="row" key={r.mutation}>
            <span className="mut-name" role="rowheader">{MUT[r.mutation] ?? r.mutation}</span>
            <span className="mut-bars" role="cell">
              <span className="bar-track"><span className="bar bar-muted" style={{ width: `${r.caught_7_rules * 100}%` }} /><b>{pct(r.caught_7_rules, 0)}</b></span>
              <span className="bar-track"><span className="bar bar-blue" style={{ width: `${r.caught_11_rules * 100}%` }} /><b>{pct(r.caught_11_rules, 0)}</b></span>
            </span>
          </div>
        ))}
        <div className="mut-row mut-total" role="row">
          <span className="mut-name" role="rowheader">All five defect types</span>
          <span className="mut-total-val" role="cell"><span className="mono">{pct(m.caught_7, 0)}</span> → <span className="mono strong">{pct(m.caught_11)}</span></span>
        </div>
      </div>
      <Details>
        <p>Pass and fail counts on all {n.toLocaleString()} real cycles. R6 is a gate, not a defect: unsteady cycles are held back from scoring.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Rule</th><th>Check</th><th className="num">Pass</th><th className="num">Fail</th></tr></thead>
          <tbody>
            {d.s.spec.map(r => <tr key={r.id}><td className="mono">{r.id}</td><td>{r.name}<div className="fine mono">{r.rule}</div></td><td className="num">{r.pass.toLocaleString()}</td><td className="num">{r.fail.toLocaleString()}</td></tr>)}
            {PHYS_RULES.map(r => { const f = m.new_rule_fails_on_real_data[r.id]; return <tr key={r.id}><td className="mono">{r.id}</td><td>{r.name}<div className="fine mono">{r.rule}</div></td><td className="num">{(n - f).toLocaleString()}</td><td className="num">{f}</td></tr> })}
          </tbody>
        </table></div>
        <p className="fine">The four physics rules were written after seeing which defects slipped through, so the mutation test shows they work; it is not an independent test.</p>
      </Details>
    </div>
  )
}
