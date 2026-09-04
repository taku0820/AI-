#!/usr/bin/env python3
"""localhost限定 SQLiteバックアップ・検証CLI（MISSION 016）。

対象は常にプロジェクト内の `ai_company.db`（`work_logs`・AI Hive OSの
7テーブル・`audit_logs` を含むDBファイル全体）。バックアップ先は常に
プロジェクト内の `backups/` 配下に限定する。

設計上の安全方針:
  - バックアップ作成時、元の `ai_company.db` は読み取り専用
    （`file:...?mode=ro` のSQLite URI接続）で開き、一切書き込まない。
  - コピーには SQLite公式のOnline Backup API
    （`sqlite3.Connection.backup()`）を使う。単純なファイルコピーと
    異なり、同時書き込みが発生していても壊れたスナップショットに
    ならない、SQLiteが推奨する安全な方式。
  - バックアップ1回ごとに、日時とランダム要素を含む専用ディレクトリ
    （`backups/backup_<timestamp>_<suffix>/`）を新規作成する
    （既存バックアップの上書き・自動削除は行わない）。
  - バックアップ直後に、コピー先DBの `PRAGMA integrity_check` と
    `PRAGMA foreign_key_check` を実行して安全性を確認し、コピー先の
    SHA-256ハッシュ・作成日時・テーブル別件数を記録した
    `metadata.json` を同じディレクトリに書き出す。
  - 検証（`verify`）は指定されたバックアップに対して読み取り専用で
    行い、`backups/` 配下から外れたパス・存在しないパスは安全に
    拒否する。実DBへの復元（上書き・削除・置換）はこのスクリプトには
    一切実装しない。

実行例（docs/MISSION016_backup_recovery_runbook.md も参照）:
    python hive_backup.py create
    python hive_backup.py verify backups/backup_20260905_010203_ab12cd
"""

import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import sys
import uuid

# 対象DB・バックアップ先はどちらも固定する。CLI引数・環境変数で
# 変更できる設定は追加しない（プロジェクト外への読み書きを防ぐため）。
DB_NAME = "ai_company.db"
BACKUPS_ROOT = "backups"

METADATA_FILENAME = "metadata.json"
BACKUP_DB_FILENAME = "ai_company.db"


class BackupError(Exception):
  """CLI利用者にそのまま表示してよいエラーメッセージのみを持つ例外。"""


def _sha256_of_file(path):
  digest = hashlib.sha256()
  with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def _table_row_counts(conn):
  """DB内の全ユーザーテーブル(sqlite_*系を除く)の件数を返す。

  読み取りのみ(SELECT COUNT(*))であり、対象コネクションを変更しない。
  """
  tables = [
      row[0]
      for row in conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table'"
          " AND name NOT LIKE 'sqlite_%' ORDER BY name"
      ).fetchall()
  ]
  counts = {}
  for table in tables:
    counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
  return counts


def _check_integrity(db_path):
  """指定DBファイルに対し integrity_check / foreign_key_check を実行する。

  読み取り専用接続のみを使い、対象DBを一切変更しない。ファイルが破損
  している等でPRAGMA自体が例外を送出するケースも、検証処理全体を
  クラッシュさせず「異常あり」として安全に結果へ反映する
  （改変されたバックアップの検証が例外で落ちてしまうことを防ぐため）。
  """
  uri = f"file:{os.path.abspath(db_path)}?mode=ro"
  conn = sqlite3.connect(uri, uri=True)
  try:
    try:
      integrity_result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as e:
      integrity_result = f"error: {e}"

    try:
      fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
      fk_ok = len(fk_violations) == 0
      fk_count = len(fk_violations)
    except sqlite3.DatabaseError:
      fk_ok = False
      fk_count = -1

    try:
      row_counts = _table_row_counts(conn)
    except sqlite3.DatabaseError:
      row_counts = {}

    return {
        "integrity_check": integrity_result,
        "foreign_key_check_ok": fk_ok,
        "foreign_key_violation_count": fk_count,
        "table_row_counts": row_counts,
    }
  finally:
    conn.close()


