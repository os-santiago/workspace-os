# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0
"""
Security policy definitions and evaluation helpers for Workspace OS.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import tomllib
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class SecurityPatternRule:
    name: str
    pattern: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class SecurityHeaderRule:
    name: str
    paths: tuple[str, ...]
    lines: tuple[str, ...]


@dataclass(frozen=True)
class SecurityEncryptionRule:
    name: str
    config_path: str
    enabled_profile_kind: str
    required_fields: tuple[str, ...]
    forbidden_fields: tuple[str, ...]


@dataclass(frozen=True)
class SecurityPolicy:
    allowed_dependencies: tuple[str, ...]
    banned_patterns: tuple[SecurityPatternRule, ...]
    required_headers: tuple[SecurityHeaderRule, ...]
    encryption_requirements: tuple[SecurityEncryptionRule, ...]


@dataclass(frozen=True)
class SecurityPolicyReport:
    passed: bool
    summary: dict[str, int | float | bool | str]
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "findings": list(self.findings),
        }


def load_security_policy(policy_path: Path) -> SecurityPolicy:
    if not policy_path.exists():
        return _default_security_policy()

    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Security policy must be a YAML mapping.")

    allowed_dependencies = tuple(
        _normalize_dependency_name(value) for value in _read_string_list(payload.get("allowed_dependencies"))
    )
    banned_patterns = tuple(
        _parse_pattern_rule(index, raw)
        for index, raw in enumerate(_read_object_list(payload.get("banned_patterns")))
    )
    required_headers = tuple(
        _parse_header_rule(index, raw)
        for index, raw in enumerate(_read_object_list(payload.get("required_headers")))
    )
    encryption_requirements = tuple(
        _parse_encryption_rule(index, raw)
        for index, raw in enumerate(_read_object_list(payload.get("encryption_requirements")))
    )
    return SecurityPolicy(
        allowed_dependencies=allowed_dependencies,
        banned_patterns=banned_patterns,
        required_headers=required_headers,
        encryption_requirements=encryption_requirements,
    )


def evaluate_security_policy(project_root: Path, policy: SecurityPolicy) -> SecurityPolicyReport:
    resolved_root = project_root.resolve()
    findings: list[str] = []
    summary: dict[str, int | float | bool | str] = {
        "declared_dependencies_total": 0,
        "declared_dependencies_disallowed": 0,
        "banned_pattern_rules_total": len(policy.banned_patterns),
        "banned_pattern_rules_failed": 0,
        "header_rules_total": len(policy.required_headers),
        "header_rules_failed": 0,
        "encryption_rules_total": len(policy.encryption_requirements),
        "encryption_rules_failed": 0,
        "compliance_controls_total": 0,
        "compliance_controls_failed": 0,
        "compliance_rate": 1.0,
        "policy_ready": bool(policy.allowed_dependencies or policy.banned_patterns or policy.required_headers or policy.encryption_requirements),
    }

    declared_dependencies = _load_declared_dependencies(resolved_root)
    summary["declared_dependencies_total"] = len(declared_dependencies)
    disallowed_dependencies = sorted(
        dependency
        for dependency in declared_dependencies
        if dependency not in policy.allowed_dependencies
    )
    summary["declared_dependencies_disallowed"] = len(disallowed_dependencies)
    for dependency in disallowed_dependencies:
        findings.append(f"Dependency '{dependency}' is not allowed by policy.")

    pattern_failures = 0
    for rule in policy.banned_patterns:
        matched_file = _find_banned_pattern_match(resolved_root, rule)
        if matched_file is not None:
            pattern_failures += 1
            findings.append(f"Pattern rule '{rule.name}' matched in '{matched_file}'.")
    summary["banned_pattern_rules_failed"] = pattern_failures

    header_failures = 0
    for rule in policy.required_headers:
        missing = _find_missing_headers(resolved_root, rule)
        if missing:
            header_failures += 1
            findings.append(
                f"Header rule '{rule.name}' is missing required lines in: {', '.join(missing)}."
            )
    summary["header_rules_failed"] = header_failures

    encryption_failures = 0
    for rule in policy.encryption_requirements:
        passed, detail = _check_encryption_requirement(resolved_root, rule)
        if not passed:
            encryption_failures += 1
            findings.append(f"Encryption rule '{rule.name}' failed: {detail}")
    summary["encryption_rules_failed"] = encryption_failures

    summary["compliance_controls_total"] = (
        summary["declared_dependencies_total"]
        + summary["banned_pattern_rules_total"]
        + summary["header_rules_total"]
        + summary["encryption_rules_total"]
    )
    summary["compliance_controls_failed"] = (
        summary["declared_dependencies_disallowed"]
        + summary["banned_pattern_rules_failed"]
        + summary["header_rules_failed"]
        + summary["encryption_rules_failed"]
    )
    total_controls = int(summary["compliance_controls_total"])
    failed_controls = int(summary["compliance_controls_failed"])
    summary["compliance_rate"] = 1.0 if total_controls == 0 else round(1.0 - (failed_controls / total_controls), 4)

    passed = failed_controls == 0
    return SecurityPolicyReport(passed=passed, summary=summary, findings=tuple(findings))


def _default_security_policy() -> SecurityPolicy:
    return SecurityPolicy(
        allowed_dependencies=(
            "aiohttp",
            "ansible",
            "bandit",
            "black",
            "cyclonedx-bom",
            "cryptography",
            "pillow",
            "pip-audit",
            "pyyaml",
            "pytest",
            "pytest-cov",
            "python-dotenv",
            "requests",
            "rich",
            "safety",
            "sentry-sdk",
            "starlette",
            "torch",
        ),
        banned_patterns=(
            SecurityPatternRule(
                name="unsafe_yaml_loader",
                pattern=r"\byaml\.load\(",
                paths=("src/**/*.py", "tests/**/*.py", "docs/**/*.md", "config/**/*.json", "config/**/*.yml", "config/**/*.yaml", "config/**/*.toml"),
            ),
            SecurityPatternRule(
                name="shell_injection_flag",
                pattern=r"shell=True",
                paths=("src/**/*.py", "tests/**/*.py"),
            ),
            SecurityPatternRule(
                name="dynamic_eval_usage",
                pattern=r"\beval\(",
                paths=("src/**/*.py", "tests/**/*.py"),
            ),
        ),
        required_headers=(
            SecurityHeaderRule(
                name="security_package_headers",
                paths=("src/workspace_os/security/*.py",),
                lines=(
                    "# Copyright 2026 Sergio Canales",
                    "# SPDX-License-Identifier: Apache-2.0",
                ),
            ),
            SecurityHeaderRule(
                name="security_validator_tests_headers",
                paths=("tests/test_security_validator.py",),
                lines=(
                    "# Copyright 2026 Sergio Canales",
                    "# SPDX-License-Identifier: Apache-2.0",
                ),
            ),
        ),
        encryption_requirements=(
            SecurityEncryptionRule(
                name="modeling_secrets_env_backed",
                config_path="config/workspace.sources.example.json",
                enabled_profile_kind="openai_compatible",
                required_fields=("base_url_env", "api_key_env", "model_env"),
                forbidden_fields=("api_key",),
            ),
        ),
    )


def _load_declared_dependencies(project_root: Path) -> set[str]:
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return set()

    with pyproject_path.open("rb") as handle:
        payload = tomllib.load(handle)

    project = payload.get("project", {})
    if not isinstance(project, dict):
        return set()

    dependencies: set[str] = set()
    for raw_dependency in project.get("dependencies", []) or []:
        if isinstance(raw_dependency, str):
            dependencies.add(_normalize_dependency_name(raw_dependency))

    optional_dependencies = project.get("optional-dependencies", {})
    if isinstance(optional_dependencies, dict):
        for raw_group in optional_dependencies.values():
            if not isinstance(raw_group, list):
                continue
            for raw_dependency in raw_group:
                if isinstance(raw_dependency, str):
                    dependencies.add(_normalize_dependency_name(raw_dependency))

    return {dependency for dependency in dependencies if dependency}


def _normalize_dependency_name(raw_dependency: str) -> str:
    name = raw_dependency.split(";", 1)[0].strip()
    name = re.split(r"[<>=!~]", name, maxsplit=1)[0].strip()
    name = name.split("[", 1)[0].strip()
    return name.lower().replace("_", "-")


def _find_banned_pattern_match(project_root: Path, rule: SecurityPatternRule) -> str | None:
    resolved_root = project_root.resolve()
    pattern = re.compile(rule.pattern)
    for relative in _iter_matching_files(resolved_root, rule.paths):
        if _is_policy_scaffold_file(relative, resolved_root):
            continue
        try:
            text = relative.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if pattern.search(text):
            return str(relative.relative_to(resolved_root))
    return None


def _find_missing_headers(project_root: Path, rule: SecurityHeaderRule) -> list[str]:
    resolved_root = project_root.resolve()
    missing: list[str] = []
    for relative in _iter_matching_files(resolved_root, rule.paths):
        try:
            text = relative.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            missing.append(str(relative.relative_to(resolved_root)))
            continue
        first_lines = [line.rstrip("\r") for line in text.splitlines()[: len(rule.lines)]]
        if tuple(first_lines) != rule.lines:
            missing.append(str(relative.relative_to(resolved_root)))
    return missing


def _check_encryption_requirement(project_root: Path, rule: SecurityEncryptionRule) -> tuple[bool, str]:
    config_path = project_root / rule.config_path
    if not config_path.exists():
        return False, f"Config file '{rule.config_path}' is missing."

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"Config file '{rule.config_path}' is not valid JSON: {exc}."

    modeling = payload.get("modeling", {})
    if not isinstance(modeling, dict):
        return False, "Modeling section is missing or invalid."

    profiles = modeling.get("profiles", {})
    if not isinstance(profiles, dict):
        return False, "Modeling profiles are missing or invalid."

    checked_profiles = 0
    for profile_name, raw_profile in profiles.items():
        if not isinstance(raw_profile, dict):
            return False, f"Profile '{profile_name}' must be an object."
        kind = str(raw_profile.get("kind", "")).strip().lower()
        enabled = bool(raw_profile.get("enabled", True))
        if not enabled or kind != rule.enabled_profile_kind:
            continue
        checked_profiles += 1
        missing_required = [field for field in rule.required_fields if not _is_nonempty_string(raw_profile.get(field))]
        if missing_required:
            return False, f"Profile '{profile_name}' is missing required secret-handling fields: {', '.join(missing_required)}."
        forbidden_present = [field for field in rule.forbidden_fields if _is_nonempty_string(raw_profile.get(field))]
        if forbidden_present:
            return False, f"Profile '{profile_name}' uses forbidden inline fields: {', '.join(forbidden_present)}."

    if checked_profiles == 0:
        return False, f"No enabled '{rule.enabled_profile_kind}' profiles were found."
    return True, "Encryption controls use environment-backed settings."


def _iter_matching_files(project_root: Path, patterns: Iterable[str]) -> list[Path]:
    matched: dict[Path, None] = {}
    for pattern in patterns:
        for path in project_root.glob(pattern):
            if path.is_file():
                matched[path.resolve()] = None
    return sorted(matched.keys())


def _is_policy_scaffold_file(path: Path, project_root: Path) -> bool:
    try:
        relative = path.relative_to(project_root).as_posix()
    except ValueError:
        relative = path.as_posix()
    return relative in {
        "config/security-policy.yml",
        "src/workspace_os/security/policy.py",
        "tests/test_security_validator.py",
    }


def _read_string_list(raw_value: object) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if not isinstance(raw_value, list):
        raise ValueError("Policy list entries must be arrays.")
    values: list[str] = []
    for index, raw in enumerate(raw_value):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"Policy list entry #{index + 1} must be a non-empty string.")
        values.append(raw.strip())
    return tuple(values)


def _read_object_list(raw_value: object) -> list[dict[str, object]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("Policy sections must be arrays of objects.")
    objects: list[dict[str, object]] = []
    for index, raw in enumerate(raw_value):
        if not isinstance(raw, dict):
            raise ValueError(f"Policy entry #{index + 1} must be an object.")
        objects.append(raw)
    return objects


def _parse_pattern_rule(index: int, raw: dict[str, object]) -> SecurityPatternRule:
    name = _require_string(raw, "name", index)
    pattern = _require_string(raw, "pattern", index)
    paths = tuple(_require_string_list(raw.get("paths"), f"banned_patterns entry '{name}' paths"))
    return SecurityPatternRule(name=name, pattern=pattern, paths=paths)


def _parse_header_rule(index: int, raw: dict[str, object]) -> SecurityHeaderRule:
    name = _require_string(raw, "name", index)
    paths = tuple(_require_string_list(raw.get("paths"), f"required_headers entry '{name}' paths"))
    lines = tuple(_require_string_list(raw.get("lines"), f"required_headers entry '{name}' lines"))
    return SecurityHeaderRule(name=name, paths=paths, lines=lines)


def _parse_encryption_rule(index: int, raw: dict[str, object]) -> SecurityEncryptionRule:
    name = _require_string(raw, "name", index)
    config_path = _require_string(raw, "config_path", index)
    enabled_profile_kind = _require_string(raw, "enabled_profile_kind", index).lower()
    required_fields = tuple(_require_string_list(raw.get("required_fields"), f"encryption_requirements entry '{name}' required_fields"))
    forbidden_fields = tuple(_require_string_list(raw.get("forbidden_fields"), f"encryption_requirements entry '{name}' forbidden_fields"))
    return SecurityEncryptionRule(
        name=name,
        config_path=config_path,
        enabled_profile_kind=enabled_profile_kind,
        required_fields=required_fields,
        forbidden_fields=forbidden_fields,
    )


def _require_string(raw: dict[str, object], field: str, index: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Policy entry #{index + 1} must define non-empty '{field}'.")
    return value.strip()


def _require_string_list(raw_value: object, label: str) -> list[str]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError(f"{label} must be a non-empty list of strings.")
    values: list[str] = []
    for index, raw in enumerate(raw_value):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"{label} entry #{index + 1} must be a non-empty string.")
        values.append(raw.strip())
    return values


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
