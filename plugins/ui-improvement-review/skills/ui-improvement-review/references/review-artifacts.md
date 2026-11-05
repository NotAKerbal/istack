# Review artifacts

Adapt these formats to the run; keep every field unless it truly does not apply.

## Reviewer brief

```text
You are an independent UI reviewer. Work read-only and do not change anything.

Lens: <task flow and UX | visual system | accessibility and resilience>
Product, audience, primary tasks: <...>
Revision: <exact revision or build>
Constraints to respect: <...>
Evidence bundle: <paths or links, with IDs>
Benchmark bundle: <paths or links, with IDs, or "none: gap disclosed">
Known evidence gaps: <...>
Rubric: <path to rubric.md>

Open the evidence yourself. Score every applicable rubric category, not just your
lens, using only evidence you opened. Use N/A or unknown where the rubric says to;
a missing score is more useful than a guessed one. There is no desired result.
Return the reviewer format below.
```

Do not include the target, earlier scores, other reviewers' output, or a list of changes.

## Reviewer return

```text
Reviewer: <model as reported by the tool> / <lens>
Revision reviewed: <...>
Evidence opened: <IDs>; could not open: <IDs or none>

Category | Score, N/A, or unknown | Confidence | Evidence | Gap
...

Blockers: <none, or each with evidence>
Findings: <in the finding format>
Peer observations: <evidence ID, technique or taste, relevance>
```

## Finding

```text
ID and priority: F3, P1
Category: <rubric category>
Location: <screen, state, viewport>
Evidence: <IDs>
User impact: <what goes wrong, for whom, how often>
Proposed change: <specific enough to implement>
Verification: <observable check that shows it worked>
Tradeoffs: <costs, risks, effect on constraints or identity>
Raised by / dissent: <reviewers, and any who disagree and why>
```

Priorities: **P0** open blocker. **P1** materially harms a primary task or access. **P2** repeated friction or a moderate secondary-path issue. **P3** minor refinement or polish.

## Benchmark record

```text
Peer and URL: <...>    Accessed: <date>    Evidence: <IDs>
Flow and state: <what was actually viewed>; access limits: <...>
Observable technique: <what it does, as seen>
Taste: <preference, labeled as such>
Applies here? <yes, no, or partly, and what would not transfer>
```

List any peer or flow that could not be accessed, and why.

## Round ledger

Round 0 is the frozen baseline. Add one row per round. Do not rewrite earlier rows.

| Round | Revision | Evidence | Council (model / lens) | Below target (lowest score) | Open blockers | Unknowns | Gate | Changes since last round |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Final report

1. **Verdict.** Gate state, target, revision, and council, including any agreed reduction. Example: "Not met at abc123: target 9, lowest scores Typography 7 and States 6, one open blocker."
2. **Score matrix.** Categories by reviewers, with confidence and a lowest-score column. Any mean is informational only.
3. **Blockers and prioritized findings.**
4. **Benchmark summary,** with sources, dates, and gaps.
5. **Dissent and unresolved tradeoffs,** stated without being averaged away.
6. **Round ledger and stop reason** (improve mode).
7. **Status by stage,** each as Passed, Failed, Blocked, or Not run: implementation, independent review, automated checks, and runtime verification.
8. **Gaps.** Unavailable models or tools, uncaptured states, and estimates used instead of measurements.
