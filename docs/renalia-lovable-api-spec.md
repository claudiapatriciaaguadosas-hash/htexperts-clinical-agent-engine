# RENALIA CKM Integration API for HTExperts Agent Engine

Status: proposed contract for Lovable implementation.
Date: 2026-10-03.
Owner: HTExperts / Dra. Claudia Aguado.
Target product: RENALIA CKM.
API base path: `/api/agent-engine/v1`.

Implementation note: Lovable later reported an implemented contract under
`/api/public/agent-engine/v1` with `identity_proof`, voice blocked for missing
voice/recording consent, and handoff status without acknowledgement tracking.
Keep this document as the original proposal only; use
`lovable-contract-clarification-request.md` plus the implemented contract report
to reconcile final schemas before external testing.

This specification is the single API contract to hand to Lovable for RENALIA CKM. It defines the HTTPS API that RENALIA should expose to the external HTExperts Clinical Agent Engine. These routes are proposals until Lovable implements and verifies them against the real RENALIA codebase. Do not treat them as existing endpoints.

The external engine must not connect directly to RENALIA's database, must not duplicate the clinical record, and must not use a Supabase service-role key as an isolation boundary. RENALIA remains the source of truth for patients, appointments, validated clinical data, CKM/PREVENT/KFRE, consent, human review, and audit.

## 1. Design Rules

- The engine credential determines `product_id`, RENALIA installation, and clinic context on the RENALIA server. Request bodies never choose tenant or clinic authority.
- Patient identity and patient permission are separate from engine authentication. A valid engine credential alone never authorizes disclosure of patient-specific data.
- All resource references returned to the engine are opaque and scoped to the installation and clinic that produced them.
- The API returns minimum data needed for the workflow, not complete records.
- Reported values and task completion reports are pending human review. The API must not write validated `lab_results`, change treatment, confirm CKM stage, or mark clinical work as verified from an engine request.
- Unknown or ambiguous contacts must not reveal whether a patient exists.
- WhatsApp and voice can share this API, but RENALIA must allow only one active event-processing path per installation to avoid two engines processing the same event.
- Every write operation is idempotent and auditable.

## 2. Transport, Authentication, And Replay Protection

All routes require HTTPS.

Required headers:

```http
Authorization: HTEA1 Credential=<credential_id>, Signature=<base64url_hmac_sha256>, Timestamp=<unix_seconds>
X-HTE-Installation-Id: <opaque_installation_id>
X-HTE-Request-Id: <uuid>
X-HTE-Idempotency-Key: <opaque_key_for_write_requests>
Content-Type: application/json
```

`X-HTE-Idempotency-Key` is required for `POST` requests that create or mutate state. It is optional for pure reads.

Signing input:

```text
<method>\n
<path_with_query>\n
<timestamp>\n
<x-hte-request-id>\n
<sha256_hex_of_raw_body>
```

RENALIA stores a secret per installation in its server-side secret store. It resolves the installation from `X-HTE-Installation-Id`, looks up the secret reference, verifies the HMAC signature, validates a timestamp skew of at most 300 seconds, and rejects replayed `(installation_id, request_id)` values within the replay window.

Credential lifecycle:

- Credentials are per product installation, not global cron tokens.
- Credentials can be disabled without affecting other clinics.
- Rotation supports two active key versions during a short overlap window.
- Revoked credentials return `401 credential_revoked`.

Recommended rate limits:

- Per installation and per route.
- Separate limits for read tools, write tools, and channel event ingestion.
- Return `429 rate_limited` with `Retry-After` where appropriate.

## 3. Context Model

RENALIA constructs trusted context server-side:

```json
{
  "product_id": "renalia",
  "clinic_id": "clinic_opaque_ref",
  "installation_id": "inst_renalia_clinic_a",
  "credential_id": "cred_2026_10_a",
  "policy_version": "renalia-agent-v1"
}
```

