import { useEffect, useState } from 'react'

// Types for the precomputed pipeline output in public/data. Values are read as shipped; nothing is recomputed here.

export type Spec = { id: string; name: string; rule: string; pass: number; fail: number }
export type Confusion = number[][]

export type Summary = {
  n_cycles: number
  n_channels: number
  rates: Record<string, number>
  units: Record<string, string>
  labels: Record<string, Record<string, number>>
  labels_match_doc: boolean
  spec: Spec[]
  kpi: {
    hand: {
      cycle: number; t_s: number; p_bar: number; q_lpm: number; p_motor_w: number; p_hyd_kw: number; eff_pct: number
      cycle_p_hyd_kw: number; cycle_p_motor_kw: number; cycle_eff_pct: number; cycle_se_pct: number
    }
    fit: { slope: number; intercept: number; r: number; resid_sd: number }
    eff_median: number
    se_median: number
    eff_by_leak: Record<string, number>
  }
  models: { target: string; acc_blocked: number; acc_random: number; acc_majority: number; published: string }[]
}

export type Band = { c: number[]; lo: number[]; hi: number[] }
export type EnvCycle = {
  label: { cooler: number; valve: number; leak: number; accumulator: number; stable_flag: number }
  trace: Record<string, number[]>
  frac: Record<string, number>
  area: Record<string, number>
}
export type Envelope = {
  tags: string[]
  units: Record<string, string>
  t: number[]
  k: number
  alarm_frac: number
  n_golden: number
  golden_ids: number[]
  loo_false_alarm: number
  band: Record<string, Band>
  cycles: Record<string, EnvCycle>
  examples: Record<string, number>
  conditions: { component: string; level: number; n: number; alarm_rate: number; top_tag: string; tag_rate: Record<string, number> }[]
}

export type Rate = { k: number; n: number; rate: number; lo: number; hi: number }
export type OpCondition = Rate & { component: string; level: number }
export type ModelScore = { blocked: number; blocked_lo: number; blocked_hi: number; shuffled: number; confusion: Confusion }
export type ExtModel = {
  target: string
  classes: number[]
  base: ModelScore
  with_physics: ModelScore
  physics_only: { n_features: number; blocked: number; blocked_lo: number; blocked_hi: number }
  top_features_with_physics: { name: string; imp: number }[]
}
type Mode = {
  operating_point: { k: number; f: number; false_alarm: Rate; detection_mean: number; conditions: OpCondition[] }
  at_k4_f5: { false_alarm: Rate; detection_mean: number; fa_by_cooler: Record<string, Rate> }
}
export type Extended = {
  calibration: {
    n_healthy: number
    modes: { single_context: Mode; per_context: Mode; pooled_detrend: Mode }
    sample_size: { k: number; f: number; rows: { n_golden: number; fa_mean: number; fa_p2_5: number; fa_p97_5: number; alarms: number; tests: number }[]; rule_of_three: Record<string, number> }
  }
  physics: {
    step_edges_s: number[]
    tau1_by_acc_cooler100_s: Record<string, { median: number; lo: number; hi: number; n: number }>
    valve_lag_PS2_ms: Record<string, { median: number; lo: number; hi: number }>
    loglog_slope: { value: number; lo: number; hi: number; bounds: Record<string, number> }
  }
  models: ExtModel[]
  block_sensitivity: Record<'accumulator' | 'valve', { shuffled: number; rows: { block: number; acc: number; gap_vs_shuffled_pts: number }[] }>
  leak_recall: Record<string, Rate>
  value: {
    leak1: { eff_pts: { n_cells: number; median: number; lo: number; hi: number } }
    leak2: { eff_pts: { n_cells: number; median: number; lo: number; hi: number } }
    eta_ok: number
    duty_h_per_yr: number
    price_usd_kwh: number
    price_source: string
    per_installed_hydraulic_kw: number
    energy: Record<'leak1' | 'leak2', Record<'median' | 'lo' | 'hi', { extra_motor_pct: number; extra_kwh_yr: number; extra_usd_yr: number }>>
  }
  mutations: {
    synthetic: boolean
    sample_n: number
    new_rule_fails_on_real_data: Record<string, number>
    rows: { mutation: string; n: number; caught_7_rules: number; caught_11_rules: number; by_rule: Record<string, number> }[]
    caught_7: number
    caught_11: number
  }
}
export type KpiPoint = { i: number; eff: number; se: number; valve: number; leak: number; acc: number; cooler: number }

export type Data = { s: Summary; e: Envelope; x: Extended; k: KpiPoint[] }

export function useData() {
  const [d, setD] = useState<Data | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    const get = (f: string) => fetch(`${import.meta.env.BASE_URL}data/${f}`).then(r => { if (!r.ok) throw new Error(f); return r.json() })
    Promise.all([get('summary.json'), get('envelope.json'), get('extended.json'), get('kpi_points.json')])
      .then(([s, e, x, k]) => setD({ s, e, x, k }))
      .catch(() => setErr('The precomputed results could not be loaded. Reload the page to try again.'))
  }, [])
  return { d, err }
}

export const pct = (x: number, dp = 1) => `${(100 * x).toFixed(dp)}%`
export const fmt = (x: number, dp = 1) => x.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp })
