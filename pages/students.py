"""
pages/students.py — Import and browse students.
"""
import io
import json
import pandas as pd
import streamlit as st
from services import auth_service

from services import student_service, model_service

PALETTE_MUTED = "#766B8B"
PALETTE_BORDER = "#E8DFFA"


def render():
    if not auth_service.require_role("teacher"):
        return
    st.markdown("## 👥 Students")
    st.caption("Upload a CSV to import students, or browse existing records.")

    model_ok = model_service.model_available()
    if not model_ok:
        st.error(
            "⚠️ **Model not found.** Please place `eduhope_model.joblib` "
            "in the project root before importing students."
        )

    # ── Upload section ──────────────────────────────────────────────────────
    st.subheader("📥 Import from CSV")
    uploaded = st.file_uploader("Upload student CSV (dataset.csv format)", type=["csv"], key="students_upload")

    if uploaded is not None:
        try:
            df_raw = pd.read_csv(uploaded)
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")
            return

        st.markdown(f"**Preview** — {len(df_raw):,} rows × {df_raw.shape[1]} columns")
        st.dataframe(df_raw.head(10), use_container_width=True)

        missing_cols = student_service.validate_csv(df_raw)
        if missing_cols:
            st.error(f"❌ CSV validation found {len(missing_cols)} issue(s):")
            st.code("\n".join(missing_cols))
            error_csv = pd.DataFrame({"Missing columns": missing_cols})
            st.download_button(
                "⬇ Download validation errors",
                error_csv.to_csv(index=False),
                file_name="validation_errors.csv",
                mime="text/csv",
                key="students_dl_errors",
            )
            return

        if not model_ok:
            st.warning("Import is disabled until the model file is placed correctly.")
            return

        if st.button("✅ Import Students", key="students_import_btn", type="primary"):
            with st.spinner(f"Running predictions on {len(df_raw):,} rows…"):
                inserted, errors = student_service.import_students(df_raw)
            if errors:
                st.warning(f"Imported {inserted} students. {len(errors)} rows had errors.")
                st.dataframe(pd.DataFrame(errors), use_container_width=True)
            else:
                st.success(f"✅ Successfully imported {inserted} students.")

    st.divider()

    # ── Student list ────────────────────────────────────────────────────────
    st.subheader("📋 Student Records")
    all_students = student_service.get_all_students()

    if not all_students:
        st.info("No students imported yet. Use the upload section above.")
        return

    search = st.text_input("Search by student name or reference", placeholder="e.g. Student 001", key="students_search")
    filtered = [
        student for student in all_students
        if not search or search.lower() in (student.get("display_name") or "").lower()
        or search.lower() in (student.get("reference") or "").lower()
    ]

    st.caption(f"Showing {len(filtered)} of {len(all_students)} records")

    # Build a simple table
    rows = []
    for s in filtered:
        rows.append({
            "Student":     s.get("display_name") or s.get("reference", "?"),
            "Reference":   s.get("reference", "—"),
            "Prediction":  s.get("prediction", "—"),
            "P(Dropout)":  f"{s.get('p_dropout', 0):.1%}" if s.get("p_dropout") is not None else "—",
            "P(Enrolled)": f"{s.get('p_enrolled', 0):.1%}" if s.get("p_enrolled") is not None else "—",
            "P(Graduate)": f"{s.get('p_graduate', 0):.1%}" if s.get("p_graduate") is not None else "—",
            "Created":     (s.get("created_at") or "")[:10],
            "id":          s["id"],
        })

    df_display = pd.DataFrame(rows)

    # Colour-code prediction column
    def _color_pred(val):
        c = {"Dropout": "background-color:#fde8e8", "Enrolled": "#fff8e1", "Graduate": "#e8f5e9"}.get(val, "")
        return c

    student_labels = {
        student["id"]: f"{student.get('display_name') or student.get('reference')} ({student.get('reference')})"
        for student in filtered
    }
    selected_id = st.selectbox(
        "Select a student to view details",
        options=[""] + [student["id"] for student in filtered],
        format_func=lambda sid: "? select ?" if not sid else student_labels[sid],
        key="students_select",
    )

    st.dataframe(
        df_display.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
    )

    if selected_id:
        _render_student_detail(selected_id)


def _render_student_detail(student_id: str):
    student = student_service.get_student(student_id)
    if not student:
        st.error("Student not found.")
        return

    st.divider()
    st.subheader(student.get("display_name") or student["reference"])
    st.caption(f"Reference: {student['reference']}")
    with st.form(f"display_name_form_{student_id}"):
        display_name = st.text_input(
            "Student display name",
            value=student.get("display_name") or student.get("reference") or "",
            key=f"display_name_{student_id}",
        )
        if st.form_submit_button("Save display name"):
            try:
                student_service.update_display_name(student_id, display_name)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    col_pred, col_proba = st.columns(2)
    with col_pred:
        pred = student.get("prediction", "Unknown")
        color = {"Dropout": "#C0392B", "Enrolled": "#E67E22", "Graduate": "#27AE60"}.get(pred, "#7044BF")
        st.markdown(
            f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
            f"padding:16px;text-align:center;'><div style='font-size:1.4rem;font-weight:700;"
            f"color:{color}'>{pred}</div><div style='color:#766B8B;font-size:0.82rem'>Last Prediction</div></div>",
            unsafe_allow_html=True,
        )
    with col_proba:
        p_d = student.get("p_dropout") or 0
        p_e = student.get("p_enrolled") or 0
        p_g = student.get("p_graduate") or 0
        st.markdown(
            f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
            f"padding:12px 16px;'>"
            f"<b>Probabilities</b><br/>"
            f"🔴 Dropout: <b>{p_d:.1%}</b><br/>"
            f"🟡 Enrolled: <b>{p_e:.1%}</b><br/>"
            f"🟢 Graduate: <b>{p_g:.1%}</b></div>",
            unsafe_allow_html=True,
        )

    st.markdown("**Raw Features**")
    try:
        raw = json.loads(student["raw_data"])
        st.json(raw, expanded=False)
    except Exception:
        st.code(student["raw_data"])


render()