The request body can include channel, session, event, patient identity proof, and resource references. Those fields are inputs for validation only; they never override the credential-resolved clinic.

## 4. Shared Schemas

### ChannelSession

```json
{
  "channel": "whatsapp",
  "engine_session_id": "ses_01K6...",
  "engine_correlation_id": "corr_01K6...",
  "channel_connection_ref": "whatsapp_meta_clinic_a",
  "provider_conversation_ref": "wamid-demo-thread",
  "occurred_at": "2026-10-03T15:00:00-05:00"
}
```

Allowed `channel`: `whatsapp`, `retell_voice`, `admin_test`.

### PatientIdentity

```json
{
  "identity_level": "verified",
  "patient_ref": "patref_7V8F",
  "verification_method": "portal_session",
  "contact_hint": {
    "phone_e164": "+573001112233",
    "provider_contact_id": "wa_573001112233"
  }
}
```

Allowed `identity_level`:

- `unknown`: contact not linked or not authenticated.
- `contact_hint`: possible patient match, not enough for disclosure.
- `verified`: RENALIA can disclose minimum authorized information for this patient and clinic.

RENALIA may return a `patient_ref` only after its own rules determine that the identity is verified or safely linkable for the requested action. The engine must not invent `patient_ref`.

### ToolEnvelope

Every tool request body includes:

```json
{
  "session": {
    "channel": "whatsapp",
    "engine_session_id": "ses_demo",
    "engine_correlation_id": "corr_demo",
    "channel_connection_ref": "whatsapp_meta_clinic_a",
    "occurred_at": "2026-10-03T15:00:00-05:00"
  },
  "patient_identity": {
    "identity_level": "verified",
    "patient_ref": "patref_demo"
  }
}
```

### ToolResult

All success responses use:

```json
{
  "status": "ok",
  "data": {},
  "review_required": false,
  "audit_ref": "audit_01K6...",
  "idempotency": {
    "key": "idem_demo",
    "deduped": false
  }
}
```

Allowed `status`: `ok`, `accepted`, `review_required`, `not_found`, `denied`, `error`.

### ErrorResponse

```json
{
  "error": {
    "code": "identity_not_verified",
    "message": "Verified identity is required for this tool.",
    "retryable": false,
    "correlation_id": "corr_demo"
  }
}
```

Common HTTP mappings:

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `invalid_request` | Schema, enum, or semantic validation failed |
| 401 | `invalid_signature` | Missing or invalid signature |
| 401 | `credential_revoked` | Installation credential disabled |
| 403 | `tool_not_allowed` | Credential lacks this tool permission |
| 403 | `identity_not_verified` | Patient disclosure/action requires verified identity |
| 403 | `consent_revoked` | Consent or contact permission is missing/revoked |
| 404 | `not_found` | Resource absent or not visible in authorized scope |
| 409 | `idempotency_conflict` | Same idempotency key used with a different body |
| 409 | `state_conflict` | Resource state cannot accept this transition |
| 422 | `clinical_action_not_allowed` | Request attempts prohibited clinical action |
| 429 | `rate_limited` | Installation or route limit exceeded |
| 503 | `temporarily_unavailable` | RENALIA cannot safely complete request now |

## 5. Tool Endpoints

### 5.1 Resolve Contact Identity

`POST /api/agent-engine/v1/identity/resolve-contact`

Purpose: resolve channel contact into a non-disclosing identity result. This route may say whether the engine can continue verification or must hand off, but must not reveal clinical data to unknown contacts.

Required permission: `identity:resolve`.

Request:

