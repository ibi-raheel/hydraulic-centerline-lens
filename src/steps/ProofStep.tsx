import { useState } from 'react'
import type { Data } from '../data'
import { pct } from '../data'
import { scale, useWidth } from '../hooks'
import { Details, Key } from './common'

const VALIDATION: [string, string][] = [
  ['Hand calc of P_hyd, cycle 1790, t = 30 s', '166.347 bar × 7.831 l/min / 600 = 2.171 kW, reproduced in a test'],
  ['Cycle-mean P_hyd and η by a plain Python loop', 'matches the pipeline within 0.5 %'],
  ['Formula check with round numbers', '150 bar × 8 l/min = 2.000 kW exactly'],
  ['Label counts vs dataset documentation', 'all 5 label columns match'],
  ['Derived η vs the rig’s SE channel', 'r = 0.9991, residual SD 0.45 pts'],
  ['Energy balance P_hyd < P_motor', '0 violations in 2,205 cycles'],
  ['Robust band tail rate on Gaussian noise', 'matches 2(1 − Φ(k)) within 8 % at k = 2, 2.5, 3'],
  ['Wilson interval', 'wilson(0, 30) upper = 0.1135'],
  ['Step-response fit on a synthetic step', 'recovers τ = 0.25 s within 2 %'],
  ['Sub-sample edge alignment', 'recovers a 23.4-sample delay within 0.2 samples'],
  ['Energy hand calc', '10 kW, η 0.80 → 0.75: 0.833 kW, 3,333 kWh, $333'],
  ['Classifiers vs majority-class baseline', 'every component beats it by > 20 pts on blocked CV'],
]

export function ProofStep({ d }: { d: Data }) {
  const bs = d.x.block_sensitivity
  const [ref, w] = useWidth<HTMLDivElement>(700)
  const [hi, setHi] = useState<number | null>(null)
  const H = Math.round(Math.min(340, Math.max(240, w * 0.5)))
  const narrow = w < 480
  const m = { l: 44, r: narrow ? 16 : 104, t: 18, b: 40 }
  const blocks = bs.accumulator.rows.map(r => r.block)
  const sx = (i: number) => m.l + (i / (blocks.length - 1)) * (w - m.l - m.r)
  const sy = scale(0.4, 1, H - m.b, m.t)
  const line = (rows: { acc: number }[]) => rows.map((r, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(r.acc).toFixed(1)}`).join('')
  const q = blocks.indexOf(50)
  const series = [
    { k: 'accumulator', name: 'Accumulator', cls: 'orange', rows: bs.accumulator.rows },
    { k: 'valve', name: 'Valve', cls: 'blue', rows: bs.valve.rows },
  ]
  const yt = [0.4, 0.6, 0.8, 1]
  return (
    <div>
      <figure className="chart" ref={ref}>
        <div className="viz-head">
          <Key kind="orange">Accumulator</Key>
          <Key kind="blue">Valve</Key>
          <Key kind="muted">shuffled CV</Key>
        </div>
        <div className="chart-box">
          <svg width={w} height={H} role="img" aria-label="Blocked cross-validation accuracy against validation block size"
            onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); const i = Math.round(((e.clientX - r.left - m.l) / (w - m.l - m.r)) * (blocks.length - 1)); setHi(i >= 0 && i < blocks.length ? i : null) }}
            onPointerLeave={() => setHi(null)}>
            {yt.map(v => <g key={v}><line x1={m.l} x2={w - m.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={m.l - 6} y={sy(v)} className="tick" textAnchor="end" dominantBaseline="central">{v * 100}%</text></g>)}
            {blocks.map((b, i) => <text key={b} x={sx(i)} y={H - m.b + 16} className="tick" textAnchor="middle">{b}</text>)}
            <text x={w - m.r} y={H - 4} className="axis-label" textAnchor="end">validation block, cycles</text>
            <line x1={sx(q)} x2={sx(q)} y1={m.t} y2={H - m.b} className="quote-line" />
            <text x={sx(q) + 6} y={H - m.b - 8} className="anno">quoted</text>
            {[bs.accumulator.shuffled, bs.valve.shuffled].map(v => <line key={v} x1={m.l} x2={w - m.r} y1={sy(v)} y2={sy(v)} className="ref-line" />)}
            {!narrow && <text x={w - m.r + 10} y={sy(bs.accumulator.shuffled)} dominantBaseline="central" className="anno muted">shuffled CV</text>}
            {series.map(s => (
              <g key={s.k}>
                <path d={line(s.rows)} className={`ln ln-${s.cls}`} />
                {s.rows.map((r, i) => <circle key={i} cx={sx(i)} cy={sy(r.acc)} r={i === q || i === hi ? 5 : 3.5} className={`pt pt-${s.cls}`} />)}
                {!narrow && <text x={sx(blocks.length - 1) + 10} y={sy(s.rows[s.rows.length - 1].acc)} dominantBaseline="central" className="anno">{s.name} {pct(s.rows[s.rows.length - 1].acc, 0)}</text>}
              </g>
            ))}
            {hi != null && <line x1={sx(hi)} x2={sx(hi)} y1={m.t} y2={H - m.b} className="cursor" />}
          </svg>
          {hi != null && (
            <div className="tip" style={{ left: Math.min(w - 180, sx(hi) + 10), top: m.t }}>
              <div className="tip-h">{blocks[hi]}-cycle blocks</div>
              <div>Accumulator {pct(bs.accumulator.rows[hi].acc)}</div>
              <div>Valve {pct(bs.valve.rows[hi].acc)}</div>
            </div>
          )}
        </div>
      </figure>
      <Details>
        <div className="table-wrap"><table>
          <thead><tr><th className="num">Block</th><th className="num">Accumulator</th><th className="num">Gap to shuffled</th><th className="num">Valve</th><th className="num">Gap to shuffled</th></tr></thead>
          <tbody>{blocks.map((b, i) => <tr key={b}><td className="num">{b}</td><td className="num">{pct(bs.accumulator.rows[i].acc)}</td><td className="num">{bs.accumulator.rows[i].gap_vs_shuffled_pts.toFixed(1)} pts</td><td className="num">{pct(bs.valve.rows[i].acc)}</td><td className="num">{bs.valve.rows[i].gap_vs_shuffled_pts.toFixed(1)} pts</td></tr>)}</tbody>
        </table></div>
        <p className="fine">Shuffled CV: accumulator {pct(bs.accumulator.shuffled)}, valve {pct(bs.valve.shuffled)}. At 100–200 cycle blocks part of the drop is extrapolation to condition combinations never seen in training, not only leakage.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Check</th><th>Result</th></tr></thead>
          <tbody>{VALIDATION.map(([a, b]) => <tr key={a}><td>{a}</td><td>{b}</td></tr>)}</tbody>
        </table></div>
        <p className="fine">36 pytest tests cover the hand calculations, synthetic recoveries (labelled) and checks on the outputs. Full equations, assumptions and limitations are in METHOD.md in the repository.</p>
      </Details>
    </div>
  )
}
