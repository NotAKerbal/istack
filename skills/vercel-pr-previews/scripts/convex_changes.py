#!/usr/bin/env python3
"""Decide whether a PR's committed changes need a Convex preview backend.

Compares merge-base(base, head)..head, the same range a GitHub PR shows, and prints JSON.
Uncommitted changes are not part of the PR and are ignored (a warning is emitted).

The result is advisory. Import tracing is static and partial: it follows relative and simple
tsconfig-alias imports, records directly imported repository assets (such as JSON), and walks
npm lockfile v2/v3 dependency trees. Anything it cannot prove frontend-only (other lockfile
formats, workspaces, local packages, unresolved aliases, alias tsconfig changes) yields "review".

Exit codes: 0 = result printed; 2 = a ref or merge-base could not be resolved (fetch it; do not
assume "no changes").
"""

import argparse
import json
import posixpath
import re
import subprocess
import sys

SOURCE_EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
NPM_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")
LOCKFILES = NPM_LOCKFILES + ("pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb")
DEP_FIELDS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
LOCK_EDGE_FIELDS = ("dependencies", "optionalDependencies", "peerDependencies")
LOCAL_SPEC_PREFIXES = ("workspace:", "file:", "link:", "portal:")
IMPORT_RE = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|\brequire\s*\(\s*|\bexport\s+\*\s+from\s*)["']([^"'\n]+)["']"""
)


class GitError(Exception):
    pass


class Repo:
    def __init__(self, path):
        self.path = path
        self._cache = {}

    def git(self, *args, check=True):
        result = subprocess.run(["git", "-C", self.path, *args], capture_output=True, text=True)
        if check and result.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout

    def commit(self, ref):
        result = subprocess.run(
            ["git", "-C", self.path, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise GitError(f"ref not found locally: {ref} (fetch it first)")
        return result.stdout.strip()

    def files(self, rev):
        return set(self.git("ls-tree", "-r", "--name-only", rev).splitlines())

    def read(self, rev, path):
        key = (rev, path)
        if key not in self._cache:
            result = subprocess.run(["git", "-C", self.path, "show", f"{rev}:{path}"], capture_output=True)
            self._cache[key] = result.stdout.decode("utf-8", "replace") if result.returncode == 0 else None
        return self._cache[key]

    def json(self, rev, path):
        text = self.read(rev, path)
        if text is None:
            return None
        try:
            return json.loads(strip_jsonc(text))
        except ValueError:
            return None


def strip_jsonc(text):
    """Remove // and /* */ comments and trailing commas outside strings (tsconfig is JSONC)."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def under(path, directory):
    return directory in ("", ".") or path == directory or path.startswith(directory.rstrip("/") + "/")


def join(*parts):
    path = posixpath.normpath(posixpath.join(*[p for p in parts if p not in ("", ".")] or ["."]))
    return "" if path == "." else path


def package_name(specifier):
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") and len(parts) > 1 else parts[0]


def find_projects(repo, revs):
    """Convex projects: a dir with convex.json, or a package.json depending on convex, whose functions dir has files."""
    projects = {}
    for rev in revs:
        files = repo.files(rev)
        for path in files:
            if "node_modules/" in path or posixpath.basename(path) not in ("package.json", "convex.json"):
                continue
            root = posixpath.dirname(path)
            if posixpath.basename(path) == "package.json":
                pkg = repo.json(rev, path) or {}
                if not any("convex" in (pkg.get(field) or {}) for field in DEP_FIELDS):
                    continue
            config = repo.json(rev, join(root, "convex.json")) or {}
            functions = join(root, str(config.get("functions") or "convex"))
            if any(under(f, functions) for f in files):
                project = projects.setdefault(root, {"root": root or ".", "functionsDirs": set()})
                project["functionsDirs"].add(functions)
    return projects


def tsconfig_aliases(repo, rev, dirs):
    aliases = []
    for directory in dirs:
        path = join(directory, "tsconfig.json")
        options = (repo.json(rev, path) or {}).get("compilerOptions") or {}
        base = join(directory, options.get("baseUrl") or ".")
        for pattern, targets in (options.get("paths") or {}).items():
            aliases.append((pattern, [join(base, t) for t in targets if isinstance(t, str)]))
    return aliases


def resolve(path, files):
    stem = path[: -len(posixpath.splitext(path)[1])] if path.endswith((".js", ".jsx", ".mjs", ".cjs")) else path
    candidates = [path] + [stem + ext for ext in SOURCE_EXTS] + [join(path, "index" + ext) for ext in SOURCE_EXTS]
    return next((c for c in candidates if c in files), None)


