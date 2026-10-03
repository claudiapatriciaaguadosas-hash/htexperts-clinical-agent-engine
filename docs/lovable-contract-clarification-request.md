# Solicitud unica a Lovable: lagunas para cerrar integracion RENALIA

Fecha: 2026-10-03.
Repositorio: `htexperts-clinical-agent-engine`.
Contexto: el motor externo ya tiene un conector local para `/api/public/agent-engine/v1`, firma HMAC y pruebas con transporte simulado. No se han hecho llamadas reales ni envio de mensajes.

Lovable reporto un contrato implementado y probado con datos ficticios, pero el documento no incluye los cuerpos completos de peticion/respuesta de las 12 rutas ni el procedimiento exacto de alta de credenciales. Para completar la integracion sin inventar contratos, necesitamos una respuesta unica con los puntos siguientes.

## 1. OpenAPI o contrato completo por ruta

Entregar para cada ruta implementada:

- metodo y ruta exacta bajo `/api/public/agent-engine/v1`;
- JSON Schema completo de request;
- JSON Schema completo de response exitosa;
- JSON Schema completo de error;
- campos obligatorios, opcionales, enums y restricciones;
- ejemplo ficticio valido;
- ejemplo ficticio de error relevante;
- permisos requeridos;
- si requiere `X-HTE-Idempotency-Key`;
- si valida `identity_proof`;
- si puede devolver `retryable: true`.

Rutas esperadas segun el contrato implementado:

- `identity/resolve-contact`
- `tools/appointments/next`
- `tools/appointments/confirm`
- `tools/appointments/reschedule-requests`
- `tools/pending-tasks/list`
- `tools/pending-tasks/report`
- `tools/measurements/reported`
- `tools/education/material`
- `tools/handoffs`
- `tools/handoffs/status`
- `events/conversation`
- `events/outreach-result`

## 2. Alta de instalaciones y credenciales

Documentar el procedimiento exacto, sin valores secretos:

- quien puede crear `agent_engine_installations`;
- campos requeridos para crear una instalacion demo y una instalacion piloto;
- quien puede crear `agent_engine_credentials`;
- formato de `installation_key`;
- formato de `credential_id`;
- como se genera el secreto;
- como se entrega el secreto a HTExperts por canal seguro;
- donde queda el `vault_secret_name`;
- como revocar una credencial;
- como rotar credenciales y durante cuanto tiempo conviven versiones;
- como activar/desactivar una instalacion;
- como configurar `whatsapp_route_mode`.

## 3. Datos de prueba para dominio publicado

Para ejecutar una prueba externa sin pacientes reales, entregar:

- `RENALIA_API_BASE_URL` del dominio publicado o entorno de prueba;
- `RENALIA_INSTALLATION_ID` de una clinica ficticia;
- `RENALIA_CREDENTIAL_ID` de prueba;
- mecanismo seguro para recibir `RENALIA_SIGNING_SECRET` fuera del chat y fuera de GitHub;
- telefono ficticio, ultimos digitos de documento y fecha de nacimiento ficticia para `identity/resolve-contact`;
- `patient_ref` e `identity_proof` validos o instrucciones para generarlos mediante `resolve-contact`;
- referencias ficticias disponibles: cita, tarea visible, material educativo, outreach;
- modo de WhatsApp configurado para la instalacion de prueba;
- confirmacion de que la instalacion es demo y no envia mensajes reales.

## 4. Respuestas transitorias y recuperacion

Confirmar como forzar o simular:

- `503 temporarily_unavailable` para validar reintento;
- `429 rate_limited` y cabecera `Retry-After`;
- `409 state_conflict` durante idempotencia concurrente;
- `409 idempotency_conflict` con misma clave y cuerpo distinto.

El conector HTExperts reintenta solo errores marcados como recuperables y, en cada reintento, genera un nuevo `X-HTE-Request-Id` y firma nueva, conservando el cuerpo y la clave de idempotencia originales.

## 5. Consentimiento y handoffs

Confirmar:

- que `retell_voice` debe seguir devolviendo `403 consent_revoked` hasta definir consentimiento de voz y grabacion;
- si existe una fecha prevista para modelar consentimiento de voz;
- que `tools/handoffs/status` devuelve `acknowledgement_tracked: false`;
- que no existe acuse de recibo humano todavia;
- cual sera el equipo/responsable que recibira handoffs cuando se implemente acuse.

## 6. Auditoria y redaccion

Confirmar que RENALIA no guarda:

- secretos HMAC;
- `identity_proof` en claro;
- ultimos digitos de documento;
- fecha de nacimiento usada para verificacion;
- transcripciones completas salvo politica explicita.

Confirmar tambien la ubicacion donde Lovable puede revisar auditoria de:

- firma invalida;
- credencial revocada;
- permiso ausente;
- consentimiento revocado;
- idempotencia deduplicada;
- medicion pendiente;
- handoff urgente.

## 7. Evidencia solicitada

Adjuntar o resumir:

- resultado de las 48 pruebas reportadas;
- build/tipos de RENALIA;
- confirmacion de que las credenciales demo reportadas como revocadas ya no funcionan;
- confirmacion de que no quedan super-admins temporales ni datos ficticios no autorizados;
- cualquier incompatibilidad respecto al contrato implementado enviado el 2026-10-03.
