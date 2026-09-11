"""Smoke tests for AI Hive OS additions.

Verifies:
  - existing work_logs table/data and GET /, GET /api/logs still work
  - the 7 new AI Hive OS tables exist
  - the new CRUD APIs work end-to-end with the unified response envelope
"""

import os
import sqlite3
import tempfile
import unittest


class HiveOsTestCase(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.tmp_dir = tempfile.mkdtemp()
    cls.db_path = os.path.join(cls.tmp_dir, "ai_company.db")

    import init_db as init_db_module
    init_db_module.DB_NAME = cls.db_path
    init_db_module.main()

    import hive_db
    hive_db.DB_NAME = cls.db_path

    import app as app_module
    app_module.DB_NAME = cls.db_path
    cls.app_module = app_module
    cls.client = app_module.app.test_client()

  def test_01_index_page_still_works(self):
    resp = self.client.get("/")
    self.assertEqual(resp.status_code, 200)
    self.assertIn(b"\xe4\xbc\x9a\xe7\xa4\xbe", resp.data)  # "会社"

  def test_02_existing_logs_api_unchanged(self):
    resp = self.client.get("/api/logs")
    self.assertEqual(resp.status_code, 200)
    data = resp.get_json()
    self.assertIsInstance(data, list)
    self.assertEqual(len(data), 3)  # seeded rows from init_db.py
    # existing shape: [id, timestamp, theme, content, status]
    self.assertEqual(len(data[0]), 5)

  def test_03_work_logs_table_intact(self):
    conn = sqlite3.connect(self.db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(work_logs)")]
    self.assertEqual(
        cols, ["id", "timestamp", "theme", "content", "status"]
    )
    count = conn.execute("SELECT COUNT(*) FROM work_logs").fetchone()[0]
    self.assertEqual(count, 3)
    conn.close()

  def test_04_seven_new_tables_exist(self):
    conn = sqlite3.connect(self.db_path)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conn.close()
    expected = {
        "employees", "missions", "tasks", "metrics", "reports",
        "proposals", "decisions",
    }
    self.assertTrue(expected.issubset(tables), tables)

  def test_05_employees_crud(self):
    resp = self.client.post("/api/employees", json={
        "name": "蒼", "role": "SNS担当", "department": "運用",
    })
    self.assertEqual(resp.status_code, 201)
    body = resp.get_json()
    self.assertEqual(body["status"], "success")
    self.employee_id = body["data"]["id"]

    resp = self.client.get("/api/employees")
    body = resp.get_json()
    self.assertEqual(body["status"], "success")
    self.assertTrue(any(e["name"] == "蒼" for e in body["data"]))

  def test_06_employee_missing_name_fails(self):
    resp = self.client.post("/api/employees", json={"role": "no name"})
    self.assertEqual(resp.status_code, 400)
    body = resp.get_json()
    self.assertEqual(body["status"], "error")

  def test_07_mission_task_report_proposal_decision_flow(self):
    emp = self.client.post(
        "/api/employees", json={"name": "琴衣", "role": "マネージャー"}
    ).get_json()["data"]
    manager_id = emp["id"]

    worker = self.client.post(
        "/api/employees", json={"name": "海", "role": "実行担当"}
    ).get_json()["data"]
    worker_id = worker["id"]

    mission_resp = self.client.post("/api/missions", json={
        "mission_code": "M-001",
        "title": "楽天ROOM売上改善",
        "issued_by": manager_id,
        "assigned_to": worker_id,
        "priority": "high",
    })
    self.assertEqual(mission_resp.status_code, 201)
    mission = mission_resp.get_json()["data"]
    mission_id = mission["id"]

    get_resp = self.client.get(f"/api/missions/{mission_id}")
    self.assertEqual(get_resp.status_code, 200)
    self.assertEqual(get_resp.get_json()["data"]["title"], "楽天ROOM売上改善")

    task_resp = self.client.post("/api/tasks", json={
        "task_code": "T-001",
        "mission_id": mission_id,
        "title": "投稿予約の確認",
        "assigned_to": worker_id,
    })
    self.assertEqual(task_resp.status_code, 201)
    task_id = task_resp.get_json()["data"]["id"]

    patch_resp = self.client.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}
    )
    self.assertEqual(patch_resp.status_code, 200)
    self.assertEqual(patch_resp.get_json()["data"]["status"], "done")

    metric_resp = self.client.post("/api/metrics", json={
        "mission_id": mission_id,
        "metric_name": "clicks",
        "metric_value": 42,
        "unit": "count",
    })
    self.assertEqual(metric_resp.status_code, 201)

    report_resp = self.client.post("/api/reports", json={
        "mission_id": mission_id,
        "task_id": task_id,
        "reported_by": worker_id,
        "facts": "クリック数が42件increasedしました。",
        "result": "順調",
    })
    self.assertEqual(report_resp.status_code, 201)

    proposal_resp = self.client.post("/api/proposals", json={
        "mission_id": mission_id,
        "proposed_by": worker_id,
        "title": "投稿頻度を増やす",
        "reason": "反応が良いため",
    })
    self.assertEqual(proposal_resp.status_code, 201)
    proposal_id = proposal_resp.get_json()["data"]["id"]

    patch_proposal = self.client.patch(
        f"/api/proposals/{proposal_id}", json={"status": "approved"}
    )
    self.assertEqual(patch_proposal.status_code, 200)
    self.assertEqual(
        patch_proposal.get_json()["data"]["status"], "approved"
    )

    decision_resp = self.client.post("/api/decisions", json={
        "mission_id": mission_id,
        "proposal_id": proposal_id,
        "decided_by": manager_id,
        "decision": "承認する",
        "status": "active",
    })
    self.assertEqual(decision_resp.status_code, 201)
    self.assertEqual(
        decision_resp.get_json()["data"]["decided_by"], manager_id
    )

  def test_08_not_found_returns_error_envelope(self):
    resp = self.client.get("/api/missions/999999")
    self.assertEqual(resp.status_code, 404)
    body = resp.get_json()
    self.assertEqual(body["status"], "error")

  def test_09_logs_api_still_unchanged_after_hive_activity(self):
    resp = self.client.get("/api/logs")
    data = resp.get_json()
    self.assertEqual(len(data), 3)


if __name__ == "__main__":
  unittest.main()
