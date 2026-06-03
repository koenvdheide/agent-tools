"""Stage 1 (rebuilt): detect ALL Codex reviews + convergence across transcripts.

Supersedes the original Mode:-in-command / (session,cmd)-identity logic, which
undercounted reviews ~2.7x (it dropped every piped-file review, where the prompt
lives in the cat'd file, not the command) and reported 0 convergence (it keyed on
a `Previously identified findings:` marker that never appears in real commands).

This version reuses the broad, tool_use_id-deduped parser in enumerate.py, then:
- is_invocation(): separate real `codex exec`/`review` calls from cat/rm/git of codex files;
- classify(): review vs non-review by heredoc Mode:, the `review` subcommand, or output
  shape (## Breakage / Verdict / Findings) + narration — not just Mode:-in-command;
- slug_stem() + _tag_convergence(): reconstruct convergence by `-o` slug lineage.

Validated against an 8-subagent manual ground truth: ~450 reviews, ~60 chains,
independently corroborated by ~60 versioned `-rN/-vN` output-file series on disk.
"""
from __future__ import annotations
import json, re, os, sys, glob
from collections import Counter, defaultdict
from enumerate import enumerate_file, project_of

REVIEW_MODES = {"red-team", "diff-review", "plan-review", "attack-surface",
                "exhausted-hypotheses", "rollout-rollback"}
EXEC_RE = re.compile(r"codex\s+(exec|review)", re.I)
BREAKAGE_RE = re.compile(r"##\s*Breakage|##\s*Simplification|\*\*Breakage\*\*|\*\*Simplification", re.I)
REVIEW_OUT_RE = re.compile(
    r"Verdict:|VERDICT|MUST-?FIX|NOT-?CONVERGED|\bCONVERGED\b|Blocker|BLOCKERS|"
    r"I disagree|regression|Redesign|##\s*Cuts|\bFindings\b|FIX-FIRST|NEEDS (MAJOR|MINOR)", re.I)
DIFF_RE = re.compile(r"diff.?review|per-claim|blast.?radius|\bt\d-review\b|PROSE|ACCURACY", re.I)
PLAN_RE = re.compile(r"plan.?review|missing step|sequencing|rollback|spec.?review|Blocking Issue", re.I)
REVIEW_NARR_RE = re.compile(r"red.?team|review|critique|adversarial|diff.review|find (problems|issues|bugs)|audit", re.I)


def iter_transcripts(root):
    return glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)


def is_invocation(r):
    """Is this enum record an actual codex invocation (vs a cat/rm/git of a codex file)?"""
    cmd = r.get("cmd_excerpt") or ""
    if EXEC_RE.search(cmd):
        return True
    if r.get("piped_artifact"):
        return True
    if (r.get("out_slug") or "").startswith("codex-") and r.get("has_output"):
        return True
    return bool(r.get("is_review_subcmd"))


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
    """Return (kind, mode), kind in {'review','non-review'}."""
    hm = r.get("heredoc_mode")
    if hm in REVIEW_MODES:
        return ("review", hm)
    if r.get("is_review_subcmd"):
        return ("review", "review-subcmd")
    out = r.get("output_excerpt") or ""
    narr = r.get("narration_excerpt") or ""
    if BREAKAGE_RE.search(out):
        return ("review", "red-team")
    if (r.get("piped_artifact") or out) and (
            REVIEW_OUT_RE.search(out) or (REVIEW_NARR_RE.search(narr) and r.get("has_output"))):
        return ("review", infer_mode(out, narr, r.get("out_slug")))
    return ("non-review", "other")


def slug_stem(slug):
    """Normalize an -o slug to its artifact lineage (strip -r2/-v3/round/digit suffixes)."""
    if not slug:
        return None
    s = re.sub(r"\.txt$", "", slug)
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"[-_]?(r\d+|v\d+|round-?\d+|\d+)$", "", s)
    return s.rstrip("-_") or None


def extract_reviews(root):
    """Walk all transcripts under root; return (reviews, audit). Reviews carry an
    assigned convergence chain_id/round_index."""
    reviews = []
    audit = Counter()
    for path in iter_transcripts(root):
        proj = project_of(path)
        for r in enumerate_file(path):
            if not is_invocation(r):
                audit["non-invocation"] += 1
                continue
            kind, mode = classify(r)
            if kind != "review":
                audit["non-review"] += 1
                continue
            audit["review"] += 1
            reviews.append({
                "tool_use_id": r["tool_use_id"], "project": proj,
                "transcript": os.path.basename(path), "line": r.get("line"),
                "session": r["session"],
                "ts": r["ts"], "is_sidechain": r.get("is_sidechain", False), "mode": mode,
                "out_slug": r.get("out_slug"), "piped_artifact": r.get("piped_artifact"),
                "has_output": r.get("has_output", False), "output_excerpt": r.get("output_excerpt"),
                "narration_excerpt": r.get("narration_excerpt"),
                "chain_id": None, "round_index": 0,
            })
    _tag_convergence(reviews)
    return reviews, audit


def _tag_convergence(reviews):
    """Assign chain_id/round_index by (project, session, slug-stem). >=2 distinct-output
    reviews of one lineage = a convergence chain; identical-output repeats are retries."""
    clusters = defaultdict(list)
    for rv in reviews:
        stem = slug_stem(rv["out_slug"]) or (rv["piped_artifact"] or "")
        clusters[(rv["project"], rv["session"], stem)].append(rv)
    for (proj, sess, stem), group in clusters.items():
        if not stem:
            continue
        group.sort(key=lambda x: x["ts"] or "")
        seen, uniq = set(), []
        for rv in group:
            key = (rv["output_excerpt"] or "")[:200]
            if key and key in seen:
                rv["chain_id"] = "retry"
                continue
            seen.add(key)
            uniq.append(rv)
        if len(uniq) >= 2:
            label = f"{(sess or '')[:8]}:{stem}"
            for i, rv in enumerate(uniq):
                rv["chain_id"] = label
                rv["round_index"] = i


def summarize(reviews):
    modes = Counter(rv["mode"] for rv in reviews)
    chains = defaultdict(list)
    for rv in reviews:
        if rv["chain_id"] and rv["chain_id"] != "retry":
            chains[rv["chain_id"]].append(rv)
    rounds = [len(v) for v in chains.values()]
    return {
        "reviews_total": len(reviews),
        "reviews_by_mode": dict(modes.most_common()),
        "projects": len({rv["project"] for rv in reviews}),
        "convergence_chains": len(chains),
        "rounds_in_chains": sum(rounds),
        "max_chain_rounds": max(rounds) if rounds else 0,
    }


def main(root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    reviews, audit = extract_reviews(root)
    by_proj = defaultdict(list)
    for rv in reviews:
        by_proj[rv["project"]].append(rv)
    for proj, rvs in by_proj.items():
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", proj)
        with open(os.path.join(out_dir, f"{safe}.json"), "w", encoding="utf-8") as f:
            json.dump(rvs, f, indent=2)
    summary = summarize(reviews)
    summary["audit"] = dict(audit)
    with open(os.path.join(out_dir, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.claude/projects")
    out = sys.argv[2] if len(sys.argv) > 2 else "analysis/codex_deepdive/bundles/reviews"
    main(root, out)
