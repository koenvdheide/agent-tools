---
name: gemini
description: >-
  Invoke the local Gemini CLI as an independent analysis partner from a
  different model family. Use for brainstorming, red-teaming, diff review,
  or any task needing a non-Claude perspective.
  Do NOT use for trivial tasks, simple lookups, or when no concrete artifact
  or question exists yet.
---

# Gemini as a Thinking Partner

`gemini -p` provides independent perspective from Google's Gemini model family. Runs locally via Gemini CLI, can optionally read codebase, returns analysis to stdout.

## When to Use

- Have a Codex answer you want to cross-check, or need independent reasoning from a non-Anthropic / non-OpenAI model
- Task needs Gemini's 1M-token context window (content is too large for Codex)
- Codex is unavailable — rate-limited, auth broken, CLI failing, or service error

## When NOT to Use

- Single-file mechanical edit (typo, rename, one-import change) with no new concepts
- Answer is already in context
- Conversation is active back-and-forth, or user indicated urgency — 1–5 min wait would break the flow
- Already used Gemini (or Codex) for this question this session, OR you're about to fire both on the same prompt — escalate to user
- No specific artifact or concrete question — just a topic or area to "think about"
- Prompt would contain secrets, credentials, or PII
- Question is about Claude Code internals (hooks, skills, MCP, settings) — `/claude-code-docs` knows, external CLIs don't
- Answer lives in library/tool docs — WebFetch, Context7, or `man` is cheaper
- Missing local facts — reproduce the issue, inspect logs, run `rg`/`git`/`blame`, or ask user for clarification — before outsourcing reasoning
- Decision depends on product priority, compliance, or release timing not in my context — ask the user (who owns this) first
- Codex is available and the prompt fits comfortably — Gemini is fallback, not the default first reviewer

## Precedence

When multiple bullets match a single prompt:

- **WNTU wins over WTU.** If any When NOT to Use bullet matches, don't fire — even if a When to Use bullet also matches. If unsure, ask the user ("I'd skip Gemini here because X; proceed anyway?") rather than firing.
- **Among WTU, pick the most specific.** The more specific scenario carries more relevant context.
- **Among WNTU, privacy beats cost.** Privacy/confidentiality skips are hard (never fire). Session/cost skips are soft (can escalate to user). If a prompt would contain secrets, that overrides every other consideration.

## Execution Reference

### Basic Invocation

```bash
# Short prompt — pure reasoning, no file access
gemini -s --approval-mode plan -m gemini-2.5-pro -o text \
  -p "Your prompt here" > /tmp/gemini-slug.txt 2>/dev/null

# Long prompt via heredoc
gemini -s --approval-mode plan -m gemini-2.5-pro -o text -p "$(cat <<'PROMPT'
Mode: red-team
Question: Find failure modes in this approach.
Context:
...your context here...
Current belief: The conditional logic is correct.
PROMPT
)" > /tmp/gemini-slug.txt 2>/dev/null

# Source code via pipe (safe for backticks, $, etc.)
cat file.rs | gemini -s --approval-mode plan -m gemini-2.5-pro -o text \
  -p "Explain this code. Flag anything that looks like a bug." \
  > /tmp/gemini-slug.txt 2>/dev/null
```

**Do not combine** a positional prompt argument with `-p` — use one or the other.

### Key Flags

| Flag | Purpose |
|------|---------|
| `-s` / `--sandbox` | Run in sandbox isolation. **Mandatory on every invocation** — prevents file writes from escaping to the working directory. |
| `-p "prompt"` | Provide the prompt. Triggers non-interactive mode. Stdin content is prepended to this. |
| `-m model` | Model selection (default: `gemini-2.5-pro`) |
| `--approval-mode plan` | Read-only — blocks tool use. Use for pure reasoning on provided input. |
| `--approval-mode yolo` | Auto-approve all tools. Use when Gemini needs to read files. |
| `-o text` | Plain text output. Use `-o json` for structured output with stats. |

### Mode-to-Sandbox Table

| Mode | Approval | Sandbox | Why | Write risk |
|------|----------|---------|-----|------------|
| Brainstorm | `plan` | yes | Reasoning on provided context | LOW — plan mode, content piped |
| Red-team | `plan` | yes | Pure analysis, content piped | LOW — plan mode, content piped |
| Diff Review | `plan` | yes | Diff/report piped via stdin | LOW — plan mode, content piped |
| Explain | `plan` + pipe | yes | Pipe file content via stdin instead of yolo | LOW — no file access |
| Attack Surface | `yolo` + git-stash | yes | Must navigate codebase autonomously | **HIGH — git-stash wrapper mandatory** |
| Exhausted Hypotheses | `yolo` + git-stash | yes | Must navigate codebase + pipeline state | **HIGH — git-stash wrapper mandatory** |

