#!/usr/bin/env python3
"""localhost限定 日常運用保守CLI（MISSION 019）。

既存の `hive_status.py`（副作用のない状態確認）と `hive_backup.py`
（既存バックアップの読み取り専用検証）を、人が明示的に実行したときだけ
一貫した結果表示でまとめて確認できるようにする、薄いラッパーCLI。

設計上の安全方針:
  - 人が明示的にコマンドを実行したときだけ動く。常駐プロセス・cron・
    launchd・バックグラウンド自動実行・外部通知は一切実装しない
    （このスクリプトは1回実行して終了するだけであり、スケジューラー
    登録や自己再実行の仕組みは持たない）。
  - 状態確認は `hive_status.run_all_checks()` をそのまま呼び出すだけ
    であり、独自のネットワーク通信・DB操作は一切追加しない。接続先
    （`http://127.0.0.1:5050`固定・リダイレクト非追従・Authorization
    ヘッダー送信なし）や副作用ゼロという性質は `hive_status.py` 側の
    実装にそのまま従う（本ファイルはこれを一切変更しない）。
  - バックアップに関して行うのは、指定した既存バックアップの検証
    （`hive_backup.verify_backup()`、読み取り専用）だけである。
    新規バックアップの作成・実DBへの復元・バックアップの削除は、
    このCLIからは一切実行できない（そもそも呼び出していない）。
  - `--verify-backup` を指定しない場合は状態確認のみを行う。指定した
    場合は、状態確認の結果に続けて、同一の表示形式でバックアップ検証
    結果を1行追加する（「一貫した結果表示」）。
  - いずれの確認が失敗した場合も、Pythonの例外トレースバックを外へ
    漏らさず、`[NG] <項目名>: <安全な理由>` の形式で表示し、最終的な
    終了コードは 0(総合OK) / 1(総合NG) のいずれかにする。

実行例（docs/MISSION019_ops_cli_runbook.md も参照）:
    python hive_ops.py
    python hive_ops.py --verify-backup backups/backup_20260904_213645_374d29
"""

import argparse
import sys

import hive_backup
import hive_status


def run_backup_verification(backup_path):
  """指定されたバックアップを hive_backup.verify_backup() で検証する。

  読み取り専用。新規バックアップの作成・実DBへの復元・削除は一切行わ
  ない（そもそも呼び出さない）。失敗はすべて捕捉し、例外を外へ漏らさず
  結果辞書として返す。
  """
  name = f"backup_verify ({backup_path})"
  try:
    result = hive_backup.verify_backup(backup_path)
  except hive_backup.BackupError as e:
    return {"name": name, "ok": False, "detail": str(e)}
  except Exception as e:  # pylint: disable=broad-except
    # verify_backup自体は読み取り専用のためデータを壊す心配はないが、
    # 想定外の例外(例: 権限エラー等)もトレースバックを見せずに安全な
    # NG表示へ変換する。
    return {
        "name": name, "ok": False,
        "detail": f"検証中に予期しないエラーが発生しました: {e}",
    }

  detail = (
      f"hash_matches={result['hash_matches']}, "
      f"integrity_check={result['integrity_check']}, "
      f"foreign_key_check_ok={result['foreign_key_check_ok']}"
  )
  return {"name": name, "ok": result["ok"], "detail": detail}


def run_checks(backup_path=None):
  """状態確認(常時)＋バックアップ検証(backup_path指定時のみ)を実行する。

  この関数自体は状態確認・検証以外の操作(作成・復元・削除・書き込み)を
  一切行わない。
  """
  results = list(hive_status.run_all_checks())
  if backup_path is not None:
    results.append(run_backup_verification(backup_path))
  return results


def _print_report(results, out=None):
  """hive_status.py と同じ表示形式で結果をまとめて出力する。

  状態確認のみのときも、バックアップ検証を含めたときも、同じ形式・
  同じ総合判定ロジックで表示することで「一貫した結果表示」とする。
  """
  if out is None:
    out = sys.stdout
  for result in results:
    mark = "OK" if result["ok"] else "NG"
    print(f"[{mark}] {result['name']}: {result['detail']}", file=out)
    if result.get("note"):
      print(f"      ※ {result['note']}", file=out)
    if "table_row_counts" in result:
      for table, count in sorted(result["table_row_counts"].items()):
        print(f"      {table}: {count}件", file=out)
  overall_ok = all(
      result["ok"] for result in results if result.get("critical", True)
  )
  print(f"総合判定: {'OK' if overall_ok else 'NG'}", file=out)
  return overall_ok


def build_arg_parser():
  parser = argparse.ArgumentParser(
      prog="hive_ops.py",
      description=(
          "localhost限定の薄い運用保守CLI。hive_status.py(状態確認)と"
          "hive_backup.py verify(既存バックアップの読み取り専用検証)を"
          "人が明示的に実行したときだけ、一貫した結果表示でまとめて"
          "確認できる。常駐・cron・launchd・バックグラウンド自動実行・"
          "外部通知は行わない。バックアップの新規作成・実DBへの復元・"
          "削除はこのCLIからは一切実行できない。"
      ),
  )
  parser.add_argument(
      "--verify-backup",
      metavar="BACKUP_PATH",
      default=None,
      help=(
          "backups/配下の既存バックアップディレクトリ(またはそのDB"
          "ファイル)を指定すると、状態確認に加えてその検証も同じ結果"
          "表示で実行する。省略時は状態確認のみを行う。"
      ),
  )
  return parser


def main(argv=None):
  parser = build_arg_parser()
  args = parser.parse_args(argv)

  results = run_checks(backup_path=args.verify_backup)
  overall_ok = _print_report(results)
  return 0 if overall_ok else 1


if __name__ == "__main__":
  sys.exit(main())
