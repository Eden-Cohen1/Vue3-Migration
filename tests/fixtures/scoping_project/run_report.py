#!/usr/bin/env python3
"""Verification harness for the single-component composable-scoping feature.

Runs the real component migration flow (run_scoped with component_path) against
every scenario in this fixture project, compares the scoped composable against
the full-project output, and checks per-scenario + cross-cutting expectations.

Usage:
    python3 tests/fixtures/scoping_project/run_report.py
"""
import re
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT.parents[2]  # .../Vue3-Migration
sys.path.insert(0, str(REPO_ROOT))

from vue3_migration.models import MigrationConfig
from vue3_migration.workflows.auto_migrate_workflow import run, run_scoped


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------

def returned_members(content):
    m = re.search(r"return \{([^}]*)\}", content)
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def declared_names(content):
    names = re.findall(r"\b(?:const|let|var)\s+(\w+)\s*=", content)
    names += re.findall(r"\bfunction\s+(\w+)\s*\(", content)
    return set(names)


def code_body_only(content):
    """Strip comments, import lines, and the return statement, leaving code we
    can scan for member references."""
    lines = []
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("//"):
            continue
        if s.startswith("return {"):
            continue
        # strip trailing inline comment
        line = re.sub(r"//.*$", "", line)
        lines.append(line)
    return "\n".join(lines)


def referenced(name, body):
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", body) is not None


# --------------------------------------------------------------------------
# Scenario definitions: (component, title, expectations)
#   ret  = exact set the composable must return
#   decl = names that MUST be declared (superset check)
#   drop = names that must be neither declared nor returned
#   present / absent = substrings that must / must not appear in the file
# --------------------------------------------------------------------------

SCENARIOS = [
    dict(file="BasicSubset.vue", title="1. Basic subset + dead-code dropped",
         ret={"alpha", "useAlpha"}, decl={"alpha", "useAlpha"},
         drop={"beta", "gamma", "touchBeta"}),
    dict(file="Chain.vue", title="2. Transitive method chain (private helpers)",
         ret={"submit"}, decl={"submit", "validate", "sanitize", "errors"},
         drop={"standalone"}),
    dict(file="ComputedDeps.vue", title="3. Computed->computed->data closure",
         ret={"initials"}, decl={"initials", "fullName", "firstName", "lastName"},
         drop=set()),
    dict(file="LifecyclePreserved.vue", title="4. mounted preserved, pulls in deps",
         ret={"visible", "toggle"}, decl={"visible", "toggle", "init", "config"},
         drop=set(), present=["onMounted("]),
    dict(file="CreatedInlined.vue", title="5. created inlined, pulls in deps",
         ret={"bar"}, decl={"bar", "setup", "ready"}, drop=set()),
    dict(file="SideEffects.vue", title="6. Unused $emit/$refs/$router dropped (no warnings)",
         ret={"tick", "ticks"}, decl={"tick", "ticks"},
         drop={"notify", "focusInput", "goHome"},
         absent=["$emit", "$refs", "$router"]),
    dict(file="UsedEmit.vue", title="7. Used $emit method KEPT (warning kept)",
         ret={"announce"}, decl={"announce", "count"}, drop=set(),
         present=["emit"]),
    dict(file="WatchScoped.vue", title="8. Watch scoped to target member",
         ret={"query"}, decl={"query"}, drop={"page"}, absent=["page"]),
    dict(file="Debounce.vue", title="9. this._timer hoisted to local let",
         ret={"text", "setValue"}, decl={"text", "setValue", "_timer"},
         drop=set(), present=["let _timer"], absent=["this._timer"]),
    dict(file="ExternalImports.vue", title="10. External imports follow scoping",
         ret={"show"}, decl={"show", "stamp"}, drop={"process"},
         present=["formatDate"], absent=["crunch"]),
    dict(file="WordBoundary.vue", title="11. Word-boundary (search vs searchResults)",
         ret={"doSearch"}, decl={"doSearch", "search"}, drop={"searchResults"},
         absent=["searchResults"]),
    dict(file="MutualRecursion.vue", title="12. Mutual recursion terminates",
         ret={"ping"}, decl={"ping", "pong"}, drop={"lonely"}),
    dict(file="UsesEverything.vue", title="13. Uses everything => no-op vs full",
         ret={"x", "dbl", "inc"}, decl={"x", "dbl", "inc"}, drop=set(),
         equals_full=True),
    dict(file="TemplateOnly.vue", title="14. Template-only usage detected",
         ret={"label"}, decl={"label"}, drop={"hidden"}, absent=["hidden"]),
    dict(file="SideEffectOnly.vue", title="15. Side-effect-only (empty return)",
         ret=set(), decl={"logVisit", "logged"}, drop=set(),
         present=["onMounted("]),
    dict(file="WatchRef.vue", title="16. Watch handler body refs followed by closure",
         ret={"keyword"}, decl={"keyword", "runSearch", "results"}, drop=set()),
    dict(file="ReadOnlyUnderscore.vue", title="17. Read-only this._x stays external (not localized)",
         ret={"render"}, decl={"render"}, drop=set(),
         present=["this._injected", "external dep"], absent=["let _injected"]),
]


