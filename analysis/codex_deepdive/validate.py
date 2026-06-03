"""Stage 4: stratified validation sampling, agreement scoring, support gating."""
from __future__ import annotations
import random
from collections import defaultdict


def _stratum_key(ep):
    f = ep["findings"][0] if ep["findings"] else {"verdict": "none", "impact_tier": "none"}
    return (ep["mode"], f.get("verdict", "none"), f.get("impact_tier", "none"))


def stratified_sample(episodes, seed, per_stratum):
    rng = random.Random(seed)
    strata = defaultdict(list)
    for ep in episodes:
        strata[_stratum_key(ep)].append(ep)
    out = []
    for key in sorted(strata):
        group = sorted(strata[key], key=lambda e: e["episode_id"])
        rng.shuffle(group)
        out.extend(group[:per_stratum])
    return out


def agreement(pairs):
    """pairs: list of (human_dict, machine_dict). Returns per-field agreement fraction."""
    fields = defaultdict(lambda: [0, 0])  # field -> [agree, total]
    for human, machine in pairs:
        for k in human:
            fields[k][1] += 1
            if human.get(k) == machine.get(k):
                fields[k][0] += 1
    return {k: (a / t if t else 0.0) for k, (a, t) in fields.items()}


def supported(n_validated, threshold=5):
    return n_validated >= threshold
