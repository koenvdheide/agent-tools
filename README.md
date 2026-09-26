# agent-tools

Our AI overlords like to slip in some slop every now and then to keep us on our toes. They're error-prone when generating but good at catching those same errors when reviewing. The same model that'll confidently make up an API call will flag that exact fabrication when you paste it back and ask it to look for issues. Crossing models works better than any single model reviewing itself: Fable reviewing Opus, say, or a Claude plan sent through Codex for a second opinion.

## The feedback loop

Once a reviewer points at an error, the generating model can patch it. The hard part is noticing a bug buried in its own output; the patch is easy once someone else points at it. The main session still needs explicit instructions to weigh each finding on its evidence, because LLMs have a strong pull toward agreeing with whatever they were just told, and a confident-sounding review triggers that instinct. Higher level model findings are often new ideas or design-level critique, and you can't settle those by inspection, so the main session's summary has room to drift. 

## What Codex reviews add

`/codex` reviews designs and plans adversarially, usually before implementation. Red-team mode structures output under two headings, Breakage (what could fail) and Simplifications (what's over-engineered and can be cut).

Breakage catches what the plan's reasoning didn't account for: overlooked environmental constraints, inverted premises (a step that treats a prerequisite as already satisfied when it isn't), evidence claims that outrun what the tests prove, operational risk in a rollout. In security-adjacent work it's surfaced prompt-injection or trust-boundary mistakes the plan took for granted. The flaw mix matches that: correctness, a missing step, operational risk, a wrong premise, security. On the academic projects it tilts toward evidence: wrong publisher, a citation year lifted from an archive date, once a source that flatly contradicted the claim it was cited for. Four concrete ones:

- a migration spec that would have corrupted every file it wrote
- a plan pointing register writes at the wrong module, caught before 19 tasks ran against it
- a redaction guard that leaked the secret it guarded by echoing the denied name into its own error log

Simplification matters because LLM-generated plans drift toward over-engineering: a model left to plan on its own adds abstractions "for robustness," flags "for flexibility," tiers "for future expansion" and a disgusting amount of tests. a An adversarial pass from another model can catch it before implementation bakes it in. 

It's most useful on a spec or plan *before* implementation, where cutting a layer or fixing a premise is still a free win, and the findings come with enough reasoning to apply or reject on the spot.

## Architectural ownership

Both review plugins also ask where a behaviour or shared fact belongs before judging the fix. For code and technical plans, every review round includes an ownership check that follows dependencies and forks outside the diff, distinguishes adapter translation from compensating for another component's defect, and asks for the smallest fix in the owning component. Explain mode omits this check. The full checklists live with the [Codex skill](https://github.com/koenvdheide/codex-skill/blob/main/skills/codex/references/architectural-ownership.md) and [Antigravity skill](https://github.com/koenvdheide/antigravity-skill/blob/main/skills/antigravity/references/architectural-ownership.md).

## Convergence mode (Codex)

Single-pass review catches a lot, but a spec usually has more than one layer of problems, and fixing the top one exposes the next. Convergence mode turns the one-shot call into a user-gated loop: Codex reviews, I apply fixes, it re-reviews the new version, repeat until it stops finding things that matter (or I call it). Each round runs the same command over the evolving file, so the artifact is the main thing changing round to round. Simplification also compounds there: round one cuts the obvious layer, round two sees the next one now that it's exposed.

A chain that works comes back with less to fix each round:

- an enrichment red-team: 6 findings → 5 → 4 → 3 → 2 → CONVERGED
- a spec review: 11 → 5 → 1 → CONVERGED
- a compaction eval-plan: NEEDS-MAJOR → MINOR → MINOR → MINOR → READY

## Why Antigravity too

The same red-team shape applies to `/antigravity`: Breakage and Simplifications headings, same prompt structure, same use before implementation, and the same convergence loop. In my usage Gemini produces less thorough reviews, hallucinates a LOT more and shows less lateral thinking on open problems, so I treat it as a fallback. I reach for it when Codex is rate-limited, or when I want a cross-check on a Codex finding from a different model family. If you install one plugin from here, install `codex`.

## Context handoff: prep-compact

`prep-compact` solves a different agent-coding problem. Long Claude Code sessions hit `/compact` eventually, and default compaction often loses session-specific context: what you decided not to do, what your preferences were, why a previous attempt failed. The plugin keeps a warm on-disk handoff and, on demand, drafts a tailored `/compact <instructions>` command that preserves the load-bearing context. Same spirit as the review tools: don't let the model silently degrade your work over time.

## Build pipeline: orchestrated-build-flow

The review plugins are building blocks; `orchestrated-build-flow` composes Codex review into one guided build pipeline. It takes a non-trivial change from brainstorming through spec, plan, and subagent-driven implementation, and inserts Codex checkpoints at three points: the spec (red-team), the plan (plan-review), and the implementation diff (diff-review). Each checkpoint writes a durable receipt, so a skipped or stale review is caught and re-run, and an interrupted session resumes where it left off. It builds on the `superpowers-extended-cc` skills (a separate install) and declares `codex` as a plugin dependency.

## Plugins

| Plugin | Slash command | Source repo | Description |
| --- | --- | --- | --- |
| `codex` | `/codex:codex` | [koenvdheide/codex-skill](https://github.com/koenvdheide/codex-skill) | Wraps the Codex CLI as an independent analysis partner: brainstorm, red-team, debug, plan-review, diff-review, and other modes. |
| `antigravity` | `/antigravity:antigravity` | [koenvdheide/antigravity-skill](https://github.com/koenvdheide/antigravity-skill) | Wraps the Antigravity CLI (`agy`) for independent analysis from a different model family. |
| `prep-compact` | `/prep-compact:prep-compact` | [koenvdheide/prep-compact](https://github.com/koenvdheide/prep-compact) | Warm-handoff sidecar that drafts tailored `/compact` instructions when the context window fills. |
| `orchestrated-build-flow` | `/orchestrated-build-flow:orchestrated-build-flow` | [koenvdheide/orchestrated-build-flow](https://github.com/koenvdheide/orchestrated-build-flow) | Runs the brainstorm → spec → plan → execute pipeline with three Codex convergence checkpoints (spec, plan, diff) and resumable, receipt-gated phases. |

## Install

Add the marketplace:

```text
/plugin marketplace add koenvdheide/agent-tools
```

If you have a Codex subscription there is a skill that wraps the Codex CLI for review sessions:

```text
/plugin install codex@agent-tools
```

And for the theatre kids there is the Antigravity CLI wrapper too:

```text
/plugin install antigravity@agent-tools
```

And `prep-compact` for the warm session handoff:

```text
/plugin install prep-compact@agent-tools
```

And `orchestrated-build-flow` to run the whole brainstorm-to-implementation pipeline with Codex checkpoints (it pulls in `codex` automatically; the `superpowers-extended-cc` skills are a separate prerequisite from [pcvelz/superpowers](https://github.com/pcvelz/superpowers), and the [orchestrated-build-flow README](https://github.com/koenvdheide/orchestrated-build-flow#prerequisites) has the exact command):

```text
/plugin install orchestrated-build-flow@agent-tools
```

After installing, run `/reload-plugins` to activate everything in the current session (or restart Claude Code).

Refresh later with `/plugin marketplace update agent-tools`, then `/plugin update <name>@agent-tools` for each plugin you want moved to the new version, then `/reload-plugins`. The marketplace refresh only updates the catalogue, and third-party marketplaces have auto-update off by default.

## License

MIT (see [`LICENSE`](LICENSE)). Individual plugins have their own licenses in their source repos: see each repo's `LICENSE` file and any `NOTICE` file if present.