def backend_graph(repo, rev, functions_dirs, alias_dirs, dep_names):
    """Files reachable from Convex functions via relative or tsconfig-alias imports, plus bare packages imported.

    Imported non-source files (JSON and other assets) count as reachable but are not scanned for imports.
    """
    files = repo.files(rev)
    aliases = tsconfig_aliases(repo, rev, alias_dirs)
    queue = [f for f in files if any(under(f, d) for d in functions_dirs) and f.endswith(SOURCE_EXTS)
             and "/_generated/" not in f]
    seen, packages, unresolved = set(queue), set(), set()
    while queue:
        current = queue.pop()
        for spec in IMPORT_RE.findall(repo.read(rev, current) or ""):
            if spec.startswith("node:"):
                continue
            targets = []
            if spec.startswith((".", "/")):
                targets = [join(posixpath.dirname(current), spec)]
            else:
                for pattern, mapped in aliases:
                    prefix = pattern.rstrip("*")
                    if (pattern.endswith("*") and spec.startswith(prefix)) or spec == pattern:
                        rest = spec[len(prefix):] if pattern.endswith("*") else ""
                        targets = [t.replace("*", rest) for t in mapped]
                        break
                if not targets:
                    name = package_name(spec)
                    if name in dep_names or not spec.startswith(("@/", "~/", "#", "src/")):
                        packages.add(name)
                    else:
                        unresolved.add(spec)
                    continue
            found = next((r for r in (resolve(t, files) for t in targets) if r), None)
            if found is None:
                if not spec.startswith((".", "/")):
                    unresolved.add(spec)
                continue
            if found not in seen:
                seen.add(found)
                if found.endswith(SOURCE_EXTS):
                    queue.append(found)
    return seen, packages, unresolved


def dep_versions(repo, rev, path, names):
    pkg = repo.json(rev, path) or {}
    return {n: next((pkg[f][n] for f in DEP_FIELDS if n in (pkg.get(f) or {})), None) for n in names}


class Unsupported(Exception):
    pass


def lock_packages(repo, rev, path):
    """The "packages" map of an npm v2/v3 lockfile without workspaces; {} if the file is absent at rev."""
    if repo.read(rev, path) is None:
        return {}
    lock = repo.json(rev, path)
    if not isinstance(lock, dict) or not isinstance(lock.get("packages"), dict):
        raise Unsupported("not an npm lockfile v2/v3 with a packages map")
    packages = lock["packages"]
    for key, entry in packages.items():
        if key and (not key.startswith("node_modules/") or (entry or {}).get("link")):
            raise Unsupported("uses workspaces or linked packages")
    return packages


def lock_resolve(packages, parent, name):
    """Node-style lookup: the nearest node_modules/<name> at or above the parent package's location."""
    base = parent
    while True:
        candidate = f"{base}/node_modules/{name}" if base else f"node_modules/{name}"
        if candidate in packages:
            return candidate
        if not base:
            return None
        cut = base.rfind("/node_modules/")
        base = base[:cut] if cut >= 0 else ""


def lock_closure(packages, names):
    """Lockfile entries the named packages resolve to, plus everything they depend on transitively."""
    seen, stack = set(), [("", n) for n in names]
    while stack:
        parent, name = stack.pop()
        key = lock_resolve(packages, parent, name)
        if key is None or key in seen:
            continue
        seen.add(key)
        for field in LOCK_EDGE_FIELDS:
            stack.extend((key, dep) for dep in (packages[key].get(field) or {}))
    return seen


def lock_backend_changes(repo, merge_base, head, path, names):
    """Changed lockfile entries inside the backend packages' dependency closure (raises Unsupported)."""
    before, after = lock_packages(repo, merge_base, path), lock_packages(repo, head, path)
    changed = {k for k in set(before) | set(after) if k and before.get(k) != after.get(k)}
    closure = lock_closure(before, names) | lock_closure(after, names)
    return sorted(k[len("node_modules/"):] for k in changed & closure)


