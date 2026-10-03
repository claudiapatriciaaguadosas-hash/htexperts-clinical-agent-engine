from __future__ import annotations

from typing import Any

from htexperts_engine.contracts import ToolResult, ToolStatus, TrustedContext
from htexperts_engine.repository import EngineRepository


class RenaliaLabAdapter:
    """Synthetic RENALIA adapter for delivery 1.

    This adapter intentionally does not infer the real RENALIA schema. It only
    proves the engine contract with synthetic data.
    """

    product_id = "renalia"

    def __init__(self, repository: EngineRepository) -> None:
        self.repository = repository

    def execute(self, ctx: TrustedContext, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if ctx.product_id != self.product_id:
            return ToolResult(ToolStatus.DENIED, message="Adapter product mismatch")

        if tool_name == "renalia.next_appointment":
            appointment = self.repository.next_appointment(ctx)
            if appointment is None:
                return ToolResult(ToolStatus.NOT_FOUND, message="No scheduled appointment found")
            return ToolResult(ToolStatus.OK, {"appointment": appointment})

        if tool_name == "renalia.confirm_attendance":
            appointment_id = str(arguments.get("appointment_id", ""))
            idempotency_key = f"{ctx.product_id}:{ctx.tenant_id}:{ctx.patient_reference}:confirm:{appointment_id}"

            def create() -> ToolResult:
                updated = self.repository.confirm_appointment(ctx, appointment_id)
                if not updated:
                    return ToolResult(ToolStatus.NOT_FOUND, message="Appointment not found in authorized scope")
                return ToolResult(ToolStatus.OK, {"appointment_id": appointment_id, "status": "confirmed"})

            return self.repository.idempotent("confirm_attendance", idempotency_key, create)

        if tool_name == "renalia.list_pending":
            return ToolResult(ToolStatus.OK, {"pending": self.repository.list_pending(ctx)})

        if tool_name == "renalia.report_measurement":
            kind = str(arguments.get("kind", "unknown"))
            value = str(arguments.get("value", ""))
            measurement_id = self.repository.record_measurement(ctx, kind, value)
            return ToolResult(
                ToolStatus.REVIEW_REQUIRED,
                {"measurement_id": measurement_id, "status": "pending_review"},
                review_required=True,
                message="Measurement saved for human review",
            )

        if tool_name == "renalia.report_barrier":
            reason = str(arguments.get("barrier", "unspecified barrier"))
            handoff_id = self.repository.create_handoff(ctx, f"Barrier reported: {reason}", "normal")
            return ToolResult(
                ToolStatus.REVIEW_REQUIRED,
                {"handoff_id": handoff_id, "status": "created"},
                review_required=True,
            )

        if tool_name == "renalia.request_reschedule":
            handoff_id = self.repository.create_handoff(ctx, "Reschedule requested", "normal")
            return ToolResult(
                ToolStatus.REVIEW_REQUIRED,
                {"handoff_id": handoff_id, "status": "created"},
                review_required=True,
                message="A reschedule request was created; no slot is promised",
            )

        if tool_name == "renalia.create_handoff":
            reason = str(arguments.get("reason", "human review requested"))
            priority = str(arguments.get("priority", "normal"))
            handoff_id = self.repository.create_handoff(ctx, reason, priority)
            return ToolResult(
                ToolStatus.REVIEW_REQUIRED,
                {"handoff_id": handoff_id, "status": "created"},
                review_required=True,
            )

        if tool_name == "renalia.send_education":
            topic = str(arguments.get("topic", "kidney_care"))
            return ToolResult(ToolStatus.OK, {"material": f"approved://renalia/{topic}"})

        return ToolResult(ToolStatus.DENIED, message=f"Unsupported RENALIA tool: {tool_name}")

