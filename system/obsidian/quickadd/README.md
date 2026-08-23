# Optional QuickAdd Adapter

Career OS generates three reviewable QuickAdd `2.12.3` choices:

- `capture-choice.json` appends raw text to the Career Evidence inbox. It does
  not create an approved claim or canonical work record.
- `jd-review-choice.json` keeps its stable choice ID while exposing
  `Career OS: Review active record`. The tracked `review-jd.js` script reviews
  the active schema-3 JD, Company, or Engagement.
- `engagement-event-choice.json` exposes
  `Career OS: Record engagement event`. The tracked
  `record-engagement-event.js` script records one explicit recruiting event in
  the active schema-3 Engagement.

## Review active record

For a JD directly under `jds/` or in the recommended `jds/YYYY-MM/` partition
and `screened` state, A-E write `status: reviewed`, `reviewed_at`, `updated_at`,
`user_review_signal`, the matching `case_target`, and a compatible
`next_action`; F writes `status: skipped` and removes review-only fields. It
never infers priority, evidence fit, preference, or growth.

Company review requires a current, non-overdue assessment with complete research
dates. Engagement review requires valid Company and optional JD links, a
current Company assessment, and structurally valid events. Company review
updates both lifecycle and review fields; Engagement review updates only review
fields. Every record type shows the complete proposed change before one
frontmatter transaction and rechecks the source revision before writing.

After a successful review, the command can rescan the same canonical folder and
open the next actionable record. The transient queue has no saved snapshot,
statistics, or resume point.

## Record engagement event

The event command supports recruiter contact, referral, application submission
or closure, scheduled or completed interviews, received/accepted/declined
Offers, and process closure. It proposes editable `stage`,
`application_state`, and `status`, then collects an optional full-date
`review_on` checkpoint and `next_action`.

The script writes the event, projection, checkpoint, action,
`review_status: pending`, and `updated_at` together. Cancellation, an invalid
event prerequisite, chronological regression, an invalid projection, or a
concurrent record change writes nothing. The event source is `user-report`;
the command records an interaction the user says occurred and never performs an
application, message, upload, account action, Offer decision, or resignation.

## Configure QuickAdd and hotkeys

Career OS validates plugin version, generated paths, and all three choice
ID/name contracts. It does not normally edit host-owned
`.obsidian/plugins/quickadd/data.json` or `.obsidian/hotkeys.json`.

Reproduce each generated Macro in **Settings → QuickAdd**, enable it as a
command, and add the generated Vault-relative User Script path. Recommended
hotkeys:

- `Alt+J` → `QuickAdd: Career OS: Review active record`
- `Alt+I` → `QuickAdd: Career OS: Record engagement event`

Before assigning either shortcut, check Obsidian's Hotkeys settings for a
conflict. Do not replace `Alt+E`; the recommended configuration leaves it
available to Templater. When migrating the earlier JD-only choice, retain ID
`8d0e6c70-b092-4e56-a18c-f631ca6b87f2`, its macro and command IDs, rename the
choice and macro in place, and keep the existing `Alt+J` binding.

Agents may prepare and validate these assets. They may modify host QuickAdd
choices or hotkeys only after an explicit user request, and may never choose a
review signal or assert that an external event happened for the user.
