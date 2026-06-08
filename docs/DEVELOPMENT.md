# Development Notes — Intentions, Invariants & Lessons

This file is the project's memory. It exists so the next person (or AI) building
on `vue3-migration` inherits the *why*, not just the *what*: the behavior we want,
the mistakes we've already made, and the direction the tool is heading.

Read this before changing the engine. The [Architecture](ARCHITECTURE.md) doc
tells you how the code is shaped; this doc tells you why it's shaped that way and
where it tends to break.

---

## 1. What this tool is for

Vue 2 projects on mixins can't move to Vue 3's Composition API without rewriting
every mixin into a composable and updating every component that used it. Done by
hand across dozens or hundreds of components, that is slow and error-prone.

`vue3-migration` automates the mechanical 90%: it reads mixins, generates or
patches composables, rewrites components, and — crucially — **shows a full diff
and changes nothing until the developer says yes.** The remaining 10% (things
that genuinely need human judgment) is surfaced as clear, actionable warnings,
never silently skipped.

The target user is a developer mid-migration on a large, real codebase. They need
to trust the tool more than they need it to be clever. **Trust > cleverness** is
the guiding trade-off.

---

## 2. The prime directives (non-negotiable invariants)

These are the contracts the tool must always uphold. Most of our worst bugs were
violations of one of them.

1. **Preview before apply.** Every workflow returns a `MigrationPlan` of
   `FileChange` objects and renders a diff. Writing is a separate, explicit step
   gated on confirmation. Never write from inside analysis or transform code.

2. **Never leave a component broken.** If the tool can't produce a working
   replacement for a mixin, it must **not** remove that mixin. Skip the change and
   emit a warning instead. (We shipped the opposite once — see §4.2.)

3. **Idempotent.** Running the tool twice must be a no-op the second time, never a
   corruption. Re-running is how cautious users work. `tests/test_idempotency.py`
   guards this.

4. **No data loss on uncertainty.** When a transform can't confidently handle
   something, leave the original code unchanged and warn. A left-alone
   `this.$watch` the developer fixes by hand is fine; a mangled one is a bug.

5. **The three modes agree.** Full-project, single-component, and single-mixin
   migration must produce identical transforms for the same input.
   `tests/test_cross_flow_consistency.py` enforces this — they all converge on
   `run_scoped()` precisely so they can't diverge.

6. **Reports must be accurate.** A clickable `file:line` link that points at the
   wrong line, or a step for a composable that doesn't exist, erodes trust faster
   than a missing feature. Report accuracy is treated as correctness, not polish.

---

## 3. The defining constraint: no AST

All parsing is hand-rolled string scanning in `core/js_parser.py`. This was a
deliberate choice — zero parse dependencies, no Babel version treadmill, full
control, and source-preserving edits (we never pretty-print a round-trip).

The cost is equally real: **the string parser is the single largest source of
bugs in this project's history.** Almost every parser bug is one of two shapes:

- **False positives from non-code.** A pattern matched inside a string, comment,
  template literal, or regex. *The fix is almost always: route the scan through
  `skip_non_code()`.* If you add any pattern scan, ask first: "what happens when
  this text appears inside a string?"
- **Greedy / under-specified matching.** A regex that stops too early or eats too
  much (e.g. the non-greedy `<template>` fix, return-type annotations breaking
  method detection).

Before extending the parser, internalize that you are writing a miniature,
special-purpose tokenizer — not matching a regex against well-behaved input.

---

## 4. Hard-won lessons (the mistakes, by theme)

Each of these is a real bug we fixed. They recur; treat them as a checklist.

### 4.1 Classification subtleties — "uses" is not "defines"

The gap analysis in `MemberClassification` is deceptively tricky. Specific traps:

- **`watch` keys are not overrides.** A component that does `watch: { isOpen() {} }`
  is *observing* a mixin property, not defining it. We once excluded watched
  members from `setup()` because `extract_own_members` counted watch keys as the
  component's own. Only `data`, `computed`, and `methods` define/override members.
