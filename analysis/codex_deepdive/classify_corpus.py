"""Deterministic review + convergence classifier over enum/ records.
Reproduces the subagent ground truth as a reusable algorithm (the rebuilt detection core).
Detection: is-invocation -> review/non-review (4-rule + output-shape) -> slug-stem convergence.
"""
import json, re, glob, os, sys
from collections import Counter, defaultdict

REVIEW_MODES = {"red-team", "diff-review", "plan-review", "attack-surface",
                "exhausted-hypotheses", "rollout-rollback"}
EXEC_RE = re.compile(r"codex\s+(exec|review)", re.I)
BREAKAGE_RE = re.compile(r"##\s*Breakage|##\s*Simplification|\*\*Breakage\*\*|\*\*Simplification", re.I)
REVIEW_OUT_RE = re.compile(r"Verdict:|VERDICT|MUST-?FIX|NOT-?CONVERGED|\bCONVERGED\b|Blocker|BLOCKERS|"
                           r"I disagree|regression|Redesign|##\s*Cuts|\bFindings\b|FIX-FIRST|NEEDS (MAJOR|MINOR)", re.I)
DIFF_RE = re.compile(r"diff.?review|per-claim|blast.?radius|\bt\d-review\b|PROSE|ACCURACY", re.I)
PLAN_RE = re.compile(r"plan.?review|missing step|sequencing|rollback|spec.?review|Blocking Issue", re.I)
REVIEW_NARR_RE = re.compile(r"red.?team|review|critique|adversarial|diff.review|find (problems|issues|bugs)|audit", re.I)


def is_invocation(r):
    cmd = r.get("cmd_excerpt") or ""
    if EXEC_RE.search(cmd):
        return True
    if r.get("piped_artifact"):
        return True
    if (r.get("out_slug") or "").startswith("codex-") and r.get("has_output"):
        return True
    if r.get("is_review_subcmd"):
        return True
    return False


def infer_mode(out, narr, slug):
    blob = (out or "") + " " + (slug or "") + " " + (narr or "")
    if BREAKAGE_RE.search(out or ""):
        return "red-team"
    if PLAN_RE.search(blob):
        return "plan-review"
    if DIFF_RE.search(blob):
        return "diff-review"
    return "review-unknown-mode"


def classify(r):
    hm = r.get("heredoc_mode")
    if hm in REVIEW_MODES:
        return ("review", hm)
    if r.get("is_review_subcmd"):
        return ("review", "review-subcmd")
    out = r.get("output_excerpt") or ""
    narr = r.get("narration_excerpt") or ""
    if BREAKAGE_RE.search(out):
        return ("review", "red-team")
    if (r.get("piped_artifact") or out) and (REVIEW_OUT_RE.search(out) or (REVIEW_NARR_RE.search(narr) and r.get("has_output"))):
        return ("review", infer_mode(out, narr, r.get("out_slug")))
    return ("non-review", "other")


def slug_stem(slug):
    if not slug:
        return None
    s = re.sub(r"\.txt$", "", slug)
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"[-_]?(r\d+|v\d+|round-?\d+|\d+)$", "", s)
    return s.rstrip("-_") or None


def main(enum_dir):
    reviews = []
    modes = Counter()
    nonrev = 0
    invocations = 0
    for p in glob.glob(os.path.join(enum_dir, "*.json")):
        if p.endswith("_summary.json"):
            continue
        proj = os.path.basename(p)[:-5]
        recs = json.load(open(p, encoding="utf-8"))
        for r in recs:
            if not is_invocation(r):
                continue
            invocations += 1
            cls, mode = classify(r)
            if cls == "review":
                modes[mode] += 1
                reviews.append({"project": proj, "session": r.get("session"), "ts": r.get("ts"),
                                "out_slug": r.get("out_slug"), "piped_artifact": r.get("piped_artifact"),
                                "output_excerpt": r.get("output_excerpt"), "mode": mode})
            else:
                nonrev += 1

    clusters = defaultdict(list)
    for rv in reviews:
        stem = slug_stem(rv["out_slug"]) or (rv["piped_artifact"] or "")
        clusters[(rv["project"], rv["session"], stem)].append(rv)
    chains = rounds_in = maxc = 0
    chain_examples = []
    for (proj, sess, stem), v in clusters.items():
        if not stem:
            continue
        # exclude identical-output retries within the cluster
        seen_out = set()
        uniq = []
        for rv in sorted(v, key=lambda x: x["ts"] or ""):
            key = (rv["output_excerpt"] or "")[:200]
            if key and key in seen_out:
                continue
            seen_out.add(key)
            uniq.append(rv)
        if len(uniq) >= 2:
            chains += 1
            rounds_in += len(uniq)
            maxc = max(maxc, len(uniq))
            chain_examples.append((len(uniq), proj, stem))

    chain_examples.sort(reverse=True)
    print(json.dumps({
        "invocations_detected": invocations,
        "reviews_total": len(reviews),
        "reviews_by_mode": dict(modes.most_common()),
        "non_reviews": nonrev,
        "convergence_chains": chains,
        "rounds_in_chains": rounds_in,
        "max_chain_rounds": maxc,
        "top_chains": chain_examples[:12],
    }, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "analysis/codex_deepdive/enum")
