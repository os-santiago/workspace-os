"""Tests for AI-powered code review module."""

import tempfile
from pathlib import Path

from workspace_os.ai_code_review import (
    AICodeReviewer,
    CodeIssue,
    ReviewResult,
    review_directory,
    generate_review_report,
)


def test_review_simple_valid_file():
    """Test reviewing a simple valid Python file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "example.py"
        file_path.write_text("""
def calculate_sum(numbers: list[int]) -> int:
    '''Calculate the sum of a list of numbers.'''
    return sum(numbers)
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        assert isinstance(result, ReviewResult)
        assert result.file_path == str(file_path)
        assert result.passed is True
        assert len(result.issues) == 0


def test_review_file_with_long_function():
    """Test detection of excessively long functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "long_function.py"

        # Create a function with > 50 statements
        lines = ["def long_function():\n"]
        lines.extend([f"    x{i} = {i}\n" for i in range(60)])
        file_path.write_text("".join(lines), encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should detect long function
        long_func_issues = [i for i in result.issues if "too long" in i.message]
        assert len(long_func_issues) > 0
        assert long_func_issues[0].severity == "high"
        assert long_func_issues[0].category == "code_smell"


def test_review_file_with_high_complexity():
    """Test detection of high cyclomatic complexity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "complex_function.py"
        file_path.write_text("""
def complex_function(a, b, c, d, e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return 1
                    else:
                        return 2
                else:
                    return 3
            else:
                return 4
        else:
            return 5
    else:
        return 6
""", encoding="utf-8")

        # Use lower threshold to ensure detection
        reviewer = AICodeReviewer(max_complexity=5)
        result = reviewer.review_file(file_path)

        # Should detect high complexity (5 nested ifs = complexity of 6)
        complexity_issues = [i for i in result.issues if "complexity" in i.message]
        assert len(complexity_issues) > 0
        assert complexity_issues[0].category == "complexity"


def test_review_file_with_bad_naming():
    """Test detection of naming convention violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "bad_naming.py"
        file_path.write_text("""
def BadFunctionName():
    pass

class lowercase_class:
    pass

def ab():
    pass
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should detect naming violations
        naming_issues = [i for i in result.issues if i.category == "naming"]
        assert len(naming_issues) >= 2  # At least function and class naming issues


def test_review_file_with_missing_documentation():
    """Test detection of missing documentation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "no_docs.py"
        file_path.write_text("""
def public_function(x, y):
    return x + y

class PublicClass:
    def method(self):
        return 42
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should detect missing docstrings
        doc_issues = [i for i in result.issues if i.category == "documentation"]
        assert len(doc_issues) >= 2  # Function and class should be flagged


def test_review_file_with_performance_antipattern():
    """Test detection of performance anti-patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "performance.py"
        file_path.write_text("""
def string_concatenation_in_loop():
    result = ""
    for i in range(100):
        result += str(i)
    return result
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should detect string concatenation in loop
        perf_issues = [i for i in result.issues if i.category == "performance"]
        assert len(perf_issues) > 0


def test_review_file_with_magic_numbers():
    """Test detection of magic numbers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "magic_numbers.py"
        file_path.write_text("""
def calculate():
    return 42 * 3.14159
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should detect magic numbers
        magic_issues = [i for i in result.issues if "Magic number" in i.message]
        assert len(magic_issues) >= 1


def test_review_file_invalid_syntax():
    """Test handling of files with invalid syntax."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "invalid.py"
        file_path.write_text("def invalid syntax here", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should handle gracefully
        assert result.passed is False
        assert "Failed to parse" in result.summary


def test_review_directory():
    """Test reviewing multiple files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()

        # Create multiple files
        (src_dir / "file1.py").write_text("""
def good_function():
    '''A well-documented function.'''
    return 42
""", encoding="utf-8")

        (src_dir / "file2.py").write_text("""
def BadNaming():
    pass
""", encoding="utf-8")

        results = review_directory(src_dir)

        assert len(results) == 2
        assert all(isinstance(r, ReviewResult) for r in results)


