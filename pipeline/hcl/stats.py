"""Small, dependency-free uncertainty helpers."""
import math
import numpy as np

Z95 = 1.959963984540054


def wilson(k, n, z=Z95):
    """Wilson score interval for a binomial proportion k/n. Returns (p_hat, lo, hi)."""
    if n == 0:
        return float("nan"), 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def rule_of_three_n(rate):
    """Cycles with zero alarms needed to bound a rate below `rate` at ~95 % (upper bound = 3/n)."""
    return int(math.ceil(3.0 / rate))


def block_bootstrap_acc(correct, block=50, n_boot=2000, seed=0):
    """95 % CI for accuracy, resampling contiguous blocks of cycles with replacement
    (keeps the within-block correlation that a per-cycle bootstrap would ignore)."""
    correct = np.asarray(correct, float)
    nb = int(math.ceil(len(correct) / block))
    sums = np.array([correct[i * block:(i + 1) * block].sum() for i in range(nb)])
    lens = np.array([len(correct[i * block:(i + 1) * block]) for i in range(nb)])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nb, size=(n_boot, nb))
    accs = sums[idx].sum(1) / lens[idx].sum(1)
    return float(correct.mean()), float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))


def bootstrap_median_ci(x, n_boot=5000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    meds = np.median(x[rng.integers(0, len(x), size=(n_boot, len(x)))], axis=1)
    return float(np.median(x)), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))
