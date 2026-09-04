"""hive_status.py（MISSION 018 読み取り専用ヘルスチェックCLI）の単体テスト。

このテストは実際のFlaskサーバー・実ネットワークには一切接続しない。
hive_status._open_url（実HTTP通信を行う唯一の境界関数）をモックに
差し替えてHTTPチェックを検証する。DBチェックは、プロジェクトの
`ai_company.db` を一時ファイルへコピーしたものに対してのみ行い、
本番DB・プロジェクト内の `backups/` には一切書き込まない。

実行方法: venv/bin/python test_hive_status.py
"""

import contextlib
import io
import os
import shutil
import sqlite3
import tempfile
import unittest
import urllib.error

import hive_status

PROJECT_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_company.db")
TEST_TOKEN = "mission018-test-token-should-never-appear-in-output"


class _FakeResponse:
  """urllib.request.urlopenの戻り値(with文で使うレスポンス)を模したダミー。"""

  def __init__(self, status, body_text):
    self.status = status
    self._body = body_text.encode("utf-8")

  def read(self):
    return self._body

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    return False


def _make_http_error(url, code, body_text):
  fp = io.BytesIO(body_text.encode("utf-8"))
  return urllib.error.HTTPError(url, code, "error", {}, fp)


class HttpChecksTestCase(unittest.TestCase):
  """GET / ・GET /api/logs のHTTPチェック(モック通信)のテスト。"""

  def setUp(self):
    self._orig_open_url = hive_status._open_url

  def tearDown(self):
    hive_status._open_url = self._orig_open_url

  def test_root_page_ok_when_dashboard_html_returned(self):
    hive_status._open_url = lambda req: _FakeResponse(
        200, "<html>会社の全体像ダッシュボード</html>"
    )
    result = hive_status.check_root_page()
    self.assertTrue(result["ok"])
    self.assertIn("200", result["detail"])

  def test_root_page_ng_on_unexpected_status(self):
    hive_status._open_url = lambda req: _FakeResponse(500, "internal error")
    result = hive_status.check_root_page()
    self.assertFalse(result["ok"])
    self.assertIn("500", result["detail"])

  def test_root_page_ng_on_unexpected_content(self):
    hive_status._open_url = lambda req: _FakeResponse(200, "<html>別サービス</html>")
    result = hive_status.check_root_page()
    self.assertFalse(result["ok"])

  def test_root_page_ng_on_connection_failure(self):
    def fake_open(req):
      raise urllib.error.URLError("connection refused")

    hive_status._open_url = fake_open
    result = hive_status.check_root_page()
    self.assertFalse(result["ok"])
    self.assertIn(hive_status.BASE_URL, result["detail"])

  def test_root_page_does_not_follow_redirects(self):
    def raising_redirect(req):
      handler = hive_status._NoRedirectHandler()
      handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example/")

    hive_status._open_url = raising_redirect
    result = hive_status.check_root_page()
    self.assertFalse(result["ok"])
    self.assertIn("リダイレクト", result["detail"])

  def test_logs_api_ok_when_json_array_returned(self):
    hive_status._open_url = lambda req: _FakeResponse(
        200, '[[1, "t", "theme", "content", "done"]]'
    )
    result = hive_status.check_logs_api()
    self.assertTrue(result["ok"])
    self.assertIn("1件", result["detail"])

  def test_logs_api_ng_on_malformed_json(self):
    hive_status._open_url = lambda req: _FakeResponse(200, "not json{{{")
    result = hive_status.check_logs_api()
    self.assertFalse(result["ok"])
    self.assertIn("JSON", result["detail"])

  def test_logs_api_ng_on_non_array_json(self):
    hive_status._open_url = lambda req: _FakeResponse(200, '{"status": "success"}')
    result = hive_status.check_logs_api()
    self.assertFalse(result["ok"])

  def test_logs_api_ng_on_http_error_status(self):
    def fake_open(req):
      raise _make_http_error(req.full_url, 404, "not found")

    hive_status._open_url = fake_open
    result = hive_status.check_logs_api()
    self.assertFalse(result["ok"])
    self.assertIn("404", result["detail"])

  def test_http_checks_only_target_fixed_base_url(self):
    captured = []

    def fake_open(req):
      captured.append(req.full_url)
      return _FakeResponse(200, "[]")

    hive_status._open_url = fake_open
    hive_status.check_logs_api()
    self.assertTrue(captured[0].startswith(hive_status.BASE_URL))
    self.assertEqual(hive_status.BASE_URL, "http://127.0.0.1:5050")

  def test_http_checks_send_no_authorization_header(self):
    captured = {}

    def fake_open(req):
      captured["req"] = req
      return _FakeResponse(200, "[]")

    hive_status._open_url = fake_open
    hive_status.check_logs_api()
    self.assertIsNone(captured["req"].get_header("Authorization"))


