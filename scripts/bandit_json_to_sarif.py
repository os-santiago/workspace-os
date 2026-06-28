from __future__ import annotations

"""Convert Bandit JSON output into SARIF for GitHub Code Scanning."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


SARIF_VERSION = "2.1.0"


@dataclass(frozen=True)
class SarifLocation:
    uri: str
    start_line: int | None = None
    start_column: int | None = None


def convert_bandit_json_to_sarif(payload: dict[str, Any], tool_name: str = "Bandit") -> dict[str, Any]:
    results = payload.get("results", [])
    sarif_results: list[dict[str, Any]] = []
    rule_ids: set[str] = set()

    for issue in results:
        test_id = str(issue.get("test_id") or issue.get("test") or "BANDIT")
        rule_ids.add(test_id)
        location = _location_from_issue(issue)
        sarif_results.append(
            {
                "ruleId": test_id,
                "level": _sarif_level(str(issue.get("issue_severity", "medium"))),
                "message": {
                    "text": str(issue.get("issue_text") or issue.get("issue_text", "Bandit finding")),
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": location.uri},
                            "region": {
                                **({"startLine": location.start_line} if location.start_line is not None else {}),
                                **({"startColumn": location.start_column} if location.start_column is not None else {}),
                            },
                        }
                    }
                ],
                "properties": {
                    "severity": issue.get("issue_severity"),
                    "confidence": issue.get("issue_confidence"),
                    "moreInfo": issue.get("more_info"),
                    "lineRange": issue.get("line_range"),
                },
            }
        )

    rules = [
        {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": rule_id},
        }
        for rule_id in sorted(rule_ids)
    ]

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "informationUri": "https://bandit.readthedocs.io/",
                        "rules": rules,
                    }
                },
                "results": sarif_results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }
        ],
    }


def _location_from_issue(issue: dict[str, Any]) -> SarifLocation:
    filename = str(issue.get("filename") or issue.get("file") or "src")
    line_number = issue.get("line_number")
    if isinstance(line_number, int):
        return SarifLocation(uri=filename, start_line=line_number)
    if isinstance(line_number, str) and line_number.isdigit():
        return SarifLocation(uri=filename, start_line=int(line_number))
    return SarifLocation(uri=filename)


def _sarif_level(severity: str) -> str:
    normalized = severity.strip().casefold()
    if normalized in {"high", "critical"}:
        return "error"
    if normalized == "medium":
        return "warning"
    return "note"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: bandit_json_to_sarif.py <input.json> <output.sarif>", file=sys.stderr)
        return 2

    input_path = Path(argv[0])
    output_path = Path(argv[1])
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Bandit JSON payload must be an object.")

    sarif = convert_bandit_json_to_sarif(payload)
    output_path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
