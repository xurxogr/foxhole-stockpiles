"""Repository-wide import style checks."""

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = ("foxhole_stockpiles", "fs_tools")


def _type_checking_blocks(path: Path) -> list[int]:
    """Return the line numbers of ``if TYPE_CHECKING:`` blocks in a module.

    Args:
        path (Path): The Python source file to inspect.

    Returns:
        list[int]: Line numbers of every ``if TYPE_CHECKING:`` statement.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name | ast.Attribute)
        and ast.unparse(node.test).endswith("TYPE_CHECKING")
    ]


@pytest.mark.parametrize("package", _PACKAGES)
def test_no_type_checking_imports(package: str) -> None:
    """Imports are real imports; ``if TYPE_CHECKING:`` blocks are not allowed."""
    offenders = [
        f"{path.relative_to(_REPO_ROOT)}:{line}"
        for path in sorted((_REPO_ROOT / package).rglob("*.py"))
        for line in _type_checking_blocks(path)
    ]
    assert offenders == []
