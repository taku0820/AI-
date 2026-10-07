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

MISSION 090: 媒体を問わない共通の「作業台帳」(work_items)を追加する。
運用司令室から手動で追加した作業と、既存の楽天ROOM投稿候補のうち
「今日・今週」に割り当て済みの未完了候補を安全に連携したものの両方を、
1つのテーブルにまとめる。既存のpost_candidatesの行は一切削除・重複作成
せず、連携はcandidate_id列を介した参照+dedup_key("candidate:<id>")に
よる冪等なUPSERTで行う(保留候補は一度も今日/今週になっていない限り
work_itemsへ作成しない)。作業の完了(status='done')は、利用者が明示的に
完了操作をした場合のみ保存し、外部投稿の有無を推測・自動判定しない。

MISSION 091: 収益化ボード・AIオフィスの分析表示(葵)を実績数値で動かす
ための「実績スナップショット」(metric_snapshots)を追加する。日付・媒体・
指標の組み合わせごとに、利用者が手入力した数値を1件ずつ保存する(同じ
日・媒体・指標の再保存は、重複を増やさず最新の値へ安全に更新する)。
数値が空欄の指標は保存自体をスキップし、1件も値が無い場合は保存しない。
外部サービスからの自動取得・スクレイピング・ログイン・投稿・送信・
ブラウザ自動操作は一切行わない。

MISSION 092: ai_company.dbのローカル世代バックアップを、既存の
hive_backup.py(MISSION 016のSQLite Online Backup API・整合性検証済み)に
委譲して自動化する。DBへの書き込みが成功した後、当日分のバックアップが
まだ無ければ1回だけ自動作成し、新しいバックアップの整合性を確認してから
直近7世代を超えた「この機能が作成したバックアップ」だけを整理する(手動
スナップショット等、他の方法で作られたバックアップには一切触れない)。
バックアップの作成・整理に失敗しても、呼び出し元の運用記録・投稿候補・
作業台帳・実績数値の保存自体は失敗させない(例外を外へ伝播させない)。
MISSION 092時点では復元(既存DBの上書き)は対象外だった。

MISSION 093: 誤操作を防ぎながら、ai_company.dbをバックアップから復元
できるようにする。復元候補は、hive_backup.verify_backup()で実際に
再検証して整合性が確認できたものだけに絞る(作成時点のmetadata.jsonの
記録を鵜呑みにせず、改ざん・破損を見逃さない)。復元の実行は、利用者が
対象を選び、確認文言(RESTORE_CONFIRMATION_PHRASE)を正確に入力した場合
だけ、hive_backup.restore_backup()経由で行う。復元直前には必ず現在のDBを
「復元前バックアップ」として作成し、復元元とあわせて世代整理から保護する。
確認文言の不一致・無効な対象・整合性NGのバックアップは、DBを一切変更
せず理由を返す。

安全方針:
- 既存のai_company.db・work_logsテーブル・hive_db.pyの7テーブルには
  一切手を加えない(CREATE TABLE IF NOT EXISTSで新規テーブルのみ追加)。
