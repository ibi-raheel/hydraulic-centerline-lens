import { useMemo, useState } from 'react'
import type { Data } from '../data'
import { pct } from '../data'
import { Gauge } from '../components/Gauge'
import { niceTicks, scale, useWidth } from '../hooks'
import { interp } from './RigStep'
import { Details, Key } from './common'

const NAMES: Record<string, string> = {
  golden: 'Golden',
  'valve=90': 'Valve 90 %', 'valve=80': 'Valve 80 %', 'valve=73': 'Valve 73 %',
  'leak=1': 'Leak weak', 'leak=2': 'Leak severe',
  'accumulator=115': 'Acc 115 bar', 'accumulator=100': 'Acc 100 bar', 'accumulator=90': 'Acc 90 bar',
}

export function BandStep({ d }: { d: Data }) {
  const e = d.e
  const ex = Object.entries(e.examples)
  const [key, setKey] = useState('leak=2')
  const [tag, setTag] = useState('EPS1')
  const [t, setT] = useState(30)
  const cyc = e.cycles[String(e.examples[key])]
  const pick = (k: string) => {
    setKey(k)
    const c = e.cycles[String(e.examples[k])]
    const best = e.tags.reduce((a, b) => (c.frac[b] > c.frac[a] ? b : a), e.tags[0])
    if (c.frac[best] > e.alarm_frac) setTag(best)
  }
  const band = e.band[tag]
  const kW = tag === 'EPS1' ? 1000 : 1
  const unit = tag === 'EPS1' ? 'kW' : e.units[tag]
  const val = interp(e.t, cyc.trace[tag], t) / kW
  const lo = interp(e.t, band.lo, t) / kW
  const hi = interp(e.t, band.hi, t) / kW
  const out = val < lo || val > hi
  const nAlarm = e.tags.filter(g => cyc.frac[g] > e.alarm_frac).length

  const gr = useMemo(() => {
    let a = Infinity, b = -Infinity
    for (const arr of [band.lo, band.hi, ...Object.values(e.cycles).map(c => c.trace[tag])]) for (const v of arr) { a = Math.min(a, v); b = Math.max(b, v) }
    const ticks = niceTicks(a / kW, b / kW, 4)
    const step = ticks[1] - ticks[0]
    const min = Math.floor(a / kW / step) * step
    const max = Math.ceil(b / kW / step) * step
    return { min, max, step }
  }, [tag, band, e.cycles, kW])
  const dec = gr.step < 0.1 ? 3 : gr.step < 1 ? 2 : 1

  return (
    <div className="band">
      <div className="chips" role="radiogroup" aria-label="Cycle">
        {ex.map(([k, id]) => (
          <button key={k} type="button" role="radio" aria-checked={k === key} className={`chip${k === key ? ' is-on' : ''}`} onClick={() => pick(k)}>
            {NAMES[k] ?? k}<span className="chip-id">{id}</span>
          </button>
        ))}
      </div>
      <div className="band-grid">
        <BandChart d={d} tag={tag} cycleKey={key} t={t} setT={setT} kW={kW} unit={unit} />
        <aside className="band-side">
          <Gauge label={`${tag} at t = ${t.toFixed(1)} s`} unit={unit} value={val} min={gr.min} max={gr.max} major={gr.step} minor={5} zone={[lo, hi]} alarm={out} size={168} decimals={dec}
            tickFormat={v => (gr.step < 1 ? v.toFixed(gr.step < 0.1 ? 2 : 1) : String(Math.round(v)))} readout={`${val.toFixed(dec)} ${unit}`} />
          <p className={`band-state${out ? ' is-out' : ''}`}>{out ? 'Outside the band' : 'Inside the band'} <span className="mono">[{lo.toFixed(dec)}, {hi.toFixed(dec)}]</span></p>
          <div className="tags" role="radiogroup" aria-label="Sensor">
            <div className="tags-head"><span>Time out of band</span><span className="mono">alarm &gt; {pct(e.alarm_frac, 0)}</span></div>
            {e.tags.map(g => {
              const f = cyc.frac[g]
              const al = f > e.alarm_frac
              return (
                <button key={g} type="button" role="radio" aria-checked={g === tag} className={`tag${g === tag ? ' is-on' : ''}${al ? ' is-alarm' : ''}`} onClick={() => setTag(g)}>
                  <span className="mono tag-n">{g}</span>
                  <span className="tag-track"><span className="tag-bar" style={{ width: `${Math.max(f * 100, 0.6)}%` }} /><span className="tag-thr" style={{ left: `${e.alarm_frac * 100}%` }} /></span>
                  <span className="mono tag-v">{pct(f, 0)}</span>
                </button>
              )
            })}
          </div>
          <p className="fine">{nAlarm === 0 ? 'No sensor alarms on this cycle.' : `${nAlarm} of ${e.tags.length} sensors alarm on this cycle.`}</p>
        </aside>
      </div>
      <Details>
        <p>Band = median ± {e.k} · 1.4826 · MAD per 0.1 s bin, built from {e.n_golden} golden cycles (cooler 100 %, valve 100 %, no leakage, 130 bar, stable). A cycle alarms when any sensor spends more than {pct(e.alarm_frac, 0)} of the cycle outside its band. Leave-one-out, {e.loo_false_alarm} of {e.n_golden} golden cycles alarms.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Fault (cooler 100 %)</th><th className="num">n</th><th className="num">Alarm rate</th><th>Sensors out of band</th></tr></thead>
          <tbody>{d.e.conditions.map(c => (
            <tr key={c.component + c.level}><td>{c.component} {c.level}</td><td className="num">{c.n}</td><td className="num">{pct(c.alarm_rate, 0)}</td><td className="mono">{Object.entries(c.tag_rate).filter(([, v]) => v >= 0.5).map(([k]) => k).join(' ') || 'none'}</td></tr>
          ))}</tbody>
        </table></div>
        <p className="fine">Traces are drawn from 0.5 s samples; the out-of-band share comes from the pipeline's 0.1 s bins.</p>
      </Details>
    </div>
  )
}

