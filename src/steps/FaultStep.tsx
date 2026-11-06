import type { Data, ExtModel } from '../data'
import { pct } from '../data'
import type { Component } from '../components/Schematic'
import { Details, Seg } from './common'

const TITLE: Record<Component, string> = { cooler: 'Cooler', valve: 'Valve', leak: 'Pump leakage', accumulator: 'Accumulator' }
const cls = (target: string, v: number) =>
  target === 'leak' ? ['none', 'weak', 'severe'][v] : target === 'accumulator' ? `${v} bar` : `${v} %`

export function FaultStep({ d, comp, setComp, physics, setPhysics }: { d: Data; comp: Component; setComp: (c: Component) => void; physics: boolean; setPhysics: (b: boolean) => void }) {
  const m = d.x.models.find(x => x.target === comp)!
  const sc = physics ? m.with_physics : m.base
  const other = physics ? m.base : m.with_physics
  const gain = (m.with_physics.blocked - m.base.blocked) * 100
  return (
    <div className="fault">
      <div className="fault-controls">
        <Seg label="Component" value={comp} onChange={setComp} options={(['valve', 'accumulator', 'leak', 'cooler'] as Component[]).map(v => ({ v, label: TITLE[v] }))} />
        <label className="switch">
          <input type="checkbox" role="switch" checked={physics} onChange={e => setPhysics(e.target.checked)} />
          <span className="switch-track" aria-hidden="true"><span className="switch-thumb" /></span>
          <span>Physics features</span>
        </label>
      </div>
      <div className="fault-grid">
        <Matrix m={m} conf={sc.confusion} />
        <div className="fault-side">
          <div className="acc">
            <div className="acc-label">Blocked CV accuracy{physics ? ', with physics' : ''}</div>
            <div className="acc-val mono" aria-live="polite">{pct(sc.blocked)}</div>
            <div className="fine mono">95 % CI {pct(sc.blocked_lo)}–{pct(sc.blocked_hi)}</div>
            <div className="acc-delta">
              {Math.abs(gain) < 0.5
                ? <>Physics features change nothing here ({pct(m.base.blocked)} → {pct(m.with_physics.blocked)}).</>
                : <>{physics ? 'Without' : 'With'} physics: <span className="mono">{pct(other.blocked)}</span></>}
            </div>
          </div>
          <Feature d={d} comp={comp} on={physics} />
        </div>
      </div>
      <Details>
        <p>One random forest per component, scored with blocked cross-validation (contiguous 50-cycle blocks) and block-bootstrap 95 % intervals. Shuffled CV is shown for comparison with published work, which used random splits.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Component</th><th className="num">Blocked</th><th className="num">+ physics</th><th className="num">Physics only (11)</th><th className="num">Shuffled</th></tr></thead>
          <tbody>{d.x.models.map(x => (
            <tr key={x.target}><td>{TITLE[x.target as Component]}</td><td className="num">{pct(x.base.blocked)}</td><td className="num">{pct(x.with_physics.blocked)}</td><td className="num">{pct(x.physics_only.blocked)}</td><td className="num">{pct(x.base.shuffled)}</td></tr>
          ))}</tbody>
        </table></div>
        <div className="table-wrap"><table>
          <thead><tr><th>Component</th><th className="num">Majority class</th><th>Published (random split)</th></tr></thead>
          <tbody>{d.s.models.map(x => <tr key={x.target}><td>{TITLE[x.target as Component]}</td><td className="num">{pct(x.acc_majority)}</td><td>{x.published}</td></tr>)}</tbody>
        </table></div>
        <p className="fine">The accumulator is still the weakest model. In a spot-check at 100- and 200-cycle blocks its score fell well below 89.5 %, so treat that as a 50-cycle-block number. Its step fits degrade at cooler 3 % and 130 bar, a likely (not yet verified) cause of the remaining errors.</p>
      </Details>
    </div>
  )
}