- ここで追加するAPI(/api/dashboard/*)は、このアプリ自身の画面(同一
  オリジン)から呼び出される前提のローカル専用JSONエンドポイントであり、
  外部サービスへの通信・ログイン・認証トークンの発行は一切行わない
  (既存のGET /api/logsと同じく無認証で、127.0.0.1限定で待ち受ける
  Flaskプロセス内だけで完結する)。
- 楽天ROOM・楽天アフィリエイト・note・Pinterest・Threadsへの投稿・送信・
  ログイン・スクレイピング・外部API通信は一切行わない。利用者がブラウザ
  経由で入力・保存した内容をそのままこのDBへ書き写すだけ。
"""

import datetime
import json
import os
import sqlite3
import threading

from flask import jsonify, request

# MISSION 092: バックアップ作成・検証・一覧は、既存のhive_backup.py
# (MISSION 016、SQLite Online Backup APIを使う安全な実装)にそのまま委譲
# する(ロジックを重複実装しない)。hive_backup.pyはこのモジュールに
# 依存しないため、循環importにはならない。
import hive_backup

DB_NAME = "ai_company.db"

# MISSION 092: バックアップ先ディレクトリ・保持世代数。hive_backup.py側の
# 同名デフォルト(BACKUPS_ROOT="backups")と一致させつつ、テスト時にこの
# モジュールの値だけを差し替えて本番のbackups/・ai_company.dbに一切触れず
# 検証できるよう、独立した変数として持つ(DB_NAMEと同じ考え方)。
BACKUPS_ROOT = "backups"
BACKUP_RETENTION_COUNT = 7

# MISSION 093: 復元実行に必須の確認文言。利用者がこの文字列と完全に一致する
# テキストを入力した場合だけ、サーバー側がDBの復元(上書き)を実行する。
RESTORE_CONFIRMATION_PHRASE = "復元する"

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

CREATE TABLE IF NOT EXISTS work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    media TEXT NOT NULL,
    task_name TEXT NOT NULL,
    assignee TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'today',
    priority INTEGER NOT NULL DEFAULT 5,
    candidate_id INTEGER,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL,
    media TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

# MISSION 089: 候補の整理区分。「今日」「今週」「保留」の3つだけを許可し、
# それ以外の値は無視する(無効な値でUPDATEしても既存値を変えない、INSERT
# 時は'hold'にする)。
BUCKET_VALUES = ("today", "week", "hold")
BUCKET_DEFAULT = "hold"

# MISSION 090: 作業台帳(work_items)の状態。'done'(完了)は、利用者が明示的に
# 完了操作をした場合にだけcomplete_work_item()経由で設定する。手動追加
# (insert_work_item)・候補連携(sync_candidate_work_items)では'done'を直接
# 指定させない(WORK_STATUS_EDITABLE_VALUESのみ受け付ける)ことで、「完了は
# 明示操作時だけDBに保存する」という要件を守る。
WORK_STATUS_VALUES = ("today", "week", "hold", "done")
WORK_STATUS_EDITABLE_VALUES = ("today", "week", "hold")
WORK_STATUS_DEFAULT = "today"
WORK_PRIORITY_DEFAULT = 5

# MISSION 090: 楽天ROOM候補を作業台帳へ連携する際の、媒体→担当社員キーの
# 対応(AIオフィスの部署担当と一致させる)。
WORK_ITEM_MEDIA_ASSIGNEE = {
    "Pinterest": "pinterest",
    "note": "note",
    "楽天ROOM": "room",
}
WORK_ITEM_FALLBACK_ASSIGNEE = "room"

# MISSION 091: 実績スナップショット(metric_snapshots)で入力を受け付ける、
# 媒体ごとの指標一覧(キー・表示ラベル)。キーはそのままmetric列の値になる。
# office_views.py(収益化ボード・AIオフィスの分析表示)もこの定義を参照し、
# 入力フォーム・ラベル表示が二重管理にならないようにする。「投稿の有無」
# (Threads)は1(あり)/0(なし)の数値として保存する。
REVENUE_METRIC_FIELDS = {
    "楽天ROOM": [
        {"key": "product_count", "label": "商品数"},
        {"key": "likes", "label": "いいね数"},
        {"key": "comments", "label": "コメント数"},
        {"key": "followers", "label": "フォロワー数"},
    ],
    "楽天アフィリエイト": [
        {"key": "clicks", "label": "クリック数"},
        {"key": "sales", "label": "売上"},
        {"key": "commission", "label": "成果報酬"},
        {"key": "orders", "label": "注文数"},
    ],
    "Pinterest": [
        {"key": "impressions", "label": "表示数"},
        {"key": "saves", "label": "保存数"},
        {"key": "link_clicks", "label": "リンククリック数"},
    ],
    "note": [
        {"key": "pv", "label": "PV"},
        {"key": "likes", "label": "スキ"},
        {"key": "followers", "label": "フォロワー数"},
    ],
    "Threads": [
        {"key": "posted", "label": "投稿の有無"},
        {"key": "reactions", "label": "確認できた反応数"},
    ],
}
REVENUE_METRIC_MEDIA_ORDER = ["楽天ROOM", "楽天アフィリエイト", "Pinterest", "note", "Threads"]
REVENUE_METRIC_HISTORY_LIMIT = 5

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


def _normalize_work_status(status):
  """作業台帳の状態として手動追加・候補連携で受け付けてよい値
  ('today'/'week'/'hold')ならそのまま返す。'done'や無効な値はNoneを返し、
  呼び出し側でデフォルト値に差し替えさせる('done'への変更は
  complete_work_item()経由の明示操作だけに限定するため)。"""
  if status in WORK_STATUS_EDITABLE_VALUES:
    return status
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


def _work_item_dedup_key(media, task_name, assignee, created_date):
  # 手動追加は「同じ日に同じ媒体・作業名・担当」を二重送信(ボタン連打等)
  # しても1件にまとめる。日付をキーに含めるため、別の日であれば同じ内容を
  # 新規に追加できる。
  return "|".join([_norm(media), _norm(task_name), _norm(assignee), created_date])


def _work_item_candidate_dedup_key(candidate_id):
  return f"candidate:{candidate_id}"


def insert_work_item(media, task_name, assignee, status, priority=None):
  """運用司令室から、利用者が手動で作業台帳へ1件追加する(重複はスキップ)。

  statusは'today'/'week'/'hold'のみ受け付ける('done'は
  complete_work_item()の明示操作でしか設定しない)。
  """
  if not _norm(media) or not _norm(task_name) or not _norm(assignee):
    return {"inserted": False, "reason": "missing_required_field"}
  normalized_status = _normalize_work_status(status) or WORK_STATUS_DEFAULT
  try:
    priority_value = (
        int(priority) if priority is not None and priority != "" else WORK_PRIORITY_DEFAULT
    )
  except (TypeError, ValueError):
    priority_value = WORK_PRIORITY_DEFAULT
  with _LOCK:
    conn = get_connection()
    try:
      today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
      key = _work_item_dedup_key(media, task_name, assignee, today)
      cur = conn.execute(
          "INSERT OR IGNORE INTO work_items"
          " (dedup_key, media, task_name, assignee, status, priority, source)"
          " VALUES (?, ?, ?, ?, ?, ?, 'manual')",
          (key, _norm(media), _norm(task_name), _norm(assignee), normalized_status,
           priority_value),
      )
      conn.commit()
      return {"inserted": cur.rowcount > 0}
    finally:
      conn.close()


def complete_work_item(item_id):
  """利用者が明示的に「完了」にした作業だけ、statusを'done'にし
  completed_atを記録する。外部へ実際に投稿したかどうかの推測・自動判定は
  一切行わない(ここに来るのは利用者がボタンを押した場合のみ)。
  """
  try:
    item_id_int = int(item_id)
  except (TypeError, ValueError):
    return {"updated": False, "reason": "invalid_id"}
  with _LOCK:
    conn = get_connection()
    try:
      row = conn.execute(
          "SELECT id, status FROM work_items WHERE id=?", (item_id_int,)
      ).fetchone()
      if not row:
        return {"updated": False, "reason": "not_found"}
      if row["status"] == "done":
        return {"updated": True, "already_done": True}
      conn.execute(
          "UPDATE work_items SET status='done',"
          " completed_at=datetime('now','localtime'),"
          " updated_at=datetime('now','localtime') WHERE id=?",
          (item_id_int,),
      )
      conn.commit()
      return {"updated": True}
    finally:
      conn.close()


def sync_candidate_work_items():
  """既存の楽天ROOM投稿候補のうち、現在「今日・今週」に割り当て済みの候補
  だけを、重複作成せずに作業台帳(work_items)へ安全に連携する(MISSION 090)。

  - 候補自体(post_candidates)は一切削除・上書き・重複作成しない。
  - 連携の可否は、候補の「現在のbucket」が'today'/'week'かどうかだけで
    判定する(「保留候補を勝手に作業化しない」という要件を守るため、
    manual_postedの値に関わらず、bucketが'hold'の候補は新規にも更新にも
    work_itemsを作らない)。
  - 連携済みの行はcandidate_idとdedup_key("candidate:<id>")で紐付け、
    候補側のbucket/manual_postedが変わるたびに冪等にUPDATEするだけ
    (INSERTは候補が初めてtoday/weekになった時の1回だけ)。
  - 連携済みの候補がbucket='hold'に戻された場合、work_items側もstatus=
    'hold'に追従させる(today/weekの一覧には出なくなるが、行自体は削除
    しない)。
  - bucketがtoday/weekのまま、候補がmanual_posted(利用者が明示的に完了に
    した)になったときだけ、連携済みの行をstatus='done'にする(外部投稿の
    有無を推測しない。あくまで候補側に記録済みの、利用者自身の明示操作を
    反映するだけ)。
  """
  with _LOCK:
    conn = get_connection()
    try:
      candidates = conn.execute(
          "SELECT id, media, genre, product_name, bucket, manual_posted"
          " FROM post_candidates WHERE media='楽天ROOM'"
      ).fetchall()
      for c in candidates:
        bucket = c["bucket"] or BUCKET_DEFAULT
        manual_posted = bool(c["manual_posted"])
        key = _work_item_candidate_dedup_key(c["id"])
        existing = conn.execute(
            "SELECT id, status FROM work_items WHERE dedup_key=?", (key,)
        ).fetchone()
        if bucket not in ("today", "week"):
          # 保留は作業台帳化しない。すでに連携済みの行があれば保留へ
          # 追従させ(today/weekの一覧から外れる)、新規作成はしない。
          if existing and existing["status"] != "hold":
            conn.execute(
                "UPDATE work_items SET status='hold',"
                " updated_at=datetime('now','localtime') WHERE id=?",
                (existing["id"],),
            )
          continue
        target_status = "done" if manual_posted else bucket
        task_name = c["product_name"] or c["genre"] or "（商品名未入力）"
        assignee = WORK_ITEM_MEDIA_ASSIGNEE.get(c["media"], WORK_ITEM_FALLBACK_ASSIGNEE)
        if not existing:
          if target_status == "done":
            conn.execute(
                "INSERT INTO work_items"
                " (dedup_key, media, task_name, assignee, status, priority,"
                "  candidate_id, source, completed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'candidate', datetime('now','localtime'))",
                (key, c["media"], task_name, assignee, target_status,
                 WORK_PRIORITY_DEFAULT, c["id"]),
            )
          else:
            conn.execute(
                "INSERT INTO work_items"
                " (dedup_key, media, task_name, assignee, status, priority,"
                "  candidate_id, source)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'candidate')",
                (key, c["media"], task_name, assignee, target_status,
                 WORK_PRIORITY_DEFAULT, c["id"]),
            )
          continue
        if existing["status"] == target_status:
          conn.execute(
              "UPDATE work_items SET task_name=?,"
              " updated_at=datetime('now','localtime') WHERE id=?",
              (task_name, existing["id"]),
          )
        elif target_status == "done":
          conn.execute(
              "UPDATE work_items SET status='done', task_name=?,"
              " completed_at=datetime('now','localtime'),"
              " updated_at=datetime('now','localtime') WHERE id=?",
              (task_name, existing["id"]),
          )
        else:
          conn.execute(
              "UPDATE work_items SET status=?, task_name=?,"
              " updated_at=datetime('now','localtime') WHERE id=?",
              (target_status, task_name, existing["id"]),
          )
      conn.commit()
    finally:
      conn.close()


def list_work_items(status=None):
  """作業台帳の一覧を返す(候補連携の同期を先に行ってから読む)。"""
  sync_candidate_work_items()
  with _LOCK:
    conn = get_connection()
    try:
      if status:
        rows = conn.execute(
            "SELECT * FROM work_items WHERE status=?"
            " ORDER BY priority ASC, id ASC",
            (status,),
        ).fetchall()
      else:
        rows = conn.execute(
            "SELECT * FROM work_items ORDER BY"
            " CASE status WHEN 'today' THEN 0 WHEN 'week' THEN 1"
            " WHEN 'hold' THEN 2 ELSE 3 END,"
            " priority ASC, id ASC"
        ).fetchall()
      return [dict(r) for r in rows]
    finally:
      conn.close()


def _metric_dedup_key(date, media, metric):
  return "|".join([_norm(date), _norm(media), _norm(metric)])


def save_metric_snapshot_batch(date, media, values, note=""):
  """実績スナップショットを、指定した媒体・日付についてまとめて保存する
  (MISSION 091)。

  valuesは{metric_key: 値}の辞書。REVENUE_METRIC_FIELDSに無いキーは無視する。
  値が空欄(None・空文字)や数値に変換できない指標は保存をスキップする
  (「数字が分からない項目は空欄のまま保存できる」という要件)。1つも有効な
  値が無い場合は何も保存しない(「何も入力されていない場合は保存しない」
  という要件)。

  同じ日・媒体・指標の組み合わせがすでに存在する場合は、重複作成せず
  最新の値へUPDATEする(dedup_key="date|media|metric")。
  """
  if not _norm(date) or not _norm(media):
    return {"saved": False, "reason": "missing_required_field"}
  fields = REVENUE_METRIC_FIELDS.get(media)
  if not fields:
    return {"saved": False, "reason": "unknown_media"}
  valid_keys = {f["key"] for f in fields}
  saved_metrics = []
  skipped_metrics = []
  with _LOCK:
    conn = get_connection()
    try:
      for metric_key, raw_value in (values or {}).items():
        if metric_key not in valid_keys:
          continue
        if raw_value is None or raw_value == "":
          skipped_metrics.append(metric_key)
          continue
        try:
          value = float(raw_value)
        except (TypeError, ValueError):
          skipped_metrics.append(metric_key)
          continue
        key = _metric_dedup_key(date, media, metric_key)
        existing = conn.execute(
            "SELECT id FROM metric_snapshots WHERE dedup_key=?", (key,)
        ).fetchone()
        if existing:
          conn.execute(
              "UPDATE metric_snapshots SET value=?, note=?,"
              " updated_at=datetime('now','localtime') WHERE dedup_key=?",
              (value, note or "", key),
          )
        else:
          conn.execute(
              "INSERT INTO metric_snapshots"
              " (dedup_key, date, media, metric, value, note)"
              " VALUES (?, ?, ?, ?, ?, ?)",
              (key, _norm(date), _norm(media), metric_key, value, note or ""),
          )
        saved_metrics.append(metric_key)
      conn.commit()
    finally:
      conn.close()
  if not saved_metrics:
    return {"saved": False, "reason": "no_values", "skippedMetrics": skipped_metrics}
  return {
      "saved": True, "date": _norm(date), "media": _norm(media),
      "savedMetrics": saved_metrics, "skippedMetrics": skipped_metrics,
  }


def list_metrics(date=None, media=None):
  """実績スナップショットの一覧を返す(新しい順)。date/mediaで絞り込める。"""
  with _LOCK:
    conn = get_connection()
    try:
      clauses = []
      params = []
      if date:
        clauses.append("date=?")
        params.append(date)
      if media:
        clauses.append("media=?")
        params.append(media)
      where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
      rows = conn.execute(
          f"SELECT * FROM metric_snapshots{where}"
          " ORDER BY date DESC, id DESC",
          params,
      ).fetchall()
      return [dict(r) for r in rows]
    finally:
      conn.close()


def get_media_metric_summary(media):
  """指定媒体の各指標について、最新記録・前回記録との差分・直近履歴
  (最大REVENUE_METRIC_HISTORY_LIMIT件)をまとめて返す(MISSION 091)。

  媒体自体に1件も記録が無い場合はNoneではなく、全指標がlatest=Noneの
  辞書を返す(呼び出し側で「未記録」と判定できるようにするため)。比較対象
  (前回記録)が無い指標はdiff=Noneとし、呼び出し側で「比較できる記録は
  まだありません」と正直に表示できるようにする(増減を捏造しない)。
  """
  fields = REVENUE_METRIC_FIELDS.get(media, [])
  with _LOCK:
    conn = get_connection()
    try:
      result = {}
      for field in fields:
        metric_key = field["key"]
        rows = conn.execute(
            "SELECT * FROM metric_snapshots WHERE media=? AND metric=?"
            " ORDER BY date DESC, id DESC LIMIT ?",
            (media, metric_key, REVENUE_METRIC_HISTORY_LIMIT),
        ).fetchall()
        rows = [dict(r) for r in rows]
        latest = rows[0] if rows else None
        previous = rows[1] if len(rows) > 1 else None
        diff = None
        if latest is not None and previous is not None:
          diff = latest["value"] - previous["value"]
        result[metric_key] = {
            "label": field["label"], "latest": latest, "previous": previous,
            "diff": diff, "history": rows,
        }
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


def _managed_backup_entries():
  """このモジュールのDB_NAME/BACKUPS_ROOT設定で、hive_backup.list_backups()
  を呼び、「この機能が作成したバックアップ」(ok=True かつ
  backup_<timestamp>_<suffix>/の名前を持つもの)だけに絞って、新しい順の
  まま返す。手動スナップショット等、他の方法で作られたバックアップは
  含めない(prune_backups()が削除対象を絞り込むのと同じ基準)。
  """
  entries = hive_backup.list_backups(backups_root=BACKUPS_ROOT)
  return [
      e for e in entries
      if e.get("ok") and e["identifier"].startswith(hive_backup.BACKUP_DIR_PREFIX)
  ]


def maybe_auto_backup_today():
  """DBへの書き込みが成功した後に呼ぶ、当日1回だけの自動バックアップ
  (MISSION 092)。

  当日分の(この機能が作成した)バックアップがすでにあれば何もしない。
  無ければ新規作成し、整合性を確認したうえで直近
  BACKUP_RETENTION_COUNT世代を超えた古い世代を整理する。

  重要: この関数はどのような例外も外へ伝播させない。バックアップの作成・
  整理に失敗しても、呼び出し元(運用記録・投稿候補・作業台帳・実績数値の
  保存)の成功には一切影響しない(安全性要件)。
  """
  try:
    today = datetime.date.today().isoformat()
    already_today = any(
        str(e.get("created_at") or "").startswith(today)
        for e in _managed_backup_entries()
    )
    if already_today:
      return {"created": False, "reason": "already_backed_up_today"}

    result = hive_backup.create_backup(db_path=DB_NAME, backups_root=BACKUPS_ROOT)
  except Exception:
    return {"created": False, "reason": "error"}

  if result["metadata"]["integrity_check"] != "ok":
    # 新しいバックアップの正常性が確認できない場合、古い世代の整理は
    # 行わない(異常なバックアップを基準に世代を削り過ぎないため)。
    return {"created": True, "backup_dir": result["backup_dir"], "pruned": False}

  try:
    hive_backup.prune_backups(keep=BACKUP_RETENTION_COUNT, backups_root=BACKUPS_ROOT)
    return {"created": True, "backup_dir": result["backup_dir"], "pruned": True}
  except Exception:
    # 整理の失敗は、すでに作成済みのバックアップ自体の成功を損なわない。
    return {"created": True, "backup_dir": result["backup_dir"], "pruned": False}


def create_manual_backup():
  """運用司令室の「今すぐバックアップを作成」用(MISSION 092)。

  当日分が既にあるかどうかに関わらず、利用者の明示操作として必ず新しい
  バックアップを1つ作成する。作成後、正常性を確認してから直近
  BACKUP_RETENTION_COUNT世代を超えた古い世代(この機能が作成したものだけ)
  を整理する。利用者が明示的に押した操作のため、失敗時はエラー内容を
  隠さず返す(自動バックアップとは異なり、ここでは例外を飲み込まない)。
  """
  try:
    result = hive_backup.create_backup(db_path=DB_NAME, backups_root=BACKUPS_ROOT)
  except hive_backup.BackupError as e:
    return {"created": False, "reason": "backup_error", "message": str(e)}
  except OSError as e:
    return {"created": False, "reason": "os_error", "message": str(e)}

  metadata = result["metadata"]
  pruned = False
  if metadata["integrity_check"] == "ok":
    try:
      hive_backup.prune_backups(keep=BACKUP_RETENTION_COUNT, backups_root=BACKUPS_ROOT)
      pruned = True
    except Exception:
      # 整理の失敗は、すでに作成済みのバックアップ自体の成功を損なわない。
      pruned = False

  return {
      "created": True,
      "pruned": pruned,
      "createdAt": metadata["created_at"],
      "sizeBytes": metadata["size_bytes"],
      "integrityCheck": metadata["integrity_check"],
  }


def get_backup_status():
  """運用司令室の「データ保護」表示用に、最終バックアップ日時・保存済み
  世代数・直近一覧(日時・サイズのみ)をまとめて返す(MISSION 092)。

  DBの中身(テーブル件数等)・認証情報・ファイルパスは一切含めない。
  一覧の取得自体に失敗しても例外を外へ伝播させず、「バックアップは未確認」
  として安全なデフォルト値を返す。
  """
  try:
    entries = _managed_backup_entries()
  except Exception:
    entries = []
  recent = [
      {"createdAt": e.get("created_at"), "sizeBytes": e.get("size_bytes")}
      for e in entries[:BACKUP_RETENTION_COUNT]
  ]
  return {
      "lastBackupAt": entries[0]["created_at"] if entries else None,
      "generationCount": len(entries),
      "retentionCount": BACKUP_RETENTION_COUNT,
      "recent": recent,
  }


def list_restore_candidates():
  """整合性が実際に再確認できたバックアップだけを、復元候補として返す
  (MISSION 093)。

  一覧の表示のたびにhive_backup.verify_backup()で再検証する(作成時点の
  metadata.jsonに記録された結果を鵜呑みにせず、保存後の改ざん・破損を
  見逃さないため)。DBの中身(テーブル件数等)・認証情報・ファイルパスは
  一切含めない。一覧の取得自体に失敗しても例外を外へ伝播させず、空の
  候補一覧を返す。
  """
  candidates = []
  try:
    managed = _managed_backup_entries()
  except Exception:
    managed = []
  for entry in managed:
    identifier = entry["identifier"]
    try:
      verify_result = hive_backup.verify_backup(
          os.path.join(BACKUPS_ROOT, identifier), backups_root=BACKUPS_ROOT,
      )
    except Exception:
      continue
    if not verify_result["ok"]:
      continue
    candidates.append({
        "identifier": identifier,
        "createdAt": verify_result.get("metadata_created_at"),
        "sizeBytes": entry.get("size_bytes"),
        "integrityCheck": verify_result.get("integrity_check"),
        "foreignKeyCheckOk": verify_result.get("foreign_key_check_ok"),
    })
  candidates.sort(key=lambda c: c.get("createdAt") or "", reverse=True)
  return candidates


def restore_from_backup(identifier, confirmation_phrase):
  """運用司令室の「バックアップから復元」操作の実行(MISSION 093)。

  利用者が明示的に選んだ対象(identifier、list_restore_candidates()が
  返したディレクトリ名のみ受け付ける)と、確認文言
  (RESTORE_CONFIRMATION_PHRASEと完全一致)の両方が正しい場合だけ、
  実際にDBを復元する。それ以外(空欄・誤入力・存在しない/無効な候補)は
  DBを一切変更せず、理由を返す。

  復元の実行中は、他の書き込み処理(運用記録・投稿候補・作業台帳・
  実績数値の保存)と競合しないよう_LOCKを保持する。復元前バックアップの
  作成・DBの実書き換えに失敗した場合、hive_backup.restore_backup()の
  安全設計により現在のDBは変更されない。
  """
  if confirmation_phrase != RESTORE_CONFIRMATION_PHRASE:
    return {"restored": False, "reason": "confirmation_mismatch"}

  if not identifier or not isinstance(identifier, str):
    return {"restored": False, "reason": "invalid_identifier"}

  valid_identifiers = {c["identifier"] for c in list_restore_candidates()}
  if identifier not in valid_identifiers:
    return {"restored": False, "reason": "not_a_valid_candidate"}

  backup_path = os.path.join(BACKUPS_ROOT, identifier)
  with _LOCK:
    try:
      result = hive_backup.restore_backup(
          backup_path, db_path=DB_NAME, backups_root=BACKUPS_ROOT,
      )
    except hive_backup.BackupError as e:
      return {"restored": False, "reason": "restore_error", "message": str(e)}
    except OSError as e:
      return {"restored": False, "reason": "os_error", "message": str(e)}
    except Exception:
      # 想定外の例外も、現在のDBが変更されない限りは安全に理由を返す
      # (hive_backup.restore_backup()自体が、db_path書き換え前の失敗は
      # 例外を再送出し、db_pathを変更しない設計のため)。
      return {"restored": False, "reason": "error"}

  # 復元元・復元前バックアップは、この整理では保護する(MISSION 093要件)。
  protect = {
      os.path.basename(result["restored_from"]),
      os.path.basename(result["pre_restore_backup_dir"]),
  }
  try:
    hive_backup.prune_backups(
        keep=BACKUP_RETENTION_COUNT, backups_root=BACKUPS_ROOT, protect=protect,
    )
  except Exception:
    pass

  return {
      "restored": True,
      "restoredFromCreatedAt": result["restored_from_created_at"],
      "preRestoreBackupCreatedAt": result["pre_restore_created_at"],
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
      if result.get("inserted"):
        maybe_auto_backup_today()
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
      if result.get("inserted") or result.get("updated"):
        maybe_auto_backup_today()
      return jsonify(result)
    target_date = request.args.get("targetDate")
    return jsonify({"candidates": list_post_candidates(target_date)})

  @app.route("/api/dashboard/migrate", methods=["POST"])
  def dashboard_migrate():
    data = request.get_json(silent=True) or {}
    result = migrate_from_payload(data.get("records", []), data.get("candidates", []))
    if result["records"]["inserted"] or result["candidates"]["inserted"]:
      maybe_auto_backup_today()
    return jsonify(result)

  # MISSION 090: 全媒体共通の作業台帳。POSTは、idを含む場合は「完了」操作
  # (complete_work_item)、含まない場合は手動での新規追加(insert_work_item)
  # として扱う(2つの操作だけを1エンドポイントにまとめる、既存のcandidates
  # エンドポイントと同じ考え方)。
  @app.route("/api/dashboard/work-items", methods=["GET", "POST"])
  def dashboard_work_items():
    if request.method == "POST":
      data = request.get_json(silent=True) or {}
      if data.get("id"):
        result = complete_work_item(data.get("id"))
      else:
        result = insert_work_item(
            data.get("media"), data.get("taskName"), data.get("assignee"),
            data.get("status"), data.get("priority"),
        )
      if result.get("inserted") or result.get("updated"):
        maybe_auto_backup_today()
      return jsonify(result)
    status = request.args.get("status")
    return jsonify({"workItems": list_work_items(status)})

  # MISSION 091: 実績スナップショット。POSTはvaluesの辞書をまとめて保存
  # する(1つも有効な値が無い場合はsaved:falseを返し、呼び出し側(JS)で
  # 画面内の案内表示に使う)。
  @app.route("/api/dashboard/metrics", methods=["GET", "POST"])
  def dashboard_metrics():
    if request.method == "POST":
      data = request.get_json(silent=True) or {}
      result = save_metric_snapshot_batch(
          data.get("date"), data.get("media"), data.get("values", {}),
          data.get("note", ""),
      )
      if result.get("saved"):
        maybe_auto_backup_today()
      return jsonify(result)
    date = request.args.get("date")
    media = request.args.get("media")
    return jsonify({"metrics": list_metrics(date, media)})

  @app.route("/api/dashboard/metrics/summary")
  def dashboard_metrics_summary():
    media = request.args.get("media")
    if media:
      return jsonify({"summary": {media: get_media_metric_summary(media)}})
    return jsonify({
        "summary": {
            m: get_media_metric_summary(m) for m in REVENUE_METRIC_MEDIA_ORDER
        },
    })

  # MISSION 092: 運用司令室の「データ保護」表示用。GETは最終バックアップ
  # 日時・世代数・直近一覧(日時・サイズのみ、DBの中身は含めない)を返す。
  # POSTは「今すぐバックアップを作成」ボタン用で、常に新しいバックアップを
  # 1つ作成する(自動バックアップの「当日1回だけ」制限は適用しない)。
  @app.route("/api/dashboard/backups", methods=["GET", "POST"])
  def dashboard_backups():
    if request.method == "POST":
      return jsonify(create_manual_backup())
    return jsonify(get_backup_status())

  # MISSION 093: 復元候補一覧(整合性を実際に再確認できたものだけ)。
  # DBの中身・認証情報は一切含めない。
  @app.route("/api/dashboard/backups/restore-candidates")
  def dashboard_backup_restore_candidates():
    return jsonify({"candidates": list_restore_candidates()})

  # MISSION 093: 復元の実行。identifier(対象)とconfirmation(確認文言)の
  # 両方が正しい場合だけ実際にDBを復元する。ブラウザ側の確認ダイアログ
  # だけに依存せず、ここでも必ず検証する。
  @app.route("/api/dashboard/backups/restore", methods=["POST"])
  def dashboard_backup_restore():
    data = request.get_json(silent=True) or {}
    result = restore_from_backup(data.get("identifier"), data.get("confirmation", ""))
    return jsonify(result)
