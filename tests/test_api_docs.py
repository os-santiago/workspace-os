from __future__ import annotations

from pathlib import Path
import sys


DOCS_EXT = Path(__file__).resolve().parents[1] / "docs" / "api" / "_ext"
if str(DOCS_EXT) not in sys.path:
    sys.path.insert(0, str(DOCS_EXT))

from wos_api_docs import discover_public_modules, generate_api_docs  # noqa: E402


def test_discover_public_modules_includes_core_api():
    modules = discover_public_modules()
    names = {module.name for module in modules}

    assert "workspace_os" in names
    assert "workspace_os.agent_queue" in names
    assert "workspace_os.web_server" in names
    assert "workspace_os.security.policy" in names
    assert all(not name.split(".")[-1].startswith("_") for name in names)


def test_generate_api_docs_writes_index_and_module_pages(tmp_path):
    generated = generate_api_docs(tmp_path)
    module_names = {module.name for module in generated}

    assert (tmp_path / "modules.rst").exists()
    assert (tmp_path / "workspace_os" / "agent_queue.rst").exists()
    assert (tmp_path / "workspace_os" / "web_server.rst").exists()

    index_text = (tmp_path / "modules.rst").read_text(encoding="utf-8")
    assert "workspace_os/agent_queue" in index_text
    assert "workspace_os/web_server" in index_text
    assert "workspace_os" in module_names
