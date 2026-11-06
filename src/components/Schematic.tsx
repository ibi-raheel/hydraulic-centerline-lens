import type { KeyboardEvent } from 'react'

// Simplified circuit drawn with ISO 1219 symbol conventions. Sensor positions are indicative, not a copy of the rig drawing.
export type Component = 'cooler' | 'valve' | 'leak' | 'accumulator'

type Props = { onPick: (c: Component) => void; active?: Component | null; flowing: boolean }

function Part({ id, label, active, onPick, children, hit }: { id: Component; label: string; active?: Component | null; onPick: (c: Component) => void; children: React.ReactNode; hit: [number, number, number, number] }) {
  const key = (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(id) } }
  return (
    <g className={`sc-part${active === id ? ' is-active' : ''}`} role="button" tabIndex={0} aria-label={`${label}: open its fault model`} onClick={() => onPick(id)} onKeyDown={key}>
      <rect className="sc-hit" x={hit[0]} y={hit[1]} width={hit[2]} height={hit[3]} rx={6} />
      {children}
    </g>
  )
}

function GaugeSym({ x, y, tag, labelAt = 'above' }: { x: number; y: number; tag: string; labelAt?: 'above' | 'below' | 'left' }) {
  const lx = labelAt === 'left' ? x - 20 : x
  const ly = labelAt === 'above' ? y - 20 : labelAt === 'below' ? y + 30 : y + 5
  return (
    <g className="sc-sensor">
      <circle cx={x} cy={y} r={12} />
      <line x1={x - 7} y1={y + 7} x2={x + 6} y2={y - 6} />
      <path d={`M${x + 7.5},${y - 7.5} l-6,1.2 l4.8,4.8 Z`} className="sc-fill" />
      <text x={lx} y={ly} textAnchor={labelAt === 'left' ? 'end' : 'middle'} className="sc-tag">{tag}</text>
    </g>
  )
}

function Tank({ x, y }: { x: number; y: number }) {
  return <path className="sc-line" d={`M${x - 16},${y - 8} V${y + 8} H${x + 16} V${y - 8}`} />
}

