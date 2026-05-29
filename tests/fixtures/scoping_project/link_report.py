#!/usr/bin/env python3
"""Build SCENARIOS.md: per scenario, three line-anchored links (component,
the unused member in the mixin, the composable) + a short explanation of why
the result is what we expected.

Two outcomes are distinguished:
  - DROPPED  : member is unused by the component AND not a dependency of any
               used member/lifecycle hook -> absent from the composable entirely.
  - PRIVATE  : member is unused by the component but a used member/lifecycle
               hook depends on it -> generated internally, excluded from `return`.

    python3 tests/fixtures/scoping_project/link_report.py
"""
import re
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_report import PROJECT, SCENARIOS, returned_members, declared_names, find_generated
from vue3_migration.models import MigrationConfig
from vue3_migration.workflows.auto_migrate_workflow import run_scoped

RESULTS = PROJECT.parent / "scoping_results"


def line_of(text: str, pattern: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line):
            return i
    return None


def member_decl_line_in_mixin(src: str, name: str) -> int | None:
    # data: `name: ...`  /  method|computed: `name(...)`
    return (line_of(src, rf"^\s*{re.escape(name)}\s*[:(]")
            or line_of(src, rf"(?<!\w){re.escape(name)}(?!\w)"))


def member_decl_line_in_composable(src: str, name: str) -> int | None:
    return (line_of(src, rf"\b(?:const|let|var)\s+{re.escape(name)}\b")
            or line_of(src, rf"\bfunction\s+{re.escape(name)}\s*\("))


def rel(target: Path) -> str:
    import os
    return os.path.relpath(target, RESULTS)


def main():
    cfg = MigrationConfig(project_root=PROJECT)
    md = ["# Per-scenario proof: unused members vs the generated composable\n",
          "For each scenario: the component, the mixin (anchored to a member the "
          "component does **not** use), and the generated composable. The note "
          "explains whether that member was **dropped** (absent — not a dependency "
          "of anything used) or kept **private** (a used member/lifecycle depends "
          "on it, so it's generated but excluded from `return`).\n"]

    for sc in SCENARIOS:
        comp_path = next(PROJECT.rglob(sc["file"]))
        with patch("builtins.print"):
            plan = run_scoped(PROJECT, cfg, component_path=comp_path)
        gen = find_generated(plan)
        entry = plan.entries_by_component[0][1][0]
        mixin_path = entry.mixin_path
        mixin_src = mixin_path.read_text()
        content = gen.new_content if gen else ""

        used = set(entry.used_members)
        all_names = entry.members.all_names
        unused = [m for m in all_names if m not in used]
        ret = set(returned_members(content))
        decl = declared_names(content) - {gen.file_path.stem if gen else ""}

        # classify unused members
        dropped = [m for m in unused if m not in decl]
        private = [m for m in unused if m in decl and m not in ret]

        scen = Path(sc["file"]).stem
        comp_file = RESULTS / scen / sc["file"]
        comp_js = RESULTS / scen / (gen.file_path.name if gen else "")

        comp_link = rel(comp_file) if comp_file.exists() else rel(comp_path)
        js_link = rel(comp_js) if gen else None

        # choose representative member: prefer a fully-dropped one
        ret_line = line_of(content, r"return\s*\{") if content else None
        if dropped:
            member = dropped[0]
            kind = "DROPPED"
            mline = member_decl_line_in_mixin(mixin_src, member)
            js_anchor = f"#L{ret_line}" if ret_line else ""
            why = (f"`{member}` is declared in the mixin but the component never "
                   f"references it, and no used member/lifecycle depends on it. "
                   f"Result: it is **absent from the composable** — never generated. "
                   f"Compare with the composable's `return` (line {ret_line}): `{member}` isn't there, "
                   f"nor anywhere in the file. Other dropped: {dropped[1:] or 'none'}.")
        elif private:
            member = private[0]
            kind = "PRIVATE"
            mline = member_decl_line_in_mixin(mixin_src, member)
            cline = member_decl_line_in_composable(content, member)
            js_anchor = f"#L{cline}" if cline else ""
            why = (f"`{member}` is unused by the component directly, but a used member "
                   f"or lifecycle hook depends on it — so it's **generated as a private "
                   f"helper** (declared at composable line {cline}) and deliberately "
                   f"**left out of `return`** (line {ret_line}). The component can't see it.")
        else:
            member = "—"
            kind = "NONE"
            mline = None
            js_anchor = ""
            why = ("The component uses every member, so nothing is dropped or hidden: "
                   "the scoped composable equals the full-project output (control case).")

        mixin_anchor = f"#L{mline}" if mline else ""
        md.append(f"\n### {sc['title']}")
        links = [f"[component]({comp_link})",
                 f"[mixin → `{member}`]({rel(mixin_path)}{mixin_anchor})"]
        if js_link:
            links.append(f"[composable]({js_link}{js_anchor})")
        md.append(" · ".join(links))
        md.append(f"\n**[{kind}]** {why}")

    out = RESULTS / "SCENARIOS.md"
    out.write_text("\n".join(md) + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
