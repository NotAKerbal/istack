---
name: ui-simplify
description: >-
  Isaac's defaults for lean UI: no extra text, duplicate information, or
  decorative chrome. Use when building, changing, redesigning, or mocking up
  app or web UI, including screens, components, settings, dashboards, and
  artifact pages, and when asked to simplify, declutter, or condense a UI or to
  "remove the extra text". Not for code-only cleanup (simplify), scored
  multi-model design reviews, or remembering UI preferences
  (ui-improvement-review handles both).
---

# UI simplify

Isaac's most frequent UI feedback is that agents add too much: titles that repeat the header, explainer and disclaimer copy, duplicate information, dividers, nested cards, and decorative chips. Isaac then removes them one request at a time. Build lean from the start, so a first version already looks like the result of a cleanup.

Keep an element only if a user would miss it.

## Defaults

**Text**

- No visible title that repeats the header, tab, or nav. Keep an accessible page heading, visually hidden if needed.
- No subtitles, taglines, or one-line descriptions under headings.
- No intro blurbs, tips, keyboard hints, or "how this works" paragraphs. Optional explanations go in the docs and behind an info button that works by hover, keyboard, and tap. Instructions people need in order to act stay visible, in one short line.
- No reassurance microcopy ("no account needed", "your feedback helps shape the app"), no marketing inside the product, and no notes about how it was made (read time, model names, "generated with AI").
- Labels are one or two words. A familiar toggle can be an icon with an accessible name.

**Say it once.** Show each fact in one place. Merge stacked headers and toolbars into one row. Don't pair a dot with a highlight that already marks the selection, or put a screen title on its own row under a back button.

**Chrome**

- Few horizontal dividers. Use spacing, alignment, or a table or column layout instead.
- One level of container. No card inside a card.
- No decorative chips, badges, pills, play buttons, mascots, or icons that don't do anything.
- No banners for routine state. Put a small action beside what it affects, such as an Update button on the item that needs it, plus Update all. T3 Code is Isaac's reference for this kind of management UI.
- Status earns its space only if it says something a user can act on. A bare green dot or a header "Connected" chip doesn't.
- Save quietly, or confirm next to the changed setting. Follow the system theme rather than adding a toggle.

**Layout**

- Keep primary content and the main action above the fold, on phones too.
- Put search and page controls in the existing header instead of new bars, rows, or floating buttons.
- Merge related panels, and reuse an existing button rather than adding a parallel one.
- Use progressive disclosure. Collapse secondary or long reference content, offer "Add method" instead of listing every option, and hide controls that don't matter on a platform.
- Settings, theme, and accounts live in a settings screen, not the sidebar.
- List items show only the fields people scan for.

## What stays

- Anything the current request asks for. These are defaults, not overrides.
- Information people need to proceed or avoid a mistake, such as a required step or a warning about a lasting side effect.
- Real limits on storage, access, or sharing. Keep such a notice to one short line, or fix the limitation itself when that is part of the task.
- Accessible names, focus indicators, form labels, error messages, and loading feedback that assistive tech can perceive.
- Required legal or brand notices, as small as the requirement allows.
- Functionality. Isaac's words: "simplify the UI without removing functionality." Hide, collapse, or move a feature rather than drop it.

Lean doesn't mean cramped. Don't shrink tap targets or squeeze spacing to show less.

## When asked to simplify

1. **Treat the example as a category.** If Isaac points at one blurb, chip, or divider, fix every element of that kind on the screens or flow in question, and sweep the whole app only when asked ("all over the place"). On a partial pass, Isaac said: "The goal was no extra text and there was extra text on all of them."
2. **Cover every variant in scope,** across platforms, device types, themes, breakpoints, and empty, loading, and error states. When the fix touches a shared component, leave its uses outside the requested scope unchanged.
3. **Remove rather than relocate.** A tooltip or docs page is for text that is still needed. Don't recreate removed text elsewhere on screen.
4. **Ask before deleting features or data.** Removing the markup, styles, and strings behind in-scope clutter is part of the job. Removing a feature, its underlying implementation, or data needs Isaac's explicit go-ahead, even when it looks obsolete, unreachable, legacy, or fake. Name the candidates in one line rather than deleting them or expanding the task.
5. **Do the simplification first,** before setup, unrelated polish, or a redesign nobody asked for.
6. **Update tests** that asserted removed copy so they check behavior instead.
7. **Check the running UI** as the shared workflow requires, looking for what is left rather than confirming what you removed.

When you build mockups or options, each one follows these defaults. Vary layout and style, not the amount of clutter.

When unsure whether a decorative or explanatory element earns its place, leave it out and mention it in one line of your reply. This never applies to anything under What stays.

For before-and-after examples from Isaac's requests, see [references/examples.md](references/examples.md).
