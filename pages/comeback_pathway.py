"""
pages/comeback_pathway.py — Create and view support plans.
"""
import datetime
import html
import streamlit as st
from services import auth_service

from services import student_service, support_service


def render():
    if not auth_service.require_role("teacher"):
        return
    st.markdown("## 🛤️ Comeback Pathway")
    st.caption("Create a support plan to guide a student back on track.")

    all_students = student_service.get_all_students()
    if not all_students:
        st.info("No students in the database yet. Import some via the Students page.")
        if st.button("→ Go to Students", key="cp_goto"):
            st.switch_page("pages/students.py")
        return

    refs = {s["reference"]: s["id"] for s in all_students}
    ref_list = list(refs.keys())

    # Pre-fill from Risk Report navigation
    default_ref = st.session_state.pop("pathway_student_ref", None)
    default_idx = ref_list.index(default_ref) if default_ref in ref_list else 0

    chosen_ref = st.selectbox("Select student", options=ref_list, index=default_idx, key="cp_student_select")
    student_id = refs[chosen_ref]

    st.divider()

    # ── Create new plan ─────────────────────────────────────────────────────
    st.subheader("➕ New Support Plan")

    with st.form("cp_new_plan_form"):
        concern = st.selectbox(
            "Concern", options=support_service.CONCERN_OPTIONS, key="cp_concern"
        )
        priority = st.selectbox(
            "Priority", options=support_service.PRIORITIES, index=1, key="cp_priority"
        )
        action = st.text_area(
            "Action plan", placeholder="Describe the intervention or support steps…", key="cp_action"
        )
        mentor = st.text_input("Mentor / counsellor (optional)", key="cp_mentor")
        follow_up = st.date_input(
            "Follow-up date",
            value=datetime.date.today() + datetime.timedelta(days=14),
            key="cp_followup",
        )
        notes = st.text_area("Additional notes (optional)", key="cp_notes")
        submitted = st.form_submit_button("💾 Save Plan", type="primary")

    if submitted:
        if not action.strip():
            st.error("Action plan cannot be empty.")
        else:
            plan_id = support_service.create_plan(
                student_id=student_id,
                concern=concern,
                priority=priority,
                action=action.strip(),
                mentor=mentor.strip(),
                follow_up_date=follow_up.isoformat(),
                notes=notes.strip(),
            )
            st.success(f"✅ Support plan created (ID: {plan_id[:8]}…)")
            st.rerun()

    st.divider()

    # ── Existing plans for this student ─────────────────────────────────────
    plans = support_service.get_plans_for_student(student_id)
    st.subheader(f"📋 Plans for {chosen_ref} ({len(plans)} total)")

    if not plans:
        st.caption("No plans yet for this student.")
        return

    for p in plans:
        status_color = {
            "Needs follow-up":     "#E67E22",
            "Support in progress": "#7044BF",
            "Follow-up completed": "#27AE60",
        }.get(p["status"], "#766B8B")
        priority_color = {
            "High":   "#C0392B",
            "Medium": "#E67E22",
            "Low":    "#27AE60",
        }.get(p["priority"], "#766B8B")

        with st.expander(f"📋 {p['concern']} — {p['status']}", expanded=False):
            st.markdown(
                f"**Priority:** <span style='color:{priority_color}'>{p['priority']}</span>  \n"
                f"**Action:** {html.escape(str(p['action']))}  \n"
                f"**Mentor:** {html.escape(str(p.get('mentor') or '—'))}  \n"
                f"**Follow-up:** {p.get('follow_up_date') or '—'}  \n"
                f"**Status:** <span style='color:{status_color}'>{p['status']}</span>  \n"
                f"**Notes:** {html.escape(str(p.get('notes') or '—'))}  \n"
                f"**Created:** {p['created_at'][:10]}",
                unsafe_allow_html=True,
            )


render()
