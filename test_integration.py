"""ローカル運用ツール群(hive_status.py / hive_backup.py / hive_ops.py /

hive_admin.py)の統合結合テスト（MISSION 020）。

個々のツールの単体テストは test_hive_status.py / test_hive_backup.py /
test_hive_ops.py / test_hive_admin.py に既にある。本ファイルはそれらを
「一連の運用ワークフロー」として繋げて動かし、ツール間で結果の一貫性が
保たれていること、破壊的シナリオ(改ざん・破損・サーバー停止・不正パス)
がどのツールを通しても一貫して安全に拒否されることを確認する。

安全方針(すべてのテストに共通):
  - 本番の `ai_company.db`・プロジェクト内の実 `backups/` ディレクトリ・
    `work_logs`・`audit_logs` は一切変更しない。対象DB・バックアップ先は
    すべて `tempfile` が作る一時ディレクトリ内のコピーを使う。
  - HTTP通信はすべてモック(`hive_status._open_url` / `hive_admin._open_url`
    の差し替え)で行い、実ネットワーク通信は一切発生しない。
  - バックアップの新規作成・復元・削除は、この統合テストの検証目的で
    一時領域に対してのみ行う(hive_backup.create_backup/restore_testを
    直接呼ぶのは、あくまで一時コピーが対象)。実DBへの復元は一切行わない
    （restore_testも常に一時領域にのみ復旧し、実DBには触れない）。
  - admin API・成功時に監査ログを書き込む新Hive APIは、実DBに対しては
    一切呼び出さない(呼び出す場合も常にモックしたHTTP層のみを対象とする)。
  - 実トークンは使わない。テスト専用のダミー文字列のみを使う。

実行方法: venv/bin/python test_integration.py
"""

import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error

import hive_admin
import hive_backup
import hive_ops
import hive_status

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_DB_PATH = os.path.join(PROJECT_ROOT, "ai_company.db")
PROJECT_BACKUPS_ROOT = os.path.join(PROJECT_ROOT, "backups")

TEST_ADMIN_TOKEN = "mission020-integration-test-admin-token"


def _hash_file(path):
  digest = hashlib.sha256()
  with open(path, "rb") as f:
    digest.update(f.read())
  return digest.hexdigest()


def _snapshot_real_project_state():
  """本番DBのハッシュと、実backups/直下のエントリ一覧を記録する。

  統合テスト全体の前後でこれらが変化していないことを確認するために使う
  (読み取りのみ。書き込みは一切行わない)。
  """
  return {
      "db_hash": _hash_file(PROJECT_DB_PATH),
      "backups_entries": sorted(os.listdir(PROJECT_BACKUPS_ROOT)),
  }


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


def _fake_open_url_ok(req):
  if "api/logs" in req.full_url:
    return _FakeResponse(200, "[]")
  return _FakeResponse(200, "<html>会社の全体像ダッシュボード</html>")


