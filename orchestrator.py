from __future__ import annotations

from .adapters.renalia import RenaliaLabAdapter
from .contracts import ActionProposal, ToolResult, ToolStatus, TrustedContext
from .policy import AuthorizationError, assert_tool_authorized, detect_clinical_risk
from .repository import EngineRepository


URGENT_MESSAGE = (
    "Por seguridad, busca atención inmediata según tu contexto local. "
    "Este asistente no sustituye los canales de emergencia."
)


class ClinicalAgentEngine:
    def __init__(self, repository: EngineRepository) -> None:
        self.repository = repository
        self.renalia = RenaliaLabAdapter(repository)

    def handle(self, ctx: TrustedContext, user_text: str, proposal: ActionProposal) -> ToolResult:
        risk = detect_clinical_risk(user_text)
        if risk == "urgent_symptom":
            audit_id = self.repository.audit(ctx, decision="urgent_handoff", detail={"risk": risk})
            handoff_id = self.repository.create_handoff(ctx, "Possible urgent symptom", "urgent")
            return ToolResult(
                ToolStatus.REVIEW_REQUIRED,
                {"handoff_id": handoff_id},
                review_required=True,
                audit_reference=audit_id,
                message=URGENT_MESSAGE,
            )

        if risk == "treatment_change":
            audit_id = self.repository.audit(ctx, decision="treatment_change_handoff", detail={"risk": risk})
            handoff_id = self.repository.create_handoff(ctx, "Medication change request", "high")
            return ToolResult(
                ToolStatus.REVIEW_REQUIRED,
                {"handoff_id": handoff_id},
                review_required=True,
                audit_reference=audit_id,
                message="Esa solicitud debe revisarla el equipo clínico.",
            )

        if not proposal.tool_name:
            audit_id = self.repository.audit(ctx, decision="respond_only", detail={"intent": proposal.intent})
            return ToolResult(ToolStatus.OK, {"response": proposal.response_draft}, audit_reference=audit_id)

        try:
            policy = assert_tool_authorized(ctx, proposal.tool_name)
        except AuthorizationError as exc:
            audit_id = self.repository.audit(
                ctx,
                decision="denied",
                tool_name=proposal.tool_name,
                detail={"reason": str(exc), "intent": proposal.intent},
            )
            return ToolResult(ToolStatus.DENIED, audit_reference=audit_id, message=str(exc))

        if ctx.product_id == "renalia":
            result = self.renalia.execute(ctx, proposal.tool_name, proposal.arguments)
        else:
            result = ToolResult(ToolStatus.DENIED, message="No adapter registered for product")

        decision = "allowed"
        review_required = result.review_required or policy.human_review_required
        if result.status is ToolStatus.DENIED:
            decision = "denied"
        elif review_required:
            decision = "review_required"

        audit_id = self.repository.audit(
            ctx,
            decision=decision,
            tool_name=proposal.tool_name,
            detail={"status": result.status.value, "intent": proposal.intent},
        )
        return ToolResult(
            status=result.status,
            authorized_payload=result.authorized_payload,
            review_required=review_required,
            audit_reference=audit_id,
            retryable=result.retryable,
            message=result.message,
        )

