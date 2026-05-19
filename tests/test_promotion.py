from pathlib import Path
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.promotion import build_promotion_proposal


class PromotionTests(unittest.TestCase):
    def test_build_promotion_proposal_renders_related_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ADEV.md").write_text("Agents must validate scripts.\n", encoding="utf-8")
            source = Source("adev", "doctrine", "Doctrine.", root)

            proposal = build_promotion_proposal(
                sources=[source],
                target="adev",
                rule="Agents must validate scripts.",
                evidence="scanales-kb:captures/session/example.md",
                max_matches=5,
            )
            rendered = proposal.render_markdown()

        self.assertIn("# Promotion Proposal", rendered)
        self.assertIn("Target: adev", rendered)
        self.assertIn("adev:ADEV.md:1", rendered)

    def test_build_promotion_proposal_sanitizes_rule_and_evidence(self):
        proposal = build_promotion_proposal(
            sources=[],
            target="adev",
            rule="Never store token=plain-text",
            evidence="password: plain-text",
        )
        rendered = proposal.render_markdown()

        self.assertIn("token=[REDACTED]", rendered)
        self.assertIn("password: [REDACTED]", rendered)
        self.assertNotIn("plain-text", rendered)

    def test_build_promotion_proposal_rejects_unknown_target(self):
        with self.assertRaisesRegex(ValueError, "Promotion target"):
            build_promotion_proposal([], "unknown", "Rule", "Evidence")


if __name__ == "__main__":
    unittest.main()
