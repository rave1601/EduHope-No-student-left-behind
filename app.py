"""EduHope Streamlit application entry point."""
import streamlit as st
from urllib.parse import urlsplit

st.set_page_config(page_title="EduHope ? No Student Left Behind", page_icon="??", layout="wide", initial_sidebar_state="collapsed")

from database import db
db.init_db()

st.markdown('\n<style>\n@import url(\'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap\');\n\n/* ── Base ── */\nhtml, body, [data-testid="stAppViewContainer"] {\n    background-color: #F8F6FF;\n    color: #281B42;\n    font-family: \'Inter\', \'Segoe UI\', sans-serif;\n}\n\n/* ── Sidebar ── */\n[data-testid="stSidebar"] {\n    background: #FFFFFF;\n    border-right: 1px solid #E8DFFA;\n}\n[data-testid="stSidebar"] * {\n    color: #281B42 !important;\n}\n\n/* ── Header bar ── */\nheader[data-testid="stHeader"] {\n    background: #FFFFFF;\n    border-bottom: 1px solid #E8DFFA;\n}\n\n/* ================================================================\n   FORM INPUT WIDGETS — white background, dark text, purple border\n   ================================================================ */\n\n/* Dark text-entry fields need a light, normal-weight typing color. */\n[data-testid="stTextInput"] input,\n[data-testid="stTextArea"] textarea {\n    color:#FFFFFF !important;\n    -webkit-text-fill-color:#FFFFFF !important;\n    font-weight:400 !important;\n}\n\n/* Form labels stay readable above inputs without using bold text. */\n[data-testid="stTextInput"] label,\n[data-testid="stTextArea"] label,\n[data-testid="stSelectbox"] label,\n[data-testid="stMultiSelect"] label,\n[data-testid="stDateInput"] label,\n[data-testid="stNumberInput"] label,\n[data-testid="stCheckbox"] label,\n[data-testid="stSlider"] label,\n[data-testid="stFileUploader"] label {\n    color:#281B42 !important;\n    -webkit-text-fill-color:#281B42 !important;\n    opacity:1 !important;\n    font-weight:400 !important;\n}\n\n/* ================================================================\n   BUTTONS — purple fill, white text\n   ================================================================ */\n.stButton > button {\n    background: #7044BF !important;\n    color: #FFFFFF !important;\n    border: none !important;\n    border-radius: 12px !important;\n    font-weight: 600 !important;\n    transition: background 0.2s, transform 0.1s;\n}\n.stButton > button:hover {\n    background: #5a36a0 !important;\n    color: #FFFFFF !important;\n    transform: translateY(-1px);\n}\n.stButton > button:active {\n    transform: translateY(0px);\n}\n\n/* ── Download button — must NOT be dark ── */\n.stDownloadButton > button {\n    background: #7044BF !important;\n    color: #FFFFFF !important;\n    border: none !important;\n    border-radius: 12px !important;\n    font-weight: 600 !important;\n    transition: background 0.2s;\n}\n.stDownloadButton > button:hover {\n    background: #5a36a0 !important;\n    color: #FFFFFF !important;\n}\n\n/* ── Form submit buttons ── */\n.stFormSubmitButton > button {\n    background: #7044BF !important;\n    color: #FFFFFF !important;\n    border: none !important;\n    border-radius: 12px !important;\n    font-weight: 600 !important;\n}\n.stFormSubmitButton > button:hover {\n    background: #5a36a0 !important;\n    color: #FFFFFF !important;\n}\n\n/* ================================================================\n   CARDS / METRICS\n   ================================================================ */\ndiv[data-testid="stMetric"] {\n    background: #FFFFFF;\n    border: 1px solid #E8DFFA;\n    border-radius: 12px;\n    padding: 12px;\n    box-shadow: 0 2px 8px rgba(112, 68, 191, 0.08);\n}\ndiv[data-testid="stMetricValue"],\ndiv[data-testid="stMetricLabel"] {\n    color: #281B42 !important;\n}\n\n/* ── Dividers ── */\nhr { border-color: #E8DFFA; }\n\n/* ── Tabs ── */\n.stTabs [data-baseweb="tab"] {\n    color: #766B8B;\n    font-weight: 500;\n}\n.stTabs [aria-selected="true"] {\n    color: #7044BF;\n    border-bottom-color: #7044BF;\n}\n\n/* ── Plotly chart containers ── */\n.js-plotly-plot { border-radius: 12px; }\n\n/* ── DataFrames ── */\n.stDataFrame {\n    border: 1px solid #E8DFFA;\n    border-radius: 12px;\n}\n\n/* ── Remove default padding on main block ── */\n.block-container {\n    padding-top: 1.5rem;\n    padding-bottom: 2rem;\n}\n\n/* NOTE: Do NOT globally override text color to white.\n   Do NOT force colour on input widgets. */\n</style>\n', unsafe_allow_html=True)
st.markdown('<style>[data-testid="stTopNavLink"]{color:#281B42!important;opacity:1!important;font-weight:600!important}[data-testid="stTopNavLink"] *{color:#281B42!important;-webkit-text-fill-color:#281B42!important;opacity:1!important}[data-testid="stTopNavLink"][aria-current="page"]{background:#EDE0FF!important;color:#452477!important}</style>', unsafe_allow_html=True)
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;min-height:56px;margin:18px 0;padding:10px 14px;background:#fff;border:1px solid #E8DFFA;border-radius:12px;">
  <span style="font-size:2rem;line-height:1">&#127891;</span>
  <div><span style="font-size:1.6rem;font-weight:800;color:#7044BF;line-height:1.2">EduHope</span><span style="margin-left:10px;color:#766B8B;font-size:.9rem">No Student Left Behind.</span></div>
