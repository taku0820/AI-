"""hive_ops.py（MISSION 019 日常運用保守CLI）の単体テスト。

このテストは実際のFlaskサーバー・実ネットワークには一切接続しない。
hive_status._open_url をモックに差し替えてHTTPチェック部分を、
一時ディレクトリ内のDB・バックアップコピーで hive_backup 部分を検証する。
本番の `ai_company.db`・プロジェクト内 `backups/` には一切書き込まない。

実行方法: venv/bin/python test_hive_ops.py
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
import urllib.error

import hive_backup
import hive_ops
import hive_status

PROJECT_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_company.db")
TEST_TOKEN = "mission019-test-token-should-never-appear-in-output"


class _FakeResponse:
  def __init__(self, status, body_text):
    self.status = status
    self._body = body_text.encode("utf-8")

  def read(self):
    return self._body

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    return False


def _fake_open_ok(req):
  if "api/logs" in req.full_url:
    return _FakeResponse(200, "[]")
  return _FakeResponse(200, "<html>会社の全体像ダッシュボード</html>")


class HiveOpsTestCase(unittest.TestCase):

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_ops_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

    self._orig_status_db_name = hive_status.DB_NAME
    self._orig_open_url = hive_status._open_url
    self._orig_backups_root = hive_backup.BACKUPS_ROOT

    hive_status.DB_NAME = self.source_db
    hive_status._open_url = _fake_open_ok
    hive_backup.BACKUPS_ROOT = self.backups_root

  def tearDown(self):
    hive_status.DB_NAME = self._orig_status_db_name
    hive_status._open_url = self._orig_open_url
    hive_backup.BACKUPS_ROOT = self._orig_backups_root
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_ops.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def _source_hash(self):
    return hive_backup._sha256_of_file(self.source_db)

  # --- 状態確認のみ(--verify-backupなし) --------------------------------------

  def test_status_only_ok(self):
    code, out, _err = self._run_main([])
    self.assertEqual(code, 0)
    self.assertIn("root_page", out)
    self.assertIn("logs_api", out)
    self.assertIn("database", out)
    self.assertNotIn("backup_verify", out)
    self.assertIn("総合判定: OK", out)

  def test_status_only_ng_when_db_missing(self):
    hive_status.DB_NAME = os.path.join(self.tmp_root, "does_not_exist.db")
    code, out, _err = self._run_main([])
    self.assertEqual(code, 1)
    self.assertIn("総合判定: NG", out)

  def test_status_only_ng_on_connection_failure(self):
    def fake_open(req):
      raise urllib.error.URLError("connection refused")

    hive_status._open_url = fake_open
    code, out, _err = self._run_main([])
    self.assertEqual(code, 1)
    self.assertIn("総合判定: NG", out)

  # --- --verify-backup あり ---------------------------------------------------

  def test_verify_backup_included_and_ok(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    code, out, _err = self._run_main(["--verify-backup", created["backup_dir"]])
    self.assertEqual(code, 0)
    self.assertIn("backup_verify", out)
    self.assertIn("root_page", out)  # 状態確認も引き続き含まれる
    self.assertIn("総合判定: OK", out)

  def test_verify_backup_failure_causes_overall_ng_without_crash(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    with open(created["backup_db_path"], "r+b") as f:
      f.seek(50)
      original = f.read(1)
      f.seek(50)
      f.write(bytes([original[0] ^ 0xFF]))

    code, out, _err = self._run_main(["--verify-backup", created["backup_dir"]])
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)
    self.assertIn("総合判定: NG", out)

  def test_verify_backup_rejects_path_outside_backups_root_safely(self):
    outside_dir = os.path.join(self.tmp_root, "not_a_backup")
    os.makedirs(outside_dir, exist_ok=True)
    code, out, _err = self._run_main(["--verify-backup", outside_dir])
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)
    self.assertIn("総合判定: NG", out)

  def test_verify_backup_missing_path_fails_safely(self):
    os.makedirs(self.backups_root, exist_ok=True)
    missing = os.path.join(self.backups_root, "backup_does_not_exist")
    code, out, _err = self._run_main(["--verify-backup", missing])
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)

  # --- 新規作成・復元を行わないことの確認 --------------------------------------

  def test_does_not_create_or_restore_backups(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )

    def fail_if_called(*args, **kwargs):
      self.fail("hive_ops.py が create_backup/restore_test を呼び出した")

    orig_create = hive_backup.create_backup
    orig_restore = hive_backup.restore_test
    hive_backup.create_backup = fail_if_called
    hive_backup.restore_test = fail_if_called
    try:
      code, _out, _err = self._run_main(
          ["--verify-backup", created["backup_dir"]]
      )
      self.assertEqual(code, 0)
    finally:
      hive_backup.create_backup = orig_create
      hive_backup.restore_test = orig_restore

  # --- 副作用ゼロ・トークン非漏洩 ----------------------------------------------

  def test_source_db_and_backup_unchanged_after_run(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    source_hash_before = self._source_hash()
    backup_hash_before = hive_backup._sha256_of_file(created["backup_db_path"])

    self._run_main(["--verify-backup", created["backup_dir"]])

    self.assertEqual(self._source_hash(), source_hash_before)
    self.assertEqual(
        hive_backup._sha256_of_file(created["backup_db_path"]), backup_hash_before
    )

  def test_output_never_contains_token_values(self):
    orig_env_val = os.environ.get("AI_HIVE_ADMIN_TOKEN")
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_TOKEN
    try:
      code, out, err = self._run_main([])
      self.assertEqual(code, 0)
      self.assertNotIn(TEST_TOKEN, out)
      self.assertNotIn(TEST_TOKEN, err)
    finally:
      if orig_env_val is None:
        os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)
      else:
        os.environ["AI_HIVE_ADMIN_TOKEN"] = orig_env_val

  # --- 表示の一貫性 ------------------------------------------------------------

  def test_report_format_is_consistent_with_and_without_backup(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    _code1, out_status_only, _err1 = self._run_main([])
    _code2, out_with_backup, _err2 = self._run_main(
        ["--verify-backup", created["backup_dir"]]
    )
    for marker in ("root_page", "logs_api", "database", "総合判定:"):
      self.assertIn(marker, out_status_only)
      self.assertIn(marker, out_with_backup)
    self.assertNotIn("backup_verify", out_status_only)
    self.assertIn("backup_verify", out_with_backup)

  # --- CLI引数の安全性 ---------------------------------------------------------

  def test_cli_rejects_unexpected_positional_argument(self):
    with self.assertRaises(SystemExit):
      self._run_main(["some-unexpected-positional"])


if __name__ == "__main__":
  unittest.main()
