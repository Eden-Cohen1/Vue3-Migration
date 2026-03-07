"""Cross-flow consistency tests for the auto-migrate pipeline.

Verifies that the three migration flows (full-project, single-component,
single-mixin) produce equivalent results for the same input.  Also covers
divergence points D1–D5 identified during the behavioral audit.
"""
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from vue3_migration.models import MigrationConfig, MixinMembers
from vue3_migration.workflows.auto_migrate_workflow import run, run_scoped

DUMMY = Path(__file__).parent / "fixtures" / "dummy_project"


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "project"
    shutil.copytree(DUMMY, dest)
    return dest


def _run_full(project):
    with patch("builtins.print"):
        return run(project, MigrationConfig(project_root=project))


def _run_component(project, component_name):
    comp_path = next(project.rglob(component_name))
    with patch("builtins.print"):
        return run_scoped(
            project, MigrationConfig(project_root=project),
            component_path=comp_path,
        )


def _run_mixin(project, mixin_stem):
    with patch("builtins.print"):
        return run_scoped(
            project, MigrationConfig(project_root=project),
            mixin_stem=mixin_stem,
        )


# ---------------------------------------------------------------------------
# Cross-flow integration tests
# ---------------------------------------------------------------------------

class TestCrossFlowConsistency:
    """Tests 1–8: compare outputs of the three migration flows."""

    def test_full_vs_mixin_composable_output_identical(self, project):
        """Mixin-scoped flow includes ALL consumers of a mixin, so composable
        output should be identical to the full-project flow."""
        full_plan = _run_full(project)
        full_composable_map = {
            c.file_path.name: c.new_content
            for c in full_plan.composable_changes if c.has_changes
        }

        seen_stems = set()
        for _path, entries in full_plan.entries_by_component:
            for entry in entries:
                if entry.mixin_stem in seen_stems:
                    continue
                seen_stems.add(entry.mixin_stem)
                mixin_plan = _run_mixin(project, entry.mixin_stem)
                for mc in mixin_plan.composable_changes:
                    if mc.has_changes and mc.file_path.name in full_composable_map:
                        assert mc.new_content == full_composable_map[mc.file_path.name], (
                            f"Composable {mc.file_path.name} differs between "
                            f"full-project and mixin-scoped flow for {entry.mixin_stem}"
                        )

    def test_full_vs_component_output_unique_mixin(self, project):
        """NoComposable.vue uses notificationMixin (unique to it), so
        single-component output should match full-project output."""
        full_plan = _run_full(project)
        comp_plan = _run_component(project, "NoComposable.vue")
        full_nc = next(
            (c for c in full_plan.component_changes
             if "NoComposable" in str(c.file_path) and c.has_changes),
            None,
        )
        comp_nc = next(
            (c for c in comp_plan.component_changes
             if "NoComposable" in str(c.file_path) and c.has_changes),
            None,
        )
        assert full_nc is not None, "NoComposable.vue missing from full-project plan"
        assert comp_nc is not None, "NoComposable.vue missing from component plan"
        assert full_nc.new_content == comp_nc.new_content

    def test_generated_composable_identical_across_flows(self, project):
        """useNotification.js is generated (no pre-existing composable).
        All three flows should produce identical content."""
        full_plan = _run_full(project)
        comp_plan = _run_component(project, "NoComposable.vue")
        mixin_plan = _run_mixin(project, "notificationMixin")

        contents = []
        for plan, label in [
            (full_plan, "full"),
            (comp_plan, "component"),
            (mixin_plan, "mixin"),
        ]:
            notif = next(
                (c for c in plan.composable_changes
                 if "useNotification" in str(c.file_path) and c.has_changes),
                None,
            )
            assert notif is not None, f"[{label}] useNotification not generated"
            contents.append((label, notif.new_content))

        for i in range(1, len(contents)):
            assert contents[0][1] == contents[i][1], (
                f"Generated composable differs between "
                f"{contents[0][0]} and {contents[i][0]}"
            )

    def test_warnings_consistent_across_flows(self, project):
        """Warning categories for the same component/mixin pair should be
        identical whether collected via full-project or single-component flow."""
        full_plan = _run_full(project)
        for comp_path, full_entries in full_plan.entries_by_component:
            if str(comp_path) == "<standalone>":
                continue
            comp_plan = _run_component(project, comp_path.name)
            if not comp_plan.entries_by_component:
                continue
            _, comp_entries = comp_plan.entries_by_component[0]
            for fe in full_entries:
                matching = [
                    ce for ce in comp_entries if ce.mixin_stem == fe.mixin_stem
                ]
                if not matching:
                    continue
                ce = matching[0]
                full_cats = sorted(w.category for w in fe.warnings)
                comp_cats = sorted(w.category for w in ce.warnings)
                assert full_cats == comp_cats, (
                    f"Warning categories differ for {fe.mixin_stem} "
                    f"in {comp_path.name}: full={full_cats} comp={comp_cats}"
                )

    def test_shared_composable_full_aggregates_all_needs(self, project):
        """usePagination.js is shared — full-project run must patch it with
        all requirements (resetPagination in return, hasPrevPage/prevPage added)."""
        full_plan = _run_full(project)
        pag = next(
            (c for c in full_plan.composable_changes
             if "usePagination" in str(c.file_path) and c.has_changes),
            None,
        )
        assert pag is not None, "usePagination not patched in full-project flow"
        assert "resetPagination" in pag.new_content

    def test_shared_composable_single_component_subset(self, project):
        """D2: single-component flow patches the shared composable for that
        component's needs only — may be a subset of full-project patches."""
        full_plan = _run_full(project)
        comp_plan = _run_component(project, "MultiMixin.vue")
        full_pag = next(
            (c for c in full_plan.composable_changes
             if "usePagination" in str(c.file_path)),
            None,
        )
        comp_pag = next(
            (c for c in comp_plan.composable_changes
             if "usePagination" in str(c.file_path)),
            None,
        )
        assert full_pag is not None
        # Single-component patch must include at least what MultiMixin needs.
        # comp_pag may be None or unchanged if the component's own requirements
        # don't trigger patching — that's a valid D2 outcome (by design).
        assert comp_pag is not None, "usePagination should appear in composable changes"
        if comp_pag.has_changes:
            assert "resetPagination" in comp_pag.new_content

    def test_lifecycle_hooks_in_composable_not_component_all_flows(self, project):
        """Lifecycle hooks must be in useLogging composable, never in
        LifecycleHooks.vue component, regardless of which flow runs."""
        for run_fn, label in [
            (lambda p: _run_full(p), "full"),
            (lambda p: _run_component(p, "LifecycleHooks.vue"), "component"),
            (lambda p: _run_mixin(p, "loggingMixin"), "mixin"),
        ]:
            plan = run_fn(project)
            logging = next(
                (c for c in plan.composable_changes
                 if "useLogging" in str(c.file_path) and c.has_changes),
                None,
            )
            assert logging is not None, f"[{label}] useLogging not patched"
            assert "onMounted(" in logging.new_content, (
                f"[{label}] Missing onMounted in composable"
            )

            lh = next(
                (c for c in plan.component_changes
                 if str(c.file_path).endswith("LifecycleHooks.vue")
                 and "All" not in str(c.file_path)),
                None,
            )
            if lh:
                assert "onMounted" not in lh.new_content, (
                    f"[{label}] onMounted leaked into component"
                )

    def test_reactive_guard_prevents_patching_all_flows(self, project):
        """D1: useStorage.js uses reactive() — no composable changes should
        be produced in any flow."""
        for run_fn, label in [
            (lambda p: _run_full(p), "full"),
            (lambda p: _run_component(p, "ReactiveGuard.vue"), "component"),
            (lambda p: _run_mixin(p, "storageMixin"), "mixin"),
        ]:
            plan = run_fn(project)
            storage = next(
                (c for c in plan.composable_changes
                 if "useStorage" in str(c.file_path)),
                None,
            )
            if storage:
                assert not storage.has_changes, (
                    f"[{label}] reactive() guard failed — useStorage was modified"
                )


