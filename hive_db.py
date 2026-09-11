"""AI Hive OS - shared database helpers.

This module adds the AI Hive OS data foundation on top of the existing
``ai_company.db`` SQLite database used by ``app.py``. It never touches the
pre-existing ``work_logs`` table; it only creates new tables (with
``CREATE TABLE IF NOT EXISTS``) so it is always safe to import and call
``init_hive_schema()`` even if the tables already exist.
"""

import sqlite3

DB_NAME = "ai_company.db"


def get_connection():
  """Return a new sqlite3 connection configured for AI Hive OS use.

  Foreign keys are enabled only on this connection; it has no effect on the
  pre-existing work_logs table since that table defines no foreign keys.
  """
  conn = sqlite3.connect(DB_NAME)
  conn.execute("PRAGMA foreign_keys = ON")
  conn.row_factory = sqlite3.Row
  return conn


# All AI Hive OS tables are additive (CREATE TABLE IF NOT EXISTS) and never
# redefine or drop the existing work_logs table.
HIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT,
    department TEXT,
    manager_id INTEGER,
    personality TEXT,
    skills TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (manager_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_code TEXT UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    issued_by INTEGER,
    assigned_to INTEGER,
    priority TEXT,
    status TEXT DEFAULT 'open',
    start_at TEXT,
    due_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (issued_by) REFERENCES employees(id),
    FOREIGN KEY (assigned_to) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_code TEXT UNIQUE,
    mission_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    assigned_to INTEGER,
    priority TEXT,
    status TEXT DEFAULT 'open',
    due_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (assigned_to) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER,
    source TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    unit TEXT,
    recorded_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_code TEXT UNIQUE,
    mission_id INTEGER,
    task_id INTEGER,
    reported_by INTEGER,
    facts TEXT,
    analysis TEXT,
    hypothesis TEXT,
    result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (reported_by) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_code TEXT UNIQUE,
    mission_id INTEGER,
    proposed_by INTEGER,
    title TEXT NOT NULL,
    reason TEXT,
    expected_effect TEXT,
    risk TEXT,
    recommendation TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (proposed_by) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_code TEXT UNIQUE,
    mission_id INTEGER,
    proposal_id INTEGER,
    decided_by INTEGER,
    decision TEXT,
    reason TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (proposal_id) REFERENCES proposals(id),
    FOREIGN KEY (decided_by) REFERENCES employees(id)
);

CREATE INDEX IF NOT EXISTS idx_employees_manager_id ON employees(manager_id);

CREATE INDEX IF NOT EXISTS idx_missions_issued_by ON missions(issued_by);
CREATE INDEX IF NOT EXISTS idx_missions_assigned_to ON missions(assigned_to);

CREATE INDEX IF NOT EXISTS idx_tasks_mission_id ON tasks(mission_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);

CREATE INDEX IF NOT EXISTS idx_metrics_mission_id ON metrics(mission_id);

CREATE INDEX IF NOT EXISTS idx_reports_mission_id ON reports(mission_id);
CREATE INDEX IF NOT EXISTS idx_reports_task_id ON reports(task_id);
CREATE INDEX IF NOT EXISTS idx_reports_reported_by ON reports(reported_by);

CREATE INDEX IF NOT EXISTS idx_proposals_mission_id ON proposals(mission_id);
CREATE INDEX IF NOT EXISTS idx_proposals_proposed_by ON proposals(proposed_by);

CREATE INDEX IF NOT EXISTS idx_decisions_mission_id ON decisions(mission_id);
CREATE INDEX IF NOT EXISTS idx_decisions_proposal_id ON decisions(proposal_id);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_by ON decisions(decided_by);
"""


def init_hive_schema():
  """Create the AI Hive OS tables/indexes if they do not already exist.

  Safe to call on every app startup: it never drops or alters existing
  tables (including work_logs), only adds new ones.
  """
  conn = get_connection()
  try:
    conn.executescript(HIVE_SCHEMA)
    conn.commit()
  finally:
    conn.close()
