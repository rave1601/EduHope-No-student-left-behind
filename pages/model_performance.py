"""
pages/model_performance.py — Compare baseline classifiers from eval_*.json artifacts.
"""
import json
import pathlib
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from services import auth_service

_ROOT = pathlib.Path(__file__).parent.parent
_EVAL_FILES = {
    "Random Forest":      _ROOT / "eval_random_forest.json",
    "Decision Tree":      _ROOT / "eval_decision_tree.json",
    "Logistic Regression": _ROOT / "eval_logistic_regression.json",
}


def _load_eval() -> dict:
    results = {}
    for name, path in _EVAL_FILES.items():
        if path.exists():
            with open(path, encoding="utf-8") as f:
                results[name] = json.load(f)
        else:
            results[name] = None
    return results


def render():
    if not auth_service.require_role("teacher"):
        return
    st.markdown("## 🏆 Model Performance")
    st.caption(
        "Metrics computed via 5-fold cross-validation on the training dataset, seed 42. "
        "These are **not** test-set metrics."
    )

    evals = _load_eval()
    missing = [k for k, v in evals.items() if v is None]
    if missing:
        st.warning(
            f"⚠️ Evaluation files missing: {', '.join(missing)}. "
            "Run the training script to regenerate them."
        )

    available = {k: v for k, v in evals.items() if v is not None}
    if not available:
        st.error("No evaluation JSON files found. Cannot display model performance.")
        return

    # ── Comparison table ─────────────────────────────────────────────────────
    st.subheader("📊 Comparison Table")
    table_rows = []
    for name, data in available.items():
        table_rows.append({
            "Model":           name,
            "Accuracy":        f"{data['accuracy']:.4f}",
            "Macro Precision": f"{data['macro_precision']:.4f}",
            "Macro Recall":    f"{data['macro_recall']:.4f}",
            "Macro F1":        f"{data['macro_f1']:.4f}",
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    # ── Per-model detail ─────────────────────────────────────────────────────
    for name, data in available.items():
        st.divider()
        st.subheader(f"🔍 {name}")
        classes = data.get("classes", ["Dropout", "Enrolled", "Graduate"])
        cm = np.array(data["confusion_matrix"])

        col_cm, col_cr = st.columns([1, 1])
        with col_cm:
            _confusion_heatmap(cm, classes, name)
        with col_cr:
            st.markdown("**Per-class Metrics**")
            cr = data.get("classification_report", {})
            cr_rows = []
            for label, cls in zip(classes, ["0", "1", "2"]):
                if cls in cr:
                    m = cr[cls]
                    cr_rows.append({
                        "Class":     label,
                        "Precision": f"{m['precision']:.3f}",
                        "Recall":    f"{m['recall']:.3f}",
                        "F1":        f"{m['f1-score']:.3f}",
                        "Support":   int(m.get("support", 0)),
                    })
            st.dataframe(pd.DataFrame(cr_rows), use_container_width=True, hide_index=True)
            st.caption(
                f"Accuracy: **{data['accuracy']:.4f}** · "
                f"Macro F1: **{data['macro_f1']:.4f}**"
            )


def _confusion_heatmap(cm: np.ndarray, classes: list, model_name: str):
    text = [[str(v) for v in row] for row in cm]
    fig = go.Figure(go.Heatmap(
        z=cm,
        x=classes,
        y=classes,
        text=text,
        texttemplate="%{text}",
        colorscale=[[0, "#F8F6FF"], [1, "#7044BF"]],
        showscale=False,
    ))
    fig.update_layout(
        title=f"Confusion Matrix — {model_name}",
        xaxis_title="Predicted",
        yaxis_title="Actual",
        yaxis_autorange="reversed",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=50, b=20, l=20, r=10),
        font=dict(color="#281B42"),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)


render()
