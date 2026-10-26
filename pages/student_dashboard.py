"""Student-only dashboard with an academic summary and active support plans."""
import datetime
import html
import json
import streamlit as st
from services import auth_service, student_service, support_service


def _summary_card(column, label: str, value: str):
    column.markdown(
        f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
        f"padding:12px 14px;min-height:78px'>"
        f"<div style='font-size:.8rem;color:#766B8B;margin-bottom:6px'>{html.escape(label)}</div>"
        f"<div style='font-size:1.2rem;font-weight:700;color:#281B42'>{html.escape(value)}</div></div>",
        unsafe_allow_html=True,
    )


def render():
    if not auth_service.require_role("student"):
        return
    user = st.session_state.user
    student = student_service.get_student(user.get("student_id"))
    if not student:
        st.error("Your linked student record could not be found. Contact your teacher.")
        return

    name = student.get("display_name") or student.get("reference") or user["username"]
    st.title(f"Welcome, {name}")
    st.caption("Your progress, support plan, and next steps are here.")

    action_calendar, action_simulator = st.columns(2)
    with action_calendar:
        if st.button("View Calendar and Upcoming Dates", key="student_open_calendar", use_container_width=True):
            st.switch_page("pages/student_calendar.py")
    with action_simulator:
        if st.button("Open Future-Me Simulator", key="student_open_simulator", use_container_width=True):
            st.switch_page("pages/simulator.py")

    raw = json.loads(student.get("raw_data") or "{}")
    semester_1 = raw.get("Curricular units 1st sem (grade)", "Not available")
    semester_2 = raw.get("Curricular units 2nd sem (grade)", "Not available")
    summary_1, summary_2, summary_3 = st.columns(3)
    _summary_card(summary_1, "Predicted outcome", student.get("prediction") or "Unknown")
    _summary_card(summary_2, "Semester 1 grade", str(semester_1))
    _summary_card(summary_3, "Semester 2 grade", str(semester_2))

    plans = [
        plan for plan in support_service.get_plans_for_student(student["id"])
        if plan.get("status") != "Follow-up completed"
    ]
    today = datetime.date.today().isoformat()
    upcoming = sorted(
        (plan for plan in plans if plan.get("follow_up_date") and plan["follow_up_date"] >= today),
        key=lambda plan: plan["follow_up_date"],
    )
    if upcoming:
        next_plan = upcoming[0]
        next_follow_up = (
            f"Next follow-up: {next_plan['follow_up_date']} — "
            f"{next_plan.get('concern') or 'Support plan'} with "
            f"{next_plan.get('mentor') or 'your support team'}. Open Calendar for all dates."
        )
        st.markdown(
            f"<div style='background:#EDE0FF;border:1px solid #D5C3F5;border-radius:10px;"
            f"padding:14px 16px;color:#281B42;font-weight:600'>{html.escape(next_follow_up)}</div>",
            unsafe_allow_html=True,
        )

    st.subheader("Your active support plans")
    if not plans:
        st.info("You have no active support plans right now.")
    else:
        for plan in plans:
            with st.container(border=True):
                st.markdown(f"**{plan.get('concern') or 'Support plan'}**  |  Priority: {plan.get('priority') or 'Not set'}")
                st.write(plan.get("action") or "No action details provided.")
                st.caption(f"Status: {plan.get('status', 'Unknown')} | Mentor: {plan.get('mentor') or 'Not assigned'}")
                if plan.get("follow_up_date"):
                    st.caption(f"Follow-up: {plan['follow_up_date']}")

render()
