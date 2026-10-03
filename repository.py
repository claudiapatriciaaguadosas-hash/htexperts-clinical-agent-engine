from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .contracts import ToolResult, ToolStatus, TrustedContext


class EngineRepository:
    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self.database_path = str(database_path)
        self.connection = sqlite3.connect(self.database_path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS tenants (
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY (product_id, tenant_id)
            );

            CREATE TABLE IF NOT EXISTS patients (
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              patient_reference TEXT NOT NULL,
              display_name TEXT NOT NULL,
              PRIMARY KEY (product_id, tenant_id, patient_reference)
            );

            CREATE TABLE IF NOT EXISTS appointments (
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              patient_reference TEXT NOT NULL,
              appointment_id TEXT NOT NULL,
              starts_at TEXT NOT NULL,
              status TEXT NOT NULL,
              PRIMARY KEY (product_id, tenant_id, appointment_id)
            );

            CREATE TABLE IF NOT EXISTS pending_items (
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              patient_reference TEXT NOT NULL,
              pending_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              description TEXT NOT NULL,
              status TEXT NOT NULL,
              PRIMARY KEY (product_id, tenant_id, pending_id)
            );

            CREATE TABLE IF NOT EXISTS reported_measurements (
              id TEXT PRIMARY KEY,
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              patient_reference TEXT NOT NULL,
              kind TEXT NOT NULL,
              value TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS handoffs (
              id TEXT PRIMARY KEY,
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              patient_reference TEXT,
              reason TEXT NOT NULL,
              priority TEXT NOT NULL,
              status TEXT NOT NULL,
              acknowledgement TEXT,
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS idempotency_keys (
              scope TEXT NOT NULL,
              key TEXT NOT NULL,
              result_json TEXT NOT NULL,
              created_at REAL NOT NULL,
              PRIMARY KEY (scope, key)
            );

            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              queue_name TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              locked_until REAL,
              last_error TEXT,
              created_at REAL NOT NULL,
              UNIQUE (queue_name, idempotency_key)
            );

            CREATE TABLE IF NOT EXISTS audit_events (
              audit_id TEXT PRIMARY KEY,
              product_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              correlation_id TEXT NOT NULL,
              actor TEXT,
              tool_name TEXT,
              decision TEXT NOT NULL,
              detail_json TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            """
        )

    def seed_lab_data(self) -> None:
        tenants = [
            ("renalia", "clinic-a", "Clinica A"),
            ("renalia", "clinic-b", "Clinica B"),
            ("safety-err", "clinic-a", "Clinica A Safety"),
        ]
        patients = [
            ("renalia", "clinic-a", "patient-1", "Paciente Uno"),
            ("renalia", "clinic-b", "patient-1", "Paciente Uno B"),
        ]
        appointments = [
            ("renalia", "clinic-a", "patient-1", "appt-a1", "2026-10-10T09:00:00-05:00", "scheduled"),
            ("renalia", "clinic-b", "patient-1", "appt-b1", "2026-10-11T11:00:00-05:00", "scheduled"),
        ]
        pending = [
            ("renalia", "clinic-a", "patient-1", "pending-a1", "lab", "Creatinina de control", "open"),
            ("renalia", "clinic-b", "patient-1", "pending-b1", "visit", "Control nutricion", "open"),
        ]
        self.connection.executemany("INSERT OR IGNORE INTO tenants VALUES (?, ?, ?, 1)", tenants)
        self.connection.executemany("INSERT OR IGNORE INTO patients VALUES (?, ?, ?, ?)", patients)
        self.connection.executemany("INSERT OR IGNORE INTO appointments VALUES (?, ?, ?, ?, ?, ?)", appointments)
        self.connection.executemany("INSERT OR IGNORE INTO pending_items VALUES (?, ?, ?, ?, ?, ?, ?)", pending)

    def audit(
        self,
        ctx: TrustedContext,
        *,
        decision: str,
        tool_name: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        audit_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO audit_events
              (audit_id, product_id, tenant_id, correlation_id, actor, tool_name, decision, detail_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                ctx.product_id,
                ctx.tenant_id,
                ctx.correlation_id,
                ctx.authenticated_principal_id,
                tool_name,
                decision,
                json.dumps(detail or {}, sort_keys=True),
                time.time(),
            ),
        )
        return audit_id

    def idempotent(self, scope: str, key: str, create: Any) -> ToolResult:
        existing = self.connection.execute(
            "SELECT result_json FROM idempotency_keys WHERE scope = ? AND key = ?",
            (scope, key),
        ).fetchone()
        if existing:
            payload = json.loads(existing["result_json"])
            return ToolResult(
                status=ToolStatus(payload["status"]),
                authorized_payload=payload["authorized_payload"],
                review_required=payload["review_required"],
                audit_reference=payload["audit_reference"],
                retryable=payload["retryable"],
                message=payload["message"],
            )
        result: ToolResult = create()
        self.connection.execute(
            "INSERT INTO idempotency_keys VALUES (?, ?, ?, ?)",
            (
                scope,
                key,
                json.dumps(
                    {
                        "status": result.status.value,
                        "authorized_payload": result.authorized_payload,
                        "review_required": result.review_required,
                        "audit_reference": result.audit_reference,
                        "retryable": result.retryable,
                        "message": result.message,
                    },
                    sort_keys=True,
                ),
                time.time(),
            ),
        )
        return result

    def next_appointment(self, ctx: TrustedContext) -> dict[str, Any] | None:
        return self._one(
            """
            SELECT appointment_id, starts_at, status
            FROM appointments
            WHERE product_id = ? AND tenant_id = ? AND patient_reference = ? AND status = 'scheduled'
            ORDER BY starts_at ASC
            LIMIT 1
            """,
            (ctx.product_id, ctx.tenant_id, ctx.patient_reference),
        )

    def confirm_appointment(self, ctx: TrustedContext, appointment_id: str) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE appointments
            SET status = 'confirmed'
            WHERE product_id = ? AND tenant_id = ? AND patient_reference = ? AND appointment_id = ?
            """,
            (ctx.product_id, ctx.tenant_id, ctx.patient_reference, appointment_id),
        )
        return cursor.rowcount == 1

    def list_pending(self, ctx: TrustedContext) -> list[dict[str, Any]]:
        return self._many(
            """
            SELECT pending_id, kind, description, status
            FROM pending_items
            WHERE product_id = ? AND tenant_id = ? AND patient_reference = ? AND status = 'open'
            ORDER BY pending_id
            """,
            (ctx.product_id, ctx.tenant_id, ctx.patient_reference),
        )

    def record_measurement(self, ctx: TrustedContext, kind: str, value: str) -> str:
        measurement_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO reported_measurements
              (id, product_id, tenant_id, patient_reference, kind, value, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending_review', ?)
            """,
            (measurement_id, ctx.product_id, ctx.tenant_id, ctx.patient_reference, kind, value, time.time()),
        )
        return measurement_id

    def create_handoff(self, ctx: TrustedContext, reason: str, priority: str = "normal") -> str:
        handoff_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO handoffs
              (id, product_id, tenant_id, patient_reference, reason, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'created', ?)
            """,
            (handoff_id, ctx.product_id, ctx.tenant_id, ctx.patient_reference, reason, priority, time.time()),
        )
        return handoff_id

    def enqueue(self, ctx: TrustedContext, queue_name: str, idempotency_key: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT OR IGNORE INTO jobs
              (job_id, product_id, tenant_id, queue_name, idempotency_key, payload_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'ready', ?)
            """,
            (job_id, ctx.product_id, ctx.tenant_id, queue_name, idempotency_key, json.dumps(payload), time.time()),
        )
        row = self.connection.execute(
            "SELECT job_id FROM jobs WHERE queue_name = ? AND idempotency_key = ?",
            (queue_name, idempotency_key),
        ).fetchone()
        return row["job_id"]

    def lease_jobs(self, queue_name: str, limit: int = 1, lease_seconds: int = 30) -> list[dict[str, Any]]:
        now = time.time()
        rows = self._many(
            """
            SELECT * FROM jobs
            WHERE queue_name = ?
              AND status IN ('ready', 'retry')
              AND (locked_until IS NULL OR locked_until < ?)
            ORDER BY created_at
            LIMIT ?
            """,
            (queue_name, now, limit),
        )
        for row in rows:
            self.connection.execute(
                "UPDATE jobs SET status = 'locked', locked_until = ?, attempts = attempts + 1 WHERE job_id = ?",
                (now + lease_seconds, row["job_id"]),
            )
        return rows

    def complete_job(self, job_id: str) -> None:
        self.connection.execute("UPDATE jobs SET status = 'done', locked_until = NULL WHERE job_id = ?", (job_id,))

    def _one(self, query: str, params: Iterable[Any]) -> dict[str, Any] | None:
        row = self.connection.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None

    def _many(self, query: str, params: Iterable[Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(query, tuple(params)).fetchall()]

