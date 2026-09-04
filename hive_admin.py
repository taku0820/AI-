#!/usr/bin/env python3
"""localhost限定 監査ログ確認CLI（MISSION 015）。

ブラウザへadminトークンを保存せず、ターミナル上で `GET /api/audit-logs`
（admin専用・読み取り専用のHive API。MISSION 014で追加）を安全に呼び出す
ための最小限のCLI。

設計上の安全方針:
  - 接続先は http://127.0.0.1:5050 に固定する。CLI引数・環境変数で
    上書きできる設定は一切追加しない（外部URL・任意URL・リダイレクト先
    への接続を防ぐ）。HTTPリダイレクトも一切追跡しない。
  - adminトークンは環境変数 AI_HIVE_ADMIN_TOKEN からのみ取得する
    （コマンドライン引数では受け取らない。シェル履歴・`ps`出力への
    露出を避けるため）。
  - トークンをコマンドライン引数・標準出力・標準エラー出力・例外
    メッセージ・ファイルへ一切表示・保存しない。
  - 呼び出すのは GET /api/audit-logs のみ。監査ログの作成・更新・削除、
    その他のHive API操作はこのCLIから行わない。

実行例（docs/MISSION015_admin_cli_runbook.md も参照）:
    export AI_HIVE_ADMIN_TOKEN="<admin token>"
    python hive_admin.py --limit 20
    unset AI_HIVE_ADMIN_TOKEN
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# 接続先はlocalhost限定で固定する。CLI引数・環境変数で上書きできる設定は
# 一切追加しない（外部URL・任意URL・リダイレクト先への接続を防ぐため）。
BASE_URL = "http://127.0.0.1:5050"
AUDIT_LOGS_PATH = "/api/audit-logs"

# adminトークンはこの環境変数からのみ取得する。CLI引数では受け取らない。
TOKEN_ENV_VAR = "AI_HIVE_ADMIN_TOKEN"

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

REQUEST_TIMEOUT_SECONDS = 5


class CliError(Exception):
  """CLI利用者にそのまま表示してよいエラーメッセージのみを持つ例外。

  ここに渡す文字列には、トークン・Authorizationヘッダーの値を含めない
  こと（呼び出し側の責務）。
  """


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
  """HTTPリダイレクトを一切追跡しない。

  127.0.0.1:5050以外へ誘導されることを防ぐための安全策
  （自分自身のサーバーはこのAPIでリダイレクトを返さないため、通常は
  発火しない）。
  """

  def redirect_request(self, req, fp, code, msg, headers, newurl):
    raise CliError(
        f"サーバーがリダイレクトを返しました(HTTP {code})。安全のため"
        "追跡しません。"
    )


def _parse_limit(raw_limit):
  """CLI引数の件数指定を検証する。この関数はネットワーク通信を一切行わない。

  不正な指定（整数として解釈できない、または0以下）はCliErrorを送出する。
  MAX_LIMITを超える指定は安全側（上限）に丸める。
  """
  if raw_limit is None:
    return DEFAULT_LIMIT
  try:
    limit = int(raw_limit)
  except (TypeError, ValueError):
    raise CliError("--limit には正の整数を指定してください。")
  if limit <= 0:
    raise CliError("--limit には正の整数を指定してください。")
  if limit > MAX_LIMIT:
    limit = MAX_LIMIT
  return limit


def _get_admin_token(env=None):
  """環境変数からadminトークンを取得する。

  未設定・空文字の場合はネットワーク通信を一切行わずCliErrorを送出する。
  取得したトークンの値そのものは、この関数の戻り値以外のどこにも
  出力しない。
  """
  env = os.environ if env is None else env
  token = env.get(TOKEN_ENV_VAR)
  if not token:
    raise CliError(
        f"環境変数 {TOKEN_ENV_VAR} が設定されていません。"
        "admin権限のトークンを設定してから再実行してください。"
    )
  return token


def _open_url(request_obj):
  """実際のHTTP通信を行う薄いラッパー（テストでモック化するための境界）。"""
  opener = urllib.request.build_opener(_NoRedirectHandler)
  return opener.open(request_obj, timeout=REQUEST_TIMEOUT_SECONDS)


def _safe_json_loads(body_text):
  try:
    return json.loads(body_text)
  except (TypeError, ValueError):
    return None


def fetch_audit_logs(limit, token):
  """GET /api/audit-logs だけを呼び出し、(status_code, body_dict) を返す。

  他のエンドポイント・他のHTTPメソッドは一切使わない。接続失敗・
  タイムアウトはCliErrorとして送出する（トークン・Authorizationヘッダー
  の値はCliErrorのメッセージに含めない）。
  """
  query = urllib.parse.urlencode({"limit": limit})
  url = f"{BASE_URL}{AUDIT_LOGS_PATH}?{query}"
  request_obj = urllib.request.Request(
      url,
      method="GET",
      headers={
          "Authorization": f"Bearer {token}",
          "Accept": "application/json",
      },
  )
  try:
    with _open_url(request_obj) as resp:
      body_text = resp.read().decode("utf-8", errors="replace")
      return resp.status, _safe_json_loads(body_text)
  except urllib.error.HTTPError as e:
    try:
      body_text = e.read().decode("utf-8", errors="replace")
    finally:
      e.close()
    return e.code, _safe_json_loads(body_text)
  except urllib.error.URLError:
    raise CliError(
        f"{BASE_URL} へ接続できませんでした。サーバー(hive_admin.pyが"
        "利用するlocalhost:5050のAPI)が起動しているか確認してください。"
    ) from None
  except TimeoutError:
    raise CliError(f"{BASE_URL} への接続がタイムアウトしました。") from None


def _format_row(row):
  return (
      f"[{row.get('id')}] {row.get('recorded_at')} "
      f"{row.get('event_type')} {row.get('http_method')} "
      f"{row.get('endpoint')} status={row.get('status_code')} "
      f"permission={row.get('permission')} "
      f"summary={row.get('result_summary')}"
  )


def _print_rows(rows, out=None):
  # 呼び出し時点のsys.stdoutを使う(デフォルト引数として束縛すると、
  # テストのcontextlib.redirect_stdoutが効かなくなるため)。
  if out is None:
    out = sys.stdout
  if not rows:
    print("監査ログはありません。", file=out)
    return
  for row in rows:
    print(_format_row(row), file=out)
  print(f"{len(rows)} 件を表示しました。", file=out)


def _print_error_body(status_code, body, out=None):
  # 呼び出し時点のsys.stderrを使う(理由は_print_rowsと同様)。
  if out is None:
    out = sys.stderr
  message = None
  if isinstance(body, dict):
    message = body.get("message")
  if not message:
    message = f"サーバーがエラーを返しました(HTTP {status_code})。"
  print(f"エラー: {message}", file=out)


def build_arg_parser():
  parser = argparse.ArgumentParser(
      prog="hive_admin.py",
      description=(
          "localhost限定の監査ログ確認CLI（読み取り専用）。"
          f" 接続先は {BASE_URL}{AUDIT_LOGS_PATH} に固定されており、"
          "変更するオプションはありません。"
          f" adminトークンは環境変数 {TOKEN_ENV_VAR} から読み取ります"
          "（コマンドライン引数では受け付けません）。"
      ),
  )
  parser.add_argument(
      "--limit",
      default=None,
      help=f"取得件数（既定{DEFAULT_LIMIT}件、最大{MAX_LIMIT}件）",
  )
  return parser


def main(argv=None):
  parser = build_arg_parser()
  args = parser.parse_args(argv)

  try:
    limit = _parse_limit(args.limit)
    token = _get_admin_token()
    status_code, body = fetch_audit_logs(limit, token)
  except CliError as e:
    print(f"エラー: {e}", file=sys.stderr)
    return 1

  if (
      status_code == 200
      and isinstance(body, dict)
      and body.get("status") == "success"
  ):
    _print_rows(body.get("data") or [])
    return 0

  _print_error_body(status_code, body)
  return 1


if __name__ == "__main__":
  sys.exit(main())
