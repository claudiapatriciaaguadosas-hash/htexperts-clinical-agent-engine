from __future__ import annotations

from dataclasses import dataclass

from .contracts import IdentityLevel, TrustedContext


class AuthorizationError(Exception):
    """Raised when a deterministic policy denies a model proposal."""


URGENT_TERMS = {
    "dolor de pecho",
    "no puedo respirar",
    "desmayo",
    "sangrado",
    "convulsion",
    "convulsión",
    "suicidio",
}

TREATMENT_CHANGE_TERMS = {
    "cambiar medicamento",
    "suspender medicamento",
    "subir dosis",
    "bajar dosis",
    "dejar la pastilla",
}


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    name: str
    permission: str
    requires_verified_identity: bool = True
    requires_patient_context: bool = True
    write_action: bool = False
    human_review_required: bool = False


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "renalia.next_appointment": ToolPolicy("renalia.next_appointment", "appointments:read"),
    "renalia.confirm_attendance": ToolPolicy(
        "renalia.confirm_attendance",
        "appointments:write",
        write_action=True,
    ),
    "renalia.request_reschedule": ToolPolicy(
        "renalia.request_reschedule",
        "appointments:request_reschedule",
        write_action=True,
        human_review_required=True,
    ),
    "renalia.list_pending": ToolPolicy("renalia.list_pending", "pending:read"),
    "renalia.report_barrier": ToolPolicy(
        "renalia.report_barrier",
        "barriers:write",
        write_action=True,
        human_review_required=True,
    ),
    "renalia.report_measurement": ToolPolicy(
        "renalia.report_measurement",
        "measurements:report",
        write_action=True,
        human_review_required=True,
    ),
    "renalia.send_education": ToolPolicy("renalia.send_education", "education:send"),
    "renalia.create_handoff": ToolPolicy(
        "renalia.create_handoff",
        "handoff:create",
        write_action=True,
        human_review_required=True,
    ),
}


def detect_clinical_risk(text: str) -> str | None:
    normalized = text.lower()
    if any(term in normalized for term in URGENT_TERMS):
        return "urgent_symptom"
    if any(term in normalized for term in TREATMENT_CHANGE_TERMS):
        return "treatment_change"
    return None


def assert_tool_authorized(ctx: TrustedContext, tool_name: str) -> ToolPolicy:
    policy = TOOL_POLICIES.get(tool_name)
    if policy is None:
        raise AuthorizationError(f"Tool is not registered: {tool_name}")
    if policy.permission not in ctx.permissions:
        raise AuthorizationError(f"Missing permission: {policy.permission}")
    if policy.requires_verified_identity and ctx.identity_level is not IdentityLevel.VERIFIED:
        raise AuthorizationError("Verified identity is required")
    if policy.requires_patient_context and not ctx.patient_reference:
        raise AuthorizationError("Patient context is required")
    return policy

