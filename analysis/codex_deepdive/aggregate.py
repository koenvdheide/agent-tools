"""Stage 3: aggregate classified episodes into publishable, anonymized metrics."""
from __future__ import annotations
import json, sys
from collections import Counter

ADOPTED = {"adopted", "partial"}


def _has_valid_adopted(ep):
    return any(f["validity"] == "valid" and f["verdict"] in ADOPTED
              for f in ep["findings"])


def aggregate(episodes):
    chains = {}
    single = []
    for ep in episodes:
        if ep.get("chain_id"):
            chains.setdefault(ep["chain_id"], []).append(ep)
        else:
            single.append(ep)

    n = len(episodes)
    ep_hits = sum(1 for ep in episodes if _has_valid_adopted(ep))

    all_findings = [f for ep in episodes for f in ep["findings"]]
    adopted = [f for f in all_findings if f["verdict"] in ADOPTED]

    cat = Counter(f["category"] for f in adopted)
    heading = Counter(f["heading"] for f in adopted)
    tier = Counter(f["impact_tier"] for f in all_findings)

    slugs = {ep["project_slug"] for ep in episodes}
    times = sorted(ep["ts"] for ep in episodes if ep.get("ts"))

    chain_hits = sum(1 for eps in chains.values()
                     if any(_has_valid_adopted(e) for e in eps))

    return {
        "corpus": {
            "n_episodes": n,
            "n_projects": len(slugs),
            "date_range": [times[0], times[-1]] if times else [None, None],
        },
        "episode": {
            "pct_with_valid_adopted": round(100 * ep_hits / n, 1) if n else 0.0,
            "pct_single_shot_with_valid_adopted": round(100 * sum(_has_valid_adopted(e) for e in single) / len(single), 1) if single else 0.0,
            "n_single_shot": len(single),
        },
        "chain": {
            "n_chains": len(chains),
            "pct_chains_with_valid_adopted": round(100 * chain_hits / len(chains), 1) if chains else 0.0,
            "rounds_per_chain": sorted(len(v) for v in chains.values()),
        },
        "findings": {
            "n_findings": len(all_findings),
            "n_adopted": len(adopted),
            "n_invalid": sum(1 for f in all_findings if f["validity"] == "invalid"),
            "n_debatable": sum(1 for f in all_findings if f["validity"] == "debatable"),
            "breakage_vs_simplification": dict(heading),
            "category_among_adopted": dict(cat),
            "impact_tier_distribution": dict(tier),
        },
    }


def story_shortlist(episodes, k=8):
    rank = {"scrapped": 3, "plan/direction-change": 2, "local-edit": 1, "not-observed": 0}
    scored = []
    for ep in episodes:
        best = max((rank[f["impact_tier"]] for f in ep["findings"]), default=0)
        if best >= 2:
            scored.append((best, ep["episode_id"], ep["project_slug"]))
    scored.sort(reverse=True)
    return scored[:k]


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "analysis/codex_deepdive/out/episodes.jsonl"
    eps = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    agg = aggregate(eps)
    print(json.dumps(agg, indent=2))
    print("STORY SHORTLIST:", json.dumps(story_shortlist(eps), indent=2))
