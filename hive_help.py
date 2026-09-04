#!/usr/bin/env python3
"""localhost限定 統合ヘルプ／ナビゲーションCLI（MISSION 022）。

`hive_status.py`・`hive_ops.py`・`hive_backup.py` という既存の安全な
運用ツール群を、どれをどう使えばよいか迷わないように1つの入口から
案内・呼び出しする薄いディスパッチャ。新しい機能は一切追加しない。

設計上の安全方針:
  - 引数なしで実行した場合、またはargparseの `--help`/`-h` を使った
    場合は、利用可能な操作の一覧と説明を表示するだけであり、
    ネットワーク通信・DB操作・バックアップの作成/復元/削除/検証は
    一切行わない（このモジュールをimportした時点でも何も実行されない。
    実際の操作は、利用者が明示的にサブコマンドを指定したときにのみ
    実行される）。
  - 実行できる操作は、以下の4つの読み取り専用・副作用ゼロの操作のみ:
      status         -> hive_status.py の状態確認
      ops            -> hive_ops.py の状態確認(+任意でバックアップ検証)
      backup-list    -> hive_backup.py list (バックアップ一覧・読み取り専用)
      backup-verify  -> hive_backup.py verify <path> (指定バックアップの
                         読み取り専用検証。利用者が明示的にパスを指定
                         した場合のみ実行する)
    いずれも、実体は既存モジュールの `main()` をそのまま呼び出すだけで
    あり、本ファイル独自のネットワーク通信・DB操作・ファイル書き込みは
    一切追加しない。
  - `hive_admin.py`（監査ログ確認CLI）は、呼び出しのたびに`audit_logs`
    へ1件記録するという副作用を持つため、このCLIからは自動実行・
    初期実行・一括実行のいずれも行わない。`admin-info` サブコマンドは
    案内文を表示するだけであり、`hive_admin.py`を呼び出すことも、
    トークンの有無を確認することも一切ない。
  - 常駐・cron・launchd・バックグラウンド自動実行・外部公開・外部通信・
    外部通知は一切実装しない。トークン・秘密情報は一切扱わない
    （このファイル自身が環境変数やAuthorizationヘッダーを参照する
    コードを持たない）。

実行例（docs/MISSION022_help_cli_runbook.md も参照）:
    python hive_help.py
    python hive_help.py status
    python hive_help.py ops --verify-backup backups/backup_20260904_213645_374d29
    python hive_help.py backup-list
    python hive_help.py backup-verify backups/backup_20260904_213645_374d29
    python hive_help.py admin-info
"""

import argparse
import sys

import hive_backup
import hive_ops
import hive_status

MENU_TEXT = """\
localhost限定 統合ヘルプ／ナビゲーションCLI（hive_help.py）

このコマンドは何も実行していません。以下から、実行したい操作を
サブコマンドとして明示的に指定してください。

  1. 状態確認だけを行う(副作用なし)
       python hive_help.py status

  2. 状態確認 + 必要であればバックアップ検証も一緒に行う(副作用なし)
       python hive_help.py ops
       python hive_help.py ops --verify-backup backups/backup_<日時>_<suffix>

  3. 既存バックアップの一覧を見る(読み取り専用・副作用なし)
       python hive_help.py backup-list

  4. 指定したバックアップを検証する(読み取り専用・副作用なし)
       python hive_help.py backup-verify backups/backup_<日時>_<suffix>

  5. 監査ログ確認(hive_admin.py)についての案内を見る(案内のみ・何も実行しない)
       python hive_help.py admin-info

上記のいずれも、対象は http://127.0.0.1:5050 のローカルサーバーと、
プロジェクト内の ai_company.db・backups/ に限定されています。
バックアップの新規作成・実DBへの復元・削除は、このCLIからは一切
実行できません。

各操作の副作用・異常時の確認順序・実復元に必要な承認については
docs/MISSION022_help_cli_runbook.md を参照してください。
"""

