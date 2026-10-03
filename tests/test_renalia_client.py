from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from htexperts_engine.renalia_client import (
    RENALIA_PUBLIC_AGENT_BASE_PATH,
    RenaliaApiClient,
    RenaliaClientConfig,
    RenaliaClientError,
    RenaliaHttpResponse,
    base64url_hmac_sha256,
    build_signed_input,
    canonical_json_bytes,
    redact_sensitive,
)


class FakeTransport:
    def __init__(self, responses: list[RenaliaHttpResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> RenaliaHttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.responses:
            raise AssertionError("No fake response queued")
        return self.responses.pop(0)


def response(status_code: int, payload: dict[str, Any]) -> RenaliaHttpResponse:
    return RenaliaHttpResponse(status_code, json.dumps(payload).encode("utf-8"), {})


def response_with_headers(status_code: int, payload: dict[str, Any], headers: dict[str, str]) -> RenaliaHttpResponse:
    return RenaliaHttpResponse(status_code, json.dumps(payload).encode("utf-8"), headers)


def config(max_attempts: int = 3) -> RenaliaClientConfig:
    return RenaliaClientConfig(
        api_base_url="https://renalia.example.test",
        installation_id="inst_demo",
        credential_id="cred_demo",
        signing_secret="secret_demo",
        timeout_seconds=5,
        max_attempts=max_attempts,
    )


def session(channel: str = "whatsapp") -> dict[str, str]:
    return {
        "channel": channel,
        "engine_session_id": "ses_demo",
        "engine_correlation_id": "corr_demo",
    }


def patient_identity() -> dict[str, str]:
    return {"patient_ref": "patref_demo", "identity_proof": "idp_demo_secret"}


class RenaliaClientTests(unittest.TestCase):
    def test_hmac_signature_matches_contract_shape(self) -> None:
        body = canonical_json_bytes({"b": 2, "a": 1})
        signed_input = build_signed_input(
            "POST",
            f"{RENALIA_PUBLIC_AGENT_BASE_PATH}/tools/appointments/next",
            1791065400,
            "request-1",
            body,
        )

        signature = base64url_hmac_sha256("secret_demo", signed_input)

        self.assertNotIn("=", signature)
        self.assertEqual(signature, "HFFSfI7mmCSFwO_8RyRHCFrvyQyNBmuYD83oP1olNgI")

    def test_patient_tool_requires_identity_proof_before_network_call(self) -> None:
        transport = FakeTransport([])
        client = RenaliaApiClient(config(), transport=transport, clock=lambda: 1791065400)

        with self.assertRaises(RenaliaClientError) as raised:
            client.next_appointment(session=session(), patient_identity={"patient_ref": "patref_demo"})

        self.assertEqual(raised.exception.code, "identity_not_verified")
        self.assertEqual(raised.exception.http_status, 403)
        self.assertEqual(transport.calls, [])

    def test_voice_channel_is_blocked_locally_until_consent_exists(self) -> None:
        transport = FakeTransport([])
        client = RenaliaApiClient(config(), transport=transport, clock=lambda: 1791065400)

        with self.assertRaises(RenaliaClientError) as raised:
            client.handoff_status(
                session=session("retell_voice"),
                patient_identity=patient_identity(),
                handoff_ref="handoff_demo",
            )

        self.assertEqual(raised.exception.code, "consent_revoked")
        self.assertIn("voice", str(raised.exception).lower())
        self.assertEqual(transport.calls, [])

    def test_retry_uses_new_request_id_and_signature_but_same_body_and_idempotency(self) -> None:
        transport = FakeTransport(
            [
                response(
                    503,
                    {
                        "error": {
                            "code": "temporarily_unavailable",
                            "message": "try again",
                            "retryable": True,
                            "correlation_id": "corr_demo",
                        }
                    },
                ),
                response(
                    200,
                    {
                        "status": "review_required",
                        "data": {"reported_value_ref": "rvref_demo", "review_status": "pending"},
                        "review_required": True,
                        "audit_ref": "audit_demo",
                        "idempotency": {"key": "idem_measurement_demo", "deduped": False},
                    },
                ),
            ]
        )
        ids = iter(["request-1", "request-2"])
        client = RenaliaApiClient(
            config(max_attempts=2),
            transport=transport,
            clock=lambda: 1791065400,
            sleeper=lambda seconds: None,
            request_id_factory=lambda: next(ids),
        )

        result = client.report_measurement(
            session=session(),
            patient_identity=patient_identity(),
            measurement={"lab_type": "systolic_bp", "value": "140", "unit": "mmHg", "raw_text": "140/90"},
            idempotency_key="idem_measurement_demo",
        )

        self.assertEqual(result["status"], "review_required")
        self.assertEqual(len(transport.calls), 2)
        first, second = transport.calls
        self.assertEqual(first["body"], second["body"])
        self.assertEqual(first["headers"]["X-HTE-Idempotency-Key"], "idem_measurement_demo")
        self.assertEqual(second["headers"]["X-HTE-Idempotency-Key"], "idem_measurement_demo")
        self.assertEqual(first["headers"]["X-HTE-Request-Id"], "request-1")
        self.assertEqual(second["headers"]["X-HTE-Request-Id"], "request-2")
        self.assertNotEqual(first["headers"]["Authorization"], second["headers"]["Authorization"])

    def test_rate_limit_retry_respects_retry_after(self) -> None:
        slept: list[float] = []
        transport = FakeTransport(
            [
                response_with_headers(
                    429,
                    {
                        "error": {
                            "code": "rate_limited",
                            "message": "too many requests",
                            "retryable": True,
                            "correlation_id": "corr_demo",
                        }
                    },
                    {"Retry-After": "2"},
                ),
                response(
                    200,
                    {
                        "status": "ok",
                        "data": {"appointment": {"appointment_ref": "apptref_demo"}},
                        "review_required": False,
                        "audit_ref": "audit_demo",
                    },
                ),
            ]
        )
        ids = iter(["request-1", "request-2"])
        client = RenaliaApiClient(
            config(max_attempts=2),
            transport=transport,
            clock=lambda: 1791065400,
            sleeper=lambda seconds: slept.append(seconds),
            request_id_factory=lambda: next(ids),
        )

        result = client.next_appointment(session=session(), patient_identity=patient_identity())

        self.assertEqual(result["status"], "ok")
        self.assertEqual(slept, [2.0])
        self.assertEqual(transport.calls[0]["body"], transport.calls[1]["body"])

    def test_in_progress_state_conflict_is_retryable(self) -> None:
        transport = FakeTransport(
            [
                response(
                    409,
                    {
                        "error": {
                            "code": "state_conflict",
                            "message": "idempotent request is still in progress",
                            "retryable": True,
                            "correlation_id": "corr_demo",
                        }
                    },
                ),
                response(
                    200,
                    {
                        "status": "ok",
                        "data": {"appointment_ref": "apptref_demo", "status": "confirmed"},
                        "review_required": False,
                        "audit_ref": "audit_demo",
                        "idempotency": {"key": "idem_confirm_demo", "deduped": True},
                    },
                ),
            ]
        )
        ids = iter(["request-1", "request-2"])
        client = RenaliaApiClient(
            config(max_attempts=2),
            transport=transport,
            clock=lambda: 1791065400,
            sleeper=lambda seconds: None,
            request_id_factory=lambda: next(ids),
        )

        result = client.confirm_appointment(
            session=session(),
            patient_identity=patient_identity(),
            appointment_ref="apptref_demo",
            confirmation_text="Confirmo",
            idempotency_key="idem_confirm_demo",
        )

        self.assertEqual(result["data"]["status"], "confirmed")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.calls[0]["body"], transport.calls[1]["body"])
        self.assertEqual(transport.calls[0]["headers"]["X-HTE-Idempotency-Key"], "idem_confirm_demo")
        self.assertEqual(transport.calls[1]["headers"]["X-HTE-Idempotency-Key"], "idem_confirm_demo")

    def test_idempotency_conflict_is_definitive(self) -> None:
        transport = FakeTransport(
            [
                response(
                    409,
                    {
                        "error": {
                            "code": "idempotency_conflict",
                            "message": "same key used with different body",
                            "retryable": False,
                            "correlation_id": "corr_demo",
                        }
                    },
                )
            ]
        )
        client = RenaliaApiClient(
            config(max_attempts=3),
            transport=transport,
            clock=lambda: 1791065400,
            request_id_factory=lambda: "request-1",
        )

        with self.assertRaises(RenaliaClientError) as raised:
            client.confirm_appointment(
                session=session(),
                patient_identity=patient_identity(),
                appointment_ref="apptref_demo",
                confirmation_text="Confirmo",
                idempotency_key="idem_conflict_demo",
            )

        self.assertEqual(raised.exception.code, "idempotency_conflict")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(len(transport.calls), 1)

    def test_not_found_appointment_is_normal_result(self) -> None:
        transport = FakeTransport(
            [
                response(
                    404,
                    {
                        "status": "not_found",
                        "data": {"appointment": None},
                        "review_required": False,
                        "audit_ref": "audit_demo",
                    },
                )
            ]
        )
        client = RenaliaApiClient(config(), transport=transport, clock=lambda: 1791065400)

        result = client.next_appointment(session=session(), patient_identity=patient_identity())

        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["data"]["appointment"])

    def test_not_found_education_material_is_normal_result(self) -> None:
        transport = FakeTransport(
            [
                response(
                    404,
                    {
                        "status": "not_found",
                        "data": {"material": None},
                        "review_required": False,
                        "audit_ref": "audit_demo",
                    },
                )
            ]
        )
        client = RenaliaApiClient(config(), transport=transport, clock=lambda: 1791065400)

        result = client.education_material(
            session=session(),
            patient_identity=patient_identity(),
            topic="no-template",
            language="es-CO",
        )

        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["data"]["material"])

    def test_deterministic_400_error_is_not_retried_and_payload_is_redacted(self) -> None:
        transport = FakeTransport(
            [
                response(
                    400,
                    {
                        "error": {
                            "code": "invalid_request",
                            "message": "unknown field",
                            "retryable": False,
                            "correlation_id": "corr_demo",
                        },
                        "identity_proof": "idp_should_not_be_logged",
                    },
                )
            ]
        )
        client = RenaliaApiClient(
            config(max_attempts=3),
            transport=transport,
            clock=lambda: 1791065400,
            request_id_factory=lambda: "request-1",
        )

        with self.assertRaises(RenaliaClientError) as raised:
            client.report_measurement(
                session=session(),
                patient_identity=patient_identity(),
                measurement={"lab_type": "other", "value": "n/a"},
                idempotency_key="idem_bad_demo",
            )

        self.assertEqual(raised.exception.code, "invalid_request")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(raised.exception.payload["identity_proof"], "<redacted>")

    def test_handoff_status_exposes_no_acknowledgement_tracking(self) -> None:
        transport = FakeTransport(
            [
                response(
                    200,
                    {
                        "status": "ok",
                        "data": {
                            "handoff_ref": "handoff_demo",
                            "state": "created",
                            "acknowledgement_tracked": False,
                        },
                        "review_required": False,
                        "audit_ref": "audit_demo",
                    },
                )
            ]
        )
        client = RenaliaApiClient(config(), transport=transport, clock=lambda: 1791065400)

        result = client.handoff_status(
            session=session(),
            patient_identity=patient_identity(),
            handoff_ref="handoff_demo",
        )

        self.assertFalse(result["data"]["acknowledgement_tracked"])

    def test_redactor_removes_identity_and_verification_material(self) -> None:
        redacted = redact_sensitive(
            {
                "patient_identity": {"identity_proof": "idp_secret", "patient_ref": "patref_demo"},
                "verification_evidence": {"claims": {"document_suffix": "1234", "birth_date": "1970-01-31"}},
            }
        )

        self.assertEqual(redacted["patient_identity"]["identity_proof"], "<redacted>")
        self.assertEqual(redacted["verification_evidence"], "<redacted>")

    def test_config_from_environment_requires_secret_by_default(self) -> None:
        keys = [
            "RENALIA_API_BASE_URL",
            "RENALIA_INSTALLATION_ID",
            "RENALIA_CREDENTIAL_ID",
            "RENALIA_SIGNING_SECRET",
        ]
        old = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["RENALIA_API_BASE_URL"] = "https://renalia.example.test"
            os.environ["RENALIA_INSTALLATION_ID"] = "inst_demo"
            os.environ["RENALIA_CREDENTIAL_ID"] = "cred_demo"
            os.environ.pop("RENALIA_SIGNING_SECRET", None)

            with self.assertRaises(RenaliaClientError) as raised:
                RenaliaClientConfig.from_environment()

            self.assertEqual(raised.exception.code, "missing_secret")
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_config_from_environment_can_load_non_secret_values_for_readiness_checks(self) -> None:
        keys = [
            "RENALIA_API_BASE_URL",
            "RENALIA_INSTALLATION_ID",
            "RENALIA_CREDENTIAL_ID",
            "RENALIA_SIGNING_SECRET",
            "RENALIA_REQUEST_TIMEOUT_SECONDS",
            "RENALIA_MAX_ATTEMPTS",
        ]
        old = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["RENALIA_API_BASE_URL"] = "https://renalia.example.test"
            os.environ["RENALIA_INSTALLATION_ID"] = "inst_demo"
            os.environ["RENALIA_CREDENTIAL_ID"] = "cred_demo"
            os.environ.pop("RENALIA_SIGNING_SECRET", None)
            os.environ["RENALIA_REQUEST_TIMEOUT_SECONDS"] = "7"
            os.environ["RENALIA_MAX_ATTEMPTS"] = "2"

            loaded = RenaliaClientConfig.from_environment(require_secret=False)

            self.assertEqual(loaded.api_base_url, "https://renalia.example.test")
            self.assertEqual(loaded.installation_id, "inst_demo")
            self.assertEqual(loaded.credential_id, "cred_demo")
            self.assertEqual(loaded.signing_secret, "")
            self.assertEqual(loaded.timeout_seconds, 7)
            self.assertEqual(loaded.max_attempts, 2)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
