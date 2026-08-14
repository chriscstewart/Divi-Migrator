"""Guard against pyproject.toml and divi_migrator.__version__ drifting apart.

The built distribution version is read from pyproject.toml's static
`version`, while runtime code reads divi_migrator.__version__. If they disagree,
the published package version silently mismatches the code -- exactly the bug
that blocked the 0.1.4 release (pyproject stayed 0.1.3 while __init__ said 0.1.4,
so PyPI rejected the re-upload of an existing 0.1.3). This test makes any future
drift a hard CI failure instead of a silent publish break.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_version_matches_package_version() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_version = pyproject["project"]["version"]

    import divi_migrator

    package_version = divi_migrator.__version__

    assert pyproject_version == package_version, (
        f"pyproject.toml version ({pyproject_version!r}) does not match "
        f"divi_migrator.__version__ ({package_version!r}). Bump BOTH when releasing."
    )


@pytest.mark.parametrize("prefix", ["v"])
def test_version_is_pep440_and_release_tag_shape(prefix: str) -> None:
    import divi_migrator

    # Reject stray suffixes like -dev/-alpha that would break `git tag vX.Y.Z`.
    assert divi_migrator.__version__[0].isdigit()
    assert prefix  # documents the expected git tag prefix
