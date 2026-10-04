"""AI Hive OS ダッシュボード(運用記録・投稿候補)用のローカル永続化。

MISSION 088: これまでブラウザごとのlocalStorageだけに保存していた
「本日の運用記録」(運用司令室)と「楽天ROOM・noteの投稿候補」を、
同じMac上で動くこのFlaskアプリ内のSQLite(既存のai_company.db)へも
保存できるようにする。

MISSION 089: post_candidatesに、楽天ROOM候補を「今日・今週・保留」に
整理するための`bucket`列を追加する。すでにMISSION 088時点のDBで
post_candidatesテーブルが存在する環境でも安全に動くよう、
CREATE TABLE IF NOT EXISTS(新規DB用)とは別に、既存テーブルへは
ALTER TABLE ADD COLUMN(列がまだ無い場合のみ)で移行する。既存の行は
一切削除・上書きせず、bucket列だけが'hold'(保留)で追加される。

安全方針:
- 既存のai_company.db・work_logsテーブル・hive_db.pyの7テーブルには
  一切手を加えない(CREATE TABLE IF NOT EXISTSで新規2テーブルのみ追加)。
- ここで追加するAPI(/api/dashboard/*)は、このアプリ自身の画面(同一
  オリジン)から呼び出される前提のローカル専用JSONエンドポイントであり、
  外部サービスへの通信・ログイン・認証トークンの発行は一切行わない
  (既存のGET /api/logsと同じく無認証で、127.0.0.1限定で待ち受ける
  Flaskプロセス内だけで完結する)。
- 楽天ROOM・楽天アフィリエイト・note・Pinterest・Threadsへの投稿・送信・
  ログイン・スクレイピング・外部API通信は一切行わない。利用者がブラウザ
  経由で入力・保存した内容をそのままこのDBへ書き写すだけ。
"""

import json
import sqlite3
import threading

from flask import jsonify, request

DB_NAME = "ai_company.db"

# MISSION 088: 既存のwork_logs(init_db.py)・employees/missions/...
# (hive_db.py)とは独立した2テーブルだけを追加する。
SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL,
    media TEXT NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    metric TEXT,
    reference TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS post_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    target_date TEXT NOT NULL,
    media TEXT NOT NULL,
    slot INTEGER,
    genre TEXT,
    product_name TEXT,
    url TEXT,
    intro TEXT,
    hashtags TEXT,
    manual_checked INTEGER NOT NULL DEFAULT 0,
    manual_posted INTEGER NOT NULL DEFAULT 0,
    bucket TEXT NOT NULL DEFAULT 'hold',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

# MISSION 089: 候補の整理区分。「今日」「今週」「保留」の3つだけを許可し、
# それ以外の値は無視する(無効な値でUPDATEしても既存値を変えない、INSERT
# 時は'hold'にする)。
BUCKET_VALUES = ("today", "week", "hold")
BUCKET_DEFAULT = "hold"

# sqlite3接続はスレッドごとに作り直す(Flask開発サーバーはリクエストごとに
# 別スレッドで処理されうるため、1つのconnectionを使い回さない)。書き込みの
# 競合はこのロックで直列化する(開発用途のローカルSQLiteとしては十分)。
_LOCK = threading.Lock()


def get_connection():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  return conn


def _ensure_post_candidates_bucket_column(conn):
  """MISSION 089: MISSION 088時点で作られたpost_candidatesテーブル(bucket
  列なし)が既に存在する環境でも安全に動く移行。列が無いときだけADD COLUMN
  する(既存の行・他の列は一切変更しない)。CREATE TABLE IF NOT EXISTSは
  テーブルが無い場合にしか列を追加できないため、この移行が必要になる。
  """
  cols = {
      row[1]
      for row in conn.execute("PRAGMA table_info(post_candidates)").fetchall()
  }
  if "bucket" not in cols:
    conn.execute(
        "ALTER TABLE post_candidates ADD COLUMN bucket TEXT NOT NULL"
        f" DEFAULT '{BUCKET_DEFAULT}'"
    )


def init_schema():
  with _LOCK:
    conn = get_connection()
    try:
      conn.executescript(SCHEMA)
      _ensure_post_candidates_bucket_column(conn)
      conn.commit()
    finally:
      conn.close()


def _normalize_bucket(bucket):
  """有効な区分('today'/'week'/'hold')ならそのまま返し、未指定・無効な値は
  Noneを返す(呼び出し側でNoneは「変更しない」の意味として扱う)。"""
  if bucket in BUCKET_VALUES:
    return bucket
  return None