- **Kind matters, not just presence.** A name present in both mixin and composable
  can still be wrong if it's a `ref` in one and a `function` in the other. That's
  a `kind_mismatched` warning, not a clean match.
- **"Covered" means declared *and* returned.** A composable that declares a member
  but doesn't `return` it hasn't really provided it (`BLOCKED_NOT_RETURNED`).

### 4.2 Never remove a mixin you can't replace

The pipeline once removed mixin imports for *every* `READY` entry — including ones
where `injectable` was empty, leaving components with the mixin gone and nothing
in its place. Now three cases skip removal and warn instead:

- `skipped-lifecycle-only` — mixin has hooks but the component uses no members.
- `skipped-no-usage` — no mixin members are referenced.
- `skipped-all-overridden` — every used member is overridden by the component.

**Lesson:** "ready to migrate" must mean "we will actually inject a working
replacement," not merely "nothing blocks us."

### 4.3 Assignment-awareness for `this._private`

A `this._timer` not in `data()` is ambiguous. We first localized *all* such props
to `let _x = null` in the generated composable **and** flagged them as external
dependencies — a self-contradiction (clean composable, yet a red warning).

The reliable signal is **whether the mixin assigns the prop**:

- Assigned (`this._timer = …`) → mixin-owned scratch state → localize, no warning.
- Read-only (`f(this._injected)`) → component-provided → external dependency; leave
  it as `this._x` and keep the warning. Localizing to `null` would be a silent bug.

**Lesson — and the meta-lesson of this whole project:** the generator and the
warning system were making the *same* decision in two places and disagreed. They
now route through one shared helper (`find_internal_private_props`) so they
*can't* diverge. When two subsystems classify the same thing, give them one
source of truth. (The recent `MEMBER_KIND_LABELS` consolidation is the same
lesson applied to a duplicated constant.)

### 4.4 Incremental migration creates collisions

Real migrations are half-done. A component may already have a `setup()`, or two
composables may both export `loading`. Defenses, layered:

- Detect identifiers already declared in an existing `setup()` and exclude them
  from the injected destructure (`extract_setup_identifiers`), with a warning.
- Deduplicate names across multiple composables injected into one component.
- Detect `data()` ↔ `setup()` return collisions and link the report to the
  component's own declaration.

Assume the component is already partway migrated. Greenfield is the easy case.

### 4.5 The `this.$*` rewrite ordering

`rewrite_this_refs` (member refs) must run **before** `rewrite_this_dollar_refs`
(`$watch`, `$set`, …). The `$watch` rewrite passes the handler body through
unchanged *because* its `this.x` refs are already `x.value` by then. Reorder these
and handlers silently keep `this.` references. Preserve the order in any new flow.

### 4.6 Lifecycle hooks are full of small traps

Param extraction, inline (`created`) vs wrapped (`onMounted`) handling, multi-line
block atomicity when patching, and not duplicating an inlined body on re-run — each
has bitten us. When touching lifecycle code, re-run `test_idempotency.py` and
`test_lifecycle_converter.py` specifically.

### 4.7 Recent, concrete mistakes worth remembering

- **f-string backslash portability.** Several report headers built a separator
  with `f"… {' · '.join(parts)}"`, where the `·`/`—` were written as `·`/`—`
  escapes *inside* the f-string expression. A backslash inside an f-string
  expression is a `SyntaxError` before Python 3.12 (PEP 701) — so the package
  silently required 3.12+ despite advertising `>=3.9`. Fix: build the joined
  string in a plain statement first, then interpolate. **Lesson:** keep escapes
  out of f-string expressions, and remember `requires-python` is a promise.
