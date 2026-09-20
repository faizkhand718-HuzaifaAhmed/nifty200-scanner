"""
Defense in depth, mirroring Phase 13's no-real-orders test: none of
app.brokers' CORE files (the interface, mock adapter, paper adapter,
safety gate, factory, models, exceptions) should import a networking
library directly. A future real-broker adapter needs one, of course -
but it belongs in its own separate module that calls register_live_broker(),
not mixed into these files. This test guards against that boundary
eroding over time, even though nothing violates it today.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BROKERS_DIR = Path(__file__).resolve().parents[1] / "app" / "brokers"

FORBIDDEN_MODULES = {
    "requests", "httpx", "urllib", "urllib2", "urllib3", "socket",
    "aiohttp", "http.client", "websocket", "websockets",
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


def test_core_broker_files_never_import_a_networking_library():
    offending = {}
    for py_file in BROKERS_DIR.glob("*.py"):
        imported = _imported_module_names(py_file)
        bad = imported & FORBIDDEN_MODULES
        if bad:
            offending[py_file.name] = bad

    assert not offending, (
        f"app.brokers' core files must not import a networking library directly - "
        f"a real broker integration belongs in its own module, registered via "
        f"register_live_broker(). Found: {offending}"
    )


def test_brokers_directory_is_not_empty():
    py_files = list(BROKERS_DIR.glob("*.py"))
    assert len(py_files) >= 6
