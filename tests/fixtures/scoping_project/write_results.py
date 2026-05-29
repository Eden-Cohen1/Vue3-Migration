#!/usr/bin/env python3
"""Materialize the scoping-feature verification as inspectable artifacts.

For every scenario it runs the real single-component migration flow, writes the
generated composable + rewritten component into `_results/<Scenario>/`, and
builds `_results/RESULTS.md` — a linked index with the per-scenario verdict,
the scoping summary (used / returned / private / dropped), and the full
before/after so each example can be seen in action.

Inputs in src/ are NOT modified. Re-runnable.

    python3 tests/fixtures/scoping_project/write_results.py
"""
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_report import (  # reuse the verified harness logic
    PROJECT, SCENARIOS, returned_members, declared_names, code_body_only,
    referenced, find_generated,
)
from vue3_migration.models import MigrationConfig
from vue3_migration.workflows.auto_migrate_workflow import run, run_scoped
from vue3_migration.reporting.diff import write_migration_report

# IMPORTANT: results live OUTSIDE project_root. The migration tool scans the
# whole project tree (rglob / os.walk) for components and composables, so
# writing generated composables inside the project would pollute re-runs (the
# tool would treat them as pre-existing composables and switch to the patch path).
RESULTS = PROJECT.parent / "scoping_results"


def rel(target: Path, start: Path) -> str:
    import os
    return os.path.relpath(target, start)


