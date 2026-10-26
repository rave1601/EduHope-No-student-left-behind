"""
services/model_service.py

Loads eduhope_model.joblib, engineers features, and generates predictions.
NEVER trains a model. NEVER fabricates predictions.
"""
import pathlib
import functools
import numpy as np
import pandas as pd
import joblib
import streamlit as st

_MODEL_PATH = pathlib.Path(__file__).parent.parent / "eduhope_model.joblib"

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ModelNotLoadedError(Exception):
    """Raised when eduhope_model.joblib is missing or unreadable."""


# ---------------------------------------------------------------------------
# Loading (cached per Streamlit session)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading prediction model…")
def load_model() -> dict:
    """Load and cache the model dict from eduhope_model.joblib.

    Returns a dict with keys: model, label_encoder, feature_names, classes.
    Raises ModelNotLoadedError if the file is absent.
    """
    if not _MODEL_PATH.exists():
        raise ModelNotLoadedError(
            f"Model file not found at {_MODEL_PATH}. "
            "Please place eduhope_model.joblib in the project root."
        )
    artifact = joblib.load(str(_MODEL_PATH))
    return artifact


def model_available() -> bool:
    """Return True if the model file exists on disk."""
    return _MODEL_PATH.exists()


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

# Short aliases used in the raw dataset
_COL = {
    "approved_1st":     "Curricular units 1st sem (approved)",
    "enrolled_1st":     "Curricular units 1st sem (enrolled)",
    "evaluations_1st":  "Curricular units 1st sem (evaluations)",
    "grade_1st":        "Curricular units 1st sem (grade)",
    "approved_2nd":     "Curricular units 2nd sem (approved)",
    "enrolled_2nd":     "Curricular units 2nd sem (enrolled)",
    "evaluations_2nd":  "Curricular units 2nd sem (evaluations)",
    "grade_2nd":        "Curricular units 2nd sem (grade)",
    "debtor":           "Debtor",
    "tuition_ok":       "Tuition fees up to date",
    "age":              "Age at enrollment",
}


def engineer_features(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the 18 engineered features and return a DataFrame with all 46
    columns in the exact order of feature_names from the model artifact.

    Parameters
    ----------
    raw_df : pd.DataFrame
        Must contain the raw columns present in dataset.csv (minus Target).

    Returns
    -------
    pd.DataFrame  with exactly 46 columns matching feature_names order.
    """
    df = raw_df.copy()
    eps = 1e-6

    ap1 = df[_COL["approved_1st"]]
    en1 = df[_COL["enrolled_1st"]]
    ev1 = df[_COL["evaluations_1st"]]
    gr1 = df[_COL["grade_1st"]]

    ap2 = df[_COL["approved_2nd"]]
    en2 = df[_COL["enrolled_2nd"]]
    ev2 = df[_COL["evaluations_2nd"]]
    gr2 = df[_COL["grade_2nd"]]

    df["pass_rate_1st"]       = ap1 / (en1 + eps)
    df["pass_rate_2nd"]       = ap2 / (en2 + eps)
    df["eval_per_unit_1st"]   = ev1 / (en1 + eps)
    df["eval_per_unit_2nd"]   = ev2 / (en2 + eps)
    df["grade_x_pass_1st"]    = gr1 * df["pass_rate_1st"]
    df["grade_x_pass_2nd"]    = gr2 * df["pass_rate_2nd"]
    df["pass_rate_delta"]     = df["pass_rate_2nd"] - df["pass_rate_1st"]
    df["grade_delta"]         = gr2 - gr1
    df["total_approved"]      = ap1 + ap2
    df["total_enrolled"]      = en1 + en2
    df["overall_pass_rate"]   = df["total_approved"] / (df["total_enrolled"] + eps)
    df["evaluations_both"]    = ev1 + ev2
    df["evaluations_per_approved"] = df["evaluations_both"] / (df["total_approved"] + 1)
    df["failed_sem1"]         = (ap1 == 0).astype(int)
    df["failed_sem2"]         = (ap2 == 0).astype(int)
    df["failed_both"]         = ((df["failed_sem1"] == 1) & (df["failed_sem2"] == 1)).astype(int)
    df["financial_risk"]      = df[_COL["debtor"]] * (1 - df[_COL["tuition_ok"]])
    df["age_bucket"]          = pd.cut(
        df[_COL["age"]], bins=[-np.inf, 20, 25, 30, np.inf], labels=[0, 1, 2, 3]
    ).astype(int)

    # Reorder columns to exactly match model feature_names
    artifact = load_model()
    feature_names = artifact["feature_names"]
    missing = [c for c in feature_names if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns after feature engineering: {missing}")
    return df[feature_names]


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

def predict_batch(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Run prediction on a batch of raw rows.

    Returns a DataFrame with columns:
        prediction, p_Dropout, p_Enrolled, p_Graduate
    """
    artifact = load_model()
    model = artifact["model"]
    classes = artifact["classes"]   # e.g. ["Dropout", "Enrolled", "Graduate"]

    X = engineer_features(raw_df)
    proba = model.predict_proba(X)           # shape (n, 3)
    preds = model.predict(X)                 # integer encoded

    # Map integer predictions back to class labels
    label_encoder = artifact.get("label_encoder")
    if label_encoder is not None:
        pred_labels = label_encoder.inverse_transform(preds)
    else:
        pred_labels = [classes[p] for p in preds]

    result = pd.DataFrame({
        "prediction": pred_labels,
        "p_Dropout":  proba[:, classes.index("Dropout")],
        "p_Enrolled": proba[:, classes.index("Enrolled")],
        "p_Graduate": proba[:, classes.index("Graduate")],
    })
    return result


def predict_one(raw_dict: dict) -> dict:
    """
    Run prediction on a single student represented as a dict of raw features.

    Returns dict with keys: prediction, p_Dropout, p_Enrolled, p_Graduate.
    """
    df = pd.DataFrame([raw_dict])
    result_df = predict_batch(df)
    row = result_df.iloc[0]
    return {
        "prediction": row["prediction"],
        "p_Dropout":  float(row["p_Dropout"]),
        "p_Enrolled": float(row["p_Enrolled"]),
        "p_Graduate": float(row["p_Graduate"]),
    }
