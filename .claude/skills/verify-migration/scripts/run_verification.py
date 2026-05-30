#!/usr/bin/env python3
"""Generic verification runner for the vue3-migration tool.

Given a manifest of runs, for EACH run it:
  1. copies the pristine fixture to a throwaway temp dir (never mutates inputs),
  2. runs the REAL CLI applied (`python -m vue3_migration --root <copy> <cmd>`),
  3. captures the tool's migration-report-*.md, generated composables, migrated
     components, and the CLI log,
  4. checks expectations (substring contains/absent on the report + named files),
  5. writes per-run artifacts + INDEX.md + results.json under the out dir.

The out base defaults OUTSIDE any project root the tool scans
(`<repo>/tests/fixtures/.verify/<fixture-name>/`). Inputs stay pristine; every
run resets a fresh copy. EVERY run is KEPT: results are written to a per-run
subdir `<out-base>/run-<timestamp>/` (or `<out-base>/<label>/` with --label),
never overwriting prior runs, and a `<out-base>/latest` pointer tracks the most
recent one — so the developer can review and compare past runs.

Usage:
    python3 run_verification.py path/to/verification.json [--out DIR] [--label NAME]

Manifest schema (see templates/verification.example.json):
    {
      "fixture": "tests/fixtures/<env>",        # pristine project root (rel to repo or abs)
      "out": "tests/fixtures/.verify/<env>",    # optional; default derived
      "runs": [
        {
          "name": "scenario-id",
          "command": "component" | "mixin" | "all",
          "target": "src/components/X.vue" | "someMixin" | "",
          "expect": {
            "report_contains": ["..."],
            "report_absent":   ["..."],
            "files": {
              "src/composables/useX.js": {"contains": ["..."], "absent": ["..."]},
              "src/components/X.vue":    {"contains": ["..."]}
            }
          }
        }
      ]
    }
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / "vue3_migration").is_dir() and (d / "pyproject.toml").is_file():
            return d
    raise SystemExit(f"Could not locate repo root (with vue3_migration/) above {start}")


def rel(target: Path, start: Path) -> str:
    return os.path.relpath(target, start)


def check(text: str, contains, absent):
    """Return list of (ok, label) for contains/absent substring checks."""
    out = []
    for s in contains or []:
        out.append((s in text, f"contains {s!r}"))
    for s in absent or []:
        out.append((s not in text, f"omits {s!r}"))
    return out


def run_one(run, fixture: Path, repo_root: Path, out_dir: Path):
    name = run["name"]
    command = run.get("command", "component")
    target = run.get("target", "")
    expect = run.get("expect", {})
    run_out = out_dir / name
    run_out.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix=f"verify-{name}-"))
    copy = tmp / fixture.name
    shutil.copytree(fixture, copy)

    # Build CLI args. component -> path under copy; mixin -> name; all -> none.
    args = [sys.executable, "-m", "vue3_migration", "--root", str(copy), command]
    if command == "component" and target:
        args.append(str(copy / target))
    elif command == "mixin" and target:
        args.append(target)

    proc = subprocess.run(
        args, input="y\n" * 20, capture_output=True, text=True, cwd=str(repo_root),
    )
    cli_log = (proc.stdout or "") + (proc.stderr or "")
    (run_out / "cli.txt").write_text(cli_log)

    # The tool writes the migration report into the run root (--root = copy).
    reports = sorted(copy.glob("migration-report-*.md"))
    report_text = ""
    report_link = None
    if reports:
        report_text = reports[-1].read_text()
        (run_out / "migration-report.md").write_text(report_text)
        report_link = "migration-report.md"

    # Capture artifacts: created composables + components that changed vs pristine.
    artifacts = []
    comp_dir = copy / "src" / "composables"
    if comp_dir.is_dir():
        for js in sorted(comp_dir.glob("*.js")):
            (run_out / js.name).write_text(js.read_text())
            artifacts.append(js.name)
    for vue in sorted((copy / "src" / "components").glob("*.vue")):
        original = fixture / "src" / "components" / vue.name
        if original.is_file() and original.read_text() != vue.read_text():
            (run_out / vue.name).write_text(vue.read_text())
            artifacts.append(vue.name)

    # Checks.
    checks = []
    checks += check(report_text, expect.get("report_contains"), expect.get("report_absent"))
    for relpath, rules in (expect.get("files") or {}).items():
        f = copy / relpath
        if not f.is_file():
            checks.append((False, f"file exists: {relpath}"))
            continue
        txt = f.read_text()
        for ok, label in check(txt, rules.get("contains"), rules.get("absent")):
            checks.append((ok, f"{relpath}: {label}"))

    shutil.rmtree(tmp, ignore_errors=True)

    passed = all(ok for ok, _ in checks)
    return {
        "name": name, "command": command, "target": target,
        "passed": passed,
        "checks": [{"ok": ok, "label": lbl} for ok, lbl in checks],
        "report": report_link, "artifacts": artifacts,
        "report_tier": _tier(report_text),
    }


def _tier(report_text: str) -> str:
    m = re.search(r"🟢|🟡|🔴", report_text)
    return {"🟢": "ready", "🟡": "drop-in fixes", "🔴": "design decisions"}.get(
        m.group(0) if m else "", "—")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    manifest_path = Path(sys.argv[1]).resolve()
    manifest = json.loads(manifest_path.read_text())

    fixture = Path(manifest["fixture"])
    if not fixture.is_absolute():
        # resolve relative to repo root (manifest usually lives inside the fixture)
        repo_guess = find_repo_root(manifest_path.parent)
        fixture = (repo_guess / fixture).resolve()
    repo_root = find_repo_root(fixture)

    out_arg = None
    if "--out" in sys.argv:
        out_arg = sys.argv[sys.argv.index("--out") + 1]
    label = None
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]

    # Output base — every run is KEPT under its own timestamped (or labeled)
    # subdir so previous runs are never destroyed and stay reviewable.
    out_base = Path(out_arg) if out_arg else Path(manifest.get(
        "out", repo_root / "tests" / "fixtures" / ".verify" / fixture.name))
    if not out_base.is_absolute():
        out_base = (repo_root / out_base).resolve()

    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_name = label or f"run-{stamp}"
    out_dir = out_base / run_name
    n = 2
    while out_dir.exists():
        out_dir = out_base / f"{run_name}-{n}"
        n += 1
    out_dir.mkdir(parents=True)

    results = [run_one(r, fixture, repo_root, out_dir) for r in manifest["runs"]]

    # INDEX.md
    md = [f"# Verification — {fixture.name}  ·  {stamp}\n",
          "Real CLI runs (reset-then-apply per scenario). Each row links the tool's "
          "own migration report and the generated/changed files.\n",
          "| Scenario | Verdict | Report tier | Report | Files |",
          "|---|---|---|---|---|"]
    for r in results:
        d = r["name"]
        rep = f"[report]({d}/{r['report']})" if r["report"] else "—"
        files = ", ".join(f"[{a}]({d}/{a})" for a in r["artifacts"]) or "—"
        md.append(f"| {d} | {'✅' if r['passed'] else '⚠️'} | {r['report_tier']} | {rep} | {files} |")
    md.append("")
    for r in results:
        md.append(f"\n## {r['name']} — {'✅ all checks passed' if r['passed'] else '⚠️ check(s) failed'}")
        md.append(f"`{r['command']} {r['target']}` · tier: {r['report_tier']}")
        for c in r["checks"]:
            md.append(f"- {'✅' if c['ok'] else '❌'} {c['label']}")
    (out_dir / "INDEX.md").write_text("\n".join(md) + "\n")
    (out_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    # Stable pointer to the most recent run for easy review.
    latest = out_base / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(out_dir.name, target_is_directory=True)
    except OSError:
        (out_base / "LATEST.txt").write_text(out_dir.name + "\n")

    n_pass = sum(1 for r in results if r["passed"])
    print(f"Wrote {out_dir}/INDEX.md  ({n_pass}/{len(results)} scenarios passed all checks)")
    print(f"Kept under {out_base}  (previous runs preserved; latest -> {out_dir.name})")
    for r in results:
        if not r["passed"]:
            bad = [c["label"] for c in r["checks"] if not c["ok"]]
            print(f"  ⚠️ {r['name']}: {bad}")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