</div>
""", unsafe_allow_html=True)

from services import auth_service, student_service

def _render_login_gate():
    st.markdown("""
    <style>
    /* Keep contrast styling limited to login and registration fields. */
    [data-testid="stTextInput"] input {
        background:#FFFFFF !important;
        color:#281B42 !important;
        -webkit-text-fill-color:#281B42 !important;
        font-weight:400 !important;
        border-color:#C8B8F0 !important;
    }
    [data-testid="stTextInput"] input:focus { border-color:#7044BF !important; }
    [data-testid="stSelectbox"] [role="combobox"],
    [data-testid="stSelectbox"] [role="combobox"] *,
    [data-testid="stSelectbox"] input,
    [data-testid="stSelectbox"] [role="option"],
    [data-testid="stSelectbox"] [role="option"] *,
    [data-baseweb="popover"], [data-baseweb="popover"] *,
    [role="listbox"], [role="listbox"] * {
        color: #281B42 !important;
        -webkit-text-fill-color: #281B42 !important;
        opacity: 1 !important;
    }
    [data-testid="stSelectbox"] [role="combobox"],
    [data-baseweb="popover"], [role="listbox"] { background:#FFFFFF !important; }
    [data-testid="stSelectbox"] input[role="combobox"] {
        font-weight: 400 !important;
        text-shadow: none !important;
    }
    [data-testid="stSelectbox"] [role="option"] { background:#FFFFFF !important; }
    [data-testid="stSelectbox"] [role="option"]:hover,
    [data-testid="stSelectbox"] [role="option"][aria-selected="true"] { background:#EDE0FF !important; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:3vh'></div>", unsafe_allow_html=True)
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown("<h2 style='text-align:center;color:#7044BF'>Welcome to EduHope</h2>", unsafe_allow_html=True)
        st.caption("Sign in to continue to your EduHope workspace.")
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            user = auth_service.authenticate(username, password)
            if user:
                st.session_state.user = user
                st.session_state["login_redirect"] = True
                st.rerun()
            st.error("Username or password is incorrect.")
        with st.expander("Register"):
            role = st.selectbox("Account type", ["teacher", "student"], format_func=str.title, key="register_role")
            students = student_service.get_all_students() if role == "student" else []
            student_ids = [student["id"] for student in students]
            labels = {student["id"]: (student.get("display_name") or student.get("reference") or student["id"]) for student in students}
            selected_student = None
            if role == "student":
                if student_ids:
                    selected_student = st.selectbox("Link to student record", student_ids, format_func=lambda sid: labels[sid], key="register_student_id")
                else:
                    st.info("Import student records before registering a student account.")
            with st.form("register_form"):
                new_username = st.text_input("Choose a username", key="register_username")
                new_password = st.text_input("Choose a password", type="password", key="register_password")
                registered = st.form_submit_button("Create account", use_container_width=True)
            if registered:
                try:
                    auth_service.register_user(new_username, new_password, role, selected_student)
                    st.success("Account created. You can now log in.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Could not create the account. Please try another username.")

login_page = st.Page(_render_login_gate, title="\u200b", url_path="login")
if st.session_state.get("user") is None:
    st.navigation([login_page], position="hidden").run()
    st.stop()

user = auth_service.get_user_by_id(st.session_state.user.get("id"))
if user is None:
    st.session_state.pop("user", None)
    st.rerun()
st.session_state.user = user
teacher_only_paths = {
    "/students", "/risk-report", "/comeback-pathway",
    "/support-tracker", "/model-performance",
}
requested_path = urlsplit(st.context.url).path.rstrip("/") or "/"
if requested_path == "/model-performance":
    st.error("Model Performance is not available in the teacher portal.")
    st.stop()
if user.get("role") == "student" and requested_path in teacher_only_paths:
    st.error("Access Denied. You do not have permission to view this page.")
    st.stop()

profile_col, logout_col = st.columns([6, 1])
with profile_col:
    st.caption(f"Logged in as **{user['username']}** · {user['role'].title()}")
with logout_col:
    if st.button("Logout", key="logout_button", use_container_width=True):
        st.session_state.pop("user", None)
        st.switch_page(login_page)

dashboard_page = st.Page("pages/dashboard.py", title="Dashboard", url_path="dashboard", default=True)
students_page = st.Page("pages/students.py", title="Students", url_path="students")
risk_report_page = st.Page("pages/risk_report.py", title="Risk Report", url_path="risk-report")
pathway_page = st.Page("pages/comeback_pathway.py", title="Comeback Pathway", url_path="comeback-pathway")
tracker_page = st.Page("pages/support_tracker.py", title="Support Tracker", url_path="support-tracker")
simulator_page = st.Page("pages/simulator.py", title="Simulator", url_path="simulator")
student_dashboard_page = st.Page("pages/student_dashboard.py", title="Dashboard", url_path="student-dashboard", default=True)
student_calendar_page = st.Page("pages/student_calendar.py", title="Calendar", url_path="student-calendar")
teacher_pages = [dashboard_page, students_page, risk_report_page, pathway_page, tracker_page, simulator_page, login_page]
student_pages = [student_dashboard_page, student_calendar_page, simulator_page, login_page]
pg = st.navigation(teacher_pages if user["role"] == "teacher" else student_pages, position="top")
if st.session_state.pop("login_redirect", False) or requested_path == "/login":
    st.switch_page(student_dashboard_page if user["role"] == "student" else dashboard_page)
pg.run()

