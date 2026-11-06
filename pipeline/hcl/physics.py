"""First-principles transient features.

Accumulator: after each PS1 set-point step the line pressure relaxes like a first-order system
    p(t) = p_inf + (p_0 - p_inf) exp(-t / tau),   tau = R_h * C
with C the hydraulic capacitance. For a gas-charged accumulator (polytropic p V^n = p0 V0^n),
    C_acc = dV/dp = V0 p0^(1/n) / (n p^(1 + 1/n)),
so at a fixed operating pressure tau scales with p0^(1/n), n between 1 (isothermal) and 1.4 (adiabatic).

Valve: switching lag = time shift of the PS2 pressure edge against the golden-run median edge,
found by least-squares template alignment (the minimum-SSE form of cross-correlation) with
parabolic interpolation of the minimum for sub-sample resolution.
"""
import numpy as np
from scipy.optimize import curve_fit

RATE = 100
STEP_WINDOWS = [(900, 1000), (1880, 1980), (2880, 2980), (3880, 3980), (4880, 4980)]  # PS1 samples, t ~ 9.4 .. 49.3 s
FIT_LEN = 300  # 3 s after each edge


def first_order(t, p_inf, p0, tau):
    return p_inf + (p0 - p_inf) * np.exp(-t / np.maximum(tau, 1e-4))


def fit_step(seg, rate=RATE):
    """Fit a first-order response starting at seg[0]. Returns (p_inf, p0, tau_s, rmse)."""
    t = np.arange(len(seg)) / rate
    try:
        p, _ = curve_fit(first_order, t, seg, p0=[seg[-20:].mean(), seg[0], 0.2],
                         bounds=([-np.inf, -np.inf, 1e-3], [np.inf, np.inf, 5.0]), maxfev=4000)
    except RuntimeError:
        return np.nan, np.nan, np.nan, np.nan
    rmse = float(np.sqrt(np.mean((first_order(t, *p) - seg) ** 2)))
    return float(p[0]), float(p[1]), float(p[2]), rmse


def step_edges(x):
    """Index of steepest change in each nominal window (one PS1 row)."""
    return [a + int(np.argmax(np.abs(np.diff(x[a:b])))) for a, b in STEP_WINDOWS]


def step_taus(ps1):
    """(n, 5) time constants and (n, 5) fit RMSE in bar."""
    n = ps1.shape[0]
    taus = np.full((n, len(STEP_WINDOWS)), np.nan)
    rmse = np.full_like(taus, np.nan)
    for i in range(n):
        x = ps1[i].astype(np.float64)
        for s, e in enumerate(step_edges(x)):
            _, _, taus[i, s], rmse[i, s] = fit_step(x[e:e + FIT_LEN])
    return taus, rmse


def align_lag(x, template, centre, pre=50, post=100, max_lag=(-100, 250)):
    """Shift (samples, sub-sample) that best aligns x to template around `centre`.
    template is the reference trace (same length as x). Positive = x lags the template."""
    tpl = template[centre - pre:centre + post]
    lags = np.arange(max_lag[0], max_lag[1] + 1)
    sse = np.array([np.sum((x[centre - pre + L:centre + post + L] - tpl) ** 2) for L in lags])
    i = int(np.argmin(sse))
    if 0 < i < len(sse) - 1:
        a, b, c = sse[i - 1], sse[i], sse[i + 1]
        den = a - 2 * b + c
        frac = 0.5 * (a - c) / den if den > 0 else 0.0
    else:
        frac = 0.0
    return float(lags[i] + frac)


def edge_lags(x2d, template, centre, rate=RATE):
    """Lag in ms for each row."""
    x2d = x2d.astype(np.float64)
    return np.array([align_lag(row, template, centre) for row in x2d]) * 1000.0 / rate


def loglog_slope(p0, log_tau):
    A = np.column_stack([np.ones(len(p0)), np.log(p0)])
    coef, *_ = np.linalg.lstsq(A, log_tau, rcond=None)
    return float(coef[1])
