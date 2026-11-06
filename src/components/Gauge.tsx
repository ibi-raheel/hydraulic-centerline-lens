// A Bourdon-tube style dial: 240° sweep, major/minor ticks, an optional acceptance arc (the golden band at the cursor), and a needle.
type Props = {
  value: number
  min: number
  max: number
  major: number // value step between numbered ticks
  minor?: number // minor ticks per major interval
  label: string
  unit: string
  zone?: [number, number] | null
  alarm?: boolean
  size?: number
  decimals?: number
  smooth?: boolean // CSS transition on the needle (for discrete changes); off when driven per frame
  tickFormat?: (v: number) => string
  readout?: string
}

const SWEEP = 240
const START = -120

function polar(cx: number, cy: number, r: number, deg: number) {
  const a = ((deg - 90) * Math.PI) / 180
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
}
function arc(cx: number, cy: number, r: number, a0: number, a1: number) {
  const [x0, y0] = polar(cx, cy, r, a0)
  const [x1, y1] = polar(cx, cy, r, a1)
  const large = a1 - a0 > 180 ? 1 : 0
  return `M${x0.toFixed(2)},${y0.toFixed(2)} A${r},${r} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)}`
}

export function Gauge({ value, min, max, major, minor = 4, label, unit, zone, alarm, size = 120, decimals = 1, smooth, tickFormat, readout }: Props) {
  const c = 50
  const clamp = (v: number) => Math.max(min, Math.min(max, v))
  const ang = (v: number) => START + ((clamp(v) - min) / (max - min)) * SWEEP
  const ticks: { v: number; major: boolean }[] = []
  const nMaj = Math.round((max - min) / major)
  for (let i = 0; i <= nMaj; i++) {
    for (let j = 0; j < (i === nMaj ? 1 : minor); j++) ticks.push({ v: min + i * major + (j * major) / minor, major: j === 0 })
  }
  const fmtTick = tickFormat ?? ((v: number) => `${Math.round(v * 100) / 100}`)
  const needle = ang(value)
  const z = zone ? [ang(Math.min(zone[0], zone[1])), ang(Math.max(zone[0], zone[1]))] : null
  const zoneVisible = z && z[1] - z[0] < 0.6 ? [z[0] - 0.3, z[1] + 0.3] : z
  return (
    <figure className={`gauge${alarm ? ' is-alarm' : ''}`} style={{ width: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={`${label}: ${value.toFixed(decimals)} ${unit}`}>
        <circle cx={c} cy={c} r={47} className="gauge-bezel" />
        <circle cx={c} cy={c} r={43.5} className="gauge-face" />
        {zoneVisible && <path d={arc(c, c, 38.5, zoneVisible[0], zoneVisible[1])} className="gauge-zone" />}
        {ticks.map(t => {
          const a = ang(t.v)
          const [x0, y0] = polar(c, c, t.major ? 33 : 35.5, a)
          const [x1, y1] = polar(c, c, 40, a)
          return <line key={t.v} x1={x0} y1={y0} x2={x1} y2={y1} className={t.major ? 'gauge-tick-major' : 'gauge-tick-minor'} />
        })}
        {ticks.filter(t => t.major).map(t => {
          const [x, y] = polar(c, c, 26.5, ang(t.v))
          return <text key={t.v} x={x} y={y} className="gauge-num" textAnchor="middle" dominantBaseline="central">{fmtTick(t.v)}</text>
        })}
        <text x={c} y={c + 15} className="gauge-unit" textAnchor="middle">{unit}</text>
        <g className={`gauge-needle${smooth ? ' is-smooth' : ''}`} style={{ transform: `rotate(${needle}deg)` }}>
          <path d={`M${c - 1.6},${c + 7} L${c},${c - 37} L${c + 1.6},${c + 7} Z`} />
        </g>
        <circle cx={c} cy={c} r={4.2} className="gauge-hub" />
        <circle cx={c} cy={c} r={1.4} className="gauge-hub-pin" />
      </svg>
      <figcaption>
        <span className="gauge-label">{label}</span>
        <span className="gauge-readout">{readout ?? value.toFixed(decimals)}</span>
      </figcaption>
    </figure>
  )
}