function Matrix({ m, conf }: { m: ExtModel; conf: number[][] }) {
  const n = m.classes.length
  return (
    <figure className="matrix-fig">
      <figcaption className="chart-title">Confusion matrix, {conf.flat().reduce((a, b) => a + b, 0).toLocaleString()} cycles</figcaption>
      <div className="matrix" style={{ gridTemplateColumns: `auto repeat(${n}, minmax(0, 1fr))` }} role="table" aria-label="Rows: true state. Columns: predicted state.">
        <span className="mx-corner" role="presentation"><span>true ↓</span><span>predicted →</span></span>
        {m.classes.map(c => <span key={c} className="mx-col mono" role="columnheader">{cls(m.target, c)}</span>)}
        {conf.map((row, i) => {
          const tot = row.reduce((a, b) => a + b, 0)
          return [
            <span key={`h${i}`} className="mx-row mono" role="rowheader">{cls(m.target, m.classes[i])}</span>,
            ...row.map((v, j) => {
              const s = tot ? v / tot : 0
              return (
                <span key={`${i}-${j}`} role="cell" className={`mx-cell${i === j ? ' is-diag' : ''}${s > 0.5 ? ' is-dark' : ''}${i !== j && v > 0 ? ' is-miss' : ''}`}
                  style={{ ['--s' as string]: `${Math.round(Math.sqrt(s) * 100)}%` }} title={`true ${cls(m.target, m.classes[i])}, predicted ${cls(m.target, m.classes[j])}: ${v} (${pct(s)})`}>
                  {v}
                </span>
              )
            }),
          ]
        })}
      </div>
    </figure>
  )
}

function Feature({ d, comp, on }: { d: Data; comp: Component; on: boolean }) {
  const p = d.x.physics
  if (comp === 'valve' || comp === 'accumulator') {
    const isV = comp === 'valve'
    const rows = isV
      ? (['100', '90', '80', '73'] as const).map(k => ({ k: `${k} %`, v: p.valve_lag_PS2_ms[k].median, txt: `${p.valve_lag_PS2_ms[k].median.toFixed(0)} ms` }))
      : (['130', '115', '100', '90'] as const).map(k => ({ k: `${k} bar`, v: p.tau1_by_acc_cooler100_s[k].median, txt: `${p.tau1_by_acc_cooler100_s[k].median.toFixed(3)} s` }))
    const [lo, hi] = isV ? [0, 320] : [0.2, 0.32]
    return (
      <div className={`feat${on ? '' : ' is-off'}`}>
        <div className="feat-h">{isV ? 'Switching lag on the PS2 edge' : 'Step-response time constant τ'}<span className="feat-state">{on ? 'in the model' : 'not used'}</span></div>
        <div className="feat-rows">
          {rows.map(r => (
            <div key={r.k} className="feat-row">
              <span className="mono feat-k">{r.k}</span>
              <span className="feat-track"><span className="feat-dot" style={{ left: `${((r.v - lo) / (hi - lo)) * 100}%` }} /></span>
              <span className="mono feat-v">{r.txt}</span>
            </div>
          ))}
        </div>
        <p className="fine">{isV
          ? 'The valve edge arrives later as the opening shrinks. Measured by template matching against the golden edge.'
          : `τ grows with pre-charge, as the gas law predicts. Fitted p(t) = p∞ + (p₀ − p∞)e^(−t/τ) after the 9.43 s step, cooler 100 %. Exponent ${p.loglog_slope.value} (CI ${p.loglog_slope.lo}–${p.loglog_slope.hi}).`}</p>
      </div>
    )
  }
  const m = d.x.models.find(x => x.target === comp)!
  const top = m.top_features_with_physics.slice(0, 4)
  const mx = top[0].imp
  return (
    <div className="feat">
      <div className="feat-h">Top features</div>
      <div className="feat-rows">
        {top.map(f => (
          <div key={f.name} className="feat-row">
            <span className="mono feat-k feat-k-wide">{f.name}</span>
            <span className="feat-track"><span className="feat-bar" style={{ width: `${(f.imp / mx) * 100}%` }} /></span>
            <span className="mono feat-v">{f.imp.toFixed(3)}</span>
          </div>
        ))}
      </div>
      <p className="fine">{comp === 'leak'
        ? `Efficiency carries it: SE and the derived η rank near the top. Weak leakage is recognised with ${pct(d.x.leak_recall['1'].rate)} recall.`
        : 'Cooling efficiency and cooling power channels carry it; no physics feature is needed.'}</p>
    </div>
  )
}
