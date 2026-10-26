"""
services/support_service.py

Support plan CRUD, progress notes, and audit log helpers.
"""
import uuid
import datetime
import json

from database import db

PLAN_STATUSES = [
    "Needs follow-up",
    "Support in progress",
    "Follow-up completed",
]
_UPDATABLE_PLAN_FIELDS = {"status", "follow_up_date"}

PRIORITIES = ["Low", "Medium", "High"]

CONCERN_OPTIONS = [
    "Academic performance",
    "Attendance",
    "Financial difficulty",
    "Personal / family issues",
    "Mental health",
    "Motivation",
    "Other",
]


# ---------------------------------------------------------------------------
# Support Plans
# ---------------------------------------------------------------------------

def create_plan(
    student_id: str,
    concern: str,
    priority: str,
    action: str,
    mentor: str,
    follow_up_date: str | None,
    notes: str,
) -> str:
    """Insert a new support plan and write an audit_log entry. Returns plan id."""
    plan_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    db.execute(
        """
        INSERT INTO support_plans
            (id, student_id, concern, priority, action, mentor,
             created_at, follow_up_date, status, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id, student_id, concern, priority, action,
            mentor or None, now, follow_up_date or None,
            "Needs follow-up", notes or None, now,
        ),
    )
    _audit(
        entity_type="plan",
        entity_id=plan_id,
        field="status",
        old_value=None,
        new_value="Needs follow-up",
    )
    return plan_id


def get_plans_for_student(student_id: str) -> list[dict]:
    return db.fetchall(
        "SELECT * FROM support_plans WHERE student_id=? ORDER BY created_at DESC",
        (student_id,),
    )


def get_all_plans() -> list[dict]:
    return db.fetchall("SELECT * FROM support_plans ORDER BY created_at DESC")


def get_plan(plan_id: str) -> dict | None:
    return db.fetchone("SELECT * FROM support_plans WHERE id=?", (plan_id,))


def delete_plan(plan_id: str) -> bool:
    """Delete a plan and its notes, preserving an audit entry for the deletion."""
    conn = db.get_conn()
    try:
        conn.execute("BEGIN")
        plan = conn.execute(
            "SELECT status FROM support_plans WHERE id=?", (plan_id,)
        ).fetchone()
        if plan is None:
            conn.rollback()
            return False

        conn.execute("DELETE FROM progress_notes WHERE plan_id=?", (plan_id,))
        conn.execute("DELETE FROM support_plans WHERE id=?", (plan_id,))
        conn.execute(
            """
            INSERT INTO audit_log
                (id, entity_type, entity_id, field, old_value, new_value, created_at)
            VALUES (?, 'plan', ?, 'deleted', ?, NULL, ?)
            """,
            (
                str(uuid.uuid4()),
                plan_id,
                plan["status"],
                datetime.datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def update_plan_field(plan_id: str, field: str, new_value) -> None:
    """Update a single field on a plan and write audit log."""
    if field not in _UPDATABLE_PLAN_FIELDS:
        raise ValueError(f"Unsupported support plan field: {field}")
    plan = get_plan(plan_id)
    if plan is None:
        return
    old_value = plan.get(field)
    now = datetime.datetime.utcnow().isoformat()
    db.execute(
        f"UPDATE support_plans SET {field}=?, updated_at=? WHERE id=?",
        (new_value, now, plan_id),
    )
    _audit(
        entity_type="plan",
        entity_id=plan_id,
        field=field,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
    )


# ---------------------------------------------------------------------------
# Progress Notes
# ---------------------------------------------------------------------------

def add_note(plan_id: str, author: str, body: str) -> str:
    note_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO progress_notes (id, plan_id, author, body, created_at) VALUES (?,?,?,?,?)",
        (note_id, plan_id, author or None, body, now),
    )
    return note_id


def get_notes_for_plan(plan_id: str) -> list[dict]:
    return db.fetchall(
        "SELECT * FROM progress_notes WHERE plan_id=? ORDER BY created_at DESC",
        (plan_id,),
    )


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

def _audit(
    entity_type: str,
    entity_id: str,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    audit_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    db.execute(
        """
        INSERT INTO audit_log
            (id, entity_type, entity_id, field, old_value, new_value, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (audit_id, entity_type, entity_id, field, old_value, new_value, now),
    )


def get_audit_log(entity_id: str | None = None) -> list[dict]:
    if entity_id:
        return db.fetchall(
            "SELECT * FROM audit_log WHERE entity_id=? ORDER BY created_at DESC",
            (entity_id,),
        )
    return db.fetchall("SELECT * FROM audit_log ORDER BY created_at DESC")


# ---------------------------------------------------------------------------
# Recent activity (dashboard)
# ---------------------------------------------------------------------------

def get_recent_activity(limit: int = 5) -> list[dict]:
    """Return recent plans and notes combined, sorted newest first."""
    plans = db.fetchall(
        "SELECT id, 'plan' AS type, student_id, status AS detail, created_at FROM support_plans ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    notes = db.fetchall(
        """
        SELECT pn.id, 'note' AS type, sp.student_id,
               pn.body AS detail, pn.created_at
        FROM progress_notes pn
        JOIN support_plans sp ON pn.plan_id = sp.id
        ORDER BY pn.created_at DESC LIMIT ?
        """,
        (limit,),
    )
    combined = plans + notes
    combined.sort(key=lambda x: x["created_at"], reverse=True)
    return combined[:limit]


def count_overdue_plans() -> int:
    today = datetime.date.today().isoformat()
    result = db.fetchone(
        """
        SELECT COUNT(*) AS cnt FROM support_plans
        WHERE follow_up_date < ? AND status != 'Follow-up completed'
        """,
        (today,),
    )
    return result["cnt"] if result else 0