def main():
    if RESULTS.exists():
        import shutil
        shutil.rmtree(RESULTS)
    RESULTS.mkdir(parents=True)

    cfg = MigrationConfig(project_root=PROJECT)
    with patch("builtins.print"):
        full_plan = run(PROJECT, cfg)
    full_by_name = {c.file_path.name: c.new_content
                    for c in full_plan.composable_changes if c.has_changes}

    md = []
    md.append("# Composable-scoping verification results\n")
    md.append("Each scenario runs the real `component <path>` migration flow. "
              "Inputs (mixin + component) are linked alongside the generated "
              "composable and rewritten component, plus a checks verdict.\n")
    md.append("Reproduce: `python3 tests/fixtures/scoping_project/write_results.py` "
              "then `python3 tests/fixtures/scoping_project/run_report.py`.\n")

    total = passed = 0
    rows = []

    for sc in SCENARIOS:
        comp_path = next(PROJECT.rglob(sc["file"]))
        with patch("builtins.print"):
            plan = run_scoped(PROJECT, cfg, component_path=comp_path)

        scen_name = Path(sc["file"]).stem
        out_dir = RESULTS / scen_name
        out_dir.mkdir(parents=True, exist_ok=True)

        gen = find_generated(plan)
        comp_change = next(
            (c for c in plan.component_changes
             if c.file_path.name == sc["file"] and c.has_changes), None)

        entry = plan.entries_by_component[0][1][0] if plan.entries_by_component else None
        used = sorted(entry.used_members) if entry else []
        mixin_name = entry.mixin_path.name if entry else "?"

        # write artifacts
        gen_link = comp_link = None
        content = gen.new_content if gen else ""
        if gen:
            p = out_dir / gen.file_path.name
            p.write_text(content)
            gen_link = rel(p, RESULTS)
        if comp_change:
            p = out_dir / sc["file"]
            p.write_text(comp_change.new_content)
            comp_link = rel(p, RESULTS)

        # The official migration report (Summary / Action Plan / warnings /
        # patterns). write_migration_report writes a timestamped file into the
        # project root; capture its content, save it under _results, and remove
        # the original so the fixture stays clean.
        report_link = None
        report_text = ""
        tmp_report = write_migration_report(plan, PROJECT)
        report_text = tmp_report.read_text()
        tmp_report.unlink()
        rp = out_dir / "migration-report.md"
        rp.write_text(report_text)
        report_link = rel(rp, RESULTS)

        # scoping summary (exclude the composable's own `export function` name,
        # which the declaration regex would otherwise count as a "member")
        import re as _re
        def _fn_name(text):
            m = _re.search(r"export\s+function\s+(\w+)", text or "")
            return {m.group(1)} if m else set()
        ret = sorted(returned_members(content)) if content else []
        decl = (declared_names(content) - _fn_name(content)) if content else set()
        full_text = full_by_name.get(gen.file_path.name, "") if gen else ""
        full_decl = declared_names(full_text) - _fn_name(full_text)
        private = sorted(decl - set(ret))
        dropped = sorted(full_decl - decl)

        # checks (mirror run_report)
        checks = []

        def chk(label, ok):
            checks.append((ok, label))

        if gen:
            chk(f"returns exactly {sorted(sc['ret'])}", set(ret) == sc["ret"])
            chk(f"declares {sorted(sc['decl'])}", not (sc["decl"] - decl))
            if sc["drop"]:
                chk(f"drops {sorted(sc['drop'])}",
                    not ((sc["drop"] & decl) | (sc["drop"] & set(ret))))
            if sc.get("equals_full"):
                chk("scoped == full output", content == full_by_name.get(gen.file_path.name, ""))
            for s in sc.get("present", []):
                chk(f"contains {s!r}", s in content)
            for s in sc.get("absent", []):
                chk(f"omits {s!r}", s not in content)
            body = code_body_only(content)
            undeclared = sorted(n for n in (full_decl | sc.get("drop", set()))
                                if n not in decl and referenced(n, body))
            chk("no undeclared member referenced in body", not undeclared)

        scen_ok = all(ok for ok, _ in checks) and bool(gen or comp_change)
        total += len(checks)
        passed += sum(1 for ok, _ in checks if ok)
        rows.append((scen_name, sc["title"], scen_ok, f"./{scen_name}/"))

        # markdown section
        md.append(f"\n## {sc['title']}\n")
        md.append(f"**Verdict:** {'✅ all checks passed' if scen_ok else '⚠️ see checks'}\n")
        in_mixin = rel(PROJECT / 'src' / 'mixins' / mixin_name, RESULTS)
        in_comp = rel(comp_path, RESULTS)
        comp_name = sc["file"]
        out_composable = f"[composable: {gen.file_path.name}]({gen_link})" if gen_link else "_(none generated)_"
        out_component = f"[migrated: {comp_name}]({comp_link})" if comp_link else "_(no change)_"
        md.append("| Input | Output |")
        md.append("|---|---|")
        md.append(f"| [mixin: {mixin_name}]({in_mixin}) | {out_composable} |")
        md.append(f"| [component: {comp_name}]({in_comp}) | {out_component} |")
        md.append("")
        if report_link:
            md.append(f"📋 **[migration report]({report_link})**\n")
        md.append(f"- **used by component:** `{used or '—'}`")
        md.append(f"- **returned (public):** `{ret or '—'}`")
        md.append(f"- **private (declared, not returned):** `{private or '—'}`")
        md.append(f"- **dropped vs full-project:** `{dropped or '—'}`")
        md.append("")
        if gen:
            md.append("<details><summary>generated composable</summary>\n")
            md.append("```js")
            md.append(content.rstrip())
            md.append("```\n</details>\n")
        if comp_change:
            md.append("<details><summary>rewritten component</summary>\n")
            md.append("```vue")
            md.append(comp_change.new_content.rstrip())
            md.append("```\n</details>\n")
        if report_text:
            md.append("<details><summary>migration report</summary>\n")
            md.append("```md")
            md.append(report_text.rstrip())
            md.append("```\n</details>\n")
        md.append("**checks:**")
        for ok, label in checks:
            md.append(f"- {'✅' if ok else '❌'} {label}")

    # summary table at top
    summary = ["\n## Scenario index\n", "| # | Scenario | Verdict | Artifacts |", "|---|---|---|---|"]
    for i, (name, title, ok, link) in enumerate(rows, 1):
        summary.append(f"| {i} | {title} | {'✅' if ok else '⚠️'} | [{name}/]({link}) |")
    summary.append(f"\n**Total: {passed}/{total} checks passed across {len(rows)} scenarios.**\n")

    final = md[:3] + summary + md[3:]
    (RESULTS / "RESULTS.md").write_text("\n".join(final) + "\n")
    print(f"Wrote {RESULTS / 'RESULTS.md'}  ({passed}/{total} checks across {len(rows)} scenarios)")


if __name__ == "__main__":
    main()
