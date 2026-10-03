# HTExperts Clinical Agent Engine

Entrega 1 de laboratorio para el motor clínico común de HTExperts.

Este repositorio implementa un core multi-producto/multi-institución con datos sintéticos. No conecta RENALIA real, Retell real, Meta real ni bases clínicas de producción. La frontera de autorización es siempre `(product_id, tenant_id)` y el contexto confiable se construye del lado servidor, no desde texto del usuario ni desde campos propuestos por el modelo.

## Incluye

- Contratos tipados del motor: `TrustedContext`, `ActionProposal`, `ToolResult`, `Handoff`.
- Repositorio durable de laboratorio sobre SQLite, diseñado para migrarse a PostgreSQL/Supabase.
- Cola durable con bloqueo transaccional, reintentos, estado e idempotencia.
- Auditoría mínima por correlación, producto, clínica, herramienta y decisión.
- Adaptador RENALIA simulado con citas, pendientes, mediciones reportadas y derivación.
- Adaptadores sandbox para Meta WhatsApp y Retell. No envían mensajes ni llamadas reales.
- Pruebas adversariales de aislamiento, identidad, inyección, idempotencia y seguridad clínica.
- Esqueleto FastAPI versionado bajo `/v1`.

## Ejecutar pruebas

```powershell
python -m unittest discover -s tests
```

Si instalas dependencias del proyecto:

```powershell
python -m pip install -e ".[dev]"
pytest
```

## Variables de entorno

Copia `.env.example` y configura solo valores de sandbox. No pegues secretos reales en chats, prompts ni archivos versionados.

## Pendiente para Entrega 2

- Crear/conectar el repositorio privado `htexperts-clinical-agent-engine`.
- Inspeccionar backend real de RENALIA antes de escribir contratos de integración.
- Validar documentación vigente de Retell Custom LLM, Meta WhatsApp Cloud API, Railway y proveedor de modelo.
- Sustituir SQLite por PostgreSQL/Supabase con roles de privilegio mínimo y pruebas usando credenciales reales del servicio.
- Configurar secretos exclusivamente en el entorno de despliegue.

