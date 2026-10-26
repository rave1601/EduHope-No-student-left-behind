"""
services/student_service.py

CSV import, validation, and batch prediction storage.
"""
import io
import json
import uuid
import datetime
import pandas as pd

from database import db
from services import model_service

# Required raw columns that must be present in an uploaded CSV
REQUIRED_COLUMNS = [
    "Marital status",
    "Application mode",
    "Course",
    "Daytime/evening attendance",
    "Previous qualification",
    "Mother's qualification",
    "Father's qualification",
    "Mother's occupation",
    "Father's occupation",
    "Displaced",
    "Educational special needs",
    "Debtor",
    "Tuition fees up to date",
    "Gender",
    "Scholarship holder",
    "Age at enrollment",
    "Curricular units 1st sem (credited)",
    "Curricular units 1st sem (enrolled)",
    "Curricular units 1st sem (evaluations)",
    "Curricular units 1st sem (approved)",
    "Curricular units 1st sem (grade)",
    "Curricular units 1st sem (without evaluations)",
    "Curricular units 2nd sem (credited)",
    "Curricular units 2nd sem (enrolled)",
    "Curricular units 2nd sem (evaluations)",
    "Curricular units 2nd sem (approved)",
    "Curricular units 2nd sem (grade)",
    "Curricular units 2nd sem (without evaluations)",
]


def validate_csv(df: pd.DataFrame) -> list[str]:
    """Return missing-column and invalid-feature errors for an uploaded CSV."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    errors = [f"Missing column: {c}" for c in missing]
    if missing:
        return errors

    numeric = REQUIRED_COLUMNS
    for column in numeric:
        values = pd.to_numeric(df[column], errors="coerce")
        bad = values.isna() | ~values.map(lambda value: pd.notna(value) and abs(value) < float("inf"))
        if bad.any():
            errors.append(f"{column}: contains missing or non-numeric values")

    for semester in ("1st", "2nd"):
        approved_col = f"Curricular units {semester} sem (approved)"
        enrolled_col = f"Curricular units {semester} sem (enrolled)"
        approved = pd.to_numeric(df[approved_col], errors="coerce")
        enrolled = pd.to_numeric(df[enrolled_col], errors="coerce")
        if ((approved > enrolled) | (approved < 0) | (enrolled < 0)).any():
            errors.append(f"{semester} semester: unit counts must be non-negative and approved cannot exceed enrolled")

    ages = pd.to_numeric(df["Age at enrollment"], errors="coerce")
    if (ages < 0).any():
        errors.append("Age at enrollment: values must be non-negative")
    return errors


def import_students(raw_df: pd.DataFrame) -> tuple[int, list[dict]]:
    """
    Run predictions on raw_df and store each row in the students table.

    Returns (rows_inserted, errors_list).
    errors_list items: {"row": int, "error": str}
    """
    errors = []
    inserted = 0
    now = datetime.datetime.utcnow().isoformat()

    # Drop Target column if present (the dataset.csv includes it)
    upload_df = raw_df.copy()
    if "Target" in upload_df.columns:
        upload_df = upload_df.drop(columns=["Target"])

    try:
        preds = model_service.predict_batch(upload_df)
    except Exception as exc:
        # If batch prediction fails entirely, record error for all rows
        for i in range(len(upload_df)):
            errors.append({"row": i + 1, "error": str(exc)})
        return 0, errors

    for i, (_, raw_row) in enumerate(upload_df.iterrows()):
        try:
            pred_row = preds.iloc[i]
            student_id = str(uuid.uuid4())
            reference = f"Student {student_id.upper()}"
            raw_dict = raw_row.to_dict()
            display_name = next(
                (str(raw_dict[key]).strip() for key in ("display_name", "Display Name", "Student Name", "Name")
                 if raw_dict.get(key) is not None and str(raw_dict[key]).strip()),
                reference,
            )
            db.execute(
                """
                INSERT INTO students
                    (id, reference, display_name, raw_data, prediction,
                     p_dropout, p_enrolled, p_graduate,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    reference,
                    display_name,
                    json.dumps(raw_dict),
                    pred_row["prediction"],
                    float(pred_row["p_Dropout"]),
                    float(pred_row["p_Enrolled"]),
                    float(pred_row["p_Graduate"]),
                    now,
                    now,
                ),
            )
            inserted += 1
        except Exception as exc:
            errors.append({"row": i + 1, "error": str(exc)})

    return inserted, errors


def get_all_students() -> list[dict]:
    return db.fetchall("SELECT * FROM students ORDER BY created_at DESC")


def get_student(student_id: str) -> dict | None:
    return db.fetchone("SELECT * FROM students WHERE id = ?", (student_id,))


def update_display_name(student_id: str, display_name: str) -> None:
    """Set the human-readable student name shown in the teacher and student views."""
    name = display_name.strip()
    if not name:
        raise ValueError("Display name cannot be empty.")
    db.execute(
        "UPDATE students SET display_name=?, updated_at=? WHERE id=?",
        (name, datetime.datetime.utcnow().isoformat(), student_id),
    )


def update_prediction(student_id: str, pred: dict) -> None:
    now = datetime.datetime.utcnow().isoformat()
    db.execute(
        """
        UPDATE students
        SET prediction=?, p_dropout=?, p_enrolled=?, p_graduate=?, updated_at=?
        WHERE id=?
        """,
        (
            pred["prediction"],
            pred["p_Dropout"],
            pred["p_Enrolled"],
            pred["p_Graduate"],
            now,
            student_id,
        ),
    )
