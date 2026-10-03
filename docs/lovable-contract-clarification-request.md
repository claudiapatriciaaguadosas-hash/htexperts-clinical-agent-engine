# Solicitud unica a Lovable: preparar prueba externa RENALIA

Fecha: 2026-10-03.
Repositorio HTExperts: `htexperts-clinical-agent-engine`.
Estado local: el conector HTExperts ya implementa `/api/public/agent-engine/v1`, firma HMAC, `identity_proof`, reintentos limitados, `Retry-After`, 404 normales y distincion de 409 recuperable vs definitivo con pruebas simuladas. No se han hecho llamadas reales ni envios reales.

El contrato implementado recibido el 2026-10-03 cierra los esquemas de las 12 rutas y el procedimiento tecnico de alta. Para ejecutar la comprobacion desde dominio publicado falta preparar un entorno demo activo y entregar secretos por un canal seguro fuera del chat y fuera del repositorio.

## 1. Preparar instalacion demo activa

Crear o reactivar una instalacion de prueba con estas condiciones:

- `is_demo=true`.
- `active=true`.
- `installation_key` sugerida: `inst_hte_prueba`.
- `whatsapp_route_mode="external_engine"` solo si no dispara envios reales; si hay riesgo, usar el modo mas seguro e informar la limitacion.
- Permisos necesarios para probar las 12 rutas:
  - `identity:resolve`
  - `appointments:read`
  - `appointments:write`
  - `appointments:request_reschedule`
  - `pending:read`
  - `pending:report`
  - `measurements:report`
  - `education:read`
  - `handoff:create`
  - `handoff:read`
  - `conversation:event_write`
  - `outreach:event_write`

Confirmar que la instalacion demo no envia WhatsApp, voz ni outreach reales.

## 2. Crear credencial vigente

Crear una credencial demo:

- `credential_id` sugerido: `cred_hte_prueba_v1`.
- `status="active"`.
- `key_version=1`.
- secreto aleatorio de al menos 32 bytes en la boveda cifrada.
- registrar `vault_secret_name` internamente.

Entregar a HTExperts, sin valores secretos en chat ni GitHub:

- `RENALIA_API_BASE_URL`.
- `RENALIA_INSTALLATION_ID`.
- `RENALIA_CREDENTIAL_ID`.
- mecanismo seguro para recibir `RENALIA_SIGNING_SECRET`, por ejemplo gestor de secretos compartido, cofre seguro o entrega directa fuera del chat.

## 3. Crear datos ficticios autorizados

Crear datos demo para una clinica ficticia:

- paciente activo ficticio;
- telefono E.164 ficticio;
- ultimos 4-6 digitos de documento ficticio;
- fecha de nacimiento ficticia;
- consentimientos concedidos:
  - `data_processing`;
  - `whatsapp_messaging`;
  - `telemonitoring`;
- una cita futura `scheduled`;
- una tarea visible para paciente `patient_visible=true`, `status=open`;
- una plantilla activa de categoria `educacion`;
- si se prueba `events/outreach-result`, un `outreach_id` demo valido.

No entregar `patient_ref` ni `identity_proof` manualmente salvo que sea imprescindible; el flujo normal debe generarlos con `identity/resolve-contact`.

## 4. Preparar casos negativos seguros

Para validar sin pacientes reales, confirmar como probar:

- `tools/appointments/next` sin cita futura: HTTP 404 con `status:"not_found"` y `appointment:null`.
- `tools/education/material` sin plantilla aprobada: HTTP 404 con `status:"not_found"` y `material:null`.
- `409 state_conflict` recuperable por peticion idempotente en curso.
- `409 idempotency_conflict` definitivo por misma clave con cuerpo distinto.
- `429 rate_limited` con `Retry-After`, idealmente bajando temporalmente `HTE_AGENT_ENGINE_RATE_LIMIT_PER_MINUTE` para no hacer 120 llamadas por minuto.
- `503 temporarily_unavailable`; si no hay interruptor real, confirmar que solo se validara con transporte simulado del conector HTExperts.

## 5. Mantener bloqueos clinicos

Confirmar durante la prueba:

- `retell_voice` sigue bloqueado con `403 consent_revoked`.
- No hay consentimiento de voz/grabacion definido todavia.
- `tools/handoffs/status` devuelve `acknowledgement_tracked:false`.
- No existe acuse humano registrado todavia.
- Escalamiento sin identidad verificada sigue pendiente de decision funcional; no activar flujo paciente real para contactos desconocidos.

## 6. Evidencia esperada de Lovable

Al terminar la preparacion, devolver:

- dominio exacto a usar;
- instalacion y credencial creadas, sin secreto;
- confirmacion de que el secreto se entrego por canal seguro;
- datos ficticios necesarios para `resolve-contact`;
- lista de rutas habilitadas;
- confirmacion de que no habra mensajes/llamadas reales;
- confirmacion de donde revisar auditoria;
- cualquier cambio respecto al contrato implementado del 2026-10-03.
