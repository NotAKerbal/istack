#!/usr/bin/env python3
"""Create or replace the marker-delimited Previews section of a PR description.

Reads the current body, replaces the section between the markers (or appends one), and writes the
new body. Text outside the markers is preserved byte for byte. The whole section is regenerated on
every call, so links from an earlier head never survive an update.

Exit codes: 0 = body written; 2 = invalid input or malformed markers (fix by hand; nothing written).
"""

import argparse
import re
import sys
from urllib.parse import parse_qsl, urlsplit

START = "<!-- pr-previews:start -->"
END = "<!-- pr-previews:end -->"
FRONTEND = {
    "ready": "Ready",
    "building": "Building, not ready yet",
    "queued": "Queued, not ready yet",
    "pending": "Pending: no deployment for this commit yet",
    "error": "Build failed",
    "canceled": "Canceled",
    "skipped": "Skipped by the project's build settings",
    "blocked": "Blocked",
}
SECRET_QUERY = re.compile(r"bypass|token|secret|key|auth|sig|password", re.IGNORECASE)


class InputError(Exception):
    pass


def checked_url(value, label):
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc:
        raise InputError(f"{label} must be an https URL")
    if parts.username or parts.password or any(SECRET_QUERY.search(k) for k, _ in parse_qsl(parts.query)):
        raise InputError(f"{label} looks like it carries a credential; use the plain deployment URL")
    return value


def one_line(text):
    return " ".join((text or "").split())


def link(url):
    return f"[{urlsplit(url).netloc}]({url})"


def render(args):
    if not re.fullmatch(r"[0-9a-f]{40}", args.head):
        raise InputError("--head must be the full 40-character commit SHA")
    frontend = checked_url(args.frontend_url, "--frontend-url")
    inspector = checked_url(args.inspector_url, "--inspector-url")
    dashboard = checked_url(args.convex_dashboard, "--convex-dashboard")
    api = checked_url(args.convex_api, "--convex-api")
    if args.frontend_status == "ready" and not frontend:
        raise InputError("--frontend-status ready requires --frontend-url")
    if args.convex != "preview" and (dashboard or api):
        raise InputError("Convex links belong only to --convex preview")

    status = FRONTEND[args.frontend_status]
    lines = [START, "## Previews", "",
             f"Commit `{args.head}`. This section is regenerated after each push; edits inside it are replaced.", ""]
    lines.append(f"- **Frontend (Vercel preview):** {link(frontend) + ' · ' if frontend else ''}{status}")
    if inspector:
        lines.append(f"- **Vercel deployment details:** [Inspect]({inspector})")
    if args.convex == "existing":
        lines.append("- **Convex:** no backend changes in this PR, so no Convex preview was created; "
                     "the frontend uses the existing configured backend")
    elif args.convex == "preview":
        # A discovered URL is not proof the backend is deployed and serving; only an explicit status says Ready.
        convex_status = one_line(args.convex_status) or "Pending"
        lines.append(f"- **Convex preview backend:** {f'[Dashboard]({dashboard}) · ' if dashboard else ''}{convex_status}")
        if api:
            lines.append(f"- **Convex API URL** (client endpoint, not a web page): {api}")
    if args.checked:
        lines.append(f"- **Checked:** {one_line(args.checked)}")
    lines.append(END)
    return "\n".join(lines)


def splice(body, section):
    starts, ends = body.count(START), body.count(END)
    if starts == ends == 0:
        stripped = body.rstrip("\n")
        return f"{stripped}\n\n{section}\n" if stripped else f"{section}\n"
    if starts != 1 or ends != 1 or body.index(START) > body.index(END):
        raise InputError("PR body has missing, duplicated, or out-of-order pr-previews markers")
    before, rest = body.split(START, 1)
    return before + section + rest.split(END, 1)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--body-file", required=True, help="current PR body ('-' for stdin)")
    parser.add_argument("--out", help="write the new body here instead of stdout")
    parser.add_argument("--head", required=True, help="full PR head SHA these results describe")
    parser.add_argument("--frontend-status", required=True, choices=sorted(FRONTEND))
    parser.add_argument("--frontend-url", help="preview URL of the deployment built from --head")
    parser.add_argument("--inspector-url", help="Vercel inspector URL of that deployment")
    parser.add_argument("--convex", choices=["none", "existing", "preview"], default="none",
                        help="none: no Convex project; existing: no backend changes; preview: Convex preview needed")
    parser.add_argument("--convex-status", help="verified state, e.g. 'Ready' or 'Pending: preview deploy key not "
                        "configured' (default Pending, even when URLs are given)")
    parser.add_argument("--convex-dashboard", help="discovered dashboard URL of the Convex preview deployment")
    parser.add_argument("--convex-api", help="Convex preview deployment URL (the client endpoint)")
    parser.add_argument("--checked", help="one-line, truthful smoke-test result for --head")
    args = parser.parse_args()
    try:
        body = sys.stdin.read() if args.body_file == "-" else open(args.body_file, encoding="utf-8").read()
        new_body = splice(body, render(args))
    except InputError as error:
        print(f"pr_previews_section: {error}", file=sys.stderr)
        sys.exit(2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(new_body)
    else:
        sys.stdout.write(new_body)


if __name__ == "__main__":
    main()
