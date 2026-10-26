"""Student-only calendar for scheduled support follow-ups."""
import calendar
import datetime
import html

import streamlit as st
from services import auth_service, support_service


def _date_value(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _month_grid(month, event_days):
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(month.year, month.month)
    weekdays = "".join(
        f"<div class='weekday'>{day}</div>"
        for day in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    )
    cells = []
    today = datetime.date.today()
    for week in weeks:
        for day in week:
            if not day:
                cells.append("<div class='day empty'></div>")
                continue
            day_date = datetime.date(month.year, month.month, day)
            classes = ["day"]
            if day in event_days:
                classes.append("has-event")
            if day_date == today:
                classes.append("today")
            marker = "<span class='event-dot'></span>" if day in event_days else ""
            cells.append(f"<div class='{' '.join(classes)}'><span>{day}</span>{marker}</div>")
    return (
        "<div class='calendar-grid'>" + weekdays + "".join(cells) + "</div>"
    )


def render():
    if not auth_service.require_role("student"):
        return

    student_id = st.session_state.user.get("student_id")
    plans = support_service.get_plans_for_student(student_id)
    scheduled = []
    for plan in plans:
        follow_up = _date_value(plan.get("follow_up_date"))
        if follow_up:
            scheduled.append((follow_up, plan))
    scheduled.sort(key=lambda item: item[0])
    today = datetime.date.today()
    upcoming = [(date, plan) for date, plan in scheduled if date >= today]
    past = [(date, plan) for date, plan in scheduled if date < today]

    st.title("Your Calendar")
    st.caption("A clear view of your upcoming support meetings and follow-ups.")

    next_date = upcoming[0][0].strftime("%b %d").replace(" 0", " ") if upcoming else "None scheduled"
    stats = st.columns(3)
    for column, label, value in zip(
        stats,
        ("Upcoming follow-ups", "Next follow-up", "Past follow-ups"),
        (str(len(upcoming)), next_date, str(len(past))),
    ):
        column.markdown(
            f"<div style='background:#fff;border:1px solid #E8DFFA;border-radius:12px;"
            f"padding:12px 15px;min-height:82px'><div style='color:#766B8B;font-size:.82rem;"
            f"margin-bottom:7px'>{label}</div><div style='color:#281B42;font-size:1.45rem;"
            f"font-weight:700'>{value}</div></div>",
            unsafe_allow_html=True,
        )

    month = upcoming[0][0].replace(day=1) if upcoming else today.replace(day=1)
    event_days = {date.day for date, _ in upcoming if date.year == month.year and date.month == month.month}
    st.markdown(
        f"<section class='calendar-panel'><div class='calendar-heading'>"
        f"<div><div class='eyebrow'>MONTH AT A GLANCE</div>"
        f"<h3>{month.strftime('%B %Y')}</h3></div>"
        f"<div class='calendar-legend'><span class='legend-dot'></span> Follow-up</div></div>"
        f"{_month_grid(month, event_days)}</section>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """<style>
        .calendar-panel{background:#fff;border:1px solid #E8DFFA;border-radius:16px;padding:20px 22px;margin:8px 0 24px}
        .calendar-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
        .calendar-heading h3{margin:3px 0 0;color:#281B42;font-size:1.3rem}
        .eyebrow{font-size:.7rem;letter-spacing:.12em;font-weight:700;color:#766B8B}
        .calendar-legend{font-size:.82rem;color:#5D506F;display:flex;align-items:center;gap:7px}
        .legend-dot,.event-dot{width:7px;height:7px;background:#7044BF;border-radius:50%;display:inline-block}
        .calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}
        .weekday{text-align:center;font-size:.76rem;font-weight:700;color:#766B8B;padding:7px 0}
        .day{height:52px;border-radius:10px;background:#F8F6FF;color:#34254D;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;font-size:.9rem}
        .day.empty{background:transparent}.day.has-event{background:#EDE0FF;color:#452477;font-weight:700}.day.today{outline:2px solid #7044BF;outline-offset:-2px}
        @media(max-width:600px){.calendar-panel{padding:15px}.day{height:42px}.calendar-grid{gap:3px}}
        </style>""",
        unsafe_allow_html=True,
    )

    st.subheader("Upcoming")
    if not upcoming:
        st.info("There are no upcoming meetings or follow-ups scheduled.")
    else:
        for date, plan in upcoming:
            with st.container(border=True):
                date_col, detail_col = st.columns([1, 5])
                with date_col:
                    st.markdown(
                        f"<div style='background:#EDE0FF;border-radius:12px;text-align:center;"
                        f"padding:11px 8px;color:#452477'><div style='font-size:.72rem;font-weight:700'>"
                        f"{date.strftime('%a').upper()}</div><div style='font-size:1.55rem;font-weight:800'>"
                        f"{date.day}</div><div style='font-size:.75rem'>{date.strftime('%b %Y')}</div></div>",
                        unsafe_allow_html=True,
                    )
                with detail_col:
                    st.markdown(f"**{html.escape(plan.get('concern') or 'Support follow-up')}**")
                    st.write(plan.get("action") or "No action details provided.")
                    mentor = html.escape(plan.get("mentor") or "Not assigned")
                    status = html.escape(plan.get("status") or "Unknown")
                    st.caption(f"Mentor: {mentor} · Status: {status}")

    if past:
        with st.expander(f"Past follow-ups ({len(past)})"):
            for date, plan in reversed(past):
                st.markdown(
                    f"**{date.strftime('%b %d, %Y')} · "
                    f"{html.escape(plan.get('concern') or 'Follow-up')}**"
                )
                st.caption(
                    f"Mentor: {plan.get('mentor') or 'Not assigned'} · "
                    f"{plan.get('status') or 'Unknown'} · {plan.get('action') or 'No action details provided.'}"
                )


render()
