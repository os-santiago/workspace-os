import unittest

from workspace_os.sanitization import sanitize_text


class SanitizationTests(unittest.TestCase):
    def test_sanitize_text_redacts_common_secret_assignments(self):
        self.assertEqual("password: [REDACTED]", sanitize_text("password: plain-text"))
        self.assertEqual("api_key=[REDACTED]", sanitize_text("api_key=abc123"))


if __name__ == "__main__":
    unittest.main()
