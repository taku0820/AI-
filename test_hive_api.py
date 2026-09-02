"""AI Hive OS 追加機能の簡易自動テスト。

本番の ai_company.db を汚さないよう、一時コピーに対してテストを実行する。
実行方法: venv/bin/python test_hive_api.py
"""

import os
import shutil
import tempfile
import unittest

import app as app_module
import hive_db


class HiveApiTestCase(unittest.TestCase):

  def setUp(self):
    fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy(hive_db.DB_NAME, self.temp_db_path)

    self._orig_app_db_name = app_module.DB_NAME
    self._orig_hive_db_name = hive_db.DB_NAME
    app_module.DB_NAME = self.temp_db_path
    hive_db.DB_NAME = self.temp_db_path

    app_module.app.testing = True
    self.client = app_module.app.test_client()

  def tearDown(self):
    app_module.DB_NAME = self._orig_app_db_name
    hive_db.DB_NAME = self._orig_hive_db_name
    os.remove(self.temp_db_path)

  def test_existing_root_page_still_works(self):
    res = self.client.get("/")
    self.assertEqual(res.status_code, 200)
    self.assertIn("会社の全体像ダッシュボード", res.get_data(as_text=True))

  def test_existing_logs_api_unchanged(self):
    res = self.client.get("/api/logs")
    self.assertEqual(res.status_code, 200)
    data = res.get_json()
    self.assertIsInstance(data, list)
    self.assertGreaterEqual(len(data), 1)
    self.assertEqual(len(data[0]), 5)  # id, timestamp, theme, content, status

  def test_hive_tables_exist_alongside_work_logs(self):
    conn = hive_db.get_connection()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    for t in (
        "work_logs", "employees", "missions", "tasks", "metrics",
        "reports", "proposals", "decisions",
    ):
      self.assertIn(t, tables)

  def test_foreign_keys_enforced_on_new_connections(self):
    conn = hive_db.get_connection()
    pragma_value = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    self.assertEqual(pragma_value, 1)

    with self.assertRaises(app_module.sqlite3.IntegrityError):
      conn.execute(
          "INSERT INTO tasks (title, mission_id) VALUES (?, ?)",
          ("存在しないmissionを参照するtask", 999999),
      )
    conn.close()

    res = self.client.post(
        "/api/tasks",
        json={"title": "存在しないmissionを参照するtask", "mission_id": 999999},
    )
    self.assertEqual(res.status_code, 500)
    self.assertEqual(res.get_json()["status"], "error")

  def test_employee_crud_flow(self):
    res = self.client.post(
        "/api/employees",
        json={"name": "テスト社員", "role": "QA", "department": "検証部"},
    )
    self.assertEqual(res.status_code, 201)
    body = res.get_json()
    self.assertEqual(body["status"], "success")
    employee_id = body["data"]["id"]

    res = self.client.get("/api/employees")
    self.assertEqual(res.status_code, 200)
    body = res.get_json()
    self.assertEqual(body["status"], "success")
    self.assertTrue(any(e["id"] == employee_id for e in body["data"]))

  def test_full_mission_flow(self):
    emp = self.client.post(
        "/api/employees", json={"name": "発行者"}
    ).get_json()["data"]

    mission = self.client.post(
        "/api/missions",
        json={"title": "テストMISSION", "issued_by": emp["id"]},
    ).get_json()["data"]
    self.assertIsNotNone(mission["mission_code"])

    res = self.client.get(f"/api/missions/{mission['id']}")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.get_json()["data"]["id"], mission["id"])

    task = self.client.post(
        "/api/tasks",
        json={
            "title": "テストTASK",
            "mission_id": mission["id"],
            "assigned_to": emp["id"],
        },
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "done", "completed_at": "2026-09-02 12:00:00"},
    )
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.get_json()["data"]["status"], "done")

    res = self.client.post(
        "/api/metrics",
        json={
            "mission_id": mission["id"],
            "metric_name": "revenue",
            "metric_value": 100.0,
        },
    )
    self.assertEqual(res.status_code, 201)

    report = self.client.post(
        "/api/reports",
        json={
            "mission_id": mission["id"],
            "task_id": task["id"],
            "reported_by": emp["id"],
            "facts": "テスト事実",
        },
    ).get_json()["data"]
    self.assertIsNotNone(report["id"])

    proposal = self.client.post(
        "/api/proposals",
        json={
            "mission_id": mission["id"],
            "proposed_by": emp["id"],
            "title": "テスト提案",
        },
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/proposals/{proposal['id']}", json={"status": "approved"}
    )
    self.assertEqual(res.get_json()["data"]["status"], "approved")

    decision = self.client.post(
        "/api/decisions",
        json={
            "mission_id": mission["id"],
            "proposal_id": proposal["id"],
            "decided_by": emp["id"],
            "decision": "承認",
        },
    ).get_json()["data"]
    self.assertIsNotNone(decision["id"])

    res = self.client.get(f"/api/tasks?mission_id={mission['id']}")
    self.assertEqual(len(res.get_json()["data"]), 1)

  def test_error_response_format_on_missing_required_field(self):
    res = self.client.post("/api/employees", json={})
    self.assertEqual(res.status_code, 400)
    body = res.get_json()
    self.assertEqual(body["status"], "error")
    self.assertIn("message", body)

  def test_404_on_unknown_mission(self):
    res = self.client.get("/api/missions/999999")
    self.assertEqual(res.status_code, 404)
    self.assertEqual(res.get_json()["status"], "error")


if __name__ == "__main__":
  unittest.main()
