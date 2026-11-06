import { useMemo, useState } from 'react'
import type { Data } from '../data'
import { fmt } from '../data'
import { niceTicks, scale, useWidth } from '../hooks'
import { Details } from './common'

export function KpiStep({ d }: { d: Data }) {
  const h = d.s.kpi.hand
  const fit = d.s.kpi.fit
  const handKw = (h.p_bar * h.q_lpm) / 600 // the worked line below, done in the browser as a cross-check of the shipped value
  return (
    <div className="kpi">
      <div className="calc" aria-label="Hand calculation">
        <div className="calc-head">By hand · cycle {h.cycle}, t = {h.t_s.toFixed(1)} s</div>
        <dl>
          <div><dt>p, pump outlet PS1</dt><dd className="mono">{h.p_bar.toFixed(3)} bar</dd></div>
          <div><dt>Q, main flow FS1</dt><dd className="mono">{h.q_lpm.toFixed(3)} l/min</dd></div>
        </dl>
        <div className="calc-eq mono">
          <div>P<sub>hyd</sub> = p · Q / 600</div>
          <div>= {h.p_bar.toFixed(3)} × {h.q_lpm.toFixed(3)} / 600</div>
          <div className="calc-res">= {handKw.toFixed(3)} kW</div>
        </div>
        <div className="calc-cmp">
          <span>Pipeline</span><span className="mono">{h.p_hyd_kw.toFixed(4)} kW</span>
        </div>
        <div className="calc-head calc-gap">Whole cycle, t = 10–60 s</div>
        <div className="calc-eq mono">
          <div>η = {h.cycle_p_hyd_kw.toFixed(4)} / {h.cycle_p_motor_kw.toFixed(4)} kW</div>
          <div className="calc-res">= {h.cycle_eff_pct.toFixed(2)} %</div>
        </div>
        <p className="fine">1 bar = 10<sup>5</sup> Pa and 1 l/min = 1/60 000 m³/s, so p·Q in kW is p·Q/600.</p>
      </div>
      <Scatter d={d} />
      <Details>
        <div className="table-wrap"><table>
          <tbody>
            <tr><td>Derived η vs the rig's SE channel</td><td className="num">r = {fit.r}, SE ≈ {fit.slope}·η + {fit.intercept}, residual SD {fit.resid_sd} pts</td></tr>
            <tr><td>Median η / median SE</td><td className="num">{d.s.kpi.eff_median} % / {d.s.kpi.se_median} %</td></tr>
            <tr><td>Cycle {h.cycle}: η vs SE</td><td className="num">{h.cycle_eff_pct} % vs {h.cycle_se_pct} %</td></tr>
            <tr><td>Energy balance P<sub>hyd</sub> &lt; P<sub>motor</sub></td><td className="num">0 violations in {d.s.n_cycles.toLocaleString()} cycles</td></tr>
          </tbody>
        </table></div>
        <p className="fine">SE's formula is undocumented, so the correlation shows the two agree, not that they are identical. Cycle-mean P<sub>hyd</sub> and η are also recomputed by a plain Python loop in the test suite and match within 0.5 %.</p>
      </Details>
    </div>
  )
}

function Scatter({ d }: { d: Data }) {
  const [ref, w] = useWidth<HTMLDivElement>(520)
  const [hover, setHover] = useState<number | null>(null)
  const H = Math.round(Math.min(380, Math.max(260, w * 0.72)))
  const m = { l: 40, r: 12, t: 14, b: 38 }
  const pts = d.k
  const [x0, x1, y0, y1] = useMemo(() => {
    let a = Infinity, b = -Infinity, c = Infinity, e = -Infinity
    for (const p of pts) { a = Math.min(a, p.eff); b = Math.max(b, p.eff); c = Math.min(c, p.se); e = Math.max(e, p.se) }
    return [Math.floor(a - 0.5), Math.ceil(b + 0.5), Math.floor(c - 0.5), Math.ceil(e + 0.5)]
  }, [pts])
  const sx = scale(x0, x1, m.l, w - m.r)
  const sy = scale(y0, y1, H - m.b, m.t)
  const fit = d.s.kpi.fit
  const hc = d.s.kpi.hand.cycle
  const hp = pts[hc]
  const xt = niceTicks(x0, x1, w < 420 ? 4 : 6)
  const yt = niceTicks(y0, y1, 4)
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const mx = e.clientX - r.left, my = e.clientY - r.top
    let best = -1, bd = 400
    for (let i = 0; i < pts.length; i++) {
      const dx = sx(pts[i].eff) - mx, dy = sy(pts[i].se) - my
      const dd = dx * dx + dy * dy
      if (dd < bd) { bd = dd; best = i }
    }
    setHover(best >= 0 ? best : null)
  }
  const hv = hover != null ? pts[hover] : null
  return (
    <figure className="chart" ref={ref}>
      <figcaption className="chart-title">Derived η vs the rig's own efficiency channel, all {pts.length.toLocaleString()} cycles</figcaption>
      <div className="chart-box">
        <svg width={w} height={H} onPointerMove={onMove} onPointerLeave={() => setHover(null)} role="img" aria-label={`Scatter of derived efficiency against SE, r = ${fit.r}`}>
          {yt.map(v => <g key={v}><line x1={m.l} x2={w - m.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={m.l - 6} y={sy(v)} className="tick" textAnchor="end" dominantBaseline="central">{v}</text></g>)}
          {xt.map(v => <text key={v} x={sx(v)} y={H - m.b + 16} className="tick" textAnchor="middle">{v}</text>)}
          <line x1={m.l} x2={w - m.r} y1={H - m.b} y2={H - m.b} className="axis" />
          <text x={w - m.r} y={H - 4} className="axis-label" textAnchor="end">derived η, %</text>
          <text x={m.l} y={m.t - 2} className="axis-label">SE, %</text>
          <g className="dots">{pts.map(p => <circle key={p.i} cx={sx(p.eff)} cy={sy(p.se)} r={1.7} />)}</g>
          <line x1={sx(x0)} y1={sy(fit.slope * x0 + fit.intercept)} x2={sx(x1)} y2={sy(fit.slope * x1 + fit.intercept)} className="fit-line" />
          {hp && <g><circle cx={sx(hp.eff)} cy={sy(hp.se)} r={5.5} className="mark-ring" /><text x={sx(hp.eff) - 9} y={sy(hp.se) - 9} textAnchor="end" className="anno">cycle {hc}</text></g>}
          {hv && <circle cx={sx(hv.eff)} cy={sy(hv.se)} r={4.5} className="mark-hover" />}
          <text x={w - m.r - 4} y={sy(y0) - 12} textAnchor="end" className="anno strong">r = {fit.r}</text>
        </svg>
        {hv && (
          <div className="tip" style={{ left: Math.min(w - 170, Math.max(0, sx(hv.eff) + 10)), top: Math.max(0, sy(hv.se) - 64) }}>
            <div className="tip-h">Cycle {hv.i}</div>
            <div>η {fmt(hv.eff, 2)} % · SE {fmt(hv.se, 2)} %</div>
            <div className="fine">valve {hv.valve} % · leak {hv.leak} · acc {hv.acc} bar · cooler {hv.cooler} %</div>
          </div>
        )}
      </div>
    </figure>
  )
}
