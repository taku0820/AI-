#!/usr/bin/env python3
"""localhost限定 読み取り専用ヘルスチェック／状態確認CLI（MISSION 018）。

ローカルで動いている `app.py`（AI Hive OS）とDB（`ai_company.db`）の
稼働状態を、副作用なしで安全に確認するための最小限のCLI。

設計上の安全方針:
  - 接続先は `http://127.0.0.1:5050` にコード上で固定する。CLI引数・
    環境変数で変更できる設定は一切追加しない。HTTPリダイレクトも
    一切追跡しない（`hive_admin.py` と同じ方針）。
  - HTTP経由で確認するのは、認証不要かつ監査ログ(`audit_logs`)への
    記録が発生しない既存2エンドポイント `GET /`・`GET /api/logs` の
    みに限定する。`hive_db.require_permission` で保護された新規Hive
    API（`/api/employees` 等、`GET /api/audit-logs` を含む）は、成功
    する呼び出しであっても `audit_logs` へ1件記録するという副作用を
    伴うため、意図的に一切呼び出さない（「既存サーバーへ副作用のない
    確認だけを行う」という要件を満たすため）。
  - DBの状態（整合性・外部キー整合性・想定テーブルの有無・件数）は、
    HTTP経由ではなく `ai_company.db` への読み取り専用接続
    （`file:...?mode=ro` のSQLite URI接続）で直接確認する。書き込みは
    一切行わない。
  - Hive API用トークンの環境変数（`AI_HIVE_READ_TOKEN` 等）について
    確認するのは「このCLIプロセス自身の環境に設定されているか否か」
    のみであり、値そのものは一切取得・表示・保存しない。
  - 接続失敗・タイムアウト・想定外のHTTPステータス・不正なレスポンス
    形式は、いずれも例外を外へ漏らさず、安全で分かりやすいメッセージ
    として結果に含める。

実行例（docs/MISSION018_status_check_runbook.md も参照）:
    python hive_status.py
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

# 接続先・対象DBはどちらも固定する。CLI引数・環境変数で変更できる設定は
# 一切追加しない（外部URL・任意URLへの接続や、意図しないDBの参照を
# 防ぐため）。
BASE_URL = "http://127.0.0.1:5050"
DB_NAME = "ai_company.db"

REQUEST_TIMEOUT_SECONDS = 5

# Hive OSが管理する全テーブル（work_logsと、MISSION 005以降で追加した
# 7テーブル、MISSION 013で追加したaudit_logs）。存在確認・件数確認のみに
# 使い、書き込みは一切行わない。
EXPECTED_TABLES = [
    "work_logs", "employees", "missions", "tasks", "metrics", "reports",
    "proposals", "decisions", "audit_logs",
]

# 値そのものは一切読み取り内容として扱わない。「設定されているか否か」
# の確認にのみ使う環境変数名の一覧。
TOKEN_ENV_VARS = ("AI_HIVE_READ_TOKEN", "AI_HIVE_WRITE_TOKEN", "AI_HIVE_ADMIN_TOKEN")


class StatusCheckError(Exception):
  """利用者にそのまま表示してよいエラーメッセージのみを持つ例外。

  ここに渡す文字列には、トークン・Authorizationヘッダーの値を含めない
  こと（呼び出し側の責務）。
  """


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
  """HTTPリダイレクトを一切追跡しない（127.0.0.1:5050以外への誘導を防ぐ）。"""

  def redirect_request(self, req, fp, code, msg, headers, newurl):
    raise StatusCheckError(
        f"サーバーがリダイレクトを返しました(HTTP {code})。安全のため"
        "追跡しません。"
    )


def _open_url(request_obj):
  """実際のHTTP通信を行う薄いラッパー（テストでモック化するための境界）。"""
  opener = urllib.request.build_opener(_NoRedirectHandler)
  return opener.open(request_obj, timeout=REQUEST_TIMEOUT_SECONDS)


def _http_get(url):
  """GETリクエストのみを送り、(status_code, body_text) を返す。

  トークン・Authorizationヘッダーは一切付与しない（対象は認証不要の
  既存エンドポイントのみのため）。接続失敗・タイムアウトは
  StatusCheckErrorとして送出する。
  """
  request_obj = urllib.request.Request(url, method="GET")
  try:
    with _open_url(request_obj) as resp:
      body_text = resp.read().decode("utf-8", errors="replace")
      return resp.status, body_text
  except urllib.error.HTTPError as e:
    try:
      body_text = e.read().decode("utf-8", errors="replace")
    finally:
      e.close()
    return e.code, body_text
  except urllib.error.URLError:
    raise StatusCheckError(
        f"{BASE_URL} へ接続できませんでした。サーバー(app.py)が"
        "起動しているか確認してください。"
    ) from None
  except TimeoutError:
    raise StatusCheckError(f"{BASE_URL} への接続がタイムアウトしました。") from None


def check_root_page():
  """GET / を確認する（既存ルート。認証不要・副作用なし）。"""
  name = "root_page (GET /)"
  try:
    status_code, body_text = _http_get(f"{BASE_URL}/")
  except StatusCheckError as e:
    return {"name": name, "ok": False, "detail": str(e)}

  if status_code != 200:
    return {
        "name": name, "ok": False,
        "detail": f"想定外のHTTPステータスでした: {status_code}",
    }
  if "会社の全体像ダッシュボード" not in body_text:
    return {
        "name": name, "ok": False,
        "detail": "想定していないレスポンス内容でした(ダッシュボードのHTMLではない可能性)。",
    }
  return {"name": name, "ok": True, "detail": f"OK (HTTP {status_code})"}


def check_logs_api():
  """GET /api/logs を確認する（既存ルート。認証不要・副作用なし）。"""
  name = "logs_api (GET /api/logs)"
  try:
    status_code, body_text = _http_get(f"{BASE_URL}/api/logs")
  except StatusCheckError as e:
    return {"name": name, "ok": False, "detail": str(e)}

  if status_code != 200:
    return {
        "name": name, "ok": False,
        "detail": f"想定外のHTTPステータスでした: {status_code}",
    }
  try:
    data = json.loads(body_text)
  except (TypeError, ValueError):
    return {
        "name": name, "ok": False,
        "detail": "レスポンスが不正なJSON形式でした。",
    }
  if not isinstance(data, list):
    return {
        "name": name, "ok": False,
        "detail": "レスポンス形式が想定と異なります(配列ではありません)。",
    }
  return {"name": name, "ok": True, "detail": f"OK ({len(data)}件, HTTP {status_code})"}


def check_database(db_path=None):
  """ai_company.dbの状態を読み取り専用で確認する（書き込みは一切行わない）。

  確認内容: ファイルの存在、PRAGMA integrity_check、
  PRAGMA foreign_key_check、想定テーブル(EXPECTED_TABLES)の有無と件数。
  """
  db_path = DB_NAME if db_path is None else db_path
  name = f"database ({db_path})"

  if not os.path.isfile(db_path):
    return {"name": name, "ok": False, "detail": f"DBファイルが見つかりません: {db_path}"}

  uri = f"file:{os.path.abspath(db_path)}?mode=ro"
  try:
    conn = sqlite3.connect(uri, uri=True)
  except sqlite3.Error as e:
    return {"name": name, "ok": False, "detail": f"DBへ接続できませんでした: {e}"}

  try:
    try:
      integrity_result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as e:
      return {"name": name, "ok": False, "detail": f"整合性チェックに失敗しました: {e}"}

    try:
      fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.DatabaseError as e:
      return {"name": name, "ok": False, "detail": f"外部キー整合性チェックに失敗しました: {e}"}

    existing_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing_tables = [t for t in EXPECTED_TABLES if t not in existing_tables]

    table_row_counts = {}
    for table in EXPECTED_TABLES:
      if table in existing_tables:
        table_row_counts[table] = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
  finally:
    conn.close()

  integrity_ok = integrity_result == "ok"
  fk_ok = len(fk_violations) == 0
  tables_ok = not missing_tables
  ok = bool(integrity_ok and fk_ok and tables_ok)

  detail_parts = [
      f"integrity_check={integrity_result}",
      f"foreign_key_violations={len(fk_violations)}",
  ]
  if missing_tables:
    detail_parts.append(f"不足テーブル={missing_tables}")
  return {
      "name": name,
      "ok": ok,
      "detail": ", ".join(detail_parts),
      "table_row_counts": table_row_counts,
  }


def check_token_env_presence(env=None):
  """Hive API用トークンの環境変数が、このCLIプロセス自身に設定されて

  いるか(値そのものは見ない)を確認する。サーバー側(app.pyを起動して
  いる別プロセス・別ターミナル)の設定を保証するものではない。
  """
  env = os.environ if env is None else env
  name = "token_env_presence (このCLIプロセス自身の環境変数)"
  presence = {var: bool(env.get(var)) for var in TOKEN_ENV_VARS}
  ok = all(presence.values())
  detail = ", ".join(
      f"{var}={'設定済み' if is_set else '未設定'}"
      for var, is_set in presence.items()
  )
  return {
      "name": name,
      "ok": ok,
      "detail": detail,
      "note": (
          "値そのものは表示していません。サーバー側の設定確認では"
          "なく、参考情報のため総合判定には含めません。"
      ),
      # このCLIプロセス自身の環境変数設定は、サーバーの稼働状態を示す
      # ものではない参考情報のため、総合判定(overall_ok)には含めない。
      "critical": False,
  }


def run_all_checks(db_path=None, env=None):
  """全チェックを実行し、結果のリストを返す（この関数自体は副作用を持たない）。"""
  return [
      check_root_page(),
      check_logs_api(),
      check_database(db_path=db_path),
      check_token_env_presence(env=env),
  ]


def _print_report(results, out=None):
  if out is None:
    out = sys.stdout
  for result in results:
    mark = "OK" if result["ok"] else "NG"
    print(f"[{mark}] {result['name']}: {result['detail']}", file=out)
    if "note" in result:
      print(f"      ※ {result['note']}", file=out)
    if "table_row_counts" in result:
      for table, count in sorted(result["table_row_counts"].items()):
        print(f"      {table}: {count}件", file=out)
  overall_ok = all(result["ok"] for result in results if result.get("critical", True))
  print(f"総合判定: {'OK' if overall_ok else 'NG'}", file=out)
  return overall_ok


def build_arg_parser():
  parser = argparse.ArgumentParser(
      prog="hive_status.py",
      description=(
          "localhost限定の読み取り専用ヘルスチェックCLI。"
          f" 接続先は {BASE_URL} に、対象DBは {DB_NAME} に固定されており、"
          "変更するオプションはない。副作用のある操作は一切行わない。"
      ),
  )
  return parser


def main(argv=None):
  parser = build_arg_parser()
  parser.parse_args(argv)

  results = run_all_checks()
  overall_ok = _print_report(results)
  return 0 if overall_ok else 1


if __name__ == "__main__":
  sys.exit(main())
