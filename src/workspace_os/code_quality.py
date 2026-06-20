# Automated Code Quality Module
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import ast
import re
import subprocess
import json

@dataclass(frozen=True)
class QualityMetric:
    name: str
    value: float
    threshold: float
    passed: bool
    category: Literal["complexity", "coverage", "security", "style", "documentation"]
    detail: str
    
    def render(self) -> str:
        status = "✓" if self.passed else "✗"
        return f"{status} {self.name}: {self.value:.2f} (threshold: {self.threshold}) - {self.detail}"

@dataclass(frozen=True)
class QualityReport:
    file_path: str
    metrics: tuple[QualityMetric, ...]
    overall_score: float
    passed: bool
    summary: str

@dataclass(frozen=True)
class QualityThresholds:
    max_complexity: int = 10
    min_coverage: float = 80.0
    max_function_length: int = 50
    max_line_length: int = 120
    min_documentation_ratio: float = 0.5
