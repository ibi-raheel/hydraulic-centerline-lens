import { useState } from 'react'
import type { Data } from '../data'
import { Gauge } from '../components/Gauge'
import { Details, Seg } from './common'

type Lvl = 0 | 1 | 2

export function CostStep({ d }: { d: Data }) {
  const [lvl, setLvl] = useState<Lvl>(1)
  const v = d.x.value
  const eff = lvl === 0 ? null : lvl === 1 ? v.leak1.eff_pts : v.leak2.eff_pts
  const en = lvl === 0 ? null : lvl === 1 ? v.energy.leak1 : v.energy.leak2
  const lost = eff ? -eff.median : 0
  const extra = en ? en.median.extra_motor_pct : 0
  const usd = (x: number) => `$${Math.round(x).toLocaleString()}`
  return (
    <div className="cost">
      <Seg<Lvl> label="Pump leakage" value={lvl} onChange={setLvl} options={[{ v: 0, label: 'No leakage' }, { v: 1, label: 'Weak leakage' }, { v: 2, label: 'Severe leakage' }]} />
      <div className="cost-dials">
        <Gauge label="Efficiency lost" unit="points" value={lost} min={0} max={6} major={1} minor={5} size={208} smooth
          zone={eff ? [-eff.hi, -eff.lo] : null} readout={eff ? `−${lost.toFixed(1)} pts` : '0 pts'} />
        <Gauge label="Extra motor energy" unit="%" value={extra} min={0} max={8} major={2} minor={4} size={208} smooth
          zone={en ? [en.hi.extra_motor_pct, en.lo.extra_motor_pct] : null} readout={en ? `+${extra.toFixed(1)} %` : '0 %'} />
      </div>
      <p className="cost-line" aria-live="polite">
        {en
          ? <>About <span className="mono strong">{usd(en.median.extra_usd_yr)}</span> a year for every {v.per_installed_hydraulic_kw} kW of hydraulic power delivered <span className="fine">(95 % CI {usd(en.hi.extra_usd_yr)}–{usd(en.lo.extra_usd_yr)}; {v.duty_h_per_yr.toLocaleString()} h/yr at {(v.price_usd_kwh * 100).toFixed(2)} ¢/kWh)</span></>
          : <>Healthy pump: median η {(v.eta_ok * 100).toFixed(1)} %. Pick a leakage level.</>}
      </p>
      <Details>
        <p>Matched comparison: within each of {v.leak1.eff_pts.n_cells} cells of identical cooler, valve and accumulator state, the difference in median η; median over cells with a bootstrap 95 % CI. For the same hydraulic work W, extra motor energy is W·(1/η<sub>leak</sub> − 1/η<sub>ok</sub>).</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Leakage</th><th className="num">Δη, points</th><th className="num">Extra motor energy</th><th className="num">kWh / yr per 10 kW</th><th className="num">$ / yr per 10 kW</th></tr></thead>
          <tbody>
            {([['Weak', v.leak1.eff_pts, v.energy.leak1], ['Severe', v.leak2.eff_pts, v.energy.leak2]] as const).map(([n, e, g]) => (
              <tr key={n}><td>{n}</td><td className="num">{e.median.toFixed(1)} ({e.lo.toFixed(2)} to {e.hi.toFixed(2)})</td><td className="num">+{g.median.extra_motor_pct.toFixed(1)} %</td><td className="num">{Math.round(g.median.extra_kwh_yr).toLocaleString()}</td><td className="num">{usd(g.median.extra_usd_yr)} ({usd(g.hi.extra_usd_yr)}–{usd(g.lo.extra_usd_yr)})</td></tr>
            ))}
          </tbody>
        </table></div>
        <p className="fine">Price: {v.price_source}. The energy cost is real but modest; the stronger argument is that the weak stage is recognisable early. The dataset holds fixed leakage levels, not a progression over time, so lead time in a plant is inferred, not measured.</p>
      </Details>
    </div>
  )
}
