"""
Enforces "No real orders should be sent" at the architecture level: the
paper_trading package must import no networking or HTTP library. Inspects
actual Python import statements via the `ast` module (not a string/grep
match), same technique as Phase 10's no-scoring-dependency test.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PAPER_TRADING_DIR = Path(__file__).resolve().parents[1] / "app" / "paper_trading"

FORBIDDEN_MODULES = {
    "requests", "httpx", "urllib", "urllib2", "urllib3", "socket",
    "aiohttp", "http.client", "ftplib", "smtplib", "websocket", "websockets",
}


def _imported_module_names(path: Path) -> set:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_paper_trading_never_imports_a_networking_library():
    offending = {}
    for py_file in PAPER_TRADING_DIR.glob("*.py"):
        imported = _imported_module_names(py_file)
        bad = imported & FORBIDDEN_MODULES
        if bad:
            offending[py_file.name] = bad

    assert not offending, (
        f"app.paper_trading must never import a networking/broker library "
        f"(no real orders should ever be sent), but found: {offending}"
    )


def test_paper_trading_directory_is_not_empty():
    py_files = list(PAPER_TRADING_DIR.glob("*.py"))
    assert len(py_files) >= 4
