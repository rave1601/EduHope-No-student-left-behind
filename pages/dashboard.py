"""
pages/dashboard.py — EduHope Dashboard
"""
import streamlit as st
from services import auth_service
import html
import plotly.graph_objects as go
import plotly.express as px

from services import analytics_service, support_service

PALETTE = {
    "dropout":  "#7044BF",
    "enrolled": "#8757D9",
    "graduate": "#452477",
    "bg":       "#F8F6FF",
    "card":     "#FFFFFF",
    "primary":  "#7044BF",
    "text":     "#281B42",
    "muted":    "#766B8B",
    "border":   "#E8DFFA",
}


def render():
    if not auth_service.require_role("teacher"):
        return
    st.markdown("## 📊 Dashboard")
    st.caption("Overview of student risk distribution and support activity.")

    kpis = analytics_service.get_kpis()

    # ── KPI Cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    _kpi(c1, "👥 Total Students", kpis["total_students"])
    _kpi(c2, "🔴 Dropout Risk",   kpis["dropout"],  "#C0392B")
    _kpi(c3, "🟡 Enrolled",       kpis["enrolled"], "#E67E22")
    _kpi(c4, "🟢 Graduate",       kpis["graduate"], "#27AE60")
    _kpi(c5, "📋 Open Plans",     kpis["open_plans"])
    _kpi(c6, "⚠️ Overdue",        kpis["overdue"],  "#C0392B" if kpis["overdue"] > 0 else None)

    st.divider()

    if kpis["total_students"] == 0:
        st.info(
            "💡 No students are in the database yet. "
            "Head over to **Students** to upload a CSV and import records."
        )
        if st.button("→ Go to Students", key="dash_goto_students"):
            st.switch_page("pages/students.py")
        return

    # ── Charts row ─────────────────────────────────────────────────────────
    col_pie, col_hist, col_bar = st.columns(3)

    with col_pie:
        _pred_pie(analytics_service.get_prediction_distribution())

    with col_hist:
        _pass_rate_hist(analytics_service.get_pass_rate_distribution())

    with col_bar:
        _plan_status_bar(analytics_service.get_plan_status_distribution())

    st.divider()

    # ── Recent Activity ─────────────────────────────────────────────────────
    st.subheader("🕐 Recent Activity")
    activity = support_service.get_recent_activity(limit=5)
    if not activity:
        st.caption("No activity yet.")
    else:
        for item in activity:
            icon = "📋" if item["type"] == "plan" else "📝"
            label = "Support plan created" if item["type"] == "plan" else "Progress note added"
            st.markdown(
                f"""<div style="background:{PALETTE['card']};border:1px solid {PALETTE['border']};
                border-radius:12px;padding:10px 16px;margin-bottom:8px;">
                {icon} <strong>{label}</strong> &nbsp;·&nbsp;
                <span style='color:{PALETTE["muted"]}'>{html.escape(str(item['created_at'][:16].replace('T',' ')))}</span>
                <br/><span style='color:{PALETTE["text"]}'>{html.escape(str(item['detail'])[:120])}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Quick Actions ───────────────────────────────────────────────────────
    st.subheader("⚡ Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        if st.button("📥 Import Students", use_container_width=True, key="dash_qa_students"):
            st.switch_page("pages/students.py")
    with qa2:
        if st.button("📊 Risk Report", use_container_width=True, key="dash_qa_risk"):
            st.switch_page("pages/risk_report.py")
    with qa3:
        if st.button("🛤️ Comeback Pathway", use_container_width=True, key="dash_qa_pathway"):
            st.switch_page("pages/comeback_pathway.py")


# ── Helpers ────────────────────────────────────────────────────────────────

def _kpi(col, label: str, value: int, color: str = "#7044BF"):
    col.markdown(
        f"""<div style='background:#FFFFFF;border:1px solid #E8DFFA;border-radius:12px;
        padding:14px 10px;text-align:center;box-shadow:0 2px 8px rgba(112,68,191,0.08)'>
        <div style='font-size:1.6rem;font-weight:700;color:{color}'>{value}</div>
        <div style='font-size:0.78rem;color:#766B8B;margin-top:4px'>{label}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _pred_pie(data: list[dict]):
    if not data:
        st.caption("No prediction data yet.")
        return
    labels = [d["prediction"] or "Unknown" for d in data]
    values = [d["count"] for d in data]
    color_map = {"Dropout": "#C0392B", "Enrolled": "#E67E22", "Graduate": "#27AE60", "Unknown": "#95A5A6"}
    colors = [color_map.get(l, "#7044BF") for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.4,
        marker=dict(colors=colors),
        textinfo="percent+label",
    ))
    fig.update_layout(
        title=dict(text="Prediction Distribution", font=dict(color="#281B42", size=13)),
        margin=dict(t=40, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=240,
    )
    st.plotly_chart(fig, use_container_width=True)


def _pass_rate_hist(values: list[float]):
    if not values:
        st.caption("No pass rate data yet.")
        return
    fig = px.histogram(
        x=values, nbins=20,
        labels={"x": "Pass Rate (Sem 1)", "y": "Students"},
        color_discrete_sequence=["#7044BF"],
        title="Pass Rate Distribution (Sem 1)",
    )
    fig.update_layout(
        margin=dict(t=40, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#281B42"),
        title=dict(font=dict(size=13)),
        height=240,
        bargap=0.05,
    )
    fig.update_xaxes(title_font=dict(size=11), range=[0, 1])
    fig.update_yaxes(title_font=dict(size=11))
    st.plotly_chart(fig, use_container_width=True)


def _plan_status_bar(data: list[dict]):
    if not data:
        st.caption("No plan data yet.")
        return
    statuses = [d["status"] for d in data]
    counts   = [d["count"] for d in data]
    color_map = {
        "Needs follow-up":     "#E67E22",
        "Support in progress": "#7044BF",
        "Follow-up completed": "#27AE60",
    }
    colors = [color_map.get(s, "#8757D9") for s in statuses]
    fig = go.Figure(go.Bar(
        x=statuses, y=counts,
        marker_color=colors,
        text=counts, textposition="auto",
    ))
    fig.update_layout(
        title=dict(text="Plan Status", font=dict(color="#281B42", size=13)),
        xaxis_title="Status",
        yaxis_title="Count",
        margin=dict(t=40, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#281B42"),
        height=240,
    )
    st.plotly_chart(fig, use_container_width=True)


render()
