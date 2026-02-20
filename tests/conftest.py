"""Shared fixtures for the vue3-migration test suite."""
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DUMMY_PROJECT = FIXTURES_DIR / "dummy_project"


@pytest.fixture
def dummy_project():
    """Root of the dummy Vue project fixture."""
    return DUMMY_PROJECT


@pytest.fixture
def mixins_dir(dummy_project):
    return dummy_project / "src" / "mixins"


@pytest.fixture
def composables_dir(dummy_project):
    return dummy_project / "src" / "composables"


@pytest.fixture
def components_dir(dummy_project):
    return dummy_project / "src" / "components"
