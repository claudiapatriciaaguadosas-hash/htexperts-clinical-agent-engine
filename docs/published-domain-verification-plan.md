# Plan de comprobacion externa desde dominio publicado

Este plan prepara la prueba del conector HTExperts contra RENALIA publicada. No debe ejecutarse contra pacientes reales ni enviar mensajes reales.

## Prerrequisitos

- `RENALIA_API_BASE_URL` del dominio publicado o entorno de prueba.
- `RENALIA_INSTALLATION_ID` de clinica demo.
- `RENALIA_CREDENTIAL_ID` de credencial demo activa.
- `RENALIA_SIGNING_SECRET` recibido por canal seguro, nunca por chat ni GitHub.
- Datos ficticios para `identity/resolve-contact`.
- Confirmacion de que `whatsapp_route_mode` no activara dos procesadores para el mismo numero.

## Comprobaciones

1. Health de conectividad HTTPS al dominio, sin enviar datos clinicos.
2. Firma invalida contra una ruta inocua: debe responder `401`.
3. `identity/resolve-contact` con datos ficticios correctos: debe devolver `identity_proof`.
4. Reuso del mismo `X-HTE-Request-Id`: debe responder `401 replayed_request`.
5. Herramienta de lectura con `identity_proof`: `tools/appointments/next`.
6. Herramienta de escritura con idempotencia: repetir misma operacion y confirmar `deduped: true`.
7. Misma clave de idempotencia con cuerpo distinto: debe responder `409 idempotency_conflict`.
8. Voz `retell_voice`: debe permanecer bloqueada con `403 consent_revoked`.
9. Handoff status: debe mostrar `acknowledgement_tracked: false`.
10. Limite de peticiones: probar en entorno demo con autorizacion, idealmente bajando temporalmente el limite o usando una ruta de prueba para evitar 120 llamadas reales por minuto.
11. Recuperacion ante fallos temporales: solicitar a Lovable una forma de simular `503`; validar que el conector reintenta con nuevo request id y firma, conservando cuerpo e idempotencia.

## Criterios de no avance

- Falta de URL o credenciales demo.
- Instalacion no marcada como demo.
- Riesgo de enviar WhatsApp/voz real.
- Falta de datos ficticios autorizados.
- Inconsistencia entre esquemas documentados y respuestas reales.

## Evidencia a conservar

- Fecha/hora de prueba.
- Commit del motor.
- Dominio usado.
- Rutas probadas.
- Codigos HTTP y codigos de error.
- Confirmacion de que no se registraron secretos ni pruebas de identidad en logs.
- Resultado de pruebas locales y, si aplica, CI.