class IntegrationTestCase(unittest.TestCase):
  """一時DB・一時backups_root・モックHTTPのみを使う統合テストの基底。"""

  def setUp(self):
    # 統合テスト開始前に、本番DB・実backups/の状態を記録しておく。
    self.real_state_before = _snapshot_real_project_state()

    self.tmp_root = tempfile.mkdtemp(prefix="mission020_integration_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

    self._orig_status_db_name = hive_status.DB_NAME
    self._orig_status_open_url = hive_status._open_url
    self._orig_backup_backups_root = hive_backup.BACKUPS_ROOT
    self._orig_admin_open_url = hive_admin._open_url

    hive_status.DB_NAME = self.source_db
    hive_status._open_url = _fake_open_url_ok
    hive_backup.BACKUPS_ROOT = self.backups_root

  def tearDown(self):
    hive_status.DB_NAME = self._orig_status_db_name
    hive_status._open_url = self._orig_status_open_url
    hive_backup.BACKUPS_ROOT = self._orig_backup_backups_root
    hive_admin._open_url = self._orig_admin_open_url
    shutil.rmtree(self.tmp_root, ignore_errors=True)

    # 統合テストの前後で、本番DB・実backups/が一切変化していないことを
    # 全テスト共通の後始末として確認する(万一の設計ミスの回帰防止)。
    real_state_after = _snapshot_real_project_state()
    self.assertEqual(
        real_state_after, self.real_state_before,
        "統合テストの実行によって本番プロジェクトの状態が変化しました。",
    )

  def _run_cli(self, module, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = module.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class HappyPathWorkflowTestCase(IntegrationTestCase):
  """正常系: 状態確認→バックアップ作成→検証→隔離復旧訓練→統合運用確認。"""

  def test_full_workflow_is_consistent_across_all_tools(self):
    # 1. 状態確認(hive_status)はバックアップ作成前でもOKであること。
    status_results = hive_status.run_all_checks(
        db_path=self.source_db,
        env={
            "AI_HIVE_READ_TOKEN": "x",
            "AI_HIVE_WRITE_TOKEN": "x",
            "AI_HIVE_ADMIN_TOKEN": "x",
        },
    )
    self.assertTrue(all(r["ok"] for r in status_results))

    # 2. バックアップを作成する(一時backups_rootのみ)。
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    self.assertTrue(os.path.isdir(created["backup_dir"]))

    # 3. 作成したバックアップを検証する。
    verify_result = hive_backup.verify_backup(
        created["backup_dir"], backups_root=self.backups_root
    )
    self.assertTrue(verify_result["ok"])

    # 4. 検証済みバックアップで隔離復旧訓練を行う(一時領域のみ、訓練後に
    #    自動削除される)。
    restore_result = hive_backup.restore_test(
        created["backup_dir"], backups_root=self.backups_root
    )
    self.assertTrue(restore_result["ok"])
    self.assertFalse(os.path.isdir(restore_result["temp_dir_used"]))
    self.assertEqual(
        restore_result["restored_table_row_counts"],
        created["metadata"]["table_row_counts"],
    )

    # 5. hive_ops(状態確認+バックアップ検証の一貫表示)もOKであること。
    code, out, _err = self._run_cli(
        hive_ops, ["--verify-backup", created["backup_dir"]]
    )
    self.assertEqual(code, 0)
    self.assertIn("backup_verify", out)
    self.assertIn("総合判定: OK", out)

  def test_admin_cli_read_only_flow_is_mocked_and_consistent(self):
    # hive_admin.pyの正常系(モック通信のみ、実DB・実ネットワーク不使用)を、
    # 同じ統合シナリオの一部として確認する。
    hive_admin._open_url = lambda req: _FakeResponse(
        200,
        '{"status": "success", "data": [{"id": 1, "recorded_at": "x",'
        ' "event_type": "admin_operation", "http_method": "GET",'
        ' "endpoint": "/api/audit-logs", "status_code": 200,'
        ' "permission": "admin", "result_summary": "success count=0"}]}',
    )
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_ADMIN_TOKEN
    try:
      code, out, err = self._run_cli(hive_admin, [])
      self.assertEqual(code, 0)
      self.assertIn("1 件を表示しました", out)
      self.assertNotIn(TEST_ADMIN_TOKEN, out)
      self.assertNotIn(TEST_ADMIN_TOKEN, err)
    finally:
      os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)


class TamperedAndCorruptedInputsTestCase(IntegrationTestCase):
  """異常系: 改ざん・破損・不正パスがどのツールでも一貫して安全に拒否される。"""

  def test_tampered_backup_is_rejected_consistently_by_all_tools(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    with open(created["backup_db_path"], "r+b") as f:
      f.seek(50)
      original = f.read(1)
      f.seek(50)
      f.write(bytes([original[0] ^ 0xFF]))

    # verify単体でもNG。
    verify_result = hive_backup.verify_backup(
        created["backup_dir"], backups_root=self.backups_root
    )
    self.assertFalse(verify_result["ok"])

    # restore-testは検証段階で弾かれ、BackupErrorとして安全に失敗する
    # (復旧コピー自体を試みない)。
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(
          created["backup_dir"], backups_root=self.backups_root
      )

    # hive_ops経由でも一貫してNG(総合判定NG、例外は外に漏れない)。
    code, out, _err = self._run_cli(
        hive_ops, ["--verify-backup", created["backup_dir"]]
    )
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)
    self.assertIn("総合判定: NG", out)

  def test_corrupted_db_is_rejected_by_status_and_ops(self):
    with open(self.source_db, "r+b") as f:
      f.seek(100)
      original = f.read(1)
      f.seek(100)
      f.write(bytes([original[0] ^ 0xFF]))

    db_result = hive_status.check_database(db_path=self.source_db)
    self.assertFalse(db_result["ok"])

    code, out, _err = self._run_cli(hive_ops, [])
    self.assertEqual(code, 1)
    self.assertIn("[NG] database", out)
    self.assertIn("総合判定: NG", out)

  def test_backup_path_outside_backups_root_is_rejected_by_all_tools(self):
    outside_dir = os.path.join(self.tmp_root, "not_a_backup")
    os.makedirs(outside_dir, exist_ok=True)
    shutil.copy(
        self.source_db, os.path.join(outside_dir, hive_backup.BACKUP_DB_FILENAME)
    )

    with self.assertRaises(hive_backup.BackupError):
      hive_backup.verify_backup(outside_dir, backups_root=self.backups_root)
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(outside_dir, backups_root=self.backups_root)

    code, out, _err = self._run_cli(hive_ops, ["--verify-backup", outside_dir])
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)

  def test_path_traversal_is_rejected_by_all_tools(self):
    os.makedirs(self.backups_root, exist_ok=True)
    traversal_path = os.path.join(self.backups_root, "..")

    with self.assertRaises(hive_backup.BackupError):
      hive_backup.verify_backup(traversal_path, backups_root=self.backups_root)
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(traversal_path, backups_root=self.backups_root)

    code, out, _err = self._run_cli(
        hive_ops, ["--verify-backup", traversal_path]
    )
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)

  def test_missing_backup_is_rejected_by_all_tools(self):
    os.makedirs(self.backups_root, exist_ok=True)
    missing = os.path.join(self.backups_root, "backup_does_not_exist")

    with self.assertRaises(hive_backup.BackupError):
      hive_backup.verify_backup(missing, backups_root=self.backups_root)
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(missing, backups_root=self.backups_root)

    code, out, _err = self._run_cli(hive_ops, ["--verify-backup", missing])
    self.assertEqual(code, 1)
    self.assertIn("[NG] backup_verify", out)


