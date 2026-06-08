#!/usr/bin/env python3
"""Demo runner for the vue3-migration tool.

Runs the REAL CLI (applied) against an external demo Vue project to show the
tool working end-to-end, then LEAVES the changes in place so they can be
reviewed with `git diff` (e.g. in an open VS Code window). This is the
reproducible core of the `demo-migration` skill.

It does NOT pick the route — the skill's agent asks the user (default: 3
component migrations; alternatives: more components, a mixin retirement, or a
mix) and passes the choice here as flags. Routes compose freely:

  --components N            auto-select N READY components from a status scan,
                            spread across mixin-counts (1, 2, 3 ...) for variety
  --component-paths a,b,c   migrate these exact components (rel to root or abs)
  --mixins name1,name2      retire each mixin across the whole project

Safety rules (each learned the hard way during the first manual run):
  * Always invoke with `--root <project>` — the CLI derives the project root
    from --root/cwd and IGNORES a positional path argument.
  * Drive the single `Apply changes? (y/n)` prompt with "y".
  * The tool writes `migration-*.md` reports into the project root. Afterward we
    remove ONLY UNTRACKED ones; a TRACKED/committed report is never touched
    (deleting a pre-existing committed report once polluted the diff).
  * The migration changes themselves are LEFT IN PLACE — never reverted.

Usage:
  python3 run_demo.py [--root PATH] [--components N]
                      [--component-paths a.vue,b.vue] [--mixins m1,m2]
                      [--keep-reports]
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Last-resort demo project this skill was built against. The actual default is
# resolved portably by default_demo_root() below; override with --root.
_FALLBACK_DEMO = "/Users/base/Projects/dummy_vue_migration_project"

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(s: str) -> str:
    return _ANSI.sub("", s)


def find_repo_root(start: Path) -> Path:
    """Locate the vue3-migration tool repo (has the package + pyproject)."""
    for d in [start, *start.parents]:
        if (d / "vue3_migration").is_dir() and (d / "pyproject.toml").is_file():
            return d
    raise SystemExit("Could not locate the vue3-migration tool repo from " + str(start))


def default_demo_root() -> str:
    """Resolve the demo project portably so the skill works on any machine:
    $VUE3_DEMO_PROJECT → a sibling 'dummy_vue_migration_project' next to the tool
    repo → the built-in fallback."""
    env = os.environ.get("VUE3_DEMO_PROJECT")
    if env:
        return env
    try:
        sib = find_repo_root(Path(__file__).resolve()).parent / "dummy_vue_migration_project"
        if sib.is_dir():
            return str(sib)
    except SystemExit:
        pass
    return _FALLBACK_DEMO


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def run_tool(repo_root: Path, project_root: Path, *cmd: str) -> str:
    """Run the real CLI applied (answers the single apply prompt with 'y')."""
    proc = subprocess.run(
        [sys.executable, "-m", "vue3_migration", "--root", str(project_root), *cmd],
        cwd=str(repo_root), input="y\n", capture_output=True, text=True,
    )
    return strip_ansi(proc.stdout + proc.stderr)


def parse_ready_components(report: str):
    """From a status report, return [(rel_path, mixin_count)] for READY components."""
    out = []
    for block in re.split(r"^### ", report, flags=re.M):
        path_m = re.search(r"`([^`]+\.vue)`", block)
        if not path_m or "**Ready**" not in block:
            continue
        mix_line = re.search(r"- Mixins:\s*(.+)", block)
        count = len(re.findall(r"`[^`]+`", mix_line.group(1))) if mix_line else 1
        out.append((path_m.group(1), count))
    return out


def select_components(ready, n):
    """Pick n READY components spread across mixin-counts (1, 2, 3, ...) for variety."""
    by_count: dict[int, list[str]] = {}
    for path, count in ready:
        by_count.setdefault(count, []).append(path)
    picks: list[str] = []
    # First pass: one from each distinct count, ascending — the 1/2/3-mixin spread.
    for c in sorted(by_count):
        if len(picks) < n and by_count[c]:
            picks.append(by_count[c].pop(0))
    # Second pass: fill the rest from the smallest counts.
    for c in sorted(by_count):
        while len(picks) < n and by_count[c]:
            picks.append(by_count[c].pop(0))
    return picks[:n]


def clean_untracked_reports(root: Path, only: "set[str] | None" = None) -> list[str]:
    """Remove untracked migration-*.md (optionally limited to `only`); never a tracked one."""
    removed = []
    for f in sorted(root.glob("migration-*.md")):
        if only is not None and f.name not in only:
            continue
        tracked = git(root, "ls-files", "--error-unmatch", f.name).returncode == 0
        if not tracked:
            f.unlink()
            removed.append(f.name)
    return removed


def summarize(out: str) -> str:
    keys = ("MIGRATED", "PATCHED", "CREATED", "mixins:", "composables:", "setup()",
            "Nothing to migrate", "Components to update", "Composables to patch")
    lines = [ln.rstrip() for ln in out.splitlines() if any(k in ln for k in keys)]
    return "\n".join(lines) or out.strip()[:400]


def main():
    ap = argparse.ArgumentParser(description="Demo the vue3-migration tool on an external project.")
    ap.add_argument("--root", default=default_demo_root(),
                    help="target Vue project (default: $VUE3_DEMO_PROJECT or sibling demo repo)")
    ap.add_argument("--components", type=int, default=3, help="auto-select this many READY components")
    ap.add_argument("--component-paths", default="", help="comma-separated explicit component paths")
    ap.add_argument("--mixins", default="", help="comma-separated mixin names to retire project-wide")
    ap.add_argument("--clean-reports", action="store_true",
                    help="delete THIS run's untracked migration-*.md afterward "
                         "(default: KEEP them — the report is a primary deliverable of the demo)")
    args = ap.parse_args()

    project_root = Path(args.root).resolve()
    if not project_root.is_dir():
        raise SystemExit(f"Target project not found: {project_root}")
    if git(project_root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise SystemExit(f"Target is not a git repo (needed for diff review): {project_root}")
    repo_root = find_repo_root(Path(__file__).resolve())
    reports_before = {p.name for p in project_root.glob("migration-*.md")}

    baseline_dirty = bool(git(project_root, "status", "--porcelain").stdout.strip())
    if baseline_dirty:
        print("NOTE: target has uncommitted changes; your diff will include them too.\n")

    explicit = [p.strip() for p in args.component_paths.split(",") if p.strip()]
    mixins = [m.strip() for m in args.mixins.split(",") if m.strip()]

    components = explicit
    if not components and args.components > 0:
        print("Scanning project for READY components ...")
        run_tool(repo_root, project_root, "status")
        reports = sorted(project_root.glob("migration-status-*.md"), key=lambda p: p.stat().st_mtime)
        ready = parse_ready_components(reports[-1].read_text()) if reports else []
        components = select_components(ready, args.components)
        print(f"Selected {len(components)}/{len(ready)} READY component(s): {components}\n")

    if not components and not mixins:
        raise SystemExit("Nothing to run: no components selected and no --mixins given.")

    for path in components:
        target = path if Path(path).is_absolute() else str(project_root / path)
        print(f"--- component migration: {path} ---")
        print(summarize(run_tool(repo_root, project_root, "component", target)) + "\n")
    for name in mixins:
        print(f"--- mixin retirement: {name} ---")
        print(summarize(run_tool(repo_root, project_root, "mixin", name)) + "\n")

    new_reports = {p.name for p in project_root.glob("migration-*.md")} - reports_before
    if args.clean_reports:
        removed = clean_untracked_reports(project_root, only=new_reports)
        print(f"Cleaned {len(removed)} untracked tool report(s).\n")
    else:
        kept = sorted(n for n in new_reports if n.startswith("migration-report-"))
        if kept:
            print("Migration report(s) kept for review — open in your editor:")
            for n in kept:
                print(f"  {project_root / n}")
            print()

    # Light validation: migrated components should retain no mixin references.
    changed = [ln[3:] for ln in git(project_root, "status", "--porcelain").stdout.splitlines()
               if ln.endswith(".vue")]
    for rel in changed:
        text = (project_root / rel.strip()).read_text(errors="ignore")
        flag = "WARN: still references a mixin" if ("mixins:" in text or "/mixins/" in text) else "ok"
        print(f"  [{flag}] {rel.strip()}")

    print("\n===== git diff --stat (changes LEFT IN PLACE for review) =====")
    print(git(project_root, "diff", "--stat").stdout or "(no changes)")
    print("===== git status --short =====")
    print(git(project_root, "status", "--short").stdout or "(clean)")
    print(f"\nReview in your editor or with: git -C {project_root} diff")


if __name__ == "__main__":
    main()
