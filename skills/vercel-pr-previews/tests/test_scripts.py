"""Tests for the helper scripts. Run: python3 -m unittest discover -s skills/vercel-pr-previews/tests"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SHA = "0123456789abcdef0123456789abcdef01234567"


def npm_lock(esbuild="0.20.0", scheduler="0.25.0"):
    """npm v3 lockfile: convex has a nested esbuild; react pulls in a hoisted scheduler."""
    return json.dumps({"lockfileVersion": 3, "packages": {
        "": {"dependencies": {"convex": "1.20.0", "zod": "3.0.0", "react": "19.0.0"}},
        "node_modules/convex": {"version": "1.20.0", "dependencies": {"esbuild": "^0.20.0"}},
        "node_modules/convex/node_modules/esbuild": {"version": esbuild},
        "node_modules/react": {"version": "19.0.0", "dependencies": {"scheduler": "^0.25.0"}},
        "node_modules/scheduler": {"version": scheduler},
        "node_modules/zod": {"version": "3.0.0"},
    }})


def run(args, **kwargs):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, **kwargs)


class ConvexChangesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.git("init", "-q", "-b", "main")
        self.write("package.json", json.dumps({"dependencies": {"convex": "1.20.0", "zod": "3.0.0", "react": "19.0.0"}}))
        self.write("tsconfig.json", '{ // comment\n "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["./src/*"] } }, }')
        self.write("convex/messages.ts", 'import { v } from "convex/values";\nimport { clamp } from "../src/shared/math";\n')
        self.write("convex/_generated/api.d.ts", "export {};\n")
        self.write("src/shared/math.ts", "export const clamp = 1;\n")
        self.write("src/App.tsx", 'import { api } from "../convex/_generated/api";\n')
        self.commit("base")
        self.git("checkout", "-q", "-b", "feature")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       check=True, capture_output=True)

    def write(self, path, text):
        target = Path(self.repo, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def on_main(self, files):
        """Add files to the base branch and restart the feature branch from it."""
        self.git("checkout", "-q", "main")
        for path, text in files.items():
            self.write(path, text)
        self.commit("base setup")
        self.git("checkout", "-q", "-B", "feature")

    def analyze(self, base="main"):
        result = run([str(SCRIPTS / "convex_changes.py"), "--repo", self.repo, "--base", base])
        return result.returncode, json.loads(result.stdout)

    def test_frontend_only_uses_existing_backend(self):
        self.write("src/App.tsx", 'import { api } from "../convex/_generated/api";\nexport default 1;\n')
        self.commit("frontend")
        code, out = self.analyze()
        self.assertEqual((code, out["decision"]), (0, "existing-backend"))

    def test_backend_change_in_earlier_commit_still_counts(self):
        self.write("convex/messages.ts", 'import { v } from "convex/values";\nexport const x = 2;\n')
        self.commit("backend")
        self.write("src/App.tsx", "export default 2;\n")
        self.commit("frontend after backend")
        code, out = self.analyze()
        self.assertEqual(out["decision"], "convex-preview")
        self.assertIn("convex/messages.ts", out["projects"][0]["backend"])

    def test_shared_module_imported_by_functions(self):
        self.write("src/shared/math.ts", "export const clamp = 2;\n")
        self.commit("shared")
        self.assertEqual(self.analyze()[1]["decision"], "convex-preview")

    def test_imported_json_asset_counts(self):
        self.on_main({"convex/tasks.ts": 'import values from "../shared/values.json";\nexport const n = values.limit;\n',
                      "shared/values.json": '{"limit": 1}\n'})
        self.write("shared/values.json", '{"limit": 2}\n')
        self.commit("asset")
        code, out = self.analyze()
        self.assertEqual(out["decision"], "convex-preview")
        self.assertIn("shared/values.json (imported by Convex functions)", out["projects"][0]["backend"])

    def test_alias_tsconfig_change_needs_review(self):
        self.write("tsconfig.json", '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./lib/*"]}}}')
        self.commit("tsconfig")
        self.assertEqual(self.analyze()[1]["decision"], "review")

    def test_transitive_backend_lockfile_change(self):
        self.on_main({"package-lock.json": npm_lock()})
        self.write("package-lock.json", npm_lock(esbuild="0.20.2"))
        self.commit("nested esbuild bump")
        code, out = self.analyze()
        self.assertEqual(out["decision"], "convex-preview")
        self.assertIn("convex/node_modules/esbuild", out["projects"][0]["config"][0])

    def test_transitive_frontend_lockfile_change(self):
        self.on_main({"package-lock.json": npm_lock()})
        self.write("package-lock.json", npm_lock(scheduler="0.25.1"))
        self.commit("scheduler bump")
        self.assertEqual(self.analyze()[1]["decision"], "existing-backend")

    def test_unprovable_lockfiles_need_review(self):
        self.on_main({"yarn.lock": "# v1\n"})
        self.write("yarn.lock", "# v1\nchanged\n")
        self.commit("yarn")
        self.assertEqual(self.analyze()[1]["decision"], "review")
        self.on_main({"package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {
            "": {}, "packages/ui": {"version": "1.0.0"}, "node_modules/ui": {"link": True, "resolved": "packages/ui"}}})})
        self.write("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
            "": {}, "packages/ui": {"version": "1.1.0"}, "node_modules/ui": {"link": True, "resolved": "packages/ui"}}}))
        self.commit("workspace lock")
        self.assertEqual(self.analyze()[1]["decision"], "review")

    def test_custom_functions_dir_and_convex_json(self):
        self.git("checkout", "-q", "main")
        self.git("mv", "convex", "backend")
        self.write("convex.json", '{"functions": "backend/"}')
        self.write("src/shared/math.ts", "export const clamp = 1;\n")
        self.commit("move functions")
        self.git("checkout", "-q", "-B", "feature")
        self.write("backend/schema.ts", "export default 1;\n")
        self.commit("schema")
        code, out = self.analyze()
        self.assertEqual(out["decision"], "convex-preview")
        self.assertEqual(out["projects"][0]["functionsDirs"], ["backend"])

    def test_backend_dependency_bump(self):
        self.write("package.json", json.dumps({"dependencies": {"convex": "1.21.0", "zod": "3.0.0", "react": "19.0.0"}}))
        self.commit("bump convex")
        self.assertEqual(self.analyze()[1]["decision"], "convex-preview")

    def test_frontend_dependency_bump_is_not_backend(self):
        self.write("package.json", json.dumps({"dependencies": {"convex": "1.20.0", "zod": "3.0.0", "react": "19.1.0"}}))
        self.commit("bump react")
        self.assertEqual(self.analyze()[1]["decision"], "existing-backend")

    def test_no_convex_project(self):
        self.git("checkout", "-q", "main")
        self.git("rm", "-rq", "convex")
        self.write("package.json", "{}")
        self.commit("no convex")
        self.git("checkout", "-q", "-B", "feature")
        self.write("src/App.tsx", "export default 3;\n")
        self.commit("frontend")
        self.assertEqual(self.analyze()[1]["decision"], "not-applicable")

    def test_missing_base_ref_is_blocked(self):
        code, out = self.analyze(base="origin/does-not-exist")
        self.assertEqual((code, out["decision"]), (2, "blocked"))


class PreviewsSectionTest(unittest.TestCase):
    def section(self, body, *args):
        return run([str(SCRIPTS / "pr_previews_section.py"), "--body-file", "-", "--head", SHA, *args], input=body)

    def test_append_then_replace_preserves_other_text(self):
        body = "Summary\n\nDetails here.\n"
        first = self.section(body, "--frontend-status", "pending")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(first.stdout.startswith(body.rstrip("\n") + "\n\n<!-- pr-previews:start -->"))
        edited = first.stdout + "\nFooter\n"
        second = self.section(edited, "--frontend-status", "ready", "--frontend-url", "https://app-abc.vercel.app",
                              "--convex", "existing")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout.count("<!-- pr-previews:start -->"), 1)
        self.assertNotIn("Pending", second.stdout)
        self.assertTrue(second.stdout.startswith("Summary\n\nDetails here.\n"))
        self.assertTrue(second.stdout.endswith("<!-- pr-previews:end -->\n\nFooter\n"))
        again = self.section(second.stdout, "--frontend-status", "ready", "--frontend-url",
                             "https://app-abc.vercel.app", "--convex", "existing")
        self.assertEqual(again.stdout, second.stdout)

    def test_convex_links_only_for_preview(self):
        out = self.section("", "--frontend-status", "pending", "--convex", "existing",
                           "--convex-api", "https://x.convex.cloud")
        self.assertEqual(out.returncode, 2)
        out = self.section("", "--frontend-status", "pending", "--convex", "preview",
                           "--convex-api", "https://x.convex.cloud")
        self.assertIn("Convex API URL** (client endpoint", out.stdout)
        self.assertIn("Convex preview backend:** Pending", out.stdout)
        self.assertNotIn("Ready", out.stdout)
        out = self.section("", "--frontend-status", "pending", "--convex", "preview",
                           "--convex-api", "https://x.convex.cloud", "--convex-status", "Ready")
        self.assertIn("Convex preview backend:** Ready", out.stdout)

    def test_rejects_credentials_short_sha_and_bad_markers(self):
        out = self.section("", "--frontend-status", "ready", "--frontend-url",
                           "https://a.vercel.app/?x-vercel-protection-bypass=s")
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("=s", out.stderr)
        out = run([str(SCRIPTS / "pr_previews_section.py"), "--body-file", "-", "--head", "abc123",
                   "--frontend-status", "pending"], input="")
        self.assertEqual(out.returncode, 2)
        out = self.section("<!-- pr-previews:start -->\nno end", "--frontend-status", "pending")
        self.assertEqual((out.returncode, out.stdout), (2, ""))
        out = self.section("", "--frontend-status", "ready")
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
