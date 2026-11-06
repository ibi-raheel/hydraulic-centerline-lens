"""Calibrated golden-run centerline.

Two context-aware references, both scored by robust z = |x - centre| / max(1.4826*MAD, floor):
  A. per-context: one envelope per cooler level, fit on that level's healthy stable cycles.
  B. pooled + temperature detrend: one envelope on all healthy stable cycles after removing,
     bin by bin, a least-squares linear trend in cycle-mean oil temperature TS1.
A cycle alarms at (k, f) when, on any tag, more than a fraction f of bins have z > k.
"""
import numpy as np

from .envelope import MAD_SCALE


def _floor(g):
    return 0.01 * (np.percentile(g, 98) - np.percentile(g, 2)) + 1e-3


def fit_robust(g, floor):
    med = np.median(g, axis=0)
    mad = np.maximum(MAD_SCALE * np.median(np.abs(g - med), axis=0), floor)
    return med, mad


def fit_detrend(g, temp):
    """Per-bin x = a + b*T on the reference cycles. Returns (a, b, med_resid, mad_resid)."""
    T = np.column_stack([np.ones(len(temp)), temp])
    coef, *_ = np.linalg.lstsq(T, g, rcond=None)
    resid = g - T @ coef
    med, mad = fit_robust(resid, _floor(g))
    return coef[0], coef[1], med, mad


def z_detrend(x, temp, model):
    a, b, med, mad = model
    return np.abs(x - (a + np.outer(temp, b)) - med) / mad


def exceed_frac(z, ks):
    """z: (n, bins). Returns (n, len(ks)) fraction of bins with z > k."""
    return np.stack([(z > k).mean(axis=1) for k in ks], axis=1)


def alarm_from_frac(fr, fs):
    """fr: (n_tags, n, n_k) -> alarm (n, n_k, n_f)."""
    worst = fr.max(axis=0)
    return worst[:, :, None] > np.asarray(fs)[None, None, :]


def score_contexts(sig, ctx, temp, healthy, ks, mode):
    """Exceedance fractions for every cycle, plus leave-one-out fractions for the healthy reference cycles.
    sig: {tag: (n, bins)}; ctx: (n,) context label; healthy: bool (n,).
    Returns fr (n_tags, n, n_k) where healthy cycles carry their leave-one-out score."""
    tags = list(sig)
    n = len(ctx)
    fr = np.zeros((len(tags), n, len(ks)))
    for ti, t in enumerate(tags):
        x = sig[t]
        if mode == "per_context":
            for c in np.unique(ctx):
                ref = np.where(healthy & (ctx == c))[0]
                fl = _floor(x[ref])
                med, mad = fit_robust(x[ref], fl)
                m = ctx == c
                fr[ti, m] = exceed_frac(np.abs(x[m] - med) / mad, ks)
                for j in ref:
                    rest = ref[ref != j]
                    med, mad = fit_robust(x[rest], fl)
                    fr[ti, j] = exceed_frac((np.abs(x[j] - med) / mad)[None], ks)[0]
        elif mode == "pooled_detrend":
            ref = np.where(healthy)[0]
            model = fit_detrend(x[ref], temp[ref])
            fr[ti] = exceed_frac(z_detrend(x, temp, model), ks)
            for j in ref:
                rest = ref[ref != j]
                model = fit_detrend(x[rest], temp[rest])
                fr[ti, j] = exceed_frac(z_detrend(x[j][None], temp[j:j + 1], model), ks)[0]
        elif mode == "single_context":   # the original build: one envelope from one context, applied everywhere
            ref = np.where(healthy & (ctx == ctx.max()))[0]
            fl = _floor(x[ref])
            med, mad = fit_robust(x[ref], fl)
            fr[ti] = exceed_frac(np.abs(x - med) / mad, ks)
            for j in ref:
                rest = ref[ref != j]
                med, mad = fit_robust(x[rest], fl)
                fr[ti, j] = exceed_frac((np.abs(x[j] - med) / mad)[None], ks)[0]
        else:
            raise ValueError(mode)
    return fr


def sample_size_study(sig, temp, healthy_idx, k, f, ns, n_draw=200, seed=0):
    """Fit the pooled-detrend envelope on n random healthy cycles, test on the held-out rest.
    Returns {n: (mean FA rate, p2.5, p97.5, total alarms, total tests)}."""
    rng = np.random.default_rng(seed)
    out = {}
    for n in ns:
        rates, alarms, tests = [], 0, 0
        for _ in range(n_draw):
            perm = rng.permutation(healthy_idx)
            fit, test = perm[:n], perm[n:]
            worst = np.zeros(len(test))
            for x in sig.values():
                model = fit_detrend(x[fit], temp[fit])
                z = z_detrend(x[test], temp[test], model)
                worst = np.maximum(worst, (z > k).mean(axis=1))
            a = worst > f
            rates.append(a.mean()); alarms += int(a.sum()); tests += len(test)
        out[n] = (float(np.mean(rates)), float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5)), alarms, tests)
    return out


def sample_size_per_context(sig, ctx, healthy, k, f, ns, n_draw=300, seed=0):
    """Per-context envelope fit on n random healthy cycles of that context, tested on the held-out
    healthy cycles of the same context; pooled over contexts. Returns {n: (mean, p2.5, p97.5, alarms, tests)}."""
    rng = np.random.default_rng(seed)
    out = {}
    ctxs = np.unique(ctx[healthy])
    for n in ns:
        rates, alarms, tests = [], 0, 0
        for _ in range(n_draw):
            a_d, t_d = 0, 0
            for c in ctxs:
                ref = rng.permutation(np.where(healthy & (ctx == c))[0])
                fit, test = ref[:n], ref[n:]
                worst = np.zeros(len(test))
                for x in sig.values():
                    med, mad = fit_robust(x[fit], _floor(x[ref]))
                    worst = np.maximum(worst, ((np.abs(x[test] - med) / mad) > k).mean(axis=1))
                a_d += int((worst > f).sum()); t_d += len(test)
            rates.append(a_d / t_d); alarms += a_d; tests += t_d
        out[n] = (float(np.mean(rates)), float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5)), alarms, tests)
    return out
