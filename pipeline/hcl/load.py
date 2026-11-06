"""Load the UCI hydraulic rig matrices (rows = cycles, columns = samples)."""
from pathlib import Path
import numpy as np
import pandas as pd

RATES = {**{f"PS{i}": 100 for i in range(1, 7)}, "EPS1": 100, "FS1": 10, "FS2": 10,
         **{f"TS{i}": 1 for i in range(1, 5)}, "VS1": 1, "CE": 1, "CP": 1, "SE": 1}
UNITS = {**{f"PS{i}": "bar" for i in range(1, 7)}, "EPS1": "W", "FS1": "l/min", "FS2": "l/min",
         **{f"TS{i}": "degC" for i in range(1, 5)}, "VS1": "mm/s", "CE": "%", "CP": "kW", "SE": "%"}
PROFILE_COLS = ["cooler", "valve", "leak", "accumulator", "stable_flag"]


def load_channel(raw: Path, tag: str, cache: Path | None = None) -> np.ndarray:
    if cache is not None:
        c = cache / f"{tag}.npy"
        if c.exists():
            return np.load(c)
    arr = pd.read_csv(raw / f"{tag}.txt", sep="\t", header=None, dtype=np.float32).to_numpy()
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.save(cache / f"{tag}.npy", arr)
    return arr


def load_profile(raw: Path) -> pd.DataFrame:
    return pd.read_csv(raw / "profile.txt", sep="\t", header=None, names=PROFILE_COLS)


def to_10hz(x: np.ndarray, rate: int) -> np.ndarray:
    """Common 10 Hz grid: 100 Hz -> mean of 10-sample blocks (boxcar anti-alias),
    10 Hz -> as is, 1 Hz -> zero-order hold (repeat each sample 10 times)."""
    n = x.shape[0]
    if rate == 100:
        return x.reshape(n, -1, 10).mean(axis=2)
    if rate == 10:
        return x
    if rate == 1:
        return np.repeat(x, 10, axis=1)
    raise ValueError(rate)
