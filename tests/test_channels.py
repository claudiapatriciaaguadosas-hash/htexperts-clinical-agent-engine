from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from htexperts_engine.adapters.meta import MetaWebhookSandbox
from htexperts_engine.adapters.retell import RetellSandbox, RetellSessionBinding


class ChannelSandboxTests(unittest.TestCase):
    def test_meta_signature_uses_raw_body_hmac(self) -> None:
        body = b'{"entry":[]}'
        signature = MetaWebhookSandbox.sign(body, "secret")

        self.assertTrue(MetaWebhookSandbox.verify_signature(body, signature, "secret"))
        self.assertFalse(MetaWebhookSandbox.verify_signature(body + b" ", signature, "secret"))

    def test_retell_call_id_alone_is_not_authorization(self) -> None:
        sandbox = RetellSandbox()
        with self.assertRaises(PermissionError):
            sandbox.assert_authenticated(
                RetellSessionBinding(
                    call_id="call-1",
                    channel_connection_id="voice-1",
                    product_id="renalia",
                    tenant_id="clinic-a",
                    authenticated=False,
                )
            )


if __name__ == "__main__":
    unittest.main()

