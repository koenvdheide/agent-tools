# review-plugins

A Claude Code plugin marketplace for reviewing AI-generated output.

## Install

Add the marketplace:

```text
/plugin marketplace add koenvdheide/review-plugins
```

Install `claude-reviewer` **first** (the `review-suite` plugins depend on its `reviewer` subagent for mandatory QA steps):

```text
/plugin install claude-reviewer@review-plugins
/plugin install review-suite@review-plugins
```

## Plugins

| Plugin | Slash commands | Description |
| --- | --- | --- |
| [`claude-reviewer`](https://github.com/koenvdheide/claude-reviewer) | `/claude-reviewer:qa` | Reviewer subagent that catches miscounts, duplicates, stale totals, hallucinations, and internal contradictions. |
| `review-suite` | `/review-suite:codex`, `/review-suite:gemini`, `/review-suite:brainstorming` | External-LLM wrappers for independent red-team / brainstorm / diff-review, plus a spec-document brainstorming workflow with mandatory reviewer QA. |

### Dependencies

`review-suite` invokes the `reviewer` subagent from `claude-reviewer` for its mandatory QA steps (high-stakes Codex/Gemini modes and brainstorming's External Review Round). Claude Code's plugin manifest has no auto-install dependency field, so install `claude-reviewer` manually before using `review-suite`. If the reviewer subagent is unavailable, the skills fall back to self-review with a flagged caveat (see each skill's SKILL.md).

## Local development

To iterate on this marketplace without pushing:

```text
/plugin marketplace add c:/Users/koen_/Documents/Projects/review-plugins
/plugin install claude-reviewer@review-plugins
/plugin install review-suite@review-plugins
```

## Attribution

`review-suite/skills/brainstorming` is a modified fork of the brainstorming skill from the [obra/superpowers](https://github.com/obra/superpowers) project (via the `superpowers-extended-cc` community fork). Upstream is MIT licensed, Copyright (c) 2025 Jesse Vincent. The upstream license text is preserved in [`plugins/review-suite/skills/brainstorming/LICENSE-UPSTREAM`](plugins/review-suite/skills/brainstorming/LICENSE-UPSTREAM). See also [`plugins/review-suite/NOTICE`](plugins/review-suite/NOTICE).

## License

MIT (see [`LICENSE`](LICENSE)). Individual plugins and forked skills may have their own attribution — see the `LICENSE` and `NOTICE` files inside each plugin directory where applicable.
