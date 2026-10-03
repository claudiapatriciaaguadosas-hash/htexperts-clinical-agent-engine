from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetellSessionBinding:
    call_id: str
    channel_connection_id: str
    product_id: str
    tenant_id: str
    authenticated: bool


class RetellSandbox:
    """Retell Custom LLM sandbox binding.

    A call id alone is never authorization. The caller must provide a registered
    binding resolved from server-side channel configuration.
    """

    def assert_authenticated(self, binding: RetellSessionBinding) -> None:
        if not binding.authenticated:
            raise PermissionError("Retell session is not authenticated")

