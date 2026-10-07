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


class HiveBackupListTestCase(unittest.TestCase):
  """hive_backup.list_backups()（MISSION 021 バックアップ一覧）の単体テスト。

  ここでも、対象は一時ディレクトリ内のbackups_rootのみに限定し、
  プロジェクト内の `backups/` や本番の `ai_company.db` には一切触れない。
  """

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_backup_list_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

  def tearDown(self):
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_backup.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  # --- 基本動作 ---------------------------------------------------------------

  def test_list_returns_empty_when_backups_root_missing(self):
    self.assertEqual(hive_backup.list_backups(backups_root=self.backups_root), [])

  def test_list_returns_empty_when_backups_root_is_empty_dir(self):
    os.makedirs(self.backups_root, exist_ok=True)
    self.assertEqual(hive_backup.list_backups(backups_root=self.backups_root), [])

  def test_list_shows_created_backup_with_expected_fields(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    entries = hive_backup.list_backups(backups_root=self.backups_root)
    self.assertEqual(len(entries), 1)
    entry = entries[0]
    self.assertTrue(entry["ok"])
    self.assertEqual(entry["identifier"], os.path.basename(created["backup_dir"]))
    self.assertEqual(entry["sha256"], created["metadata"]["sha256"])
    self.assertEqual(entry["created_at"], created["metadata"]["created_at"])
    self.assertEqual(entry["integrity_check"], "ok")
    self.assertTrue(entry["foreign_key_check_ok"])
    self.assertEqual(
        entry["table_row_counts"], created["metadata"]["table_row_counts"]
    )

  def test_list_orders_newest_backup_first(self):
    created1 = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    created2 = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    # created_atの秒精度が同一になる可能性があるため、順序を明確にする
    # ためにcreated2のcreated_atを明示的に新しい日時へ書き換える。
    metadata_path = os.path.join(created2["backup_dir"], "metadata.json")
    with open(metadata_path, encoding="utf-8") as f:
      metadata = json.load(f)
    metadata["created_at"] = "2099-01-01T00:00:00"
    with open(metadata_path, "w", encoding="utf-8") as f:
      json.dump(metadata, f)

    entries = hive_backup.list_backups(backups_root=self.backups_root)
    self.assertEqual(len(entries), 2)
    self.assertEqual(
        entries[0]["identifier"], os.path.basename(created2["backup_dir"])
    )
    self.assertEqual(
        entries[1]["identifier"], os.path.basename(created1["backup_dir"])
    )

  # --- 不正・不完全なエントリの安全な扱い -------------------------------------

  def test_list_ignores_unrelated_directory_without_metadata_or_db(self):
    hive_backup.create_backup(db_path=self.source_db, backups_root=self.backups_root)
    unrelated_dir = os.path.join(self.backups_root, "not_a_backup_at_all")
    os.makedirs(unrelated_dir)
    with open(os.path.join(unrelated_dir, "random.txt"), "w") as f:
      f.write("hello")

    entries = hive_backup.list_backups(backups_root=self.backups_root)
    identifiers = [e["identifier"] for e in entries]
    self.assertNotIn("not_a_backup_at_all", identifiers)
    self.assertEqual(len(entries), 1)

  def test_list_flags_corrupted_metadata_json(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    metadata_path = os.path.join(created["backup_dir"], "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
      f.write("{not valid json!!!")

    entries = hive_backup.list_backups(backups_root=self.backups_root)
    self.assertEqual(len(entries), 1)
    self.assertFalse(entries[0]["ok"])
    self.assertIn("metadata.json", entries[0]["reason"])

  def test_list_flags_metadata_without_db_file(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    os.remove(created["backup_db_path"])

    entries = hive_backup.list_backups(backups_root=self.backups_root)
    self.assertEqual(len(entries), 1)
    self.assertFalse(entries[0]["ok"])
    self.assertIn("ai_company.db", entries[0]["reason"])

  def test_list_ignores_symlinked_backup_directory(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    link_path = os.path.join(self.backups_root, "symlinked_backup")
    os.symlink(created["backup_dir"], link_path)

    entries = hive_backup.list_backups(backups_root=self.backups_root)
    identifiers = [e["identifier"] for e in entries]
    self.assertNotIn("symlinked_backup", identifiers)
    self.assertEqual(len(entries), 1)

  def test_list_flags_symlinked_internal_db_file(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    os.remove(created["backup_db_path"])
    os.symlink(self.source_db, created["backup_db_path"])

    entries = hive_backup.list_backups(backups_root=self.backups_root)
    self.assertEqual(len(entries), 1)
    self.assertFalse(entries[0]["ok"])
    self.assertIn("シンボリックリンク", entries[0]["reason"])

  # --- 副作用ゼロ・DB非アクセスの確認 ------------------------------------------

  def test_list_never_opens_any_database_connection(self):
    hive_backup.create_backup(db_path=self.source_db, backups_root=self.backups_root)

    def fail_if_called(*args, **kwargs):
      raise AssertionError("list_backups()がsqlite3.connect()を呼び出した")

    orig_connect = hive_backup.sqlite3.connect
    hive_backup.sqlite3.connect = fail_if_called
    try:
      entries = hive_backup.list_backups(backups_root=self.backups_root)
      self.assertEqual(len(entries), 1)
      self.assertTrue(entries[0]["ok"])
    finally:
      hive_backup.sqlite3.connect = orig_connect

  def test_list_does_not_modify_backup_files_or_create_new_files(self):
    created = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    before = sorted(os.listdir(created["backup_dir"]))
    db_hash_before = hive_backup._sha256_of_file(created["backup_db_path"])

    hive_backup.list_backups(backups_root=self.backups_root)

    after = sorted(os.listdir(created["backup_dir"]))
    self.assertEqual(before, after)
    self.assertEqual(
        hive_backup._sha256_of_file(created["backup_db_path"]), db_hash_before
    )

  # --- CLI経由 ---------------------------------------------------------------

  def test_cli_list_end_to_end(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      created = hive_backup.create_backup(
          db_path=self.source_db, backups_root=self.backups_root
      )
      code, out, _err = self._run_main(["list"])
      self.assertEqual(code, 0)
      self.assertIn(os.path.basename(created["backup_dir"]), out)
      self.assertIn("バックアップ一覧", out)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root

  def test_cli_list_reports_no_backups_found(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      code, out, _err = self._run_main(["list"])
      self.assertEqual(code, 0)
      self.assertIn("見つかりません", out)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root

  def test_cli_list_accepts_no_extra_arguments(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      with self.assertRaises(SystemExit):
        self._run_main(["list", "some-unexpected-path"])
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root


class HiveBackupPruneTestCase(unittest.TestCase):
  """hive_backup.prune_backups()（MISSION 092 世代整理）の単体テスト。

  ここでも、対象は一時ディレクトリ内のbackups_rootのみに限定し、
  プロジェクト内の `backups/` や本番の `ai_company.db` には一切触れない。
  """

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_backup_prune_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

  def tearDown(self):
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _run_main(self, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
      code = hive_backup.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()

  def _create_n_backups(self, n):
    created = []
    for i in range(n):
      result = hive_backup.create_backup(
          db_path=self.source_db, backups_root=self.backups_root
      )
      created.append(result)
      # created_atの秒精度が同一になりうるため、作成順が一意に分かるよう
      # metadata.jsonのcreated_atへ明示的な連番日時を書き込み直す。
      metadata_path = os.path.join(result["backup_dir"], "metadata.json")
      with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)
      metadata["created_at"] = f"2099-01-{i + 1:02d}T00:00:00"
      with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)
    return created

  def test_prune_keeps_only_the_newest_n_generations(self):
    self._create_n_backups(10)
    result = hive_backup.prune_backups(keep=7, backups_root=self.backups_root)
    self.assertEqual(result["kept"], 7)
    self.assertEqual(len(result["deleted"]), 3)
    self.assertEqual(result["errors"], [])
    remaining = [
        e for e in hive_backup.list_backups(backups_root=self.backups_root)
        if e["ok"]
    ]
    self.assertEqual(len(remaining), 7)

  def test_prune_deletes_the_oldest_generations_first(self):
    created = self._create_n_backups(9)
    hive_backup.prune_backups(keep=7, backups_root=self.backups_root)
    remaining_ids = {
        e["identifier"]
        for e in hive_backup.list_backups(backups_root=self.backups_root)
        if e["ok"]
    }
    # created[0]・created[1]が最も古い(2099-01-01・2099-01-02)ため削除され、
    # 残り7件(created[2]〜created[8])は維持される。
    self.assertNotIn(os.path.basename(created[0]["backup_dir"]), remaining_ids)
    self.assertNotIn(os.path.basename(created[1]["backup_dir"]), remaining_ids)
    for c in created[2:]:
      self.assertIn(os.path.basename(c["backup_dir"]), remaining_ids)

  def test_prune_does_not_touch_entries_without_backup_prefix(self):
    # MISSION 092: backup_<timestamp>_<suffix>/ 以外の名前のディレクトリ
    # (手動スナップショット等)は、たとえmetadata.jsonを持っていても削除
    # 対象にしない。
    self._create_n_backups(8)
    manual_dir = os.path.join(self.backups_root, "pre_mission999_20990101_000000")
    os.makedirs(manual_dir)
    shutil.copy(self.source_db, os.path.join(manual_dir, "ai_company.db"))
    manual_metadata = {
        "created_at": "2099-02-01T00:00:00",
        "sha256": hive_backup._sha256_of_file(self.source_db),
        "size_bytes": os.path.getsize(self.source_db),
        "integrity_check": "ok",
        "foreign_key_check_ok": True,
        "table_row_counts": {},
    }
    with open(os.path.join(manual_dir, "metadata.json"), "w", encoding="utf-8") as f:
      json.dump(manual_metadata, f)

    result = hive_backup.prune_backups(keep=7, backups_root=self.backups_root)
    self.assertNotIn("pre_mission999_20990101_000000", result["deleted"])
    self.assertTrue(os.path.isdir(manual_dir))

  def test_prune_does_not_touch_entries_without_valid_metadata(self):
    # metadata.jsonが無い/壊れている等でok=Falseのエントリは削除しない
    # (list_backups()が安全に無視・末尾表示する対象と同じ)。
    self._create_n_backups(8)
    broken_dir = os.path.join(self.backups_root, "backup_broken_entry")
    os.makedirs(broken_dir)
    shutil.copy(self.source_db, os.path.join(broken_dir, "ai_company.db"))
    # metadata.jsonをわざと置かない(= list_backups()でok:Falseになる)。

    result = hive_backup.prune_backups(keep=7, backups_root=self.backups_root)
    self.assertTrue(os.path.isdir(broken_dir))
    self.assertNotIn("backup_broken_entry", result["deleted"])

  def test_prune_is_a_no_op_when_within_retention_limit(self):
    self._create_n_backups(5)
    result = hive_backup.prune_backups(keep=7, backups_root=self.backups_root)
    self.assertEqual(result["kept"], 5)
    self.assertEqual(result["deleted"], [])
    remaining = [
        e for e in hive_backup.list_backups(backups_root=self.backups_root)
        if e["ok"]
    ]
    self.assertEqual(len(remaining), 5)

  def test_prune_handles_missing_backups_root_safely(self):
    result = hive_backup.prune_backups(keep=7, backups_root=self.backups_root)
    self.assertEqual(result, {"kept": 0, "deleted": [], "errors": []})

  def test_cli_prune_end_to_end(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      self._create_n_backups(10)
      code, out, _err = self._run_main(["prune", "--keep", "7"])
      self.assertEqual(code, 0)
      self.assertIn("残した件数: 7", out)
      self.assertIn("削除した件数: 3", out)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root

  def test_cli_prune_default_keep_is_seven(self):
    orig_backups_root = hive_backup.BACKUPS_ROOT
    hive_backup.BACKUPS_ROOT = self.backups_root
    try:
      self._create_n_backups(9)
      code, out, _err = self._run_main(["prune"])
      self.assertEqual(code, 0)
      self.assertIn("残した件数: 7", out)
    finally:
      hive_backup.BACKUPS_ROOT = orig_backups_root

  # --- protect引数(MISSION 093: 復元元・復元前バックアップの保護) --------

  def test_prune_protect_keeps_specified_identifiers_beyond_retention_limit(self):
    created = self._create_n_backups(9)
    protected_id = os.path.basename(created[0]["backup_dir"])
    result = hive_backup.prune_backups(
        keep=7, backups_root=self.backups_root, protect={protected_id}
    )
    # 9件中、keep=7を超える2件が本来削除対象だが、うち1件(created[0])は
    # 保護されているため削除されない(実際に消えるのは1件だけ)。
    self.assertEqual(len(result["deleted"]), 1)
    self.assertNotIn(protected_id, result["deleted"])
    remaining_ids = {
        e["identifier"]
        for e in hive_backup.list_backups(backups_root=self.backups_root)
        if e["ok"]
    }
    self.assertIn(protected_id, remaining_ids)

  def test_prune_protect_empty_set_behaves_like_no_protection(self):
    self._create_n_backups(10)
    result = hive_backup.prune_backups(
        keep=7, backups_root=self.backups_root, protect=set()
    )
    self.assertEqual(len(result["deleted"]), 3)


class HiveBackupRestoreTestCase(unittest.TestCase):
  """hive_backup.restore_backup()（MISSION 093 実際の復元）の単体テスト。

  restore_test()(隔離訓練、実DBは一切変更しない)とは異なり、ここでは
  実際にself.source_db(一時ディレクトリ内のコピー)を書き換える。本番の
  `ai_company.db`・`backups/` には一切触れない。
  """

  def setUp(self):
    self.tmp_root = tempfile.mkdtemp(prefix="hive_backup_restore_test_")
    self.source_db = os.path.join(self.tmp_root, "ai_company.db")
    shutil.copy(PROJECT_DB_PATH, self.source_db)
    self.backups_root = os.path.join(self.tmp_root, "backups")

  def tearDown(self):
    shutil.rmtree(self.tmp_root, ignore_errors=True)

  def _row_counts(self, db_path):
    conn = sqlite3.connect(db_path)
    try:
      return hive_backup._table_row_counts(conn)
    finally:
      conn.close()

  def test_restore_backup_replaces_current_db_with_backup_content(self):
    backup = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    counts_at_backup = self._row_counts(self.source_db)

    conn = sqlite3.connect(self.source_db)
    conn.execute(
        "INSERT INTO work_logs (timestamp, theme, content, status)"
        " VALUES ('2099-01-01','t','mutation after backup','done')"
    )
    conn.commit()
    conn.close()
    self.assertNotEqual(self._row_counts(self.source_db), counts_at_backup)

    hive_backup.restore_backup(
        backup["backup_dir"], db_path=self.source_db,
        backups_root=self.backups_root,
    )
    self.assertEqual(self._row_counts(self.source_db), counts_at_backup)

  def test_restore_backup_creates_pre_restore_backup(self):
    backup = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    before = {
        e["identifier"]
        for e in hive_backup.list_backups(backups_root=self.backups_root)
        if e["ok"]
    }
    result = hive_backup.restore_backup(
        backup["backup_dir"], db_path=self.source_db,
        backups_root=self.backups_root,
    )
    after = {
        e["identifier"]
        for e in hive_backup.list_backups(backups_root=self.backups_root)
        if e["ok"]
    }
    new_dirs = after - before
    self.assertEqual(len(new_dirs), 1)
    self.assertEqual(
        new_dirs.pop(), os.path.basename(result["pre_restore_backup_dir"])
    )
    self.assertIsNotNone(result["pre_restore_created_at"])
    self.assertIsNotNone(result["restored_from_created_at"])

  def test_restore_backup_rejects_tampered_backup_and_leaves_db_unchanged(self):
    backup = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    original_hash = hive_backup._sha256_of_file(self.source_db)
    with open(
        os.path.join(backup["backup_dir"], "ai_company.db"), "ab"
    ) as f:
      f.write(b"TAMPERED")

    before_backups = len(
        [e for e in hive_backup.list_backups(backups_root=self.backups_root) if e["ok"]]
    )
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_backup(
          backup["backup_dir"], db_path=self.source_db,
          backups_root=self.backups_root,
      )
    self.assertEqual(hive_backup._sha256_of_file(self.source_db), original_hash)
    # 検証失敗時点で中止するため、復元前バックアップも作られない。
    after_backups = len(
        [e for e in hive_backup.list_backups(backups_root=self.backups_root) if e["ok"]]
    )
    self.assertEqual(before_backups, after_backups)

  def test_restore_backup_rejects_missing_backup_and_leaves_db_unchanged(self):
    original_hash = hive_backup._sha256_of_file(self.source_db)
    missing_path = os.path.join(self.backups_root, "backup_doesnotexist_000000")
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_backup(
          missing_path, db_path=self.source_db, backups_root=self.backups_root,
      )
    self.assertEqual(hive_backup._sha256_of_file(self.source_db), original_hash)

  def test_restore_backup_rejects_path_outside_backups_root(self):
    outside = os.path.join(self.tmp_root, "not_in_backups_root")
    os.makedirs(outside, exist_ok=True)
    original_hash = hive_backup._sha256_of_file(self.source_db)
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_backup(
          outside, db_path=self.source_db, backups_root=self.backups_root,
      )
    self.assertEqual(hive_backup._sha256_of_file(self.source_db), original_hash)

  def test_restore_backup_does_not_modify_source_backup_file(self):
    backup = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    backup_hash_before = hive_backup._sha256_of_file(
        os.path.join(backup["backup_dir"], "ai_company.db")
    )
    hive_backup.restore_backup(
        backup["backup_dir"], db_path=self.source_db,
        backups_root=self.backups_root,
    )
    backup_hash_after = hive_backup._sha256_of_file(
        os.path.join(backup["backup_dir"], "ai_company.db")
    )
    self.assertEqual(backup_hash_before, backup_hash_after)

  def test_restore_backup_fails_safely_when_db_path_missing(self):
    backup = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    missing_db_path = os.path.join(self.tmp_root, "does_not_exist.db")
    with self.assertRaises(hive_backup.BackupError):
      hive_backup.restore_backup(
          backup["backup_dir"], db_path=missing_db_path,
          backups_root=self.backups_root,
      )

  def test_restore_backup_current_db_survives_when_pre_restore_backup_fails(self):
    # 復元前バックアップの作成自体が失敗する場合(例: backups_root配下へ
    # 書き込めない)、実DBの書き換えには一切進まないことを確認する。
    backup = hive_backup.create_backup(
        db_path=self.source_db, backups_root=self.backups_root
    )
    original_hash = hive_backup._sha256_of_file(self.source_db)

    orig_create_backup = hive_backup.create_backup
    def _boom(*args, **kwargs):
      raise hive_backup.BackupError("simulated pre-restore backup failure")
    hive_backup.create_backup = _boom
    try:
      with self.assertRaises(hive_backup.BackupError):
        hive_backup.restore_backup(
            backup["backup_dir"], db_path=self.source_db,
            backups_root=self.backups_root,
        )
    finally:
      hive_backup.create_backup = orig_create_backup
    self.assertEqual(hive_backup._sha256_of_file(self.source_db), original_hash)


if __name__ == "__main__":
  unittest.main()
