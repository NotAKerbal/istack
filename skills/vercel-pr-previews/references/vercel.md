# Vercel: find, wait for, and open the exact-commit preview

Official docs: [Environments](https://vercel.com/docs/deployments/environments), [Vercel for GitHub](https://vercel.com/docs/git/vercel-for-github), [List deployments API](https://vercel.com/docs/rest-api/reference/endpoints/deployments/list-deployments), [`vercel list`](https://vercel.com/docs/cli/list), [`vercel inspect`](https://vercel.com/docs/cli/inspect), [`vercel deploy`](https://vercel.com/docs/cli/deploy).

## Resolve the target

- **Project and team.** Read `projectId` and `orgId` from `.vercel/project.json` in the app root, if it exists. Otherwise, find the project whose Git repository and Root Directory match the app root by using the Vercel MCP (`list_projects`/`get_project`; inspect the live tool schemas) or `vercel project inspect --non-interactive` from the app root. Stop if the result is `link_required` or does not match.
- **Monorepos.** Several projects can build the same SHA. Use only the project whose Root Directory contains the changed app. If more than one app changed, report each project separately.

## Match the deployment

A deployment counts only when all of these hold:

- Its project is the target project.
- It was built for preview. In the REST API that is `target: null` with no `customEnvironment` object; `production`, `staging`, and custom environments do not qualify.
- Its Git metadata matches the full head SHA (`meta.githubCommitSha`, or the GitLab or Bitbucket equivalent) and the PR branch (`meta.githubCommitRef`).

Server-side filters only narrow the list. Always check these conditions on each returned deployment yourself.

Ways to look it up, in order of preference:

- **Vercel MCP:** use `list_deployments` or `get_deployment`, and filter by project and SHA.
- **REST API:** `GET /v7/deployments?projectId=<id>&teamId=<team>&sha=<full sha>`. Do not pass a `target` filter for previews; preview deployments have `target: null`. Keep only results that meet every condition above.
- **CLI:** `vercel ls <project> --scope <team> --environment preview -m githubCommitSha=<sha>`, then `vercel inspect <url>`.

The Vercel check and GitHub deployment status on the PR head can confirm the result. A PR bot comment can be edited after a later push, so verify that its SHA matches before using its links.

Use the deployment's unique URL as the frontend link. Use `inspectorUrl` as the Inspect link. A branch alias (`*-git-<branch>-*`) always serves the newest build, so label it "latest branch preview", never "this commit".

## Waiting and stale links

- After a push there may be no deployment yet. Check every 15 to 30 seconds. Stop after about 15 minutes, or sooner if the project's recent builds are known to be faster. Then report `pending` with what you observed. Do not loop indefinitely.
- Final states are `READY`, `ERROR`, `CANCELED`, and `BLOCKED`. For `ERROR`, give a short build-log reason from `vercel inspect <url> --logs` or the MCP events, without copying secrets. A `CANCELED` deployment whose message says the project was not affected means the Ignored Build Step skipped this commit. Report it as `skipped`.
- If the head moves while you wait, restart from the new SHA, rewrite the Previews section, and stop reporting the old links as current.

## CLI fallback (rare)

Use a CLI deployment only when the Git integration cannot build this commit and the user wants a preview anyway. All of these must be true first:

- The app root is already linked to the verified project. Run `vercel project inspect --non-interactive`. Never pass `--yes`, because it accepts setup defaults and can link or create a project.
- The project already has a production deployment. Vercel documents that the first deployment of a new project is always a production deployment, even without `--prod`. If the project has never been deployed, report this and do not fall back.
- The working tree is clean at the PR head SHA. The CLI uploads local files, including uncommitted ones.

Then deploy with an explicit preview target and the branch metadata: `vercel deploy --cwd <app root> --target=preview --meta githubDeployment=1 --meta githubCommitRef=<branch>`. Confirm afterwards that the deployment's target and project are what you intended. Before using these flags, check `vercel --version` and `vercel deploy --help`.

## Protected previews

Vercel Authentication or SSO may protect a preview. Open it in a browser profile that is already signed in to Vercel. If the profile is not signed in, show the login page to the user and let them sign in themselves. Use `vercel curl` for authenticated HTTP checks. Do not disable protection, and do not create bypass secrets. Use an existing Protection Bypass for Automation only if the user has authorized it, and keep its value out of URLs that you show, store, or put in the PR.