def _resolve_within_backups_root(path, backups_root):
  """pathがbackups_root配下であることを検証し、正規化した絶対パスを返す。

  backups/以外の任意パス・`..`によるパストラバーサル・シンボリック
  リンクによる脱出を防ぐため、os.path.realpathで両方を正規化してから
  比較する。backups_root配下でない場合はBackupErrorを送出する
  （ここではファイルの読み書きは一切行わない）。
  """
  backups_root_real = os.path.realpath(backups_root)
  target_real = os.path.realpath(path)
  try:
    common = os.path.commonpath([backups_root_real, target_real])
  except ValueError:
    # 異なるドライブ等でcommonpathが比較不能な場合も安全に拒否する。
    common = None
  if common != backups_root_real:
    raise BackupError(
        f"{backups_root}/ 配下以外のパスは扱えません。"
    )
  return target_real


def create_backup(db_path=None, backups_root=None):
  """ai_company.dbの安全なバックアップを作成し、結果を辞書で返す。

  元DBは読み取り専用で開き、一切変更しない。バックアップ先は
  backups_root配下に新規作成する専用ディレクトリに限定する。
  既存バックアップの上書き・自動削除・自動復元は行わない。
  """
  db_path = DB_NAME if db_path is None else db_path
  backups_root = BACKUPS_ROOT if backups_root is None else backups_root

  if not os.path.isfile(db_path):
    raise BackupError(f"対象DBが見つかりません: {db_path}")

  os.makedirs(backups_root, exist_ok=True)

  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
  suffix = uuid.uuid4().hex[:6]
  backup_dir = os.path.join(backups_root, f"backup_{timestamp}_{suffix}")
  # 同名ディレクトリが万一存在する場合は上書きせず安全に失敗する
  # (既存バックアップの自動上書きを行わない方針のため)。
  os.makedirs(backup_dir, exist_ok=False)

  backup_db_path = os.path.join(backup_dir, BACKUP_DB_FILENAME)

  source_uri = f"file:{os.path.abspath(db_path)}?mode=ro"
  src_conn = sqlite3.connect(source_uri, uri=True)
  dest_conn = sqlite3.connect(backup_db_path)
  try:
    src_conn.backup(dest_conn)
  finally:
    dest_conn.close()
    src_conn.close()

  check_result = _check_integrity(backup_db_path)
  backup_hash = _sha256_of_file(backup_db_path)
  created_at = datetime.datetime.now().isoformat(timespec="seconds")

  metadata = {
      "created_at": created_at,
      "source_db_path": os.path.abspath(db_path),
      "backup_db_filename": BACKUP_DB_FILENAME,
      "sha256": backup_hash,
      "size_bytes": os.path.getsize(backup_db_path),
      "integrity_check": check_result["integrity_check"],
      "foreign_key_check_ok": check_result["foreign_key_check_ok"],
      "foreign_key_violation_count": check_result["foreign_key_violation_count"],
      "table_row_counts": check_result["table_row_counts"],
  }
  metadata_path = os.path.join(backup_dir, METADATA_FILENAME)
  with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2, sort_keys=True)
    f.write("\n")

  return {
      "backup_dir": backup_dir,
      "backup_db_path": backup_db_path,
      "metadata_path": metadata_path,
      "metadata": metadata,
  }


