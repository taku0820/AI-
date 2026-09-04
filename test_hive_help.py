"""hive_help.py（MISSION 022 統合ヘルプ／ナビゲーションCLI）の単体テスト。

このテストは実際のFlaskサーバー・実ネットワークには一切接続しない。
hive_status._open_url をモックに差し替えてHTTPチェック部分を、
一時ディレクトリ内のDB・バックアップコピーで hive_backup 部分を検証する。
本番の `ai_company.db`・プロジェクト内 `backups/` には一切書き込まない。

hive_help.py はディスパッチャに過ぎないため、ここでは主に
「引数なし・--help・admin-infoでは何も実行されないこと」「各サブコマンドが
対応するモジュールの正しい機能を正しい引数で呼び出すこと」を確認する。
各機能そのものの詳細な単体テストは test_hive_status.py・test_hive_ops.py・
test_hive_backup.py に既にある。

実行方法: venv/bin/python test_hive_help.py
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
import urllib.error

import hive_backup
import hive_help
import hive_ops
import hive_status

PROJECT_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_company.db")
TEST_TOKEN = "mission022-test-token-should-never-appear-in-output"


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


def _fake_open_url_ok(req):
  if "api/logs" in req.full_url:
    return _FakeResponse(200, "[]")
  return _FakeResponse(200, "<html>会社の全体像ダッシュボード</html>")


class HiveHelpNoActionTestCase(unittest.TestCase):
  """引数なし・--help・admin-infoでは、いかなる操作も実行されないことの確認。"""

  def setUp(self):
    self._orig_status_open_url = hive_status._open_url
    self._orig_status_db_name = hive_status.DB_NAME

    def fail_if_network_called(req):
      self.fail("ネットワーク通信が発生した(引数なし/help/admin-infoのはず)")

    hive_status._open_url = fail_if_network_called

  def tearDown(self):
    hive_status._open_url = self._orig_status_open_url
    hive_status.DB_NAME = self._orig_status_db_name

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_help.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def test_no_args_shows_menu_without_any_action(self):
    code, out, _err = self._run_main([])
    self.assertEqual(code, 0)
    self.assertIn("何も実行していません", out)
    self.assertIn("status", out)
    self.assertIn("backup-list", out)
    self.assertIn("backup-verify", out)
    self.assertIn("admin-info", out)

  def test_help_flag_shows_usage_without_any_action(self):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
      with self.assertRaises(SystemExit) as cm:
        hive_help.main(["--help"])
    self.assertEqual(cm.exception.code, 0)
    self.assertIn("hive_help.py", stdout.getvalue())

  def test_admin_info_prints_guidance_without_calling_hive_admin(self):
    code, out, _err = self._run_main(["admin-info"])
    self.assertEqual(code, 0)
    self.assertIn("hive_admin.py", out)
    self.assertIn("audit_logs", out)
    self.assertIn("別途", out)

  def test_admin_info_never_touches_network_or_env(self):
    # admin-infoは案内文の表示のみであり、トークンの有無すら確認しない。
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_TOKEN
    try:
      code, out, err = self._run_main(["admin-info"])
      self.assertEqual(code, 0)
      self.assertNotIn(TEST_TOKEN, out)
      self.assertNotIn(TEST_TOKEN, err)
    finally:
      os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)


class HiveHelpDispatchTestCase(unittest.TestCase):
  """各サブコマンドが正しいモジュール・引数を呼び出すことの確認。"""

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_help_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

    self._orig_status_db_name = hive_status.DB_NAME
    self._orig_status_open_url = hive_status._open_url
    self._orig_backups_root = hive_backup.BACKUPS_ROOT

    hive_status.DB_NAME = self.source_db
    hive_status._open_url = _fake_open_url_ok
    hive_backup.BACKUPS_ROOT = self.backups_root

  def tearDown(self):
    hive_status.DB_NAME = self._orig_status_db_name
    hive_status._open_url = self._orig_status_open_url
    hive_backup.BACKUPS_ROOT = self._orig_backups_root
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_help.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def test_status_subcommand_runs_hive_status(self):
    code, out, _err = self._run_main(["status"])
    self.assertEqual(code, 0)
    self.assertIn("root_page", out)
    self.assertIn("logs_api", out)
    self.assertIn("database", out)
    self.assertIn("総合判定: OK", out)

  def test_status_subcommand_reflects_failure(self):
    def fake_open(req):
      raise urllib.error.URLError("connection refused")

    hive_status._open_url = fake_open
    code, out, _err = self._run_main(["status"])
    self.assertEqual(code, 1)
    self.assertIn("総合判定: NG", out)

  def test_ops_subcommand_without_backup_runs_status_only(self):
    code, out, _err = self._run_main(["ops"])
    self.assertEqual(code, 0)
    self.assertIn("root_page", out)
    self.assertNotIn("backup_verify", out)
    self.assertIn("総合判定: OK", out)

  def test_ops_subcommand_with_backup_includes_backup_verify(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    code, out, _err = self._run_main(
        ["ops", "--verify-backup", created["backup_dir"]]
    )
    self.assertEqual(code, 0)
    self.assertIn("backup_verify", out)
    self.assertIn("総合判定: OK", out)

  def test_backup_list_subcommand_runs_hive_backup_list(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    code, out, _err = self._run_main(["backup-list"])
    self.assertEqual(code, 0)
    self.assertIn(os.path.basename(created["backup_dir"]), out)
    self.assertIn("バックアップ一覧", out)

  def test_backup_list_subcommand_reports_empty(self):
    code, out, _err = self._run_main(["backup-list"])
    self.assertEqual(code, 0)
    self.assertIn("見つかりません", out)

  def test_backup_verify_subcommand_ok(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    code, out, _err = self._run_main(["backup-verify", created["backup_dir"]])
    self.assertEqual(code, 0)
    self.assertIn("総合判定: OK", out)

  def test_backup_verify_subcommand_rejects_path_outside_backups_root(self):
    outside_dir = os.path.join(self.tmp_root, "not_a_backup")
    os.makedirs(outside_dir, exist_ok=True)
    code, _out, err = self._run_main(["backup-verify", outside_dir])
    self.assertEqual(code, 1)
    self.assertIn("エラー", err)

  def test_backup_verify_subcommand_rejects_tampered_backup(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    with open(created["backup_db_path"], "r+b") as f:
      f.seek(50)
      original = f.read(1)
      f.seek(50)
      f.write(bytes([original[0] ^ 0xFF]))

    code, out, _err = self._run_main(["backup-verify", created["backup_dir"]])
    self.assertEqual(code, 1)
    self.assertIn("総合判定: NG", out)

  # --- hive_adminを一切呼び出さないことの確認 ---------------------------------

  def test_no_subcommand_ever_calls_hive_admin_module(self):
    # hive_help.pyはhive_adminをimportすらしていないことを確認する
    # (誤ってどこかで呼び出す経路が追加されていないことの裏付け)。
    self.assertNotIn("hive_admin", dir(hive_help))

  # --- 副作用ゼロ・トークン非漏洩 ----------------------------------------------

  def test_no_secrets_leak_across_all_subcommands(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_TOKEN
    try:
      outputs = []
      for argv in (
          [],
          ["status"],
          ["ops", "--verify-backup", created["backup_dir"]],
          ["backup-list"],
          ["backup-verify", created["backup_dir"]],
          ["admin-info"],
      ):
        _code, out, err = self._run_main(argv)
        outputs.append(out + err)
      combined = "".join(outputs)
      self.assertNotIn(TEST_TOKEN, combined)
    finally:
      os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)

  def test_source_db_and_backup_unchanged_after_all_subcommands(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    source_hash_before = hive_backup._sha256_of_file(self.source_db)
    backup_hash_before = hive_backup._sha256_of_file(created["backup_db_path"])

    for argv in (
        [],
        ["status"],
        ["ops", "--verify-backup", created["backup_dir"]],
        ["backup-list"],
        ["backup-verify", created["backup_dir"]],
        ["admin-info"],
    ):
      self._run_main(argv)

    self.assertEqual(hive_backup._sha256_of_file(self.source_db), source_hash_before)
    self.assertEqual(
        hive_backup._sha256_of_file(created["backup_db_path"]), backup_hash_before
    )

  def test_cli_rejects_unknown_subcommand(self):
    with self.assertRaises(SystemExit):
      self._run_main(["not-a-real-subcommand"])


if __name__ == "__main__":
  unittest.main()
