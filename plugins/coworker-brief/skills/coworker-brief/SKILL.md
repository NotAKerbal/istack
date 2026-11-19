---
name: coworker-brief
description: Pause and explain the current thread's work the way you would to a coworker who just stopped by your desk, covering what you are working on, why it matters, where it stands, and what you need from them. Use when the user asks for a coworker brief, a catch-up, a status check, "what are you working on", "where are we", "remind me what this is", or otherwise wants to get back into a thread quickly after working elsewhere. Report only: it takes no new action on the task.
---

# Coworker brief

The user works across many threads at once and calls this skill to get back into one fast. Write what you would say to a coworker who just walked up and asked, "What are you working on?" They should come away knowing what this thread is for, why it matters, where it stands, and whether they need to do anything, without scrolling back through the thread.

## Ground it in the actual state

Before writing, look at where things actually stand. Don't rely on what you remember planning.

- Reread the user's original request and any later changes to it, so the goal you describe is theirs, in their terms.
- Check cheap, read-only state when it applies: `git status` and recent commits, the branch and PR with its checks and review state, background tasks, and delegated agents. Do not run builds or test suites, poll for new results, or start anything just to write the brief.
- Separate what is done and verified from what is done but unverified, in progress, or only planned. Report each check you mention as Passed, Failed, Blocked, or Not run, at the revision it ran on. Never describe a plan as finished work or an expected result as an observed one.
- If you are unsure about something, say what you don't know rather than guessing.

## Write it for a coworker

The reader is a smart colleague who knows the project in general but hasn't followed this thread. Write the way you would talk to them: plain sentences, first person, no log of what you did.

Start with the bottom line. The first sentence names the work and its purpose, for example: "I'm moving session storage to Redis so sign-ins survive a deploy." If the user has to decide or do something, say so in the next sentence, not at the end.

Then cover, in this order and only as far as each matters:

1. **Why it matters.** The problem being solved, who it helps, or what it unblocks. One or two sentences in the user's terms, not the code's.
2. **Where it stands.** What is done, what has been verified and how, and what is in progress. Name the moment the work is at, such as "implementation done, review pending" or "blocked on a failing migration".
3. **What's next.** The next step, and whether you will take it or are waiting on something.
4. **What I need from you.** A decision, an approval, access, or an answer, framed so the user can reply in one line. If nothing is needed, say "Nothing yet. I'll keep going when you say so." or whatever is true.
5. **Risks or surprises.** Only if there is something the user would want to know before relying on the work: a scope change, a tradeoff you made, a known gap.

Finish with a short **Pointers** line or list for things the user may want to open: branch, PR link, key files as clickable paths, artifacts. Keep identifiers there instead of in the explanation.

## Keep it short

- Aim for 100 to 250 words. A large or tangled thread can run longer, but the first two sentences must still stand on their own.
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

The brief is the whole response. Don't continue the task, edit files, commit, start agents, or send anything outward in the same turn, unless the user asked for that alongside the brief. Afterward, resume the work only when the user says to.
