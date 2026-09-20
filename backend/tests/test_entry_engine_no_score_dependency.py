"""
Enforces "never generate an ENTRY merely because the Opportunity Score is
high" at the architecture level: the entry_engine package must have NO
import path to app.scoring whatsoever. This inspects actual Python import
statements via the `ast` module (not a string/grep match, which could be
fooled by a comment or a string literal) - if anyone ever adds
`import app.scoring` (or `from app.scoring import ...`) anywhere in
app/entry_engine/, this test fails the build.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ENTRY_ENGINE_DIR = Path(__file__).resolve().parents[1] / "app" / "entry_engine"


def _imported_module_names(path: Path) -> set:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_entry_engine_has_no_import_of_scoring_module():
    offending = {}
    for py_file in ENTRY_ENGINE_DIR.glob("*.py"):
        imported = _imported_module_names(py_file)
        scoring_imports = {name for name in imported if name == "app.scoring" or name.startswith("app.scoring.")}
        if scoring_imports:
            offending[py_file.name] = scoring_imports

    assert not offending, (
        f"app.entry_engine must never import app.scoring (the Opportunity "
        f"Score must never influence entry timing), but found: {offending}"
    )


def test_entry_engine_directory_is_not_empty():
    """Guards against the above test passing vacuously if the directory
    were ever accidentally emptied or renamed."""
    py_files = list(ENTRY_ENGINE_DIR.glob("*.py"))
    assert len(py_files) >= 4
