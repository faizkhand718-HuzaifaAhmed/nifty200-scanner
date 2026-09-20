"""
Enforces "risk management must operate independently from the signal
engine" at the architecture level: app.risk_management must have no
import path to any module that decides WHAT or WHEN to trade. Inspects
actual Python import statements via the `ast` module (not a grep, which
could be fooled by a comment or string), same technique as Phase 10's
no-scoring-dependency test and Phase 13's no-real-orders test.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RISK_MANAGEMENT_DIR = Path(__file__).resolve().parents[1] / "app" / "risk_management"

FORBIDDEN_MODULES = {
    "app.setup_detection",
    "app.scoring",
    "app.entry_engine",
    "app.ranking",
    "app.ml",
    "app.alerts",
    "app.backtesting",
}


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


def test_risk_management_has_no_import_of_any_signal_producing_module():
    offending = {}
    for py_file in RISK_MANAGEMENT_DIR.glob("*.py"):
        imported = _imported_module_names(py_file)
        bad = {
            name for name in imported
            if any(name == forbidden or name.startswith(forbidden + ".") for forbidden in FORBIDDEN_MODULES)
        }
        if bad:
            offending[py_file.name] = bad

    assert not offending, (
        f"app.risk_management must never import a signal-producing module "
        f"(risk management must operate independently from the signal engine), "
        f"but found: {offending}"
    )


def test_risk_management_directory_is_not_empty():
    py_files = list(RISK_MANAGEMENT_DIR.glob("*.py"))
    assert len(py_files) >= 4