```json
{
  "session": {
    "channel": "whatsapp",
    "engine_session_id": "ses_demo",
    "engine_correlation_id": "corr_demo",
    "channel_connection_ref": "whatsapp_meta_clinic_a",
    "provider_conversation_ref": "wamid.demo",
    "occurred_at": "2026-10-03T15:00:00-05:00"
  },
  "contact": {
    "phone_e164": "+573001112233",
    "provider_contact_id": "wa_573001112233"
  },
  "verification_evidence": {
    "method": "outbound_call_confirmed_recipient",
    "claims": {
      "document_suffix": "1234",
      "birth_date": "1970-01-31"
    }
  }
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "identity_level": "verified",
    "patient_ref": "patref_demo",
    "allowed_channels": ["whatsapp"],
    "contact_allowed": true
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

Notes:

- If ambiguous, return `identity_level: contact_hint` and no patient details.
- If unknown, return `identity_level: unknown`; do not create a patient.
- Voice identity and recording consent require separate policy confirmation; do not infer them from WhatsApp consent.

### 5.2 Get Next Appointment

`POST /api/agent-engine/v1/tools/appointments/next`

Required permission: `appointments:read`.
Identity: verified.
Clinical effect: none.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"}
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "appointment": {
      "appointment_ref": "apptref_demo",
      "scheduled_at": "2026-10-10T09:00:00-05:00",
      "duration_minutes": 30,
      "status": "scheduled",
      "specialty": "Nefrologia",
      "clinician_display": "Equipo RENALIA"
    }
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

Return only the minimum details safe for the verified patient.

### 5.3 Confirm Appointment Attendance

`POST /api/agent-engine/v1/tools/appointments/confirm`

Required permission: `appointments:write`.
Identity: verified.
Idempotency: required.
Clinical effect: administrative appointment confirmation only.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "appointment_ref": "apptref_demo",
  "confirmation_text": "Si, confirmo mi asistencia"
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "appointment_ref": "apptref_demo",
    "status": "confirmed"
  },
  "review_required": false,
  "audit_ref": "audit_demo",
  "idempotency": {"key": "idem_confirm_appt_demo", "deduped": false}
}
```

The same idempotency key and same body must return the same logical result. A different body with the same key returns `409 idempotency_conflict`.

### 5.4 Request Reschedule

`POST /api/agent-engine/v1/tools/appointments/reschedule-requests`

Required permission: `appointments:request_reschedule`.
Identity: verified.
Idempotency: required.
Human review: required.
Clinical effect: creates request only; no slot is promised.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "appointment_ref": "apptref_demo",
  "reason": "No puedo asistir ese dia",
  "preferred_windows": [
    {"starts_after": "2026-10-12T08:00:00-05:00", "ends_before": "2026-10-12T12:00:00-05:00"}
  ]
}
```

Response:

```json
{
  "status": "review_required",
  "data": {
    "request_ref": "reschedreq_demo",
    "handoff_ref": "handoff_demo",
    "state": "created"
  },
  "review_required": true,
  "audit_ref": "audit_demo"
}
```

### 5.5 List Visible Pending Tasks

`POST /api/agent-engine/v1/tools/pending-tasks/list`

Required permission: `pending:read`.
Identity: verified.
Clinical effect: none.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "filters": {
    "status": ["open", "patient_reported", "blocked"],
    "patient_visible_only": true
  }
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "tasks": [
      {
        "task_ref": "taskref_demo",
        "task_type": "lab",
        "title": "Creatinina de control",
        "patient_instructions": "Traer resultado al proximo control",
        "priority": "normal",
        "status": "open"
      }
    ]
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

Do not return internal notes.

### 5.6 Report Task Completion Or Barrier

`POST /api/agent-engine/v1/tools/pending-tasks/report`

Required permission: `pending:report`.
Identity: verified.
Idempotency: required.
Human review: required.
Clinical effect: patient report only; does not verify the task.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "task_ref": "taskref_demo",
  "report_type": "barrier",
  "patient_text": "No tengo transporte",
  "barrier": {
    "category": "transport",
    "details": "No tengo transporte"
  }
}
```

Allowed `report_type`: `completed`, `barrier`, `question`.

Response:

