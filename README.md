# agent-tools

Our AI overlords like to slip in some slop every now and then to keep us on our toes. They're error-prone when generating but good at catching those same errors when reviewing. The same model that'll confidently make up an API call will flag that exact fabrication when you paste it back and ask it to look for issues. Crossing models works better than any single model reviewing itself: Sonnet reviewing Opus, say, or a plan sent through Codex for a second opinion.

That's the idea behind most of the plugins in this marketplace. They make review a real step in your workflow, so errors get caught before they compound.

## The feedback loop

Once a reviewer points at an error, the generating model can patch it. The hard part is noticing a bug buried in its own output; the patch is easy once someone else points at it. The main session still needs explicit instructions to weigh each finding on its evidence, because LLMs have a strong pull toward agreeing with whatever they were just told, and a confident-sounding review triggers that instinct.

Codex findings are new ideas or design-level critique, and you can't settle those by inspection, so the main session's summary has room to drift. For high-stakes Codex output I run a separate QA pass on the summary; a recent one caught a dropped citation, two invented connections, and a shifted severity grade.

Skipping review ships those errors blind, and occasionally a whole plan built on something that isn't true.

## What Codex reviews add

`/codex:codex` reviews designs and plans adversarially, usually before implementation. Red-team mode structures output under two headings, Breakage (what could fail) and Simplifications (what's over-engineered and can be cut).

To put numbers on this I went back through my Claude Code transcripts and had subagents read every Codex review in full and trace what I did with it afterwards. It's one operator's history, so read it as an internal audit, but it's a real sample: about 450 Codex review calls across 9 projects (code, plus academic-archival and pharma research), ~436 of them judged in full after dropping retries and mislabelled non-reviews. Across that set, roughly:

- about 1,300 distinct findings, call it 3 a review
- around 1,070 were real flaws and ~540 were valid improvements (overlapping categories, not additive)
- only ~28 of those findings were false or invalid, a ~2.1% false-finding rate
- I acted on ~94% of the reviews, mostly in part (taking some findings and leaving others); I rejected two outright
- ~32% went past a local edit into a plan or direction change (a spec revision, a resequenced rollout, a premise I had to go fix), which is the number I care about

Breakage catches what the plan's reasoning didn't account for: overlooked environmental constraints, inverted premises (a step that treats a prerequisite as already satisfied when it isn't), evidence claims that outrun what the tests prove, operational risk in a rollout. In security-adjacent work it's surfaced prompt-injection or trust-boundary mistakes the plan took for granted. The flaw mix matches that: about 630 of the real flaws break down as ~213 correctness, ~159 a missing step, ~110 operational, ~109 a wrong premise and ~37 security. On the academic projects it tilts toward evidence (~188 citation findings across those projects: wrong publisher, a citation year lifted from an archive date, once a source that flatly contradicted the claim it was cited for). Four concrete ones:

- a migration spec that would have corrupted every file it wrote (`Set-Content -NoNewline` with no `-Encoding` on Windows PowerShell 5.1, which defaults to UTF-16)
- a plan pointing register writes at the wrong module, caught before 19 tasks ran against it
- a redaction guard that leaked the secret it guarded by echoing the denied name into its own error log
- the reminder that force-push isn't erasure (sensitive commits stay reachable through forks, PR refs and caches after a history rewrite)

Simplification matters because LLM-generated plans drift toward over-engineering: a model left to plan on its own adds abstractions "for robustness," flags "for flexibility," tiers "for future expansion." An adversarial pass from another model can catch it before implementation bakes it in (~116 of the real flaws were over-engineering). Two I cut on its say-so. One was a configurable state-directory option a plan had added "for flexibility" that no caller needed and that would have quietly broken the existing uninstall path. The other was a third fallback tier in a config-resolution chain that let a tool emit an authoritative-looking result from a weaker substitute (collapsed to two tiers plus fail-closed, so it now stops and reports "unavailable").

The weak spot is subjective style review. A chain where I had Codex vet a CLAUDE.md file for "AI tells" ran about 38% false (it flagged standard curly-quote typography as a tell, called a required `Co-Authored-By` trailer "attribution pollution," and read a deliberately Git-Bash-only scope as a missing feature). Codex is most reliably right on code-correctness, operational, security and domain-factual citation findings, and misfires on taste. Most of the other false findings are incomplete-prompt artifacts, where Codex assumed a file was missing because it wasn't in the snippet I piped in. Outright fabrication is rare.

It's most useful on a spec or plan *before* implementation, where cutting a layer or fixing a premise is still a free win, and the findings come with enough reasoning to apply or reject on the spot.

## Convergence mode (Codex)

Single-pass review catches a lot, but a spec usually has more than one layer of problems, and fixing the top one exposes the next. Convergence mode turns the one-shot call into a user-gated loop: Codex reviews, I apply fixes, it re-reviews the new version, repeat until it stops finding things that matter (or I call it). Each round runs the same command over the evolving file, so the artifact is the main thing changing round to round. Simplification also compounds there: round one cuts the obvious layer, round two sees the next one now that it's exposed.

In the transcripts this was about 52 review chains, and ~62% reached an affirmative verdict in-session (CONVERGED / READY / no-redesign-needed). When it works, each round comes back with less to fix than the last:

- an enrichment red-team: 6 findings → 5 → 4 → 3 → 2 → CONVERGED
- a spec review: 11 → 5 → 1 → CONVERGED
- a compaction eval-plan: NEEDS-MAJOR → MINOR → MINOR → MINOR → READY

The deepest chains ran 28 and 32 rounds, though those were mostly iterative QC and sanitisation where flaw density stayed flat (a real loop, just lower-stakes than rescuing a design). The other ~38% don't converge inside the session: sometimes the spec is genuinely contested and stays mixed for rounds, sometimes I'm using the loop as feedback and ship anyway after settling the question empirically. The mode's own failure case is the scope-drift spiral, where each round's "valid" finding is locally reasonable but the accumulation quietly pulls the artifact off the original brief. Both the `codex` and `antigravity` SKILL.md call this out and tell Claude when to stop and re-confirm scope. (When I red-teamed the plan behind these numbers, Codex caught a bug in my own counting logic before it shipped wrong figures.)

## Why Antigravity too

The same red-team shape applies to `/antigravity:antigravity`: Breakage and Simplifications headings, same prompt structure, same use before implementation, and the same convergence loop. In my usage Gemini produces less thorough reviews and shows less lateral thinking on open problems, so I treat it as a fallback. I reach for it when Codex is rate-limited, or when I want a cross-check on a Codex finding from a different model family. If you install one plugin from here, install `codex`.

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

> **Migrating from `gemini`:** that plugin is now `antigravity`, wrapping the Antigravity CLI
> (`agy`) instead of the Gemini CLI, and it lives at
> [koenvdheide/antigravity-skill](https://github.com/koenvdheide/antigravity-skill). A plugin's
> name is its installation identity, so the rename does not convert an installed copy. Check
> the scope with `claude plugin list --json`, then uninstall `gemini` and install
> `antigravity` at that same scope; uninstall defaults to `user` and would leave a
> project- or local-scoped copy behind. Invocation becomes `/antigravity:antigravity`.

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
