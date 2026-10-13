"""Confirmed parking sessions, with server timestamps and persistent receipts."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator


class ConfirmedPlate(BaseModel):
    plate: str = Field(description="Plate checked against the image by the operator.")
    confirmed: Literal[True] = Field(description="Set true only after checking the plate.")

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value):
        value = re.sub(r"[\s.\-]", "", value.upper())
        if not re.fullmatch(r"[A-Z0-9]{3,15}", value):
            raise ValueError("Use 3–15 letters/digits, optionally separated by spaces, dots or hyphens.")
        return value


class ParkingStore:
    def __init__(self, path: Path, hourly_rate_minor=10000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.hourly_rate_minor = hourly_rate_minor
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, plate TEXT NOT NULL,
                    entry_time TEXT NOT NULL, exit_time TEXT,
                    hourly_rate_minor INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'PKR',
                    duration_seconds INTEGER, billed_hours INTEGER, amount_minor INTEGER
                );
                CREATE UNIQUE INDEX IF NOT EXISTS unique_active_plate
                ON sessions(plate) WHERE exit_time IS NULL;
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def enter(self, plate, now=None):
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        session_id = str(uuid4())
        with self.connection() as db:
            try:
                db.execute(
                    "INSERT INTO sessions(id,plate,entry_time,hourly_rate_minor) VALUES (?,?,?,?)",
                    (session_id, plate, timestamp, self.hourly_rate_minor),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "This plate already has an active parking session.") from exc
            return dict(db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())

    def exit(self, session_id, plate, now=None):
        with self.connection() as db:
            # Serialize exits so a repeated request returns the original stored charge.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Parking session not found.")
            if row["plate"] != plate:
                raise HTTPException(409, "The confirmed plate does not match this session.")
            if row["exit_time"] is not None:
                return dict(row)
            end = now or datetime.now(timezone.utc)
            elapsed = end - datetime.fromisoformat(row["entry_time"])
            microseconds = ((elapsed.days * 86400 + elapsed.seconds) * 1000000 + elapsed.microseconds)
            if microseconds < 0:
                raise HTTPException(409, "Server time is earlier than the entry time.")
            # Demo policy: minimum one hour; every started hour is charged; no grace period.
            hours = max(1, (microseconds + 3600000000 - 1) // 3600000000)
            db.execute(
                "UPDATE sessions SET exit_time=?,duration_seconds=?,billed_hours=?,amount_minor=? WHERE id=?",
                (end.isoformat(), microseconds // 1000000, hours, hours * row["hourly_rate_minor"], session_id),
            )
            return dict(db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone())

    def list_sessions(self, active):
        condition = "IS NULL" if active else "IS NOT NULL"
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                f"SELECT * FROM sessions WHERE exit_time {condition} ORDER BY entry_time DESC LIMIT 500"
            )]

    def summary(self):
        with self.connection() as db:
            row = db.execute("""SELECT
                COUNT(CASE WHEN exit_time IS NULL THEN 1 END) AS active_count,
                COUNT(CASE WHEN exit_time IS NOT NULL THEN 1 END) AS closed_count,
                COALESCE(SUM(amount_minor), 0) AS total_amount_minor FROM sessions""").fetchone()
            return dict(row)

    def receipt(self, session_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Parking session not found.")
            if row["exit_time"] is None:
                raise HTTPException(409, "The session is still active; exit before requesting its receipt.")
            return dict(row)


def present(row):
    result = dict(row)
    result["status"] = "closed" if row["exit_time"] else "active"
    result["hourly_rate"] = f"{row['hourly_rate_minor'] // 100}.{row['hourly_rate_minor'] % 100:02d}"
    amount = row["amount_minor"]
    result["amount"] = None if amount is None else f"{amount // 100}.{amount % 100:02d}"
    result["receipt_url"] = f"/parking/sessions/{row['id']}/receipt" if row["exit_time"] else None
    return result


router = APIRouter(prefix="/parking", tags=["Parking"])


@router.get("/summary")
def summary(request: Request):
    return request.app.state.parking.summary()


@router.get("/pricing")
def pricing(request: Request):
    return {"currency": "PKR", "hourly_rate_minor": request.app.state.parking.hourly_rate_minor,
            "policy": "Demo rate: PKR 100 per started hour, minimum one hour, no grace period. Rate is saved at entry."}


@router.post("/entry", status_code=201)
def entry(body: ConfirmedPlate, request: Request):
    return present(request.app.state.parking.enter(body.plate))


@router.get("/active")
def active(request: Request):
    return [present(row) for row in request.app.state.parking.list_sessions(active=True)]


@router.get("/history")
def history(request: Request):
    return [present(row) for row in request.app.state.parking.list_sessions(active=False)]


@router.post("/sessions/{session_id}/exit")
def exit_session(session_id: str, body: ConfirmedPlate, request: Request):
    return present(request.app.state.parking.exit(session_id, body.plate))


@router.get("/sessions/{session_id}/receipt")
def receipt(session_id: str, request: Request):
    """Return saved receipt data as JSON; PDF export is a later milestone."""
    return present(request.app.state.parking.receipt(session_id))
