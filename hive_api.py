"""AI Hive OS - new REST API endpoints.

Implemented as a Flask Blueprint so app.py only needs to register it,
keeping the existing routes (GET /, GET /api/logs) untouched. All routes
here are new additions layered on top of the existing ai_company.db; none
of them read or write the work_logs table.

Local-only by design: this blueprint is mounted on the same Flask app as
the existing dashboard and is not meant to be exposed to the public
internet without authentication being added later.
"""

import sqlite3

from flask import Blueprint, jsonify, request

import hive_db

bp = Blueprint("hive_api", __name__)


def ok(data, status_code=200):
  return jsonify({"status": "success", "data": data}), status_code


def err(message, status_code=400):
  return jsonify({"status": "error", "message": message}), status_code


def row_to_dict(row):
  return {key: row[key] for key in row.keys()}


def rows_to_list(rows):
  return [row_to_dict(row) for row in rows]


def fetch_json_body():
  data = request.get_json(silent=True)
  if data is None or not isinstance(data, dict):
    return None
  return data


# ---------------------------------------------------------------------------
# Generic list/create/update helpers
# ---------------------------------------------------------------------------


def list_rows(table, order_by="id DESC"):
  conn = hive_db.get_connection()
  try:
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    return ok(rows_to_list(rows))
  finally:
    conn.close()


def get_row(table, row_id):
  conn = hive_db.get_connection()
  try:
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    if row is None:
      return err(f"{table} id={row_id} が見つかりません", 404)
    return ok(row_to_dict(row))
  finally:
    conn.close()


def create_row(table, allowed_fields, required_fields):
  data = fetch_json_body()
  if data is None:
    return err("リクエストボディはJSON形式で送信してください")

  for field in required_fields:
    if not data.get(field):
      return err(f"'{field}' は必須項目です")

  fields = [f for f in allowed_fields if f in data]
  values = [data[f] for f in fields]
  placeholders = ", ".join("?" for _ in fields)
  columns = ", ".join(fields)

  conn = hive_db.get_connection()
  try:
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values
    )
    conn.commit()
    new_row = conn.execute(
        f"SELECT * FROM {table} WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return ok(row_to_dict(new_row), 201)
  except sqlite3.IntegrityError as exc:
    return err(f"データ整合性エラー: {exc}")
  finally:
    conn.close()


def update_row(table, row_id, allowed_fields):
  data = fetch_json_body()
  if data is None:
    return err("リクエストボディはJSON形式で送信してください")

  fields = [f for f in allowed_fields if f in data]
  if not fields:
    return err("更新対象のフィールドがありません")

  set_clause = ", ".join(f"{f} = ?" for f in fields)
  values = [data[f] for f in fields] + [row_id]

  conn = hive_db.get_connection()
  try:
    existing = conn.execute(
        f"SELECT id FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    if existing is None:
      return err(f"{table} id={row_id} が見つかりません", 404)

    conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
    conn.commit()
    updated_row = conn.execute(
        f"SELECT * FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    return ok(row_to_dict(updated_row))
  except sqlite3.IntegrityError as exc:
    return err(f"データ整合性エラー: {exc}")
  finally:
    conn.close()


# ---------------------------------------------------------------------------
# employees
# ---------------------------------------------------------------------------

EMPLOYEE_FIELDS = [
    "name", "role", "department", "manager_id", "personality", "skills",
    "status",
]


@bp.route("/api/employees", methods=["GET"])
def list_employees():
  return list_rows("employees")


@bp.route("/api/employees", methods=["POST"])
def create_employee():
  return create_row("employees", EMPLOYEE_FIELDS, required_fields=["name"])


# ---------------------------------------------------------------------------
# missions
# ---------------------------------------------------------------------------

MISSION_FIELDS = [
    "mission_code", "title", "description", "issued_by", "assigned_to",
    "priority", "status", "start_at", "due_at",
]


@bp.route("/api/missions", methods=["GET"])
def list_missions():
  return list_rows("missions")


@bp.route("/api/missions", methods=["POST"])
def create_mission():
  return create_row("missions", MISSION_FIELDS, required_fields=["title"])


@bp.route("/api/missions/<int:mission_id>", methods=["GET"])
def get_mission(mission_id):
  return get_row("missions", mission_id)


# ---------------------------------------------------------------------------
# tasks
# ---------------------------------------------------------------------------

TASK_FIELDS = [
    "task_code", "mission_id", "title", "description", "assigned_to",
    "priority", "status", "due_at", "completed_at",
]


@bp.route("/api/tasks", methods=["GET"])
def list_tasks():
  return list_rows("tasks")


@bp.route("/api/tasks", methods=["POST"])
def create_task():
  return create_row("tasks", TASK_FIELDS, required_fields=["title"])


@bp.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
  return update_row("tasks", task_id, TASK_FIELDS)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

METRIC_FIELDS = [
    "mission_id", "source", "metric_name", "metric_value", "unit",
    "recorded_at",
]


@bp.route("/api/metrics", methods=["GET"])
def list_metrics():
  return list_rows("metrics")


@bp.route("/api/metrics", methods=["POST"])
def create_metric():
  return create_row(
      "metrics", METRIC_FIELDS, required_fields=["metric_name"]
  )


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

REPORT_FIELDS = [
    "report_code", "mission_id", "task_id", "reported_by", "facts",
    "analysis", "hypothesis", "result",
]


@bp.route("/api/reports", methods=["GET"])
def list_reports():
  return list_rows("reports")


@bp.route("/api/reports", methods=["POST"])
def create_report():
  return create_row("reports", REPORT_FIELDS, required_fields=["facts"])


# ---------------------------------------------------------------------------
# proposals
# ---------------------------------------------------------------------------

PROPOSAL_FIELDS = [
    "proposal_code", "mission_id", "proposed_by", "title", "reason",
    "expected_effect", "risk", "recommendation", "status",
]


@bp.route("/api/proposals", methods=["GET"])
def list_proposals():
  return list_rows("proposals")


@bp.route("/api/proposals", methods=["POST"])
def create_proposal():
  return create_row("proposals", PROPOSAL_FIELDS, required_fields=["title"])


@bp.route("/api/proposals/<int:proposal_id>", methods=["PATCH"])
def update_proposal(proposal_id):
  return update_row("proposals", proposal_id, PROPOSAL_FIELDS)


# ---------------------------------------------------------------------------
# decisions
# ---------------------------------------------------------------------------

DECISION_FIELDS = [
    "decision_code", "mission_id", "proposal_id", "decided_by", "decision",
    "reason", "status",
]


@bp.route("/api/decisions", methods=["GET"])
def list_decisions():
  return list_rows("decisions")


@bp.route("/api/decisions", methods=["POST"])
def create_decision():
  return create_row(
      "decisions", DECISION_FIELDS, required_fields=["decision"]
  )