export function Schematic({ onPick, active, flowing }: Props) {
  return (
    <div className={`schematic${flowing ? ' is-flowing' : ''}`}>
      <svg viewBox="0 0 680 430" className="sc-primary" role="group" aria-label="Working circuit: main pump, switching valve, accumulator and load">
        <text x={8} y={22} className="sc-title">Working circuit</text>

        {/* pressure path, pump → valve → load */}
        <path className="sc-line sc-pressure" d="M150,276 V110 H330 V140" />
        <path className="sc-line sc-pressure" d="M330,180 V240 H660 V392" />
        <path className="sc-flow" d="M150,276 V110 H330 V140" />
        <path className="sc-flow" d="M330,180 V240 H660 V392" />
        <path className="sc-line" d="M150,324 V392" />
        <path className="sc-line" d="M490,240 V276" />
        <circle cx={210} cy={110} r={3.2} className="sc-node" />
        <circle cx={420} cy={240} r={3.2} className="sc-node" />
        <circle cx={490} cy={240} r={3.2} className="sc-node" />
        <Tank x={150} y={400} />
        <Tank x={660} y={400} />

        {/* motor + coupling */}
        <circle cx={70} cy={300} r={24} className="sc-line" />
        <text x={70} y={306} textAnchor="middle" className="sc-glyph">M</text>
        <path className="sc-line" d="M94,296.5 H126 M94,303.5 H126" />
        <path className="sc-pilot" d="M70,276 V250" />
        <GaugeSym x={70} y={236} tag="EPS1" labelAt="left" />

        {/* sensors on the pressure line */}
        <path className="sc-line" d="M210,110 V76" />
        <GaugeSym x={210} y={62} tag="PS1" />
        <g className="sc-sensor">
          <circle cx={270} cy={110} r={12} className="sc-flowmeter" />
          <path d="M262,110 H277" />
          <path d="M279,110 l-6,-3.6 v7.2 Z" className="sc-fill" />
          <text x={270} y={88} textAnchor="middle" className="sc-tag">FS1</text>
        </g>
        <path className="sc-line" d="M420,240 V274" />
        <GaugeSym x={420} y={288} tag="PS2" labelAt="below" />

        {/* main pump: fixed displacement, one direction */}
        <Part id="leak" label="Main pump" active={active} onPick={onPick} hit={[122, 268, 168, 66]}>
          <circle cx={150} cy={300} r={24} className="sc-line sc-body" />
          <path d="M150,276 l-8,13 h16 Z" className="sc-fill" />
          <text x={186} y={296} className="sc-label">Main pump</text>
          <text x={186} y={314} className="sc-sub">internal leakage</text>
        </Part>

        {/* switching valve: 2 envelopes, spring return, proportional solenoid */}
        <Part id="valve" label="Switching valve" active={active} onPick={onPick} hit={[284, 132, 254, 56]}>
          <rect x={310} y={140} width={40} height={40} className="sc-line sc-body" />
          <rect x={350} y={140} width={40} height={40} className="sc-line sc-body" />
          <path className="sc-line" d="M330,146 V172" />
          <path d="M330,176 l-4,-8 h8 Z" className="sc-fill" />
          <path className="sc-line" d="M370,140 V150 M364,150 H376 M370,180 V170 M364,170 H376" />
          <path className="sc-line" d="M310,160 H306 L302,152 L298,168 L294,152 L290,168 L288,160" />
          <rect x={390} y={150} width={14} height={20} className="sc-line sc-body" />
          <path className="sc-line" d="M386,176 L408,144" />
          <text x={416} y={158} className="sc-label">Switching valve</text>
          <text x={416} y={176} className="sc-sub">opening 100–73 %</text>
        </Part>

        {/* gas-charged accumulator */}
        <Part id="accumulator" label="Accumulator" active={active} onPick={onPick} hit={[466, 270, 160, 90]}>
          <rect x={475} y={278} width={30} height={72} rx={15} className="sc-line sc-body" />
          <path className="sc-line" d="M475,302 H505" />
          <path d="M490,284 l-6,10 h12 Z" className="sc-fill" />
          <text x={514} y={310} className="sc-label">Accumulator</text>
          <text x={514} y={328} className="sc-sub">pre-charge 130–90</text>
        </Part>

        {/* load orifice */}
        <path className="sc-line" d="M648,302 Q660,312 648,322 M672,302 Q660,312 672,322" />
        <text x={652} y={366} textAnchor="end" className="sc-sub">load</text>
      </svg>

      <svg viewBox="0 0 300 430" className="sc-secondary" role="group" aria-label="Cooling and filtration circuit: pump, filter and cooler">
        <text x={8} y={22} className="sc-title">Cooling circuit</text>
        <path className="sc-line" d="M70,280 V110 H128 M172,110 H208 M252,110 H270 V392" />
        <path className="sc-flow sc-flow-slow" d="M70,280 V110 H128 M172,110 H208 M252,110 H270 V392" />
        <path className="sc-line" d="M70,320 V392" />
        <Tank x={70} y={400} />
        <Tank x={270} y={400} />
        <circle cx={70} cy={300} r={20} className="sc-line" />
        <path d="M70,280 l-7,11 h14 Z" className="sc-fill" />
        <text x={98} y={304} className="sc-sub">cooling pump</text>
        {/* filter */}
        <path className="sc-line" d="M150,88 L172,110 L150,132 L128,110 Z" />
        <path className="sc-pilot" d="M150,92 V128" />
        <text x={150} y={76} textAnchor="middle" className="sc-sub">filter</text>
        {/* cooler: diamond, coolant line with outward arrowheads */}
        <Part id="cooler" label="Cooler" active={active} onPick={onPick} hit={[150, 72, 120, 136]}>
          <path className="sc-line sc-body" d="M230,88 L252,110 L230,132 L208,110 Z" />
          <path className="sc-line" d="M230,80 V140" />
          <path d="M230,74 l-4.5,8 h9 Z M230,146 l-4.5,-8 h9 Z" className="sc-fill" />
          <text x={258} y={172} textAnchor="end" className="sc-label">Cooler</text>
          <text x={258} y={190} textAnchor="end" className="sc-sub">100 / 20 / 3 %</text>
        </Part>
      </svg>
    </div>
  )
}
