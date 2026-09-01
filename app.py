import os
import sqlite3
from urllib.parse import quote

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
DB_NAME = "ai_company.db"
PRESIDENT_IMAGE_CANDIDATES = ["president.png", "大統領.png", "社長.png"]


def _find_president_image():
  images_dir = os.path.join(app.static_folder, "images")
  for name in PRESIDENT_IMAGE_CANDIDATES:
    if os.path.exists(os.path.join(images_dir, name)):
      return name
  return None

SHIBA_AVATAR = """
<svg viewBox="0 0 100 190" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
  <defs>
    <radialGradient id="furGrad" cx="35%" cy="28%" r="80%">
      <stop offset="0%" stop-color="#fde68a"/>
      <stop offset="55%" stop-color="#d97706"/>
      <stop offset="100%" stop-color="#92400e"/>
    </radialGradient>
    <linearGradient id="lensGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#c084fc"/>
      <stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
    <filter id="neonGlow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="1.6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <ellipse cx="50" cy="184" rx="30" ry="5" fill="#000" opacity="0.28"/>

  <!-- tail -->
  <path d="M78 122 Q97 110 92 138 Q87 153 72 146 Z" fill="url(#furGrad)"/>

  <!-- sitting body -->
  <path d="M25 178 Q18 118 50 106 Q82 118 75 178 Z" fill="url(#furGrad)"/>
  <path d="M50 118 Q67 126 65 162 Q50 175 35 162 Q33 126 50 118 Z" fill="#fff7ed"/>

  <!-- back legs -->
  <ellipse cx="22" cy="172" rx="9" ry="11" fill="url(#furGrad)"/>
  <ellipse cx="78" cy="172" rx="9" ry="11" fill="url(#furGrad)"/>

  <!-- front paws -->
  <ellipse cx="39" cy="178" rx="9.5" ry="7" fill="#fff7ed"/>
  <ellipse cx="61" cy="178" rx="9.5" ry="7" fill="#fff7ed"/>

  <!-- headphone cable -->
  <path d="M18 92 Q6 128 20 172" stroke="#111827" stroke-width="2.6" fill="none" stroke-linecap="round"/>

  <!-- neck -->
  <rect x="38" y="94" width="24" height="20" fill="url(#furGrad)"/>

  <!-- ears -->
  <path d="M20 44 L9 12 L42 31 Z" fill="url(#furGrad)"/>
  <path d="M80 44 L91 12 L58 31 Z" fill="url(#furGrad)"/>
  <path d="M23 40 L17 20 L37 31 Z" fill="#fde68a" opacity="0.6"/>
  <path d="M77 40 L83 20 L63 31 Z" fill="#fde68a" opacity="0.6"/>

  <!-- head -->
  <circle cx="50" cy="68" r="37" fill="url(#furGrad)"/>

  <!-- muzzle -->
  <ellipse cx="50" cy="82" rx="21" ry="17" fill="#fff7ed"/>
  <path d="M43 73 Q50 69 57 73 Q57 80 50 82 Q43 80 43 73 Z" fill="#1c1917"/>

  <!-- eyes -->
  <circle cx="36" cy="64" r="4.3" fill="#1c1917"/>
  <circle cx="64" cy="64" r="4.3" fill="#1c1917"/>
  <circle cx="37.5" cy="62.3" r="1.3" fill="#fff"/>
  <circle cx="65.5" cy="62.3" r="1.3" fill="#fff"/>

  <!-- mouth -->
  <path d="M50 82 Q45 89 37 87" stroke="#1c1917" stroke-width="1.7" fill="none" stroke-linecap="round"/>
  <path d="M50 82 Q55 89 63 87" stroke="#1c1917" stroke-width="1.7" fill="none" stroke-linecap="round"/>
  <path d="M45 88 Q50 94 55 88 Q53 98 50 100 Q47 98 45 88 Z" fill="#f87171"/>

  <!-- headphone band -->
  <path d="M13 60 Q50 18 87 60" fill="none" stroke="#111827" stroke-width="7" stroke-linecap="round"/>

  <!-- headphone ear cups (neon) -->
  <g filter="url(#neonGlow)">
    <ellipse cx="12" cy="68" rx="9.5" ry="14" fill="#111827"/>
    <ellipse cx="12" cy="68" rx="9.5" ry="14" fill="none" stroke="#38bdf8" stroke-width="1.6"/>
    <ellipse cx="88" cy="68" rx="9.5" ry="14" fill="#111827"/>
    <ellipse cx="88" cy="68" rx="9.5" ry="14" fill="none" stroke="#f472b6" stroke-width="1.6"/>
  </g>

  <!-- neon ski goggles pushed up on forehead -->
  <g filter="url(#neonGlow)">
    <path d="M14 45 Q50 29 86 45 Q86 57 76 59 L24 59 Q14 57 14 45 Z" fill="#111827"/>
    <path d="M21 46 Q50 35 79 46 Q79 53 71 55 L29 55 Q21 53 21 46 Z" fill="url(#lensGrad)" opacity="0.92"/>
    <path d="M17 45 Q50 31 83 45" fill="none" stroke="#e0e7ff" stroke-width="1.4"/>
    <path d="M22 52 Q50 43 78 52" fill="none" stroke="#f472b6" stroke-width="1.2"/>
  </g>
</svg>
"""


