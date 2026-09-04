"""hive_backup.py（MISSION 016 バックアップ・検証CLI）の単体テスト。

すべてのバックアップ・検証操作は一時ディレクトリ(tempfile)内でのみ行い、
プロジェクト内の `backups/` ディレクトリや本番の `ai_company.db` には
一切書き込まない。対象DBはプロジェクトの `ai_company.db` を一時ファイルへ
コピーしたものを使う（本番DBはコピー元として読み取るのみ）。

実行方法: venv/bin/python test_hive_backup.py
"""

import contextlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import unittest

import hive_backup

PROJECT_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_company.db")


class HiveBackupTestCase(unittest.TestCase):

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_backup_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

  def tearDown(self):
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _source_hash(self):
    return hive_backup._sha256_of_file(self.source_db)

  def _source_counts(self):
    conn = sqlite3.connect(self.source_db)
    try:
      return hive_backup._table_row_counts(conn)
    finally:
      conn.close()

  # --- バックアップ作成 ------------------------------------------------------

  def test_create_backup_produces_valid_copy_with_metadata(self):
    result = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    self.assertTrue(os.path.isdir(result["backup_dir"]))
    self.assertTrue(os.path.isfile(result["backup_db_path"]))
    self.assertTrue(os.path.isfile(result["metadata_path"]))

    with open(result["metadata_path"], encoding="utf-8") as f:
      metadata = json.load(f)
    self.assertEqual(metadata["integrity_check"], "ok")
    self.assertTrue(metadata["foreign_key_check_ok"])
    self.assertEqual(
        metadata["sha256"], hive_backup._sha256_of_file(result["backup_db_path"])
    )
    self.assertIn("created_at", metadata)

  def test_source_db_hash_and_counts_unchanged_after_backup(self):
    hash_before = self._source_hash()
    counts_before = self._source_counts()

    hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )

    self.assertEqual(self._source_hash(), hash_before)
    self.assertEqual(self._source_counts(), counts_before)

  def test_backup_row_counts_match_source(self):
    counts_before = self._source_counts()
    result = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    self.assertEqual(result["metadata"]["table_row_counts"], counts_before)
    # work_logs・audit_logsを含むDB全体が対象であることの確認。
    self.assertIn("work_logs", result["metadata"]["table_row_counts"])
    self.assertIn("audit_logs", result["metadata"]["table_row_counts"])
    self.assertIn("employees", result["metadata"]["table_row_counts"])

  def test_repeated_backups_produce_distinct_directories(self):
    result1 = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    result2 = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    self.assertNotEqual(result1["backup_dir"], result2["backup_dir"])
    self.assertTrue(os.path.isdir(result1["backup_dir"]))
    self.assertTrue(os.path.isdir(result2["backup_dir"]))

  def test_create_backup_fails_safely_when_source_db_missing(self):
    missing_path = os.path.join(self.tmp_root, "does_not_exist.db")
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.create_backup(
          db_path=missing_path, backups_root=self.backups_root
      )
    # 失敗時にbackups_rootへ何も作られていないこと。
    self.assertFalse(os.path.isdir(self.backups_root))

  # --- 検証(verify) ----------------------------------------------------------

  def test_verify_succeeds_for_untampered_backup(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    result = hive_backup.verify_backup(
        created["backup_dir"], backups_root=self.backups_root
    )
    self.assertTrue(result["ok"])
    self.assertTrue(result["hash_matches"])
    self.assertTrue(result["integrity_ok"])
    self.assertTrue(result["foreign_key_check_ok"])

  def test_verify_accepts_direct_db_file_path(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    result = hive_backup.verify_backup(
        created["backup_db_path"], backups_root=self.backups_root
    )
    self.assertTrue(result["ok"])

  def test_verify_fails_safely_when_backup_file_tampered(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    # メタデータは変更せず、バックアップDBファイルのみ改変する。
    with open(created["backup_db_path"], "r+b") as f:
      f.seek(100)
      original_byte = f.read(1)
      f.seek(100)
      f.write(bytes([original_byte[0] ^ 0xFF]))

    result = hive_backup.verify_backup(
        created["backup_dir"], backups_root=self.backups_root
    )
    self.assertFalse(result["ok"])
    self.assertFalse(result["hash_matches"])

  def test_verify_fails_safely_when_backup_path_missing(self):
    missing = os.path.join(self.backups_root, "backup_does_not_exist")
    os.makedirs(self.backups_root, exist_ok=True)
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.verify_backup(missing, backups_root=self.backups_root)

  def test_verify_rejects_path_outside_backups_root(self):
    outside_dir = os.path.join(self.tmp_root, "not_a_backup")
    os.makedirs(outside_dir, exist_ok=True)
    shutil.copy(
        self.source_db, os.path.join(outside_dir, hive_backup.BACKUP_DB_FILENAME)
    )
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.verify_backup(outside_dir, backups_root=self.backups_root)

  def test_verify_rejects_path_traversal_outside_backups_root(self):
    os.makedirs(self.backups_root, exist_ok=True)
    traversal_path = os.path.join(self.backups_root, "..")
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.verify_backup(traversal_path, backups_root=self.backups_root)

  def test_verify_does_not_modify_backup_or_source(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    backup_hash_before = hive_backup._sha256_of_file(created["backup_db_path"])
    source_hash_before = self._source_hash()

    hive_backup.verify_backup(
        created["backup_dir"], backups_root=self.backups_root
    )

    self.assertEqual(
        hive_backup._sha256_of_file(created["backup_db_path"]), backup_hash_before
    )
    self.assertEqual(self._source_hash(), source_hash_before)

  # --- CLIエントリポイント ----------------------------------------------------

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_backup.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def test_cli_create_then_verify_round_trip(self):
    orig_db_name = hive_backup.DB_NAME
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.DB_NAME = self.source_db
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      code, out, _err = self._run_main(["create"])
      self.assertEqual(code, 0)
      self.assertIn("バックアップを作成しました", out)

      entries = os.listdir(self.backups_root)
      self.assertEqual(len(entries), 1)
      backup_dir = os.path.join(self.backups_root, entries[0])

      code, out, _err = self._run_main(["verify", backup_dir])
      self.assertEqual(code, 0)
      self.assertIn("OK", out)
    finally:
      hive_backup.DB_NAME = orig_db_name
      hive_backup.BACKUPS_ROOT = orig_backups_root

  def test_cli_verify_reports_failure_exit_code_for_invalid_path(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    os.makedirs(self.backups_root, exist_ok=True)
    try:
      code, _out, err = self._run_main(
          ["verify", os.path.join(self.tmp_root, "not_under_backups_root")]
      )
      self.assertEqual(code, 1)
      self.assertIn("エラー", err)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root


class HiveRestoreTestDrillTestCase(unittest.TestCase):
  """hive_backup.restore_test()（MISSION 017 隔離復旧訓練）の単体テスト。

  ここでも、対象DB・バックアップ先はすべて一時ディレクトリ内に限定し、
  プロジェクト内の `backups/` や本番の `ai_company.db` には一切触れない。
  """

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_restore_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")
    self.created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )

  def tearDown(self):
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _source_hash(self):
    return hive_backup._sha256_of_file(self.source_db)

  def _backup_hash(self):
    return hive_backup._sha256_of_file(self.created["backup_db_path"])

  # --- 正常系: 検証済みバックアップからの隔離復旧 ----------------------------

  def test_restore_test_succeeds_from_verified_backup(self):
    result = hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    self.assertTrue(result["ok"])
    self.assertTrue(result["integrity_ok"])
    self.assertTrue(result["foreign_key_check_ok"])
    self.assertTrue(result["table_counts_match"])
    self.assertTrue(result["backup_source_hash_unchanged"])

  def test_restored_table_counts_match_metadata(self):
    result = hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    self.assertEqual(
        result["restored_table_row_counts"], result["expected_table_row_counts"]
    )
    self.assertEqual(
        result["restored_table_row_counts"],
        self.created["metadata"]["table_row_counts"],
    )
    self.assertIn("work_logs", result["restored_table_row_counts"])
    self.assertIn("audit_logs", result["restored_table_row_counts"])

  def test_restore_test_accepts_direct_db_file_path(self):
    result = hive_backup.restore_test(
        self.created["backup_db_path"], backups_root=self.backups_root
    )
    self.assertTrue(result["ok"])

  # --- 一時領域の隔離・後始末 -------------------------------------------------

  def test_temp_dir_is_deleted_after_drill(self):
    result = hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    self.assertFalse(os.path.isdir(result["temp_dir_used"]))

  def test_temp_dir_is_outside_project_and_backups_root(self):
    result = hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    project_root_real = os.path.realpath(os.path.dirname(hive_backup.__file__))
    backups_root_real = os.path.realpath(self.backups_root)
    temp_dir_used = result["temp_dir_used"]
    self.assertFalse(
        temp_dir_used == project_root_real
        or temp_dir_used.startswith(project_root_real + os.sep)
    )
    self.assertFalse(
        temp_dir_used == backups_root_real
        or temp_dir_used.startswith(backups_root_real + os.sep)
    )
    self.assertNotEqual(temp_dir_used, os.path.realpath(self.source_db))

  def test_temp_dir_is_cleaned_up_even_when_counts_would_mismatch(self):
    # metadata.jsonを直接改ざんして件数不一致を発生させても
    # (バックアップDB自体・ハッシュは無傷のまま)、一時ディレクトリは
    # 必ず削除されることを確認する。
    metadata_path = os.path.join(self.created["backup_dir"], "metadata.json")
    with open(metadata_path, encoding="utf-8") as f:
      metadata = json.load(f)
    tampered_hash_target = metadata["sha256"]
    metadata["table_row_counts"]["work_logs"] = 999
    with open(metadata_path, "w", encoding="utf-8") as f:
      json.dump(metadata, f)

    # ハッシュ自体は変えていないので、verify_backup自体はOKのまま
    # restore_testの処理に進む(検証はハッシュ・integrity・fkのみを見る)。
    self.assertEqual(self._backup_hash(), tampered_hash_target)

    result = hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    self.assertFalse(result["ok"])
    self.assertFalse(result["table_counts_match"])
    self.assertFalse(os.path.isdir(result["temp_dir_used"]))

  # --- 実DB・バックアップ元への影響なし ---------------------------------------

  def test_backup_source_hash_unchanged_before_and_after_drill(self):
    hash_before = self._backup_hash()
    hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    self.assertEqual(self._backup_hash(), hash_before)

  def test_original_source_db_unchanged_before_and_after_drill(self):
    hash_before = self._source_hash()
    hive_backup.restore_test(
        self.created["backup_dir"], backups_root=self.backups_root
    )
    self.assertEqual(self._source_hash(), hash_before)

  def test_restore_test_has_no_destination_override_parameters(self):
    # 復旧先を指定できるパラメータ(destination/output_dir等)が
    # 存在しないこと=CLI引数・環境変数で復旧先を変更できないことの
    # コード上の裏付け。
    import inspect
    params = list(inspect.signature(hive_backup.restore_test).parameters)
    self.assertEqual(params, ["backup_path", "backups_root"])

  # --- 不正・改変・検証未済バックアップの安全な拒否 ---------------------------

  def test_restore_test_rejects_tampered_backup(self):
    with open(self.created["backup_db_path"], "r+b") as f:
      f.seek(50)
      original_byte = f.read(1)
      f.seek(50)
      f.write(bytes([original_byte[0] ^ 0xFF]))

    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(
          self.created["backup_dir"], backups_root=self.backups_root
      )

  def test_restore_test_rejects_path_outside_backups_root(self):
    outside_dir = os.path.join(self.tmp_root, "not_a_backup")
    os.makedirs(outside_dir, exist_ok=True)
    shutil.copy(
        self.created["backup_db_path"],
        os.path.join(outside_dir, hive_backup.BACKUP_DB_FILENAME),
    )
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(outside_dir, backups_root=self.backups_root)

  def test_restore_test_rejects_path_traversal(self):
    traversal_path = os.path.join(self.backups_root, "..")
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(traversal_path, backups_root=self.backups_root)

  def test_restore_test_rejects_missing_backup(self):
    missing = os.path.join(self.backups_root, "backup_does_not_exist")
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_test(missing, backups_root=self.backups_root)

  # --- CLI経由 ---------------------------------------------------------------

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_backup.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def test_cli_restore_test_round_trip(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      code, out, _err = self._run_main(
          ["restore-test", self.created["backup_dir"]]
      )
      self.assertEqual(code, 0)
      self.assertIn("隔離復旧訓練", out)
      self.assertIn("総合判定: OK", out)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root

  def test_cli_restore_test_fails_safely_for_invalid_path(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      code, _out, err = self._run_main(
          ["restore-test", os.path.join(self.tmp_root, "not_under_backups_root")]
      )
      self.assertEqual(code, 1)
      self.assertIn("エラー", err)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root


if __name__ == "__main__":
  unittest.main()
