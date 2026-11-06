import type { ReactNode } from 'react'

export function Details({ children, label = 'Show details' }: { children: ReactNode; label?: string }) {
  return (
    <details className="more">
      <summary>
        <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4 2.5 7.5 6 4 9.5" /></svg>
        <span>{label}</span>
      </summary>
      <div className="more-body">{children}</div>
    </details>
  )
}

export function Seg<T extends string | number>({ options, value, onChange, label }: { options: { v: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map(o => (
        <button key={String(o.v)} type="button" role="radio" aria-checked={o.v === value} className={o.v === value ? 'is-on' : ''} onClick={() => onChange(o.v)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Key({ kind, children }: { kind: 'blue' | 'orange' | 'muted' | 'band' | 'ink'; children: ReactNode }) {
  return <span className="key"><i className={`key-${kind}`} aria-hidden="true" />{children}</span>
}