**Key change from earlier version:** Explain mode no longer uses `yolo`. Pipe relevant files via stdin with `plan` mode. Only Attack Surface and Exhausted Hypotheses genuinely need autonomous file navigation — those MUST use the git-stash wrapper.

**Always use `--sandbox`** on every invocation. The `--approval-mode plan` flag claims to be "read-only" but does NOT reliably prevent file writes — Gemini has been observed writing files, creating directories, modifying `pytest.ini`, and even executing entire implementation plans despite `plan` mode. The `--sandbox` flag provides additional isolation but is ALSO unreliable on Windows (Docker must be running; without it, writes escape to the host filesystem silently).

**CRITICAL: Gemini WILL write to your working directory.** Treat every Gemini invocation as potentially destructive. Mitigations below are mandatory, not optional.

### Execution Rules

- **Always add `-s` (or `--sandbox`)** to every gemini invocation — no exceptions
- Use `run_in_background: true` so user is not blocked
- Always redirect stderr: `2>/dev/null` (suppresses YOLO mode spam and libuv warnings)
- **Cleanup:** after reading output file, delete it (`rm -f /tmp/gemini-slug.txt`)
- Use descriptive slugs: `/tmp/gemini-redteam-auth.txt`, not `/tmp/gemini-output.txt`
- **Wait for completion:** NEVER read or delete the output file (the `> /tmp/gemini-slug.txt` redirection target) until you receive `<task-notification>` confirming background task completed. File may be 0 bytes or missing before Gemini finishes — does NOT mean it failed. Premature reads produce false "empty output" conclusions; premature deletes destroy results the process is about to write.
- **Re-launch safety:** if re-launching a Gemini invocation, use a DIFFERENT output file path (e.g., `/tmp/gemini-redteam-auth-v2.txt`). Never reuse the same output path as a still-running or recently-launched invocation — two processes will collide on output file.
- **Chase down all output:** if output file is empty but task completed successfully, Gemini may have written to an internal location (e.g., `.gemini/tmp/`). Check background task log for file paths and read them. Never skip or dismiss review output because it ended up somewhere unexpected.
- **Passing output paths to subagents:** subagents launched via Task/Agent run in an isolated tool environment that does NOT resolve Git Bash's `/tmp/` to its native Windows path (`C:\Users\<user>\AppData\Local\Temp\`). The subagent's Read tool will fail to find `/tmp/gemini-<slug>.txt`. Two safe patterns: (1) **inline content** — `cat /tmp/gemini-<slug>.txt` in the parent shell and paste the output directly into the subagent prompt; works on every platform; preferred for outputs ≤ ~50KB. (2) **convert path** — on Windows + Git Bash, pass `$(cygpath -w /tmp/gemini-<slug>.txt)` (yields `C:\Users\...\Temp\gemini-<slug>.txt` which the subagent's Read tool resolves natively). On Linux/macOS, the literal `/tmp/` path works as-is. Inline content is the default; convert-path is the fallback when output is too large to embed in the prompt.

### Mandatory Write Protection (prevents sandbox escapes)

Gemini's sandbox is unreliable on Windows. These steps are MANDATORY for every invocation:

**Before launching Gemini:**
```bash
# Snapshot current state
git stash --include-untracked -m "gemini-pre-snapshot" 2>/dev/null; GEMINI_STASHED=$?
```

**After Gemini completes (in the task-notification handler):**
```bash
# Check for unauthorized writes
GEMINI_CHANGES=$(git status --short)
if [ -n "$GEMINI_CHANGES" ]; then
    echo "WARNING: Gemini wrote to working directory despite sandbox:"
    echo "$GEMINI_CHANGES"
    # Revert ALL Gemini writes
    git checkout -- .
    git clean -fd 2>/dev/null
fi
# Restore pre-Gemini state
if [ "$GEMINI_STASHED" -eq 0 ]; then git stash pop 2>/dev/null; fi
```

**Simplified rule:** if you don't want to stash/unstash, at minimum run `git status --short` after every Gemini completion and `git checkout -- .` if anything changed. Bare minimum.

**For yolo mode specifically:** when Gemini needs to read files (Explain, Attack Surface, Exhausted Hypotheses), prefer piping file content via stdin over yolo mode:
```bash
# PREFERRED: pipe content, use plan mode (no file writes possible)
cat file1.py file2.py | gemini -s --approval-mode plan -m gemini-2.5-pro -o text -p "Explain this code"

# AVOID: yolo mode (Gemini can and will write files)
gemini -s --approval-mode yolo -m gemini-2.5-pro -o text -p "Explain the code in file1.py"
```

Only use yolo when Gemini genuinely needs to navigate codebase autonomously (e.g., Exhausted Hypotheses where you don't know which files are relevant). In those cases, the git-stash wrapper is mandatory.

## Session Management

**Not yet supported.** Gemini's `-r <index>` may use positional indexes that shift across unrelated calls, making session resume unsafe. Session support is deferred until stable opaque session IDs are verified.

If any session flag is passed (`--session`, `--new-session`, `--artifact`, `--reuse-session`, `list`, `delete`), hard-fail with:

> "Gemini session resume is not yet supported — pending stable session ID verification. Remove session flags and run as one-shot."

This error takes precedence over all other flag validation (including review-mode gating).

### Model Selection

| Model | When |
|-------|------|
| `gemini-2.5-pro` | Default for deep analysis and complex reasoning |
| `gemini-2.5-flash` | Fast turnaround, good for most tasks |
| `gemini-2.5-flash-lite` | Cheapest and fastest, simple questions |
| `gemini-3.1-pro-preview` | Maximum reasoning capability (preview, may be unstable) |
| `gemini-3-flash-preview` | Next-gen speed + quality balance (preview) |
| `gemini-3.1-flash-lite-preview` | Next-gen budget option (preview) |

**Rate limits are per-model.** If one model hits a rate limit (429), switch to a different model rather than waiting. For example, if `gemini-2.5-pro` is rate-limited, `gemini-2.5-flash` has a separate quota and may still be available. Choose the strongest available model appropriate for the task.

## Response Style

Append this clause to every outgoing Gemini prompt, regardless of mode:

> Response style: compress prose. Drop fillers, hedges, connectives unless load-bearing. Prefer short active sentences. Keep verbatim: code blocks, diffs, file:line citations, log entries, numbers, names, paths, quoted context, and tables (headers, cells, and structure). Never compress code. If compression would obscure a finding, write normal prose.

Unlike the Codex skill — where this clause lives inside a unified Base Prompt Template and propagates automatically — the Gemini skill has no such template, so the clause must be appended manually on every invocation. TODO: consider adding a Base Prompt Template to this skill so the clause propagates automatically.

## Modes

Lightweight guidance for what to include per mode. Adapt to the situation — these aren't rigid templates.

**Brainstorm** — include constraints (dead-ends, existing hypotheses, "do not rediscover" lists) and the specific question. Ask for 3–5 alternatives with tradeoffs.

**Red-team** — include the plan/approach being attacked and your constraints (framed as hard facts, not beliefs). Ask Gemini to find weaknesses under two explicit headings: Breakage (failure modes, edge cases, wrong assumptions; attack assumptions and give the strongest counterargument) and Simplifications (over-engineering + missed reductions). For each simplification: what to cut/merge/flatten, why safe, expected impact. Do not strip defensive code at system boundaries, WHY comments, or anything whose removal sacrifices clarity for brevity. "Do not agree just to be agreeable."

**Diff Review** — include the diff/report and any source files it references. Ask to verify each claim, flag assumptions stated as facts, check for stale line numbers.

**Explain** — pipe file content via stdin with `plan` mode (preferred), or use `yolo` with git-stash wrapper (only if you don't know which files to pipe). Ask what the code does, why it's structured that way, what's non-obvious.

**Attack Surface** — use `yolo` mode. Include dead-end list and known patterns as constraints. Ask for overlooked vectors, underexplored entry points, non-obvious vulnerability classes.

**Exhausted Hypotheses** — use `yolo` mode. Include full pipeline state (scope, dead-ends, coverage, existing hypotheses) as constraints. Ask for 5–10 novel hypotheses NOT in the dead-ends, with exact file:line references and attack scenarios.

## Handling Output

- **Never relay raw Gemini output.** Extract key findings, disagreements, next steps.
- If Gemini disagrees with your approach, present both perspectives.
- Always validate cited file names and line numbers — Gemini hallucinates references.
- If output is generic/unhelpful, retry once with narrower question. Do not retry more than once.
- **Dead-end persistence:** after triaging Gemini hypotheses, immediately persist killed hypotheses to `notes/dead-ends.yaml` and add an outcome entry to `notes/outcomes.yaml`. Do not defer — context compaction loses the kill reasons.

## Summarization Fidelity

Gemini summaries drift in the same ways Codex summaries do: compression-with-punch turns measured verbs into rhetorical ones, and inline prose citations get skimmed past during bullet-counting. Three rules, ordered by frequency of violation:

### 1. Quote evaluative language verbatim, never paraphrase it

Model verbs are calibrated. `"I disagree"` ≠ `"rejects"`. `"too narrow"` ≠ `"misses an entire class"`. `"targets the pattern class"` ≠ `"highest-leverage"`. If Gemini used a measured verb, quote it — do not substitute a stronger rhetorical synonym when compressing.

- **Bad:** "Gemini rejects the approach in 7 of 7 dimensions."
- **Good:** Gemini restructures 6 of 7 items and says *"I disagree with the belief that X is highest-leverage"* on the 7th.

### 2. Do not add explanatory bridges that are not in source

When Gemini makes a bare claim ("X is too narrow") without giving an example, do not add a parenthetical that supplies one from elsewhere in your context. The connection between two true facts is fabrication if Gemini did not make it.

- **Bad:** "Column 3 is too narrow (misses the platform-failure class — the InboundNonce+UsedHash bundle died on this)"
- **Good:** "Column 3 is too narrow." [no example given by Gemini]

### 3. Count inline citations in prose, not just bullet lists

Gemini sometimes cites `file:line` inside an explanatory sentence rather than in a bullet. When counting call sites or references, scan the prose, not just the list markers. Undercounts happen when you enumerate bullets and miss inline citations.

This rule is especially important for Gemini because its hypothesis output often mixes bullets with prose explanation — unlike Codex, which tends toward stricter bullet structure. A Gemini summary that counts "5 hypotheses" is easy to get wrong if one of them lived inside a narrative sentence.

### Mandatory QA for high-stakes modes

After summarizing Gemini output for `red-team`, `diff-review`, `exhausted-hypotheses`, or `attack-surface` modes, run the reviewer agent on your summary **before presenting it to the user**. These modes produce the longest outputs and the highest-consequence summaries. The QA step is non-optional for them.

Low-stakes modes (`brainstorm`, `explain`) do not require the QA step — rely on the three rules above. Brainstorm output feeds into the hypothesis pipeline where every hypothesis passes through targeted VA and challenge anyway, so a summarization error on a single hypothesis has a built-in safety net.

**Short-output exception:** If the Gemini output is under ~200 words AND contains no bullet lists, numbered findings, or file:line citations, the mandatory QA step can be skipped. Short prose responses leave little room for strength amplification or undercounts — the three failure modes all require enough surface area to happen.

**Reviewer-unavailable fallback:** If the reviewer agent is unavailable (tool failure, subagent budget exhausted), fall back to self-review against the three rules: re-read the source Gemini output, quote every evaluative verb verbatim in the summary, and count inline citations in prose as well as in bullets. Flag the fallback explicitly in the presented summary: *"(self-reviewed against fidelity rules — no reviewer agent pass)"*.

The QA check runs against the source Gemini output and your summary, flagging strength amplification, fabricated bridges, undercounts, and line-number hallucinations. Errors caught in QA must be corrected in the summary before presentation, not annotated afterward.

**Note on hallucination frequency:** Gemini hallucinates cited file paths and line numbers more often than Codex. The "validate cited file names and line numbers" rule above is about hallucinated *references to the codebase*, which is a different failure mode from the summarization errors this section addresses. Both checks are needed for high-stakes modes — validate references against the actual codebase AND run QA against the Gemini source.

### Structured hypothesis output

When using Brainstorm, Attack Surface, or Exhausted Hypotheses modes, append this to your task prompt:

```
For each hypothesis, also include at the end:
- slug: kebab-case-identifier
- asset: which contract(s)
- kill_conditions: what single check would immediately falsify this
```

This makes post-triage persistence to `dead-ends.yaml` faster — slug and asset are pre-populated, and kill_conditions become the `blocker` field if the hypothesis is killed.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Please set an Auth method" | Set `GEMINI_API_KEY` env var or run `gemini` interactively to login |
| "exhausted your capacity" / 429 | Rate limited — wait for reset or switch to API key with billing |
| Empty output | Check stderr (remove `2>/dev/null` temporarily). May be auth or model issue. |
| Hangs indefinitely | Ensure `--approval-mode` is set (prevents interactive approval prompts) |
| Wrong/irrelevant analysis | Check that your prompt actually reached Gemini — verify the heredoc closed properly |
| Subagent reports output file not found | Subagent's isolated tool environment doesn't resolve Git Bash `/tmp/` paths. Inline file content into subagent prompt, or pass `$(cygpath -w /tmp/gemini-<slug>.txt)` on Windows. See Execution Rules → "Passing output paths to subagents". |

## Authentication

### Recommended: API Key with Billing

```
GEMINI_API_KEY=<your-key>  # Set as Windows environment variable
```

Get a key at https://aistudio.google.com/apikey. Link to a billing account for Tier 1 limits (300 RPM, 1000 RPD).

### Not Recommended: OAuth

OAuth via `gemini` interactive login gives only 5 hours/month of CLI usage on AI Pro. OK for quick interactive use, not for automated invocations.
