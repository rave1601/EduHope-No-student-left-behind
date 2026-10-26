"""
pages/support_tracker.py — All support plans, filterable; status updates and progress notes.
"""
import datetime
import html
import streamlit as st
from services import auth_service
import pandas as pd

from services import support_service, student_service


def render():
    if not auth_service.require_role("teacher"):
        return
    st.markdown("## 📋 Support Tracker")
    st.caption("View, filter, and update all support plans across students.")

    all_plans = support_service.get_all_plans()

    if not all_plans:
        st.info("No support plans created yet. Use Comeback Pathway to create one.")
        if st.button("→ Go to Comeback Pathway", key="st_goto"):
            st.switch_page("pages/comeback_pathway.py")
        return

    # ── Filters ─────────────────────────────────────────────────────────────
    st.subheader("🔎 Filters")
    today = datetime.date.today().isoformat()

    f1, f2, f3 = st.columns(3)
    with f1:
        status_filter = st.multiselect(
            "Status",
            options=support_service.PLAN_STATUSES,
            default=[],
            key="st_status_filter",
        )
    with f2:
        all_mentors = sorted({p.get("mentor") or "" for p in all_plans} - {""})
        mentor_filter = st.selectbox(
            "Mentor", options=["All"] + all_mentors, key="st_mentor_filter"
        )
    with f3:
        overdue_only = st.checkbox("Overdue only", key="st_overdue_filter")

    # Apply filters
    filtered = all_plans
    if status_filter:
        filtered = [p for p in filtered if p["status"] in status_filter]
    if mentor_filter != "All":
        filtered = [p for p in filtered if p.get("mentor") == mentor_filter]
    if overdue_only:
        filtered = [
            p for p in filtered
            if p.get("follow_up_date")
            and p["follow_up_date"] < today
            and p["status"] != "Follow-up completed"
        ]

    # ── Summary table ────────────────────────────────────────────────────────
    # Enrich with student reference
    students_map = {s["id"]: s["reference"] for s in student_service.get_all_students()}

    rows = []
    for p in filtered:
        is_overdue = (
            bool(p.get("follow_up_date"))
            and p["follow_up_date"] < today
            and p["status"] != "Follow-up completed"
        )
        rows.append({
            "Student":    students_map.get(p["student_id"], p["student_id"][:8]),
            "Concern":    p["concern"],
            "Priority":   p["priority"],
            "Status":     p["status"],
            "Mentor":     p.get("mentor") or "—",
            "Follow-up":  p.get("follow_up_date") or "—",
            "Overdue":    "⚠️ Yes" if is_overdue else "",
            "_plan_id":   p["id"],
        })

    if not rows:
        st.info("No plans match the selected filters.")
        return

    df_table = pd.DataFrame(rows)
    st.caption(f"{len(filtered)} plans shown")
    st.dataframe(df_table.drop(columns=["_plan_id"]), use_container_width=True, hide_index=True)

    st.divider()

    # ── Detail / edit panel ──────────────────────────────────────────────────
    st.subheader("✏️ Plan Detail")
    plan_options = {f"{r['Student']} — {r['Concern']} [{r['Status']}]": r["_plan_id"] for r in rows}

    if not plan_options:
        st.caption("No plans match the current filter.")
        return

    chosen_label = st.selectbox("Select plan to edit", options=list(plan_options.keys()), key="st_plan_select")
    plan_id = plan_options[chosen_label]
    plan = support_service.get_plan(plan_id)

    if not plan:
        st.error("Plan not found.")
        return

    with st.form("st_edit_form"):
        new_status = st.selectbox(
            "Status",
            options=support_service.PLAN_STATUSES,
            index=support_service.PLAN_STATUSES.index(plan["status"]),
            key="st_edit_status",
        )
        follow_up_str = plan.get("follow_up_date") or datetime.date.today().isoformat()
        try:
            fu_date = datetime.date.fromisoformat(follow_up_str)
        except Exception:
            fu_date = datetime.date.today()
        new_follow_up = st.date_input("Follow-up date", value=fu_date, key="st_edit_followup")
        save_plan = st.form_submit_button("💾 Save Changes", type="primary")

    if save_plan:
        if new_status != plan["status"]:
            support_service.update_plan_field(plan_id, "status", new_status)
        if new_follow_up.isoformat() != (plan.get("follow_up_date") or ""):
            support_service.update_plan_field(plan_id, "follow_up_date", new_follow_up.isoformat())
        st.success("Plan updated.")
        st.rerun()

    delete_state_key = "st_delete_plan_confirmation"
    if st.button("🗑 Delete support plan", key="st_delete_plan_button"):
        st.session_state[delete_state_key] = plan_id

    if st.session_state.get(delete_state_key) == plan_id:
        st.warning(
            "Deleting this plan also deletes its progress notes. The audit log will retain a deletion record."
        )
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            confirm_delete = st.button(
                "Confirm delete", key="st_confirm_delete_plan", type="primary"
            )
        with cancel_col:
            cancel_delete = st.button("Cancel", key="st_cancel_delete_plan")

        if confirm_delete:
            support_service.delete_plan(plan_id)
            st.session_state.pop(delete_state_key, None)
            st.success("Support plan deleted.")
            st.rerun()
        if cancel_delete:
            st.session_state.pop(delete_state_key, None)
            st.rerun()

    # ── Progress notes ───────────────────────────────────────────────────────
    st.markdown("**Progress Notes**")
    with st.form("st_note_form"):
        note_author = st.text_input("Your name / role (optional)", key="st_note_author")
        note_body   = st.text_area("Note", placeholder="Write a progress update…", key="st_note_body")
        add_note = st.form_submit_button("➕ Add Note")

    if add_note:
        if note_body.strip():
            support_service.add_note(plan_id, note_author.strip(), note_body.strip())
            st.success("Note added.")
            st.rerun()
        else:
            st.error("Note cannot be empty.")

    notes = support_service.get_notes_for_plan(plan_id)
    if notes:
        for n in notes:
            author_label = n.get("author") or "Anonymous"
            st.markdown(
                f"<div style='background:#F8F6FF;border:1px solid #E8DFFA;border-radius:10px;"
                f"padding:10px 14px;margin-bottom:8px;'>"
                f"<b>{html.escape(str(author_label))}</b> &nbsp;"
                f"<span style='color:#766B8B;font-size:0.8rem'>{n['created_at'][:16].replace('T',' ')}</span>"
                f"<br/>{html.escape(str(n['body']))}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No notes yet.")

    # ── Audit log for this plan ───────────────────────────────────────────────
    with st.expander("🔍 Audit Log", expanded=False):
        log = support_service.get_audit_log(plan_id)
        if log:
            for entry in log:
                st.markdown(
                    f"<small style='color:#766B8B'>{html.escape(str(entry['created_at'][:16].replace('T',' ')))}</small> "
                    f"<b>{html.escape(str(entry.get('field','—')))}</b>: "
                    f"<code>{html.escape(str(entry.get('old_value','—')))}</code> → "
                    f"<code>{html.escape(str(entry.get('new_value','—')))}</code>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No audit entries.")


render()