def verify_backup(backup_path, backups_root=None):
  """指定したバックアップの整合性・外部キー整合性・ハッシュを検証する。

  読み取り専用で行い、対象のバックアップDB・元のai_company.dbのいずれも
  変更しない。backups_root配下から外れたパス・存在しないパスは
  BackupErrorとして安全に拒否する。復元(上書き・削除)は一切行わない。

  backup_pathには、create_backup()が作成したディレクトリ、または
  そのディレクトリ内のDBファイルそのものを渡せる。
  """
  backups_root = BACKUPS_ROOT if backups_root is None else backups_root

  resolved = _resolve_within_backups_root(backup_path, backups_root)

  if os.path.isdir(resolved):
    backup_dir = resolved
    db_path = os.path.join(backup_dir, BACKUP_DB_FILENAME)
  elif os.path.isfile(resolved):
    db_path = resolved
    backup_dir = os.path.dirname(resolved)
  else:
    raise BackupError(f"指定されたバックアップが見つかりません: {backup_path}")

  if not os.path.isfile(db_path):
    raise BackupError(f"バックアップ内にDBファイルが見つかりません: {db_path}")

  metadata_path = os.path.join(backup_dir, METADATA_FILENAME)
  if not os.path.isfile(metadata_path):
    raise BackupError(f"バックアップのメタデータが見つかりません: {metadata_path}")

  try:
    with open(metadata_path, "r", encoding="utf-8") as f:
      metadata = json.load(f)
  except (OSError, json.JSONDecodeError) as e:
    raise BackupError(f"メタデータの読み込みに失敗しました: {e}") from None

  recorded_hash = metadata.get("sha256")
  actual_hash = _sha256_of_file(db_path)
  hash_matches = bool(recorded_hash) and actual_hash == recorded_hash

  check_result = _check_integrity(db_path)
  integrity_ok = check_result["integrity_check"] == "ok"
  fk_ok = check_result["foreign_key_check_ok"]

  ok = bool(hash_matches and integrity_ok and fk_ok)

  return {
      "ok": ok,
      "backup_dir": backup_dir,
      "db_path": db_path,
      "recorded_sha256": recorded_hash,
      "actual_sha256": actual_hash,
      "hash_matches": hash_matches,
      "integrity_check": check_result["integrity_check"],
      "integrity_ok": integrity_ok,
      "foreign_key_check_ok": fk_ok,
      "foreign_key_violation_count": check_result["foreign_key_violation_count"],
      "table_row_counts": check_result["table_row_counts"],
      "metadata_created_at": metadata.get("created_at"),
  }


def _print_create_result(result, out=None):
  if out is None:
    out = sys.stdout
  metadata = result["metadata"]
  print(f"バックアップを作成しました: {result['backup_dir']}", file=out)
  print(f"  作成日時: {metadata['created_at']}", file=out)
  print(f"  SHA-256: {metadata['sha256']}", file=out)
  print(f"  整合性チェック: {metadata['integrity_check']}", file=out)
  print(
      "  外部キー整合性: "
      + ("問題なし" if metadata["foreign_key_check_ok"] else "違反あり"),
      file=out,
  )
  for table, count in sorted(metadata["table_row_counts"].items()):
    print(f"    {table}: {count}件", file=out)


def _print_verify_result(result, out=None):
  if out is None:
    out = sys.stdout
  print(f"検証対象: {result['db_path']}", file=out)
  print(f"  記録済みハッシュ一致: {'はい' if result['hash_matches'] else 'いいえ'}", file=out)
  print(f"  整合性チェック: {result['integrity_check']}", file=out)
  print(
      "  外部キー整合性: "
      + ("問題なし" if result["foreign_key_check_ok"] else "違反あり"),
      file=out,
  )
  print(f"  総合判定: {'OK' if result['ok'] else 'NG'}", file=out)


def build_arg_parser():
  parser = argparse.ArgumentParser(
      prog="hive_backup.py",
      description=(
          "localhost限定のSQLiteバックアップ・検証CLI(読み取り専用)。"
          f" 対象DBは {DB_NAME} に、バックアップ先は {BACKUPS_ROOT}/ 配下"
          "に固定されている。実DBへの復元(上書き・削除)は行わない。"
      ),
  )
  subparsers = parser.add_subparsers(dest="command", required=True)

  subparsers.add_parser(
      "create",
      help=f"{DB_NAME} の安全なバックアップを {BACKUPS_ROOT}/ 配下に作成する",
  )

  verify_parser = subparsers.add_parser(
      "verify",
      help="指定したバックアップの整合性・ハッシュを検証する(読み取り専用)",
  )
  verify_parser.add_argument(
      "backup_path",
      help=f"{BACKUPS_ROOT}/ 配下のバックアップディレクトリ、またはそのDBファイル",
  )

  return parser


def main(argv=None):
  parser = build_arg_parser()
  args = parser.parse_args(argv)

  try:
    if args.command == "create":
      result = create_backup()
      _print_create_result(result)
      return 0
    if args.command == "verify":
      result = verify_backup(args.backup_path)
      _print_verify_result(result)
      return 0 if result["ok"] else 1
  except BackupError as e:
    print(f"エラー: {e}", file=sys.stderr)
    return 1

  return 1


if __name__ == "__main__":
  sys.exit(main())
