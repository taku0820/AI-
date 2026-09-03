"""AI Hive OS 追加機能の簡易自動テスト。

本番の ai_company.db を汚さないよう、一時コピーに対してテストを実行する。
新規Hive APIはMISSION 012でread/write/adminの3階層Bearerトークン認証と
なったため、テスト専用のダミートークン（実運用トークンではない）を
環境変数 AI_HIVE_READ_TOKEN / AI_HIVE_WRITE_TOKEN / AI_HIVE_ADMIN_TOKEN に
設定して検証する。
実行方法: venv/bin/python test_hive_api.py
"""

import os
import shutil
import tempfile
import unittest

import app as app_module
import hive_db

# テスト専用のダミートークン。実運用トークンではなく、コミットしても問題ない。
TEST_READ_TOKEN = "mission012-test-read-token"
TEST_WRITE_TOKEN = "mission012-test-write-token"
TEST_ADMIN_TOKEN = "mission012-test-admin-token"

TOKEN_ENV_VARS = ("AI_HIVE_READ_TOKEN", "AI_HIVE_WRITE_TOKEN", "AI_HIVE_ADMIN_TOKEN")


class HiveApiTestCase(unittest.TestCase):

  def setUp(self):
    fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy(hive_db.DB_NAME, self.temp_db_path)

    self._orig_app_db_name = app_module.DB_NAME
    self._orig_hive_db_name = hive_db.DB_NAME
    app_module.DB_NAME = self.temp_db_path
    hive_db.DB_NAME = self.temp_db_path

    self._orig_token_env = {name: os.environ.get(name) for name in TOKEN_ENV_VARS}
    os.environ["AI_HIVE_READ_TOKEN"] = TEST_READ_TOKEN
    os.environ["AI_HIVE_WRITE_TOKEN"] = TEST_WRITE_TOKEN
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_ADMIN_TOKEN

    app_module.app.testing = True
    self.client = app_module.app.test_client()
    self.read_headers = {"Authorization": f"Bearer {TEST_READ_TOKEN}"}
    self.write_headers = {"Authorization": f"Bearer {TEST_WRITE_TOKEN}"}
    self.admin_headers = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

  def tearDown(self):
    app_module.DB_NAME = self._orig_app_db_name
    hive_db.DB_NAME = self._orig_hive_db_name
    os.remove(self.temp_db_path)

    for name, value in self._orig_token_env.items():
      if value is None:
        os.environ.pop(name, None)
      else:
        os.environ[name] = value

  # --- 既存機能の回帰確認 -------------------------------------------------

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

  def test_existing_routes_require_no_auth(self):
    res = self.client.get("/")
    self.assertEqual(res.status_code, 200)
    res = self.client.get("/api/logs")
    self.assertEqual(res.status_code, 200)

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
        headers=self.admin_headers,
    )
    self.assertEqual(res.status_code, 500)
    self.assertEqual(res.get_json()["status"], "error")

  # --- 基本CRUD（admin権限で一連の機能が動くことの確認） -------------------

  def test_employee_crud_flow(self):
    res = self.client.post(
        "/api/employees",
        json={"name": "テスト社員", "role": "QA", "department": "検証部"},
        headers=self.admin_headers,
    )
    self.assertEqual(res.status_code, 201)
    body = res.get_json()
    self.assertEqual(body["status"], "success")
    employee_id = body["data"]["id"]

    res = self.client.get("/api/employees", headers=self.admin_headers)
    self.assertEqual(res.status_code, 200)
    body = res.get_json()
    self.assertEqual(body["status"], "success")
    self.assertTrue(any(e["id"] == employee_id for e in body["data"]))

  def test_full_mission_flow(self):
    emp = self.client.post(
        "/api/employees", json={"name": "発行者"}, headers=self.admin_headers
    ).get_json()["data"]

    mission = self.client.post(
        "/api/missions",
        json={"title": "テストMISSION", "issued_by": emp["id"]},
        headers=self.admin_headers,
    ).get_json()["data"]
    self.assertIsNotNone(mission["mission_code"])

    res = self.client.get(
        f"/api/missions/{mission['id']}", headers=self.admin_headers
    )
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.get_json()["data"]["id"], mission["id"])

    task = self.client.post(
        "/api/tasks",
        json={
            "title": "テストTASK",
            "mission_id": mission["id"],
            "assigned_to": emp["id"],
        },
        headers=self.admin_headers,
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "done", "completed_at": "2026-09-02 12:00:00"},
        headers=self.admin_headers,
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
        headers=self.admin_headers,
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
        headers=self.admin_headers,
    ).get_json()["data"]
    self.assertIsNotNone(report["id"])

    proposal = self.client.post(
        "/api/proposals",
        json={
            "mission_id": mission["id"],
            "proposed_by": emp["id"],
            "title": "テスト提案",
        },
        headers=self.admin_headers,
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/proposals/{proposal['id']}",
        json={"status": "approved"},
        headers=self.admin_headers,
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
        headers=self.admin_headers,
    ).get_json()["data"]
    self.assertIsNotNone(decision["id"])

    res = self.client.get(
        f"/api/tasks?mission_id={mission['id']}", headers=self.admin_headers
    )
    self.assertEqual(len(res.get_json()["data"]), 1)

  def test_error_response_format_on_missing_required_field(self):
    res = self.client.post(
        "/api/employees", json={}, headers=self.admin_headers
    )
    self.assertEqual(res.status_code, 400)
    body = res.get_json()
    self.assertEqual(body["status"], "error")
    self.assertIn("message", body)

  def test_404_on_unknown_mission(self):
    res = self.client.get("/api/missions/999999", headers=self.admin_headers)
    self.assertEqual(res.status_code, 404)
    self.assertEqual(res.get_json()["status"], "error")

  # --- MISSION 010: 認証の基本 --------------------------------------------

  def test_hive_api_rejects_request_without_authorization_header(self):
    res = self.client.get("/api/employees")
    self.assertEqual(res.status_code, 401)
    body = res.get_json()
    self.assertEqual(body["status"], "error")
    for token in (TEST_READ_TOKEN, TEST_WRITE_TOKEN, TEST_ADMIN_TOKEN):
      self.assertNotIn(token, str(body))

  def test_hive_api_rejects_malformed_authorization_header(self):
    res = self.client.get(
        "/api/employees", headers={"Authorization": "Basic abcdef"}
    )
    self.assertEqual(res.status_code, 401)
    self.assertEqual(res.get_json()["status"], "error")

  def test_hive_api_rejects_invalid_token(self):
    res = self.client.get(
        "/api/employees", headers={"Authorization": "Bearer wrong-token"}
    )
    self.assertEqual(res.status_code, 401)
    self.assertEqual(res.get_json()["status"], "error")

  def test_hive_api_fail_closed_when_any_token_env_unset(self):
    del os.environ["AI_HIVE_WRITE_TOKEN"]
    try:
      # write用の環境変数が未設定の場合、adminトークンで来た要求も含めて
      # Hive API全体を拒否する（部分的な設定では動作させない）。
      res = self.client.get("/api/employees", headers=self.admin_headers)
      self.assertEqual(res.status_code, 401)
      self.assertEqual(res.get_json()["status"], "error")
    finally:
      os.environ["AI_HIVE_WRITE_TOKEN"] = TEST_WRITE_TOKEN

  # --- MISSION 012: 権限分離 ----------------------------------------------

  def test_read_token_allows_read_endpoint(self):
    res = self.client.get("/api/employees", headers=self.read_headers)
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.get_json()["status"], "success")

  def test_read_token_rejected_on_write_endpoint(self):
    res = self.client.post(
        "/api/employees", json={"name": "権限テスト"}, headers=self.read_headers
    )
    self.assertEqual(res.status_code, 403)
    self.assertEqual(res.get_json()["status"], "error")

  def test_write_token_allows_normal_write_endpoint(self):
    res = self.client.post(
        "/api/employees",
        json={"name": "write権限テスト社員"},
        headers=self.write_headers,
    )
    self.assertEqual(res.status_code, 201)
    self.assertEqual(res.get_json()["status"], "success")

  def test_write_token_also_allows_read_endpoint(self):
    res = self.client.get("/api/employees", headers=self.write_headers)
    self.assertEqual(res.status_code, 200)

  def test_write_token_rejected_on_admin_only_endpoint(self):
    emp = self.client.post(
        "/api/employees", json={"name": "権限テスト発行者"},
        headers=self.admin_headers,
    ).get_json()["data"]
    mission = self.client.post(
        "/api/missions",
        json={"title": "権限テストMISSION", "issued_by": emp["id"]},
        headers=self.admin_headers,
    ).get_json()["data"]
    proposal = self.client.post(
        "/api/proposals",
        json={
            "mission_id": mission["id"],
            "proposed_by": emp["id"],
            "title": "権限テスト提案",
        },
        headers=self.admin_headers,
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/proposals/{proposal['id']}",
        json={"status": "approved"},
        headers=self.write_headers,
    )
    self.assertEqual(res.status_code, 403)
    self.assertEqual(res.get_json()["status"], "error")

  def test_admin_token_allows_admin_only_endpoint(self):
    emp = self.client.post(
        "/api/employees", json={"name": "admin権限テスト発行者"},
        headers=self.admin_headers,
    ).get_json()["data"]
    mission = self.client.post(
        "/api/missions",
        json={"title": "admin権限テストMISSION", "issued_by": emp["id"]},
        headers=self.admin_headers,
    ).get_json()["data"]
    proposal = self.client.post(
        "/api/proposals",
        json={
            "mission_id": mission["id"],
            "proposed_by": emp["id"],
            "title": "admin権限テスト提案",
        },
        headers=self.admin_headers,
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/proposals/{proposal['id']}",
        json={"status": "approved"},
        headers=self.admin_headers,
    )
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.get_json()["data"]["status"], "approved")

  def test_duplicate_token_across_permissions_is_safely_rejected(self):
    # read用とwrite用に同一のトークン値を設定した場合、どちらの権限か
    # 安全に一意判定できないため、Hive API全体を拒否しなければならない。
    os.environ["AI_HIVE_WRITE_TOKEN"] = TEST_READ_TOKEN
    try:
      res = self.client.get("/api/employees", headers=self.read_headers)
      self.assertEqual(res.status_code, 401)

      # 重複に関与していないadminトークンでも、設定全体が安全でない
      # とみなして拒否する。
      res = self.client.get("/api/employees", headers=self.admin_headers)
      self.assertEqual(res.status_code, 401)
    finally:
      os.environ["AI_HIVE_WRITE_TOKEN"] = TEST_WRITE_TOKEN


if __name__ == "__main__":
  unittest.main()