def _norm(value):
  return (value or "").strip()


def _daily_record_dedup_key(date, media, type_, content):
  return "|".join([_norm(date), _norm(media), _norm(type_), _norm(content)])


def _candidate_dedup_key(target_date, media, slot, product_name):
  # 毎日の候補(ROOM・note)はdate+media+slotで1枠につき1件に定まるため、
  # それを一意キーにする(slot未指定の場合だけ商品名で代替する)。
  slot_part = str(slot) if slot is not None and slot != "" else ("name:" + _norm(product_name))
  return "|".join([_norm(target_date), _norm(media), slot_part])


def insert_daily_record(date, media, type_, content, metric="", reference=""):
  """本日の運用記録を1件追加する(重複はスキップ)。

  重複判定キー: date+media+type+content が完全一致する既存行がある場合は
  INSERT OR IGNOREにより新規行を作らない(同じ内容を何度移行しても件数が
  増えないようにするため)。
  """
  if not _norm(date) or not _norm(media) or not _norm(type_) or not _norm(content):
    return {"inserted": False, "reason": "missing_required_field"}
  key = _daily_record_dedup_key(date, media, type_, content)
  with _LOCK:
    conn = get_connection()
    try:
      cur = conn.execute(
          "INSERT OR IGNORE INTO daily_records"
          " (dedup_key, date, media, type, content, metric, reference)"
          " VALUES (?, ?, ?, ?, ?, ?, ?)",
          (key, _norm(date), _norm(media), _norm(type_), _norm(content),
           metric or "", reference or ""),
      )
      conn.commit()
      return {"inserted": cur.rowcount > 0}
    finally:
      conn.close()


def list_daily_records(date=None):
  with _LOCK:
    conn = get_connection()
    try:
      if date:
        rows = conn.execute(
            "SELECT * FROM daily_records WHERE date=? ORDER BY id ASC", (date,)
        ).fetchall()
      else:
        rows = conn.execute(
            "SELECT * FROM daily_records ORDER BY date DESC, id DESC"
        ).fetchall()
      return [dict(r) for r in rows]
    finally:
      conn.close()


def upsert_post_candidate(target_date, media, slot, genre, product_name, url,
                           intro, hashtags, manual_checked, manual_posted,
                           bucket=None):
  """投稿候補を1件保存する(同じ対象日・媒体・枠番号ならUPDATE、なければ
  INSERT=重複を増やさない)。

  MISSION 089: bucket('today'/'week'/'hold')は「今日・今週・保留」の整理
  区分。Noneまたは無効な値を渡した場合、UPDATE時は既存のbucketをそのまま
  維持し(例:「手動投稿を完了した」ボタンはbucketを送らないため、直前まで
  の整理区分を消さない)、INSERT時(=初めて保存する候補)は'hold'(保留)に
  する(既存候補は初期状態では保留として扱うという要件どおり)。
  """
  if not _norm(target_date) or not _norm(media):
    return {"inserted": False, "updated": False, "reason": "missing_required_field"}
  key = _candidate_dedup_key(target_date, media, slot, product_name)
  hashtags_json = json.dumps(list(hashtags or []), ensure_ascii=False)
  slot_value = None
  try:
    slot_value = int(slot) if slot is not None and slot != "" else None
  except (TypeError, ValueError):
    slot_value = None
  normalized_bucket = _normalize_bucket(bucket)
  with _LOCK:
    conn = get_connection()
    try:
      existing = conn.execute(
          "SELECT id FROM post_candidates WHERE dedup_key=?", (key,)
      ).fetchone()
      if existing:
        conn.execute(
            "UPDATE post_candidates SET genre=?, product_name=?, url=?,"
            " intro=?, hashtags=?, manual_checked=?, manual_posted=?,"
            " bucket=COALESCE(?, bucket),"
            " updated_at=datetime('now','localtime') WHERE dedup_key=?",
            (genre or "", product_name or "", url or "", intro or "",
             hashtags_json, int(bool(manual_checked)), int(bool(manual_posted)),
             normalized_bucket, key),
        )
        conn.commit()
        return {"inserted": False, "updated": True}
      conn.execute(
          "INSERT INTO post_candidates"
          " (dedup_key, target_date, media, slot, genre, product_name, url,"
          "  intro, hashtags, manual_checked, manual_posted, bucket)"
          " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
          (key, _norm(target_date), _norm(media), slot_value, genre or "",
           product_name or "", url or "", intro or "", hashtags_json,
           int(bool(manual_checked)), int(bool(manual_posted)),
           normalized_bucket or BUCKET_DEFAULT),
      )
      conn.commit()
      return {"inserted": True, "updated": False}
    finally:
      conn.close()


