# Codex Review-Impact Deep Dive — method apparatus

An internal, retrospective audit of Codex review episodes in **one operator's** local
Claude Code transcripts. Not a benchmark of Codex. Every number describes this corpus only.

## Run order
1. `python extract.py "$HOME/.claude/projects" bundles/` produces `bundles/bundles.json` and `bundles/audit_table.json`.
2. Stage 0 pilot (below) is a gate. Do not proceed until it passes.
3. Classify each bundle with a subagent (CLASSIFY_PROMPT_V1) into `out/episodes.jsonl`; validate each object against `schema.json`.
4. `python aggregate.py out/episodes.jsonl > out/aggregate.json`.
5. Stage 4 validation: stratified sample (seed 20260603), hand-label, score agreement, apply the per-metric support gate.

## Denominator
A review episode is one distinct `codex exec` review invocation, keyed by Bash tool-use id.
Counted modes: red-team, diff-review, plan-review, attack-surface, exhausted-hypotheses,
rollout-rollback, and the `codex exec review` subcommand. Excluded: brainstorm, debug,
explain, spec-extraction, compare-decide, test-gaps, post-mortem. The audit table buckets
every detected invocation (paired, no-output, unpaired, retry-dup, excluded-mode). Project
count and date range are derived from the data, never hardcoded.

## How the headline is defined (read before quoting a number)
- The headline is "% of review episodes with at least one `valid`, subsequently-`adopted` finding."
  `valid` means technically correct. `debatable` findings (judgment calls) are NOT in the headline;
  they sit on the invalid/debatable burden ledger, reported separately.
- `adopted` includes `partial` adoption (the artifact changed in response, fully or partly). This is
  a deliberate definitional choice; a strict adopted-only rate would be lower.
- "Adopted in the transcript" is adjacency, not proven causation (the edit may have been already
  planned, test-forced, or user-directed). Causal language is reserved for individual stories with
  explicit quoted rationale, never the aggregate.
- Report the single-shot rate and the chain rate side by side (`pct_single_shot_with_valid_adopted`
  and `pct_chains_with_valid_adopted`), not the blended all-episode rate: convergence rounds are not
  independent and would inflate a single headline.
- Impact tiers `plan/direction-change` and `scrapped` require explicit quoted rationale or
  before/after evidence; absent that, a finding is downgraded to `local-edit`.

## Validation
Stratified by mode, first-finding verdict, and impact_tier; seed 20260603 (committed for
reproduction). A published number is suppressed unless its slice has at least 5 hand-validated
instances (`supported(threshold=5)`). Agreement is scored per field against the human label as
ground truth; a missing machine label counts as disagreement. Stratification keys on the first
finding only, so a rare tier hidden behind a first finding can be under-sampled: any `scrapped`
or `plan/direction-change` rate must be hand-confirmed to have real validated instances before
publishing, not assumed from the stratum count.

## Known limitations (disclose alongside the numbers)
- Retry de-dup is byte-exact: only character-identical `(session, command)` pairs collapse to one
  episode, so a retry differing by a flag or slug counts twice. Eyeball the `retry-dup` count.
- The follow-through window over-attributes: edits from the invocation up to the next human turn or
  next Codex call are attributed to the review, including unrelated same-turn work, so "edits per
  review" is an upper bound.
- Mode parse is first-match on the command text, so a prompt body pasting a conflicting `Mode:` line
  could be misclassified (see the pilot checklist).
