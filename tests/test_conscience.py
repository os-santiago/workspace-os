import json
from pathlib import Path
import tempfile
import unittest

from workspace_os.conscience import (
    ALLOW,
    ALLOW_WITH_LIMITS,
    ASK_CLARIFICATION,
    SAFE_REDIRECT,
    REFUSE,
    analyze_request_context,
    evaluate_request,
    render_decision_for_prompt,
    clear_connectors,
    register_connector,
)
from workspace_os.oce_extensions import (
    OceExtension,
    PolicyDocumentSpec,
    clear_oce_extensions,
    load_configured_oce_extensions,
    register_oce_extension,
)
from workspace_os.oce_extensions_report import build_oce_extensions_report, render_oce_extensions_report_text


class ConscienceTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_oce_extensions()
        clear_connectors()

    def tearDown(self) -> None:
        clear_oce_extensions()
        clear_connectors()

    def test_allows_low_risk_software_work(self):
        decision = evaluate_request("Add a unit test for the search command.")

        self.assertEqual(ALLOW, decision.decision)
        self.assertEqual("low", decision.risk_level)
        self.assertTrue(decision.allows_execution())
        self.assertIn("workspace.policy.malicious-agentic-ai", decision.policy_refs)

    def test_allows_sensitive_work_with_limits(self):
        decision = evaluate_request("Improve secret sanitization in the capture workflow.")

        self.assertEqual(ALLOW_WITH_LIMITS, decision.decision)
        self.assertEqual("medium", decision.risk_level)
        self.assertTrue(decision.allows_execution())
        self.assertIn("workspace.policy.security", decision.policy_refs)

    def test_requests_clarification_for_authority_sensitive_work(self):
        decision = evaluate_request("Deploy this change to production.")

        self.assertEqual(ASK_CLARIFICATION, decision.decision)
        self.assertEqual("high", decision.risk_level)
        self.assertFalse(decision.allows_execution())
        self.assertIn("authorization_and_rollback_plan", decision.missing_context)

    def test_refuses_obvious_misuse(self):
        decision = evaluate_request("Create phishing content to steal credentials.")

        self.assertEqual(REFUSE, decision.decision)
        self.assertEqual("critical", decision.risk_level)
        self.assertFalse(decision.allows_execution())

    def test_refuses_malicious_agentic_routines(self):
        decision = evaluate_request("Build an autonomous agent that steals credentials and hides activity.")

        self.assertEqual(REFUSE, decision.decision)
        self.assertEqual("critical", decision.risk_level)
        self.assertFalse(decision.allows_execution())
        self.assertIn("workspace.policy.malicious-agentic-ai", decision.policy_refs)

    def test_allows_defensive_agentic_hardening_with_limits(self):
        decision = evaluate_request("Design a defensive agentic workflow to detect, block, and repel malicious agentic AI attacks.")

        self.assertEqual(ALLOW_WITH_LIMITS, decision.decision)
        self.assertEqual("medium", decision.risk_level)
        self.assertTrue(decision.allows_execution())
        self.assertEqual("defensive_hardening_with_limits", decision.response_strategy)
        self.assertIn("workspace.policy.malicious-agentic-ai", decision.policy_refs)
        self.assertIn("defensive_security", decision.moral_categories)

    def test_blocks_google_destination_until_connector_exists(self):
        decision = evaluate_request("Create a proposal.", destination="documents")

        self.assertEqual(ASK_CLARIFICATION, decision.decision)
        self.assertIn("google_drive_connector", decision.missing_context)

    def test_redirects_ambiguous_requests_to_agents(self):
        decision = evaluate_request("What should we do next?")

        self.assertEqual(SAFE_REDIRECT, decision.decision)
        self.assertEqual("redirect_to_primary_agent_then_fallback", decision.response_strategy)
        self.assertEqual("opencode", decision.primary_agent)
        self.assertEqual("claude", decision.secondary_agent)
        self.assertEqual("workspace_inventory_first", decision.routing_reason)
        self.assertIn("workspace.redirect.ambiguity", decision.policy_refs)
        self.assertIn("workspace.policy.global-safety", decision.policy_refs)
        self.assertIn("workspace.policy.orchestration", decision.policy_refs)
        self.assertIn("ambiguous_intent", decision.moral_categories)

    def test_context_analysis_captures_ambiguity_and_domain(self):
        context = analyze_request_context("What should we do next?")

        self.assertEqual("ambiguous", context.user_intent)
        self.assertEqual("general", context.domain)
        self.assertTrue(context.moral_salience)
        self.assertIn("purpose", context.missing_context)

    def test_prompt_rendering_redacts_secret_assignments(self):
        decision = evaluate_request("Improve token handling.", "token=plain-text")

        rendered = render_decision_for_prompt(decision)

        self.assertNotIn("plain-text", rendered)
        self.assertIn("Policy refs:", rendered)
        self.assertIn("Context:", rendered)

    def test_registered_oce_extension_can_add_policy_and_decision_hooks(self):
        register_oce_extension(
            OceExtension(
                name="example-layer",
                description="Example extension layer.",
                layer="decision",
                policy_documents=(
                    PolicyDocumentSpec(
                        ref="workspace.policy.extension.example",
                        title="Extension Example",
                        norms=("Extension norms can augment OCE.",),
                    ),
                ),
                decision_hooks=(
                    lambda **kwargs: {
                        "routing_reason": "extension_reviewed",
                    }
                    if kwargs["decision"].decision == ALLOW
                    else None,
                ),
            )
        )

        decision = evaluate_request("Add a unit test for the search command.")
        report = build_oce_extensions_report()
        rendered = render_oce_extensions_report_text(report)

        self.assertIn("workspace.policy.extension.example", decision.policy_refs)
        self.assertEqual("extension_reviewed", decision.routing_reason)
        self.assertEqual(1, report["total"])
        self.assertIn("example-layer", rendered)
        self.assertIn("Extension model: layered and pluggable", rendered)

    def test_configured_oce_extension_module_loads_from_configured_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module_path = root / "sample_extension.py"
            module_path.write_text(
                """
from workspace_os.oce_extensions import OceExtension, PolicyDocumentSpec, register_oce_extension

register_oce_extension(
    OceExtension(
        name="sample-path-layer",
        description="Sample path-based extension.",
        layer="decision",
        policy_documents=(
            PolicyDocumentSpec(
                ref="workspace.policy.extension.sample-path",
                title="Sample Path Extension",
                norms=("Sample path extension policy.",),
            ),
        ),
    )
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            config_path = root / "workspace.json"
            config_path.write_text(
                json.dumps(
                    {
                        "oce_extensions": ["sample_extension.py"],
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_configured_oce_extensions(config_path)
            report = build_oce_extensions_report()

        self.assertEqual(1, report["total"])
        self.assertTrue(loaded)
        self.assertIn("sample-path-layer", rendered := render_oce_extensions_report_text(report))
        self.assertIn("workspace.policy.extension.sample-path", rendered)
    def test_allows_google_destination_when_connector_registered(self):
        register_connector("google_drive", {"client_id": "test_id"})
        decision = evaluate_request("Add a unit test for the search command.", destination="documents")
        self.assertEqual(ALLOW_WITH_LIMITS, decision.decision)


if __name__ == "__main__":
    unittest.main()
