---
name: vercel-pr-previews
description: When you create a pull request or push an update to one in a project deployed on Vercel. Before pushing, decide from the PR diff whether Convex backend changes need a Convex preview and check that the build will not deploy Convex for a frontend-only PR. After pushing, find the Vercel preview built from the exact head commit, open it visibly for the user, and keep a Previews section with current links in the PR description. Not for production deploys, promotion, or projects that are not on Vercel.
---

# Vercel PR previews

This is agent-selected guidance, not a hook. It applies only while it is installed and loaded and while you are the one creating or pushing to the PR. It does not watch PRs that others create.

Work from facts you discover. Do not guess URLs, deployment names, or which backend a build uses.

## Hard limits

- Do not deploy to production or promote anything. Never run `vercel --prod`, `vercel promote`, or `npx convex deploy` without a verified preview deploy key. Without `CONVEX_DEPLOY_KEY`, `convex deploy` targets the project's **production** deployment.
- Change provider or build setup only when the current task already authorizes that specific change, for example when the user asked you to set up Convex previews or to change the build. This covers the Vercel Build Command, `vercel.json` or `vercel.ts` build settings, build wrappers in the repo, and integration settings. Without that authorization, report the exact missing setup as a blocker and finish the work that does not depend on it.
- Billing, Deployment Protection, auth providers, environment variables, deploy keys, and other secrets need explicit authorization for that particular change, even when other setup is authorized. Do not link or create Vercel or Convex projects.
- Never print or store deploy keys, tokens, protection-bypass values, or env file contents. This includes chat, PR text, command lines, and logs. When a secret is needed, ask the user to enter it in the provider's dashboard, or use a private secret prompt such as T3 `request_secret` if the consuming tool accepts the returned reference. Never ask for a secret in chat.
- The only PR write this skill authorizes is the marker-delimited Previews section of the PR description. Do not post comments or other messages. Existing Vercel or Convex bot comments stay as they are.

## Workflow

Steps 1 to 4 happen before you push. If the push has already happened, do them right away and treat any unwanted deployment it caused as a finding to report.

1. **Applicability.** Look for Vercel signals: `.vercel/project.json`, `vercel.json` or `vercel.ts`, Vercel checks or deployments on the PR, or a Vercel MCP project linked to the repo. If there are none, stop silently.
2. **Identify the PR.** Record the PR URL (if it exists yet), base branch, head branch, and the full head SHA you are about to push. In a monorepo, find the app root that the Vercel project builds (Root Directory) and the project and team IDs. Read them from `.vercel/project.json`, the Vercel MCP, or `vercel project inspect`.
3. **Classify Convex changes.** Fetch the base branch. Then run `python3 <skill>/scripts/convex_changes.py --repo <repo> --base origin/<base> --head <sha>`. It diffs `merge-base..head`, which is the PR's own range, not just the latest commit or the working tree. It honors the `functions` path in `convex.json` and also counts shared modules and repository assets (such as JSON) that Convex functions import, `convex.json` changes, backend dependency bumps, and npm lockfile changes inside the backend packages' dependency tree. Frontend files that import `_generated/api` count as frontend. Exit 2 means a ref is missing; fetch it rather than assuming nothing changed. Act on the `decision` field:
   - `not-applicable`: there is no Convex project. Handle the PR as Vercel-only and skip step 4.
   - `existing-backend`: frontend-only. Do not create or deploy a Convex preview.
   - `convex-preview`: a Convex preview backend is needed.
   - `review`: the helper could not prove the change is frontend-only, for example because of a non-npm or workspace lockfile, a local package, an unresolved import alias, or a changed tsconfig that resolves backend imports. Inspect the listed items, then choose `existing-backend` or `convex-preview` and say why. If inspection cannot establish whether the backend changes, report the Convex decision as blocked rather than deploying speculatively.

   The result is advisory. The helper's import tracing is static and partial, so it does not replace looking at what the backend build actually consumes. If the diff touches anything else that feeds the Convex build (bundler or esbuild settings, env-dependent code paths, generated inputs), decide from that.
