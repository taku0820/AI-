import os
import sqlite3
from flask import Flask, jsonify, render_template_string, request

import hive_db
from office_views import register_office_views

app = Flask(__name__)
DB_NAME = "ai_company.db"

# AI Hive OS の新規テーブル（employees / missions / tasks / metrics /
# reports / proposals / decisions）を安全に作成する。
# CREATE TABLE IF NOT EXISTS のみを使うため、既存の work_logs テーブルや
# データには一切影響しない。
hive_db.init_hive_schema()
register_office_views(app)


# ---------------------------------------------------------------------------
# ダッシュボード用ミニフィギュア風アバター（MISSION 024）
#
# 表示専用の装飾SVGを生成するだけのヘルパー。外部画像・外部フォント・
# 外部CDN・外部JavaScriptは一切使用せず、すべて画面内(インラインSVG)で
# 完結する。アニメーションはCSS側の @keyframes に対応するクラス名を
# 付与するだけであり、ここで生成する内容自体は完全に静的なマークアップ。
# DB・API・認証・監査ログ等には一切関与しない。
# ---------------------------------------------------------------------------

# 職種・ステータスごとの「作業中バッジ」。実際の処理結果ではなく、
# 隣接して表示される既存のステータス文言に対応する装飾アイコン。
_PROP_BADGES = {
    # 承認印を軽く上下させる(社長の「承認」ステータスに対応する装飾)。
    "stamp": (
        '<circle class="prop-stamp-head" cx="10" cy="7" r="4.2"/>'
        '<rect class="prop-stamp-handle" x="8.4" y="11" width="3.2" height="4" rx="1"/>'
        '<circle class="prop-stamp-mark" cx="10" cy="16.6" r="2.6" fill="none" stroke-width="1.4"/>'
    ),
    # 書類をめくるような点滅(経理の書類確認に対応する装飾)。
    "doc": (
        '<rect class="prop-doc-back" x="4" y="5" width="10" height="12" rx="1.6"/>'
        '<rect class="prop-doc-top" x="6.5" y="3" width="10" height="12" rx="1.6"/>'
        '<line class="prop-doc-line" x1="9" y1="7" x2="14" y2="7" stroke-width="1.2"/>'
        '<line class="prop-doc-line" x1="9" y1="10" x2="13" y2="10" stroke-width="1.2"/>'
    ),
    # チェックマークが軽く脈打つ(確認・承認系ステータスに対応する装飾)。
    "check": (
        '<rect class="prop-check-board" x="3.5" y="3.5" width="13" height="14" rx="2.4" fill="none" '
        'stroke-width="1.4"/>'
        '<path class="prop-check-mark" d="M6.5 10.5 L9 13 L13.5 7" fill="none" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # 通知ドットが点滅(SNS投稿準備などのステータスに対応する装飾)。
    "phone": (
        '<rect class="prop-phone-body" x="6" y="2.5" width="8" height="15" rx="2.4" fill="none" '
        'stroke-width="1.4"/>'
        '<circle class="prop-phone-dot" cx="10" cy="15.5" r="1.1"/>'
    ),
    # チェックリストの行がハイライトされる(進行整理系ステータスに対応)。
    "list": (
        '<rect class="prop-list-board" x="3.5" y="2.5" width="13" height="15" rx="1.8" fill="none" '
        'stroke-width="1.4"/>'
        '<line class="prop-list-line" x1="6" y1="6.5" x2="14" y2="6.5" stroke-width="1.4"/>'
        '<line class="prop-list-line" x1="6" y1="10" x2="14" y2="10" stroke-width="1.4"/>'
        '<line class="prop-list-line" x1="6" y1="13.5" x2="11.5" y2="13.5" stroke-width="1.4"/>'
    ),
    # ペン先が小さく揺れる(デザイン調整系ステータスに対応する装飾)。
    "pen": (
        '<rect class="prop-pen-paper" x="3" y="10" width="10" height="7" rx="1.2" fill="none" '
        'stroke-width="1.2"/>'
        '<g class="prop-pen-tip">'
        '<line x1="8" y1="13" x2="16.5" y2="4.5" stroke-width="1.8" stroke-linecap="round"/>'
        '<circle cx="16.5" cy="4.5" r="1.4"/>'
        "</g>"
    ),
    # カーソルが点滅するコード表示(実装系ステータスに対応する装飾)。
    "code": (
        '<path class="prop-code-bracket" d="M7 5 L3.5 10 L7 15" fill="none" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path class="prop-code-bracket" d="M13 5 L16.5 10 L13 15" fill="none" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<rect class="prop-code-cursor" x="9.3" y="6" width="1.6" height="8"/>'
    ),
    # 虫眼鏡が左右に小さく往復する(テスト・QA系ステータスに対応する装飾)。
    "search": (
        '<g class="prop-search-lens">'
        '<circle cx="8.5" cy="8.5" r="4.6" fill="none" stroke-width="1.6"/>'
        '<line x1="11.8" y1="11.8" x2="16" y2="16" stroke-width="1.8" stroke-linecap="round"/>'
        "</g>"
    ),
}


def _prop_badge_svg(prop_type, badge_fg):
  """役割に応じた小さな作業アイコン(装飾のみ)のSVG断片を返す。"""
  inner = _PROP_BADGES[prop_type]
  return (
      f'<span class="avatar-badge prop-{prop_type}" style="--badge-fg:{badge_fg};" aria-hidden="true">'
      '<svg viewBox="0 0 20 20" width="18" height="18">' + inner + "</svg>"
      "</span>"
  )


# 頭髪/耳の形状バリエーション(すべて画面内SVGのpath。外部素材は使わない)。
_HAIR_PATHS = {
    # 柴犬社長: 三角の耳(柴犬モチーフ)。
    "shiba_ears": (
        '<path class="fig-hair" d="M16 16 L23 2 L28 18 Z"/>'
        '<path class="fig-hair" d="M56 16 L49 2 L44 18 Z"/>'
    ),
    "short": '<path class="fig-hair" d="M14 22 Q36 2 58 22 L58 16 Q36 -4 14 16 Z"/>',
    "bob": '<path class="fig-hair" d="M13 24 Q36 0 59 24 L59 30 Q52 20 36 20 Q20 20 13 30 Z"/>',
    "side": '<path class="fig-hair" d="M14 24 Q30 -2 60 14 Q50 10 40 12 Q52 18 56 28 L50 26 Q34 6 14 24 Z"/>',
    "cap": (
        '<path class="fig-hair" d="M13 20 Q36 -2 59 20 L59 24 L13 24 Z"/>'
        '<rect class="fig-hair" x="34" y="10" width="6" height="6" rx="1"/>'
    ),
}


def _mini_figure_svg(hair_key, blink_delay):
  """職種メンバー1名分のミニフィギュア(顔・髪・体)を返す。

  色(肌・髪・服)はCSS変数(--skin/--hair/--outfit)側で指定するため、ここでは
  形状のみを組み立てる。同じ形状を複数人で使い回しても配色で個性が出る。
  """
  hair_markup = _HAIR_PATHS[hair_key]
  return (
      '<svg class="figure" viewBox="0 0 72 84" width="72" height="72" aria-hidden="true" focusable="false">'
      '<ellipse class="fig-body" cx="36" cy="66" rx="22" ry="16"/>'
      '<circle class="fig-head" cx="36" cy="34" r="20"/>'
      + hair_markup
      + f'<g class="fig-eyes" style="animation-delay:{blink_delay};">'
        '<ellipse cx="29" cy="34" rx="1.8" ry="2.2"/>'
        '<ellipse cx="43" cy="34" rx="1.8" ry="2.2"/>'
        "</g>"
        '<path class="fig-mouth" d="M30 41 Q36 45 42 41" fill="none" stroke-width="1.6" '
        'stroke-linecap="round"/>'
        "</svg>"
  )


def _avatar(sprite_key, prop_type, badge_fg, size=""):
  """アバター1体分(ローカル画像スプライト+作業バッジ)を返す。

  スプライトはプロジェクト内の静的画像だけを参照する。表示以外の処理、
  外部通信、DBアクセスは行わない。人物名・役職は隣接テキストで読み上げ
  られるため、絵そのものは装飾としてスクリーンリーダーから除外する。
  """
  wrap_class = "avatar-wrap" + (f" {size}" if size else "")
  return (
      f'<span class="{wrap_class}">'
      f'<span class="avatar-sprite avatar-sprite-{sprite_key}" aria-hidden="true"></span>'
      + _prop_badge_svg(prop_type, badge_fg)
      + "</span>"
  )


@app.route("/")
def index():
  # MISSION 038: 会社の全体像ダッシュボードを、現在の実運用(AIとガジェット
  # で暮らしをラクにする発信を、柴犬社長が手動でPinterest・楽天ROOM・note・
  # コンテンツスタジオを使って進めている状態)に合わせて整理し直したもの。
  # A8.net・美容アフィリエイト・美容サロンWEB制作・架空の売上額/更新件数/
  # LIVE表示・実在しない作業チーム(琴衣・蒼・美咲・海・湊・伊藤)は、
  # このページから完全に削除した(/officeのライブオフィス表示では、既存の
  # 演出用デスクキャラクターとして引き続き使われているが、このトップページ
  # とは無関係)。表示する数値は一切なく、外部サービスからの自動取得や
  # SNS投稿の自動連携も行わない。
  html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>会社の全体像ダッシュボード</title>
        <style>
            :root {
                --bg-main: #090c15;
                --card-bg: #121a2c;
                --card-bg-soft: #0e1524;
                --card-border: #212c46;
                --accent-blue: #38bdf8;
                --accent-pink: #f472b6;
                --accent-amber: #f59e0b;
                --accent-green: #34d399;
                --text-main: #f1f5f9;
                --text-sub: #94a3b8;
            }
            * { box-sizing: border-box; }
            body {
                background: var(--bg-main);
                color: var(--text-main);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                margin: 0; padding: 20px;
            }

            /* ヘッダー */
            .header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid var(--card-border); padding-bottom: 14px; margin-bottom: 20px; }
            .header-title { display: flex; align-items: center; gap: 8px; }
            h1 { font-size: 19px; color: var(--text-main); margin: 0 0 2px 0; font-weight: bold; }
            .sub-title { font-size: 11px; color: var(--text-sub); }
            .btn-top { background: #1a2338; color: var(--text-main); border: 1px solid #2c3856; padding: 6px 14px; border-radius: 8px; font-size: 12px; cursor: pointer; }
            .btn-top:hover, .btn-top:focus-visible { background: #263655; border-color: var(--accent-blue); outline: none; }
            .details-panel { background: #0e1524; border: 1px solid #2c3856; border-radius: 12px; margin: -6px 0 18px; padding: 14px 16px; }
            .details-panel[hidden] { display: none; }
            .details-panel h2 { font-size: 13px; margin: 0 0 8px; }
            .details-panel p { color: var(--text-sub); font-size: 12px; line-height: 1.65; margin: 0; }

            /* 手動運用についての注記 */
            .notice-banner { background: #1c2c1f; border: 1px solid #2f5136; color: #bfe8c6; padding: 12px 16px; border-radius: 12px; font-size: 12px; line-height: 1.6; margin-bottom: 18px; }
            .notice-banner b { color: #eafff0; display: block; margin-bottom: 2px; font-size: 13px; }

            .card {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 16px;
                box-shadow: 0 10px 24px rgba(0,0,0,0.45);
                position: relative;
                transition: border-color .2s ease, transform .2s ease;
            }
            .card:hover { border-color: #33507a; transform: translateY(-2px); }
            .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 12px; color: var(--text-sub); }

            .badge-manual { background: #1c2c52; color: #8fb4ff; padding: 2px 8px; border-radius: 999px; font-size: 10px; }

            /* ミニフィギュア(共通。プロジェクト内のオリジナル画像のみ使用) */
            .avatar-wrap { position: relative; display: inline-block; flex-shrink: 0; line-height: 0; }
            .avatar-sprite {
                display: block; width: 88px; height: 118px;
                background-image: url('/static/images/office-avatars-v1.png?v=2');
                background-size: 400% 200%; background-repeat: no-repeat;
                animation: fig-bob 3.6s ease-in-out infinite;
                filter: drop-shadow(0 8px 10px rgba(0,0,0,.26));
            }
            .avatar-sprite-president { background-position: 0% 0%; }
            .avatar-badge {
                position: absolute; right: -3px; bottom: -3px;
                width: 22px; height: 22px; border-radius: 50%;
                background: #0b0f1c; border: 2px solid var(--card-bg);
                display: flex; align-items: center; justify-content: center;
            }
            .avatar-badge svg circle:not([fill="none"]),
            .avatar-badge svg rect:not([fill="none"]),
            .avatar-badge svg ellipse:not([fill="none"]) { fill: var(--badge-fg); }
            .avatar-badge svg [fill="none"] { fill: none; }
            .avatar-badge svg [stroke-width] { stroke: var(--badge-fg); }

            /* アニメーション定義(prefers-reduced-motionで一括縮退。下部メディアクエリ参照) */
            @keyframes fig-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
            @keyframes stamp-press { 0%, 45%, 100% { transform: translateY(0); } 55% { transform: translateY(3px); } }
            @keyframes stamp-flash { 0%, 55%, 100% { opacity: 0; } 62% { opacity: 1; } 75% { opacity: 0; } }

            .prop-stamp .prop-stamp-head, .prop-stamp .prop-stamp-handle { animation: stamp-press 3.2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
            .prop-stamp .prop-stamp-mark { animation: stamp-flash 3.2s ease-in-out infinite; }

            @media (prefers-reduced-motion: reduce) {
                *, *::before, *::after {
                    animation-duration: 0.001ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.001ms !important;
                }
            }

            /* 社長からのひとこと */
            .intro-card { display: flex; gap: 15px; align-items: center; margin-bottom: 15px; }

            /* Pinterest・楽天ROOM・note・コンテンツスタジオの4枚 */
            .channel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
            .channel-role, .channel-next { font-size: 12px; color: var(--text-sub); line-height: 1.6; margin: 0 0 6px; }
            .channel-next b { color: var(--text-main); }
            .channel-link { display: inline-block; margin-top: 8px; background: #1a2338; color: var(--text-main); border: 1px solid #2c3856; padding: 6px 12px; border-radius: 8px; font-size: 11px; text-decoration: none; }
            .channel-link:hover, .channel-link:focus-visible { background: #263655; border-color: var(--accent-blue); outline: none; }

            /* レスポンシブ(小画面) */
            @media (max-width: 860px) {
                .channel-grid { grid-template-columns: 1fr; }
            }
            @media (max-width: 480px) {
                body { padding: 12px; }
                .header { flex-direction: column; }
                .intro-card { flex-direction: column; align-items: flex-start; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-title">
                <div>
                    <h1>会社の全体像ダッシュボード</h1>
                    <span class="sub-title">AIとガジェットで暮らしをラクにする発信の、投稿準備と手動確認をまとめた画面です</span>
                </div>
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
                <a class="btn-top" href="/office" style="text-decoration:none;">ライブオフィスを見る</a>
                <a class="btn-top" href="/revenue" style="text-decoration:none;">収益化ボードを見る</a>
                <button class="btn-top" type="button" id="details-toggle" aria-expanded="false" aria-controls="details-panel">詳細を表示</button>
            </div>
        </div>

        <div class="notice-banner">
            <b>この画面について。</b>
            この画面は投稿準備と手動確認のためのローカル画面であり、SNS投稿・分析取得・売上取得の自動連携は行いません。
        </div>

        <section class="details-panel" id="details-panel" hidden aria-labelledby="details-title">
            <h2 id="details-title">ダッシュボードの見方</h2>
            <p>表示中のカードは、Pinterest・楽天ROOM・note・コンテンツスタジオそれぞれの「現在の役割」と「次の行動」をまとめたものです。フォロワー数・PV・クリック数・売上額などの数値は表示していません。投稿の準備や確認は、それぞれのリンク先の画面で行ってください。</p>
        </section>

        <!-- 社長からのひとこと -->
        <div class="card intro-card">
            __AVATAR_PRESIDENT__
            <div style="flex-grow: 1;">
                <div style="font-size: 13px; font-weight: bold; margin-bottom: 4px;">柴犬社長</div>
                <div style="font-size: 12px; color: var(--text-sub); line-height: 1.6;">Pinterest・楽天ROOM・note・投稿づくりは、すべて社長が手動で担当しています。自動投稿・自動集計・外部サービスとの自動連携は行っていません。</div>
            </div>
        </div>

        <!-- Pinterest・楽天ROOM・note・コンテンツスタジオ -->
        <div class="channel-grid">
            <div class="card">
                <div class="card-header">
                    <span>Pinterest</span>
                    <span class="badge-manual">手動</span>
                </div>
                <p class="channel-role">現在の役割：初回投稿1件と投稿キュー3件の準備。</p>
                <p class="channel-next">次の行動：<b>投稿キューの内容を確認し、社長が手動でPinterestへ投稿・分析確認を行う。</b></p>
                <a class="channel-link" href="/content-studio/publish-queue">投稿キューを見る →</a>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>楽天ROOM</span>
                    <span class="badge-manual">手動</span>
                </div>
                <p class="channel-role">現在の役割：紹介できそうなカテゴリ候補の整理(商品はまだ未登録)。</p>
                <p class="channel-next">次の行動：<b>ROOM投稿準備を確認し、社長が手動で商品整理・投稿を行う。</b></p>
                <a class="channel-link" href="/revenue#room-prep">ROOM投稿準備を見る →</a>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>note</span>
                    <span class="badge-manual">手動</span>
                </div>
                <p class="channel-role">現在の役割：初回記事1本を準備済み(まだ未公開)。</p>
                <p class="channel-next">次の行動：<b>note初回記事を確認し、社長が手動でnoteに貼り付けて公開する。</b></p>
                <a class="channel-link" href="/content-studio/note-first-article">note初回記事を見る →</a>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>コンテンツスタジオ</span>
                    <span class="badge-manual">手動</span>
                </div>
                <p class="channel-role">現在の役割：投稿テーマ・投稿パッケージ・計画のたたき台づくり。</p>
                <p class="channel-next">次の行動：<b>投稿企画工場で次のテーマ・投稿パッケージを作成する。</b></p>
                <a class="channel-link" href="/content-studio">投稿企画工場を見る →</a>
            </div>
        </div>

        <script>
            const detailsToggle = document.getElementById('details-toggle');
            const detailsPanel = document.getElementById('details-panel');
            detailsToggle.addEventListener('click', () => {
                const willOpen = detailsPanel.hidden;
                detailsPanel.hidden = !willOpen;
                detailsToggle.setAttribute('aria-expanded', String(willOpen));
                detailsToggle.textContent = willOpen ? '詳細を閉じる' : '詳細を表示';
            });
        </script>
    </body>
    </html>
    """
  # プレースホルダーをミニフィギュアのSVG断片へ置換する(単純な文字列置換
  # のみ。DB・API・ネットワーク通信には一切関与しない)。
  avatars = {
      "__AVATAR_PRESIDENT__": _avatar("president", "stamp", "#f59e0b"),
  }
  for placeholder, avatar_svg in avatars.items():
    html_content = html_content.replace(placeholder, avatar_svg)

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
@hive_db.require_permission("read")
def list_employees():
  try:
    return hive_db.success_response(
        hive_db.list_rows("employees", order_by="id ASC")
    )
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


@app.route("/api/employees", methods=["POST"])
@hive_db.require_permission("write")
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
@hive_db.require_permission("read")
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
@hive_db.require_permission("write")
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
@hive_db.require_permission("read")
def get_mission(mission_id):
  try:
    row = hive_db.get_row("missions", mission_id)
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)
  if row is None:
    return hive_db.error_response("指定されたmissionが見つかりません。", 404)
  return hive_db.success_response(row)


@app.route("/api/tasks", methods=["GET"])
@hive_db.require_permission("read")
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
@hive_db.require_permission("write")
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
@hive_db.require_permission("write")
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
@hive_db.require_permission("read")
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
@hive_db.require_permission("write")
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
@hive_db.require_permission("read")
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
@hive_db.require_permission("write")
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
@hive_db.require_permission("read")
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
@hive_db.require_permission("write")
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
@hive_db.require_permission("admin")
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
@hive_db.require_permission("read")
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
@hive_db.require_permission("write")
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


# ---------------------------------------------------------------------------
# MISSION 014: 監査ログ参照API（admin専用・読み取り専用）
#
# GET /api/audit-logs のみを追加する。POST/PATCH/DELETEは実装しない。
# audit_logs以外のテーブルへは一切書き込まない。認証・権限判定・
# レート制限・「この参照操作自体をadmin操作として監査記録する」処理は
# すべて hive_db.require_permission("admin") が既存の仕組みのまま担う。
# ---------------------------------------------------------------------------


@app.route("/api/audit-logs", methods=["GET"])
@hive_db.require_permission("admin")
def list_audit_logs():
  limit_param = request.args.get("limit")
  if limit_param is None:
    limit = hive_db.AUDIT_LOG_DEFAULT_LIMIT
  else:
    try:
      limit = int(limit_param)
    except (TypeError, ValueError):
      return hive_db.error_response("limitは正の整数で指定してください。")
    if limit <= 0:
      return hive_db.error_response("limitは正の整数で指定してください。")
    if limit > hive_db.AUDIT_LOG_MAX_LIMIT:
      limit = hive_db.AUDIT_LOG_MAX_LIMIT
  try:
    return hive_db.success_response(hive_db.list_audit_logs(limit))
  except sqlite3.Error as e:
    return hive_db.error_response(str(e), 500)


if __name__ == "__main__":
  # localhost専用の起動ポート設定。
  # 既定は5050（ポート5000はmacOSのAirPlay Receiverが使用しているため）。
  # 環境変数 PORT で上書き可能。未設定・不正な値の場合は安全に5050へ
  # フォールバックする。host は外部公開を避けるため常に127.0.0.1固定。
  _port_env = os.environ.get("PORT")
  try:
    _port = int(_port_env) if _port_env else 5050
    if not (1 <= _port <= 65535):
      raise ValueError
  except (TypeError, ValueError):
    _port = 5050
  app.run(host="127.0.0.1", debug=True, port=_port)
