from __future__ import annotations

import unittest

from ctx2doc.redaction import redact_text


class RedactionTest(unittest.TestCase):
    def test_redacts_bearer_tokens_and_assignments(self) -> None:
        source = "Authorization: Bearer abcdef123456\napi_key=secret123"
        redacted = redact_text(source)
        self.assertIn("Authorization: Bearer [REDACTED]", redacted)
        self.assertIn("api_key=[REDACTED]", redacted)

    def test_redacts_private_key_blocks(self) -> None:
        source = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
        redacted = redact_text(source)
        self.assertIn("[REDACTED]", redacted)
        self.assertNotIn("abc", redacted)
