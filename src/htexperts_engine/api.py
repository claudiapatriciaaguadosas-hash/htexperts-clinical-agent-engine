from __future__ import annotations

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover - lets core tests run without deps.
    FastAPI = None  # type: ignore[assignment]


if FastAPI is not None:
    app = FastAPI(title="HTExperts Clinical Agent Engine", version="0.1.0")

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "lab"}
else:
    app = None

