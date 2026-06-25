# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""
AI-powered code review module for automated quality analysis.

Checks:
- Code smells (long methods, duplicate code, magic numbers)
- Complexity metrics (cyclomatic complexity)
- Naming conventions (PEP 8 compliance)
- Documentation completeness
- Performance anti-patterns
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class CodeIssue:
    """Represents a single code quality issue."""
    file_path: str
    line_number: int
    severity: Literal["low", "medium", "high", "critical"]
    category: Literal["code_smell", "complexity", "naming", "documentation", "performance"]
    message: str
    suggestion: str | None = None

    def render(self) -> str:
        """Render issue as human-readable string."""
        severity_symbol = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨"
        }[self.severity]

        result = f"{severity_symbol} {self.file_path}:{self.line_number} [{self.category}] {self.message}"
        if self.suggestion:
            result += f"\n  Suggestion: {self.suggestion}"
        return result


@dataclass(frozen=True)
class ReviewResult:
    """Results from AI code review analysis."""
    file_path: str
    issues: tuple[CodeIssue, ...]
    metrics: dict[str, float]
    passed: bool
    summary: str

    def render_summary(self) -> str:
        """Render review summary."""
        status = "✅ PASS" if self.passed else "❌ FAIL"
        issue_count = len(self.issues)
        critical = sum(1 for i in self.issues if i.severity == "critical")
        high = sum(1 for i in self.issues if i.severity == "high")

        lines = [
            f"{status} - {self.file_path}",
            f"Issues: {issue_count} (Critical: {critical}, High: {high})",
            f"Complexity: {self.metrics.get('avg_complexity', 0):.1f}",
            f"Documentation: {self.metrics.get('doc_ratio', 0):.1%}",
        ]
        return "\n".join(lines)


