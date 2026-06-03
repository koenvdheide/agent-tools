# Classifier prompt — CLASSIFY_PROMPT_V1

You are labeling ONE Codex review episode from a Claude Code transcript. You are given a bundle: the Codex prompt, Codex's output, the follow-through edits, and any reviewer QA. Emit ONE JSON object matching `schema.json`. Label only what the bundle evidences — never infer beyond it.

## Field rules

- `verdict` — what happened to the finding IN THE TRANSCRIPT, not whether Codex was right:
  - `adopted`: a follow-through edit clearly implements the finding. Example: Codex says "retry path drops the idempotency key"; a later Edit to the retry file adds the key.
  - `partial`: some but not all of the finding was acted on.
  - `rejected`: the operator explicitly declined it.
  - `deferred`: explicitly postponed.
- `validity` — was the finding correct on its merits:
  - `valid`: technically correct. `invalid`: Codex was wrong (a correct rejection is the system working). `debatable`: a judgment call.
- `impact_tier` — how far the change reached. Evidence standard: the top two REQUIRE an explicit quoted rationale or before/after artifact evidence in the bundle; absent that, downgrade to `local-edit`.
  - `not-observed`: no change followed. `local-edit`: a bounded code/prose edit. `plan/direction-change`: the artifact's approach changed (needs quoted rationale). `scrapped`: the artifact/plan was abandoned (needs explicit evidence).
- `category` — coarse bucket only: `correctness`, `evidence/citation`, `operational-risk`, `simplification`, `security/trust-boundary`, `other`.
- `evidence_quote` + `location` — a verbatim snippet from the bundle backing every label.

Do not invent findings the bundle does not contain. If Codex produced no findings, return `findings: []`.
