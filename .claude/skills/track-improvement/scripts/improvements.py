#!/usr/bin/env python3
"""Backlog manager for IMPROVEMENTS.md — the vue3-migration improvement log.

IMPROVEMENTS.md is the single source of truth: a human-readable backlog whose
issues are wrapped in HTML-comment delimiters so this script can add, list,
look up, and DELETE-on-solve them reliably without a sidecar database.

Each issue is one block:

    <!-- ISSUE id=CORR-1 severity=high category=correctness status=open discovered=2026-06-08 source=review-migration-output -->
    ### CORR-1 · <title>
    ...rich markdown body (Symptom / Reproduce / Root cause / Why / Fix / Verify)...
    <!-- /ISSUE id=CORR-1 -->

A regenerated `<!-- INDEX -->` table at the top gives an at-a-glance, grouped view.

Commands:
    init                         create IMPROVEMENTS.md scaffold (no-op if present)
    add [--file F | --stdin]     add issue(s) from a JSON object or array; prints new IDs
    close ID [ID ...]            DELETE solved issue block(s) + reindex (use when fixed)
    status ID <open|wip|blocked> set an issue's status
    get ID                       print one issue's full block
    list [--category C]          list issues (id · sev · category · title · status)
    reindex                      rebuild the index table from the blocks
    validate                     parse all blocks; check unique IDs + required fields

JSON issue spec (for `add`):
    {"category":"correctness","severity":"high","title":"...",
     "symptom":"...","repro":"...","root_cause":"...","impact":"...",
     "fix":"...","verify":"...","source":"manual","date":"YYYY-MM-DD"}
  category ∈ correctness|report|codegen|dx|perf|test|docs ; severity ∈ high|med|low
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

CATEGORY_ORDER = ["correctness", "report", "codegen", "dx", "perf", "test", "docs"]
PREFIX = {"correctness": "CORR", "report": "RPT", "codegen": "CG", "dx": "DX",
          "perf": "PERF", "test": "TEST", "docs": "DOCS"}
LABEL = {"correctness": "Correctness / Behavior", "report": "Report Accuracy",
         "codegen": "Codegen Quality", "dx": "DX / Ergonomics",
         "perf": "Performance", "test": "Testing", "docs": "Documentation"}
SEV_ICON = {"high": "🔴", "med": "🟠", "low": "🟡"}
SEV_ORDER = {"high": 0, "med": 1, "low": 2}
BODY_FIELDS = [  # (key, heading)
    ("symptom", "Symptom"), ("repro", "Reproduce"), ("root_cause", "Root cause / likely source"),
    ("impact", "Why it matters"), ("fix", "Fix direction"), ("verify", "Verify when fixed"),
]

ISSUE_RE = re.compile(r"<!-- ISSUE (?P<attrs>[^>]*?)-->\n(?P<body>.*?)\n<!-- /ISSUE id=(?P<cid>[\w-]+) -->", re.S)
INDEX_RE = re.compile(r"<!-- INDEX:START -->.*?<!-- INDEX:END -->", re.S)
ISSUES_END = "<!-- ISSUES:END -->"

SCAFFOLD = """# IMPROVEMENTS.md — vue3-migration backlog

Living backlog of bugs and quality/DX improvements **in the vue3-migration tool**
(not in any project it migrates). Findings come from the `review-migration-output`
skill, from real runs, and from anything we stumble across. Add issues with the
`track-improvement` skill; **delete an issue the moment it's fixed**.

**How to pick one up (cold start):** scan the Index → read the block → follow
**Reproduce → Fix direction → Verify when fixed**. Every block is self-contained:
it names the symptom with file:line, the likely tool source, and how to confirm a
fix. Severity: 🔴 high · 🟠 med · 🟡 low.

**Conventions:** IDs are stable (prefix per category: CORR/RPT/CG/DX/PERF/TEST/DOCS) —
reference them in commits (`fix(<ID>): …`). Demo specimen for repro:
`/Users/base/Projects/dummy_vue_migration_project`.
Do not hand-edit the Index; run `track-improvement` (or `improvements.py reindex`).

## Index

<!-- INDEX:START -->
_(empty — add issues with the track-improvement skill)_
<!-- INDEX:END -->

## Issues

<!-- ISSUES:START -->

