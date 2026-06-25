"""Workspace OS package."""

__version__ = "0.1.0"

# Import AI code review module for easy access
from workspace_os.ai_code_review import (
    AICodeReviewer,
    CodeIssue,
    ReviewResult,
    review_directory,
    generate_review_report,
)

__all__ = [
    "AICodeReviewer",
    "CodeIssue",
    "ReviewResult",
    "review_directory",
    "generate_review_report",
]
