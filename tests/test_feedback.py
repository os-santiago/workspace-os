from __future__ import annotations

import unittest

from workspace_os.feedback import assess_feedback


class FeedbackAssessmentTests(unittest.TestCase):
    def test_assess_feedback_infers_common_agent_errors(self):
        too_verbose = assess_feedback(
            "Please summarize the repo state.",
            "This is a long explanation with a lot of unnecessary detail.",
            "This is too verbose and not helpful.",
        )
        wrong_agent = assess_feedback(
            "Please analyze the repo.",
            "I routed this through the wrong agent.",
            "Wrong agent, please use the preferred route next time.",
        )
        missing_repo = assess_feedback(
            "Please analyze the repo.",
            "I could not resolve the repository name.",
            "This is wrong; you missed the repo resolution.",
        )

        self.assertEqual("questionable", too_verbose.status)
        self.assertEqual("too_verbose", too_verbose.error_type)
        self.assertEqual("questionable", wrong_agent.status)
        self.assertEqual("wrong_agent", wrong_agent.error_type)
        self.assertEqual("questionable", missing_repo.status)
        self.assertEqual("missing_repo_resolution", missing_repo.error_type)


if __name__ == "__main__":
    unittest.main()
