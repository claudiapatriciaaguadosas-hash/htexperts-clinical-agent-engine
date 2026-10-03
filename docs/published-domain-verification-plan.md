# Plan de comprobacion externa desde dominio publicado

Este plan prepara la prueba del conector HTExperts contra RENALIA publicada. No debe ejecutarse contra pacientes reales ni enviar mensajes reales.

## Estado actual

Lovable preparo una instalacion demo activa para prueba externa. Los valores no secretos estan en `.env`, que esta ignorado por Git. El secreto HMAC no esta en el repositorio: debe guardarse localmente con `scripts/set-renalia-secret.ps1`, que usa Windows DPAPI para el usuario actual.

No ejecutar peticiones firmadas hasta que el secreto este configurado por canal seguro fuera del chat y fuera de GitHub.

## Prerrequisitos

- `RENALIA_API_BASE_URL=https://project--1523cd03-5b53-4774-9f2f-41ed4688f22e.lovable.app`.
- `RENALIA_INSTALLATION_ID=inst_hte_prueba`.
- `RENALIA_CREDENTIAL_ID=cred_hte_prueba_v1`.
- `RENALIA_SIGNING_SECRET` recibido por canal seguro, nunca por chat ni GitHub.
- Datos ficticios para `identity/resolve-contact`: telefono `+15550000999`, documento sufijo `0001`, nacimiento `1970-06-15`.
- Confirmacion recibida: `whatsapp_route_mode=external_engine`, Meta no configurado, voz bloqueada y ninguna ruta envia mensajes reales.

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
11. Recuperacion ante fallos temporales: solicitar a Lovable una forma de simular `503`; si no existe interruptor, mantener esta validacion en pruebas locales con transporte simulado.
12. `409 state_conflict` recuperable: validar peticion en curso con la misma clave de idempotencia.
13. `409 idempotency_conflict` definitivo: validar misma clave con cuerpo distinto y sin reintento.
14. `tools/appointments/next` sin cita y `tools/education/material` sin material: deben tratarse como 404 normales con `status:not_found`.
15. Escalamiento sin identidad verificada: no divulgar datos clinicos ni crear paciente; dejar pendiente el criterio funcional final de escalamiento administrativo.

## Criterios de no avance

- Falta de `RENALIA_SIGNING_SECRET` en el almacen local protegido.
- Instalacion no marcada como demo.
- Riesgo de enviar WhatsApp/voz real.
- Falta de datos ficticios autorizados.
- Inconsistencia entre esquemas documentados y respuestas reales.

## Preparacion local

Configurar valores no secretos:

```powershell
scripts\check-renalia-demo-config.ps1
```

Cuando el secreto llegue por canal seguro, guardarlo sin imprimirlo:

```powershell
scripts\set-renalia-secret.ps1
```

Para una sesion de prueba posterior, cargar configuracion y secreto en el proceso:

```powershell
. .\scripts\load-renalia-demo-env.ps1
```

Estos scripts no ejecutan peticiones firmadas.

## Evidencia a conservar

- Fecha/hora de prueba.
- Commit del motor.
- Dominio usado.
- Rutas probadas.
- Codigos HTTP y codigos de error.
- Confirmacion de que no se registraron secretos ni pruebas de identidad en logs.
- Resultado de pruebas locales y, si aplica, CI.