def _person_avatar(uid, skin, shirt, pants, hair, hair_style="short", glasses=False):
  """3Dグロス調・全身の人型アバターSVGを生成する。"""
  if hair_style == "bob":
    hair_svg = (
        f'<path d="M20 46 Q17 68 24 78 L33 78 Q27 56 31 42 Q39 15 60 15'
        f' Q81 15 80 42 Q84 56 78 78 L87 78 Q94 68 91 46 Q90 8 55 7'
        f' Q21 8 20 46 Z" fill="{hair}"/>'
    )
  elif hair_style == "pigtails":
    hair_svg = (
        f'<circle cx="18" cy="52" r="10" fill="{hair}"/>'
        f'<circle cx="82" cy="52" r="10" fill="{hair}"/>'
        f'<path d="M23 40 Q23 13 50 13 Q77 13 77 40 Q77 30 60 25'
        f' Q50 31 40 25 Q23 30 23 40 Z" fill="{hair}"/>'
    )
  elif hair_style == "bun":
    hair_svg = (
        f'<circle cx="50" cy="8" r="9" fill="{hair}"/>'
        f'<path d="M22 42 Q19 20 50 14 Q81 20 78 42 Q78 30 60 25'
        f' Q50 31 40 25 Q22 30 22 42 Z" fill="{hair}"/>'
    )
  else:
    hair_svg = (
        f'<path d="M23 40 Q22 12 50 11 Q78 12 77 40 Q77 27 60 23'
        f' Q50 29 40 23 Q23 27 23 40 Z" fill="{hair}"/>'
    )

  glasses_svg = ""
  if glasses:
    glasses_svg = (
        '<circle cx="41" cy="39" r="7" fill="none" stroke="#0f172a"'
        ' stroke-width="2"/>'
        '<circle cx="59" cy="39" r="7" fill="none" stroke="#0f172a"'
        ' stroke-width="2"/>'
        '<line x1="48" y1="39" x2="52" y2="39" stroke="#0f172a"'
        ' stroke-width="2"/>'
    )

  return f"""
<svg viewBox="0 0 100 190" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
  <defs>
    <linearGradient id="skin-{uid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{skin[0]}"/>
      <stop offset="100%" stop-color="{skin[1]}"/>
    </linearGradient>
    <linearGradient id="shirt-{uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{shirt[0]}"/>
      <stop offset="100%" stop-color="{shirt[1]}"/>
    </linearGradient>
    <linearGradient id="pants-{uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{pants[0]}"/>
      <stop offset="100%" stop-color="{pants[1]}"/>
    </linearGradient>
  </defs>
  <ellipse cx="50" cy="184" rx="28" ry="5" fill="#000" opacity="0.28"/>
  <rect x="32" y="128" width="15" height="50" rx="7" fill="url(#pants-{uid})"/>
  <rect x="53" y="128" width="15" height="50" rx="7" fill="url(#pants-{uid})"/>
  <ellipse cx="39" cy="177" rx="9" ry="4.5" fill="#1e293b"/>
  <ellipse cx="61" cy="177" rx="9" ry="4.5" fill="#1e293b"/>
  <rect x="15" y="80" width="13" height="46" rx="6.5" fill="url(#skin-{uid})"/>
  <path d="M28 76 Q50 60 72 76 L76 130 Q50 140 24 130 Z" fill="url(#shirt-{uid})"/>
  <rect x="72" y="80" width="13" height="46" rx="6.5" fill="url(#skin-{uid})"/>
  <rect x="44" y="56" width="12" height="18" fill="url(#skin-{uid})"/>
  <circle cx="50" cy="40" r="27" fill="url(#skin-{uid})"/>
  {hair_svg}
  <circle cx="41" cy="39" r="2.6" fill="#292524"/>
  <circle cx="59" cy="39" r="2.6" fill="#292524"/>
  <path d="M42 49 Q50 54 58 49" stroke="#9a3412" stroke-width="2" fill="none" stroke-linecap="round"/>
  {glasses_svg}
</svg>
"""


