# review-plugins

A Claude Code plugin marketplace for reviewing AI-generated output.

## Install

Add the marketplace:

```text
/plugin marketplace add koenvdheide/review-plugins
```

Install `claude-reviewer` **first** — the other plugins depend on its `reviewer` subagent for mandatory QA steps:

```text
/plugin install claude-reviewer@review-plugins
/plugin install codex@review-plugins
/plugin install gemini@review-plugins
/plugin install brainstorming@review-plugins
```

## Plugins

| Plugin | Slash command | Source repo | Description |
| --- | --- | --- | --- |
| `claude-reviewer` | `/claude-reviewer:qa` | [koenvdheide/claude-reviewer](https://github.com/koenvdheide/claude-reviewer) | Reviewer subagent that catches miscounts, duplicates, stale totals, hallucinations, and internal contradictions. |
| `codex` | `/codex:codex` | [koenvdheide/codex-skill](https://github.com/koenvdheide/codex-skill) | Wraps the Codex CLI as an independent analysis partner — brainstorm, red-team, debug, plan-review, diff-review, and other modes. |
| `gemini` | `/gemini:gemini` | [koenvdheide/gemini-skill](https://github.com/koenvdheide/gemini-skill) | Wraps the Gemini CLI — independent analysis from a different model family. |
| `brainstorming` | `/brainstorming:brainstorming` | [koenvdheide/brainstorming-skill](https://github.com/koenvdheide/brainstorming-skill) | Spec-document brainstorming workflow with External Review Round (reviewer + /codex:codex). Fork of obra/superpowers. |

## Dependencies between plugins

Three of the four plugins call the `reviewer` subagent from `claude-reviewer`:

- `codex` invokes `reviewer` for mandatory QA on high-stakes modes (plan-review, red-team, diff-review, exhausted-hypotheses, attack-surface)
- `gemini` does the same for its high-stakes modes
- `brainstorming` dispatches `reviewer` during the External Review Round

Claude Code's plugin manifest has no auto-install dependency field, so install `claude-reviewer` manually before the others. If the reviewer subagent is unavailable, the skills fall back to self-review with a flagged caveat (see each SKILL.md).

## Local development

Test the marketplace against the local path instead of GitHub:

```text
/plugin marketplace add c:/Users/koen_/Documents/Projects/review-plugins
/plugin install claude-reviewer@review-plugins
```

Note: relative-path plugin sources only resolve when the marketplace is added via Git (not a URL to `marketplace.json`). This marketplace uses `github` sources for all four plugins, so both local-path and GitHub-added marketplaces work identically.

## Attribution

`brainstorming@review-plugins` is a fork of the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers), MIT-licensed (© 2025 Jesse Vincent). Upstream license text is preserved in the source repo at [koenvdheide/brainstorming-skill](https://github.com/koenvdheide/brainstorming-skill).

## License

MIT (see [`LICENSE`](LICENSE)). Individual plugins have their own licenses in their source repos — see each repo's `LICENSE` and `NOTICE` files.
