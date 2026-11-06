import { useEffect, useState } from 'react'

// Minimal results page. The guided-story UI is a later pass; this only proves the static JSON loads.
type Model = { target: string; acc_blocked: number; acc_random: number; acc_majority: number; published: string; tag_importance: Record<string, number> }
type Summary = {
  n_cycles: number; n_channels: number; labels_match_doc: boolean
  spec: { id: string; name: string; rule: string; pass: number; fail: number }[]
  kpi: { hand: Record<string, number>; fit: { slope: number; intercept: number; r: number; resid_sd: number }; eff_by_leak: Record<string, number> }
  models: Model[]
}
type Cond = { component: string; level: number; n: number; alarm_rate: number; tag_rate: Record<string, number> }
type Env = { n_golden: number; loo_false_alarm: number; k: number; alarm_frac: number; conditions: Cond[] }

const pct = (x: number) => `${(100 * x).toFixed(1)}%`
const cell = { padding: '4px 10px', borderBottom: '1px solid #ccc', textAlign: 'left' as const }

export function App() {
  const [s, setS] = useState<Summary | null>(null)
  const [e, setE] = useState<Env | null>(null)
  useEffect(() => {
    fetch('/data/summary.json').then(r => r.json()).then(setS)
    fetch('/data/envelope.json').then(r => r.json()).then(setE)
  }, [])
  if (!s || !e) return <p style={{ fontFamily: 'system-ui', padding: 24 }}>Loading results…</p>
  const h = s.kpi.hand
  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 960, margin: '0 auto', padding: 24, lineHeight: 1.45 }}>
      <h1>Hydraulic Centerline Lens</h1>
      <p>{s.n_cycles.toLocaleString()} real 60 s load cycles, {s.n_channels} sensor channels, from the UCI hydraulic test-rig dataset (CC BY 4.0).</p>

      <h2>1. Data contract</h2>
      <table style={{ borderCollapse: 'collapse' }}><tbody>
        {s.spec.map(r => <tr key={r.id}><td style={cell}>{r.id}</td><td style={cell}>{r.name}</td><td style={cell}><code>{r.rule}</code></td><td style={cell}>{r.pass} pass / {r.fail} fail</td></tr>)}
      </tbody></table>
      <p>Label counts match the dataset documentation: {s.labels_match_doc ? 'yes' : 'no'}.</p>

      <h2>2. Hydraulic power, checked by hand</h2>
      <p>Cycle {h.cycle}, t = {h.t_s} s: P_hyd = p·Q/600 = {h.p_bar} bar × {h.q_lpm} l/min / 600 = <b>{h.p_hyd_kw} kW</b>.
        Cycle mean: {h.cycle_p_hyd_kw} kW hydraulic / {h.cycle_p_motor_kw} kW motor = {h.cycle_eff_pct}% (rig SE channel: {h.cycle_se_pct}%).</p>
      <p>Across all cycles, derived efficiency vs rig SE: r = {s.kpi.fit.r}, SE ≈ {s.kpi.fit.slope}·η + {s.kpi.fit.intercept}, residual SD {s.kpi.fit.resid_sd} pts.</p>

      <h2>3. Golden-run centerline</h2>
      <p>{e.n_golden} golden cycles, band = median ± {e.k}·1.4826·MAD per 0.1 s bin. Leave-one-out false alarms: {e.loo_false_alarm}/{e.n_golden}.</p>
      <table style={{ borderCollapse: 'collapse' }}><thead><tr><th style={cell}>Fault</th><th style={cell}>n</th><th style={cell}>Alarm rate</th><th style={cell}>Tags out of band</th></tr></thead><tbody>
        {e.conditions.map(c => <tr key={c.component + c.level}><td style={cell}>{c.component} = {c.level}</td><td style={cell}>{c.n}</td><td style={cell}>{pct(c.alarm_rate)}</td>
          <td style={cell}>{Object.entries(c.tag_rate).filter(([, v]) => v >= 0.5).map(([k]) => k).join(', ') || 'none'}</td></tr>)}
      </tbody></table>

      <h2>4. Root cause classifiers</h2>
      <table style={{ borderCollapse: 'collapse' }}><thead><tr><th style={cell}>Component</th><th style={cell}>Blocked CV</th><th style={cell}>Shuffled CV</th><th style={cell}>Majority</th><th style={cell}>Published</th><th style={cell}>Top tags</th></tr></thead><tbody>
        {s.models.map(m => <tr key={m.target}><td style={cell}>{m.target}</td><td style={cell}>{pct(m.acc_blocked)}</td><td style={cell}>{pct(m.acc_random)}</td><td style={cell}>{pct(m.acc_majority)}</td><td style={cell}>{m.published}</td>
          <td style={cell}>{Object.keys(m.tag_importance).slice(0, 3).join(', ')}</td></tr>)}
      </tbody></table>

      <p style={{ marginTop: 32, fontSize: 14 }}>Data: Helwig, Pignanelli, Schütze (2015), "Condition monitoring of hydraulic systems", UCI ML Repository, doi:10.24432/C5CW21, CC BY 4.0.
        Built by Ibi Raheel · <a href="https://ibiraheel.com">ibiraheel.com</a></p>
    </main>
  )
}
