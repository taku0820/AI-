import sqlite3
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
DB_NAME = "ai_company.db"


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
                --bg-main: #0b0f17;
                --card-bg: #131b2e;
                --card-border: #1e293b;
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
            .dashboard-grid { display: grid; grid-template-columns: 1.2fr 1.2fr 1fr; gap: 15px; margin-bottom: 15px; }

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

            /* 1. 社長室（3D立体ハムスター型＆進捗バー） */
            .president-card { display: flex; gap: 15px; align-items: center; grid-column: span 1; }
            .hamster-3d {
                width: 75px; height: 75px; flex-shrink: 0;
                background: radial-gradient(circle at 35% 35%, #fcd34d 0%, #d97706 70%, #92400e 100%);
                border-radius: 50%;
                display: flex; align-items: center; justify-content: center;
                font-size: 38px;
                box-shadow: inset 0 6px 12px rgba(255,255,255,0.6), inset 0 -8px 16px rgba(0,0,0,0.6), 0 8px 16px rgba(0,0,0,0.5);
                position: relative;
                animation: floatHamster 3s infinite ease-in-out;
            }
            @keyframes floatHamster { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }

            .progress-item { margin-bottom: 8px; }
            .progress-label { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 3px; }
            .progress-bar-bg { background: #1e293b; height: 6px; border-radius: 3px; overflow: hidden; }
            .progress-bar-fill { background: #38bdf8; height: 100%; border-radius: 3px; }

            /* 2. 運用チームフロア */
            .team-grid-small { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .member-mini-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 10px; display: flex; align-items: center; gap: 10px; }
            .avatar-mini { width: 36px; height: 36px; border-radius: 50%; background: #334155; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }

            /* 3. 下段：WEB制作フロア（カード背景イラスト風＋人型アバター） */
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
                height: 110px;
                background: radial-gradient(circle at center, #312e81 0%, #0f172a 100%);
                display: flex; align-items: center; justify-content: center;
                position: relative;
            }
            .human-3d-avatar {
                width: 60px; height: 60px;
                border-radius: 50%;
                background: radial-gradient(circle at 35% 35%, #60a5fa, #1d4ed8);
                display: flex; align-items: center; justify-content: center;
                font-size: 28px;
                box-shadow: inset 0 4px 8px rgba(255,255,255,0.4), 0 6px 12px rgba(0,0,0,0.6);
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
                    <div class="hamster-3d">🐹</div>
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
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: #334155; display: flex; align-items: center; justify-content: center; font-size: 20px;">👩‍💼</div>
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
                        <div class="avatar-mini">👧</div>
                        <div>
                            <div style="font-size: 12px; font-weight: bold;">琴衣 (Lv.1)</div>
                            <div style="font-size: 10px; color: var(--text-sub);">A8.net提携確認</div>
                        </div>
                    </div>
                    <div class="member-mini-card">
                        <div class="avatar-mini">🧑‍🎨</div>
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

        <!-- 下段：WEB制作フロア（背景プレビュー付き人型3Dアバター） -->
        <div class="card" style="margin-bottom: 0;">
            <div class="card-header">
                <span>WEB制作フロア</span>
                <span style="font-size: 11px; color: var(--text-sub);">4人稼働</span>
            </div>
            <div class="web-team-grid">
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar">👩‍💻</div></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">美咲 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">WEBディレクター</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #34d399;">制約進行を整理中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar" style="background: radial-gradient(circle, #ec4899, #be185d);">🎨</div></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">海 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">UIデザイナー</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #38bdf8;">デザインを調整中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar" style="background: radial-gradient(circle, #10b981, #047857);">👨‍💻</div></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">湊 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">フロントエンド</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #fbbf24;">コードを実装中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar" style="background: radial-gradient(circle, #8b5cf6, #5b21b6);">📊</div></div>
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


if __name__ == "__main__":
  app.run(debug=True, port=5000)
