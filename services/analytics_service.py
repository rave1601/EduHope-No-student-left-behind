"""
services/analytics_service.py

Aggregations for the dashboard charts and KPI cards.
"""
import datetime
from database import db


def get_kpis() -> dict:
    """Return KPI counts for the dashboard."""
    total = db.fetchone("SELECT COUNT(*) AS cnt FROM students")["cnt"]
    dropout = db.fetchone("SELECT COUNT(*) AS cnt FROM students WHERE prediction='Dropout'")["cnt"]
    enrolled = db.fetchone("SELECT COUNT(*) AS cnt FROM students WHERE prediction='Enrolled'")["cnt"]
    graduate = db.fetchone("SELECT COUNT(*) AS cnt FROM students WHERE prediction='Graduate'")["cnt"]
    open_plans = db.fetchone(
        "SELECT COUNT(*) AS cnt FROM support_plans WHERE status != 'Follow-up completed'"
    )["cnt"]
    today = datetime.date.today().isoformat()
    overdue = db.fetchone(
        """
        SELECT COUNT(*) AS cnt FROM support_plans
        WHERE follow_up_date < ? AND status != 'Follow-up completed'
        """,
        (today,),
    )["cnt"]
    return {
        "total_students": total,
        "dropout": dropout,
        "enrolled": enrolled,
        "graduate": graduate,
        "open_plans": open_plans,
        "overdue": overdue,
    }


def get_prediction_distribution() -> list[dict]:
    """[{prediction, count}]"""
    return db.fetchall(
        "SELECT prediction, COUNT(*) AS count FROM students GROUP BY prediction"
    )


def get_pass_rate_distribution() -> list[float]:
    """
    Extract pass_rate_1st values from raw_data JSON for histogram.
    Returns a flat list of floats.
    """
    import json

    rows = db.fetchall("SELECT raw_data FROM students")
    values = []
    for r in rows:
        try:
            d = json.loads(r["raw_data"])
            enrolled = d.get("Curricular units 1st sem (enrolled)", 0)
            approved = d.get("Curricular units 1st sem (approved)", 0)
            if enrolled > 0:
                values.append(approved / enrolled)
            else:
                values.append(0.0)
        except Exception:
            pass
    return values


def get_plan_status_distribution() -> list[dict]:
    """[{status, count}]"""
    return db.fetchall(
        "SELECT status, COUNT(*) AS count FROM support_plans GROUP BY status"
    )
