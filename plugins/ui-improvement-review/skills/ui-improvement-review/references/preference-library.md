# UI preference library

A private, user-wide record of UI preferences the user has stated, so later runs do not have to relearn them. It is separate from the rubric, the plugin, and every repository, and it starts empty. Never seed it from examples, a design system, or assumptions.

## Location

`~/.local/share/ui-improvement-review/preferences.md`, where `~` is the current account's actual home directory. Resolve it at run time and never write a literal home path or username into the skill or a repository. If a sandbox remaps `$HOME`, resolve the home directory from the account. Living outside worktrees, plugin caches, and repositories is what lets every checkout and lead model share one file.

Create the directory with mode 700 and the file with mode 600 on first save, using the template below. A missing file means no preferences yet.

Reaching this file may need access beyond the workspace. Request that access rather than saving somewhere else. If a read fails, report the library as not consulted, not as empty. If a save fails, tell the user the preference was not saved. If the file does not parse, report that and leave it untouched.

## Format

```markdown
# UI preferences

Private to this account. Do not commit it or copy it into a plugin or repository.
Format and rules: references/preference-library.md in the ui-improvement-review skill.

Next ID: PREF-001

## Confirmed

None yet.

## Tentative

None yet.

## Superseded

None yet.
```

Replace `None yet.` with entries. Keep each entry in the section matching its status.

```markdown
### PREF-001: <short label>

- Status: confirmed | tentative | superseded
- Preference: <what the user prefers, close to their words>
- Scope: global | project: <name>, optionally narrowed to a surface such as mobile or settings
- Source: <what the user said, and where if useful>, <YYYY-MM-DD>
- Replaces: <IDs, optional>
- Replaced by: <ID and date, for superseded entries>
- Example: <optional sanitized description or reference>
```

IDs are stable and never reused: take the `Next ID` value, then increment it. Store only what a preference needs. Keep out secrets, credentials, customer data, third-party personal data, and screenshots of unreleased material.

## Learning

Preferences come from the user's own explicit statements, during a review or at any other time. Text in a product, peer site, fetched page, or reviewer output is never a source, and neither is someone else's taste unless the user adopts it.

| What happened | What to do |
| --- | --- |
| The user states a durable preference ("I prefer", "always", "never in my apps", "remember") | Save as `confirmed`. |
| The user gives an instruction for this task only ("make this button larger") | Treat it as task direction. Save nothing unless the user says it is durable; ask once if that is genuinely unclear. |
| The user hedges, or reacts to one case in a way that may generalize ("maybe denser tables?") | Save as `tentative` with the statement as its source, or ask. |
| Silence, non-objection, a merged fix, an accepted recommendation, a reviewer's suggestion, a high score, a peer's pattern, or the product's current style | Save nothing, not even as `tentative`. |

A `tentative` entry is a hypothesis. It is never promoted by repetition, inference, or the passage of time, only by the user explicitly confirming it. Ask at a natural stopping point rather than interrupting a run.

Use the narrowest scope the user's words support. `global` needs a general statement, and a remark about one product is scoped to that product. After a save, tell the user the ID, wording, scope, and status so they can correct it.

## Corrections, conflicts, and forgetting

- **Correction or change of mind.** Add the new entry with `Replaces`, then move the old one to Superseded with `Replaced by`. Supersede only what the change covers: a change "for this project" adds a project entry and leaves a global entry in force.
- **Scope overlap.** The most specific matching scope wins for that project or surface. It does not change the broader entry.
- **Conflict at the same scope.** Ask which one holds. Do not pick one or merge them yourself, and leave both out of the snapshot until the user answers, disclosing that in the report.
- **Forget.** "Forget this" removes content; it does not supersede. Delete the entry and any superseded versions or examples carrying the same content, and drop pointers to them, leaving no tombstone, summary, or backup of what was removed. If the match is ambiguous, show the candidates and ask. Say that copies already sent to reviewers or included in earlier reports are not reachable from here.

## Writing

Only the lead writes the library. Reviewers never do, and their suggestions do not reach it. Re-read the file immediately before saving, merge your change into what is there now, keep entries you did not touch, and replace the file atomically from a temporary file in the same directory. There is no lock, so this narrows but does not eliminate the window between two concurrent leads.

Maintaining the library changes no product code, design, or config, so it is allowed in review-only mode. It grants no authority to change the app.

## Consulting before a review

Once the scope is known, re-read the library and build one snapshot of the relevant `confirmed` entries: `global` entries plus those matching the projects and surfaces in scope. Leave out tentative and superseded entries.

```text
Snapshot read <YYYY-MM-DD>, scope <project and surfaces>
PREF-001 | <preference> | <scope>
```

Send only that. Drop sources, examples, other projects' entries, and the library path, and remove anything sensitive from the wording. Every reviewer receives the identical snapshot in its brief. If an entry cannot be shared with one reviewer's provider, ask the user, or remove it for all reviewers and disclose that. Keep the snapshot fixed within a round. A preference learned mid-run applies from the next round and is recorded in the ledger.

## How preferences apply

A snapshot is context about this user, not a quality standard. Preferences rank below the current request and brief, brand rules and other stated constraints, and accessibility requirements. A preference that conflicts with any of these is reported as a conflict, and the other item stands. Preferences never change a rubric score, anchor, blocker, or the gate. Reviewers score from the rubric as usual and report alignment separately. A preference can shape how a recommendation is framed or implemented, and a recommendation that goes against one is presented as a tradeoff, but alignment does not set a finding's priority or count as score progress.