class DatabaseCheckTestCase(unittest.TestCase):
  """check_database()のテスト。一時コピーのDBのみを対象とする。"""

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_status_test_")
    self.db_path = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.db_path)

  def tearDown(self):
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _hash(self, path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as f:
      digest.update(f.read())
    return digest.hexdigest()

  def test_database_ok_for_valid_copy(self):
    result = hive_status.check_database(db_path=self.db_path)
    self.assertTrue(result["ok"])
    self.assertIn("work_logs", result["table_row_counts"])
    self.assertIn("audit_logs", result["table_row_counts"])
    self.assertIn("employees", result["table_row_counts"])

  def test_database_check_is_read_only_and_does_not_modify_file(self):
    hash_before = self._hash(self.db_path)
    hive_status.check_database(db_path=self.db_path)
    self.assertEqual(self._hash(self.db_path), hash_before)

  def test_database_ng_when_file_missing(self):
    missing = os.path.join(self.tmp_root, "does_not_exist.db")
    result = hive_status.check_database(db_path=missing)
    self.assertFalse(result["ok"])
    self.assertIn("見つかりません", result["detail"])

  def test_database_ng_when_file_is_corrupted(self):
    with open(self.db_path, "r+b") as f:
      f.seek(100)
      original = f.read(1)
      f.seek(100)
      f.write(bytes([original[0] ^ 0xFF]))

    # 破損ファイルへのチェックが例外で落ちず、NGとして安全に返ることを
    # 確認する(hive_backup.pyの同種の不具合修正と同じ観点)。
    result = hive_status.check_database(db_path=self.db_path)
    self.assertFalse(result["ok"])

  def test_database_ng_when_expected_table_missing(self):
    conn = sqlite3.connect(self.db_path)
    conn.execute("DROP TABLE audit_logs")
    conn.commit()
    conn.close()

    result = hive_status.check_database(db_path=self.db_path)
    self.assertFalse(result["ok"])
    self.assertIn("audit_logs", result["detail"])

  def test_production_db_unaffected_by_running_check_against_it(self):
    # 本番DBに対して直接check_database()を実行しても、読み取り専用
    # 接続のため一切変更されないことを確認する(ハッシュ比較)。
    prod_hash_before = self._hash(PROJECT_DB_PATH)
    result = hive_status.check_database(db_path=PROJECT_DB_PATH)
    self.assertTrue(result["ok"])
    self.assertEqual(self._hash(PROJECT_DB_PATH), prod_hash_before)


class TokenEnvPresenceTestCase(unittest.TestCase):

  def test_reports_presence_without_leaking_values(self):
    env = {
        "AI_HIVE_READ_TOKEN": TEST_TOKEN,
        "AI_HIVE_WRITE_TOKEN": TEST_TOKEN,
        "AI_HIVE_ADMIN_TOKEN": TEST_TOKEN,
    }
    result = hive_status.check_token_env_presence(env=env)
    self.assertTrue(result["ok"])
    self.assertNotIn(TEST_TOKEN, result["detail"])
    self.assertNotIn(TEST_TOKEN, str(result))

  def test_reports_missing_vars_as_not_ok(self):
    result = hive_status.check_token_env_presence(env={})
    self.assertFalse(result["ok"])
    self.assertIn("未設定", result["detail"])

  def test_token_env_presence_is_marked_non_critical(self):
    # token_env_presenceは参考情報であり、総合判定(overall_ok)には
    # 含めない設計であることをコード上でも確認する。
    result = hive_status.check_token_env_presence(env={})
    self.assertFalse(result["ok"])
    self.assertFalse(result.get("critical", True))

  def test_partial_presence_is_reported_accurately(self):
    env = {"AI_HIVE_READ_TOKEN": TEST_TOKEN}
    result = hive_status.check_token_env_presence(env=env)
    self.assertFalse(result["ok"])
    self.assertIn("AI_HIVE_READ_TOKEN=設定済み", result["detail"])
    self.assertIn("AI_HIVE_WRITE_TOKEN=未設定", result["detail"])
    self.assertNotIn(TEST_TOKEN, result["detail"])


class RunAllChecksAndCliTestCase(unittest.TestCase):

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_status_cli_test_")
    self.db_path = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.db_path)
    self._orig_open_url = hive_status._open_url

  def tearDown(self):
    hive_status._open_url = self._orig_open_url
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_status.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def test_run_all_checks_ok_end_to_end(self):
    hive_status._open_url = lambda req: _FakeResponse(
        200,
        "[]" if "api/logs" in req.full_url
        else "<html>会社の全体像ダッシュボード</html>",
    )
    results = hive_status.run_all_checks(
        db_path=self.db_path,
        env={
            "AI_HIVE_READ_TOKEN": "x",
            "AI_HIVE_WRITE_TOKEN": "x",
            "AI_HIVE_ADMIN_TOKEN": "x",
        },
    )
    self.assertTrue(all(r["ok"] for r in results))

  def test_cli_exit_code_reflects_overall_status(self):
    orig_db_name = hive_status.DB_NAME
    hive_status.DB_NAME = self.db_path
    hive_status._open_url = lambda req: _FakeResponse(
        200,
        "[]" if "api/logs" in req.full_url
        else "<html>会社の全体像ダッシュボード</html>",
    )
    try:
      code, out, _err = self._run_main([])
      self.assertEqual(code, 0)
      self.assertIn("総合判定: OK", out)
    finally:
      hive_status.DB_NAME = orig_db_name

  def test_cli_reports_ng_and_nonzero_exit_on_connection_failure(self):
    orig_db_name = hive_status.DB_NAME
    hive_status.DB_NAME = self.db_path
    hive_status._open_url = lambda req: (_ for _ in ()).throw(
        urllib.error.URLError("connection refused")
    )
    try:
      code, out, _err = self._run_main([])
      self.assertEqual(code, 1)
      self.assertIn("総合判定: NG", out)
    finally:
      hive_status.DB_NAME = orig_db_name

  def test_cli_output_never_contains_token_values(self):
    orig_db_name = hive_status.DB_NAME
    hive_status.DB_NAME = self.db_path
    hive_status._open_url = lambda req: _FakeResponse(
        200,
        "[]" if "api/logs" in req.full_url
        else "<html>会社の全体像ダッシュボード</html>",
    )
    orig_env_val = os.environ.get("AI_HIVE_ADMIN_TOKEN")
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_TOKEN
    try:
      code, out, err = self._run_main([])
      self.assertEqual(code, 0)
      self.assertNotIn(TEST_TOKEN, out)
      self.assertNotIn(TEST_TOKEN, err)
    finally:
      hive_status.DB_NAME = orig_db_name
      if orig_env_val is None:
        os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)
      else:
        os.environ["AI_HIVE_ADMIN_TOKEN"] = orig_env_val

  def test_cli_rejects_unexpected_arguments(self):
    with self.assertRaises(SystemExit):
      self._run_main(["--base-url", "http://example.com"])


if __name__ == "__main__":
  unittest.main()