def test_review_directory_skips_test_files():
    """Test that test files are skipped during review."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()

        (src_dir / "module.py").write_text("def func(): pass", encoding="utf-8")
        (src_dir / "test_module.py").write_text("def test(): pass", encoding="utf-8")

        results = review_directory(src_dir)

        # Should only review module.py, not test_module.py
        assert len(results) == 1
        assert "module.py" in results[0].file_path


def test_generate_review_report():
    """Test report generation from review results."""
    results = (
        ReviewResult(
            file_path="file1.py",
            issues=(
                CodeIssue(
                    file_path="file1.py",
                    line_number=10,
                    severity="critical",
                    category="code_smell",
                    message="Critical issue",
                ),
            ),
            metrics={"avg_complexity": 5.0, "doc_ratio": 0.8},
            passed=False,
            summary="1 critical issue found"
        ),
        ReviewResult(
            file_path="file2.py",
            issues=(),
            metrics={"avg_complexity": 3.0, "doc_ratio": 1.0},
            passed=True,
            summary="No issues"
        ),
    )

    report = generate_review_report(results)

    assert "AI CODE REVIEW REPORT" in report
    assert "Files reviewed: 2" in report
    assert "Files passed: 1/2" in report
    assert "Critical: 1" in report


def test_code_issue_render():
    """Test rendering of code issues."""
    issue = CodeIssue(
        file_path="example.py",
        line_number=42,
        severity="high",
        category="complexity",
        message="Function too complex",
        suggestion="Refactor into smaller functions"
    )

    rendered = issue.render()

    assert "example.py:42" in rendered
    assert "complexity" in rendered
    assert "Function too complex" in rendered
    assert "Refactor into smaller functions" in rendered


def test_review_result_render_summary():
    """Test rendering of review result summary."""
    result = ReviewResult(
        file_path="example.py",
        issues=(
            CodeIssue(
                file_path="example.py",
                line_number=10,
                severity="critical",
                category="code_smell",
                message="Bad code",
            ),
            CodeIssue(
                file_path="example.py",
                line_number=20,
                severity="high",
                category="complexity",
                message="Too complex",
            ),
        ),
        metrics={"avg_complexity": 12.0, "doc_ratio": 0.5},
        passed=False,
        summary="2 issues found"
    )

    summary = result.render_summary()

    assert "example.py" in summary
    assert "Issues: 2" in summary
    assert "Critical: 1" in summary
    assert "High: 1" in summary


def test_complexity_calculation():
    """Test cyclomatic complexity calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "complexity.py"
        file_path.write_text("""
def simple():
    return 1

def with_if(x):
    if x:
        return 1
    return 0

def with_loop(items):
    for item in items:
        if item:
            return item
    return None
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Complexity should be calculated
        assert "avg_complexity" in result.metrics
        assert result.metrics["avg_complexity"] > 1.0


def test_documentation_ratio():
    """Test documentation ratio calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "docs.py"
        file_path.write_text("""
def documented():
    '''This function has documentation.'''
    return 1

def undocumented():
    return 2
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Should calculate doc ratio
        assert "doc_ratio" in result.metrics
        assert 0.0 <= result.metrics["doc_ratio"] <= 1.0


def test_review_with_private_functions():
    """Test that private functions don't require documentation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "private.py"
        file_path.write_text("""
def _private_function():
    return 42

def public_function():
    return 42
""", encoding="utf-8")

        reviewer = AICodeReviewer()
        result = reviewer.review_file(file_path)

        # Only public function should require docs
        doc_issues = [i for i in result.issues if i.category == "documentation"]
        assert len(doc_issues) == 1
        assert "public_function" in doc_issues[0].message


def test_configurable_thresholds():
    """Test that thresholds can be configured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("""
def moderate_complexity(a, b, c):
    if a:
        if b:
            if c:
                return 1
    return 0
""", encoding="utf-8")

        # Strict threshold
        strict_reviewer = AICodeReviewer(max_complexity=5)
        strict_result = strict_reviewer.review_file(file_path)

        # Lenient threshold
        lenient_reviewer = AICodeReviewer(max_complexity=20)
        lenient_result = lenient_reviewer.review_file(file_path)

        strict_complexity_issues = [
            i for i in strict_result.issues if i.category == "complexity"
        ]
        lenient_complexity_issues = [
            i for i in lenient_result.issues if i.category == "complexity"
        ]

        # Strict should find more issues
        assert len(strict_complexity_issues) >= len(lenient_complexity_issues)