class ServerDownAndAuthFailureTestCase(IntegrationTestCase):
  """異常系: サーバー停止・認証失敗が、状態確認/運用CLIで一貫して安全に扱われる。"""

  def test_server_down_is_reported_consistently_by_status_and_ops(self):
    def fake_open(req):
      raise urllib.error.URLError("connection refused")

    hive_status._open_url = fake_open

    status_results = hive_status.run_all_checks(db_path=self.source_db)
    critical = [r for r in status_results if r.get("critical", True)]
    self.assertFalse(all(r["ok"] for r in critical))

    code, out, _err = self._run_cli(hive_ops, [])
    self.assertEqual(code, 1)
    self.assertIn("総合判定: NG", out)
    self.assertIn(hive_status.BASE_URL, out)

  def test_admin_cli_rejects_missing_token_without_network_call(self):
    calls = []
    hive_admin._open_url = lambda req: calls.append(req) or self.fail(
        "トークン未設定時にネットワーク通信が発生した"
    )
    os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)

    code, _out, err = self._run_cli(hive_admin, [])
    self.assertEqual(code, 1)
    self.assertEqual(calls, [])
    self.assertIn(hive_admin.TOKEN_ENV_VAR, err)

  def test_admin_cli_rejects_invalid_limit_without_network_call(self):
    calls = []
    hive_admin._open_url = lambda req: calls.append(req) or self.fail(
        "不正なlimitでネットワーク通信が発生した"
    )
    os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_ADMIN_TOKEN
    try:
      code, _out, err = self._run_cli(hive_admin, ["--limit", "abc"])
      self.assertEqual(code, 1)
      self.assertEqual(calls, [])
      self.assertNotIn(TEST_ADMIN_TOKEN, err)
    finally:
      os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)

  def test_admin_cli_reports_401_and_403_safely(self):
    for status_code, message in (
        (401, "認証に失敗しました。"),
        (403, "権限が不足しています。"),
    ):
      def fake_open(req, _status=status_code, _message=message):
        raise _make_http_error(
            req.full_url, _status,
            f'{{"status": "error", "message": "{_message}"}}',
        )

      hive_admin._open_url = fake_open
      os.environ["AI_HIVE_ADMIN_TOKEN"] = TEST_ADMIN_TOKEN
      try:
        code, out, err = self._run_cli(hive_admin, [])
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertNotIn(TEST_ADMIN_TOKEN, out + err)
      finally:
        os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)


class NoSideEffectsGuaranteeTestCase(IntegrationTestCase):
  """一時領域内での一連の操作全体を通じて、副作用ゼロが保たれることの確認。"""

  def test_source_and_backup_hashes_unchanged_through_full_cycle(self):
    source_hash_before = _hash_file(self.source_db)

    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    backup_hash_after_create = _hash_file(created["backup_db_path"])

    hive_backup.verify_backup(created["backup_dir"], backups_root=self.backups_root)
    hive_backup.restore_test(created["backup_dir"], backups_root=self.backups_root)
    hive_status.run_all_checks(db_path=self.source_db)
    self._run_cli(hive_ops, ["--verify-backup", created["backup_dir"]])

    self.assertEqual(_hash_file(self.source_db), source_hash_before)
    self.assertEqual(_hash_file(created["backup_db_path"]), backup_hash_after_create)

  def test_no_secrets_leak_across_combined_run(self):
    secret = "mission020-should-never-leak-anywhere"
    os.environ["AI_HIVE_ADMIN_TOKEN"] = secret
    hive_admin._open_url = lambda req: _FakeResponse(
        200, '{"status": "success", "data": []}'
    )
    try:
      created = hive_backup.create_backup(
          db_path=self.source_db, backups_root=self.backups_root
      )
      _c1, out1, err1 = self._run_cli(hive_admin, [])
      _c2, out2, err2 = self._run_cli(
          hive_ops, ["--verify-backup", created["backup_dir"]]
      )
      combined = out1 + err1 + out2 + err2
      self.assertNotIn(secret, combined)
    finally:
      os.environ.pop("AI_HIVE_ADMIN_TOKEN", None)


if __name__ == "__main__":
  unittest.main()
