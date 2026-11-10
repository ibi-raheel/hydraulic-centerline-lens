import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useData, pct } from './data'
import type { Component } from './components/Schematic'
import { useReducedMotion } from './hooks'
import { RigStep } from './steps/RigStep'
import { ContractStep } from './steps/ContractStep'
import { KpiStep } from './steps/KpiStep'
import { BandStep } from './steps/BandStep'
import { CalibStep } from './steps/CalibStep'
import { FaultStep } from './steps/FaultStep'
import { CostStep } from './steps/CostStep'
import { ProofStep } from './steps/ProofStep'
import { SolutionStep } from './steps/SolutionStep'

const STEPS = [
  { id: 'rig', short: 'The rig' },
  { id: 'contract', short: 'Data contract' },
  { id: 'kpi', short: 'A KPI you can trust' },
  { id: 'band', short: 'Golden-run bands' },
  { id: 'context', short: 'Calibrated for context' },
  { id: 'fault', short: 'Which component' },
  { id: 'cost', short: 'What it costs' },
  { id: 'proof', short: 'How we know' },
  { id: 'solution', short: 'The solution' },
]

function Step({ n, id, title, lede, children }: { n: number; id: string; title: string; lede: ReactNode; children: ReactNode }) {
  return (
    <section className="step" id={id} data-step={n} aria-labelledby={`${id}-h`}>
      <header className="step-head">
        <h2 id={`${id}-h`}><span className="step-num mono" aria-hidden="true">{n}</span>{title}</h2>
        <p className="lede">{lede}</p>
      </header>
      {children}
    </section>
  )
}