class AICodeReviewer:
    """AI-powered code reviewer for Python code."""

    def __init__(self, max_complexity: int = 10, min_doc_ratio: float = 0.5):
        self.max_complexity = max_complexity
        self.min_doc_ratio = min_doc_ratio

    def review_file(self, file_path: Path) -> ReviewResult:
        """Review a single Python file."""
        try:
            code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(code, filename=str(file_path))
        except Exception as e:
            return ReviewResult(
                file_path=str(file_path),
                issues=(),
                metrics={},
                passed=False,
                summary=f"Failed to parse: {e}"
            )

        issues: list[CodeIssue] = []

        # Run all analyzers
        issues.extend(self._check_code_smells(file_path, tree, code))
        issues.extend(self._check_complexity(file_path, tree))
        issues.extend(self._check_naming_conventions(file_path, tree))
        issues.extend(self._check_documentation(file_path, tree))
        issues.extend(self._check_performance(file_path, tree, code))

        # Calculate metrics
        metrics = self._calculate_metrics(tree)

        # Determine pass/fail
        critical_count = sum(1 for i in issues if i.severity == "critical")
        high_count = sum(1 for i in issues if i.severity == "high")
        passed = critical_count == 0 and high_count <= 3

        summary = f"Found {len(issues)} issues (Critical: {critical_count}, High: {high_count})"

        return ReviewResult(
            file_path=str(file_path),
            issues=tuple(issues),
            metrics=metrics,
            passed=passed,
            summary=summary
        )

    def _check_code_smells(self, file_path: Path, tree: ast.AST, code: str) -> list[CodeIssue]:
        """Detect common code smells."""
        issues: list[CodeIssue] = []

        for node in ast.walk(tree):
            # Long methods
            if isinstance(node, ast.FunctionDef):
                body_lines = len(node.body)
                if body_lines > 50:
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="high",
                        category="code_smell",
                        message=f"Function '{node.name}' is too long ({body_lines} statements)",
                        suggestion="Consider breaking into smaller functions"
                    ))

                # Too many parameters
                param_count = len(node.args.args)
                if param_count > 7:
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="medium",
                        category="code_smell",
                        message=f"Function '{node.name}' has too many parameters ({param_count})",
                        suggestion="Consider using a parameter object or builder pattern"
                    ))

            # Magic numbers (use ast.Constant for Python 3.8+)
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)) and node.value not in (0, 1, -1, True, False, None):
                    # Check if in a constant assignment
                    parent = getattr(node, 'parent', None)
                    if not (isinstance(parent, ast.Assign) and
                            any(isinstance(t, ast.Name) and t.id.isupper() for t in parent.targets)):
                        issues.append(CodeIssue(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            severity="low",
                            category="code_smell",
                            message=f"Magic number detected: {node.value}",
                            suggestion="Consider using a named constant"
                        ))

        # Detect duplicate code blocks
        issues.extend(self._detect_duplicates(file_path, code))

        return issues

    def _check_complexity(self, file_path: Path, tree: ast.AST) -> list[CodeIssue]:
        """Check cyclomatic complexity."""
        issues: list[CodeIssue] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._calculate_complexity(node)
                if complexity > self.max_complexity:
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="high" if complexity > 15 else "medium",
                        category="complexity",
                        message=f"Function '{node.name}' has high cyclomatic complexity ({complexity})",
                        suggestion="Refactor to reduce branching and nesting"
                    ))

        return issues

    def _check_naming_conventions(self, file_path: Path, tree: ast.AST) -> list[CodeIssue]:
        """Check PEP 8 naming conventions."""
        issues: list[CodeIssue] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Functions should be snake_case
                if not re.match(r'^[a-z_][a-z0-9_]*$', node.name):
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="low",
                        category="naming",
                        message=f"Function '{node.name}' violates snake_case convention",
                        suggestion="Use lowercase with underscores"
                    ))

                # Too short names
                if len(node.name) < 3 and node.name not in ('__init__', '__str__', '__repr__'):
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="low",
                        category="naming",
                        message=f"Function name '{node.name}' is too short",
                        suggestion="Use descriptive names (3+ characters)"
                    ))

            if isinstance(node, ast.ClassDef):
                # Classes should be PascalCase
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="low",
                        category="naming",
                        message=f"Class '{node.name}' violates PascalCase convention",
                        suggestion="Use PascalCase for class names"
                    ))

        return issues

    def _check_documentation(self, file_path: Path, tree: ast.AST) -> list[CodeIssue]:
        """Check documentation completeness."""
        issues: list[CodeIssue] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                # Skip private/internal functions
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue

                has_docstring = (
                    ast.get_docstring(node) is not None and
                    len(ast.get_docstring(node) or "") > 10
                )

                if not has_docstring:
                    entity_type = "Function" if isinstance(node, ast.FunctionDef) else "Class"
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="medium",
                        category="documentation",
                        message=f"{entity_type} '{node.name}' lacks documentation",
                        suggestion="Add a docstring explaining purpose and parameters"
                    ))

        return issues

    def _check_performance(self, file_path: Path, tree: ast.AST, code: str) -> list[CodeIssue]:
        """Detect performance anti-patterns."""
        issues: list[CodeIssue] = []

        for node in ast.walk(tree):
            # String concatenation in loops
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                        if isinstance(child.target, ast.Name):
                            issues.append(CodeIssue(
                                file_path=str(file_path),
                                line_number=node.lineno,
                                severity="medium",
                                category="performance",
                                message="String concatenation in loop detected",
                                suggestion="Use list and join() for better performance"
                            ))

            # List comprehension vs append in loop
            if isinstance(node, ast.For):
                has_append = False
                for child in ast.walk(node.body[0]) if node.body else []:
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute) and child.func.attr == 'append':
                            has_append = True
                            break

                if has_append and len(node.body) == 1:
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        severity="low",
                        category="performance",
                        message="Consider using list comprehension instead of loop with append",
                        suggestion="Use [item for item in iterable] for better readability"
                    ))

        return issues

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                complexity += 1
            elif isinstance(child, ast.IfExp):  # Ternary expressions
                complexity += 1

        return complexity

    def _calculate_metrics(self, tree: ast.AST) -> dict[str, float]:
        """Calculate code metrics."""
        total_functions = 0
        total_complexity = 0
        documented_functions = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                total_functions += 1
                total_complexity += self._calculate_complexity(node)
                if ast.get_docstring(node):
                    documented_functions += 1

        return {
            "total_functions": float(total_functions),
            "avg_complexity": total_complexity / max(total_functions, 1),
            "doc_ratio": documented_functions / max(total_functions, 1),
        }

    def _detect_duplicates(self, file_path: Path, code: str) -> list[CodeIssue]:
        """Detect duplicate code blocks."""
        issues: list[CodeIssue] = []
        lines = code.splitlines()

        # Simple duplicate detection: look for repeated sequences of 5+ lines
        min_duplicate_lines = 5
        seen_blocks: dict[str, int] = {}

        for i in range(len(lines) - min_duplicate_lines + 1):
            block = "\n".join(lines[i:i + min_duplicate_lines])
            normalized = re.sub(r'\s+', ' ', block).strip()

            if normalized and len(normalized) > 50:  # Skip trivial blocks
                if normalized in seen_blocks:
                    issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=i + 1,
                        severity="medium",
                        category="code_smell",
                        message=f"Duplicate code block detected (similar to line {seen_blocks[normalized]})",
                        suggestion="Extract common code into a function"
                    ))
                else:
                    seen_blocks[normalized] = i + 1

        return issues


def review_directory(directory: Path, extensions: tuple[str, ...] = ('.py',)) -> tuple[ReviewResult, ...]:
    """Review all files in a directory."""
    reviewer = AICodeReviewer()
    results: list[ReviewResult] = []

    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix in extensions:
            # Skip test files and generated files
            if 'test_' in file_path.name or '__pycache__' in str(file_path):
                continue

            result = reviewer.review_file(file_path)
            results.append(result)

    return tuple(results)


def generate_review_report(results: tuple[ReviewResult, ...]) -> str:
    """Generate a comprehensive review report."""
    total_issues = sum(len(r.issues) for r in results)
    total_critical = sum(sum(1 for i in r.issues if i.severity == "critical") for r in results)
    total_high = sum(sum(1 for i in r.issues if i.severity == "high") for r in results)
    passed_count = sum(1 for r in results if r.passed)

    lines = [
        "=" * 80,
        "AI CODE REVIEW REPORT",
        "=" * 80,
        f"Files reviewed: {len(results)}",
        f"Files passed: {passed_count}/{len(results)}",
        f"Total issues: {total_issues}",
        f"  Critical: {total_critical}",
        f"  High: {total_high}",
        "",
    ]

    # Group issues by severity
    for severity in ["critical", "high", "medium", "low"]:
        severity_issues = [
            issue for result in results
            for issue in result.issues
            if issue.severity == severity
        ]

        if severity_issues:
            lines.append(f"\n{severity.upper()} SEVERITY ISSUES:")
            lines.append("-" * 80)
            for issue in severity_issues[:10]:  # Limit to top 10 per severity
                lines.append(issue.render())

    lines.append("\n" + "=" * 80)

    return "\n".join(lines)
