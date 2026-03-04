"""
Data models for the Vue mixin migration tool.

Typed dataclasses replace the raw dicts used in the original scripts,
providing clear structure and computed properties.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class MigrationStatus(Enum):
    """Status of a single mixin's migration readiness."""
    READY = "ready"
    BLOCKED_NO_COMPOSABLE = "blocked_no_composable"
    BLOCKED_MISSING_MEMBERS = "blocked_missing"
    BLOCKED_NOT_RETURNED = "blocked_not_returned"
    FORCE_UNBLOCKED = "force_unblocked"


class ConfidenceLevel(str, Enum):
    """Confidence in the quality of a generated/patched composable."""
    HIGH = "HIGH"       # 0 remaining this., 0 TODOs, 0 warnings
    MEDIUM = "MEDIUM"   # has TODOs or warnings but no remaining this.
    LOW = "LOW"         # has remaining this.$, unbalanced brackets, or structural warnings


@dataclass
class MigrationWarning:
    """A single warning detected during mixin analysis or composable generation."""
    mixin_stem: str           # Which mixin triggered this
    category: str             # e.g. "this.$router", "watch", "mixin-option"
    message: str              # Human-readable description
    action_required: str      # What the developer must do
    line_hint: str | None     # Source line context (for inline comment)
    severity: str             # "error" | "warning" | "info"


@dataclass
class MixinMembers:
    """Members extracted from a mixin source file."""
    data: list[str] = field(default_factory=list)
    computed: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    watch: list[str] = field(default_factory=list)

    @property
    def all_names(self) -> list[str]:
        return list(dict.fromkeys(self.data + self.computed + self.methods + self.watch))


@dataclass
class MemberClassification:
    """Classification of how mixin members relate to a composable and the component.

    Given a set of used members, a composable's capabilities, and the component's
    own members, this classifies each member into categories that determine
    whether injection can proceed.
    """
    missing: list[str] = field(default_factory=list)
    """Members not found anywhere in the composable."""
    truly_missing: list[str] = field(default_factory=list)
    """Missing members that the component does NOT override (blockers)."""
    not_returned: list[str] = field(default_factory=list)
    """Members present in composable but not in its return statement."""
    truly_not_returned: list[str] = field(default_factory=list)
    """Not-returned members that the component does NOT override (blockers)."""
    overridden: list[str] = field(default_factory=list)
    """Missing members that the component defines itself (safe to skip)."""
    overridden_not_returned: list[str] = field(default_factory=list)
    """Not-returned members that the component defines itself (safe to skip)."""
    injectable: list[str] = field(default_factory=list)
    """Members the composable should provide (used - overridden)."""

    @property
    def is_ready(self) -> bool:
        return not self.truly_missing and not self.truly_not_returned


@dataclass
class ComposableCoverage:
    """Analysis of a composable's coverage of a mixin's members."""
    file_path: Path
    fn_name: str
    import_path: str
    all_identifiers: list[str] = field(default_factory=list)
    return_keys: list[str] = field(default_factory=list)

    def classify_members(
        self,
        used: list[str],
        component_own_members: set[str],
    ) -> MemberClassification:
        """Classify each used member by availability in the composable and component."""
        missing = [m for m in used if m not in self.all_identifiers]
        not_returned = [m for m in used if m in self.all_identifiers and m not in self.return_keys]

        overridden = [m for m in missing if m in component_own_members]
        truly_missing = [m for m in missing if m not in component_own_members]
        overridden_not_returned = [m for m in not_returned if m in component_own_members]
        truly_not_returned = [m for m in not_returned if m not in component_own_members]

        injectable = [
            m for m in used
            if m not in overridden and m not in overridden_not_returned
        ]

        return MemberClassification(
            missing=missing,
            truly_missing=truly_missing,
            not_returned=not_returned,
            truly_not_returned=truly_not_returned,
            overridden=overridden,
            overridden_not_returned=overridden_not_returned,
            injectable=injectable,
        )


@dataclass
class MixinEntry:
    """Complete analysis of a single mixin used by a component."""
    local_name: str
    """The local import name (e.g. 'selectionMixin')."""
    mixin_path: Path
    """Resolved path to the mixin file."""
    mixin_stem: str
    """Filename stem of the mixin (e.g. 'selectionMixin')."""
    members: MixinMembers
    """Extracted mixin members."""
    lifecycle_hooks: list[str] = field(default_factory=list)
    """Lifecycle hooks found in the mixin."""
    used_members: list[str] = field(default_factory=list)
    """Members actually referenced by the component."""
    composable: Optional[ComposableCoverage] = None
    """Matched composable, if found."""
    classification: Optional[MemberClassification] = None
    """Member classification against the composable."""
    status: MigrationStatus = MigrationStatus.BLOCKED_NO_COMPOSABLE
    """Current migration status."""
    warnings: list[MigrationWarning] = field(default_factory=list)
    """Migration warnings detected during analysis and generation."""
    external_deps: list[str] = field(default_factory=list)
    """External this.X references not defined in this mixin."""

    def compute_status(self) -> MigrationStatus:
        """Determine the migration status based on analysis results."""
        if not self.used_members:
            self.status = MigrationStatus.READY
        elif not self.composable or not self.classification:
            self.status = MigrationStatus.BLOCKED_NO_COMPOSABLE
        elif self.classification.is_ready:
            self.status = MigrationStatus.READY
        elif self.classification.truly_missing:
            self.status = MigrationStatus.BLOCKED_MISSING_MEMBERS
        else:
            self.status = MigrationStatus.BLOCKED_NOT_RETURNED
        return self.status


@dataclass
class FileChange:
    """Represents a planned or completed file modification."""
    file_path: Path
    original_content: str
    new_content: str
    changes: list[str] = field(default_factory=list)
    """Human-readable descriptions of each change made."""

    @property
    def has_changes(self) -> bool:
        return self.original_content != self.new_content


@dataclass
class MigrationPlan:
    """All planned file changes for a project-wide auto-migrate run."""
    component_changes: list["FileChange"] = field(default_factory=list)
    composable_changes: list["FileChange"] = field(default_factory=list)
    entries_by_component: list[tuple[Path, list["MixinEntry"]]] = field(default_factory=list)

    @property
    def all_changes(self) -> list["FileChange"]:
        return self.composable_changes + self.component_changes

    @property
    def has_changes(self) -> bool:
        return any(c.has_changes for c in self.all_changes)


@dataclass
class MigrationConfig:
    """Configuration for the migration tool."""
    project_root: Path = field(default_factory=Path.cwd)
    skip_dirs: set[str] = field(
        default_factory=lambda: {"node_modules", "dist", ".git", "__pycache__"}
    )
    file_extensions: set[str] = field(
        default_factory=lambda: {".vue", ".js", ".ts"}
    )
    composable_dir_name: str = "composables"
    backup_enabled: bool = True
    dry_run: bool = False
    auto_confirm: bool = False
    indent: str = "  "
