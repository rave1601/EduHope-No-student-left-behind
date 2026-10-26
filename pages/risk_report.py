"""
pages/risk_report.py — Per-student risk analysis and support plan link.
"""
import json
import io
import datetime
import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from services import auth_service

from services import student_service, support_service, model_service


def render():
    if not auth_service.require_role("teacher"):
        return
    st.markdown("## 📊 Risk Report")
    st.caption("View a student's current academic indicators and model prediction.")

    model_ok = model_service.model_available()
    if not model_ok:
        st.error("⚠️ **Model not found.** Place `eduhope_model.joblib` in the project root.")

    all_students = student_service.get_all_students()
    if not all_students:
        st.info("No students in the database. Import some via the Students page first.")
        if st.button("→ Go to Students", key="rr_goto"):
            st.switch_page("pages/students.py")
        return

    refs = {s["reference"]: s["id"] for s in all_students}
    chosen_ref = st.selectbox("Select student", options=list(refs.keys()), key="rr_select")
    student_id = refs[chosen_ref]
    student = student_service.get_student(student_id)

    if not student:
        st.error("Student not found.")
        return

    st.divider()

    try:
        raw = json.loads(student["raw_data"])
    except Exception:
        st.error("Could not parse student raw data.")
        return

    pred  = student.get("prediction", "Unknown")
    p_d   = student.get("p_dropout") or 0.0
    p_e   = student.get("p_enrolled") or 0.0
    p_g   = student.get("p_graduate") or 0.0

    # ── Prediction summary ─────────────────────────────────────────────────
    col_pred, col_gauge = st.columns([1, 2])
    with col_pred:
        color = {"Dropout": "#C0392B", "Enrolled": "#E67E22", "Graduate": "#27AE60"}.get(pred, "#7044BF")
        st.markdown(
            f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
            f"padding:20px;text-align:center;'>"
            f"<div style='font-size:0.85rem;color:#766B8B;'>Current Prediction</div>"
            f"<div style='font-size:2rem;font-weight:800;color:{color};margin:8px 0'>{pred}</div>"
            f"<div style='font-size:0.8rem;color:#766B8B'>Based on last imported data</div></div>",
            unsafe_allow_html=True,
        )
        if pred == "Dropout":
            st.info(
                "💬 This student's current academic indicators may warrant "
                "a supportive conversation. Early outreach often makes a meaningful difference."
            )

    with col_gauge:
        fig = go.Figure(go.Bar(
            x=["Dropout", "Enrolled", "Graduate"],
            y=[p_d, p_e, p_g],
            marker_color=["#C0392B", "#E67E22", "#27AE60"],
            text=[f"{v:.1%}" for v in [p_d, p_e, p_g]],
            textposition="auto",
        ))
        fig.update_layout(
            title="Class Probabilities",
            yaxis_title="Probability",
            yaxis_tickformat=".0%",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#281B42"),
            margin=dict(t=40, b=20, l=10, r=10),
            height=260,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Academic Indicators ─────────────────────────────────────────────────
    st.subheader("📚 Academic Indicators")

    en1 = float(raw.get("Curricular units 1st sem (enrolled)") or 0)
    ap1 = float(raw.get("Curricular units 1st sem (approved)") or 0)
    gr1 = float(raw.get("Curricular units 1st sem (grade)") or 0)
    en2 = float(raw.get("Curricular units 2nd sem (enrolled)") or 0)
    ap2 = float(raw.get("Curricular units 2nd sem (approved)") or 0)
    gr2 = float(raw.get("Curricular units 2nd sem (grade)") or 0)
    pr1 = ap1 / max(en1, 1)
    pr2 = ap2 / max(en2, 1)

    # Alert when a student genuinely has no units enrolled (real dataset case)
    if en1 == 0 and en2 == 0:
        st.info(
            "ℹ️ This student's record shows **0 units enrolled** in both semesters. "
            "This reflects the original data — they may have enrolled at a point where "
            "no semester activity had been recorded yet."
        )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("**Semester 1**")
        st.metric("Enrolled", int(en1))
        st.metric("Approved", int(ap1))
        st.metric("Pass Rate", f"{pr1:.1%}")
        st.metric("Grade", f"{gr1:.1f}")
    with col_s2:
        st.markdown("**Semester 2**")
        st.metric("Enrolled", int(en2))
        st.metric("Approved", int(ap2))
        st.metric("Pass Rate", f"{pr2:.1%}", delta=f"{pr2 - pr1:+.1%}")
        st.metric("Grade", f"{gr2:.1f}", delta=f"{gr2 - gr1:+.1f}")

    st.divider()

    # ── Support Plans ───────────────────────────────────────────────────────
    plans = support_service.get_plans_for_student(student_id)
    st.subheader(f"📋 Support Plans ({len(plans)})")
    if plans:
        for p in plans:
            status_color = {
                "Needs follow-up":     "#E67E22",
                "Support in progress": "#7044BF",
                "Follow-up completed": "#27AE60",
            }.get(p["status"], "#766B8B")
            st.markdown(
                f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
                f"padding:12px 16px;margin-bottom:8px;'>"
                f"<b>{html.escape(str(p['concern']))}</b> &nbsp;"
                f"<span style='background:{status_color};color:#fff;border-radius:6px;"
                f"padding:2px 8px;font-size:0.78rem'>{html.escape(str(p['status']))}</span><br/>"
                f"<span style='color:#766B8B;font-size:0.82rem'>"
                f"Priority: {html.escape(str(p['priority']))} · Mentor: {html.escape(str(p.get('mentor') or '—'))} · "
                f"Follow-up: {html.escape(str(p.get('follow_up_date') or '—'))}</span></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No support plans created for this student yet.")

    if st.button("➕ Create Support Plan", key="rr_create_plan", type="primary"):
        st.session_state["pathway_student_id"] = student_id
        st.session_state["pathway_student_ref"] = chosen_ref
        st.switch_page("pages/comeback_pathway.py")

    st.divider()

    # ── Download report ─────────────────────────────────────────────────────
    report_text = _build_report_text(student, raw, pred, p_d, p_e, p_g, pr1, pr2, gr1, gr2, plans)
    st.download_button(
        "⬇ Download Report (.txt)",
        data=report_text,
        file_name=f"risk_report_{chosen_ref.replace(' ', '_')}.txt",
        mime="text/plain",
        key="rr_download",
    )
    st.caption("📌 PDF export is planned as future work (see README).")


def _build_report_text(student, raw, pred, p_d, p_e, p_g, pr1, pr2, gr1, gr2, plans) -> str:
    lines = [
        "EduHope — Student Risk Report",
        "=" * 50,
        f"Reference:    {student.get('reference')}",
        f"Generated:    {datetime.datetime.utcnow().isoformat()[:16]} UTC",
        "",
        "PREDICTION",
        f"  Class:     {pred}",
        f"  P(Dropout):  {p_d:.1%}",
        f"  P(Enrolled): {p_e:.1%}",
        f"  P(Graduate): {p_g:.1%}",
        "",
        "ACADEMIC INDICATORS",
        f"  Sem 1 Pass Rate: {pr1:.1%}  |  Sem 2 Pass Rate: {pr2:.1%}",
        f"  Sem 1 Grade:     {gr1:.2f}  |  Sem 2 Grade:     {gr2:.2f}",
        "",
        "SUPPORT PLANS",
    ]
    if plans:
        for p in plans:
            lines.append(f"  [{p['status']}] {p['concern']} — {p['action']}")
    else:
        lines.append("  None on record.")
    lines += [
        "",
        "NOTE: This is a hypothetical indicator based on a machine-learning model.",
        "It does not constitute a definitive assessment. Please use this alongside",
        "professional judgment and direct student engagement.",
    ]
    return "\n".join(lines)


render()
