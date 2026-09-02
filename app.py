import os
import sqlite3
from flask import Flask, jsonify, render_template_string, request

import hive_db

app = Flask(__name__)
DB_NAME = "ai_company.db"

# AI Hive OS の新規テーブル（employees / missions / tasks / metrics /
# reports / proposals / decisions）を安全に作成する。
# CREATE TABLE IF NOT EXISTS のみを使うため、既存の work_logs テーブルや
# データには一切影響しない。
hive_db.init_hive_schema()


@app.route("/")
def index():
  html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>会社の全体像ダッシュボード</title>
        <style>
            :root {
                --bg-main: #070913;
                --card-bg: #111827;
                --card-border: #1f2937;
                --accent-blue: #38bdf8;
                --text-main: #f8fafc;
                --text-sub: #94a3b8;
            }
            body { 
                background: var(--bg-main); 
                color: var(--text-main); 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                margin: 0; padding: 20px; 
            }
            
            /* ヘッダー */
            .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border); padding-bottom: 12px; margin-bottom: 20px; }
            h1 { font-size: 18px; color: var(--text-main); margin: 0 0 2px 0; font-weight: bold; }
            .sub-title { font-size: 11px; color: var(--text-sub); }
            .btn-top { background: #1e293b; color: var(--text-main); border: 1px solid #334155; padding: 6px 14px; border-radius: 8px; font-size: 12px; cursor: pointer; }

            /* グリッドレイアウト */
            .dashboard-grid { display: grid; grid-template-columns: 1.3fr 1.2fr 1fr; gap: 15px; margin-bottom: 15px; }
            
            .card { 
                background: var(--card-bg); 
                border: 1px solid var(--card-border); 
                border-radius: 14px; 
                padding: 16px; 
                box-shadow: 0 8px 20px rgba(0,0,0,0.5); 
                position: relative;
            }
            .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 12px; color: var(--text-sub); }
            
            .badge-live { background: #065f46; color: #34d399; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; }
            .badge-status { background: #1e3a8a; color: #60a5fa; padding: 2px 8px; border-radius: 4px; font-size: 10px; }

            /* 1. 社長室（画像フィギュア風） */
            .president-card { display: flex; gap: 15px; align-items: center; }
            .president-img-box {
                width: 85px; height: 85px; flex-shrink: 0;
                border-radius: 50%;
                overflow: hidden;
                border: 2px solid #f59e0b;
                box-shadow: 0 8px 20px rgba(245, 158, 11, 0.3);
                background: #1e293b;
            }
            .president-img-box img { width: 100%; height: 100%; object-fit: cover; }
            
            .progress-item { margin-bottom: 8px; }
            .progress-label { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 3px; }
            .progress-bar-bg { background: #1e293b; height: 6px; border-radius: 3px; overflow: hidden; }
            .progress-bar-fill { background: #38bdf8; height: 100%; border-radius: 3px; }

            /* 2. 運用チームフロア */
            .team-grid-small { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .member-mini-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 10px; display: flex; align-items: center; gap: 10px; }
            .avatar-mini { width: 36px; height: 36px; border-radius: 50%; overflow: hidden; flex-shrink: 0; background: #334155; }
            .avatar-mini img { width: 100%; height: 100%; object-fit: cover; }

            /* 3. 下段：WEB制作フロア（画像アバター表示） */
            .web-team-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
            .web-member-card {
                background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
                border: 1px solid #334155;
                border-radius: 14px;
                overflow: hidden;
                text-align: center;
                box-shadow: 0 8px 16px rgba(0,0,0,0.4);
            }
            .room-preview {
                height: 120px;
                background: radial-gradient(circle at center, #312e81 0%, #0f172a 100%);
                display: flex; align-items: center; justify-content: center;
                position: relative;
                overflow: hidden;
            }
            .room-preview img {
                width: 75px; height: 75px;
                border-radius: 50%;
                object-fit: cover;
                border: 2px solid #38bdf8;
                box-shadow: 0 6px 16px rgba(0,0,0,0.6);
            }
            .web-member-info { padding: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h1>会社の全体像ダッシュボード</h1>
                <span class="sub-title">社長室・事業・制作・運用を1画面で確認</span>
            </div>
            <button class="btn-top">詳しい画面へ戻る</button>
        </div>

        <!-- 上段エリア -->
        <div class="dashboard-grid">
            <!-- 社長室カード -->
            <div class="card">
                <div class="card-header">
                    <span>社長室</span>
                    <span class="badge-status">承認 ✓</span>
                </div>
                <div class="president-card">
                    <div class="president-img-box">
                        <img src="/static/president.png" alt="柴犬社長">
                    </div>
                    <div style="flex-grow: 1;">
                        <div class="progress-item">
                            <div class="progress-label"><span>楽天ROOM</span><span>68%</span></div>
                            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 68%;"></div></div>
                        </div>
                        <div class="progress-item">
                            <div class="progress-label"><span>Pinterest</span><span>3%</span></div>
                            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 3%; background: #ec4899;"></div></div>
                        </div>
                        <div class="progress-item">
                            <div class="progress-label"><span>A8.net</span><span>3%</span></div>
                            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 3%; background: #10b981;"></div></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 現在のタスク作業 -->
            <div class="card">
                <div class="card-header">
                    <span>現在の作業</span>
                    <span style="color: #34d399; font-size: 11px;">✓ 完了</span>
                </div>
                <div style="font-size: 14px; font-weight: bold; margin-bottom: 8px; color: #38bdf8;" id="latest-theme">公開済みラッシュアディクト投稿をキューへ反映</div>
                <div style="font-size: 12px; color: var(--text-sub);" id="latest-content">データを読み込んでいます...</div>
            </div>

            <!-- 経理・売上フロア -->
            <div class="card">
                <div class="card-header">
                    <span>経理・売上フロア</span>
                    <span class="badge-live">LIVE</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <div class="avatar-mini" style="width: 40px; height: 40px;"><img src="/static/user.png" alt="経理担当"></div>
                    <div>
                        <div style="font-size: 13px; font-weight: bold;">彩・経理担当</div>
                        <div style="font-size: 10px; color: var(--text-sub);">「1/4部署から受け取りました。残りを承認中です。」</div>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; border-top: 1px solid var(--card-border); padding-top: 8px; font-size: 12px;">
                    <div><span style="color: var(--text-sub);">本日の売上:</span> <strong style="color: #34d399;">¥301</strong></div>
                    <div><span style="color: var(--text-sub);">更新:</span> <strong>75件</strong></div>
                </div>
            </div>
        </div>

        <!-- 中段：運用チームフロア & 事業ポートフォリオ -->
        <div class="dashboard-grid" style="grid-template-columns: 1.5fr 1.5fr;">
            <div class="card">
                <div class="card-header">
                    <span>運用チームフロア</span>
                    <span class="badge-live">LIVE</span>
                </div>
                <div class="team-grid-small">
                    <div class="member-mini-card">
                        <div class="avatar-mini"><img src="/static/user.png" alt="琴衣"></div>
                        <div>
                            <div style="font-size: 12px; font-weight: bold;">琴衣 (Lv.1)</div>
                            <div style="font-size: 10px; color: var(--text-sub);">A8.net提携確認</div>
                        </div>
                    </div>
                    <div class="member-mini-card">
                        <div class="avatar-mini"><img src="/static/president.png" alt="蒼"></div>
                        <div>
                            <div style="font-size: 12px; font-weight: bold;">蒼 (Lv.1)</div>
                            <div style="font-size: 10px; color: var(--text-sub);">Pinterest投稿準備</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>事業ポートフォリオ</span>
                    <span style="font-size: 11px; color: var(--text-sub);">5 事業</span>
                </div>
                <div class="progress-item">
                    <div class="progress-label"><span>美容アフィリエイト</span><span>68%</span></div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 68%;"></div></div>
                </div>
                <div class="progress-item">
                    <div class="progress-label"><span>美容サロンWEB制作</span><span>64%</span></div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 64%; background: #ec4899;"></div></div>
                </div>
            </div>
        </div>

        <!-- 下段：WEB制作フロア -->
        <div class="card" style="margin-bottom: 0;">
            <div class="card-header">
                <span>WEB制作フロア</span>
                <span style="font-size: 11px; color: var(--text-sub);">4人稼働</span>
            </div>
            <div class="web-team-grid">
                <div class="web-member-card">
                    <div class="room-preview"><img src="/static/user.png" alt="美咲"></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">美咲 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">WEBディレクター</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #34d399;">制約進行を整理中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><img src="/static/user.png" alt="海"></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">海 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">UIデザイナー</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #38bdf8;">デザインを調整中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><img src="/static/user.png" alt="湊"></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">湊 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">フロントエンド</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #fbbf24;">コードを実装中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><img src="/static/user.png" alt="伊藤"></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">伊藤 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">QA・SEO</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #34d399;">テストを実施中</div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            fetch('/api/logs')
                .then(response => response.json())
                .then(data => {
                    if(data.length > 0) {
                        const latest = data[0];
                        document.getElementById('latest-theme').innerText = latest[2];
                        document.getElementById('latest-content').innerText = latest[3];
                    }
                });
        </script>
    </body>
    </html>
    """
  return render_template_string(html_content)


@app.route("/api/logs")
def get_logs():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, timestamp, theme, content, status FROM work_logs ORDER BY"
      " id DESC"
  )
  logs = cursor.fetchall()
  conn.close()
  return jsonify(logs)


def _json_body():
  return request.get_json(silent=True) or {}


# ---------------------------------------------------------------------------
# AI Hive OS API
#
# 既存の GET / ・GET /api/logs・work_logs テーブルには一切手を加えず、
# 同じ ai_company.db 上に追加した7テーブル（employees / missions / tasks /
# metrics / reports / proposals / decisions）に対する CRUD API を追加する。
# レスポンス形式は {"status": "success", "data": ...} /
# {"status": "error", "message": ...} に統一する。
# ---------------------------------------------------------------------------


@app.route("/api/employees", methods=["GET"])
def list_employees():
  try:
    return hive_db.success_response(
        hive_db.list_rows("employees", order_by="id ASC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/employees", methods=["POST"])
def create_employee():
  data = _json_body()
  if not data.get("name"):
    return hive_db.error_response("name は必須です。")
  payload = dict(data)
  payload.setdefault("status", "active")
  try:
    row = hive_db.insert_row("employees", hive_db.EMPLOYEE_COLUMNS, payload)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/missions", methods=["GET"])
def list_missions():
  filters = {}
  for key in ("issued_by", "assigned_to", "status"):
    value = request.args.get(key)
    if value is not None:
      filters[key] = value
  try:
    return hive_db.success_response(
        hive_db.list_rows("missions", filters, order_by="id DESC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/missions", methods=["POST"])
def create_mission():
  data = _json_body()
  if not data.get("title"):
    return hive_db.error_response("title は必須です。")
  payload = dict(data)
  payload.setdefault("mission_code", hive_db.gen_code("MSN"))
  payload.setdefault("status", "open")
  try:
    row = hive_db.insert_row("missions", hive_db.MISSION_COLUMNS, payload)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/missions/<int:mission_id>", methods=["GET"])
def get_mission(mission_id):
  try:
    row = hive_db.get_row("missions", mission_id)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)
  if row is None:
    return hive_db.error_response("指定されたmissionが見つかりません。", 404)
  return hive_db.success_response(row)


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
  filters = {}
  for key in ("mission_id", "assigned_to", "status"):
    value = request.args.get(key)
    if value is not None:
      filters[key] = value
  try:
    return hive_db.success_response(
        hive_db.list_rows("tasks", filters, order_by="id DESC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/tasks", methods=["POST"])
def create_task():
  data = _json_body()
  if not data.get("title"):
    return hive_db.error_response("title は必須です。")
  payload = dict(data)
  payload.setdefault("task_code", hive_db.gen_code("TSK"))
  payload.setdefault("status", "todo")
  try:
    row = hive_db.insert_row("tasks", hive_db.TASK_COLUMNS, payload)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
  existing = hive_db.get_row("tasks", task_id)
  if existing is None:
    return hive_db.error_response("指定されたtaskが見つかりません。", 404)
  data = _json_body()
  try:
    row = hive_db.update_row("tasks", hive_db.TASK_COLUMNS, task_id, data)
    return hive_db.success_response(row)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/metrics", methods=["GET"])
def list_metrics():
  filters = {}
  mission_id = request.args.get("mission_id")
  if mission_id is not None:
    filters["mission_id"] = mission_id
  try:
    return hive_db.success_response(
        hive_db.list_rows("metrics", filters, order_by="id DESC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/metrics", methods=["POST"])
def create_metric():
  data = _json_body()
  if not data.get("metric_name"):
    return hive_db.error_response("metric_name は必須です。")
  try:
    row = hive_db.insert_row("metrics", hive_db.METRIC_COLUMNS, data)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/reports", methods=["GET"])
def list_reports():
  filters = {}
  for key in ("mission_id", "task_id", "reported_by"):
    value = request.args.get(key)
    if value is not None:
      filters[key] = value
  try:
    return hive_db.success_response(
        hive_db.list_rows("reports", filters, order_by="id DESC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/reports", methods=["POST"])
def create_report():
  data = _json_body()
  payload = dict(data)
  payload.setdefault("report_code", hive_db.gen_code("RPT"))
  try:
    row = hive_db.insert_row("reports", hive_db.REPORT_COLUMNS, payload)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/proposals", methods=["GET"])
def list_proposals():
  filters = {}
  for key in ("mission_id", "proposed_by", "status"):
    value = request.args.get(key)
    if value is not None:
      filters[key] = value
  try:
    return hive_db.success_response(
        hive_db.list_rows("proposals", filters, order_by="id DESC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/proposals", methods=["POST"])
def create_proposal():
  data = _json_body()
  if not data.get("title"):
    return hive_db.error_response("title は必須です。")
  payload = dict(data)
  payload.setdefault("proposal_code", hive_db.gen_code("PRP"))
  payload.setdefault("status", "pending")
  try:
    row = hive_db.insert_row("proposals", hive_db.PROPOSAL_COLUMNS, payload)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/proposals/<int:proposal_id>", methods=["PATCH"])
def update_proposal(proposal_id):
  existing = hive_db.get_row("proposals", proposal_id)
  if existing is None:
    return hive_db.error_response("指定されたproposalが見つかりません。", 404)
  data = _json_body()
  try:
    row = hive_db.update_row(
        "proposals", hive_db.PROPOSAL_COLUMNS, proposal_id, data
    )
    return hive_db.success_response(row)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/decisions", methods=["GET"])
def list_decisions():
  filters = {}
  for key in ("mission_id", "proposal_id", "decided_by"):
    value = request.args.get(key)
    if value is not None:
      filters[key] = value
  try:
    return hive_db.success_response(
        hive_db.list_rows("decisions", filters, order_by="id DESC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/decisions", methods=["POST"])
def create_decision():
  data = _json_body()
  if not data.get("decision"):
    return hive_db.error_response("decision は必須です。")
  payload = dict(data)
  payload.setdefault("decision_code", hive_db.gen_code("DEC"))
  payload.setdefault("status", "final")
  try:
    row = hive_db.insert_row("decisions", hive_db.DECISION_COLUMNS, payload)
    return hive_db.success_response(row, 201)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


if __name__ == "__main__":
  app.run(debug=True, port=5000)
