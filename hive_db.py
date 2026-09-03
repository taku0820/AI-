"""AI Hive OS 用の共通DBヘルパー。

同じ ai_company.db に対して、既存の work_logs テーブルとは独立した
7つの新規テーブル（employees / missions / tasks / metrics / reports /
proposals / decisions）を安全に追加・操作するためのモジュール。

既存の app.py の GET / ・GET /api/logs の実装、および work_logs テーブルの
定義・データには一切影響しない（CREATE TABLE IF NOT EXISTS のみ使用）。
"""

import functools
import hmac
import os
import sqlite3
import time
import uuid

from flask import jsonify, request

DB_NAME = "ai_company.db"

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
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (manager_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_code TEXT,
    title TEXT NOT NULL,
    description TEXT,
    issued_by INTEGER,
    assigned_to INTEGER,
    priority TEXT,
    status TEXT DEFAULT 'open',
    start_at TEXT,
    due_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (issued_by) REFERENCES employees(id),
    FOREIGN KEY (assigned_to) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_code TEXT,
    mission_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    assigned_to INTEGER,
    priority TEXT,
    status TEXT DEFAULT 'todo',
    due_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
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
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_code TEXT,
    mission_id INTEGER,
    task_id INTEGER,
    reported_by INTEGER,
    facts TEXT,
    analysis TEXT,
    hypothesis TEXT,
    result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (reported_by) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_code TEXT,
    mission_id INTEGER,
    proposed_by INTEGER,
    title TEXT NOT NULL,
    reason TEXT,
    expected_effect TEXT,
    risk TEXT,
    recommendation TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (proposed_by) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_code TEXT,
    mission_id INTEGER,
    proposal_id INTEGER,
    decided_by INTEGER,
    decision TEXT,
    reason TEXT,
    status TEXT DEFAULT 'final',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
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

EMPLOYEE_COLUMNS = [
    "name", "role", "department", "manager_id", "personality", "skills",
    "status",
]
MISSION_COLUMNS = [
    "mission_code", "title", "description", "issued_by", "assigned_to",
    "priority", "status", "start_at", "due_at",
]
TASK_COLUMNS = [
    "task_code", "mission_id", "title", "description", "assigned_to",
    "priority", "status", "due_at", "completed_at",
]
METRIC_COLUMNS = [
    "mission_id", "source", "metric_name", "metric_value", "unit",
    "recorded_at",
]
REPORT_COLUMNS = [
    "report_code", "mission_id", "task_id", "reported_by", "facts",
    "analysis", "hypothesis", "result",
]
PROPOSAL_COLUMNS = [
    "proposal_code", "mission_id", "proposed_by", "title", "reason",
    "expected_effect", "risk", "recommendation", "status",
]
DECISION_COLUMNS = [
    "decision_code", "mission_id", "proposal_id", "decided_by", "decision",
    "reason", "status",
]


def get_connection():
  """AI Hive OS 用のDB接続を返す（既存 work_logs と同じ ai_company.db を使う）。"""
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  return conn


def init_hive_schema():
  """新規7テーブル・インデックスを安全に作成する（既存テーブルは変更しない）。"""
  conn = get_connection()
  conn.executescript(HIVE_SCHEMA)
  conn.commit()
  conn.close()


def gen_code(prefix):
  """未指定時に使う衝突しにくいコードを生成する。"""
  return f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:6]}"


def row_to_dict(row):
  return dict(row) if row is not None else None


def rows_to_list(rows):
  return [dict(row) for row in rows]


def get_row(table, row_id):
  conn = get_connection()
  row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
  conn.close()
  return row_to_dict(row)


def list_rows(table, filters=None, order_by="id DESC"):
  conn = get_connection()
  query = f"SELECT * FROM {table}"
  params = []
  if filters:
    conditions = [f"{key} = ?" for key in filters]
    params = list(filters.values())
    if conditions:
      query += " WHERE " + " AND ".join(conditions)
  query += f" ORDER BY {order_by}"
  rows = conn.execute(query, params).fetchall()
  conn.close()
  return rows_to_list(rows)


def insert_row(table, allowed_columns, data):
  """data のうち allowed_columns に含まれるキーのみINSERTし、挿入行を返す。"""
  keys = [c for c in allowed_columns if c in data]
  conn = get_connection()
  placeholders = ", ".join("?" for _ in keys)
  col_sql = ", ".join(keys)
  cursor = conn.execute(
      f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
      [data[k] for k in keys],
  )
  conn.commit()
  new_id = cursor.lastrowid
  row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (new_id,)).fetchone()
  conn.close()
  return row_to_dict(row)


