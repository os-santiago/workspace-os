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
)


class ConscienceTests(unittest.TestCase):
    def test_allows_low_risk_software_work(self):
        decision = evaluate_request("Add a unit test for the search command.")

        self.assertEqual(ALLOW, decision.decision)
        self.assertEqual("low", decision.risk_level)
        self.assertTrue(decision.allows_execution())

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

    def test_blocks_google_destination_until_connector_exists(self):
        decision = evaluate_request("Create a proposal.", destination="documents")

        self.assertEqual(ASK_CLARIFICATION, decision.decision)
        self.assertIn("google_drive_connector", decision.missing_context)

    def test_redirects_ambiguous_requests_to_agents(self):
        decision = evaluate_request("What should we do next?")

        self.assertEqual(SAFE_REDIRECT, decision.decision)
        self.assertEqual("redirect_to_primary_agent_then_fallback", decision.response_strategy)
        self.assertEqual("codex", decision.primary_agent)
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


if __name__ == "__main__":
    unittest.main()
