import { useEffect, useMemo, useState } from 'react'
import type { Data } from '../data'
import { Gauge } from '../components/Gauge'
import { Schematic, type Component } from '../components/Schematic'
import { useInView, useReducedMotion } from '../hooks'
import { Details } from './common'

export function interp(ts: number[], ys: number[], t: number) {
  const dt = ts[1] - ts[0]
  const i = Math.max(0, Math.min(ts.length - 2, Math.floor((t - ts[0]) / dt)))
  const f = Math.max(0, Math.min(1, (t - ts[i]) / dt))
  return ys[i] + (ys[i + 1] - ys[i]) * f
}

const SPEED = 3 // 60 s cycle plays in 20 s

export function RigStep({ d, onPick, active }: { d: Data; onPick: (c: Component) => void; active: Component | null }) {
  const reduced = useReducedMotion()
  const [ref, inView] = useInView<HTMLDivElement>()
  const [t, setT] = useState(30)
  const [playing, setPlaying] = useState(true)
  const run = playing && inView && !reduced
  const goldenId = d.e.examples.golden
  const g = d.e.cycles[String(goldenId)]
  const tMax = d.e.t[d.e.t.length - 1]

  useEffect(() => {
    if (!run) return
    let raf = 0
    let last = performance.now()
    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000)
      last = now
      setT(v => (v + dt * SPEED) % tMax)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [run, tMax])

  const v = (tag: string) => interp(d.e.t, g.trace[tag], t)
  const track = useMemo(() => {
    const ys = d.e.band.PS1.c
    const max = 200
    return ys.map((y, i) => `${i === 0 ? 'M' : 'L'}${((i / (ys.length - 1)) * 100).toFixed(2)},${(22 - (y / max) * 20).toFixed(2)}`).join(' ')
  }, [d])

  const chans = Object.keys(d.s.rates)
  const gs = 148
  return (
    <div ref={ref}>
      <div className="rig-card">
      <Schematic onPick={onPick} active={active} flowing={run} />
      <div className="dials" aria-live="off">
        <Gauge label="PS1 pump outlet" unit="bar" value={v('PS1')} min={0} max={200} major={50} decimals={1} size={gs} />
        <Gauge label="PS2 after valve" unit="bar" value={v('PS2')} min={0} max={200} major={50} decimals={1} size={gs} />
        <Gauge label="FS1 main flow" unit="l/min" value={v('FS1')} min={0} max={25} major={5} decimals={2} size={gs} />
        <Gauge label="EPS1 motor" unit="kW" value={v('EPS1') / 1000} min={0} max={4} major={1} decimals={2} size={gs} />
      </div>
      <div className="timeline">
        <button type="button" className="icon-btn" onClick={() => setPlaying(p => !p)} aria-label={run ? 'Pause the cycle' : 'Play the cycle'} disabled={reduced}>
          {run
            ? <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="3" width="3" height="10" rx="0.5" /><rect x="9.5" y="3" width="3" height="10" rx="0.5" /></svg>
            : <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 2.8v10.4L13 8z" /></svg>}
        </button>
        <div className="scrub">
          <svg viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true"><path d={track} vectorEffect="non-scaling-stroke" /></svg>
          <input type="range" min={0} max={tMax} step={0.1} value={t} onChange={e => { setPlaying(false); setT(+e.target.value) }} aria-label="Time in cycle, seconds" />
        </div>
        <output className="mono t-readout">t = {t.toFixed(1)} s</output>
      </div>
      </div>
      <p className="caption">Golden cycle {goldenId}, replayed from the shipped 0.5 s traces. Click the pump, valve, accumulator or cooler to open its fault model.</p>
      <Details>
        <p>Every cycle is labelled with the state of four components. These counts match the dataset documentation{d.s.labels_match_doc ? '' : ' (they do not)'}.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Component</th><th>Levels (cycles)</th></tr></thead>
          <tbody>
            <tr><td>Cooler efficiency</td><td className="num">{Object.entries(d.s.labels.cooler).map(([k, n]) => `${k} %: ${n}`).join(' · ')}</td></tr>
            <tr><td>Valve opening</td><td className="num">{Object.entries(d.s.labels.valve).map(([k, n]) => `${k} %: ${n}`).join(' · ')}</td></tr>
            <tr><td>Pump leakage</td><td className="num">{Object.entries(d.s.labels.leak).map(([k, n]) => `${['none', 'weak', 'severe'][+k]}: ${n}`).join(' · ')}</td></tr>
            <tr><td>Accumulator pre-charge</td><td className="num">{Object.entries(d.s.labels.accumulator).map(([k, n]) => `${k} bar: ${n}`).join(' · ')}</td></tr>
          </tbody>
        </table></div>
        <div className="table-wrap"><table>
          <thead><tr><th>Channel</th><th>Unit</th><th className="num">Rate</th></tr></thead>
          <tbody>{chans.map(c => <tr key={c}><td className="mono">{c}</td><td>{d.s.units[c]}</td><td className="num">{d.s.rates[c]} Hz</td></tr>)}</tbody>
        </table></div>
        <p className="fine">The schematic is simplified and drawn with ISO 1219 symbols; sensor positions are indicative. Everything is resampled to a common 10 Hz grid before analysis.</p>
      </Details>
    </div>
  )
}