ADMIN_INFO_TEXT = """\
監査ログ確認(hive_admin.py)について

hive_admin.py は admin権限のトークンで audit_logs を参照する
読み取り専用CLIですが、呼び出すたびに「その参照操作自体」が
admin操作として audit_logs へ1件記録される、という副作用を持ちます
(MISSION 013以来の仕様であり、不具合ではありません)。

このため hive_help.py からは、hive_admin.py を自動実行・初期実行・
一括実行することは一切ありません。必要な場合は、利用者が明示的に
別途、以下のように直接実行してください（トークンは環境変数から
渡し、コマンドライン引数には含めないでください）:

    export AI_HIVE_ADMIN_TOKEN="<admin token>"
    python hive_admin.py --limit 20
    unset AI_HIVE_ADMIN_TOKEN

詳細な安全な使い方は docs/MISSION015_admin_cli_runbook.md を
参照してください。
"""


def build_arg_parser():
  parser = argparse.ArgumentParser(
      prog="hive_help.py",
      description=(
          "localhost限定の統合ヘルプ／ナビゲーションCLI。既存の"
          "hive_status.py・hive_ops.py・hive_backup.py(list/verify)を"
          "案内・呼び出しするだけの薄いディスパッチャで、新しい操作は"
          "追加しない。引数なし実行・--help表示だけでは何も実行しない。"
      ),
  )
  subparsers = parser.add_subparsers(dest="command")

  subparsers.add_parser(
      "status",
      help="hive_status.py の状態確認を実行する(副作用なし)",
  )

  ops_parser = subparsers.add_parser(
      "ops",
      help="hive_ops.py の状態確認(+任意でバックアップ検証)を実行する(副作用なし)",
  )
  ops_parser.add_argument(
      "--verify-backup",
      metavar="BACKUP_PATH",
      default=None,
      help=(
          f"{hive_backup.BACKUPS_ROOT}/ 配下の既存バックアップを指定すると、"
          "状態確認に加えてその検証も一緒に行う(読み取り専用)"
      ),
  )

  subparsers.add_parser(
      "backup-list",
      help="backups/ 配下の既存バックアップを一覧表示する(読み取り専用)",
  )

  backup_verify_parser = subparsers.add_parser(
      "backup-verify",
      help="指定した既存バックアップを検証する(読み取り専用)",
  )
  backup_verify_parser.add_argument(
      "backup_path",
      help=f"{hive_backup.BACKUPS_ROOT}/ 配下の既存バックアップディレクトリ、またはそのDBファイル",
  )

  subparsers.add_parser(
      "admin-info",
      help="hive_admin.py(監査ログ確認)についての案内だけを表示する(何も実行しない)",
  )

  return parser


def main(argv=None):
  parser = build_arg_parser()
  args = parser.parse_args(argv)

  if args.command is None:
    print(MENU_TEXT, end="")
    return 0

  if args.command == "status":
    # hive_status.py自身の実装(接続先固定・副作用なし)にそのまま従う。
    return hive_status.main([])

  if args.command == "ops":
    ops_argv = []
    if args.verify_backup is not None:
      ops_argv = ["--verify-backup", args.verify_backup]
    # hive_ops.py自身の実装(状態確認+任意のバックアップ検証)にそのまま従う。
    return hive_ops.main(ops_argv)

  if args.command == "backup-list":
    # hive_backup.py list自身の実装(読み取り専用、DBを開かない)にそのまま従う。
    return hive_backup.main(["list"])

  if args.command == "backup-verify":
    # hive_backup.py verify自身の実装(読み取り専用)にそのまま従う。
    return hive_backup.main(["verify", args.backup_path])

  if args.command == "admin-info":
    # hive_admin.pyは一切呼び出さない。案内文を表示するだけ。
    print(ADMIN_INFO_TEXT, end="")
    return 0

  # argparseのサブコマンド定義外の値が来ることは通常ないが、念のため
  # 安全側で失敗させる。
  print(f"エラー: 不明なコマンドです: {args.command}", file=sys.stderr)
  return 1


if __name__ == "__main__":
  sys.exit(main())
