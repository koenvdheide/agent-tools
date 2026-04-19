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

## The feedback loop

Once a reviewer points at an error, the generating model can patch it — the hard part is noticing a bug buried in its own output, not fixing it once someone else points to it. For reviewer findings, the main session needs explicit instructions to evaluate each finding instead of rubber-stamp it — LLMs have a strong pull toward agreeing with whatever they were just told, and a confident-sounding review triggers that instinct hard. Miscounts, contradictions, stale references — all verifiable on inspection, so the main session can separate signal from noise.

Codex findings are different: new ideas or design-level critique — not point-and-verify, which leaves room for the main session's summary to drift. So for high-stakes Codex output I run a separate QA pass on the summary; a recent one caught a dropped citation, two invented connections, and a shifted severity grade.

Across 1,500+ reviews, the reviewer catches roughly two real errors per artifact. Not reviewing means shipping that error density blind — and occasionally a whole plan built on something that isn't true.

## What Codex reviews add

The stats above are about the `reviewer` subagent, which catches mechanical errors in output. `/codex:codex` is a different layer: it reviews **designs and plans** adversarially, usually before implementation. Red-team mode structures output under two headings — **Breakage** (what could fail) and **Simplifications** (what's over-engineered and can be cut).

**Breakage** catches what the plan's reasoning didn't account for: overlooked environmental constraints, inverted premises (a step that treats a prerequisite as already satisfied when it isn't), evidence claims that outrun what the tests actually prove, operational risks in a rollout. In security-adjacent work it often surfaces prompt-injection risks or trust-boundary mistakes the plan took for granted.

**Simplification** matters because LLM-generated plans drift toward over-engineering. A model left to plan on its own will add abstractions "for robustness," flags "for flexibility," tiers "for future expansion" etc. An adversarial second pass from another model catches it before implementation bakes it in.

When I ran Codex red-team against the spec for `claude-reviewer` itself, it proposed seven Simplifications — four shipped verbatim, one I applied partially, one I kept as-is, one I didn't apply. Zero of them were wording tweaks. Every finding was a whole-concept cut — a flag, a layer, a file, a rename, a misaligned default — with a named target and a one-sentence safety rationale. Codex doesn't have a single thing it's good at flagging; it has a disposition for spotting speculative complexity wherever it lives.


Codex is most useful applied to a spec or plan *before* implementation, where removing a layer or fixing a premise is a free win rather than a refactor. Findings come with enough reasoning to either apply or reject on an informed basis — the review is adversarial by default, but not hand-wavy.

## Why Gemini too

The same red-team shape applies to `/gemini:gemini` — Breakage and Simplifications headings, same prompt structure, same review-before-implementation use case. In my usage Gemini produces less thorough reviews and shows less lateral thinking on open problems, so I treat it as a fallback rather than the default. I reach for it when Codex is rate-limited, when I want a cross-check on a Codex finding from a different model family, or when the prompt needs Gemini's 1M-token window. If you install one plugin beyond `claude-reviewer`, install `codex`.

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