def update_row(table, allowed_columns, row_id, data):
  """data のうち allowed_columns に含まれるキーのみUPDATEし、更新後の行を返す。"""
  keys = [c for c in allowed_columns if c in data]
  conn = get_connection()
  if keys:
    set_sql = ", ".join(f"{k} = ?" for k in keys)
    conn.execute(
        f"UPDATE {table} SET {set_sql} WHERE id = ?",
        [data[k] for k in keys] + [row_id],
    )
    conn.commit()
  row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
  conn.close()
  return row_to_dict(row)


def success_response(data, status_code=200):
  return jsonify({"status": "success", "data": data}), status_code


def error_response(message, status_code=400):
  return jsonify({"status": "error", "message": message}), status_code


# 権限階層（数値が大きいほど強い権限。上位権限は下位権限の操作も満たす）。
PERMISSION_LEVELS = {"read": 1, "write": 2, "admin": 3}

# 各権限に対応する環境変数名。実トークンの値はここには書かない。
TOKEN_ENV_VARS = {
    "read": "AI_HIVE_READ_TOKEN",
    "write": "AI_HIVE_WRITE_TOKEN",
    "admin": "AI_HIVE_ADMIN_TOKEN",
}


def _get_configured_tokens():
  """環境変数から3権限分のトークンを読み取る（値はここでも保持のみ、出力しない）。"""
  return {
      level: os.environ.get(env_name)
      for level, env_name in TOKEN_ENV_VARS.items()
  }


def _tokens_configuration_is_safe(tokens):
  """異なる権限に同一のトークン値が設定されていないかを確認する。

  read/write/adminのいずれか2つ以上に同じ値が設定されていると、
  「そのトークンがどの権限を表すか」を安全に一意判定できない。
  その場合は設定自体を安全でないとみなし、呼び出し側でfail-closedにする。
  """
  configured = [(level, value) for level, value in tokens.items() if value]
  for i in range(len(configured)):
    for j in range(i + 1, len(configured)):
      _, value_a = configured[i]
      _, value_b = configured[j]
      if hmac.compare_digest(value_a.encode("utf-8"), value_b.encode("utf-8")):
        return False
  return True


def _resolve_permission_level(provided_token, tokens):
  """提示されたトークンがread/write/adminのどれに一致するかを安全に判定する。

  どれにも一致しなければNoneを返す。
  """
  if not provided_token:
    return None
  matched_level = None
  for level, expected in tokens.items():
    if expected and hmac.compare_digest(
        provided_token.encode("utf-8"), expected.encode("utf-8")
    ):
      matched_level = level
  return matched_level


def require_permission(min_level):
  """新規Hive API用の権限別認証デコレータ（既存 GET / ・GET /api/logs には適用しない）。

  min_level: "read" / "write" / "admin" のいずれか。呼び出し元のトークンが
  この権限以上であることを要求する（admin > write > read）。

  実トークンは環境変数 AI_HIVE_READ_TOKEN / AI_HIVE_WRITE_TOKEN /
  AI_HIVE_ADMIN_TOKEN からのみ読み取り、コード・ログ・レスポンスには
  一切出力しない。

  fail-closedの方針：
  - 3権限のいずれかの環境変数が未設定/空の場合は、Hive API全体を認証エラーにする
  - 異なる権限に同一トークン値が設定されている（安全に権限判定できない）場合も
    Hive API全体を認証エラーにする
  - 未認証・無効トークン・権限不足はいずれも401/403の統一JSON形式のみ返し、
    内部の設定理由等は開示しない
  """
  min_rank = PERMISSION_LEVELS[min_level]

  def decorator(view_func):
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
      tokens = _get_configured_tokens()

      if not all(tokens.values()):
        return error_response("認証に失敗しました。", 401)

      if not _tokens_configuration_is_safe(tokens):
        return error_response("認証に失敗しました。", 401)

      auth_header = request.headers.get("Authorization", "")
      if not auth_header.startswith("Bearer "):
        return error_response("認証に失敗しました。", 401)

      provided_token = auth_header[len("Bearer "):]
      level = _resolve_permission_level(provided_token, tokens)
      if level is None:
        return error_response("認証に失敗しました。", 401)

      if PERMISSION_LEVELS[level] < min_rank:
        return error_response("権限が不足しています。", 403)

      return view_func(*args, **kwargs)

    return wrapper

  return decorator
