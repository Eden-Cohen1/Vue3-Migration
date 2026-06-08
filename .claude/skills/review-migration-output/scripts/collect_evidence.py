#!/usr/bin/env python3
"""Evidence collector for the review-migration-output skill.

Inspects the CURRENT migration output in the demo Vue project — the working-tree
diff (migrated components + patched/generated composables) and the tool's
`migration-report-*.md` files — and emits a grounded evidence bundle:

  1. The list of changed files and the full `git diff`.
  2. Deterministic CODEGEN smell checks per changed file (formatting regressions,
     leaked private members, leftover `this.`, syntax validity, ...).
  3. Deterministic REPORT checks (the "no manual steps needed" vs. "Implementation
     Divergences" contradiction, recipe duplication, link sanity).
  4. The relevant mixin sources, so a reviewer can judge divergences against
     ground truth.

It finds *candidate* issues mechanically; the skill's reviewer (a human or an
agent fan-out) then verifies them, judges severity, and ties each back to the
vue3-migration SOURCE module that produced it. This script never edits anything.

Usage:
  python3 collect_evidence.py [--root PATH] [--json]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_FALLBACK_DEMO = "/Users/base/Projects/dummy_vue_migration_project"


def _repo_root() -> Path:
    for d in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (d / "vue3_migration").is_dir() and (d / "pyproject.toml").is_file():
            return d
    return Path.cwd()


def default_demo_root() -> str:
    """Resolve the demo project portably: $VUE3_DEMO_PROJECT → a sibling
    'dummy_vue_migration_project' next to the tool repo → built-in fallback."""
    env = os.environ.get("VUE3_DEMO_PROJECT")
    if env:
        return env
    sib = _repo_root().parent / "dummy_vue_migration_project"
    return str(sib) if sib.is_dir() else _FALLBACK_DEMO


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True).stdout


def changed_files(root: Path) -> list[str]:
    out = git(root, "diff", "--name-only").splitlines()
    return [f for f in out if f.strip()]


def reports(root: Path) -> list[Path]:
    return sorted(root.glob("migration-report-*.md"), key=lambda p: p.stat().st_mtime)


def node_check(path: Path) -> str | None:
    """Return an error string if `node --check` fails, else None (skip if no node)."""
    try:
        p = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        return None if p.returncode == 0 else p.stderr.strip().splitlines()[-1] if p.stderr else "syntax error"
    except FileNotFoundError:
        return None  # node not installed; skip silently


def check_component(text: str) -> list[dict]:
    """Codegen smell checks for a migrated .vue component."""
    flags = []
    if re.search(r"<script>\n\s*\n\s*import\b", text):
        flags.append(_f("formatting", "low", "blank line orphaned right after `<script>` (mixin import removed)"))
    if re.search(r"from '[^']+'\nexport default", text):
        flags.append(_f("formatting", "low", "no blank line between the composable import and `export default`"))
    if re.search(r"\bmixins\s*:", text) or "/mixins/" in text:
        flags.append(_f("correctness", "high", "still references a mixin after migration"))
    if "setup(" not in text:
        flags.append(_f("correctness", "med", "no setup() present after migration"))
    return flags


def check_composable(text: str, path: Path) -> list[dict]:
    """Codegen smell checks for a generated/patched composable .js."""
    flags = []
    err = node_check(path)
    if err:
        flags.append(_f("correctness", "high", f"node --check failed: {err}"))
    if "\n\n\n" in text:
        flags.append(_f("formatting", "low", "3+ consecutive blank lines (stray whitespace from insertion)"))
    # Leaked private members in the public return block.
    ret = re.search(r"return\s*\{(.*?)\}", text, re.S)
    if ret:
        privates = sorted(set(re.findall(r"\b(_\w+)\s*,?", ret.group(1))))
        if privates:
            flags.append(_f("dx", "med", f"private member(s) leaked into the public return: {', '.join(privates)}"))
    # Leftover this. (rough — strings/comments may yield false positives; reviewer confirms).
    body = re.sub(r"//[^\n]*", "", text)
    if re.search(r"\bthis\.", body):
        flags.append(_f("correctness", "high", "leftover `this.` reference in generated code"))
    if re.search(r"see migration report for details", text):
        flags.append(_f("dx", "low", "inline warning comment couples the file to an external report (which can be deleted/moved)"))
    return flags


def check_reports(report_texts: dict[str, str]) -> list[dict]:
    """Report-accuracy / DX checks across the migration reports."""
    flags = []
    recipe_count = 0
    for name, text in report_texts.items():
        # Contradiction: a composable under "no manual steps needed" that also shows divergences.
        if "no manual steps needed" in text and "Implementation Divergences" in text:
            flags.append(_f("report", "high",
                            f"{name}: composables under 'no manual steps needed' also list "
                            "'Implementation Divergences' — the summary tells the dev nothing to check "
                            "while flagging real logic differences"))
        # Stubby composable bodies shown in divergences (real behavior likely dropped).
        if re.search(r"//\s*Simulate|//\s*TODO", text):
            flags.append(_f("report", "med",
                            f"{name}: a divergence shows a stub composable body (e.g. '// Simulate ...') — "
                            "the migration may replace real logic with a stub"))
        if "Migration Patterns" in text:
            recipe_count += 1
    if recipe_count > 1:
        flags.append(_f("dx", "low",
                        f"the full 'Migration Patterns' recipe block is repeated in {recipe_count} reports "
                        "(duplication across per-migration reports)"))
    return flags


def _f(category: str, severity: str, message: str) -> dict:
    return {"category": category, "severity": severity, "message": message}


def referenced_mixins(report_texts: dict[str, str], root: Path) -> list[str]:
    names = set()
    for text in report_texts.values():
        for m in re.findall(r"src/mixins/(\w+\.js)", text):
            names.add(m)
    found = []
    for n in sorted(names):
        p = root / "src" / "mixins" / n
        if p.is_file():
            found.append(f"src/mixins/{n}")
    return found


def main():
    ap = argparse.ArgumentParser(description="Collect evidence about the tool's migration output.")
    ap.add_argument("--root", default=default_demo_root())
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of markdown")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"Target project not found: {root}")

    files = changed_files(root)
    report_paths = reports(root)
    report_texts = {p.name: p.read_text(errors="ignore") for p in report_paths}

    findings: list[dict] = []
    per_file: dict[str, list[dict]] = {}
    for rel in files:
        p = root / rel
        if not p.is_file():
            continue
        text = p.read_text(errors="ignore")
        fl = check_component(text) if rel.endswith(".vue") else (
            check_composable(text, p) if rel.endswith(".js") else [])
        if fl:
            per_file[rel] = fl
            for x in fl:
                findings.append({**x, "file": rel})
    report_flags = check_reports(report_texts)
    findings.extend(report_flags)

    mixins = referenced_mixins(report_texts, root)

    if args.json:
        print(json.dumps({
            "root": str(root), "changed_files": files,
            "reports": [p.name for p in report_paths],
            "candidate_findings": findings, "mixin_sources": mixins,
        }, indent=2))
        return

    w = print
    w("# Migration-output evidence bundle\n")
    w(f"Project: `{root}`")
    w(f"Changed files: {len(files)} · Reports: {len(report_paths)}\n")
    w("## Candidate findings (mechanical — verify before reporting)\n")
    if not findings:
        w("_No mechanical smells detected. Do the semantic review anyway._\n")
    else:
        order = {"high": 0, "med": 1, "low": 2}
        for x in sorted(findings, key=lambda d: order.get(d["severity"], 9)):
            loc = x.get("file", "report")
            w(f"- **[{x['severity']}/{x['category']}]** ({loc}) {x['message']}")
        w("")
    w("## Changed files\n" + "\n".join(f"- {f}" for f in files) + "\n")
    w("## Reports\n" + ("\n".join(f"- {p.name}" for p in report_paths) or "(none)") + "\n")
    w("## Mixin sources to diff divergences against\n" + ("\n".join(f"- {m}" for m in mixins) or "(none)") + "\n")
    w("## Full diff\n```diff\n" + git(root, "diff") + "\n```\n")
    w("## Reports (full text)\n")
    for name, text in report_texts.items():
        w(f"### {name}\n```md\n{text}\n```\n")


if __name__ == "__main__":
    main()
