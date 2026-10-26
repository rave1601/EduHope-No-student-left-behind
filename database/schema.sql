-- EduHope SQLite Schema
-- Run once at application startup.

CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    reference TEXT,
    display_name TEXT,
    raw_data TEXT NOT NULL,
    prediction TEXT,
    p_dropout REAL,
    p_enrolled REAL,
    p_graduate REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
    student_id TEXT REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS support_plans (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id),
    concern TEXT NOT NULL,
    priority TEXT NOT NULL,
    action TEXT NOT NULL,
    mentor TEXT,
    created_at TEXT NOT NULL,
    follow_up_date TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress_notes (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES support_plans(id),
    author TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);
