"""Demo authentication and role checks for EduHope."""
import hashlib
import uuid

from database import db


def hash_password(password: str) -> str:
    """Hash a password for the demo app; never persist the plain text value."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate(username: str, password: str) -> dict | None:
    user = db.fetchone(
        "SELECT id, username, role, student_id, password_hash FROM users WHERE username=?",
        (username.strip(),),
    )
    if not user or user["password_hash"] != hash_password(password):
        return None
    return {key: user[key] for key in ("id", "username", "role", "student_id")}


def get_user_by_id(user_id: str) -> dict | None:
    """Reload the current account so deleted or changed accounts lose stale sessions."""
    return db.fetchone(
        "SELECT id, username, role, student_id FROM users WHERE id=?",
        (user_id,),
    )


def register_user(username: str, password: str, role: str, student_id: str | None = None) -> str:
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if not password:
        raise ValueError("Password is required.")
    if role not in {"teacher", "student"}:
        raise ValueError("Choose Teacher or Student.")
    if role == "student":
        if not student_id or not db.fetchone("SELECT id FROM students WHERE id=?", (student_id,)):
            raise ValueError("Choose an existing student record.")
    else:
        student_id = None
    user_id = str(uuid.uuid4())
    try:
        db.execute(
            "INSERT INTO users (id, username, password_hash, role, student_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, hash_password(password), role, student_id),
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ValueError("That username is already in use.") from exc
        raise
    return user_id


def require_role(*allowed_roles: str) -> bool:
    """Stop rendering a page when the current session lacks an allowed role."""
    import streamlit as st

    user = st.session_state.get("user")
    if not user:
        st.error("Access Denied. Please log in to continue.")
        return False
    if user.get("role") not in allowed_roles:
        st.error("Access Denied. You do not have permission to view this page.")
        return False
    return True
