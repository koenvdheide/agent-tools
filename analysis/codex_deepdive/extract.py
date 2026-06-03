"""Stage 1: extract Codex review episodes from Claude Code transcripts."""
from __future__ import annotations
import json, re, os, glob
from dataclasses import dataclass, field, asdict

REVIEW_MODES = {"red-team", "diff-review", "plan-review", "attack-surface",
                "exhausted-hypotheses", "rollout-rollback"}
EXCLUDED_MODES = {"brainstorm", "debug", "explain", "spec-extraction",
                  "compare-decide", "test-gaps", "post-mortem"}
CODEX_RE = re.compile(r"codex\s+exec\b")
REVIEW_SUBCMD_RE = re.compile(r"codex\s+exec\s+review\b")
MODE_RE = re.compile(r"Mode:\s*([a-z][a-z-]*)")
SLUG_RE = re.compile(r"-o\s+(\S*codex-[A-Za-z0-9._/\\:-]+\.txt)")
PREV_FINDINGS_RE = re.compile(r"Previously identified findings:", re.I)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


@dataclass
class Episode:
    tool_use_id: str
    transcript: str
    session: str
    ts: str
    mode: str
    slug: str | None
    is_sidechain: bool
    cmd: str
    audit: str = "detected"
    output: str | None = None
    follow_through: list = field(default_factory=list)
    reviewer_qa: bool = False
    chain_id: str | None = None
    round_index: int = 0


def load_events(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def tool_uses(ev):
    msg = ev.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                yield item


def is_human_turn(ev):
    if ev.get("type") != "user":
        return False
    if ev.get("toolUseResult") is not None:
        return False
    content = (ev.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not any(isinstance(i, dict) and i.get("type") == "tool_result" for i in content)
    return False


def parse_mode(cmd):
    if REVIEW_SUBCMD_RE.search(cmd):
        return "review"
    m = MODE_RE.search(cmd)
    return m.group(1) if m else None


def parse_slug(cmd):
    m = SLUG_RE.search(cmd)
    return m.group(1) if m else None


def _basename(p):
    return os.path.basename(p.replace("\\", "/")) if p else p


def _tool_result_text(events, tool_use_id):
    for ev in events:
        if ev.get("type") != "user":
            continue
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result" \
                    and item.get("tool_use_id") == tool_use_id:
                c = item.get("content")
                if isinstance(c, str):
                    return c
                if isinstance(c, list):
                    return "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return None


def _pair_output(events, start_idx, slug):
    """Find a Read of `slug` before the next Codex call; return its text or None."""
    if not slug:
        return None
    target = _basename(slug)
    for ev in events[start_idx + 1:]:
        for tu in tool_uses(ev):
            name = tu.get("name")
            inp = tu.get("input") or {}
            if name == "Bash" and CODEX_RE.search(inp.get("command", "")):
                return None  # reached the next Codex call; output not found before it
            if name == "Read" and _basename(inp.get("file_path", "")) == target:
                return _tool_result_text(events, tu["id"])
    return None


def _follow_through(events, start_idx):
    out, qa = [], False
    for ev in events[start_idx + 1:]:
        if is_human_turn(ev):
            break
        for tu in tool_uses(ev):
            name = tu.get("name")
            inp = tu.get("input") or {}
            if name == "Bash" and CODEX_RE.search(inp.get("command", "")):
                return out, qa
            if name in EDIT_TOOLS:
                out.append({"tool": name, "file": inp.get("file_path", "")})
            if name in ("Task", "Agent") and "reviewer" in (inp.get("subagent_type") or ""):
                qa = True
    return out, qa


def extract_events(events, path="<mem>"):
    episodes = []
    for idx, ev in enumerate(events):
        if ev.get("type") != "assistant":
            continue
        for tu in tool_uses(ev):
            if tu.get("name") != "Bash":
                continue
            cmd = (tu.get("input") or {}).get("command", "")
            if not CODEX_RE.search(cmd):
                continue
            mode = parse_mode(cmd)
            ep = Episode(
                tool_use_id=tu["id"], transcript=path, session=ev.get("sessionId", ""),
                ts=ev.get("timestamp", ""), mode=mode or "unknown", slug=parse_slug(cmd),
                is_sidechain=bool(ev.get("isSidechain")), cmd=cmd,
            )
            if mode in EXCLUDED_MODES:
                ep.audit = "excluded-mode"
                episodes.append(ep)
                continue
            if mode != "review" and mode not in REVIEW_MODES:
                continue
            ep.output = _pair_output(events, idx, ep.slug)
            ep.follow_through, ep.reviewer_qa = _follow_through(events, idx)
            ep.round_index = 1 if PREV_FINDINGS_RE.search(cmd) else 0
            ep.audit = "paired" if ep.output is not None else "no-output"
            episodes.append(ep)
    _collapse_retries(episodes)
    _tag_chains(episodes)
    return episodes


def extract_file(path):
    return extract_events(load_events(path), path)


def _collapse_retries(episodes):
    """Mark exact-duplicate commands within one session as retry-dup (in place)."""
    seen = {}
    for ep in episodes:
        if ep.audit == "excluded-mode":
            continue
        key = (ep.session, ep.cmd)
        if key in seen:
            ep.audit = "retry-dup"
        else:
            seen[key] = ep.tool_use_id


def _tag_chains(episodes):
    """Group an anchor review + its consecutive round-N>=2 marker rounds into one chain."""
    by_session = {}
    for ep in episodes:
        if ep.audit in ("excluded-mode", "retry-dup"):
            continue
        by_session.setdefault(ep.session, []).append(ep)
    counter = 0
    for session, eps in by_session.items():
        eps.sort(key=lambda e: e.ts)
        i = 0
        while i < len(eps):
            members = [eps[i]]
            j = i + 1
            while j < len(eps) and eps[j].round_index == 1:
                members.append(eps[j])
                j += 1
            if len(members) >= 2:
                cid = f"{session}:chain{counter}"
                counter += 1
                for r, e in enumerate(members):
                    e.chain_id = cid
                    e.round_index = r
                i = j
            else:
                eps[i].chain_id = None
                eps[i].round_index = 0
                i += 1


def audit_table(episodes):
    table = {}
    for ep in episodes:
        table[ep.audit] = table.get(ep.audit, 0) + 1
    return table


def iter_transcripts(root):
    yield from glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)


def extract_tree(root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    all_eps, table = [], {}
    for path in iter_transcripts(root):
        eps = extract_file(path)
        all_eps.extend(eps)
        for k, v in audit_table(eps).items():
            table[k] = table.get(k, 0) + v
    bundles = [asdict(e) for e in all_eps if e.audit in ("paired", "no-output")]
    with open(os.path.join(out_dir, "bundles.json"), "w", encoding="utf-8") as f:
        json.dump(bundles, f, indent=2)
    with open(os.path.join(out_dir, "audit_table.json"), "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)
    return table


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.claude/projects")
    out = sys.argv[2] if len(sys.argv) > 2 else "analysis/codex_deepdive/bundles"
    print(json.dumps(extract_tree(root, out), indent=2))
