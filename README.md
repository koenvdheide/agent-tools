# review-plugins

Our AI overlords like to slip in some slop every now and then to keep us on our toes. But there is a saving grace: they're error-prone when generating, but good at catching these same errors when reviewing. The same model that'll confidently make up an API call will flag that exact fabrication when you paste it back and ask it to look for issues. And it gets better when you cross models: e.g. Sonnet reviewing Opus, or sending a plan through Codex for a second opinion, catches way more than any single model reviewing itself.

That's the whole idea behind this marketplace. The plugins here make review a real step in your workflow to help you catch such errors early before they compound.

My own setup: I work in Claude Code using Opus but run the `claude-reviewer` agent on Sonnet over anything that matters: code changes, plans, designs etc. Sonnet is cheaper (which adds up fast when you're reviewing constantly), surprisingly good at reviewing and crossing models like this seems to catch errors more reliably. 

I hit `/qa` to trigger a review on basically anything a Claude Code session produces. I collected the statistics of these review calls:

The **1,500+ reviewer runs** over 30+ projects (code, bug hunting, architecture and design docs, academic archival research and writing etc.) caught the following:

- **~86% of reviews surfaced at least one real issue** (reviewer flagged it, main session confirmed it was actually an error)
- **~2.3 confirmed errors per review** on average, plus ~2.7 verification flags for human follow-up

**What it tends to catch:**

| Category | Share of confirmed errors | Typical example |
| --- | --- | --- |
| Consistency | ~30% | Summary says "3 categories", details contain 4 |
| Counting & arithmetic | ~10% | "Top 10" list contains 9 items |
| Completeness | ~10% | Promised section never appears; JSON array cut off mid-object |
| Stale references | ~5% | Docstrings describing old behavior after a refactor |
| Logic errors | ~5% | Boolean OR masking a missing field check |
| Hallucinations / factual errors | ~2% | Fabricated citations, invented claims, wrong function calls |

Every so often it catches something bad enough that you scrap the plan instead of patching it. These include fabricated dependencies that don't exist, load-bearing assumptions that turn out to be false, or a misread premise that's quietly poisoned every conclusion downstream.

If you're not reviewing, you're shipping roughly two real errors per generation. And occasionally a whole plan built on something that isn't true.

## Plugins

| Plugin | Slash command | Source repo | Description |
| --- | --- | --- | --- |
| `claude-reviewer` | `/qa` | [koenvdheide/claude-reviewer](https://github.com/koenvdheide/claude-reviewer) | Reviewer subagent that catches miscounts, duplicates, stale totals, hallucinations, and internal contradictions. |
| `codex` | `/codex` | [koenvdheide/codex-skill](https://github.com/koenvdheide/codex-skill) | Wraps the Codex CLI as an independent analysis partner — brainstorm, red-team, debug, plan-review, diff-review, and other modes. |
| `gemini` | `/gemini` | [koenvdheide/gemini-skill](https://github.com/koenvdheide/gemini-skill) | Wraps the Gemini CLI — independent analysis from a different model family. |
| `brainstorming` | `/brainstorming` | [koenvdheide/brainstorming-skill](https://github.com/koenvdheide/brainstorming-skill) | Spec-document brainstorming workflow with External Review Round (reviewer + /codex:codex). Fork of obra/superpowers. |

## Install

Add the marketplace:

```text
/plugin marketplace add koenvdheide/review-plugins
```

Install `claude-reviewer` **first** — the other plugins work better with its `reviewer` subagent for mandatory QA steps:

```text
/plugin install claude-reviewer@review-plugins
```

If you have a Codex subscription there is a skill that wraps the Codex CLI for review sessions:

```text
/plugin install codex@review-plugins
```

And for the theater kids there is the same for the Gemini CLI:

```text
/plugin install gemini@review-plugins
```

There is also a fork of the popular brainstorming plugin that incorporates /qa and /codex review calls for every major step:

```text
/plugin install brainstorming@review-plugins
```


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
