from __future__ import annotations

import importlib
import importlib.util
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from workspace_os.config import load_oce_extension_modules


@dataclass(frozen=True)
class PolicyDocumentSpec:
    ref: str
    title: str
    norms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "title": self.title,
            "norms": list(self.norms),
        }


@dataclass(frozen=True)
class OceExtension:
    name: str
    description: str
    layer: str = "normative"
    policy_documents: tuple[PolicyDocumentSpec, ...] = ()
    context_hooks: tuple[Callable[..., Mapping[str, Any] | None], ...] = ()
    decision_hooks: tuple[Callable[..., Mapping[str, Any] | None], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "layer": self.layer,
            "policy_documents": [document.to_dict() for document in self.policy_documents],
            "context_hooks": len(self.context_hooks),
            "decision_hooks": len(self.decision_hooks),
        }


_LOCK = RLock()
_REGISTERED_EXTENSIONS: list[OceExtension] = []


def register_oce_extension(extension: OceExtension) -> None:
    with _LOCK:
        for index, current in enumerate(_REGISTERED_EXTENSIONS):
            if current.name == extension.name:
                _REGISTERED_EXTENSIONS[index] = extension
                return
        _REGISTERED_EXTENSIONS.append(extension)


def unregister_oce_extension(name: str) -> None:
    with _LOCK:
        _REGISTERED_EXTENSIONS[:] = [extension for extension in _REGISTERED_EXTENSIONS if extension.name != name]


def clear_oce_extensions() -> None:
    with _LOCK:
        _REGISTERED_EXTENSIONS.clear()


def registered_oce_extensions() -> tuple[OceExtension, ...]:
    with _LOCK:
        return tuple(_REGISTERED_EXTENSIONS)


def extension_policy_documents() -> tuple[PolicyDocumentSpec, ...]:
    documents: list[PolicyDocumentSpec] = []
    for extension in registered_oce_extensions():
        for document in extension.policy_documents:
            if document not in documents:
                documents.append(document)
    return tuple(documents)


def extension_summary_lines() -> tuple[str, ...]:
    extensions = registered_oce_extensions()
    if not extensions:
        return (
            "registered=0",
            "extensions: none",
        )
    lines = [f"registered={len(extensions)}"]
    for extension in extensions:
        lines.append(
            f"- {extension.name}: layer={extension.layer} docs={len(extension.policy_documents)} "
            f"context_hooks={len(extension.context_hooks)} decision_hooks={len(extension.decision_hooks)}"
        )
    return tuple(lines)


def load_configured_oce_extensions(config_path: Path) -> tuple[str, ...]:
    loaded: list[str] = []
    for module_spec in load_oce_extension_modules(config_path):
        loaded.append(_load_oce_extension_module(config_path, module_spec))
    return tuple(loaded)


def _load_oce_extension_module(config_path: Path, module_spec: str) -> str:
    module_path = Path(module_spec)
    if module_path.suffix == ".py" or any(separator in module_spec for separator in ("/", "\\")):
        if not module_path.is_absolute():
            module_path = (config_path.parent / module_path).resolve()
        module_name = _module_name_from_path(module_path)
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Unable to load OCE extension module from {module_path}.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module_name
    importlib.import_module(module_spec)
    return module_spec


def _module_name_from_path(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    slug = path.stem.replace("-", "_")
    return f"workspace_os.oce_extension_{slug}_{digest}"