function BandChart({ d, tag, cycleKey, t, setT, kW, unit }: { d: Data; tag: string; cycleKey: string; t: number; setT: (t: number) => void; kW: number; unit: string }) {
  const e = d.e
  const [ref, w] = useWidth<HTMLDivElement>(620)
  const H = Math.round(Math.min(360, Math.max(240, w * 0.56)))
  const m = { l: 48, r: 12, t: 16, b: 34 }
  const band = e.band[tag]
  const tr = e.cycles[String(e.examples[cycleKey])].trace[tag]
  const T = e.t
  const tMax = T[T.length - 1]
  const sx = scale(0, tMax, m.l, w - m.r)
  const [y0, y1] = useMemo(() => {
    let a = Infinity, b = -Infinity
    for (const arr of [band.lo, band.hi, tr]) for (const v of arr) { a = Math.min(a, v); b = Math.max(b, v) }
    const pad = (b - a) * 0.08 || 0.05
    return [(a - pad) / kW, (b + pad) / kW]
  }, [band, tr, kW])
  const sy = scale(y0, y1, H - m.b, m.t)
  const P = (ys: number[]) => ys.map((y, i) => `${i ? 'L' : 'M'}${sx(T[i]).toFixed(1)},${sy(y / kW).toFixed(1)}`).join('')
  const area = `${P(band.hi)}${band.lo.map((y, i) => `L${sx(T[T.length - 1 - i]).toFixed(1)},${sy(band.lo[T.length - 1 - i] / kW).toFixed(1)}`).join('')}Z`
  const outSegs: string[] = []
  for (let i = 0; i < T.length - 1; i++) {
    const o = (j: number) => tr[j] < band.lo[j] || tr[j] > band.hi[j]
    if (o(i) || o(i + 1)) outSegs.push(`M${sx(T[i]).toFixed(1)},${sy(tr[i] / kW).toFixed(1)}L${sx(T[i + 1]).toFixed(1)},${sy(tr[i + 1] / kW).toFixed(1)}`)
  }
  const yt = niceTicks(y0, y1, 4)
  const dec = yt.length > 1 && yt[1] - yt[0] < 0.1 ? 2 : yt.length > 1 && yt[1] - yt[0] < 1 ? 1 : 0
  const toT = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect()
    const v = ((clientX - r.left - m.l) / (w - m.l - m.r)) * tMax
    setT(Math.max(0, Math.min(tMax, Math.round(v * 10) / 10)))
  }
  const cv = interp(T, tr, t) / kW
  return (
    <figure className="chart band-chart" ref={ref}>
      <div className="viz-head">
        <Key kind="band">golden band</Key>
        <Key kind="ink">centerline</Key>
        <Key kind="blue">this cycle</Key>
        <Key kind="orange">out of band</Key>
      </div>
      <div className="chart-box">
        <svg width={w} height={H} className="scrubbable" tabIndex={0} role="slider" aria-label={`${tag} trace against the golden band; time cursor`} aria-valuemin={0} aria-valuemax={tMax} aria-valuenow={t} aria-valuetext={`${t.toFixed(1)} seconds`}
          onPointerDown={ev => { (ev.currentTarget as Element).setPointerCapture(ev.pointerId); toT(ev.clientX, ev.currentTarget) }}
          onPointerMove={ev => { if (ev.buttons || ev.pointerType === 'mouse') toT(ev.clientX, ev.currentTarget) }}
          onKeyDown={ev => { if (ev.key === 'ArrowRight') { ev.preventDefault(); setT(Math.min(tMax, t + (ev.shiftKey ? 5 : 0.5))) } if (ev.key === 'ArrowLeft') { ev.preventDefault(); setT(Math.max(0, t - (ev.shiftKey ? 5 : 0.5))) } }}>
          {yt.map(v => <g key={v}><line x1={m.l} x2={w - m.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={m.l - 6} y={sy(v)} className="tick" textAnchor="end" dominantBaseline="central">{v.toFixed(dec)}</text></g>)}
          {[0, 10, 20, 30, 40, 50, 60].map(v => <text key={v} x={sx(Math.min(v, tMax))} y={H - m.b + 16} className="tick" textAnchor="middle">{v}</text>)}
          <line x1={m.l} x2={w - m.r} y1={H - m.b} y2={H - m.b} className="axis" />
          <text x={w - m.r} y={H - 3} className="axis-label" textAnchor="end">time in cycle, s</text>
          <text x={m.l} y={m.t - 4} className="axis-label">{tag}, {unit}</text>
          <path d={area} className="band-area" />
          <path d={P(band.c)} className="band-center" />
          <path d={P(tr)} className="trace" />
          <path d={outSegs.join('')} className="trace-out" />
          <line x1={sx(t)} x2={sx(t)} y1={m.t} y2={H - m.b} className="cursor" />
          <circle cx={sx(t)} cy={sy(cv)} r={4.5} className="cursor-dot" />
        </svg>
      </div>
      <p className="fine scrub-hint">Drag across the chart, or focus it and use the arrow keys, to move the cursor.</p>
    </figure>
  )
}
