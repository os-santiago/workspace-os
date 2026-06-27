from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
import pkgutil


@dataclass(frozen=True)
class DiscoveredModule:
    name: str
    docname: str


def discover_public_modules(package_name: str = "workspace_os") -> list[DiscoveredModule]:
    package = import_module(package_name)
    discovered: list[DiscoveredModule] = [DiscoveredModule(name=package_name, docname=package_name)]
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        module_name = module_info.name
        if any(part.startswith("_") for part in module_name.split(".")):
            continue
        discovered.append(DiscoveredModule(name=module_name, docname=module_name.replace(".", "/")))
    return sorted(discovered, key=lambda item: item.name)


def _render_module_page(module_name: str) -> str:
    title = module_name
    underline = "=" * len(title)
    return "\n".join(
        [
            title,
            underline,
            "",
            f".. automodule:: {module_name}",
            "   :members:",
            "   :undoc-members:",
            "   :show-inheritance:",
            "   :member-order: bysource",
            "",
        ]
    )


def _render_modules_index(modules: list[DiscoveredModule]) -> str:
    lines = [
        "API modules",
        "===========",
        "",
        ".. toctree::",
        "   :maxdepth: 1",
        "",
    ]
    for module in modules:
        lines.append(f"   {module.docname}")
    lines.append("")
    return "\n".join(lines)


def generate_api_docs(output_dir: Path, package_name: str = "workspace_os") -> list[DiscoveredModule]:
    output_dir.mkdir(parents=True, exist_ok=True)
    modules = discover_public_modules(package_name)
    for module in modules:
        module_path = output_dir / Path(*module.name.split("."))
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.with_suffix(".rst").write_text(_render_module_page(module.name), encoding="utf-8")
    (output_dir / "modules.rst").write_text(_render_modules_index(modules), encoding="utf-8")
    return modules


def setup(app):  # pragma: no cover - Sphinx hook
    app.add_config_value("wos_api_docs_package", "workspace_os", "env")

    def _generate(app) -> None:
        generate_api_docs(Path(app.srcdir) / "_generated", app.config.wos_api_docs_package)

    app.connect("builder-inited", _generate)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
