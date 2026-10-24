# Convex: integration check and preview backends

Read this before pushing to a PR in any Convex project, including frontend-only PRs.

Official docs: [Convex with Vercel](https://docs.convex.dev/production/hosting/vercel), [Preview deployments](https://docs.convex.dev/production/multiple-deployments), [CLI](https://docs.convex.dev/cli), [`convex.json`](https://docs.convex.dev/production/project-configuration).

CLI behavior can differ between versions. Check the project's pinned `convex` version, and use `npx convex deploy --help` from the Convex project root before relying on a flag.

## What has to be true

- **URL injection.** The frontend build must receive the preview deployment's URL in the variable the frontend actually reads, such as `NEXT_PUBLIC_CONVEX_URL` or `VITE_CONVEX_URL`. Find that variable in the code. `npx convex deploy --cmd '<framework build>'` resolves or creates the preview deployment, runs the build command with its URL in that variable, and pushes the functions after the command succeeds. Add `--cmd-url-env-var-name <VAR>` when Convex cannot infer the name. The frontend can therefore be built before the new functions are live. Treat the preview as ready only after the whole `convex deploy` and the Vercel deployment have both completed for this SHA; check `npx convex deploy --help` for the exact behavior of the pinned version.
- **Key isolation.** Vercel's **Preview** environment holds the project's *preview* deploy key as `CONVEX_DEPLOY_KEY`. Production holds only the production key. Do not read key values. Check scope and presence in the Vercel dashboard or the env listing, which does not reveal values.
- **Naming.** On Vercel, the preview takes its name from the Git branch. Check `npx convex deploy --help` before using naming flags such as `--preview-name` or `--preview-create`, because they decide whether a preview and its data are reused or recreated. Preview deployments expire; see the Convex docs for the current policy rather than promising a lifetime.
- **No production data.** Never seed a preview from production, and never import production data into it. `--preview-run <function>` may seed only fixture data that is already in the repo.

## Inspect the current integration (before pushing)

Check the effective Build Command: `vercel.json` or `vercel.ts` in the commit you will push, the `package.json` script it calls, and the Vercel project's Build Command setting (Vercel MCP `get_project`, `vercel project inspect`, or the dashboard) when the repo does not override it. Also find out which backend the Preview build's Convex URL variable points to. The URL itself is public, but read it without exposing other env values, for example from a recent Preview build log or the deployed client bundle; do not pull env files. Determine which of these applies:

1. **The build runs `convex deploy` on every Preview build.** A PR with Convex changes is covered by the Git deployment; find the preview's deployment URL in that deployment's build log. A frontend-only PR would also get a Convex preview deployment, which the user does not want. Do not push a frontend-only PR into this setup. Add the conditional setup below first if the task authorizes it; otherwise report it as the blocker.
2. **The build never deploys Convex.** Frontend-only PRs are fine. A PR with Convex changes gets a Git preview that runs against the existing backend, which lacks this PR's backend changes. Add the conditional setup if the task authorizes it; otherwise report the backend preview as blocked and list the missing pieces: a preview deploy key in Vercel Preview, and the conditional setup below. Still open the Vercel preview, clearly labeled as using the existing backend, and do not run tests that rely on the new backend.
3. **The build already deploys Convex conditionally.** Check that its decision uses an explicit PR base and head, then rely on it.
4. **A Convex Vercel Marketplace integration manages the env vars.** Read what it configures for Preview before assuming any case above.

If the existing backend for frontend-only PRs is production, say so, and keep the smoke test read-only.

## Conditional setup

Add this only when the current task authorizes build or provider setup. Adding or scoping the deploy key is a secret change; the user does it, or explicitly authorizes it for this task. This setup adds a versioned build wrapper to the user's repo, for example `"buildCommand": "sh scripts/vercel-build.sh"` in `vercel.json`. It runs `convex deploy` for a Preview build only when that PR changes Convex. Make the decision from an explicit base and head. Never infer it from `VERCEL_GIT_PREVIOUS_SHA`, which is the branch's previous deployment and not the PR base, or from a shallow checkout. If the base cannot be resolved, fail with a clear error. Do not assume "no changes".

```sh
# Pseudocode. Adapt the framework build command and URL variable to the project.
if [ "$VERCEL_ENV" != "preview" ]; then exec <existing production build>; fi  # production path unchanged
BASE_REF=<PR base branch: from the GitHub API using VERCEL_GIT_PULL_REQUEST_ID, or a configured base verified to be this PR's actual base>
git fetch --no-tags --depth=<enough> origin "$BASE_REF" "$VERCEL_GIT_COMMIT_SHA" || fail "cannot fetch PR base"
python3 convex_changes.py --base FETCH_HEAD-of-base --head "$VERCEL_GIT_COMMIT_SHA"  # or an equivalent check
case decision in
  convex-preview) require CONVEX_DEPLOY_KEY to be a preview key (without printing it)
                  # convex deploy runs the build with the preview URL, then pushes functions
                  exec npx convex deploy --cmd '<framework build>' --cmd-url-env-var-name <VAR> ;;
  existing-backend|not-applicable) exec <framework build> ;;  # uses the Preview env's existing Convex URL
  *) fail "Convex change check was inconclusive: <reason>" ;;  # includes "review"; a human decides
esac
```

Prerequisites to list for the user:

- Git fetch access to the base branch from the Vercel build.
- The preview deploy key, scoped to Preview only. The user adds it in the Vercel dashboard.
- An existing non-production Convex URL in Preview, for frontend-only PRs.
- Python, or a port of the check, available in the build image.

**Optional alternative.** A branch-scoped Preview env flag can force or skip the Convex deploy for one branch. Offer it only as an override, never as a manual step required on every PR.

## Links

- **API URL.** Take it from the `convex deploy` output in the Vercel build log, for example `https://<name>.convex.cloud`. Label it as the client endpoint.
- **Dashboard.** Use the link the CLI or integration printed. Otherwise, open the Convex project dashboard and select the branch's preview in the deployment switcher, then record the URL actually shown. Do not build a dashboard URL from the deployment name unless you have confirmed that it opens that preview.