def list_post_candidates(target_date=None):
  with _LOCK:
    conn = get_connection()
    try:
      if target_date:
        rows = conn.execute(
            "SELECT * FROM post_candidates WHERE target_date=? ORDER BY id ASC",
            (target_date,),
        ).fetchall()
      else:
        rows = conn.execute(
            "SELECT * FROM post_candidates ORDER BY target_date DESC, id DESC"
        ).fetchall()
      result = []
      for r in rows:
        row = dict(r)
        try:
          row["hashtags"] = json.loads(row.get("hashtags") or "[]")
        except (TypeError, ValueError):
          row["hashtags"] = []
        result.append(row)
      return result
    finally:
      conn.close()


def migrate_from_payload(records, candidates):
  """localStorageから読み取った記録・候補をまとめて保存する(移行操作)。

  既存のlocalStorageデータは一切削除しない(呼び出し側のJSが読むだけ)。
  重複は各insert/upsert関数内のdedup_keyでスキップ・上書きされる。
  """
  rec_inserted = 0
  rec_skipped = 0
  for r in records or []:
    if not isinstance(r, dict):
      continue
    result = insert_daily_record(
        r.get("date"), r.get("media"), r.get("type"), r.get("content"),
        r.get("metric", ""), r.get("reference", ""),
    )
    if result.get("inserted"):
      rec_inserted += 1
    else:
      rec_skipped += 1

  cand_inserted = 0
  cand_skipped = 0
  for c in candidates or []:
    if not isinstance(c, dict):
      continue
    result = upsert_post_candidate(
        c.get("targetDate"), c.get("media"), c.get("slot"), c.get("genre", ""),
        c.get("productName", ""), c.get("url", ""), c.get("intro", ""),
        c.get("hashtags", []), c.get("manualChecked", False),
        c.get("manualPosted", False), bucket=c.get("bucket"),
    )
    if result.get("inserted"):
      cand_inserted += 1
    else:
      cand_skipped += 1

  return {
      "records": {"inserted": rec_inserted, "skipped": rec_skipped},
      "candidates": {"inserted": cand_inserted, "skipped": cand_skipped},
  }


def _record_row_to_json(row):
  return {
      "date": row.get("date", ""),
      "media": row.get("media", ""),
      "type": row.get("type", ""),
      "content": row.get("content", ""),
      "metric": row.get("metric", "") or "",
      "reference": row.get("reference", "") or "",
  }


def register_dashboard_api(app):
  """DB駆動の運用記録・投稿候補APIをFlaskアプリへ登録する。

  すべて同一オリジン(localhost)からの呼び出しのみを想定した表示専用+
  手動保存用のエンドポイントで、外部サービスへの通信は一切行わない。
  GET /api/logs と同様に認証を要求しない(新しいログイン機構は追加しない)。
  """
  init_schema()

  @app.route("/api/dashboard/daily-records", methods=["GET", "POST"])
  def dashboard_daily_records():
    if request.method == "POST":
      data = request.get_json(silent=True) or {}
      result = insert_daily_record(
          data.get("date"), data.get("media"), data.get("type"),
          data.get("content"), data.get("metric", ""), data.get("reference", ""),
      )
      return jsonify(result)
    date = request.args.get("date")
    rows = list_daily_records(date)
    return jsonify({"records": [_record_row_to_json(r) for r in rows]})

  @app.route("/api/dashboard/candidates", methods=["GET", "POST"])
  def dashboard_candidates():
    if request.method == "POST":
      data = request.get_json(silent=True) or {}
      result = upsert_post_candidate(
          data.get("targetDate"), data.get("media"), data.get("slot"),
          data.get("genre", ""), data.get("productName", ""), data.get("url", ""),
          data.get("intro", ""), data.get("hashtags", []),
          data.get("manualChecked", False), data.get("manualPosted", False),
          bucket=data.get("bucket"),
      )
      return jsonify(result)
    target_date = request.args.get("targetDate")
    return jsonify({"candidates": list_post_candidates(target_date)})

  @app.route("/api/dashboard/migrate", methods=["POST"])
  def dashboard_migrate():
    data = request.get_json(silent=True) or {}
    result = migrate_from_payload(data.get("records", []), data.get("candidates", []))
    return jsonify(result)