export function App() {
  const { d, err } = useData()
  const reduced = useReducedMotion()
  const [active, setActive] = useState(1)
  const [comp, setComp] = useState<Component>('valve')
  const [physics, setPhysics] = useState(true)
  const [picked, setPicked] = useState<Component | null>(null)
  const main = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!d || !main.current) return
    const secs = Array.from(main.current.querySelectorAll<HTMLElement>('section.step'))
    const io = new IntersectionObserver(entries => {
      for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.step))
    }, { rootMargin: '-45% 0px -50% 0px' })
    secs.forEach(s => io.observe(s))
    return () => io.disconnect()
  }, [d])

  const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' })
  const onPick = (c: Component) => { setComp(c); setPicked(c); go('fault') }

  if (err) return <main className="state"><p>{err}</p></main>
  if (!d) return <main className="state" aria-busy="true"><p className="mono">Loading 2,205 cycles of results…</p></main>

  const v = d.x.models.find(m => m.target === 'valve')!
  const a = d.x.models.find(m => m.target === 'accumulator')!
  const sc = d.x.calibration.modes.single_context.at_k4_f5.false_alarm
  const pc = d.x.calibration.modes.per_context.operating_point.false_alarm
  const e1 = d.x.value.energy.leak1.median
  const leak = d.x.calibration.modes.per_context.operating_point.conditions.filter(c => c.component === 'leak')
  const leakN = leak.reduce((t, c) => t + c.n, 0)

  return (
    <>
      <nav className="rail" aria-label="Steps">
        <ol>
          {STEPS.map((s, i) => (
            <li key={s.id}>
              <a href={`#${s.id}`} aria-current={active === i + 1 ? 'step' : undefined} onClick={ev => { ev.preventDefault(); go(s.id) }}>
                <span className="rail-n mono">{i + 1}</span><span className="rail-t">{s.short}</span>
              </a>
            </li>
          ))}
        </ol>
      </nav>
      <div className="topbar" aria-hidden="true">
        <div className="topbar-segs">{STEPS.map((s, i) => <i key={s.id} className={i + 1 <= active ? 'on' : ''} />)}</div>
        <div className="topbar-t"><span className="mono">{active}/{STEPS.length}</span> {STEPS[active - 1].short}</div>
      </div>

      <main ref={main}>
        <header className="intro">
          <h1>Hydraulic Centerline Lens</h1>
          <div className="qa">
            <p className="kicker mono">The question</p>
            <p className="qa-q">How many golden runs before a centerline can be trusted?</p>
            <p className="kicker mono">The answer, measured on {d.s.n_cycles.toLocaleString()} real cycles</p>
            <p className="qa-a"><strong className="qa-big">About 9 per operating condition.</strong> One golden set copied across conditions false-alarmed on {sc.k} of {sc.n} healthy cycles. One band per condition: {pc.k} of {pc.n}, with all {leakN} leakage cycles still caught.</p>
            <p className="kicker mono">The solution</p>
            <p className="qa-a">A five-step acceptance recipe and a small tool that says, per condition, whether a line's centerline is ready to trust.</p>
            <a className="qa-link" href="#solution" onClick={ev => { ev.preventDefault(); go('solution') }}>Here's the playbook <span aria-hidden="true">→</span></a>
            <p className="fine">Real hydraulic test-rig data (UCI, CC BY 4.0). Every KPI checked by hand.</p>
          </div>
        </header>

        <Step n={1} id="rig" title="The rig" lede={<>One 60 s load cycle, repeated {d.s.n_cycles.toLocaleString()} times while four components are set to known fault levels. {d.s.n_channels} channels record it.</>}>
          <RigStep d={d} onPick={onPick} active={picked} />
        </Step>

        <Step n={2} id="contract" title="The data contract" lede={<>Eleven rules run before any KPI. The seven range rules caught 1 of 5 injected defect types; four physics rules catch the rest.</>}>
          <ContractStep d={d} />
        </Step>

        <Step n={3} id="kpi" title="A KPI you can trust" lede={<>Hydraulic efficiency from two sensors, worked by hand, matches the pipeline and tracks the rig's own efficiency channel at r = {d.s.kpi.fit.r}.</>}>
          <KpiStep d={d} />
        </Step>

        <Step n={4} id="band" title="Golden-run bands" lede={<>{d.e.n_golden} golden cycles set a band for every sensor. Pick a fault and watch the trace leave it.</>}>
          <BandStep d={d} />
        </Step>

        <Step n={5} id="context" title="Calibrated for context" lede={<>One golden set raised false alarms on {sc.k} of {sc.n} healthy cycles. One band per operating context gets that to {pc.k} of {pc.n}.</>}>
          <CalibStep d={d} />
        </Step>

        <Step n={6} id="fault" title="Which component is failing" lede={<>Physics features lift valve accuracy from {pct(v.base.blocked)} to {pct(v.with_physics.blocked)} and accumulator from {pct(a.base.blocked)} to {pct(a.with_physics.blocked)} on blocked validation. Toggle them.</>}>
          <FaultStep d={d} comp={comp} setComp={setComp} physics={physics} setPhysics={setPhysics} />
        </Step>

        <Step n={7} id="cost" title="What it costs" lede={<>Weak pump leakage costs {Math.abs(d.x.value.leak1.eff_pts.median).toFixed(1)} efficiency points: {e1.extra_motor_pct.toFixed(1)} % more motor energy for the same hydraulic work.</>}>
          <CostStep d={d} />
        </Step>

        <Step n={8} id="proof" title="How we know it's right" lede={<>Neighbouring cycles are near-duplicates, so shuffled validation flatters. Scored on contiguous blocks, the accumulator drops from {pct(d.x.block_sensitivity.accumulator.shuffled)} to {pct(a.base.blocked)}.</>}>
          <ProofStep d={d} />
        </Step>

        <Step n={9} id="solution" title="The solution" lede="A one-page recipe and a small tool. Give it a line's data and the cycles you call golden; it tells you whether to trust the centerline.">
          <SolutionStep d={d} />
        </Step>

        <p className="closing">Built on public test-rig data, so these thresholds are this rig's. On a real line, week one re-measures them: run the contract, collect golden cycles per context, hand back the recipe with that line's numbers.</p>

        <footer className="foot">
          <p>Data: N. Helwig, E. Pignanelli, A. Schütze (2015), <i>Condition monitoring of hydraulic systems</i>, UCI ML Repository, <a href="https://doi.org/10.24432/C5CW21">doi:10.24432/C5CW21</a>, licensed CC BY 4.0. Full dataset, no subsetting; results precomputed by the pipeline in this repository.</p>
          <p>Built by Ibi Raheel, mechanical engineer building AI tools. More work at <a href="https://ibiraheel.com">ibiraheel.com</a>. Code, method and tests on <a href="https://github.com/ibi-raheel/hydraulic-centerline-lens">GitHub</a>.</p>
        </footer>
      </main>
    </>
  )
}