```json
{
  "status": "review_required",
  "data": {
    "task_ref": "taskref_demo",
    "status": "blocked",
    "handoff_ref": "handoff_demo"
  },
  "review_required": true,
  "audit_ref": "audit_demo"
}
```

### 5.7 Record Patient-Reported Measurement

`POST /api/agent-engine/v1/tools/measurements/reported`

Required permission: `measurements:report`.
Identity: verified.
Idempotency: required.
Human review: required.
Clinical effect: creates pending patient-reported value only.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "measurement": {
    "lab_type": "systolic_bp",
    "value": "140",
    "unit": "mmHg",
    "observed_at": "2026-10-03T08:30:00-05:00",
    "raw_text": "Mi presion fue 140/90"
  }
}
```

Allowed `lab_type` initially: `egfr`, `uacr`, `hba1c`, `systolic_bp`, `weight`, `other`.

Response:

```json
{
  "status": "review_required",
  "data": {
    "reported_value_ref": "rvref_demo",
    "review_status": "pending_review",
    "plausibility": "unreviewed"
  },
  "review_required": true,
  "audit_ref": "audit_demo"
}
```

RENALIA may perform plausibility classification, but the value remains unvalidated until a human review workflow accepts or rejects it.

### 5.8 Get Approved Education Material

`POST /api/agent-engine/v1/tools/education/material`

Required permission: `education:read`.
Identity: verified for patient-specific recommendations; `contact_hint` may receive generic non-clinical material if RENALIA policy allows it.
Clinical effect: none.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "topic": "kidney_care",
  "language": "es-CO"
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "material_ref": "matref_ckm_001",
    "title": "Cuidado renal",
    "delivery": {
      "kind": "url",
      "url": "https://renalia.example.invalid/materiales/cuidado-renal"
    },
    "version": "2026-10-approved"
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

The engine must not generate prescriptions or unsourced clinical instructions.

### 5.9 Create Human Handoff

`POST /api/agent-engine/v1/tools/handoffs`

Required permission: `handoff:create`.
Identity: verified when patient-specific; unknown contacts may create minimum administrative handoffs if RENALIA policy allows it.
Idempotency: required.
Human review: required.

Request:

```json
{
  "session": {"channel": "retell_voice", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "reason": "Possible urgent symptom",
  "priority": "urgent",
  "summary": "Paciente refiere dolor de pecho y dificultad respiratoria.",
  "requested_ack_by": "2026-10-03T16:00:00-05:00"
}
```

Allowed `priority`: `routine`, `normal`, `high`, `urgent`.

Response:

```json
{
  "status": "review_required",
  "data": {
    "handoff_ref": "handoff_demo",
    "state": "created",
    "recipient": "renalia_clinic_team",
    "acknowledgement": null
  },
  "review_required": true,
  "audit_ref": "audit_demo"
}
```

Creating a handoff is not proof that a human has received it.

### 5.10 Get Handoff Status

`POST /api/agent-engine/v1/tools/handoffs/status`

Required permission: `handoff:read`.
Identity: verified if patient-specific.
Clinical effect: none.

Request:

```json
{
  "session": {"channel": "whatsapp", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "patient_identity": {"identity_level": "verified", "patient_ref": "patref_demo"},
  "handoff_ref": "handoff_demo"
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "handoff_ref": "handoff_demo",
    "state": "acknowledged",
    "acknowledged_at": "2026-10-03T15:10:00-05:00",
    "closed_at": null
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

### 5.11 Record Conversation Event

`POST /api/agent-engine/v1/events/conversation`

Required permission: `conversation:event_write`.
Identity: may be `unknown`, `contact_hint`, or `verified`.
Idempotency: required.
Clinical effect: audit/conversation record only.

Request:

```json
{
  "session": {
    "channel": "whatsapp",
    "engine_session_id": "ses_demo",
    "engine_correlation_id": "corr_demo",
    "channel_connection_ref": "whatsapp_meta_clinic_a",
    "provider_conversation_ref": "wamid.demo",
    "occurred_at": "2026-10-03T15:00:00-05:00"
  },
  "patient_identity": {"identity_level": "contact_hint"},
  "event": {
    "direction": "inbound",
    "provider_message_id": "wamid.demo.1",
    "message_kind": "text",
    "body_redacted": "Paciente pregunta por cita",
    "requires_review": false,
    "engine_detail": {
      "intent": "next_appointment",
      "tool_name": "renalia.next_appointment"
    }
  }
}
```

Allowed `direction`: `inbound`, `outbound`, `system`.

Response:

```json
{
  "status": "ok",
  "data": {
    "conversation_event_ref": "convevt_demo",
    "deduped": false
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

Do not require full transcripts unless a retention policy explicitly authorizes them.

### 5.12 Record Outreach Provider Result

`POST /api/agent-engine/v1/events/outreach-result`

Required permission: `outreach:event_write`.
Idempotency: required.
Clinical effect: provider event record only. It must not validate clinical data.

Request:

```json
{
  "session": {"channel": "retell_voice", "engine_session_id": "ses_demo", "engine_correlation_id": "corr_demo"},
  "outreach_ref": "outreach_demo",
  "provider": "retell",
  "provider_event_id": "evt_demo_123",
  "event_type": "answered",
  "occurred_at": "2026-10-03T15:00:00-05:00",
  "structured_outcome": {
    "confirmed_recipient": true,
    "requested_callback": false
  }
}
```

Response:

```json
{
  "status": "ok",
  "data": {
    "outreach_ref": "outreach_demo",
    "state": "answered",
    "deduped": false
  },
  "review_required": false,
  "audit_ref": "audit_demo"
}
```

## 6. Existing RENALIA Endpoints And Transition

The reported existing endpoints remain RENALIA-owned and are not replaced by this contract until Lovable explicitly implements the bridge or migration:

- `GET/POST /api/public/webhooks/whatsapp-cloud`
- `POST /api/public/webhooks/twilio`
- `GET /api/public/hooks/outreach-dispatch`
- `POST /api/public/webhooks/outreach-whatsapp`
- `POST /api/public/webhooks/outreach-voice`
- `POST /api/public/hooks/agent-tasks-worker`

For WhatsApp, choose exactly one active route per installation:

1. Meta sends events to RENALIA, and RENALIA forwards authorized tool calls/events to the external engine, or
2. Meta sends events to the external engine, and the engine uses this RENALIA API for tools.

Do not run both event-processing brains for the same phone number. Add an activation flag and rollback path per installation.

## 7. Idempotency Requirements

For every idempotent route, RENALIA stores:

- installation id;
- route;
- idempotency key;
- raw body hash;
- response status and response body or resource reference;
- first seen timestamp;
- final state.

Rules:

- Same key + same body returns the same logical result.
- Same key + different body returns `409 idempotency_conflict`.
- Concurrent requests reserve the key transactionally so only one action executes.
- Provider timeouts with uncertain outcome must be reconciled before retrying side effects.

## 8. Audit Requirements

Every request records:

- installation id and resolved clinic id;
- credential id/key version, never secret value;
- route/tool;
- authenticated engine actor;
- patient ref when available;
- resource refs touched;
- authorization decision;
- result status;
- policy version;
- correlation id and request id.

Do not store secrets in audit. Avoid full transcripts unless a retention policy explicitly permits them.

## 9. Tool Permission Matrix

| Route | Permission | Verified identity | Human review | Idempotency |
|---|---|---:|---:|---:|
| `/identity/resolve-contact` | `identity:resolve` | No | Sometimes | Optional |
| `/tools/appointments/next` | `appointments:read` | Yes | No | Optional |
| `/tools/appointments/confirm` | `appointments:write` | Yes | No | Required |
| `/tools/appointments/reschedule-requests` | `appointments:request_reschedule` | Yes | Yes | Required |
| `/tools/pending-tasks/list` | `pending:read` | Yes | No | Optional |
| `/tools/pending-tasks/report` | `pending:report` | Yes | Yes | Required |
| `/tools/measurements/reported` | `measurements:report` | Yes | Yes | Required |
| `/tools/education/material` | `education:read` | Policy-dependent | No | Optional |
| `/tools/handoffs` | `handoff:create` | Policy-dependent | Yes | Required |
| `/tools/handoffs/status` | `handoff:read` | Yes when patient-specific | No | Optional |
| `/events/conversation` | `conversation:event_write` | No | Sometimes | Required |
| `/events/outreach-result` | `outreach:event_write` | No | Sometimes | Required |

## 10. Lovable Implementation Checklist

Lovable should return a final implemented contract with:

- Exact routes, methods, schemas, and examples as implemented.
- Mapping from opaque refs to actual tables without exposing internal ids unnecessarily.
- Confirmed auth mechanism, key storage, rotation, revocation, and replay protection.
- Confirmed consent checks for WhatsApp, telemonitoring, voice, and recording where applicable.
- Confirmed idempotency storage and transaction behavior under concurrency.
- Confirmed audit fields and retention choices.
- Test evidence with two clinics and synthetic patients.
- List of incompatibilities or route changes from this proposal.
- Secret names and where they are configured, without values.

## 11. Test Cases Required From Lovable

- Clinic A cannot access Clinic B appointments, tasks, values, handoffs, or messages.
- RENALIA installation cannot access Safety/ERR data through shared clinic names.
- Unknown contact gets no patient existence disclosure.
- Ambiguous identity blocks patient-specific tools.
- Invalid signature is rejected.
- Revoked credential is rejected.
- Credential for one installation cannot use resources from another installation.
- Consent revoked blocks corresponding contact route.
- Duplicate concurrent appointment confirmation executes once.
- Duplicate concurrent measurement report creates one pending value.
- Reported measurement remains pending until professional review.
- Task report does not mark task `verified`.
- Treatment-change request creates handoff, not a medication change.
- Urgent symptom creates handoff and approved safety response path.
- Handoff failure or missing acknowledgement is explicit and visible.
- WhatsApp transition has only one active event processor per installation.

## 12. Secrets And Configuration Names

Proposed RENALIA-side names:

- `HTE_AGENT_ENGINE_INSTALLATIONS`: server-side installation registry or database table, not a public env var with all data.
- `HTE_AGENT_ENGINE_SECRET_<INSTALLATION_KEY>`: HMAC signing secret reference.
- `HTE_AGENT_ENGINE_ALLOWED_SKEW_SECONDS`: default `300`.
- `HTE_AGENT_ENGINE_REPLAY_WINDOW_SECONDS`: default `600`.
- `HTE_AGENT_ENGINE_ENABLED_<INSTALLATION_KEY>`: activation flag.
- `HTE_AGENT_ENGINE_WHATSAPP_ROUTE_MODE_<INSTALLATION_KEY>`: `renalia_webhook` or `external_engine`.

Proposed external engine-side names:

- `RENALIA_API_BASE_URL`
- `RENALIA_INSTALLATION_ID`
- `RENALIA_CREDENTIAL_ID`
- `RENALIA_SIGNING_SECRET`
- `RENALIA_REQUEST_TIMEOUT_SECONDS`
- `RENALIA_CHANNEL_MODE`

Do not commit secret values.

## 13. Open Questions Before Pilot

- Which exact RENALIA workflow verifies outbound voice recipient identity?
- What consent type represents voice calls and recording retention?
- Will Meta webhooks remain in RENALIA as bridge, or move to the external engine per installation?
- Which team role receives urgent and non-urgent handoffs, and what is the required acknowledgement SLA?
- Which education material catalog is approved for agent delivery?
- What are the exact professional review screens/functions for reported values, task reports, and handoffs?

These questions do not block Lovable from implementing and testing this API with synthetic data, but they block patient pilot activation.