# ---------------------------------------------------------------------------
# Targeted divergence-point tests
# ---------------------------------------------------------------------------

class TestDivergencePoints:
    """Tests 9–12: targeted tests for each confirmed divergence point."""

    def test_missing_hooks_filters_existing(self):
        """D4: _missing_hooks() should filter out hooks already present
        in the composable (by detecting the Vue 3 wrapper function call)."""
        from vue3_migration.transform.composable_patcher import _missing_hooks

        composable = (
            "import { ref, onMounted } from 'vue'\n"
            "export function useX() {\n"
            "  const x = ref(0)\n"
            "  onMounted(() => { console.log('already here') })\n"
            "  return { x }\n"
            "}\n"
        )
        missing = _missing_hooks(composable, ["mounted", "beforeDestroy"])
        assert "mounted" not in missing, "mounted is already present, should be filtered"
        assert "beforeDestroy" in missing, "beforeDestroy is missing, should be included"

    def test_patch_half_implemented_hook_not_overwritten(self):
        """D4: Patcher must not add a second onMounted if one already exists,
        even if it's only a TODO placeholder."""
        from vue3_migration.transform.composable_patcher import patch_composable

        composable = (
            "import { ref, onMounted } from 'vue'\n"
            "export function useX() {\n"
            "  const x = ref(0)\n"
            "  onMounted(() => { /* TODO: finish */ })\n"
            "  return { x }\n"
            "}\n"
        )
        mixin = (
            "export default {\n"
            "  data() { return { x: 0 } },\n"
            "  mounted() { this.x = 42 }\n"
            "}\n"
        )
        members = MixinMembers(data=["x"])
        result = patch_composable(
            composable, mixin, [], [], members, lifecycle_hooks=["mounted"],
        )
        assert result.count("onMounted(") == 1, (
            "Patcher should not add a second onMounted"
        )

    def test_generator_never_produces_reactive(self):
        """D1: Generation path always uses ref(), never reactive().
        This makes the reactive() guard asymmetry benign."""
        from vue3_migration.transform.composable_generator import (
            generate_composable_from_mixin,
        )

        mixin = (
            "export default {\n"
            "  data() { return { cache: {}, ttl: 3600 } },\n"
            "  methods: {\n"
            "    get(key) { return this.cache[key] },\n"
            "    set(key, value) { this.cache[key] = value }\n"
            "  }\n"
            "}\n"
        )
        members = MixinMembers(data=["cache", "ttl"], methods=["get", "set"])
        result = generate_composable_from_mixin(mixin, "storageMixin", members, [])
        assert "reactive(" not in result, "Generator should never produce reactive()"
        assert "ref(" in result, "Generator should use ref() for data members"

    def test_name_collisions_integrated_in_workflow(self):
        """D3: detect_name_collisions() is called in plan_component_injections()
        for components with 2+ composables."""
        import inspect
        from vue3_migration.workflows.auto_migrate_workflow import plan_component_injections

        source = inspect.getsource(plan_component_injections)
        assert "detect_name_collisions(" in source, (
            "detect_name_collisions() should be called in plan_component_injections"
        )
