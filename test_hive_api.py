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

    # 一時コピーは本番DBの現在のaudit_logsを引き継ぐため、テストの
    # 決定性のためにここで空にする（本番DBそのものには一切触れない）。
    conn = hive_db.get_connection()
    conn.execute("DELETE FROM audit_logs")
    conn.commit()
    conn.close()

    self._orig_token_env = {name: os.environ.get(name) for name in TOKEN_ENV_VARS}
    os.environ["AI_HIVE_READ_TOKEN"] = TEST_READ_TOKEN
    os.environ["AI_HIVE_WRITE_TOKEN"] = TEST_WRITE_TOKEN
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_ADMIN_TOKEN

    app_module.app.testing = True
    self.client = app_module.app.test_client()
    self.read_headers = {"Authorization": f"Bearer {TEST_READ_TOKEN}"}
    self.write_headers = {"Authorization": f"Bearer {TEST_WRITE_TOKEN}"}
    self.admin_headers = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

    # レート制限はプロセス内メモリで保持されるため、テスト間で持ち越さない。
    hive_db.reset_rate_limits()

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
        "reports", "proposals", "decisions", "audit_logs",
    ):
      self.assertIn(t, tables)

  def test_schema_migration_is_safe_to_rerun(self):
    # init_hive_schema()は CREATE TABLE/INDEX IF NOT EXISTS のみのため、
    # 再実行してもエラーにならず、既存データも消えない。
    before = hive_db.list_rows("employees")
    hive_db.init_hive_schema()
    hive_db.init_hive_schema()
    after = hive_db.list_rows("employees")
    self.assertEqual(before, after)

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

  # --- MISSION 013: 監査ログ ----------------------------------------------

  def _all_audit_logs(self):
    conn = hive_db.get_connection()
    rows = conn.execute(
        "SELECT event_type, http_method, endpoint, status_code, permission,"
        " result_summary FROM audit_logs ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

  def test_allowed_read_operation_is_audited_without_secrets(self):
    res = self.client.get("/api/employees", headers=self.read_headers)
    self.assertEqual(res.status_code, 200)

    logs = self._all_audit_logs()
    matching = [
        l for l in logs
        if l["endpoint"] == "/api/employees" and l["http_method"] == "GET"
    ]
    self.assertTrue(matching)
    entry = matching[-1]
    self.assertEqual(entry["event_type"], "api_call")
    self.assertEqual(entry["status_code"], 200)
    self.assertEqual(entry["permission"], "read")

  def test_write_operation_is_audited(self):
    res = self.client.post(
        "/api/employees", json={"name": "監査テスト社員"},
        headers=self.write_headers,
    )
    self.assertEqual(res.status_code, 201)

    logs = self._all_audit_logs()
    matching = [
        l for l in logs
        if l["endpoint"] == "/api/employees" and l["http_method"] == "POST"
    ]
    self.assertTrue(matching)
    entry = matching[-1]
    self.assertEqual(entry["event_type"], "api_call")
    self.assertEqual(entry["status_code"], 201)
    self.assertEqual(entry["permission"], "write")
    self.assertIn("id=", entry["result_summary"])
    # 氏名などのリクエスト本文の値は要約に含まれない。
    self.assertNotIn("監査テスト社員", entry["result_summary"])

  def test_admin_only_operation_is_audited_as_admin_operation(self):
    emp = self.client.post(
        "/api/employees", json={"name": "admin監査発行者"},
        headers=self.admin_headers,
    ).get_json()["data"]
    mission = self.client.post(
        "/api/missions",
        json={"title": "admin監査MISSION", "issued_by": emp["id"]},
        headers=self.admin_headers,
    ).get_json()["data"]
    proposal = self.client.post(
        "/api/proposals",
        json={
            "mission_id": mission["id"], "proposed_by": emp["id"],
            "title": "admin監査提案",
        },
        headers=self.admin_headers,
    ).get_json()["data"]

    res = self.client.patch(
        f"/api/proposals/{proposal['id']}",
        json={"status": "approved"},
        headers=self.admin_headers,
    )
    self.assertEqual(res.status_code, 200)

    logs = self._all_audit_logs()
    matching = [
        l for l in logs
        if l["endpoint"] == f"/api/proposals/{proposal['id']}"
        and l["http_method"] == "PATCH"
    ]
    self.assertTrue(matching)
    entry = matching[-1]
    self.assertEqual(entry["event_type"], "admin_operation")
    self.assertEqual(entry["status_code"], 200)
    self.assertEqual(entry["permission"], "admin")

  def test_auth_denied_and_permission_denied_are_audited(self):
    res = self.client.get("/api/employees")
    self.assertEqual(res.status_code, 401)

    res = self.client.post(
        "/api/employees", json={"name": "x"}, headers=self.read_headers
    )
    self.assertEqual(res.status_code, 403)

    logs = self._all_audit_logs()
    self.assertTrue(any(l["event_type"] == "auth_denied" and l["status_code"] == 401 for l in logs))
    self.assertTrue(any(l["event_type"] == "permission_denied" and l["status_code"] == 403 for l in logs))

  def test_audit_log_never_contains_tokens_or_headers(self):
    self.client.get("/api/employees", headers=self.read_headers)
    self.client.post(
        "/api/employees", json={"name": "秘密情報混入確認用"},
        headers=self.write_headers,
    )
    self.client.get("/api/employees")  # 401
    self.client.post(
        "/api/employees", json={"name": "x"}, headers=self.read_headers
    )  # 403

    logs = self._all_audit_logs()
    self.assertTrue(logs)
    dump = str(logs)
    # 実トークンの値そのものが漏れていないことが本質的な確認事項。
    # ("Authorization"という語自体はエラーメッセージの一般的な説明文に
    # 現れうるが、ヘッダーの値そのものではないため許容する。)
    for secret in (TEST_READ_TOKEN, TEST_WRITE_TOKEN, TEST_ADMIN_TOKEN):
      self.assertNotIn(secret, dump)
    self.assertNotIn(f"Bearer {TEST_READ_TOKEN}", dump)
    self.assertNotIn(f"Bearer {TEST_WRITE_TOKEN}", dump)
    self.assertNotIn(f"Bearer {TEST_ADMIN_TOKEN}", dump)

  # --- MISSION 013: レート制限 ---------------------------------------------

  def test_rate_limit_exceeded_returns_429_then_recovers_after_reset(self):
    original_limits = dict(hive_db.RATE_LIMITS)
    hive_db.RATE_LIMITS["read"] = (2, 60)
    try:
      res1 = self.client.get("/api/employees", headers=self.read_headers)
      res2 = self.client.get("/api/employees", headers=self.read_headers)
      res3 = self.client.get("/api/employees", headers=self.read_headers)
      self.assertEqual(res1.status_code, 200)
      self.assertEqual(res2.status_code, 200)
      self.assertEqual(res3.status_code, 429)
      self.assertEqual(res3.get_json()["status"], "error")

      logs = self._all_audit_logs()
      self.assertTrue(any(l["event_type"] == "rate_limited" and l["status_code"] == 429 for l in logs))

      # テスト用の安全なリセット後は正常な操作に戻る。
      hive_db.reset_rate_limits()
      res4 = self.client.get("/api/employees", headers=self.read_headers)
      self.assertEqual(res4.status_code, 200)
    finally:
      hive_db.RATE_LIMITS.clear()
      hive_db.RATE_LIMITS.update(original_limits)
      hive_db.reset_rate_limits()

  def test_rate_limit_does_not_apply_to_existing_routes(self):
    original_limits = dict(hive_db.RATE_LIMITS)
    hive_db.RATE_LIMITS["read"] = (1, 60)
    try:
      self.client.get("/api/employees", headers=self.read_headers)
      # read枠を使い切った状態でも、既存 GET / ・GET /api/logs は無関係に
      # 動作し続ける。
      for _ in range(3):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/logs")
        self.assertEqual(res.status_code, 200)
    finally:
      hive_db.RATE_LIMITS.clear()
      hive_db.RATE_LIMITS.update(original_limits)
      hive_db.reset_rate_limits()

  # --- MISSION 013: 監査ログの保持整理 -------------------------------------

  def test_prune_audit_logs_removes_only_old_rows_from_audit_logs(self):
    conn = hive_db.get_connection()
    conn.execute(
        "INSERT INTO audit_logs"
        " (recorded_at, event_type, http_method, endpoint, status_code,"
        "  permission, result_summary)"
        " VALUES (datetime('now','localtime','-40 days'), 'api_call', 'GET',"
        "  '/api/employees', 200, 'read', 'old row for pruning test')"
    )
    conn.commit()
    conn.close()

    work_logs_count_before = self._work_logs_count()

    hive_db.prune_audit_logs()

    conn = hive_db.get_connection()
    remaining = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE result_summary = 'old row for pruning test'"
    ).fetchone()[0]
    conn.close()
    self.assertEqual(remaining, 0)

    self.assertEqual(self._work_logs_count(), work_logs_count_before)

  def _work_logs_count(self):
    conn = hive_db.get_connection()
    count = conn.execute("SELECT COUNT(*) FROM work_logs").fetchone()[0]
    conn.close()
    return count

  def test_prune_audit_logs_caps_row_count_without_touching_other_tables(self):
    conn = hive_db.get_connection()
    for i in range(10):
      conn.execute(
          "INSERT INTO audit_logs"
          " (event_type, http_method, endpoint, status_code, permission,"
          "  result_summary)"
          " VALUES ('api_call', 'GET', '/api/employees', 200, 'read', ?)",
          (f"row {i}",),
      )
    conn.commit()
    conn.close()

    employees_before = hive_db.list_rows("employees")
    work_logs_before = self._work_logs_count()

    original_max_rows = hive_db.AUDIT_LOG_MAX_ROWS
    hive_db.AUDIT_LOG_MAX_ROWS = 3
    try:
      hive_db.prune_audit_logs()
      conn = hive_db.get_connection()
      total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
      conn.close()
      self.assertLessEqual(total, 3)
    finally:
      hive_db.AUDIT_LOG_MAX_ROWS = original_max_rows

    self.assertEqual(hive_db.list_rows("employees"), employees_before)
    self.assertEqual(self._work_logs_count(), work_logs_before)

  # --- MISSION 013(修正): 監査記録時の自動整理 -----------------------------

  def _insert_raw_audit_log(self, recorded_at_sql, marker):
    conn = hive_db.get_connection()
    conn.execute(
        "INSERT INTO audit_logs"
        " (recorded_at, event_type, http_method, endpoint, status_code,"
        "  permission, result_summary)"
        " VALUES (datetime('now','localtime',?), 'api_call', 'GET',"
        "  '/api/employees', 200, 'read', ?)",
        (recorded_at_sql, marker),
    )
    conn.commit()
    conn.close()

  def test_old_audit_log_is_pruned_automatically_on_next_event(self):
    self._insert_raw_audit_log("-40 days", "old-row-for-auto-prune-test")

    conn = hive_db.get_connection()
    before = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE result_summary = ?",
        ("old-row-for-auto-prune-test",),
    ).fetchone()[0]
    conn.close()
    self.assertEqual(before, 1)

    # 通常のHive API呼び出し(=_record_audit_logの発火)だけで、明示的な
    # prune_audit_logs()呼び出しなしに古い記録が自動整理されるはず。
    res = self.client.get("/api/employees", headers=self.read_headers)
    self.assertEqual(res.status_code, 200)

    conn = hive_db.get_connection()
    after = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE result_summary = ?",
        ("old-row-for-auto-prune-test",),
    ).fetchone()[0]
    newest = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE endpoint = '/api/employees'"
        " AND http_method = 'GET' AND status_code = 200"
    ).fetchone()[0]
    conn.close()
    self.assertEqual(after, 0)
    self.assertGreaterEqual(newest, 1)

  def test_excess_audit_logs_beyond_cap_are_pruned_automatically(self):
    original_max_rows = hive_db.AUDIT_LOG_MAX_ROWS
    hive_db.AUDIT_LOG_MAX_ROWS = 3
    try:
      for i in range(5):
        self._insert_raw_audit_log("+0 seconds", f"pre-existing-row-{i}")

      conn = hive_db.get_connection()
      total_before = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
      conn.close()
      self.assertEqual(total_before, 5)

      # 明示的なprune呼び出しなしに、次の監査イベント(このAPI呼び出し)で
      # 自動的に上限まで整理されるはず。
      res = self.client.get("/api/employees", headers=self.read_headers)
      self.assertEqual(res.status_code, 200)

      conn = hive_db.get_connection()
      total_after = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
      newest_row = conn.execute(
          "SELECT result_summary FROM audit_logs ORDER BY id DESC LIMIT 1"
      ).fetchone()[0]
      conn.close()
      self.assertLessEqual(total_after, hive_db.AUDIT_LOG_MAX_ROWS)
      # 直近の記録(今回のAPI呼び出し由来)は整理後も残っている。
      self.assertNotIn("pre-existing-row-", newest_row)
    finally:
      hive_db.AUDIT_LOG_MAX_ROWS = original_max_rows

  def test_automatic_prune_does_not_touch_other_tables(self):
    self._insert_raw_audit_log("-40 days", "old-row-isolation-check")

    employees_before = hive_db.list_rows("employees")
    missions_before = hive_db.list_rows("missions")
    work_logs_before = self._work_logs_count()

    res = self.client.post(
        "/api/employees", json={"name": "自動整理副作用確認用"},
        headers=self.write_headers,
    )
    self.assertEqual(res.status_code, 201)
    created_id = res.get_json()["data"]["id"]

    # employees/missionsは今回のAPI呼び出し由来の増分のみを許容し、
    # それ以外の意図しない変更が起きていないことを確認する。
    employees_after = hive_db.list_rows("employees")
    self.assertEqual(len(employees_after), len(employees_before) + 1)
    self.assertTrue(any(e["id"] == created_id for e in employees_after))
    self.assertEqual(hive_db.list_rows("missions"), missions_before)
    self.assertEqual(self._work_logs_count(), work_logs_before)

  def test_explicit_prune_function_still_available_for_maintenance(self):
    # 明示的に呼び出す既存の整理関数も、保守・テスト目的で引き続き利用できる。
    self._insert_raw_audit_log("-40 days", "old-row-for-explicit-call")
    hive_db.prune_audit_logs()
    conn = hive_db.get_connection()
    remaining = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE result_summary = ?",
        ("old-row-for-explicit-call",),
    ).fetchone()[0]
    conn.close()
    self.assertEqual(remaining, 0)


if __name__ == "__main__":
  unittest.main()
