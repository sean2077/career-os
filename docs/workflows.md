# Outcome-First Workflows

This guide is the on-demand orchestration layer for Career OS. Use it when a
request crosses authority boundaries or the owning Skill is unclear. Ordinary
single-Skill work should load only the shared contract, the selected Skill, and
the minimum relevant records.

## Execution protocol

### 1. Name the deliverable

Classify the request before reading broadly:

| Requested result | Default behavior |
| --- | --- |
| Explanation, comparison, brainstorming, or unsent draft | Answer-only; do not create a record by default. |
| Capture, ingest, track, review, update, or durable decision | Reuse or write the smallest canonical record set. |
| Internal preview or local analysis artifact | Build only when it changes the decision or verifies rendering. |
| Public/application artifact or external/account action | Stop at the documented authorization gate. |

A polished answer is not automatically a durable record. A generated artifact
is not automatically shareable, sent, submitted, or successful.

### 2. Use the context ladder

Load context in this order and stop as soon as the result is decision-ready:

1. The user's request, supplied files, IDs, URLs, and quoted facts.
2. The shared contract and one primary Skill.
3. Known active record, explicit Wikilink, filename, or frontmatter match.
4. The smallest related records whose facts could change the result.
5. The authority seed before a canonical write or lifecycle/gate judgment.
6. A second Career Skill only for a distinct authority output.
7. Current web research only for changing or missing external facts.
8. A read-only reviewer only for a material independent challenge or hard gate.

Do not read every authority, scan the whole Vault, browse a fixed source quota,
or dispatch a reviewer merely because those capabilities exist.

### 3. Keep one owner and bounded handoffs

The primary Skill owns the answer and canonical write. A composed Skill returns
only its stable record IDs, decision-relevant fields, unresolved questions, and
freshness boundary. It must not duplicate its record body into the caller's
authority.

Batch related edits and run `career-os check` once after the final canonical
write. Finish with changed IDs/paths, material unknowns, any remaining approval,
and one smallest useful next action.

## Common workflows

### Capture an accomplishment

**Primary:** Career Evidence `capture` or `debrief`.

1. Preserve the smallest attributable observation and source.
2. Ask only what can change personal contribution, result credibility, or reuse.
3. Keep unknown metrics or ownership explicit.
4. Consolidate later when several captures support one Work, Story, or Claim.

Do not create Strategy, Readiness, or Communication records just because the
fact may eventually be useful there. Hand off the Evidence ID when that later
outcome is requested.

### Weekly operating review

**Primary:** the authority with the user's immediate decision; commonly Career
Strategy `align` or Opportunity Decision `track`/`decide`.

1. Read active plans, active Engagements, due next actions, and open Readiness
   blockers—not full history.
2. Identify what materially changed since the last review.
3. Update the primary authority only. Compose another Skill only when its own
   record's state, rationale, or next review materially changed.
4. Return a short priority stack: continue, clarify, stop, and next action.

A quiet week does not require synthetic events, a new plan, or a new review
record.

### Explore a role direction

**Primary:** Role Market `discover`; compose Career Outlook `scan` only when a
changing external thesis could alter the direction.

1. Define role constraints and the decision being made.
2. Produce a small comparable shortlist with sources, freshness, and unknowns.
3. Separate market evidence from personal preference and readiness.
4. Persist the selected direction or reusable Channel, not every search result.

Stop once the shortlist can support a choice or a specific information request.

### Screen a specific JD

**Primary:** Role Market `ingest` + `screen`.

1. Preserve the exact JD, source fidelity, capture time, missing sections, and
   body hash.
2. Reuse linked Evidence and Readiness IDs; do not infer absent support.
3. For an identified employer, compose Opportunity Decision `research` only if
   the canonical Company is absent, stale, ambiguous, or decision-incomplete.
4. Return fit signals, blocking gaps, risks, questions, and a next decision.

Screening does not create application state, tailor a resume, or grant
readiness.

### Prepare an application package

**Primary:** Career Communication `tailor`/`validate`; prerequisites may compose
Role Market and Career Evidence.

1. Use one exact reviewed JD and approved Claim IDs.
2. Select the smallest claim set that addresses priority requirements.
3. Draft the resume, cover letter, or application answer without inventing
   metrics or state.
4. Use an evidence audit only for application/public validation or a disputed
   material claim.
5. Build a preview only when rendering matters. Export only at the matching
   authorization gate.

Opportunity Decision `track` changes only after direct evidence or the user's
explicit report that an external event occurred.

### Run an interview-preparation loop

**Primary:** Capability Readiness; compose Career Communication for the Public
Surface and Career Evidence for new attributable facts.

1. Diagnose one target-specific blocker.
2. Run a short coached drill and preserve the original answer.
3. Practice a Minimum Credible Narrative with at most three disclosure hooks.
4. Use isolated reviewers only for strict practice or a readiness assessment.
5. Retest with fresh work; close only the gap that actually passed.

Do not confuse memorized detail, a question bank, or a polished rewrite with
readiness.

### Draft networking or recruiter outreach

**Primary:** Career Communication `compose`; compose Opportunity Decision only
for durable Company/Scope context or a reported engagement event.

1. Use verified relationship, company, role, and Claim facts only.
2. Produce one concise message with a clear purpose and low-friction next step.
3. Keep it answer-only unless reusable wording or durable tracking is requested.
4. Sending the message remains a separate explicit external action.

### Review an offer or negotiation position

**Primary:** Opportunity Decision `decide`; compose Career Communication
`compose` for unsent wording and Career Strategy `align` for material horizon
fit.

1. Separate verified terms, assumptions, missing information, preferences, and
   downside risk.
2. Compare the leading option with a credible alternative and walk-away
   constraints.
3. Draft questions or negotiation language without claiming it was sent.
4. Record acceptance, rejection, or resignation only after a separate explicit
   request and evidence of the event.

### Quarterly or horizon review

**Primary:** Career Strategy `align`/`plan`; compose Career Outlook only for
changing external facts and Capability Readiness only for explicit blockers.

1. Compare current positioning with reviewed evidence, opportunity signals, and
   readiness.
2. Distinguish execution drift from a genuinely changed strategy premise.
3. Revise the existing horizon plan when its purpose remains the same.
4. Preserve disconfirming signals, review date, and one leading next action.

A completed task does not accept strategy; a market thesis does not prove
personal fit.

## Research and reviewer stopping rules

For Company, Market, or Outlook research, begin with the source most likely to
resolve the named uncertainty. Add an independent source when interpretation,
risk, or disagreement matters. Stop when decision-critical dimensions are
covered and additional sources repeat the same information; preserve unknowns
rather than widening the search indefinitely.

Use reviewers only when independence changes the decision: strict interview
practice, readiness adjudication, application/public evidence validation,
material communication audit, or high-impact strategy/outlook challenge. A
reviewer is not a second workflow owner and does not write records or authorize
an action.
