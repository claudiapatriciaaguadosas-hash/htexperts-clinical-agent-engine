from __future__ import annotations

import hashlib
import hmac


class MetaWebhookSandbox:
    """Sandbox helper for Meta webhook validation.

    The production implementation must validate against Meta's current
    signature header and raw POST body. This class supports lab tests without
    sending or receiving real WhatsApp traffic.
    """

    @staticmethod
    def sign(body: bytes, app_secret: str) -> str:
        digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    @staticmethod
    def verify_signature(body: bytes, signature_header: str, app_secret: str) -> bool:
        expected = MetaWebhookSandbox.sign(body, app_secret)
        return hmac.compare_digest(expected, signature_header)

