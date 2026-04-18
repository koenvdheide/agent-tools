# codex-skill

A [Claude Code](https://claude.ai/code) skill that invokes the local [Codex CLI](https://github.com/openai/codex) as an independent analysis partner.

## What it does

Gives Claude Code a structured way to delegate analysis tasks to Codex — brainstorming alternatives, red-teaming plans, debugging from a fresh perspective, reviewing diffs adversarially, and more. Codex runs locally, reads the codebase, and returns its analysis for Claude to synthesize.

## Supported modes

Brainstorm, Red-team, Debug, Plan Review, Diff Review, Spec Extraction, Rollout/Rollback, Compare/Decide, Test Gaps, Explain, Post-mortem, Attack Surface, Exhausted Hypotheses.

## Session resume

Multi-round iterations on the same artifact (review plan v1 → v2, iterative debugging) can preserve prior Codex context via named sessions:

```
/codex --new-session review-auth   # create a named session
/codex --session review-auth       # resume it later
/codex list                        # see all sessions
/codex delete review-auth          # clean up
```

Sessions are stored per-worktree under `.claude/.codex-sessions/`. See the Session Management section in SKILL.md for the full workflow.

## Prerequisites

- [Claude Code](https://claude.ai/code)
- [Codex CLI](https://github.com/openai/codex) installed and on PATH

## Optional: `reviewer` subagent

The skill runs a mandatory QA pass using a `reviewer` subagent after summarizing high-stakes modes (`plan-review`, `red-team`, `diff-review`, `exhausted-hypotheses`, `attack-surface`). It expects the subagent from [koenvdheide/claude-reviewer](https://github.com/koenvdheide/claude-reviewer). Without it, the skill falls back to self-review against the same fidelity rules — workflow still works, just less rigorous.

## Installation

Copy or clone into your Claude Code skills directory:

```bash
git clone https://github.com/koenvdheide/codex-skill.git ~/.claude/skills/codex
```

## Usage

Claude invokes the skill automatically when a task matches, or you can invoke it directly:

```
/codex red-team my authentication refactor plan
```

## License

MIT
