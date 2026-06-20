from __future__ import annotations

from workspace_os.oce_extensions import extension_summary_lines, registered_oce_extensions


def build_oce_extensions_report() -> dict[str, object]:
    extensions = [extension.to_dict() for extension in registered_oce_extensions()]
    return {
        "total": len(extensions),
        "extensions": extensions,
    }


def render_oce_extensions_report_text(report: dict[str, object] | None = None) -> str:
    if report is None:
        report = build_oce_extensions_report()
    lines = ["OCE extensions"]
    lines.extend(extension_summary_lines())
    extensions = report.get("extensions", [])
    if extensions:
        lines.append("extension_details:")
        for extension in extensions:
            lines.append(
                f"- {extension.get('name', 'n/a')}: layer={extension.get('layer', 'n/a')} "
                f"docs={len(extension.get('policy_documents', []))} "
                f"context_hooks={extension.get('context_hooks', 0)} "
                f"decision_hooks={extension.get('decision_hooks', 0)}"
            )
            policy_documents = extension.get("policy_documents", [])
            if policy_documents:
                lines.append("  policy_documents:")
                for document in policy_documents:
                    lines.append(
                        f"  - {document.get('ref', 'n/a')}: {document.get('title', 'n/a')}"
                    )
    lines.append("Hardening: always-on malicious agentic protection")
    lines.append("Extension model: layered and pluggable")
    return "\n".join(lines) + "\n"
