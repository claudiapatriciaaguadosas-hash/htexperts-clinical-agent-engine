from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    RETELL_VOICE = "retell_voice"
    ADMIN = "admin"


class IdentityLevel(StrEnum):
    UNKNOWN = "unknown"
    CONTACT_HINT = "contact_hint"
    VERIFIED = "verified"


class ToolStatus(StrEnum):
    OK = "ok"
    DENIED = "denied"
    REVIEW_REQUIRED = "review_required"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TrustedContext:
    product_id: str
    tenant_id: str
    channel_connection_id: str
    channel: Channel
    session_id: str
    authenticated_principal_id: str | None
    patient_reference: str | None
    identity_level: IdentityLevel
    permissions: frozenset[str]
    policy_version: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ActionProposal:
    intent: str
    response_draft: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    uncertainty: float = 0.0


@dataclass(frozen=True, slots=True)
class ToolResult:
    status: ToolStatus
    authorized_payload: dict[str, Any] = field(default_factory=dict)
    review_required: bool = False
    audit_reference: str | None = None
    retryable: bool = False
    message: str = ""


@dataclass(frozen=True, slots=True)
class Handoff:
    reason: str
    priority: str
    recipient: str
    due_at: str
    status: str = "created"
    acknowledgement: str | None = None
    closed_at: str | None = None