def analyze(repo_path, base_ref, head_ref):
    repo = Repo(repo_path)
    head = repo.commit(head_ref)
    base = repo.commit(base_ref)
    merge_base = repo.git("merge-base", base, head, check=False).strip()
    if not merge_base:
        raise GitError(f"no merge-base between {base_ref} and {head_ref}; fetch full history for both")

    changed = set()
    for line in repo.git("diff", "--name-status", "-M", merge_base, head).splitlines():
        changed.update(line.split("\t")[1:])

    warnings = []
    if head_ref == "HEAD" and repo.git("status", "--porcelain", check=False).strip():
        warnings.append("working tree has uncommitted changes; they are not part of the PR and were not analyzed")

    projects = find_projects(repo, [merge_base, head])
    result = {"head": head, "base": base, "mergeBase": merge_base, "changedFiles": len(changed),
              "warnings": warnings, "projects": []}
    if not projects:
        result["decision"] = "not-applicable"
        result["reason"] = "no Convex project found at merge-base or head"
        return result

    claimed = set()
    for root, project in sorted(projects.items()):
        functions_dirs = sorted(project["functionsDirs"])
        root_pkg = join(root, "package.json")
        dep_names = set()
        for rev in (merge_base, head):
            for path in {root_pkg, "package.json"}:
                pkg = repo.json(rev, path) or {}
                for field in DEP_FIELDS:
                    dep_names.update((pkg.get(field) or {}).keys())
        alias_dirs = sorted({root} | set(functions_dirs))
        alias_configs = {join(d, "tsconfig.json") for d in alias_dirs}
        reachable, imported, packages, unresolved = set(), set(), {"convex"}, set()
        for rev in (merge_base, head):
            r, p, u = backend_graph(repo, rev, functions_dirs, alias_dirs, dep_names)
            reachable |= r
            imported |= p
            packages |= {n for n in p if n in dep_names or n == "convex"}
            unresolved |= u
        packages |= {n for n in dep_names if n.startswith("@convex-dev/")}
        for rev in (merge_base, head):
            for name, spec in dep_versions(repo, rev, root_pkg, packages).items():
                if isinstance(spec, str) and spec.startswith(LOCAL_SPEC_PREFIXES):
                    unresolved.add(f"{name} (local package {spec}; its files are not traced)")

        entry = {"root": project["root"], "functionsDirs": functions_dirs, "backend": [], "config": [],
                 "generated": [], "review": [], "unresolvedImports": sorted(unresolved)}
        for path in sorted(changed):
            if any(under(path, d) for d in functions_dirs):
                (entry["generated"] if "/_generated/" in f"/{path}" else entry["backend"]).append(path)
            elif path == join(root, "convex.json"):
                entry["config"].append(path)
            elif path in reachable:
                entry["backend"].append(path + " (imported by Convex functions)")
            elif path in alias_configs:
                entry["review"].append(f"{path} (tsconfig used to resolve Convex imports changed; "
                                       "check paths/baseUrl and any backend build settings)")
            elif path in (root_pkg, "package.json"):
                before = dep_versions(repo, merge_base, path, packages)
                after = dep_versions(repo, head, path, packages)
                bumped = sorted(n for n in packages if before[n] != after[n])
                if bumped:
                    entry["config"].append(f"{path} (backend dependencies: {', '.join(bumped)})")
                else:
                    continue
            elif posixpath.basename(path) in LOCKFILES and (under(path, root) or posixpath.dirname(path) == ""):
                names = sorted(packages | imported)
                if posixpath.basename(path) in NPM_LOCKFILES and posixpath.dirname(path) == root:
                    try:
                        bumped = lock_backend_changes(repo, merge_base, head, path, names)
                    except Unsupported as error:
                        entry["review"].append(f"{path} ({error}; cannot prove the change is frontend-only; "
                                               f"check the dependency trees of: {', '.join(names)})")
                        claimed.add(path)
                        continue
                    if bumped:
                        entry["config"].append(f"{path} (backend dependency tree: {', '.join(bumped)})")
                    else:
                        continue
                else:
                    entry["review"].append(f"{path} (lockfile format or location not analyzed; cannot prove the "
                                           f"change is frontend-only; check the dependency trees of: {', '.join(names)})")
            else:
                continue
            claimed.add(path)
        if entry["generated"] and not entry["backend"]:
            entry["review"].append("only Convex _generated files changed; check whether functions or the CLI version changed")
        other_sources = [p for p in changed if p not in claimed and p.endswith(SOURCE_EXTS + (".json",))]
        if unresolved and other_sources:
            entry["review"].append("Convex functions use imports this helper could not resolve; "
                                   "check whether any changed non-Convex source file is imported by them")
        result["projects"].append(entry)

    if any(p["backend"] or p["config"] for p in result["projects"]):
        result["decision"] = "convex-preview"
        result["reason"] = "PR changes Convex functions, configuration, or backend dependencies"
    elif any(p["review"] for p in result["projects"]):
        result["decision"] = "review"
        result["reason"] = "inspect the listed items before deciding"
    else:
        result["decision"] = "existing-backend"
        result["reason"] = "no Convex backend changes; use the existing configured backend"
    result["frontendOrOtherFiles"] = sorted(changed - claimed)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True, help="PR base: a fetched ref or SHA, e.g. origin/main")
    parser.add_argument("--head", default="HEAD", help="PR head commit (default HEAD)")
    parser.add_argument("--repo", default=".", help="repository path (default .)")
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(args.repo, args.base, args.head), indent=2))
    except GitError as error:
        print(json.dumps({"decision": "blocked", "error": str(error)}, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()
