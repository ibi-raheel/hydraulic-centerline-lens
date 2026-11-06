"""Per-component condition classifiers on per-cycle features."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict

STATS = ("mean", "std", "min", "max", "p10", "p90", "slope")


def channel_features(x):
    t = np.linspace(0, 1, x.shape[1])
    tc = t - t.mean()
    slope = (x - x.mean(axis=1, keepdims=True)) @ tc / (tc @ tc)
    return np.column_stack([x.mean(1), x.std(1), x.min(1), x.max(1),
                            np.percentile(x, 10, axis=1), np.percentile(x, 90, axis=1), slope])


def build_features(ch, extra=None):
    cols, names = [], []
    for tag, x in ch.items():
        cols.append(channel_features(x.astype(np.float64)))
        names += [f"{tag}.{s}" for s in STATS]
    X = np.hstack(cols)
    if extra:
        for k, v in extra.items():
            X = np.column_stack([X, v]); names.append(k)
    return X, names


def blocked_groups(n, block=50):
    return np.arange(n) // block


def evaluate(X, y, seed=0, block=50, n_splits=5):
    clf = RandomForestClassifier(n_estimators=200, n_jobs=2, random_state=seed, min_samples_leaf=2)
    pred_blk = cross_val_predict(clf, X, y, groups=blocked_groups(len(y), block), cv=GroupKFold(n_splits))
    pred_rnd = cross_val_predict(clf, X, y, cv=KFold(n_splits, shuffle=True, random_state=seed))
    vals, counts = np.unique(y, return_counts=True)
    clf.fit(X, y)
    return {"acc_blocked": float((pred_blk == y).mean()), "acc_random": float((pred_rnd == y).mean()),
            "acc_majority": float(counts.max() / len(y)), "pred_blocked": pred_blk,
            "classes": vals.tolist(), "importance": clf.feature_importances_}


def confusion(y, pred, classes):
    idx = {c: i for i, c in enumerate(classes)}
    m = np.zeros((len(classes), len(classes)), int)
    for a, b in zip(y, pred):
        m[idx[a], idx[b]] += 1
    return m