4. **Inspect the Convex integration before pushing.** For every Convex project, whatever the decision, read [references/convex.md](references/convex.md) and determine whether the Preview build deploys Convex always, never, or conditionally, and which backend the Preview build's Convex URL variable points to. Then apply this gate:
   - The build deploys Convex on every Preview build and the decision is `existing-backend`: pushing would create an unwanted Convex deployment. Do not push yet. If the task authorizes the setup, add the conditional setup from the reference first, so the commit you push already contains it. Otherwise stop and report the blocker and the exact setup needed. Push without it only if the user explicitly accepts the unconditional deploy for this push, and still report the requirement as unmet.
   - The decision is `convex-preview` and the build never deploys Convex: pushing is safe, but the preview will run against the existing backend. Add the setup if the task authorizes it. Otherwise report the backend preview as blocked on that setup.
   - You cannot see the effective Build Command (for example, it lives only in the Vercel dashboard and you have no access): say so, push, and check the build log in step 6. If it deployed Convex for a frontend-only PR, report that as a blocker, not as success.
   - Never report the Convex part as done while the provider still deploys Convex on every push.
5. **Push, then write a pending section right away.** After each push, record the new full head SHA and immediately update the PR description with a pending Previews section for that SHA, as described in [Previews section](#previews-section). This removes links from the previous head before you start waiting. Create the PR first if it does not exist.
6. **Find the preview deployment.** Reuse the deployment that the Vercel Git integration built. Do not start a CLI build of your own. Match it on project, preview environment, and exact head SHA. Wait in bounded intervals until it reaches a final state, and treat links for any other SHA as stale. Refresh the Previews section whenever the state or a link changes, and again when the wait ends, whether it is ready, failed, or still pending. See [references/vercel.md](references/vercel.md), which also covers the narrow CLI fallback and protected previews. For a Convex project, read the build log to confirm whether this build deployed Convex and which backend URL it used.
7. **Open it visibly.** See [Browser](#browser).
8. **Report.** Give the user clickable frontend and Inspect links. Add the Convex dashboard and API links only when the PR has Convex changes. Also report the exact head SHA, each status, any blockers, and what you actually checked.

## Previews section

Fetch the current body with `gh pr view <pr> --json body -q .body`, or with the GitHub connector. Write it to a temporary file and pipe it through the helper. Pass `--head <full sha>` and `--frontend-status`, plus only the URLs you discovered for that SHA. Right after a push, run it with `--frontend-status pending` and no URLs. Use `--convex existing` for a frontend-only PR in a Convex project. Use `--convex preview` when the PR has Convex changes, with `--convex-dashboard` and `--convex-api` once you discover them. The Convex status defaults to `Pending`, even when URLs are given; pass `--convex-status Ready` only after the build log shows the Convex deploy finished for this SHA, or pass `--convex-status "Pending: <reason>"` or `"Blocked: <reason>"`. Add `--checked "<one-line result>"` after a smoke test. Then apply the result with `gh pr edit <pr> --body-file <new>`, or a connected GitHub tool that can update the PR body. If neither is available, report that publishing the section is blocked and provide the prepared section.

The helper changes only the text between its markers and regenerates the whole section on each run. It rejects URLs that carry credential-like query values. If the markers are malformed, it writes nothing; tell the user instead of hand-editing. If the body changed between your read and your write, read it again and repeat.

## Browser

When the T3 tools are present, call `preview_status` first and read its current schema, tabs, owners, and profiles. Do not assume argument names. Open the preview with `preview_open` and `open: true`. Use a new tab (`reuseExistingTab: false`) unless one of your own tabs is already on this preview. Never take over a tab that a human is controlling. Pick a browser profile that is already signed in to Vercel when the preview is protected. Then use `preview_snapshot`, and set `save: true` when a screenshot helps the user. Without T3, use any visible browser tool that is available. If no browser tool is available, report the link.

Open the Convex dashboard only for a PR with Convex changes, and only at a preview dashboard URL you actually discovered. The `*.convex.cloud` API URL is a client endpoint, not a UI.

## Smoke test

Run only harmless interactions, such as navigation, reading pages, and opening non-mutating UI. Run them only after you verify which backend the build uses. Never write data while the frontend points at production. Do not seed or import production data into a preview. Report exactly what you saw. A Vercel login wall, an app sign-in page, or a blank shell is not a working app. Say "reached the login page" rather than "the app works".