SKIN_LIGHT = ("#ffe3c4", "#e8b48a")


def _president_avatar():
  name = _find_president_image()
  if not name:
    return SHIBA_AVATAR
  return (
      f'<img src="/static/images/{quote(name)}" alt="社長"'
      ' style="width:100%;height:100%;object-fit:contain;'
      ' object-position:bottom;">'
  )


AVATARS = {
    "%%AVATAR_AYA%%": _person_avatar(
        "aya", SKIN_LIGHT, ("#fb7185", "#be123c"), ("#334155", "#111827"),
        "#3f2a1d", hair_style="bob",
    ),
    "%%AVATAR_KOTOE%%": _person_avatar(
        "kotoe", SKIN_LIGHT, ("#fde68a", "#f59e0b"), ("#93c5fd", "#3b82f6"),
        "#d9a066", hair_style="pigtails",
    ),
    "%%AVATAR_AOI%%": _person_avatar(
        "aoi", SKIN_LIGHT, ("#5eead4", "#0d9488"), ("#334155", "#111827"),
        "#1c1917", hair_style="short",
    ),
    "%%AVATAR_MISAKI%%": _person_avatar(
        "misaki", SKIN_LIGHT, ("#60a5fa", "#1d4ed8"), ("#334155", "#111827"),
        "#5b3a29", hair_style="bun",
    ),
    "%%AVATAR_UMI%%": _person_avatar(
        "umi", SKIN_LIGHT, ("#f9a8d4", "#be185d"), ("#334155", "#111827"),
        "#7c2d12", hair_style="bob",
    ),
    "%%AVATAR_MINATO%%": _person_avatar(
        "minato", SKIN_LIGHT, ("#6ee7b7", "#047857"), ("#334155", "#111827"),
        "#6b4226", hair_style="short", glasses=True,
    ),
    "%%AVATAR_ITO%%": _person_avatar(
        "ito", SKIN_LIGHT, ("#c4b5fd", "#5b21b6"), ("#334155", "#111827"),
        "#111827", hair_style="bob", glasses=True,
    ),
}


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

            /* 1. 社長室（3D柴犬アバター＆進捗バー） */
            .president-card { display: flex; gap: 15px; align-items: center; grid-column: span 1; }
            .hamster-3d {
                width: 110px; height: 150px; flex-shrink: 0;
                display: flex; align-items: center; justify-content: center;
                filter: drop-shadow(0 8px 14px rgba(0,0,0,0.6));
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
            .avatar-mini { width: 46px; height: 78px; flex-shrink: 0; display: flex; align-items: flex-end; justify-content: center; }
            .avatar-accounting { width: 44px; height: 74px; flex-shrink: 0; display: flex; align-items: flex-end; justify-content: center; }

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
                width: 74px; height: 100px;
                display: flex; align-items: flex-end; justify-content: center;
                filter: drop-shadow(0 6px 10px rgba(0,0,0,0.6));
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
                    <div class="hamster-3d">%%AVATAR_SHIBA%%</div>
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
                    <div class="avatar-accounting">%%AVATAR_AYA%%</div>
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
                        <div class="avatar-mini">%%AVATAR_KOTOE%%</div>
                        <div>
                            <div style="font-size: 12px; font-weight: bold;">琴衣 (Lv.1)</div>
                            <div style="font-size: 10px; color: var(--text-sub);">A8.net提携確認</div>
                        </div>
                    </div>
                    <div class="member-mini-card">
                        <div class="avatar-mini">%%AVATAR_AOI%%</div>
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
                    <div class="room-preview"><div class="human-3d-avatar">%%AVATAR_MISAKI%%</div></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">美咲 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">WEBディレクター</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #34d399;">制約進行を整理中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar">%%AVATAR_UMI%%</div></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">海 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">UIデザイナー</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #38bdf8;">デザインを調整中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar">%%AVATAR_MINATO%%</div></div>
                    <div class="web-member-info">
                        <div style="font-weight: bold; font-size: 13px;">湊 (Lv.1)</div>
                        <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 6px;">フロントエンド</div>
                        <div style="background: #0b0f17; padding: 4px; border-radius: 6px; font-size: 10px; color: #fbbf24;">コードを実装中</div>
                    </div>
                </div>
                <div class="web-member-card">
                    <div class="room-preview"><div class="human-3d-avatar">%%AVATAR_ITO%%</div></div>
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
  for placeholder, svg in AVATARS.items():
    html_content = html_content.replace(placeholder, svg)
  html_content = html_content.replace("%%AVATAR_SHIBA%%", _president_avatar())
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
