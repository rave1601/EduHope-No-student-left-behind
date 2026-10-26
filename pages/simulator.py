"""
pages/simulator.py — Hypothetical scenario simulator.
"""
import json
import copy
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from services import auth_service

from services import student_service, model_service


def render():
    st.markdown("## 🔬 Simulator")
    st.caption(
        "Explore hypothetical academic scenarios for a student. "
        "Changes here do **not** affect stored data unless you explicitly save."
    )

    model_ok = model_service.model_available()
    if not model_ok:
        st.error("⚠️ **Model not found.** Place `eduhope_model.joblib` in the project root.")
        return

    user = st.session_state.get("user") or {}
    if user.get("role") not in {"teacher", "student"}:
        st.error("Access Denied. Please log in to continue.")
        return
    all_students = student_service.get_all_students()
    if user.get("role") == "student":
        all_students = [s for s in all_students if s["id"] == user.get("student_id")]
    if not all_students:
        st.info("No students imported yet. Use the Students page to import a CSV.")
        return

    if user.get("role") == "student":
        student_id = user["student_id"]
    else:
        refs = {s["reference"]: s["id"] for s in all_students}
        chosen_ref = st.selectbox("Select student", options=list(refs.keys()), key="sim_select")
        student_id = refs[chosen_ref]
    student = student_service.get_student(student_id)
    if not student:
        st.error("Student not found.")
        return

    try:
        raw = json.loads(student["raw_data"])
    except Exception:
        st.error("Could not parse student data.")
        return

    # ── Baseline prediction ─────────────────────────────────────────────────
    baseline_pred = {
        "prediction": student.get("prediction", "Unknown"),
        "p_Dropout":  student.get("p_dropout") or 0.0,
        "p_Enrolled": student.get("p_enrolled") or 0.0,
        "p_Graduate": student.get("p_graduate") or 0.0,
    }

    st.subheader("📐 Baseline")
    _show_prediction_row(baseline_pred)
    st.divider()

    # ── Sliders ─────────────────────────────────────────────────────────────
    st.subheader("🎛️ Adjust Hypothetical Values")

    en1 = int(float(raw.get("Curricular units 1st sem (enrolled)", 6) or 0))
    en2 = int(float(raw.get("Curricular units 2nd sem (enrolled)", 6) or 0))
    ap1_base = int(float(raw.get("Curricular units 1st sem (approved)", 0) or 0))
    ap2_base = int(float(raw.get("Curricular units 2nd sem (approved)", 0) or 0))
    gr1_base = float(raw.get("Curricular units 1st sem (grade)", 0.0) or 0.0)
    gr2_base = float(raw.get("Curricular units 2nd sem (grade)", 0.0) or 0.0)

    # Keep each student's scenario values separate when switching records.
    slider_keys = {
        "en1": f"sim_{student_id}_enrolled_1",
        "ap1": f"sim_{student_id}_approved_1",
        "gr1": f"sim_{student_id}_grade_1",
        "en2": f"sim_{student_id}_enrolled_2",
        "ap2": f"sim_{student_id}_approved_2",
        "gr2": f"sim_{student_id}_grade_2",
    }

    if st.button("🔄 Reset to Baseline", key="sim_reset"):
        for key in slider_keys.values():
            st.session_state.pop(key, None)
        st.rerun()

    if en1 == 0 or en2 == 0:
        st.info(
            "The stored baseline has no enrolled units in at least one semester. "
            "Set hypothetical enrollment above 0 to enable approved-unit and grade controls for that semester."
        )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Semester 1**")
        sim_en1 = st.slider(
            f"Enrolled units (max {max(26, en1)})", min_value=0,
            max_value=max(26, en1), value=en1,
            key=slider_keys["en1"],
        )
        if slider_keys["ap1"] in st.session_state:
            st.session_state[slider_keys["ap1"]] = min(st.session_state[slider_keys["ap1"]], sim_en1)
        if sim_en1 == 0:
            sim_ap1 = 0
            st.caption("Approved units: 0 (no units enrolled)")
            st.session_state[slider_keys["gr1"]] = 0.0
        else:
            sim_ap1 = st.slider(
                f"Approved units (max {sim_en1})", min_value=0, max_value=sim_en1,
                value=min(ap1_base, sim_en1), key=slider_keys["ap1"],
            )
        sim_gr1 = st.slider(
            "Grade (0–20)", min_value=0.0, max_value=20.0, step=0.5,
            value=gr1_base if sim_en1 > 0 else 0.0,
            key=slider_keys["gr1"], disabled=sim_en1 == 0,
        )

    with col2:
        st.markdown("**Semester 2**")
        sim_en2 = st.slider(
            f"Enrolled units (max {max(26, en2)})", min_value=0,
            max_value=max(26, en2), value=en2,
            key=slider_keys["en2"],
        )
        if slider_keys["ap2"] in st.session_state:
            st.session_state[slider_keys["ap2"]] = min(st.session_state[slider_keys["ap2"]], sim_en2)
        if sim_en2 == 0:
            sim_ap2 = 0
            st.caption("Approved units: 0 (no units enrolled)")
            st.session_state[slider_keys["gr2"]] = 0.0
        else:
            sim_ap2 = st.slider(
                f"Approved units (max {sim_en2})", min_value=0, max_value=sim_en2,
                value=min(ap2_base, sim_en2), key=slider_keys["ap2"],
            )
        sim_gr2 = st.slider(
            "Grade (0–20)", min_value=0.0, max_value=20.0, step=0.5,
            value=gr2_base if sim_en2 > 0 else 0.0,
            key=slider_keys["gr2"], disabled=sim_en2 == 0,
        )

    # ── Run simulation ───────────────────────────────────────────────────────
    if st.button("▶ Simulate", key="sim_run", type="primary"):
        modified_raw = copy.deepcopy(raw)
        modified_raw["Curricular units 1st sem (enrolled)"] = sim_en1
        modified_raw["Curricular units 1st sem (approved)"] = sim_ap1
        modified_raw["Curricular units 1st sem (grade)"]    = sim_gr1
        modified_raw["Curricular units 2nd sem (enrolled)"] = sim_en2
        modified_raw["Curricular units 2nd sem (approved)"] = sim_ap2
        modified_raw["Curricular units 2nd sem (grade)"]    = sim_gr2
        for semester, enrolled, approved in (("1st", sim_en1, sim_ap1), ("2nd", sim_en2, sim_ap2)):
            evaluations_key = f"Curricular units {semester} sem (evaluations)"
            original_evaluations = int(float(raw.get(evaluations_key, 0) or 0))
            modified_raw[evaluations_key] = max(approved, min(original_evaluations, enrolled))
            without_evaluations_key = f"Curricular units {semester} sem (without evaluations)"
            original_without_evaluations = int(float(raw.get(without_evaluations_key, 0) or 0))
            modified_raw[without_evaluations_key] = min(original_without_evaluations, enrolled)

        try:
            scenario_pred = model_service.predict_one(modified_raw)
        except Exception as exc:
            st.error(f"Simulation error: {exc}")
            return

        st.divider()
        st.subheader("📊 Baseline vs Scenario")
        col_base, col_scen = st.columns(2)
        with col_base:
            st.markdown("**Baseline**")
            _show_prediction_row(baseline_pred)
        with col_scen:
            st.markdown("**Scenario**")
            _show_prediction_row(scenario_pred)

        # Delta chart
        delta_d = scenario_pred["p_Dropout"]  - baseline_pred["p_Dropout"]
        delta_e = scenario_pred["p_Enrolled"] - baseline_pred["p_Enrolled"]
        delta_g = scenario_pred["p_Graduate"] - baseline_pred["p_Graduate"]

        fig = go.Figure(go.Bar(
            x=["Dropout", "Enrolled", "Graduate"],
            y=[delta_d, delta_e, delta_g],
            marker_color=[
                "#C0392B" if delta_d > 0 else "#27AE60",
                "#E67E22" if delta_e > 0 else "#27AE60",
                "#27AE60" if delta_g > 0 else "#C0392B",
            ],
            text=[f"{v:+.1%}" for v in [delta_d, delta_e, delta_g]],
            textposition="auto",
        ))
        fig.update_layout(
            title="Probability Delta (Scenario − Baseline)",
            yaxis_title="Change in Probability",
            yaxis_tickformat=".1%",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#281B42"),
            margin=dict(t=40, b=20, l=10, r=10),
            height=280,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "ℹ️ This is a hypothetical scenario, not a guarantee of a future outcome. "
            "Changes in model predictions do not establish that changing an individual "
            "attribute will cause the outcome to improve."
        )

        # Optional save
        if user.get("role") == "teacher" and st.button("Save as New Prediction", key="sim_save"):
            student_service.update_prediction(student_id, scenario_pred)
            st.success("Prediction updated in database.")


def _show_prediction_row(pred: dict):
    p_d = pred["p_Dropout"]
    p_e = pred["p_Enrolled"]
    p_g = pred["p_Graduate"]
    label = pred["prediction"]
    color = {"Dropout": "#C0392B", "Enrolled": "#E67E22", "Graduate": "#27AE60"}.get(label, "#7044BF")
    st.markdown(
        f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
        f"padding:12px 16px;'>"
        f"<b style='color:{color};font-size:1.1rem'>{label}</b><br/>"
        f"🔴 Dropout: <b>{p_d:.1%}</b><br/>"
        f"🟡 Enrolled: <b>{p_e:.1%}</b><br/>"
        f"🟢 Graduate: <b>{p_g:.1%}</b></div>",
        unsafe_allow_html=True,
    )


render()