- **Expected-failure tests must be `xfail`.** `test_typescript_failures.py`
  documented known parser gaps with plain `assert` — so they showed as 11 *failures*
  on every run, drowning the signal of a real regression. They're now
  `@pytest.mark.xfail(strict=False)`: the suite is green, the gaps are still
  documented, and the day the parser improves they flip to `XPASS` — a built-in
  reminder to delete the marker. **Lesson:** a test that is *supposed* to fail
  must say so to the runner, or it's just noise.

---

## 5. Known limitations (deliberate, documented)

These are understood gaps, not surprises. Most are pinned by tests.

- **TypeScript.** The string parser doesn't understand type annotations between a
  name and `=`, `as` assertions, `<Generic>` syntax, `this?.x` optional chaining,
  or `import type`. Eleven `xfail` tests in `tests/test_typescript_failures.py`
  pin exactly which constructs break. (Note: some TS cases — return types, param
  type stripping — *do* work and are plain passing tests.)
- **Factory-function mixins** (`export default () => ({ … })`) are detected and
  warned, not converted. Full support needs parameter capture and call-site arg
  forwarding.
- **Nested mixins** (a mixin with its own `mixins: []`) surface transitive members
  as warnings but aren't fully flattened.
- **`props`, `inject`, `provide`, `filters`** can't be auto-migrated — they need
  `defineProps()` / `inject()` / methods. The tool flags them with guidance.
- **`this.$emit`, `this.$refs`, `this.$parent`, `this.$options`** have no clean
  composable equivalent and are flagged as errors with the recommended pattern.

---

## 6. Direction & intentions

Where the tool is heading, roughly in priority order:

1. **An AST option for TS-heavy projects.** The single change that would unlock
   the most: an optional real parser (e.g. via a Node bridge — Babel/TS compiler)
   used when the string parser detects TypeScript. The `xfail` tests in
   `test_typescript_failures.py` are the acceptance criteria — they should flip to
   `XPASS` the day this lands. The string parser stays the default (zero-dep, fast).
2. **Divergence detection as a first-class verification step.** It already
   re-generates and diffs covered members; the direction is to make this the
   trusted answer to "did my hand-written composable actually port the logic?"
3. **Deeper `this.$*` auto-conversion** where a mechanical rewrite is unambiguous
   (the `$watch` work is the template), always with the "leave unchanged on doubt"
   fallback.
4. **Factory and nested-mixin support**, once the parser is robust enough that
   parameter/transitive analysis won't produce confident-but-wrong output.

Guardrails for all of the above: never trade away a prime directive (§2) for a
feature. A capability that occasionally corrupts a component is worse than not
having it.

---

## 7. How to extend safely — a checklist

Before you commit a change to the engine:

- [ ] Does any new text scan go through `skip_non_code()`? What happens if the
      pattern appears inside a string, comment, or template literal?
- [ ] If you classify or transform a member, is the decision made in **one** place
      shared by the generator, the warnings, and the report?
- [ ] Could this remove a mixin without injecting a replacement? (It must not.)
- [ ] Is it idempotent? Run `pytest tests/test_idempotency.py`.
- [ ] Do the three modes still agree? Run `pytest tests/test_cross_flow_consistency.py`.
- [ ] Are report line numbers / links still correct for the changed paths?
- [ ] For a known-unsupported case, did you add an `xfail` test (not a failing one)?
- [ ] Full suite green, `xfail` count unchanged unless you intended it.

### Conventions

- **Tests use real fixtures, no mocks** (`tests/fixtures/dummy_project/`). Add a
  fixture mixin/component for a new pattern rather than mocking the parser.
- **`uv`** manages the Python env; **`pytest tests/`** runs everything.
- **The `verify-migration` skill** (`.claude/skills/verify-migration/`) runs the
  real CLI end-to-end against a scenario and saves examinable before/after proof —
  use it to confirm a fix beyond unit tests.
- **Keep `package.json` and `pyproject.toml` versions in sync** (they drifted
  once — npm at 1.9.0, pyproject at 1.5.0).