- Sidechain and subagent reviews can be double-counted (a sidechain event in a parent transcript plus
  the subagent's own transcript). Size this in the pilot before trusting totals.
- Timestamps are assumed uniform UTC ISO-8601 (`...Z`); a mixed-offset timestamp would break the
  lexical date_range sort.

## Stage 0 pilot: corpus-grep checklist (run before full mining)
Measure how much the limitations above actually bite on the real corpus, then decide:
1. Commands matching `codex exec` plus `review` that the mode filter might drop (flags before `review`).
2. Sessions mixing two or more review modes (chain-grouping sanity).
3. Commands with two or more `Mode:` matches (mode-parse contamination).
4. Count of `codex exec` review calls inside `subagents/*.jsonl` versus `isSidechain` events in parent
   transcripts (double-count risk); decide whether to skip sidechain events in parent files.
5. The `retry-dup` count and any near-duplicate (non-identical) retries.
Record findings and decisions here, then run the pilot label sheet and the two gating claims:
"% of episodes with at least one valid, subsequently-adopted finding" and "category split among
adopted findings". If either is unstable, revise the prompt or buckets and re-pilot.

## Pilot outcome
The Stage 0 pilot did its job: it showed the original detector was undercounting badly. Three bugs, all in the pre-pilot `extract.py`:

- it required a literal `Mode:` line in the *command*, so it dropped the bulk of real reviews (~355 piped-file calls of the form `cat artifact.md | codex exec -`, where the prompt and `Mode:` live in the file, not the command line);
- it de-duped on `(session, command)` identity, so transcript event-duplication (the same tool-use repeated) was mislabeled `retry-dup` and dropped;
- it grouped convergence on a `Previously identified findings:` marker that never appears in real commands, so it reported 0 chains.

Net effect: ~172 reviews / 0 chains, against a far larger true corpus. Rather than patch the filter, I rebuilt detection (the `extract.py` and `enumerate.py` docstrings are now the authoritative spec):

- enumerate every Bash command containing `codex`, de-duped by Bash tool-use id;
- separate real invocations from `cat`/`rm`/`git` of codex files (`is_invocation`);
- classify review vs non-review by output shape (`## Breakage` / Verdict / Findings) and narration, not by `Mode:`-in-command;
- reconstruct convergence by `-o` output-slug lineage (strip `-r2`/`-v3`/round suffixes); ≥2 distinct-output rounds = a chain.

Rebuilt run: **~450 reviews, ~50 convergence chains, ~270 rounds, deepest 32**, across 9 projects. Triangulated three ways: the 8-subagent manual read (~62 chains), the deterministic `classify_corpus.py` over the broad enumeration (~46 chains), and ~60 versioned `-rN/-vN` output-file series still on disk.

Impact was then judged by 8 per-project subagents reading full outputs and tracing follow-through at `transcript:line` (results in `out/impact_synthesis.md`): ~1,300 findings (~3/review), ~2% false-finding rate, ~32% reaching a plan/direction change, ~52 chains with ~62% converging, zero full scraps. The formal classify/validate pipeline (`schema.json`, `classify_prompt.md`, `aggregate.py`, `validate.py`) stays in the repo as the stricter contract; the executed pass was the lighter subagent read over the rebuilt bundles.

This supersedes "Run order" step 1 and the `(session, command)` retry-dedup limitation above (now keyed on Bash tool-use id).

## Residual detector limitations (flagged in a later Codex diff-review)
A post-rebuild Codex diff-review surfaced more detector issues. None move the headline counts (those are bracketed by the three-way triangulation above, and every published figure carries a `~`), but a reusable version would need them fixed:

- `enumerate.py::find_output` pairs output by basename across the whole transcript, so a reused `-o` slug or a same-named file elsewhere can attach the wrong output, which then skews classification and chain tagging.
- Chain identity is `(project, session, slug_stem)` with no temporal-adjacency, transcript, or sidechain key, so independent reviews of one file in a session — or a main-plus-sidechain pair — can merge.
- `slug_stem` strips trailing bare digits unconditionally, so meaningful IDs (`codex-2026.txt`, `codex-rfc-9110.txt`) collapse into broader stems.
- Retry de-dup keys on the first 200 output chars and treats empty output as distinct, so same-preamble rounds can drop and no-output repeats can form a spurious chain.
- `EXEC_RE` is substring-based (a quoted `codex exec` in another command counts; `codex.cmd exec` is missed); `REVIEW_OUT_RE` is broad enough to promote some non-review outputs and misses the unspaced `NEEDS-MAJOR` / `NEEDS-MINOR` form.

A reusable version would centralise one detector core (`extract.py` and `classify_corpus.py` currently duplicate it), pair output by invocation index with a stop at the next call, and gate chains on temporal adjacency. For this one-shot audit, the triangulated counts stand.

## Privacy and provenance
Raw bundles hold client and academic content, so they stay local and git-ignored. Only this
apparatus, the anonymized aggregate, and sanitized stories are public. Classifier prompt:
CLASSIFY_PROMPT_V1. Validation seed: 20260603. Audit table: <filled at run>.
