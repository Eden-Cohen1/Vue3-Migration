# scoping_project — single-component composable-scoping harness

A small, self-contained Vue project used to verify the **component flow**'s
member scoping: when migrating one component, the generated composable should
contain only the members that component needs (plus their transitive internal
dependencies), and the migration report should reflect that.

Each `src/components/*.vue` is one scenario, paired with one `src/mixins/*.js`.
The mixins deliberately use cleanly auto-migratable constructs so the signal
reflects *scoping*, not warning noise — except three that plant specific
patterns on purpose (`sideEffectsMixin` = unused `$emit`/`$refs`/`$router` that
must be dropped, `usedEmitMixin` = a used `$emit` that must be kept + flagged,
`debounceMixin` = `this._timer` hoisting). Realistic, messy mixins live in
`../dummy_project/`.

## Scripts

```bash
# Assertion harness — runs run_scoped per scenario, checks expectations.
python3 tests/fixtures/scoping_project/run_report.py        # -> 70/70 checks

# Regenerate the human-readable artifacts (written to ../scoping_results/,
# which is git-ignored): per-scenario composable/component/report + indexes.
python3 tests/fixtures/scoping_project/write_results.py     # RESULTS.md + reports
python3 tests/fixtures/scoping_project/link_report.py       # SCENARIOS.md (linked proofs)
```

`run_report.py` is the source of truth; `write_results.py` / `link_report.py`
only materialize browsable docs. Output goes to `tests/fixtures/scoping_results/`
(git-ignored — reproducible, not committed). Inputs in `src/` are never mutated.
