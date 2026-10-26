"""
seed_db.py — Standalone script to populate eduhope.db from dataset.csv.

Run once from the project root:
    python seed_db.py

Loads the model directly (no Streamlit) and inserts all students.
Safe to re-run (prompts before clearing old data).
"""
import sys
import pathlib
import json
import uuid
import datetime
import sqlite3

import pandas as pd
import numpy as np
import joblib

ROOT = pathlib.Path(__file__).parent
DB_PATH = ROOT / "eduhope.db"
SCHEMA_PATH = ROOT / "database" / "schema.sql"
MODEL_PATH = ROOT / "eduhope_model.joblib"
CSV_PATH = ROOT / "dataset.csv"

# ── DB helpers ────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db(conn):
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()

# ── Feature engineering (mirrors model_service.py) ────────────────────────────

def engineer_features(raw_df: pd.DataFrame, feature_names: list) -> pd.DataFrame:
    df = raw_df.copy()
    eps = 1e-6

    ap1 = df["Curricular units 1st sem (approved)"]
    en1 = df["Curricular units 1st sem (enrolled)"]
    ev1 = df["Curricular units 1st sem (evaluations)"]
    gr1 = df["Curricular units 1st sem (grade)"]
    ap2 = df["Curricular units 2nd sem (approved)"]
    en2 = df["Curricular units 2nd sem (enrolled)"]
    ev2 = df["Curricular units 2nd sem (evaluations)"]
    gr2 = df["Curricular units 2nd sem (grade)"]

    df["pass_rate_1st"]           = ap1 / (en1 + eps)
    df["pass_rate_2nd"]           = ap2 / (en2 + eps)
    df["eval_per_unit_1st"]       = ev1 / (en1 + eps)
    df["eval_per_unit_2nd"]       = ev2 / (en2 + eps)
    df["grade_x_pass_1st"]        = gr1 * df["pass_rate_1st"]
    df["grade_x_pass_2nd"]        = gr2 * df["pass_rate_2nd"]
    df["pass_rate_delta"]         = df["pass_rate_2nd"] - df["pass_rate_1st"]
    df["grade_delta"]             = gr2 - gr1
    df["total_approved"]          = ap1 + ap2
    df["total_enrolled"]          = en1 + en2
    df["overall_pass_rate"]       = df["total_approved"] / (df["total_enrolled"] + eps)
    df["evaluations_both"]        = ev1 + ev2
    df["evaluations_per_approved"]= df["evaluations_both"] / (df["total_approved"] + 1)
    df["failed_sem1"]             = (ap1 == 0).astype(int)
    df["failed_sem2"]             = (ap2 == 0).astype(int)
    df["failed_both"]             = ((df["failed_sem1"] == 1) & (df["failed_sem2"] == 1)).astype(int)
    df["financial_risk"]          = df["Debtor"] * (1 - df["Tuition fees up to date"])
    df["age_bucket"]              = pd.cut(
        df["Age at enrollment"], bins=[0, 20, 25, 30, 100], labels=[0, 1, 2, 3]
    ).astype(int)

    missing = [c for c in feature_names if c not in df.columns]
    if missing:
        raise ValueError(f"Missing engineered columns: {missing}")
    return df[feature_names]


def main():
    print("=" * 55)
    print("  EduHope DB Seed")
    print("=" * 55)

    # 1. Load model
    print(f"\n[1/5] Loading model from {MODEL_PATH.name} …")
    if not MODEL_PATH.exists():
        print(f"ERROR: {MODEL_PATH} not found.")
        sys.exit(1)
    artifact = joblib.load(str(MODEL_PATH))
    model = artifact["model"]
    classes = artifact["classes"]
    feature_names = artifact["feature_names"]
    label_encoder = artifact.get("label_encoder")
    print(f"      Classes: {classes}")
    print(f"      Features: {len(feature_names)}")

    # 2. Init DB
    print("\n[2/5] Initialising database …")
    conn = get_conn()
    init_db(conn)

    # 3. Check existing
    existing = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if existing > 0:
        print(f"      {existing} students already in DB.")
        ans = input("      Clear and re-import? [y/N]: ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return
        conn.execute("DELETE FROM students")
        conn.commit()
        print("      Cleared.")

    # 4. Load CSV
    print(f"\n[3/5] Loading {CSV_PATH.name} …")
    df = pd.read_csv(CSV_PATH)
    if "Target" in df.columns:
        df = df.drop(columns=["Target"])
    total = len(df)
    print(f"      {total:,} rows, {df.shape[1]} columns.")

    # 5. Feature engineering + predictions
    print("\n[4/5] Engineering features & running predictions …")
    X = engineer_features(df, feature_names)
    proba = model.predict_proba(X)       # shape (n, 3)
    raw_preds = model.predict(X)

    if label_encoder is not None:
        pred_labels = label_encoder.inverse_transform(raw_preds)
    else:
        pred_labels = [classes[p] for p in raw_preds]

    idx_d = classes.index("Dropout")
    idx_e = classes.index("Enrolled")
    idx_g = classes.index("Graduate")

    from collections import Counter
    dist = Counter(pred_labels)
    print(f"      Distribution: {dict(dist)}")

    # 6. Insert
    print(f"\n[5/5] Inserting {total:,} students into DB …")
    now = datetime.datetime.utcnow().isoformat()
    inserted = 0
    errors = []

    rows_to_insert = []
    for i, (_, raw_row) in enumerate(df.iterrows()):
        try:
            rows_to_insert.append((
                str(uuid.uuid4()),
                f"Student {i + 1:04d}",
                json.dumps(raw_row.to_dict()),
                str(pred_labels[i]),
                float(proba[i, idx_d]),
                float(proba[i, idx_e]),
                float(proba[i, idx_g]),
                now,
                now,
            ))
        except Exception as exc:
            errors.append({"row": i + 1, "error": str(exc)})

    try:
        conn.executemany(
            """
            INSERT INTO students
                (id, reference, raw_data, prediction,
                 p_dropout, p_enrolled, p_graduate,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.commit()
        inserted = len(rows_to_insert)
    except Exception as exc:
        print(f"ERROR during batch insert: {exc}")
        sys.exit(1)

    print(f"\n✅ Done! Inserted {inserted:,} students.")
    if errors:
        print(f"⚠️  {len(errors)} rows had errors:")
        for e in errors[:5]:
            print(f"   Row {e['row']}: {e['error']}")

    conn.close()
    print("\nRefresh the Streamlit app (press R or rerun) to see populated data.")


if __name__ == "__main__":
    main()