<!-- ISSUES:END -->
"""


def repo_root() -> Path:
    for d in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (d / "vue3_migration").is_dir() and (d / "pyproject.toml").is_file():
            return d
    return Path.cwd()


def imp_path() -> Path:
    return repo_root() / "IMPROVEMENTS.md"


def parse_attrs(s: str) -> dict:
    return dict(kv.split("=", 1) for kv in s.split() if "=" in kv)


def parse_issues(text: str) -> list[dict]:
    out = []
    for m in ISSUE_RE.finditer(text):
        a = parse_attrs(m.group("attrs"))
        a["body"] = m.group("body")
        a["raw"] = m.group(0)
        out.append(a)
    return out


def next_id(issues: list[dict], category: str) -> str:
    pfx = PREFIX[category]
    nums = [int(i["id"].split("-")[1]) for i in issues
            if i.get("id", "").startswith(pfx + "-") and i["id"].split("-")[1].isdigit()]
    return f"{pfx}-{(max(nums) + 1) if nums else 1}"


def render_block(issue: dict) -> str:
    attrs = (f"id={issue['id']} severity={issue['severity']} category={issue['category']} "
             f"status={issue.get('status', 'open')} discovered={issue['discovered']} "
             f"source={issue.get('source', 'manual')}")
    icon = SEV_ICON.get(issue["severity"], "")
    lines = [f"### {issue['id']} · {issue['title']}", "",
             f"**{icon} {issue['severity']}** · {LABEL[issue['category']]} · status: `{issue.get('status', 'open')}`", ""]
    for key, heading in BODY_FIELDS:
        val = (issue.get(key) or "_(not provided)_").strip()
        lines += [f"**{heading}**", "", val, ""]
    body = "\n".join(lines).rstrip()
    return f"<!-- ISSUE {attrs} -->\n{body}\n<!-- /ISSUE id={issue['id']} -->"


def build_index(issues: list[dict]) -> str:
    if not issues:
        return "<!-- INDEX:START -->\n_(empty — add issues with the track-improvement skill)_\n<!-- INDEX:END -->"
    ordered = sorted(issues, key=lambda i: (CATEGORY_ORDER.index(i["category"]) if i["category"] in CATEGORY_ORDER else 99,
                                            SEV_ORDER.get(i["severity"], 9), i["id"]))
    rows = ["| ID | Sev | Category | Title | Status |", "|----|-----|----------|-------|--------|"]
    for i in ordered:
        title = re.sub(r"\s+", " ", _title_of(i)).strip()
        rows.append(f"| [{i['id']}](#{i['id'].lower()}) | {SEV_ICON.get(i['severity'],'')} {i['severity']} "
                    f"| {LABEL.get(i['category'], i['category'])} | {title} | {i.get('status','open')} |")
    counts = f"\n\n_{len(issues)} open: " + ", ".join(
        f"{sum(1 for i in issues if i['severity']==s)} {s}" for s in ['high', 'med', 'low']) + "._"
    return "<!-- INDEX:START -->\n" + "\n".join(rows) + counts + "\n<!-- INDEX:END -->"


def _title_of(issue: dict) -> str:
    m = re.search(r"^###\s+\S+\s+·\s+(.*)$", issue["body"], re.M)
    return m.group(1).strip() if m else issue.get("id", "")


def reindex(text: str) -> str:
    issues = parse_issues(text)
    return INDEX_RE.sub(lambda _: build_index(issues), text)


def insert_block(text: str, block: str, category: str) -> str:
    """Insert a block in category order: just before the first block of a
    higher-ordered category, else at the end of the issues section."""
    my = CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else 99
    for i in parse_issues(text):
        ci = CATEGORY_ORDER.index(i["category"]) if i["category"] in CATEGORY_ORDER else 99
        if ci > my:
            return text.replace(i["raw"], block + "\n\n" + i["raw"], 1)
    return text.replace(ISSUES_END, block + "\n\n" + ISSUES_END, 1)


def load_specs(args) -> list[dict]:
    raw = Path(args.file).read_text() if args.file else sys.stdin.read()
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


def cmd_init(_args):
    p = imp_path()
    if p.exists():
        print(f"exists: {p}")
        return
    p.write_text(SCAFFOLD)
    print(f"created: {p}")


def cmd_add(args):
    p = imp_path()
    if not p.exists():
        p.write_text(SCAFFOLD)
    text = p.read_text()
    today = datetime.date.today().isoformat()
    new_ids = []
    for spec in load_specs(args):
        cat = spec["category"]
        if cat not in PREFIX:
            sys.exit(f"unknown category '{cat}' (allowed: {', '.join(PREFIX)})")
        if spec.get("severity") not in SEV_ICON:
            sys.exit(f"severity must be one of {list(SEV_ICON)}")
        issue = {
            "id": spec.get("id") or next_id(parse_issues(text), cat),
            "severity": spec["severity"], "category": cat, "status": spec.get("status", "open"),
            "discovered": spec.get("date", today), "source": spec.get("source", "manual"),
            "title": spec["title"],
            **{k: spec.get(k) for k, _ in BODY_FIELDS},
        }
        text = insert_block(text, render_block(issue), cat)
        new_ids.append(issue["id"])
    text = reindex(text)
    p.write_text(text)
    print("added: " + ", ".join(new_ids))


def cmd_close(args):
    p = imp_path()
    text = p.read_text()
    issues = {i["id"]: i for i in parse_issues(text)}
    closed = []
    for cid in args.ids:
        if cid not in issues:
            print(f"not found: {cid}", file=sys.stderr)
            continue
        block = issues[cid]["raw"]
        # remove the block and collapse the surrounding blank lines it leaves
        text = re.sub(r"\n*" + re.escape(block) + r"\n*", "\n\n", text, count=1)
        closed.append(cid)
    text = reindex(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    p.write_text(text)
    print("closed (deleted): " + (", ".join(closed) or "(none)"))


def cmd_status(args):
    p = imp_path()
    text = p.read_text()
    issues = {i["id"]: i for i in parse_issues(text)}
    if args.id not in issues:
        sys.exit(f"not found: {args.id}")
    if args.value not in ("open", "wip", "blocked"):
        sys.exit("status must be open|wip|blocked")
    old = issues[args.id]["raw"]
    new = re.sub(r"(status=)\w+", rf"\g<1>{args.value}", old, count=1)
    new = re.sub(r"(status: `)\w+(`)", rf"\g<1>{args.value}\g<2>", new, count=1)
    text = reindex(text.replace(old, new, 1))
    p.write_text(text)
    print(f"{args.id} -> {args.value}")


def cmd_get(args):
    for i in parse_issues(imp_path().read_text()):
        if i["id"] == args.id:
            print(i["raw"])
            return
    sys.exit(f"not found: {args.id}")


def cmd_list(args):
    issues = parse_issues(imp_path().read_text())
    if args.category:
        issues = [i for i in issues if i["category"] == args.category]
    issues.sort(key=lambda i: (CATEGORY_ORDER.index(i["category"]) if i["category"] in CATEGORY_ORDER else 99,
                               SEV_ORDER.get(i["severity"], 9), i["id"]))
    for i in issues:
        print(f"{i['id']:<8} {SEV_ICON.get(i['severity'],''):<2} {i['severity']:<4} "
              f"{i['category']:<12} [{i.get('status','open')}] {_title_of(i)}")
    print(f"\n{len(issues)} issue(s).")


def cmd_reindex(_args):
    p = imp_path()
    p.write_text(reindex(p.read_text()))
    print("reindexed.")


def cmd_validate(_args):
    text = imp_path().read_text()
    issues = parse_issues(text)
    errs = []
    seen = set()
    for i in issues:
        if i["id"] in seen:
            errs.append(f"duplicate id: {i['id']}")
        seen.add(i["id"])
        if i["category"] not in PREFIX:
            errs.append(f"{i['id']}: bad category {i['category']}")
        if i["severity"] not in SEV_ICON:
            errs.append(f"{i['id']}: bad severity {i['severity']}")
        for key, heading in BODY_FIELDS:
            if f"**{heading}**" not in i["body"]:
                errs.append(f"{i['id']}: missing section '{heading}'")
    if "<!-- INDEX:START -->" not in text or "<!-- ISSUES:START -->" not in text:
        errs.append("missing INDEX/ISSUES markers")
    if errs:
        print("INVALID:\n  " + "\n  ".join(errs))
        sys.exit(1)
    print(f"OK: {len(issues)} issue(s), all blocks valid, IDs unique.")


def main():
    ap = argparse.ArgumentParser(description="Manage IMPROVEMENTS.md")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    a = sub.add_parser("add"); a.add_argument("--file"); a.add_argument("--stdin", action="store_true"); a.set_defaults(fn=cmd_add)
    c = sub.add_parser("close"); c.add_argument("ids", nargs="+"); c.set_defaults(fn=cmd_close)
    s = sub.add_parser("status"); s.add_argument("id"); s.add_argument("value"); s.set_defaults(fn=cmd_status)
    g = sub.add_parser("get"); g.add_argument("id"); g.set_defaults(fn=cmd_get)
    li = sub.add_parser("list"); li.add_argument("--category"); li.set_defaults(fn=cmd_list)
    sub.add_parser("reindex").set_defaults(fn=cmd_reindex)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
