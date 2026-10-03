# Solicitud unica pendiente a Lovable: entrega segura del secreto demo

Fecha: 2026-10-03.
Repositorio HTExperts: `htexperts-clinical-agent-engine`.

Lovable ya preparo el entorno demo:

- `RENALIA_API_BASE_URL=https://project--1523cd03-5b53-4774-9f2f-41ed4688f22e.lovable.app`
- `RENALIA_INSTALLATION_ID=inst_hte_prueba`
- `RENALIA_CREDENTIAL_ID=cred_hte_prueba_v1`
- `is_demo=true`
- `whatsapp_route_mode=external_engine`
- permisos para las 12 rutas
- paciente ficticio y datos demo para identidad, cita, pendiente, material educativo y outreach
- Meta no configurado, voz bloqueada y sin envios reales desde RENALIA

## Solicitud concreta

Entregar `RENALIA_SIGNING_SECRET` por un canal seguro fuera del chat y fuera del repositorio. Opciones aceptables:

- gestor de secretos compartido con acceso limitado;
- enlace de un solo uso y caducidad en 1Password/Bitwarden Send;
- cofre seguro del equipo HTExperts;
- entrega directa persona a persona.

No enviar el secreto por chat, correo en claro, issue, PR, commit, archivo adjunto ni captura.

## Configuracion local HTExperts

Cuando el secreto llegue, HTExperts lo guardara localmente con:

```powershell
scripts\set-renalia-secret.ps1
```

El script usa Windows DPAPI para el usuario actual y guarda el secreto fuera del repositorio en:

```text
%LOCALAPPDATA%\HTExperts\renalia-agent-engine\RENALIA_SIGNING_SECRET.dpapi
```

Para cargarlo en una sesion de prueba posterior:

```powershell
. .\scripts\load-renalia-demo-env.ps1
```

Estos scripts no ejecutan peticiones firmadas.

## Confirmaciones a mantener

Antes de iniciar prueba externa, confirmar que:

- la instalacion `inst_hte_prueba` sigue activa;
- la credencial `cred_hte_prueba_v1` sigue activa;
- los datos ficticios siguen disponibles;
- no se activaron credenciales Meta;
- `retell_voice` sigue bloqueado;
- no existe acuse humano de handoffs;
- no se enviaran mensajes ni llamadas reales.
