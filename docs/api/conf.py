from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
EXT = Path(__file__).resolve().parent / "_ext"

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(EXT))

project = "workspace-os"
author = "Sergio Canales"
copyright = "2026, Sergio Canales"  # noqa: A001

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "wos_api_docs",
]

autosummary_generate = False
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autoclass_content = "both"
templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "alabaster"
html_title = "workspace-os API documentation"

master_doc = "index"
language = "en"
