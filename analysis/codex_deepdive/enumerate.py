"""Broad, tool_use_id-deduped enumeration of EVERY codex invocation across all
transcripts. Deliberately wider than extract.py: no Mode: filter, catches
`codex exec`, `codex review`, piped-file prompts, heredoc prompts. Produces a
scoped per-project JSON so subagents can deep-dive without loading raw transcripts.
"""
from __future__ import annotations
import json, re, os, glob, sys

CODEX_TOKEN = re.compile(r"\bcodex\b")
GEMINI_TOKEN = re.compile(r"\bgemini\b")
OUT_RE = re.compile(r"-o[= ]\s*\"?([^\s\"|]+)")
CAT_PIPE_RE = re.compile(r"(?:cat|Get-Content|type)\s+\"?([^\s\"|]+)\"?\s*\|\s*(?:.*\b)?codex", re.I)
MODE_RE = re.compile(r"Mode:\s*([a-zA-Z][a-zA-Z-]*)")
REVIEW_SUBCMD_RE = re.compile(r"codex\s+(?:exec\s+)?review\b")
REVIEW_SIGNAL_RE = re.compile(r"##\s*Breakage|##\s*Simplification|red[- ]?team|adversarial|regress", re.I)


def load_events(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ev["_line"] = i  # 1-based JSONL line number, for transcript:line citations
            out.append(ev)
    return out


def tool_uses(ev):
    c = (ev.get("message") or {}).get("content")
    if isinstance(c, list):
        for it in c:
            if isinstance(it, dict) and it.get("type") == "tool_use":
                yield it


def text_of(ev):
    c = (ev.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
    return ""


def basename(p):
    return os.path.basename(p.replace("\\", "/")) if p else p


def find_output(events, slug):
    """Broad: any later Read of `slug` basename, return its tool_result text."""
    if not slug:
        return None
    for ev in events:
        for tu in tool_uses(ev):
            if tu.get("name") == "Read" and basename((tu.get("input") or {}).get("file_path", "")) == basename(slug):
                rid = tu.get("id")
                for e2 in events:
                    if e2.get("type") != "user":
                        continue
                    cc = (e2.get("message") or {}).get("content")
                    if isinstance(cc, list):
                        for it in cc:
                            if isinstance(it, dict) and it.get("type") == "tool_result" and it.get("tool_use_id") == rid:
                                t = it.get("content")
                                if isinstance(t, str):
                                    return t
                                if isinstance(t, list):
                                    return "".join(p.get("text", "") for p in t if isinstance(p, dict))
    return None


def project_of(path):
    p = path.replace("\\", "/").split("/projects/")
    return p[1].split("/")[0] if len(p) > 1 else "?"


def enumerate_file(path):
    events = load_events(path)
    seen = set()
    out = []
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        narr = text_of(ev)
        for tu in tool_uses(ev):
            if tu.get("name") != "Bash":
                continue
            cmd = (tu.get("input") or {}).get("command", "")
            if not CODEX_TOKEN.search(cmd):
                continue
            tuid = tu.get("id")
            if tuid in seen:
                continue  # dedup transcript event-duplication by tool_use_id
            seen.add(tuid)
            outm = OUT_RE.search(cmd)
            catm = CAT_PIPE_RE.search(cmd)
            modem = MODE_RE.search(cmd)
            slug = basename(outm.group(1)) if outm else None
            output = find_output(events, slug)
            out.append({
                "tool_use_id": tuid,
                "line": ev.get("_line"),
                "session": ev.get("sessionId", ""),
                "ts": ev.get("timestamp", ""),
                "is_sidechain": bool(ev.get("isSidechain")),
                "cmd_excerpt": cmd[:600],
                "out_slug": slug,
                "piped_artifact": catm.group(1) if catm else None,
                "heredoc_mode": modem.group(1).lower() if modem else None,
                "is_review_subcmd": bool(REVIEW_SUBCMD_RE.search(cmd)),
                "narration_excerpt": narr[:400],
                "has_output": output is not None,
                "output_excerpt": (output[:6000] if output else None),
                "review_signal": bool((output and REVIEW_SIGNAL_RE.search(output)) or REVIEW_SIGNAL_RE.search(narr)),
            })
    return out


def main(root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    by_project = {}
    gemini_ids = set()
    for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        proj = project_of(path)
        invs = enumerate_file(path)
        if invs:
            by_project.setdefault(proj, []).extend(invs)
        # quick gemini tally for context
        for ev in load_events(path):
            if ev.get("type") != "assistant":
                continue
            for tu in tool_uses(ev):
                if tu.get("name") == "Bash" and GEMINI_TOKEN.search((tu.get("input") or {}).get("command", "")):
                    gemini_ids.add(tu.get("id"))

    total = 0
    summary = {}
    for proj, invs in sorted(by_project.items(), key=lambda x: -len(x[1])):
        # global dedup safety by tool_use_id
        uniq = {i["tool_use_id"]: i for i in invs}
        invs = list(uniq.values())
        by_project[proj] = invs
        total += len(invs)
        heredoc_review = sum(1 for i in invs if i["heredoc_mode"] in
                             {"red-team", "diff-review", "plan-review", "attack-surface", "exhausted-hypotheses", "rollout-rollback"})
        piped = sum(1 for i in invs if i["piped_artifact"])
        sig = sum(1 for i in invs if i["review_signal"])
        summary[proj] = {"codex_calls": len(invs), "heredoc_review_mode": heredoc_review,
                         "piped_file_prompt": piped, "review_signal": sig}
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", proj)
        with open(os.path.join(out_dir, f"{safe}.json"), "w", encoding="utf-8") as f:
            json.dump(invs, f, indent=2)

    with open(os.path.join(out_dir, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"total_codex_calls_deduped": total, "projects": summary,
                   "gemini_calls_deduped": len(gemini_ids)}, f, indent=2)
    print(json.dumps({"total_codex_calls_deduped": total, "n_projects": len(summary),
                      "gemini_calls_deduped": len(gemini_ids), "by_project": summary}, indent=2))


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.claude/projects")
    out = sys.argv[2] if len(sys.argv) > 2 else "analysis/codex_deepdive/enum"
    main(root, out)
