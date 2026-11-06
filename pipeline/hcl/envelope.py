"""Golden-run centerline: robust per-bin envelope median +/- k * 1.4826 * MAD."""
import numpy as np

MAD_SCALE = 1.4826  # makes MAD a consistent estimator of sigma for normal data


def fit_envelope(golden, k=4.0, floor=None):
    """golden: (n_cycles, n_bins). Returns centre, lo, hi arrays (n_bins,)."""
    med = np.median(golden, axis=0)
    mad = MAD_SCALE * np.median(np.abs(golden - med), axis=0)
    if floor is not None:
        mad = np.maximum(mad, floor)
    return med, med - k * mad, med + k * mad


def excursion(x, lo, hi):
    """Per cycle: fraction of bins outside the band, and out-of-band area normalised by band width."""
    x = np.atleast_2d(x)
    below = np.clip(lo - x, 0, None)
    above = np.clip(x - hi, 0, None)
    width = np.maximum(np.median(hi - lo), 1e-9)
    frac = ((below > 0) | (above > 0)).mean(axis=1)
    area = (below + above).mean(axis=1) / width
    return frac, area
