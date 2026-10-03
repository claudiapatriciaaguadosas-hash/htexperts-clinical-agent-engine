from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol


RENALIA_PUBLIC_AGENT_BASE_PATH = "/api/public/agent-engine/v1"

PATIENT_TOOL_PREFIXES = (
    "tools/appointments/",
    "tools/pending-tasks/",
    "tools/measurements/",
    "tools/handoffs",
)

RETRYABLE_HTTP_STATUSES = {429, 503}

REDACTED_FIELDS = {
    "identity_proof",
    "verification_evidence",
    "document_suffix",
    "birth_date",
    "Authorization",
    "RENALIA_SIGNING_SECRET",
}


class RenaliaClientError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        retryable: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.retryable = retryable
        self.payload = payload or {}


@dataclass(frozen=True, slots=True)
class RenaliaClientConfig:
    api_base_url: str
    installation_id: str
    credential_id: str
    signing_secret: str
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    allowed_channel_modes: frozenset[str] = frozenset({"whatsapp", "admin_test"})


@dataclass(frozen=True, slots=True)
class RenaliaHttpResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str] | None = None


class RenaliaTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> RenaliaHttpResponse:
        ...


def default_urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
) -> RenaliaHttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return RenaliaHttpResponse(
                response.status,
                response.read(),
                dict(response.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        return RenaliaHttpResponse(exc.code, exc.read(), dict(exc.headers.items()))


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def base64url_hmac_sha256(secret: str, signed_input: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), signed_input.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_signed_input(method: str, path_with_query: str, timestamp: int, request_id: str, raw_body: bytes) -> str:
    body_hash = hashlib.sha256(raw_body).hexdigest()
    return "\n".join((method, path_with_query, str(timestamp), request_id, body_hash))


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key) in REDACTED_FIELDS:
                redacted[str(key)] = "<redacted>"
            else:
                redacted[str(key)] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


class RenaliaApiClient:
    def __init__(
        self,
        config: RenaliaClientConfig,
        *,
        transport: RenaliaTransport = default_urllib_transport,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if config.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.config = config
        self.transport = transport
        self.clock = clock
        self.sleeper = sleeper
        self.request_id_factory = request_id_factory or (lambda: str(uuid.uuid4()))

    def post(
        self,
        route: str,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        clean_route = route.strip("/")
        self._assert_channel_allowed(payload)
        self._assert_identity_proof_when_required(clean_route, payload)

        path = f"{RENALIA_PUBLIC_AGENT_BASE_PATH}/{clean_route}"
        url = f"{self.config.api_base_url.rstrip('/')}{path}"
        raw_body = canonical_json_bytes(payload)
        attempts = self.config.max_attempts
        last_error: RenaliaClientError | None = None

        for attempt in range(1, attempts + 1):
            request_id = self.request_id_factory()
            timestamp = int(self.clock())
            headers = self._headers(path, timestamp, request_id, raw_body, idempotency_key)
            response = self.transport("POST", url, headers, raw_body, self.config.timeout_seconds)
            parsed = self._parse_json(response)

            if 200 <= response.status_code < 300:
                return parsed
            if response.status_code == 404 and parsed.get("status") == "not_found":
                return parsed

            error = self._client_error_from_response(response, parsed)
            if not self._should_retry(error, attempt, attempts):
                raise error
            last_error = error
            delay = self._retry_delay_seconds(response)
            if delay > 0:
                self.sleeper(delay)

        if last_error is not None:
            raise last_error
        raise RenaliaClientError("request_failed", "RENALIA request failed without a response", retryable=True)

    def resolve_contact(
        self,
        *,
        session: Mapping[str, Any],
        contact: Mapping[str, Any],
        verification_evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.post(
            "identity/resolve-contact",
            {
                "session": dict(session),
                "contact": dict(contact),
                "verification_evidence": dict(verification_evidence),
            },
        )

    def next_appointment(self, *, session: Mapping[str, Any], patient_identity: Mapping[str, Any]) -> dict[str, Any]:
        return self.post(
            "tools/appointments/next",
            {"session": dict(session), "patient_identity": dict(patient_identity)},
        )

    def confirm_appointment(
        self,
        *,
        session: Mapping[str, Any],
        patient_identity: Mapping[str, Any],
        appointment_ref: str,
        confirmation_text: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self.post(
            "tools/appointments/confirm",
            {
                "session": dict(session),
                "patient_identity": dict(patient_identity),
                "appointment_ref": appointment_ref,
                "confirmation_text": confirmation_text,
            },
            idempotency_key=idempotency_key,
        )

    def report_measurement(
        self,
        *,
        session: Mapping[str, Any],
        patient_identity: Mapping[str, Any],
        measurement: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self.post(
            "tools/measurements/reported",
            {
                "session": dict(session),
                "patient_identity": dict(patient_identity),
                "measurement": dict(measurement),
            },
            idempotency_key=idempotency_key,
        )

    def education_material(
        self,
        *,
        session: Mapping[str, Any],
        patient_identity: Mapping[str, Any],
        topic: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session": dict(session),
            "patient_identity": dict(patient_identity),
        }
        if topic is not None:
            payload["topic"] = topic
        if language is not None:
            payload["language"] = language
        return self.post("tools/education/material", payload)

    def handoff_status(
        self,
        *,
        session: Mapping[str, Any],
        patient_identity: Mapping[str, Any],
        handoff_ref: str,
    ) -> dict[str, Any]:
        return self.post(
            "tools/handoffs/status",
            {
                "session": dict(session),
                "patient_identity": dict(patient_identity),
                "handoff_ref": handoff_ref,
            },
        )

    def _headers(
        self,
        path: str,
        timestamp: int,
        request_id: str,
        raw_body: bytes,
        idempotency_key: str | None,
    ) -> dict[str, str]:
        signed_input = build_signed_input("POST", path, timestamp, request_id, raw_body)
        signature = base64url_hmac_sha256(self.config.signing_secret, signed_input)
        headers = {
            "Authorization": f"HTEA1 Credential={self.config.credential_id}, Signature={signature}, Timestamp={timestamp}",
            "X-HTE-Installation-Id": self.config.installation_id,
            "X-HTE-Request-Id": request_id,
            "Content-Type": "application/json",
        }
        if idempotency_key is not None:
            headers["X-HTE-Idempotency-Key"] = idempotency_key
        return headers

    def _assert_channel_allowed(self, payload: Mapping[str, Any]) -> None:
        session = payload.get("session")
        if not isinstance(session, Mapping):
            return
        channel = session.get("channel")
        if channel == "retell_voice":
            raise RenaliaClientError(
                "consent_revoked",
                "RENALIA voice access is blocked until voice and recording consent are defined.",
                http_status=403,
                retryable=False,
            )
        if isinstance(channel, str) and channel not in self.config.allowed_channel_modes:
            raise RenaliaClientError(
                "channel_not_allowed",
                f"Channel is not enabled for this RENALIA client: {channel}",
                http_status=403,
                retryable=False,
            )

    def _assert_identity_proof_when_required(self, route: str, payload: Mapping[str, Any]) -> None:
        if not route.startswith(PATIENT_TOOL_PREFIXES):
            return
        identity = payload.get("patient_identity")
        if not isinstance(identity, Mapping) or not identity.get("patient_ref") or not identity.get("identity_proof"):
            raise RenaliaClientError(
                "identity_not_verified",
                "RENALIA patient tools require patient_ref and identity_proof.",
                http_status=403,
                retryable=False,
            )

    def _parse_json(self, response: RenaliaHttpResponse) -> dict[str, Any]:
        if not response.body:
            return {}
        try:
            parsed = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RenaliaClientError(
                "invalid_response",
                f"RENALIA returned non-JSON response with status {response.status_code}",
                http_status=response.status_code,
                retryable=response.status_code in RETRYABLE_HTTP_STATUSES,
            ) from exc
        if not isinstance(parsed, dict):
            raise RenaliaClientError(
                "invalid_response",
                "RENALIA response must be a JSON object",
                http_status=response.status_code,
                retryable=False,
            )
        return parsed

    def _client_error_from_response(self, response: RenaliaHttpResponse, parsed: dict[str, Any]) -> RenaliaClientError:
        error_payload = parsed.get("error") if isinstance(parsed.get("error"), Mapping) else {}
        code = str(error_payload.get("code") or f"http_{response.status_code}")
        message = str(error_payload.get("message") or f"RENALIA request failed with status {response.status_code}")
        retryable = bool(error_payload.get("retryable")) or response.status_code in RETRYABLE_HTTP_STATUSES
        return RenaliaClientError(
            code,
            message,
            http_status=response.status_code,
            retryable=retryable,
            payload=redact_sensitive(parsed),
        )

    def _should_retry(self, error: RenaliaClientError, attempt: int, max_attempts: int) -> bool:
        if attempt >= max_attempts:
            return False
        if not error.retryable:
            return False
        if error.http_status in RETRYABLE_HTTP_STATUSES:
            return True
        return error.http_status == 409 and error.code == "state_conflict"

    def _retry_delay_seconds(self, response: RenaliaHttpResponse) -> float:
        if response.status_code != 429 or not response.headers:
            return 0.0
        retry_after = None
        for key, value in response.headers.items():
            if key.lower() == "retry-after":
                retry_after = value
                break
        if retry_after is None:
            return 0.0
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            return 0.0
