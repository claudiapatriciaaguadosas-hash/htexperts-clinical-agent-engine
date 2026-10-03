# Contraste de contrato RENALIA implementado

Fecha: 2026-10-03.
Fuente comparada: `RENALIA_API_respuesta_lagunas_HTExperts.md`.

## Resultado

No se detectan contradicciones nuevas frente al contrato implementado anterior. El nuevo documento precisa detalles que el conector debe respetar:

- La base real sigue siendo `/api/public/agent-engine/v1`.
- Todas las rutas son `POST`.
- `session` y `patient_identity` son estrictos; campos extra producen `400`.
- `identity_level`, `verification_method` y `contact_hint` en `patient_identity` son informativos o ignorados por RENALIA.
- Las herramientas de paciente requieren `patient_ref` e `identity_proof`.
- `tools/appointments/next` sin cita futura es un 404 normal con `status:"not_found"`.
- `tools/education/material` sin plantilla aprobada es un 404 normal con `status:"not_found"`.
- `409 state_conflict` puede ser recuperable solo cuando representa peticion idempotente en curso y trae `retryable:true`.
- `409 idempotency_conflict` es definitivo y no debe reintentarse.
- `429 rate_limited` trae `Retry-After`; el conector debe respetarlo.
- En cada reintento se firma otra vez con un nuevo `X-HTE-Request-Id`, manteniendo cuerpo y `X-HTE-Idempotency-Key`.
- `retell_voice` permanece bloqueado por falta de consentimiento de voz/grabacion.
- Handoffs no tienen acuse humano: `acknowledgement_tracked:false` y `acknowledged_at:null`.

## Preparacion demo recibida

El documento `RENALIA_preparacion_prueba_HTExperts.md` confirma:

- dominio publicado recomendado: `https://project--1523cd03-5b53-4774-9f2f-41ed4688f22e.lovable.app`;
- instalacion activa `inst_hte_prueba`;
- credencial activa `cred_hte_prueba_v1`;
- `is_demo=true`;
- `whatsapp_route_mode=external_engine`;
- permisos para las 12 rutas;
- paciente ficticio con telefono `+15550000999`, documento sufijo `0001` y nacimiento `1970-06-15`;
- consentimientos `data_processing`, `whatsapp_messaging` y `telemonitoring`;
- cita futura, pendiente visible, plantilla educativa y outreach demo ficticios;
- Meta no configurado, Retell bloqueado, sin mensajes ni llamadas reales.

No hay contradiccion con el conector local. El secreto sigue fuera del chat y del repositorio.

## Pendientes funcionales

- Falta recibir `RENALIA_SIGNING_SECRET` por canal seguro y guardarlo localmente con DPAPI.
- No hay fecha para consentimiento de voz/grabacion.
- No hay pantalla/campo de acuse humano ni SLA de responsable de handoffs.
- El escalamiento sin identidad verificada sigue pendiente de decision funcional: RENALIA permite ciertos registros administrativos, pero no debe divulgar informacion clinica ni crear pacientes.

## No probado por HTExperts todavia

- Uso desde dominio publicado.
- `429` real.
- `503` real.
- Omision de webhook Meta en modo `external_engine` con evento Meta real.
- Cualquier llamada, mensaje o voz real.
