# UI scoring rubric

Give this file to every reviewer unchanged. Score against the anchors, not against earlier rounds, the effort spent, or the size of a change.

## Score anchors

Use whole numbers. If torn between two, choose the lower and say what would raise it.

| Score | Meaning |
| --- | --- |
| 10 | Reference quality. No material finding across all relevant states, and clearly ahead of strong peers on this flow. Rare and never promised. |
| 9 | Excellent. Verified across relevant states, with only minor issues that do not affect task outcome. At least matches strong peers where benchmark evidence exists. |
| 8 | Strong. Works well, with a few noticeable minor issues or one moderate issue on a secondary path. |
| 7 | Good. Competent, but moderate issues cause hesitation or inconsistency without causing failure. |
| 5-6 | Mixed. Repeated friction, or parts that work well alongside parts that clearly do not. |
| 3-4 | Poor. Primary tasks are often impaired, or an open blocker exists. |
| 1-2 | Broken. This category prevents use. |

## Every entry

- **Score** from 1 to 10, or `N/A`, or `unknown`.
- **Evidence** IDs. A score with no cited evidence is `unknown`.
- **Confidence.** *High*: direct evidence across relevant states. *Medium*: direct but partial evidence. *Low*: inferred or thin evidence.
- **Gap.** For any score below 10, name what is missing.

`N/A` means the category does not exist in scope, and it needs a stated reason. If reviewers disagree, the category is applicable. `unknown` means the category applies but the evidence cannot support a score. Never turn `unknown` into a number by estimating or by averaging other reviewers.

## Categories

Checks say what to look at. Not all apply to every product; judge against the product's platform and purpose.

| Category | Observable checks |
| --- | --- |
| Task flow and information architecture | Steps to finish primary tasks; whether the next action is evident; users can tell where they are; dead ends; reversibility of risky actions. |
| Visual hierarchy | A clear focal point and primary action per view; grouping that reflects importance; scan order matches task order. |
| Layout and spacing | Consistent spacing scale; shared alignment; density suited to the job; no collisions or unintended clipping. |
| Typography | Restrained type scale; readable size, line height, and line length; weight and size carry hierarchy; deliberate truncation; aligned numerals in data. |
| Iconography and imagery | One coherent icon family, stroke, and optical size; meaning recognizable or labeled; crisp at rendered size; imagery serves a purpose. |
| Color and contrast | Text, UI, and graphics contrast (see Accessibility standards); consistent semantic color; meaning not carried by color alone; parity across themes. |
| Components and consistency | Same things look and behave the same; patterns fit platform conventions; no near-duplicate controls. |
| States and feedback | Every action is acknowledged; useful empty, loading, error, and success states; errors explain recovery; state is never misleading. |
| Accessibility | Complete keyboard path with visible focus and logical order; correct names and roles; target size and spacing suit the input method (see Accessibility standards); respects reduced motion; usable at 200% zoom. |
| Responsive and adaptive behavior | Reflow at supported sizes (see Accessibility standards); good use of wide screens; touch and pointer both work; long content and translated strings hold up. |
| Content and microcopy | Labels name outcomes; terminology is consistent; plain language suited to the audience; helpful error and empty copy. |
| Motion and perceived performance | Immediate response to input; little layout shift; progress shown during waits; motion clarifies rather than decorates. Cite timings only if measured. |

## Accessibility standards

This rubric is not a full accessibility certification. Before claiming a WCAG AA failure or applying a contrast blocker or AA cap, confirm the WCAG version and level the product targets (or state the one assumed), that the criterion applies, and that no exception covers the element. If any of these does not hold, score the issue by user impact without claiming a failure.

| WCAG 2.2 AA criterion | Requirement | Exceptions |
| --- | --- | --- |
| [1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | Text 4.5:1; large text (at least 18 pt, or 14 pt bold) 3:1. | Inactive components, incidental or decorative text, logos. |
| [1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) | 3:1 for visual information needed to identify components and states, and for meaningful graphics. | Inactive components, unmodified user agent appearance, essential presentation. |
| [2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | Pointer targets 24 by 24 CSS px. | Sufficient spacing, an equivalent compliant control, inline targets, unmodified user agent controls, essential or legally required presentation. |
| [1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | No two-dimensional scrolling or lost content or function at 320 CSS px wide (vertical scrolling content) or 256 CSS px high (horizontal scrolling content). | Parts that need two-dimensional layout for use or meaning, such as data tables or maps. |

Platform touch guidance, such as Apple's or Android's, is a heuristic and not a WCAG requirement. Cite its current source; missing it is a usability finding, not an AA failure.

Source: W3C Understanding WCAG 2.2, checked 2026-11-04.

## Blockers

A blocker closes the gate regardless of any score and caps its category at 4. Blockers are:

- A primary task cannot be completed in a supported configuration.
- Data loss or an irreversible action occurs without adequate warning.
- The UI reports a false state, such as showing success after failure.
- Essential text or controls are unreadable, hidden, or overlapped at a supported viewport.
- Essential text measurably fails the applicable contrast minimum above.
- A primary task is unreachable by keyboard or assistive technology where the product must support them.

## Score limits

- A measured WCAG AA failure, confirmed under Accessibility standards, on an in-scope element that is not a blocker caps its category at 7.
- A 9 or 10 must cite the default state and the relevant non-default states.
- States and feedback, Accessibility, Responsive and adaptive behavior, and Motion and perceived performance need evidence of the behavior itself. From a single static screenshot they are `unknown`.
- A contrast or size figure must come from a measurement. Otherwise label it an estimate, which cannot establish a blocker or a cap and gives at most medium confidence.
