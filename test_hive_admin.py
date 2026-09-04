"""hive_admin.py（MISSION 015 監査ログ確認CLI）の単体テスト。

このテストは実際のFlaskサーバー・実ネットワーク・実DBには一切接続しない。
hive_admin._open_url（実HTTP通信を行う唯一の境界関数）をモックに差し替え、
CLIが「どのURL・メソッド・ヘッダーでリクエストを組み立てるか」「トークン
未設定・不正な件数指定のときにネットワーク通信を一切行わないか」「出力に
トークンの値が含まれないか」を検証する。

実行方法: venv/bin/python test_hive_admin.py
"""

import contextlib
import io
import os
import unittest
import urllib.error

import hive_admin

TEST_ADMIN_TOKEN = "mission015-test-admin-token"


class _FakeResponse:
  """urllib.request.urlopenの戻り値（with文で使うレスポンス）を模したダミー。"""

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


class HiveAdminCliTestCase(unittest.TestCase):

  def setUp(self):
    self._orig_token_env = os.environ.get(hive_admin.TOKEN_ENV_VAR)
    if hive_admin.TOKEN_ENV_VAR in os.environ:
      del os.environ[hive_admin.TOKEN_ENV_VAR]
    self._orig_open_url = hive_admin._open_url

  def tearDown(self):
    hive_admin._open_url = self._orig_open_url
    if self._orig_token_env is None:
      os.environ.pop(hive_admin.TOKEN_ENV_VAR, None)
    else:
      os.environ[hive_admin.TOKEN_ENV_VAR] = self._orig_token_env

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_admin.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  # --- ネットワーク通信を行わずに安全に失敗するケース -----------------------

  def test_missing_token_fails_without_network_call(self):
    calls = []
    hive_admin._open_url = lambda req: calls.append(req) or self.fail(
        "トークン未設定時にネットワーク通信が発生した"
    )

    code, _out, err = self._run_main([])
    self.assertEqual(code, 1)
    self.assertEqual(calls, [])
    self.assertIn(hive_admin.TOKEN_ENV_VAR, err)

  def test_invalid_limit_fails_without_network_call(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    for bad_value in ("0", "-1", "abc", "12.5", ""):
      calls = []
      hive_admin._open_url = lambda req: calls.append(req) or self.fail(
          f"不正なlimit({bad_value!r})でネットワーク通信が発生した"
      )
      code, _out, err = self._run_main(["--limit", bad_value])
      self.assertEqual(code, 1, msg=f"limit={bad_value!r}")
      self.assertEqual(calls, [])
      self.assertIn("limit", err)

  # --- リクエストの組み立て内容 ---------------------------------------------

  def test_default_limit_is_50(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    captured = {}

    def fake_open(req):
      captured["req"] = req
      return _FakeResponse(200, '{"status": "success", "data": []}')

    hive_admin._open_url = fake_open
    code, _out, _err = self._run_main([])
    self.assertEqual(code, 0)
    self.assertIn("limit=50", captured["req"].full_url)

  def test_limit_over_max_is_clamped_to_100(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    captured = {}

    def fake_open(req):
      captured["req"] = req
      return _FakeResponse(200, '{"status": "success", "data": []}')

    hive_admin._open_url = fake_open
    code, _out, _err = self._run_main(["--limit", "99999"])
    self.assertEqual(code, 0)
    self.assertIn("limit=100", captured["req"].full_url)

  def test_only_calls_fixed_localhost_audit_logs_endpoint(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    captured = {}

    def fake_open(req):
      captured["req"] = req
      return _FakeResponse(200, '{"status": "success", "data": []}')

    hive_admin._open_url = fake_open
    code, _out, _err = self._run_main(["--limit", "10"])
    self.assertEqual(code, 0)
    req = captured["req"]
    self.assertTrue(
        req.full_url.startswith(
            hive_admin.BASE_URL + hive_admin.AUDIT_LOGS_PATH
        )
    )
    self.assertEqual(req.get_method(), "GET")
    # BASE_URLは127.0.0.1:5050に固定されている。
    self.assertEqual(hive_admin.BASE_URL, "http://127.0.0.1:5050")

  def test_authorization_header_uses_env_token_as_bearer(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    captured = {}

    def fake_open(req):
      captured["req"] = req
      return _FakeResponse(200, '{"status": "success", "data": []}')

    hive_admin._open_url = fake_open
    self._run_main([])
    req = captured["req"]
    self.assertEqual(
        req.get_header("Authorization"), f"Bearer {TEST_ADMIN_TOKEN}"
    )

  # --- トークンが出力へ一切含まれないこと -----------------------------------

  def test_token_never_appears_in_stdout_on_success(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    hive_admin._open_url = lambda req: _FakeResponse(
        200,
        '{"status": "success", "data": [{"id": 1, "recorded_at": "x",'
        ' "event_type": "admin_operation", "http_method": "GET",'
        ' "endpoint": "/api/audit-logs", "status_code": 200,'
        ' "permission": "admin", "result_summary": "success count=0"}]}',
    )
    code, out, err = self._run_main([])
    self.assertEqual(code, 0)
    self.assertNotIn(TEST_ADMIN_TOKEN, out)
    self.assertNotIn(TEST_ADMIN_TOKEN, err)
    self.assertNotIn("Authorization", out)

  def test_token_never_appears_in_output_on_http_error_responses(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN
    for status_code, message in (
        (401, "認証に失敗しました。"),
        (403, "権限が不足しています。"),
        (429, "リクエストが多すぎます。しばらく待ってから再試行してください。"),
        (400, "limitは正の整数で指定してください。"),
    ):
      def fake_open(req, _status=status_code, _message=message):
        raise _make_http_error(
            req.full_url, _status,
            f'{{"status": "error", "message": "{_message}"}}',
        )

      hive_admin._open_url = fake_open
      code, out, err = self._run_main([])
      self.assertEqual(code, 1)
      self.assertIn(message, err)
      self.assertNotIn(TEST_ADMIN_TOKEN, out)
      self.assertNotIn(TEST_ADMIN_TOKEN, err)
      self.assertNotIn(f"Bearer {TEST_ADMIN_TOKEN}", out + err)

  def test_connection_failure_is_handled_safely_without_traceback(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN

    def fake_open(req):
      raise urllib.error.URLError("connection refused")

    hive_admin._open_url = fake_open
    code, out, err = self._run_main([])
    self.assertEqual(code, 1)
    self.assertNotIn(TEST_ADMIN_TOKEN, out)
    self.assertNotIn(TEST_ADMIN_TOKEN, err)
    self.assertIn(hive_admin.BASE_URL, err)

  def test_redirect_is_not_followed(self):
    os.environ[hive_admin.TOKEN_ENV_VAR] = TEST_ADMIN_TOKEN

    def raising_redirect_open(req):
      handler = hive_admin._NoRedirectHandler()
      handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example/")

    hive_admin._open_url = raising_redirect_open
    code, out, err = self._run_main([])
    self.assertEqual(code, 1)
    self.assertIn("リダイレクト", err)
    self.assertNotIn(TEST_ADMIN_TOKEN, out)
    self.assertNotIn(TEST_ADMIN_TOKEN, err)


if __name__ == "__main__":
  unittest.main()
