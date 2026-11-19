---
name: coworker-brief
description: >-
  Explain the current thread's work the way you would to a coworker who just
  stopped by your desk, covering what you are working on, why it matters, where
  it stands, and what you need from them. Use when the user asks for a coworker
  brief or a catch-up, such as "catch me up", "brief me", "what are you working
  on and why", or "remind me what this thread is about", to get back into a
  thread after working elsewhere. Not for a quick yes/no or single-fact status
  question. The brief itself takes no new action on the task.
---

# Coworker brief

The user works across many threads at once and calls this skill to get back into one fast. Write what you would say to a coworker who just walked up and asked, "What are you working on?" They should come away knowing what this thread is for, why it matters, where it stands, and whether they need to do anything, without scrolling back through the thread.

## Ground it in the actual state

Before writing, look at where things actually stand. Don't rely on what you remember planning.

- Reread the user's original request and any later changes to it, so the goal you describe is theirs, in their terms.
- Check cheap, read-only state when it applies: `git status` and recent commits, the branch and PR with its checks and review state, background tasks, and delegated agents. Do not run builds or test suites, poll for new results, or start anything just to write the brief.
- Separate what is done and verified from what is done but unverified, in progress, or only planned. Never describe a plan as finished work or an expected result as an observed one.
- Report each check you mention as Passed, Failed, Blocked, or Not run. For a check that ran, give the revision or state it ran against and the observed result in a few words, adding the environment or procedure when it isn't obvious. For Blocked or Not run, say what it would have covered and why it matters that it hasn't.
- If you are unsure about something, say what you don't know rather than guessing.

## Write it for a coworker

The reader is a smart colleague who knows the project in general but hasn't followed this thread. Write the way you would talk to them: plain sentences, first person, no log of what you did.

Start with the bottom line. The first sentence names the work and its purpose, for example: "I'm moving session storage to Redis so sign-ins survive a deploy." If the user has to decide or do something, say so in the next sentence, framed so they can reply in one line. Otherwise say plainly that nothing is needed from them.

Then cover the rest, in this order, saying each thing once and skipping any part with nothing to add:

1. **Why it matters.** The problem being solved, who it helps, or what it unblocks, in the user's terms, not the code's. Skip it if the opening sentence already made this clear.
2. **Where it stands.** What is done, what has been verified and how, and what is in progress. Name the moment the work is at, such as "implementation done, review pending" or "blocked on a failing migration".
3. **What's next.** The next step, and whether you will take it or are waiting on something.
4. **Risks or surprises.** Only if there is something the user would want to know before relying on the work: a scope change, a tradeoff you made, a known gap.

Finish with a short **Pointers** line or list for things the user may want to open: branch, PR link, key files as clickable paths, artifacts. Keep identifiers there instead of in the explanation.

## Keep it short

- Aim for 100 to 250 words, and go shorter when a short update covers it. A large or tangled thread can run longer, but the first two sentences must still stand on their own.
- Use short paragraphs or a few labeled lines. Skip headings for a short brief.
- Explain any term, ticket number, or internal name the coworker wouldn't already know, or leave it out.
- Leave out the chronology, tool calls, dead ends that no longer matter, and reassurance. Include a dead end only if it changed the plan.
- If the thread holds several pieces of work, lead with the one that needs the user, then the rest in a sentence each.

## Special cases

- **Nothing started yet.** Say what was asked, what you understood the goal to be, and what you need to begin.
- **Already finished.** Say what was delivered, how it was verified, and anything left open, such as an unmerged PR or a pending deploy.
- **Waiting on others.** Name who or what you are waiting on, such as a review delegate, CI, or the user, and what happens when it lands. Report a delegate's state from what you already know or one cheap status read, and don't wait for it to finish.
- **Scope changed.** If the work now differs from the original request, say so plainly and why.

## Stay in report mode

Writing the brief is the whole turn. Don't edit files, commit, start agents, or send anything outward while writing it, unless the user asked for that alongside the brief.

A brief is not a pause. It leaves the task's authorization and standing instructions in force, such as a review loop, a requested merge once checks pass, or watching a PR or delegate. When work you were already waiting on completes, carry on as you would have without the brief. Stop the task only if the user explicitly asks you to pause or stop.