def find_generated(plan):
    """Return the single generated (new-file) composable change in a plan."""
    gen = [c for c in plan.composable_changes
           if c.has_changes and c.original_content == ""]
    return gen[0] if gen else None


def main():
    cfg = MigrationConfig(project_root=PROJECT)
    with patch("builtins.print"):
        full_plan = run(PROJECT, cfg)
    full_by_name = {c.file_path.name: c.new_content
                    for c in full_plan.composable_changes if c.has_changes}

    total_checks = 0
    failed_checks = 0
    findings = []

    for sc in SCENARIOS:
        comp_path = next(PROJECT.rglob(sc["file"]))
        with patch("builtins.print"):
            plan = run_scoped(PROJECT, cfg, component_path=comp_path)
        gen = find_generated(plan)

        print("=" * 78)
        print(sc["title"])
        print(f"   component: {sc['file']}")
        print("-" * 78)
        if gen is None:
            print("   !! no composable generated")
            findings.append((sc["title"], "no composable generated"))
            continue

        content = gen.new_content
        print(content.rstrip())
        print("-" * 78)

        ret = set(returned_members(content))
        decl = declared_names(content)
        full_content = full_by_name.get(gen.file_path.name, "")
        full_decl = declared_names(full_content)
        dropped_actual = full_decl - decl
        body = code_body_only(content)

        def check(label, ok):
            nonlocal total_checks, failed_checks
            total_checks += 1
            mark = "PASS" if ok else "FAIL"
            if not ok:
                failed_checks += 1
                findings.append((sc["title"], label))
            print(f"   [{mark}] {label}")
            return ok

        is_edge = sc.get("edge")

        # returned set
        check(f"returns exactly {sorted(sc['ret'])} (got {sorted(ret)})",
              ret == sc["ret"])
        # declared superset
        missing_decl = sc["decl"] - decl
        check(f"declares {sorted(sc['decl'])} (missing {sorted(missing_decl)})",
              not missing_decl)
        # dropped
        if sc["drop"]:
            bad = (sc["drop"] & decl) | (sc["drop"] & ret)
            check(f"drops {sorted(sc['drop'])} (leaked {sorted(bad)})", not bad)
        # full-equality
        if sc.get("equals_full"):
            check("scoped content == full-project content",
                  content == full_content)
        # substring present/absent
        for s in sc.get("present", []):
            check(f"contains {s!r}", s in content)
        for s in sc.get("absent", []):
            check(f"does NOT contain {s!r}", s not in content)

        # CROSS-CUTTING INVARIANT: any mixin member referenced in the code body
        # must be declared. Catches "kept code references a dropped member".
        undeclared_refs = sorted(
            n for n in (full_decl | sc.get("drop", set()))
            if n not in decl and referenced(n, body)
        )
        ok = not undeclared_refs
        label = (f"no undeclared member referenced in body "
                 f"(violations: {undeclared_refs})")
        if is_edge and not ok:
            # Edge probe: surface as a FINDING rather than a hard failure.
            print(f"   [EDGE] {label}")
            findings.append((sc["title"],
                             f"INVARIANT VIOLATION: {undeclared_refs} referenced but not declared"))
        else:
            check(label, ok)
        print()

    print("=" * 78)
    print(f"SUMMARY: {total_checks - failed_checks}/{total_checks} checks passed, "
          f"{failed_checks} failed.")
    if findings:
        print("\nFindings to review:")
        for title, f in findings:
            print(f"  - [{title}] {f}")
    return 1 if failed_checks else 0


if __name__ == "__main__":
    sys.exit(main())
