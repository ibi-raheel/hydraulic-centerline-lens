import type { Data } from '../data'
import { pct } from '../data'
import { Details, Key } from './common'

const COND: Record<string, string> = { valve: 'Valve', leak: 'Pump leakage', accumulator: 'Accumulator' }
const UNIT: Record<string, string> = { valve: ' %', leak: '', accumulator: ' bar' }

export function CalibStep({ d }: { d: Data }) {
  const c = d.x.calibration
  const sc = c.modes.single_context.at_k4_f5
  const pd = c.modes.pooled_detrend
  const pc = c.modes.per_context.operating_point
  const ctx = ['3', '20', '100']
  // Alarms per cooler context. Single context: k = 4, f = 5 % (the original build). Pooled: its operating point alarms on every cooler-20 % cycle (10/30).
  const rows = [
    { name: 'One golden set for every context', sub: 'original build, k\u00a0=\u00a04, f\u00a0=\u00a05\u00a0%', fa: sc.false_alarm, by: ctx.map(k => sc.fa_by_cooler[k].k), det: sc.detection_mean },
    { name: 'Pooled, oil temperature detrended', sub: `k = ${pd.operating_point.k}, f\u00a0=\u00a0${Math.round(pd.operating_point.f * 100)}\u00a0%`, fa: pd.operating_point.false_alarm, by: ctx.map(k => pd.at_k4_f5.fa_by_cooler[k].k), det: pd.operating_point.detection_mean },
    { name: 'One band per operating context', sub: `calibrated, k = ${pc.k}, f\u00a0=\u00a0${Math.round(pc.f * 100)}\u00a0%`, fa: pc.false_alarm, by: [0, 0, 0] /* 0 of 30: no alarms in any context */, det: pc.detection_mean, chosen: true },
  ]
  return (
    <div>
      <div className="viz-head">
        <Key kind="orange">false alarm</Key>
        <Key kind="muted">quiet</Key>
        <span className="viz-note">{c.n_healthy} healthy, stable cycles, scored leave-one-out</span>
      </div>
      <div className="calib">
        <div className="calib-ctx" aria-hidden="true"><span /><div className="calib-ctx-g"><span>cooler 3 %</span><span>cooler 20 %</span><span>cooler 100 %</span></div><span /></div>
        {rows.map(r => (
          <div key={r.name} className={`calib-row${r.chosen ? ' is-chosen' : ''}`}>
            <div className="calib-name"><b>{r.name}</b><span className="fine mono">{r.sub}</span></div>
            <div className="calib-cells" role="img" aria-label={`${r.fa.k} of ${r.fa.n} healthy cycles raise a false alarm`}>
              {r.by.map((n, gi) => (
                <div key={gi} className="calib-group">
                  {Array.from({ length: 10 }, (_, i) => <i key={i} className={i < n ? 'on' : ''} />)}
                </div>
              ))}
            </div>
            <div className="calib-fig">
              <span className="mono strong">{r.fa.k}/{r.fa.n}</span>
              <span className="fine">detects {pct(r.det, 0)}</span>
            </div>
          </div>
        ))}
      </div>
      <Details>
        <p>Detection at the calibrated per-context point, all cooler levels, stable cycles, with Wilson 95 % intervals. 0 of 30 bounds the false-alarm rate below {pct(pc.false_alarm.hi)}; k and f were chosen on these same cycles, so expect a somewhat higher rate on new data.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Fault</th><th className="num">Caught</th><th className="num">Rate (95 % CI)</th></tr></thead>
          <tbody>{pc.conditions.map(x => <tr key={x.component + x.level}><td>{COND[x.component]} {x.component === 'leak' ? ['none', 'weak', 'severe'][x.level] : `${x.level}${UNIT[x.component]}`}</td><td className="num">{x.k}/{x.n}</td><td className="num">{pct(x.rate, 0)} ({pct(x.lo, 0)}–{pct(x.hi, 0)})</td></tr>)}</tbody>
        </table></div>
        <p>How many golden cycles per context before the band can be trusted (fit on n, test on the rest, 300 draws):</p>
        <div className="table-wrap"><table>
          <thead><tr><th className="num">Golden cycles</th><th className="num">False-alarm rate</th><th className="num">2.5–97.5 %</th></tr></thead>
          <tbody>{c.sample_size.rows.map(r => <tr key={r.n_golden}><td className="num">{r.n_golden}</td><td className="num">{pct(r.fa_mean)}</td><td className="num">{pct(r.fa_p2_5, 0)}–{pct(r.fa_p97_5, 0)}</td></tr>)}</tbody>
        </table></div>
        <p className="fine">To quote a false-alarm rate with confidence, the rule of three asks for {c.sample_size.rule_of_three.for_10pct} alarm-free cycles per context to claim ≤ 10 % and {c.sample_size.rule_of_three.for_5pct} to claim ≤ 5 %. The band catches leakage and low pre-charge well and valve faults poorly (33–47 %); the valve is better caught by the edge-lag feature in the next step.</p>
      </Details>
    </div>
  )
}
