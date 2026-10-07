"""AI Hive のライブオフィス画面。

すべてブラウザ内だけで描画する表示演出。DB/API/監査ログ/外部通信は使わず、
社長室の会話も保存されないローカルの定型リアクションである。
"""

import json
import os

from flask import render_template_string

# MISSION 091: 収益化ボード・AIオフィスの分析表示(葵)で使う、媒体ごとの
# 実績指標の定義(REVENUE_METRIC_FIELDS)を、dashboard_db.pyの定義と
# 二重管理にならないよう共有する。dashboard_db.py側はoffice_views.pyに
# 依存しないため、循環importにはならない。
import dashboard_db


SPRITES = ("president", "ayaka", "kotoe", "aoi", "misaki", "umi", "minato", "ito")


def figure(key, label):
  """名前テキストを別に置くため、絵は読み上げない装飾にする。"""
  if key not in SPRITES:
    raise ValueError("unknown office figure")
  return f'<span class="figure avatar-{key}" aria-hidden="true"></span><span class="sr-only">{label}</span>'


# MISSION 025: 実データ連携(work_logsの読み取り専用表示)用の追加スタイル。
# 既存の巨大な圧縮済みSTYLEブロックへ直接手を入れず、可読性のため別ブロック
# として追加する。副作用のあるアニメーションは追加せず、既存の
# prefers-reduced-motion(*, *::before, *::after を対象)の縮退にそのまま従う。
LIVE_DATA_STYLE = """
<style>
.status-chip{display:inline-block;width:9px;height:9px;border-radius:50%;margin-left:6px;vertical-align:middle;background:#3a4560}
.status-chip.status-done{background:var(--green)}
.status-chip.status-progress{background:var(--blue);animation:pulse 1.8s infinite}
.status-chip.status-pending,.status-chip.status-none{background:#4c5b78}
.desk em{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 4px}
.approval small{display:block;margin-top:4px;font-size:9px;font-weight:400;opacity:.85}
.command{margin-top:14px;background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px}
.command-stats{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 10px}
.command-stats .stat{background:#0f1a2c;border:1px solid var(--edge);border-radius:10px;padding:10px 16px;min-width:88px;text-align:center}
.command-stats .stat b{display:block;font-size:20px;color:var(--ink);line-height:1.2}
.command-stats .stat span{font-size:10px;color:var(--sub)}
.command-note{margin:0 0 12px;font-size:11px;color:var(--sub)}
.command-block{margin-top:12px}
.command-block h3{margin:0 0 6px;font-size:12px;color:var(--sub);font-weight:700;letter-spacing:.03em}
.command-block ul{margin:0;padding-left:18px;font-size:12px;line-height:1.7;color:var(--ink)}
.command-block p{margin:0;font-size:12px;line-height:1.5;color:var(--ink)}
.quick-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.qa-btn{background:#142039;color:var(--ink);border:1px solid var(--edge);border-radius:9px;padding:8px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.qa-btn:hover,.qa-btn:focus-visible{border-color:var(--blue);color:var(--blue)}
a.qa-btn{text-decoration:none;display:inline-block}
.desk{background:none;border:0;margin:0;padding:0;font:inherit;color:inherit;text-align:center;cursor:pointer}
.desk:focus-visible{outline:3px solid var(--blue);outline-offset:4px;border-radius:12px}
@keyframes desk-highlight{0%,100%{outline-color:var(--blue)}50%{outline-color:var(--green)}}
.desk.is-target{outline:3px solid var(--blue);outline-offset:4px;border-radius:12px;animation:desk-highlight 1.6s ease-in-out 3}
.desk-detail{margin-top:12px;padding:14px 16px;background:var(--panel);border:1px solid var(--edge);border-radius:16px;position:relative}
.desk-detail[hidden]{display:none}
.desk-detail-close{position:absolute;top:10px;right:10px;width:28px;height:28px;border-radius:50%;background:#0f1a2c;border:1px solid var(--edge);color:var(--ink);cursor:pointer;font-size:14px;line-height:1;font-family:inherit}
.desk-detail-close:hover,.desk-detail-close:focus-visible{border-color:var(--blue);color:var(--blue)}
.desk-detail h2{margin:0 26px 2px 0;font-size:16px}
.desk-detail-role{margin:0 0 10px;font-size:11px;color:var(--sub)}
.desk-detail-facts{margin:0 0 10px;display:grid;gap:6px}
.desk-detail-facts div{display:flex;gap:8px;font-size:12px;flex-wrap:wrap}
.desk-detail-facts dt{color:var(--sub);min-width:96px;flex-shrink:0}
.desk-detail-facts dd{margin:0;color:var(--ink)}
.desk-detail-disclaimer{margin:0;font-size:10px;color:var(--sub);line-height:1.5;border-top:1px dashed var(--edge);padding-top:8px}
.revenue-board{max-width:900px;margin:0 auto}
.revenue-notice{background:#1c2c1f;border:1px solid #2f5136;color:#bfe8c6;padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:16px}
.revenue-notice b{color:#eafff0;display:block;margin-bottom:2px;font-size:13px}
.revenue-card{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:14px 16px}
.revenue-card.revenue-focus{background:linear-gradient(135deg,#16233c,#0f1a2c);border:1px solid var(--blue);margin-bottom:16px}
.revenue-tag{display:inline-block;background:#0b2540;color:var(--blue);font-size:10px;font-weight:700;letter-spacing:.04em;padding:3px 10px;border-radius:999px;margin-bottom:6px}
.revenue-focus h2{margin:0;font-size:20px}
.revenue-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.revenue-card h3{margin:0 0 8px;font-size:13px;color:var(--sub);font-weight:700;letter-spacing:.03em}
.revenue-card p{margin:0;font-size:13px;line-height:1.6}
.revenue-card ul,.revenue-card ol{margin:0;padding-left:18px;font-size:12px;line-height:1.8}
.revenue-price-note{font-size:11px;color:var(--sub);margin:0 0 8px}
.revenue-price-tiers{list-style:none;padding:0;display:grid;gap:6px}
.revenue-price-tiers li{display:flex;justify-content:space-between;gap:8px;background:#0f1a2c;border:1px solid var(--edge);border-radius:8px;padding:6px 10px;font-size:12px}
.revenue-price-tiers b{color:var(--sub);font-weight:600}
.revenue-pipeline{display:flex;gap:6px;list-style:none;padding:0;flex-wrap:wrap}
.revenue-pipeline li{background:#0f1a2c;border:1px solid var(--edge);border-radius:999px;padding:5px 12px;font-size:11px}
.revenue-pipeline li:not(:last-child):after{content:"→";margin-left:8px;color:var(--sub)}
.revenue-priorities li{margin-bottom:4px}
.revenue-footnote{margin-top:16px;font-size:11px;color:var(--sub);text-align:center}
.revenue-metric-entry{margin-bottom:16px}
.revenue-metric-fieldgroup[hidden]{display:none}
.revenue-metric-summary{margin-bottom:16px}
.revenue-metric-summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.revenue-metric-summary-card{background:#0b1120;border:1px solid #253651;border-radius:10px;padding:10px 12px}
.revenue-metric-summary-card h3{margin:0 0 6px;font-size:13px;color:var(--sub)}
.revenue-metric-summary-list{list-style:none;margin:0;padding:0;font-size:12px;line-height:1.8}
.revenue-metric-summary-list b{color:var(--ink)}
.revenue-metric-history{margin:6px 0 0;padding-left:16px;font-size:11px;color:var(--sub);line-height:1.7}
@media(max-width:760px){.revenue-grid,.revenue-metric-summary-grid{grid-template-columns:1fr}}
.room-prep-section{margin-top:24px}
.room-prep-section h2{font-size:16px;margin:0 0 10px}
.room-prep-notice{background:#101827;border:1px solid var(--blue);color:var(--ink);padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:12px}
.room-prep-notice b{color:var(--blue);display:block;margin-bottom:4px;font-size:13px}
.room-prep-notice ul{margin:6px 0 0;padding-left:18px}
.room-prep-pr-note{background:#3d3106;border:1px solid #fbbf24;color:#fde68a;padding:10px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:14px}
.room-prep-pr-note b{color:#fde68a}
.room-prep-published{background:#063d2c;border:1px solid var(--green);color:var(--ink);padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:14px}
.room-prep-published h3{margin:0 0 8px;font-size:13px;color:var(--green)}
.room-prep-published ul{list-style:none;margin:0;padding:0}
.room-published-item{margin-bottom:8px}
.room-published-item:last-child{margin-bottom:0}
.room-published-next{display:block;color:var(--sub);margin-top:2px}
.room-prep-account-note{margin:10px 0 0;padding-top:10px;border-top:1px dashed #1e775e;color:var(--sub);font-size:11px;line-height:1.6}
.room-prep-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:14px 16px;margin-bottom:12px}
.room-prep-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.room-prep-head h3{margin:0;font-size:14px}
.room-prep-status{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px;flex-shrink:0}
.room-prep-status.status-planning{background:#2a2f3d;color:#94a3b8}
.room-prep-status.status-awaiting_president{background:#3d3106;color:#fbbf24}
.room-prep-status.status-manual_registration{background:#063d2c;color:var(--green)}
.room-prep-meta{font-size:12px;color:var(--sub);margin:0 0 8px;line-height:1.6}
.room-prep-genres{list-style:none;padding:0;display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}
.room-prep-genres li{background:#0f1a2c;border:1px solid var(--edge);border-radius:999px;padding:4px 10px;font-size:11px}
.room-prep-checks h4{margin:8px 0 4px;font-size:11px;color:var(--sub)}
.room-prep-checks ul{margin:0;padding-left:18px;font-size:12px;line-height:1.7}
@media(max-width:760px){.room-prep-head{flex-direction:column;align-items:flex-start}}
.content-studio{max-width:1000px;margin:0 auto}
.cs-today-step{background:linear-gradient(135deg,#16233c,#0f1a2c);border:1px solid var(--blue);border-radius:16px;padding:18px 20px;margin-bottom:18px}
.cs-today-step-label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;color:var(--blue);background:#0b2540;border-radius:999px;padding:3px 10px;margin-bottom:10px}
.cs-today-step-task{margin:0 0 14px;font-size:16px;font-weight:700;color:var(--ink);line-height:1.5}
.cs-today-step-button{display:inline-block;background:#147fac;color:#fff;font-weight:700;font-size:13px;border-radius:10px;padding:10px 18px;text-decoration:none}
.cs-today-step-button:hover,.cs-today-step-button:focus-visible{background:#1894c9}
.cs-details{margin-top:4px}
.cs-details>summary{cursor:pointer;list-style:none;font-size:12px;font-weight:700;color:var(--ink);background:#142039;border:1px solid var(--edge);border-radius:9px;padding:8px 12px;display:inline-block}
.cs-details>summary::-webkit-details-marker{display:none}
.cs-details>summary::marker{content:""}
.cs-details>summary:after{content:"▾";margin-left:6px;font-size:10px}
.cs-details[open]>summary{border-color:var(--blue);color:var(--blue)}
.cs-details-body{margin-top:14px}
.cs-theme{font-size:12px;color:var(--sub);margin:0 0 16px}
.cs-theme b{color:var(--ink)}
.cs-room-policy{background:#101827;border:1px solid var(--blue);color:var(--ink);padding:10px 12px;border-radius:10px;font-size:12px;line-height:1.6;margin:0 0 16px}
.cs-room-policy b{color:var(--blue);display:block;margin-bottom:2px;font-size:13px}
.cs-first-post-link{display:inline-block;margin:0 0 18px;font-size:12px;background:#0b2540;color:var(--blue);border:1px solid var(--blue);border-radius:999px;padding:8px 14px;text-decoration:none}
.cs-first-post-link:hover{background:#123258}
.cs-plan-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px 18px;margin-bottom:16px}
.cs-plan-card h3{margin:0 0 12px;font-size:16px}
.cs-plan-fields{margin:0;display:grid;gap:4px 0}
.cs-plan-fields dt{font-size:11px;color:var(--sub);margin-top:10px}
.cs-plan-fields dt:first-child{margin-top:0}
.cs-plan-fields dd{margin:2px 0 0;font-size:13px;color:var(--ink);line-height:1.6}
.cs-footnote{margin-top:16px;font-size:11px;color:var(--sub);text-align:center}
@media(max-width:760px){.cs-plan-card{padding:14px 16px}}
.first-post-board{max-width:1000px;margin:0 auto}
.desk-setup-board{max-width:1000px;margin:0 auto}
.publish-queue-board{max-width:1000px;margin:0 auto}
.pq-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px 18px;margin-bottom:22px}
.pq-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.pq-card-head h3{margin:0;font-size:16px}
.pq-status-badge{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px;flex-shrink:0}
.pq-status-badge.status-awaiting_president{background:#3d3106;color:#fbbf24}
.pq-status-badge.status-published{background:#063d2c;color:var(--green)}
.pq-topics-label{font-size:11px;color:var(--sub);margin:14px 0 6px}
.pq-topics{list-style:none;padding:0;display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px}
.pq-topics li{background:#0f1a2c;border:1px solid var(--edge);border-radius:999px;padding:4px 10px;font-size:11px;color:var(--sub)}
.pq-room-link{background:#101827;border:1px dashed var(--edge);color:var(--sub);padding:10px 12px;border-radius:10px;font-size:12px;line-height:1.6;margin:0 0 10px}
.pq-manual-note{background:#2c1f1c;border:1px solid #513629;color:#f0c9a5;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.6;margin:0 0 14px}
.pq-manual-note b{color:#ffe9d6}
@media(max-width:760px){.pq-card-head{flex-direction:column;align-items:flex-start}}
.note-article-board{max-width:760px;margin:0 auto}
.note-hero{position:relative;border-radius:16px;overflow:hidden;margin-bottom:8px;background:#0b0d12}
.note-hero-img{display:block;width:100%;height:auto}
.note-hero-scrim{position:absolute;inset:0;background:linear-gradient(90deg,rgba(6,10,20,.76) 0%,rgba(6,10,20,.42) 55%,rgba(6,10,20,0) 82%)}
.note-hero-overlay{position:absolute;left:0;top:0;height:100%;width:72%;display:flex;align-items:center;padding:0 4%;box-sizing:border-box}
.note-hero-title{margin:0;font-size:clamp(14px,2.05vw,24px);font-weight:800;color:#fff;line-height:1.42;text-shadow:0 2px 14px rgba(0,0,0,.7);word-break:keep-all;overflow-wrap:normal}
@media(max-width:600px){.note-hero-overlay{width:100%;padding:0 5%}.note-hero-title{font-size:clamp(11.5px,4vw,15.5px)}}
/* MISSION 039.1: 投稿キュー(.pq-card内)のヒーロー画像だけ、タイトルを
   左下ではなく左上の暗い余白へ寄せる。note初回記事のヒーロー(.note-hero、
   .pq-cardの外)は上記の垂直中央寄せのまま変更しない。フォントサイズ・
   文字色・影(コントラスト)は変更せず、配置(align-items)と上端の余白
   (padding-top)だけを上書きする。デスクトップ・モバイルのどちらでも
   同じ比率(%)で効くため、専用のメディアクエリは不要。 */
.pq-card .note-hero-overlay{align-items:flex-start;padding-top:9%}
.note-article-visible h2.note-article-title{margin:0 0 10px;font-size:19px}
.note-article-visible h3.note-section-heading{margin:20px 0 8px;font-size:15px;color:var(--blue)}
.note-article-visible h4.note-subheading{margin:12px 0 4px;font-size:12px;color:var(--sub);font-weight:700;letter-spacing:.03em}
.note-article-visible p{margin:0 0 10px;font-size:13px;line-height:1.8}
.note-article-visible .note-article-conclusion{background:#101827;border:1px solid var(--edge);border-radius:10px;padding:10px 12px}
.note-article-visible .note-article-conclusion p{margin:0 0 8px}
.note-article-visible .note-article-conclusion p:last-child{margin-bottom:0}
.note-article-copy-source{display:none}
.note-tags{list-style:none;padding:0;display:flex;gap:6px;flex-wrap:wrap;margin:0 0 4px}
.note-tags li{background:#0f1a2c;border:1px solid var(--edge);border-radius:999px;padding:5px 12px;font-size:12px;color:var(--sub)}
.fp-notice{background:#1c2c1f;border:1px solid #2f5136;color:#bfe8c6;padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:14px}
.fp-notice b{color:#eafff0;display:block;margin-bottom:2px;font-size:13px}
.fp-note{padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.6;margin:0 0 14px}
.fp-note.fp-note-warn{background:#2c1f1c;border:1px solid #513629;color:#f0c9a5}
.fp-note.fp-note-info{background:#101827;border:1px solid var(--edge);color:var(--sub)}
.fp-note b{color:#ffe9d6}
.fp-note-info b{color:var(--ink)}
.fp-theme{font-size:12px;color:var(--sub);margin:0 0 16px}
.fp-theme b{color:var(--ink)}
.fp-section-title{font-size:16px;margin:22px 0 12px}
.fp-pin-layout{display:grid;grid-template-columns:280px 1fr;gap:18px;align-items:start}
.fp-svg-wrap{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:10px;position:relative}
.fp-svg-wrap svg{display:block;width:100%;height:auto;border-radius:10px}
.fp-svg-ratio{font-size:10px;color:var(--sub);text-align:center;margin-top:6px}
.fp-png-download{display:block;text-align:center;margin-top:10px;background:#0b2540;color:var(--blue);border:1px solid var(--blue);border-radius:999px;padding:9px 12px;font-size:12px;text-decoration:none}
.fp-png-download:hover{background:#123258}
.fp-png-hint{font-size:10px;color:var(--sub);text-align:center;margin-top:6px;line-height:1.5}
.fp-fields{display:grid;gap:12px}
.fp-field{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:12px 14px}
.fp-field-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px}
.fp-field-head h4{margin:0;font-size:11px;color:var(--sub);font-weight:700;letter-spacing:.03em}
.fp-copy-btn{background:#142039;color:var(--ink);border:1px solid var(--edge);border-radius:8px;padding:4px 10px;font-size:10px;cursor:pointer;font-family:inherit}
.fp-copy-btn:hover,.fp-copy-btn:focus-visible{border-color:var(--blue);color:var(--blue)}
.fp-field p{margin:0;font-size:13px;line-height:1.6}
.fp-checklist{list-style:none;padding:0;margin:0;display:grid;gap:8px}
.fp-checklist li{display:flex;align-items:flex-start;gap:8px;font-size:12px;line-height:1.5;background:var(--panel);border:1px solid var(--edge);border-radius:10px;padding:8px 10px}
.fp-checklist input{margin-top:2px}
.fp-footnote{margin-top:18px;font-size:11px;color:var(--sub);text-align:center}
@media(max-width:760px){.fp-pin-layout{grid-template-columns:1fr}.fp-svg-wrap{max-width:280px;margin:0 auto}}
.weekly-plan-board{max-width:900px;margin:0 auto}
.wp-notice{background:#1c2c1f;border:1px solid #2f5136;color:#bfe8c6;padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:14px}
.wp-notice b{color:#eafff0;display:block;margin-bottom:2px;font-size:13px}
.wp-callout{background:#101827;border:1px solid var(--blue);color:var(--ink);padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:18px}
.wp-callout b{color:var(--blue);display:block;margin-bottom:4px;font-size:13px}
.wp-callout ul{margin:6px 0 0;padding-left:18px}
.wp-day-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:14px 16px;margin-bottom:12px}
.wp-day-card.is-published{border:2px solid var(--green)}
.wp-day-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.wp-day-head h3{margin:0;font-size:15px}
.wp-day-status{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px}
.wp-day-status.status-published{background:#063d2c;color:var(--green)}
.wp-day-status.status-manual_candidate{background:#0b2540;color:var(--blue)}
.wp-day-status.status-review{background:#3d3106;color:#fbbf24}
.wp-day-status.status-draft{background:#2a2f3d;color:#94a3b8}
.wp-day-meta{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--sub);margin-bottom:8px}
.wp-day-meta span b{color:var(--ink);font-weight:600}
.wp-day-checks{margin:8px 0 0;padding-left:18px;font-size:12px;line-height:1.7;color:var(--ink)}
.wp-day-note{font-size:11px;color:var(--sub);margin:8px 0 0;line-height:1.6}
.wp-footnote{margin-top:16px;font-size:11px;color:var(--sub);text-align:center}
@media(max-width:760px){.wp-day-meta{flex-direction:column;gap:4px}}
.room-candidate-board{max-width:900px;margin:0 auto}
.room-candidate-bucket-summary{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.rc-bucket-chip{flex:1 1 140px;background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:10px 14px;text-align:center}
.rc-bucket-chip b{display:block;font-size:22px;color:var(--ink);line-height:1.3}
.rc-bucket-chip span{font-size:11px;color:var(--sub)}
.rc-bucket-chip[data-bucket="today"]{border-color:var(--blue)}
.rc-bucket-chip[data-bucket="today"] b{color:var(--blue)}
.room-candidate-bucket-note{margin:0 0 14px;font-size:11px;color:var(--sub);line-height:1.6}
.room-candidate-bucket-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px;padding-bottom:10px;border-bottom:1px dashed var(--edge)}
.room-candidate-bucket-label{font-size:12px;color:var(--sub)}
.room-candidate-bucket-label b{color:var(--ink)}
.room-candidate-bucket-buttons{display:flex;gap:6px;flex-wrap:wrap}
.room-candidate-bucket-btn{background:#142039;color:var(--ink);border:1px solid var(--edge);border-radius:999px;padding:5px 12px;font-size:11px;cursor:pointer;font-family:inherit}
.room-candidate-bucket-btn:hover,.room-candidate-bucket-btn:focus-visible{border-color:var(--blue);color:var(--blue)}
.room-candidate-bucket-btn.is-active{background:#0b2540;border-color:var(--blue);color:var(--blue);font-weight:700}
.room-candidate-rules{background:#101827;border:1px solid var(--blue);color:var(--ink);padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:14px}
.room-candidate-rules b{color:var(--blue);display:block;margin-bottom:4px;font-size:13px}
.room-candidate-rules ul{margin:6px 0 0;padding-left:18px}
.room-candidate-date-nav{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px;background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:10px 14px}
.room-candidate-date-nav input[type="date"]{background:#0b1120;color:var(--ink);border:1px solid var(--edge);border-radius:8px;padding:6px 10px;font-family:inherit}
.room-candidate-date-nav button{background:#142039;color:var(--ink);border:1px solid var(--edge);border-radius:8px;padding:6px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.room-candidate-date-nav button:hover,.room-candidate-date-nav button:focus-visible{border-color:var(--blue);color:var(--blue)}
.room-candidate-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:14px 16px;margin-bottom:14px}
.room-candidate-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.room-candidate-head h3{margin:0;font-size:14px}
.room-candidate-verifying-badge{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px;background:#3d3106;color:#fbbf24}
.room-candidate-verifying-badge[hidden]{display:none}
.rc-field-error{margin:4px 0 0;font-size:11px;color:#fbbf24;font-weight:700}
.rc-field-error[hidden]{display:none}
.room-candidate-advanced{margin:10px 0;border-top:1px dashed var(--edge);padding-top:10px}
.room-candidate-advanced>summary{cursor:pointer;list-style:none;font-size:12px;font-weight:700;color:var(--ink);background:#142039;border:1px solid var(--edge);border-radius:9px;padding:7px 12px;display:inline-block}
.room-candidate-advanced>summary::-webkit-details-marker{display:none}
.room-candidate-advanced>summary::marker{content:""}
.room-candidate-advanced>summary:after{content:"▾";margin-left:6px;font-size:10px}
.room-candidate-advanced[open]>summary{border-color:var(--blue);color:var(--blue)}
.room-candidate-advanced-body{margin-top:10px}
.room-candidate-field{margin-bottom:10px}
.room-candidate-field label{display:block;font-size:11px;color:var(--sub);margin-bottom:4px}
.room-candidate-field input[type="text"],.room-candidate-field textarea{width:100%;background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:8px 10px;font-family:inherit;font-size:13px;box-sizing:border-box}
.room-candidate-field textarea{resize:vertical}
.room-candidate-reaction-inputs{display:flex;gap:10px;flex-wrap:wrap}
.room-candidate-reaction-inputs label{font-size:11px;color:var(--sub);display:flex;flex-direction:column;gap:4px}
.room-candidate-reaction-inputs input{background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:6px 8px;font-family:inherit;font-size:12px;width:130px;box-sizing:border-box}
.room-candidate-hashtags{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-bottom:10px}
.room-candidate-hashtags input{background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:6px 8px;font-family:inherit;font-size:12px;box-sizing:border-box}
.room-candidate-checks{display:flex;flex-direction:column;gap:6px;font-size:12px;line-height:1.5;padding-top:8px;border-top:1px dashed var(--edge)}
.room-candidate-checks label{display:flex;align-items:flex-start;gap:8px}
.room-candidate-intro-count{color:var(--sub);font-weight:400}
.room-candidate-generate-row{margin-bottom:10px}
.room-candidate-generate-btn{background:#142039;color:var(--ink);border:1px solid var(--edge);border-radius:8px;padding:7px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.room-candidate-generate-btn:hover,.room-candidate-generate-btn:focus-visible{border-color:var(--blue);color:var(--blue)}
.room-candidate-bulk-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px;background:var(--panel);border:1px solid var(--blue);border-radius:12px;padding:10px 14px}
.room-candidate-bulk-actions button{background:#142039;color:var(--ink);border:1px solid var(--blue);border-radius:8px;padding:8px 14px;font-size:12px;cursor:pointer;font-family:inherit}
.room-candidate-bulk-actions button:hover,.room-candidate-bulk-actions button:focus-visible{background:#1b2d4b}
.room-candidate-bulk-actions p{margin:0;font-size:11px;color:var(--sub);line-height:1.6}
@media(max-width:760px){.room-candidate-date-nav{flex-direction:column;align-items:stretch}.room-candidate-reaction-inputs{flex-direction:column}.room-candidate-reaction-inputs input{width:100%}.room-candidate-bulk-actions{flex-direction:column;align-items:stretch}.room-candidate-bucket-row{align-items:flex-start;flex-direction:column}}
.note-candidate-board{max-width:900px;margin:0 auto}
.note-candidate-date-nav{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px;background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:10px 14px}
.note-candidate-date-nav input[type="date"]{background:#0b1120;color:var(--ink);border:1px solid var(--edge);border-radius:8px;padding:6px 10px;font-family:inherit}
.note-candidate-date-nav button{background:#142039;color:var(--ink);border:1px solid var(--edge);border-radius:8px;padding:6px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.note-candidate-date-nav button:hover,.note-candidate-date-nav button:focus-visible{border-color:var(--blue);color:var(--blue)}
.note-candidate-generate-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px;background:var(--panel);border:1px solid var(--blue);border-radius:12px;padding:10px 14px}
.note-candidate-generate-actions button{background:#142039;color:var(--ink);border:1px solid var(--blue);border-radius:8px;padding:8px 14px;font-size:12px;cursor:pointer;font-family:inherit}
.note-candidate-generate-actions button:hover,.note-candidate-generate-actions button:focus-visible{background:#1b2d4b}
.note-candidate-generate-actions p{margin:0;font-size:11px;color:var(--sub);line-height:1.6}
.note-candidate-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:14px 16px;margin-bottom:14px}
.note-candidate-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.note-candidate-head h3{margin:0;font-size:14px}
.note-candidate-field{margin-bottom:10px}
.note-candidate-field label{display:block;font-size:11px;color:var(--sub);margin-bottom:4px}
.note-candidate-field input[type="text"],.note-candidate-field textarea,.note-candidate-field select{width:100%;background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:8px 10px;font-family:inherit;font-size:13px;box-sizing:border-box}
.note-candidate-field textarea{resize:vertical}
.note-candidate-headings{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:10px}
.note-candidate-headings input{background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:6px 8px;font-family:inherit;font-size:12px;box-sizing:border-box}
.note-candidate-hashtags{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-bottom:10px}
.note-candidate-hashtags input{background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:6px 8px;font-family:inherit;font-size:12px;box-sizing:border-box}
.note-candidate-checks{display:flex;flex-direction:column;gap:6px;font-size:12px;line-height:1.5;padding-top:8px;border-top:1px dashed var(--edge)}
.note-candidate-checks label{display:flex;align-items:flex-start;gap:8px}
.note-candidate-count{color:var(--sub);font-weight:400}
.note-candidate-price-note{font-size:11px;color:var(--sub);margin:4px 0 0;line-height:1.6}
@media(max-width:760px){.note-candidate-date-nav{flex-direction:column;align-items:stretch}.note-candidate-generate-actions{flex-direction:column;align-items:stretch}}
.command-center{max-width:1100px;margin:0 auto}
.cc-data-storage{margin-top:22px;background:var(--panel);border:1px solid var(--blue);border-radius:14px;padding:16px 18px}
.cc-data-storage h2{margin:0 0 8px;font-size:15px;color:var(--ink)}
.cc-data-storage-note{margin:0 0 12px;font-size:12px;color:var(--sub);line-height:1.6}
.cc-data-storage-counts{display:flex;gap:18px;flex-wrap:wrap;margin:0 0 14px;font-size:12px;color:var(--sub)}
.cc-data-storage-counts b{color:var(--ink);font-size:14px}
.cc-data-storage button{background:#147fac;color:#fff;font-weight:700;font-size:13px;border:0;border-radius:10px;padding:10px 18px;cursor:pointer;font-family:inherit}
.cc-data-storage button:hover,.cc-data-storage button:focus-visible{background:#1894c9}
.cc-data-storage button:disabled{opacity:.6;cursor:default}
.cc-data-storage-result{margin:10px 0 0;font-size:12px;color:var(--green);min-height:1.5em}
.cc-data-storage-hint{margin:10px 0 0;font-size:11px;color:var(--sub);line-height:1.6}
.cc-data-protection{margin-top:22px}
.cc-data-protection-summary{display:flex;gap:18px;flex-wrap:wrap;margin:0 0 14px;font-size:12px;color:var(--sub)}
.cc-data-protection-summary b{color:var(--ink);font-size:14px}
.cc-restore-box{margin-top:16px}
.cc-restore-title{margin:0 0 8px;font-size:14px;color:var(--ink)}
.cc-topbar{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:12px 16px;margin-bottom:16px;font-size:12px;color:var(--sub);line-height:1.7}
.cc-topbar b{color:var(--ink)}
.cc-topbar .cc-approver{color:var(--green);font-weight:700}
.cc-section-title{font-size:15px;margin:22px 0 10px;color:var(--ink);border-left:4px solid var(--blue);padding-left:10px}
.cc-section-title:first-of-type{margin-top:0}
.cc-check-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.cc-check-category{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:12px 14px}
.cc-check-category h3{margin:0 0 10px;font-size:13px;color:var(--blue)}
.cc-check-fields{display:flex;flex-direction:column;gap:8px;margin-bottom:10px}
.cc-check-fields label{font-size:11px;color:var(--sub);display:flex;flex-direction:column;gap:4px}
.cc-check-fields input{background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:7px 9px;font-family:inherit;font-size:13px;box-sizing:border-box}
.cc-confirmed-row{display:flex;align-items:flex-start;gap:8px;font-size:12px;padding-top:8px;border-top:1px dashed var(--edge);color:var(--sub)}
.cc-pending-box{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:14px 16px;margin-bottom:6px}
.cc-pending-empty{color:var(--sub);font-size:12px;margin:0 0 10px}
.cc-pending-box textarea{width:100%;background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:8px 10px;font-family:inherit;font-size:13px;box-sizing:border-box;resize:vertical}
.cc-pending-note{font-size:11px;color:var(--sub);margin:10px 0 0;line-height:1.6}
.cc-dept-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.cc-dept-card{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:12px 14px}
.cc-dept-card h3{margin:0 0 6px;font-size:13px;color:var(--blue)}
.cc-dept-card p{margin:0;font-size:12px;color:var(--sub);line-height:1.6}
.cc-dept-note{font-size:11px;color:var(--sub);margin:10px 0 14px;line-height:1.6}
.cc-decision-box{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:14px 16px;margin-bottom:6px}
.cc-decision-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:10px}
.cc-decision-fields label{font-size:11px;color:var(--sub);display:block;margin-bottom:4px}
.cc-decision-fields input,.cc-decision-fields select,.cc-decision-fields textarea{width:100%;background:#0b1120;color:var(--ink);border:1px solid #385072;border-radius:8px;padding:7px 9px;font-family:inherit;font-size:13px;box-sizing:border-box}
.cc-decision-fields textarea{resize:vertical}
.cc-decision-add-btn{background:#142039;color:var(--ink);border:1px solid var(--blue);border-radius:8px;padding:8px 14px;font-size:12px;cursor:pointer;font-family:inherit}
.cc-decision-add-btn:hover,.cc-decision-add-btn:focus-visible{background:#1b2d4b}
.cc-decision-note{font-size:11px;color:var(--sub);margin:10px 0 0;line-height:1.6}
.cc-decision-log-list{margin-top:14px;padding-top:12px;border-top:1px dashed var(--edge)}
.cc-decision-log-empty{color:var(--sub);font-size:12px;margin:0}
.cc-decision-log-entry{background:#0b1120;border:1px solid #253651;border-radius:10px;padding:10px 12px;margin-bottom:8px;font-size:12px;line-height:1.7}
.cc-decision-log-entry b{color:var(--blue);display:inline-block;min-width:5.5em}
.cc-work-ledger-detail{margin:0 0 10px;font-size:12px;color:var(--sub)}
.cc-work-ledger-detail summary{cursor:pointer;color:var(--blue);font-size:12px;margin-bottom:8px}
.cc-work-ledger-item{position:relative}
.wl-complete-btn{margin-top:8px;background:#142039;color:var(--ink);border:1px solid var(--green);border-radius:8px;padding:6px 12px;font-size:11px;cursor:pointer;font-family:inherit}
.wl-complete-btn:hover,.wl-complete-btn:focus-visible{background:#123022}
.wl-complete-btn:disabled{opacity:.6;cursor:default}
@media(max-width:760px){.cc-check-grid,.cc-dept-grid,.cc-decision-fields{grid-template-columns:1fr}}
.ai-office{max-width:1160px;margin:0 auto;--cyan:#22d3ee}
.ai-office-directive-card{background:linear-gradient(135deg,#16233c,#0f1a2c);border:1px solid var(--blue);border-radius:16px;padding:18px 20px;margin-bottom:14px}
.ai-office-directive-label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;color:var(--blue);background:#0b2540;border-radius:999px;padding:3px 10px;margin-bottom:10px}
.ai-office-directive-task{margin:0 0 6px;font-size:17px;font-weight:700;color:var(--ink);line-height:1.5}
.ai-office-directive-reason{margin:0 0 14px;font-size:12px;color:var(--sub)}
.ai-office-directive-button{display:inline-block;background:#147fac;color:#fff;font-weight:700;font-size:13px;border-radius:10px;padding:10px 18px;text-decoration:none}
.ai-office-directive-button:hover,.ai-office-directive-button:focus-visible{background:#1894c9}
.ai-office-demo-banner{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#3d3106;border:1px solid #7a5c0a;color:#fbbf24;border-radius:12px;padding:10px 14px;margin-bottom:10px;font-size:12px;font-weight:700}
.ai-office-demo-banner span{font-weight:400;color:#f4d98b}
.ai-office-record-mode-badge{background:#142039;border:1px solid var(--edge);color:var(--sub);border-radius:10px;padding:8px 14px;margin-bottom:18px;font-size:12px;text-align:center}
.ai-office-record-mode-badge.is-real{border-color:#34d399;color:var(--ink);background:#0b3d2e}
.ai-office-analytics-report{background:#142039;border:1px solid var(--edge);border-radius:10px;padding:8px 14px;margin-bottom:18px;font-size:12px}
.ai-office-analytics-report b{color:var(--blue);display:block;margin-bottom:2px}
.ai-office-analytics-report p{margin:0;color:var(--sub)}
.ai-office-analytics-report.is-real{border-color:#34d399}
.ai-office-analytics-report.is-real p{color:var(--ink)}
.ai-office-role-diff{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:12px 14px;margin-bottom:18px;font-size:12px;color:var(--sub);line-height:1.7}
.ai-office-role-diff b{color:var(--ink)}
.ai-office-section{margin:24px 0}
.ai-office-section h2{font-size:15px;margin:0 0 10px;color:var(--ink);border-left:4px solid var(--cyan);padding-left:10px}
.ai-office-section:first-of-type h2{margin-top:0}
.ai-office-floor{position:relative;padding:18px;border-radius:20px;border:1px solid var(--edge);background:linear-gradient(160deg,#0d1626 0%,#0a121f 65%),repeating-linear-gradient(115deg,#16233b 0 2px,transparent 2px 46px)}
.ai-office-floor-grid{position:relative;z-index:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
.ai-office-desk{background:linear-gradient(180deg,#101a2f,#0c1524);border:1px solid var(--edge);border-top:3px solid var(--cyan);border-radius:14px;padding:14px 16px}
.ai-office-desk-symbol{width:42px;height:42px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#1c3a52,#0b1a2b);border:2px solid var(--cyan);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:11px;color:var(--cyan);margin-bottom:10px}
.ai-office-desk h3{margin:0 0 2px;font-size:14px;color:var(--ink)}
.ai-office-desk-role{font-size:11px;color:var(--cyan);margin:0 0 8px;font-weight:700}
.ai-office-desk-summary{font-size:11px;color:var(--sub);line-height:1.6;margin:0 0 8px}
.ai-office-desk-scope{font-size:10px;color:var(--sub);line-height:1.6;margin:0 0 10px;padding-top:8px;border-top:1px dashed var(--edge)}
.ai-office-status-badge{display:inline-block;font-size:10px;font-weight:700;padding:3px 10px;border-radius:999px}
.ai-office-status-working{background:#0b2733;color:var(--cyan)}
.ai-office-status-waiting{background:#142039;color:#7ca0c9}
.ai-office-status-pending{background:#3d3106;color:#fbbf24}
.ai-office-status-demo_done{background:#0b3d2e;color:#34d399}
.ai-office-task-list,.ai-office-work-list,.ai-office-deliverables-list,.ai-office-activity-feed{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.ai-office-task-list li,.ai-office-work-list li,.ai-office-deliverables-list li{background:var(--panel);border:1px solid var(--edge);border-radius:10px;padding:10px 12px;font-size:12px;line-height:1.6;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center}
.ai-office-task-dept{color:var(--cyan);font-weight:700;font-size:11px;margin-right:8px}
.ai-office-demo-tag{display:inline-block;font-size:10px;font-weight:700;color:#fbbf24;background:#3d3106;padding:2px 8px;border-radius:999px;white-space:nowrap}
.ai-office-activity-feed li{padding:8px 10px;background:#0b1120;border:1px solid #253651;border-radius:8px;font-size:12px;color:var(--sub)}
.ai-office-queue-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.ai-office-queue-item{background:var(--panel);border:1px solid var(--edge);border-left:3px solid var(--cyan);border-radius:10px;padding:12px 14px}
.ai-office-queue-media{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;color:var(--blue);background:#0b2540;border-radius:999px;padding:3px 10px;margin-bottom:6px}
.ai-office-queue-content{margin:0 0 6px;font-size:13px;color:var(--ink);line-height:1.6;word-break:break-word}
.ai-office-queue-meta{margin:0 0 4px;font-size:11px;color:var(--sub)}
.ai-office-queue-meta b{color:var(--ink)}
.ai-office-queue-next{margin:0 0 8px;font-size:12px;color:var(--ink);line-height:1.6;word-break:break-word}
.ai-office-queue-next b{color:var(--cyan)}
.ai-office-queue-link{display:inline-block;font-size:11px}
.ai-office-queue-empty{list-style:none;background:var(--panel);border:1px dashed var(--edge);border-radius:10px;padding:14px;text-align:center;color:var(--sub);font-size:12px}
.ai-office-recent-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.ai-office-recent-item{background:var(--panel);border:1px solid var(--edge);border-left:3px solid var(--green);border-radius:10px;padding:12px 14px}
.ai-office-recent-header{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.ai-office-recent-date{font-size:11px;color:var(--sub);font-weight:700}
.ai-office-chat-demo{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:14px 16px}
.ai-office-chat-demo .log{height:auto;max-height:none}
.ai-office-chat-note{margin:10px 0 0;font-size:11px;color:var(--sub);line-height:1.6;padding-top:10px;border-top:1px dashed var(--edge)}
.ai-office-freshness-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.ai-office-freshness-card{background:var(--panel);border:1px solid var(--edge);border-radius:10px;padding:10px 12px;text-align:center;font-size:12px}
.ai-office-freshness-card b{display:block;margin-bottom:6px;color:var(--ink)}
.ai-office-freshness-status{display:inline-block;font-size:10px;font-weight:700;padding:3px 8px;border-radius:999px;background:#142039;color:var(--sub)}
.ai-office-freshness-note{font-size:11px;color:var(--sub);margin:10px 0 0;line-height:1.6}
.ai-office-deliverables-list a{margin-left:6px;font-size:11px}
.ai-office-floormap{position:relative;overflow:hidden;border-radius:22px;border:1px solid var(--edge);padding:20px 18px 22px;margin-bottom:26px;background:linear-gradient(165deg,#0c1424 0%,#080e1a 70%),repeating-linear-gradient(115deg,rgba(34,211,238,.05) 0 2px,transparent 2px 60px),repeating-linear-gradient(25deg,rgba(34,211,238,.035) 0 2px,transparent 2px 60px)}
.ai-office-report-banner{position:relative;z-index:1;margin:0 0 14px;padding:10px 14px;border:1px solid #a78bfa;border-radius:12px;background:#1c1533e0;color:var(--ink);font-size:14px;font-weight:700;text-align:center;line-height:1.5;word-break:break-word}
.ai-office-floormap-caption{position:relative;z-index:1;margin:0 0 14px;font-size:11px;color:var(--sub);line-height:1.6}
.ai-office-floormap-caption b{color:var(--ink)}
.ai-office-floormap-image-wrap{position:relative;z-index:1;text-align:center;margin-bottom:14px}
.ai-office-floormap-stage{position:relative;display:inline-block;width:100%;max-width:860px;line-height:0}
.ai-office-floormap-image{display:block;width:100%;height:auto;border-radius:16px;border:1px solid #1c3350;box-shadow:0 0 0 1px rgba(34,211,238,.15),0 18px 45px #0007}
.ai-office-floormap-overlay{position:absolute;inset:0;pointer-events:none}
.ai-office-floormap-token{position:absolute;width:112px;height:126px;transform:translate(-50%,-78%);transition:left 1.6s ease,top 1.6s ease;z-index:2;pointer-events:none}
.ai-office-floormap-sprite{position:absolute;inset:0;background-image:url(/static/images/ai-office-team-3d.png);background-repeat:no-repeat;background-size:300% 400%;transition:transform .5s ease}
.ai-office-floormap-sprite.is-facing-left{transform:scaleX(-1)}
.ai-office-floormap-sprite.is-facing-right{transform:scaleX(1)}
.ai-office-idle-typing{animation:ai-office-idle-typing 3.6s ease-in-out infinite}
.ai-office-idle-reading{animation:ai-office-idle-reading 4.2s ease-in-out infinite}
.ai-office-idle-analyzing{animation:ai-office-idle-analyzing 3.9s ease-in-out infinite}
.ai-office-idle-waiting{animation:ai-office-idle-waiting 4.6s ease-in-out infinite}
@keyframes ai-office-idle-typing{0%,100%{transform:translate(-50%,-78%) translateY(0) rotate(0deg)}50%{transform:translate(-50%,-78%) translateY(-2px) rotate(.6deg)}}
@keyframes ai-office-idle-reading{0%,40%,100%{transform:translate(-50%,-78%) translateY(0)}20%{transform:translate(-50%,-78%) translateY(-1.5px)}}
@keyframes ai-office-idle-analyzing{0%,100%{transform:translate(-50%,-78%) scale(1)}50%{transform:translate(-50%,-78%) scale(1.012)}}
@keyframes ai-office-idle-waiting{0%,100%{transform:translate(-50%,-78%) scale(1)}50%{transform:translate(-50%,-78%) scale(1.02)}}
.ai-office-floormap-token.is-working{animation:ai-office-work-pulse 1.4s ease-in-out infinite}
.ai-office-floormap-token.is-moving{animation:ai-office-walk-bob .55s ease-in-out infinite}
@keyframes ai-office-work-pulse{0%,100%{transform:translate(-50%,-78%) translateY(0)}50%{transform:translate(-50%,-78%) translateY(-3px)}}
@keyframes ai-office-walk-bob{0%,100%{transform:translate(-50%,-78%) translateY(0)}50%{transform:translate(-50%,-78%) translateY(-6px)}}
.ai-office-footstep{position:absolute;bottom:6%;left:50%;width:38%;height:10px;transform:translateX(-50%);border-radius:50%;background:radial-gradient(ellipse at center,rgba(34,211,238,.6),transparent 72%);opacity:0;transition:opacity .3s ease;pointer-events:none}
.ai-office-floormap-token.is-moving .ai-office-footstep{opacity:1}
.ai-office-nameplate{position:absolute;top:100%;left:50%;transform:translateX(-50%);margin-top:2px;white-space:nowrap;font-size:10px;font-weight:700;color:var(--ink);background:#0b1120e8;border:1px solid var(--edge);border-radius:8px;padding:2px 7px 2px 5px;display:flex;align-items:center;gap:4px;pointer-events:none}
.ai-office-nameplate-dot{width:7px;height:7px;border-radius:50%;flex:none;background:var(--sub)}
.ai-office-nameplate-dot-working{background:var(--cyan);box-shadow:0 0 5px 1px rgba(34,211,238,.85)}
.ai-office-nameplate-dot-pending{background:#fbbf24;box-shadow:0 0 5px 1px rgba(251,191,36,.85)}
.ai-office-nameplate-dot-waiting{background:#3b5c86}
.ai-office-nameplate-dot-demo_done{background:#34d399;box-shadow:0 0 5px 1px rgba(52,211,153,.85)}
.ai-office-nameplate-phase{color:var(--cyan);font-weight:700}
.ai-office-nameplate-phase:empty{display:none}
.ai-office-report-ring{position:absolute;left:50%;bottom:4%;width:44%;height:12px;transform:translateX(-50%);border-radius:50%;border:2px solid transparent;opacity:0;transition:opacity .3s ease,border-color .3s ease,box-shadow .3s ease;pointer-events:none}
.ai-office-floormap-token-working .ai-office-report-ring{opacity:.8;border-color:var(--cyan);box-shadow:0 0 6px 1px rgba(34,211,238,.55)}
.ai-office-floormap-token-pending .ai-office-report-ring{opacity:.8;border-color:#fbbf24;box-shadow:0 0 6px 1px rgba(251,191,36,.5)}
.ai-office-floormap-token-waiting .ai-office-report-ring{opacity:.45;border-color:#3b5c86}
.ai-office-floormap-token-demo_done .ai-office-report-ring{opacity:.8;border-color:#34d399;box-shadow:0 0 6px 1px rgba(52,211,153,.5)}
.ai-office-floormap-token.is-working .ai-office-report-ring,
.ai-office-floormap-token.is-moving .ai-office-report-ring{animation:ai-office-report-ring-pulse 1.2s ease-in-out infinite}
.ai-office-floormap-token.is-report-mover .ai-office-report-ring,
.ai-office-floormap-token.is-report-receiver .ai-office-report-ring{opacity:1;border-color:#a78bfa;box-shadow:0 0 10px 3px rgba(167,139,250,.75);animation:ai-office-report-ring-pulse 1.3s ease-in-out infinite}
@keyframes ai-office-report-ring-pulse{0%,100%{opacity:.55}50%{opacity:1}}
.ai-office-report-connector{position:absolute;height:0;border-top:2px dashed #a78bfa;transform-origin:0 50%;opacity:0;transition:opacity .3s ease;z-index:1;pointer-events:none}
.ai-office-report-connector.is-visible{opacity:.9}
.ai-office-report-connector:after{content:"";position:absolute;right:-1px;top:-5px;border-width:5px 0 5px 9px;border-style:solid;border-color:transparent transparent transparent #a78bfa}
.ai-office-floormap-overlay.is-reporting .ai-office-floormap-token{opacity:.5;transition:opacity .4s ease}
.ai-office-floormap-overlay.is-reporting .ai-office-floormap-token.is-report-mover,
.ai-office-floormap-overlay.is-reporting .ai-office-floormap-token.is-report-receiver{opacity:1}
.ai-office-monitor-glow{position:absolute;width:9px;height:7px;border-radius:2px;background:var(--cyan);opacity:.18;filter:blur(.5px);transition:opacity .3s ease;transform:translate(calc(-50% + 62px),calc(-50% - 96px));pointer-events:none;z-index:1}
.ai-office-monitor-glow-ambient{animation:ai-office-monitor-idle-flicker 3.4s ease-in-out infinite}
.ai-office-monitor-glow.is-active{animation:ai-office-monitor-flicker 1.4s steps(2) infinite}
@keyframes ai-office-monitor-flicker{0%,100%{opacity:.85}50%{opacity:.3}}
@keyframes ai-office-monitor-idle-flicker{0%,100%{opacity:.14}50%{opacity:.32}}
.ai-office-lounge-decor{position:absolute;width:1px;height:1px;pointer-events:none;z-index:1}
.ai-office-lounge-cup{position:absolute;left:-8px;top:14px;width:16px;height:10px;border-radius:0 0 6px 6px;background:linear-gradient(180deg,#2a3a54,#1a2740);border:1px solid #3b5c86}
.ai-office-lounge-steam{position:absolute;left:-3px;bottom:22px;width:5px;height:12px;border-radius:50%;background:radial-gradient(ellipse at center,rgba(210,230,255,.5),transparent 75%);opacity:0;animation:ai-office-lounge-steam-rise 3.2s ease-in infinite}
.ai-office-lounge-steam-2{left:1px;animation-delay:-1.6s}
@keyframes ai-office-lounge-steam-rise{0%{opacity:0;transform:translateY(0) scale(.8)}30%{opacity:.55}80%{opacity:0}100%{opacity:0;transform:translateY(-20px) scale(1.2)}}
.ai-office-command-pulse{position:absolute;left:0;top:0;width:26px;height:26px;transform:translate(-50%,-95%);border-radius:50%;pointer-events:none;z-index:1;opacity:0;box-shadow:0 0 0 0 rgba(34,211,238,.6)}
.ai-office-command-pulse.is-active{animation:ai-office-command-pulse-ring 1.1s ease-out}
@keyframes ai-office-command-pulse-ring{0%{opacity:.9;box-shadow:0 0 0 0 rgba(34,211,238,.7)}100%{opacity:0;box-shadow:0 0 0 26px rgba(34,211,238,0)}}
.ai-office-progress-board{position:absolute;left:10px;top:10px;z-index:4;max-width:44%;background:#0b1c2cf0;border:1px solid var(--cyan);border-radius:10px;padding:6px 10px;font-size:10px;line-height:1.5;color:var(--ink);pointer-events:none}
.ai-office-progress-board b{display:block;color:var(--cyan);font-size:10px;margin-bottom:2px}
.ai-office-progress-board span{display:block;color:var(--sub)}
.ai-office-floormap-overlay.is-paused,.ai-office-floormap-overlay.is-paused *{animation-play-state:paused!important}
.ai-office-floormap-bubble{position:absolute;transform:translate(-50%,calc(-100% - 104px));width:max-content;max-width:150px;background:#0b1c2cf0;border:1px solid var(--cyan);border-radius:10px;padding:6px 9px;font-size:10px;line-height:1.4;color:var(--ink);opacity:0;transition:opacity .3s ease;z-index:3;text-align:left}
.ai-office-floormap-bubble.is-visible{opacity:1}
.ai-office-floormap-bubble:after{content:"";position:absolute;left:50%;bottom:-6px;transform:translateX(-50%);border-width:6px 6px 0;border-style:solid;border-color:var(--cyan) transparent transparent}
.ai-office-floormap-bubble-receiver{border-color:#34d399}
.ai-office-floormap-bubble-receiver:after{border-color:#34d399 transparent transparent}
.ai-office-floormap-controls{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:12px}
.ai-office-anim-toggle{background:#142039;color:var(--ink);border:1px solid var(--cyan);border-radius:8px;padding:7px 14px;font-size:12px;cursor:pointer;font-family:inherit}
.ai-office-anim-toggle:hover,.ai-office-anim-toggle:focus-visible{background:#1b2d4b}
.ai-office-floormap-speech{max-width:860px;margin:10px auto 0;background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:10px 14px;font-size:12px;color:var(--sub);line-height:1.6;min-height:1.6em;text-align:left}
.ai-office-floormap-speech b{color:var(--cyan)}
.ai-office-floormap-speech-note{max-width:860px;margin:6px auto 0;font-size:10px;color:var(--sub);line-height:1.5;text-align:center}
.ai-office-floormap-hint{margin:10px auto 0;max-width:860px;font-size:11px;color:var(--sub);line-height:1.6}
.ai-office-report-panel{position:relative;z-index:1;margin:10px auto 0;max-width:860px;background:#1c1533e0;border:1px solid #a78bfa;border-radius:12px;padding:10px 14px;display:flex;flex-direction:column;gap:4px}
.ai-office-report-panel-line{margin:0;font-size:12px;line-height:1.6;color:var(--ink);word-break:break-word}
.ai-office-report-panel-line:empty{display:none}
.ai-office-report-legend{position:relative;z-index:1;margin:8px auto 0;max-width:860px;font-size:10px;color:var(--sub);text-align:center}
.ai-office-floormap-status-strip{position:relative;z-index:1;list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:10px;justify-content:center}
.ai-office-strip-chip{display:flex;align-items:center;gap:8px;background:linear-gradient(180deg,#101c33,#0a1424);border:1px solid var(--edge);border-radius:999px;padding:6px 14px 6px 6px;min-width:190px}
.ai-office-char-avatar{width:30px;height:30px;flex:none;border-radius:50%;background:radial-gradient(circle at 35% 30%,#1c3a52,#0b1a2b);border:2px solid var(--sub);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:10px;color:var(--ink)}
.ai-office-char-avatar-working{border-color:var(--cyan);box-shadow:0 0 12px 3px rgba(34,211,238,.55);animation:ai-office-pulse 1.8s ease-in-out infinite}
.ai-office-char-avatar-pending{border-color:#fbbf24;box-shadow:0 0 10px 2px rgba(251,191,36,.45)}
.ai-office-char-avatar-waiting{border-color:#3b5c86;box-shadow:0 0 6px 1px rgba(59,92,134,.35)}
.ai-office-char-avatar-demo_done{border-color:#34d399;box-shadow:0 0 10px 2px rgba(52,211,153,.4)}
@keyframes ai-office-pulse{0%,100%{box-shadow:0 0 12px 3px rgba(34,211,238,.55)}50%{box-shadow:0 0 20px 6px rgba(34,211,238,.85)}}
.ai-office-sprite-avatar{background-image:url(/static/images/ai-office-team-3d.png);background-repeat:no-repeat;background-size:300% 400%;background-color:#0b1120;box-shadow:0 2px 6px #0008}
.ai-office-strip-info{min-width:0;display:flex;flex-direction:column;gap:1px}
.ai-office-strip-info b{font-size:11px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:760px){.ai-office-floor-grid,.ai-office-freshness-grid{grid-template-columns:1fr}.ai-office-task-list li,.ai-office-work-list li{flex-direction:column;align-items:flex-start}.ai-office-floormap-status-strip{flex-direction:column;align-items:stretch}.ai-office-strip-chip{min-width:0}}
@media(max-width:480px){.ai-office-floormap-token{width:72px;height:81px}.ai-office-floormap-bubble{max-width:104px;font-size:9px;padding:5px 7px;transform:translate(-50%,calc(-100% - 68px))}.ai-office-nameplate{font-size:8px;padding:1px 5px}.ai-office-monitor-glow{transform:translate(calc(-50% + 40px),calc(-50% - 62px))}.ai-office-progress-board{max-width:62%;font-size:9px;padding:5px 7px}.ai-office-progress-board b{font-size:9px}.ai-office-command-pulse{width:18px;height:18px}.ai-office-report-banner{font-size:11px;padding:8px 10px}.ai-office-report-panel-line{font-size:11px}.ai-office-report-legend{font-size:9px}}
/* MISSION 083: オフィス・社長室・休憩室の3スペースで、AIオフィスと同じ
   スプライト社員トークンを再利用するための追加スタイル。 */
.space-roster-note{position:relative;z-index:1;margin:10px auto 0;max-width:860px;font-size:11px;color:var(--sub);line-height:1.6;text-align:center}
.space-status-list{position:relative;z-index:1;list-style:none;margin:12px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.space-status-list li{flex:1 1 220px;background:#0d1b2fe0;border:1px solid var(--edge);border-radius:10px;padding:8px 10px;font-size:11px;line-height:1.6;color:var(--sub)}
.space-status-list b{display:block;color:var(--ink);font-size:12px;margin-bottom:2px}
.space-status-list .is-real{border-color:#34d399;color:var(--ink)}
/* 休憩室の2つの訪問スロットは、既存のsofa-guest(pixel位置・モバイル
   対応済み)の中にAIオフィスと同じトークンを差し込むため、絶対配置を
   打ち消してsofa-guest内で自然に中央寄せされるようにする。 */
.sofa-guest .ai-office-floormap-token{position:relative;left:auto!important;top:auto!important;transform:none;display:inline-block;margin:0 auto;animation-delay:0s!important}
.sofa-guest .ai-office-floormap-token .ai-office-footstep{bottom:2%}
/* MISSION 083: オフィスの4人は、デスクトップでは横一列に並べているが、
   モバイル幅ではデスクと同じ2x2グリッドに合わせて再配置しないと、
   横幅が足りず重なってしまう(横スクロールは発生しないが、キャラクター
   同士が重なって見づらくなるため)。 */
@media(max-width:760px){
#space-token-office-room{left:17%!important;top:40%!important}
#space-token-office-rin{left:51%!important;top:40%!important}
#space-token-office-analytics{left:17%!important;top:66%!important}
#space-token-office-sou{left:51%!important;top:66%!important}
}
</style>
"""


# MISSION 053: オフィス・休憩室・社長室を「奥行きのある会社空間」へ強化する
# ための追加スタイル。既存の巨大なSTYLE文字列(部屋の骨格・座標)には最小限の
# 手（.figureの拡大縮小をCSS変数`--s`で扱えるようにする3箇所）しか入れず、
# 新規の見た目(照明・会議スペース・キャラクターの拡大縮小・社長の演出・
# 休憩室のキャラクター配置)はすべてこのブロックに分離する。DB/API/外部
# 通信は一切使わない、純粋な表示用CSSのみ。
DEPTH_STYLE = """
<style>
.cast-badge{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.04em;padding:3px 9px;border-radius:999px;background:#0d192bdc;border:1px solid #4a7595;color:#a8c0d7;margin-left:8px;vertical-align:middle}
.figure{-webkit-mask-image:radial-gradient(ellipse 68% 62% at 50% 42%,#000 62%,transparent 100%);mask-image:radial-gradient(ellipse 68% 62% at 50% 42%,#000 62%,transparent 100%)}
@media(min-width:761px){.office.scene{min-height:660px}}
.desk .desk-role{position:absolute;left:0;right:0;bottom:-3px;z-index:5;font-size:9px;color:#9fb3cf;font-style:normal;letter-spacing:.02em}
.desk em{bottom:-25px}
.desk .figure{bottom:40px}
.desk:before{height:20px}
.desk.desk-back{filter:brightness(.88) saturate(.88)}
.desk.desk-back:hover,.desk.desk-back:focus-visible{filter:none}
.desk.desk-front{--s:1.1;z-index:4}
.lamp{position:absolute;top:3%;left:47%;width:2px;height:12%;background:linear-gradient(#0000,#3a4560);z-index:1}
.lamp:after{content:"";position:absolute;left:50%;bottom:0;width:50px;height:50px;transform:translateX(-50%);border-radius:50%;background:radial-gradient(circle,#ffe9a8cc 0%,#ffe9a833 55%,transparent 72%)}
.lamp:before{content:"";position:absolute;left:50%;bottom:-6px;width:20px;height:12px;transform:translateX(-50%);background:#ecd9a0;border-radius:0 0 10px 10px;box-shadow:0 2px 16px 4px #ffdb8a80}
.meeting{position:absolute;right:5%;bottom:4%;width:150px;height:60px;z-index:1;text-align:center}
.meeting:after{content:"";position:absolute;left:50%;bottom:12px;width:82px;height:28px;transform:translateX(-50%);background:#2a3d58;border:3px solid #4a6a8f;border-radius:50%}
.meeting span{position:absolute;bottom:10px;font-size:20px}
.meeting span:nth-of-type(1){left:10px}
.meeting span:nth-of-type(2){right:10px}
.meeting small{position:absolute;left:0;right:0;top:0;color:#8ba2c2;font-size:9px;letter-spacing:.03em}
.ceo-desk{--s:1.32}
.ceo-spotlight{position:absolute;left:50%;bottom:4%;width:420px;height:420px;transform:translateX(-50%);border-radius:50%;background:radial-gradient(circle,#ffdb8a26 0%,#ffdb8a10 45%,transparent 70%);z-index:1}
.ceo-monitor{position:absolute;left:8%;bottom:30%;width:150px;background:#0d192bdc;border:1px solid #4a7595;border-radius:10px;padding:9px 11px;font-size:10px;line-height:1.7;color:#dceafa;z-index:4}
.ceo-monitor b{display:block;color:var(--green);font-size:10px;margin-bottom:4px}
.ceo-monitor div{display:flex;justify-content:space-between;gap:6px}
.ceo-monitor span:first-child{color:#a8c0d7}
.sofa{--s:1.05}
.sofa-guest{position:absolute;bottom:14px;z-index:3;width:120px;text-align:center}
.sofa-guest .figure{position:relative;left:auto;bottom:auto;display:inline-block;animation:work 3.4s ease-in-out infinite}
.sofa-guest-1{left:52px}
.sofa-guest-2{left:216px;}
.sofa-guest-2 .figure{animation-delay:.6s}
.sofa-chat{display:block;margin-top:6px;font-size:10px;line-height:1.4;color:#fff8e9;background:#0b1528d9;border:1px solid #3d5a86;border-radius:8px;padding:5px 8px}
.sofa-chat b{color:#8fd9ff;margin-right:3px}
.break-walker{--s:1.08;width:84px}
@media(max-width:760px){
.meeting{display:none}
.lamp{display:none}
.ceo-monitor{left:4%;bottom:auto;top:15%;width:118px}
.ceo-spotlight{width:260px;height:260px}
.break-walker{animation:none;right:4%;bottom:auto;top:14%}
.coffee{left:8%;right:auto;bottom:auto;top:48%;transform:scale(.65);transform-origin:top left}
.walker{animation:none;left:auto;right:8%;bottom:4%}
.sofa-guest{width:96px}
.sofa-guest-1{left:8px}
.sofa-guest-2{left:150px}
}
</style>
"""


STYLE = """
<style>
:root{--bg:#090c15;--panel:#121a2c;--edge:#293958;--ink:#f1f5f9;--sub:#a3b2c6;--blue:#38bdf8;--green:#34d399}*{box-sizing:border-box}body{margin:0;padding:20px;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.head,.tabs,main{max-width:1240px;margin:auto}.head{display:flex;justify-content:space-between;gap:12px;align-items:center;border-bottom:1px solid #202d47;padding-bottom:15px}.head h1{font-size:21px;margin:0 0 4px}.head p{margin:0;font-size:12px;color:var(--sub)}a,.chat-form button{color:var(--ink);text-decoration:none;font-size:12px;border:1px solid var(--edge);border-radius:9px;padding:8px 12px;background:#142039}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px;margin-bottom:15px}.tabs a.active,.tabs a:hover{border-color:var(--blue);color:var(--blue);background:#1b2d4b}.tabs-space{display:inline-block}.tabs-space>summary{list-style:none;cursor:pointer;color:var(--ink);font-size:12px;border:1px solid var(--edge);border-radius:9px;padding:8px 12px;background:#142039}.tabs-space>summary::-webkit-details-marker{display:none}.tabs-space>summary::marker{content:""}.tabs-space>summary:hover,.tabs-space[open]>summary{border-color:var(--blue);color:var(--blue);background:#1b2d4b}.tabs-space>summary:after{content:"▾";margin-left:6px;font-size:10px}.tabs-space-menu{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;padding:10px;background:var(--panel);border:1px solid var(--edge);border-radius:12px}.role-hint{margin:2px 0 4px;font-size:12px;color:var(--blue);font-weight:700}.scene{position:relative;min-height:590px;overflow:hidden;border:1px solid var(--edge);border-radius:20px;background:#142038;box-shadow:0 18px 45px #0007}.label{position:absolute;top:16px;left:18px;font-size:12px;font-weight:800;letter-spacing:.08em;z-index:6}.label span{color:var(--green);font-size:10px;margin-left:8px}.figure{display:block;width:74px;height:99px;background:url('/static/images/office-avatars-v1.png?v=2') no-repeat;background-size:400% 200%;filter:drop-shadow(0 7px 7px #0008);transform:scale(var(--s,1));transform-origin:bottom center}.avatar-president{background-position:0 0}.avatar-ayaka{background-position:33.333% 0}.avatar-kotoe{background-position:66.666% 0}.avatar-aoi{background-position:100% 0}.avatar-misaki{background-position:0 100%}.avatar-umi{background-position:33.333% 100%}.avatar-minato{background-position:66.666% 100%}.avatar-ito{background-position:100% 100%}.office{background:linear-gradient(#263b5b 0 44%,#c18c5e 44% 46%,#233247 46%)}.office:after{content:"";position:absolute;inset:46% 0 0;background:repeating-linear-gradient(90deg,#ffffff08 0 2px,transparent 2px 85px),linear-gradient(135deg,#28394e,#172235);z-index:0}.windows{position:absolute;left:9%;right:10%;top:11%;height:145px;display:flex;gap:15px}.windows i{flex:1;border:8px solid #354861;background:linear-gradient(#56c8ed 0 60%,#c4f3e9 60%);box-shadow:inset 0 0 0 3px #152237}.door{position:absolute;right:6%;top:27%;width:88px;height:180px;border:5px solid #3e2d25;border-radius:8px 8px 0 0;background:#784b38;text-align:center;padding-top:50px;z-index:3}.door b{display:block;font-size:24px}.door small{font-size:9px}.plant{position:absolute;bottom:20%;left:4%;font-size:48px;z-index:4}.desk{position:absolute;width:145px;height:165px;text-align:center;z-index:3}.desk .figure{position:absolute;left:36px;bottom:29px;animation:work 3.2s ease-in-out infinite}.desk:after{content:"";position:absolute;left:0;right:0;bottom:23px;height:44px;background:linear-gradient(#d8ad80,#7f4e32);border-top:5px solid #ffe0b3;border-radius:5px 5px 11px 11px;z-index:2}.desk:before{content:attr(data-screen);position:absolute;left:49px;bottom:66px;width:44px;height:32px;line-height:25px;color:#eaffff;background:#286da0;border:4px solid #111d2e;border-radius:5px;z-index:4;font:bold 13px monospace}.desk b,.desk em{position:absolute;left:0;right:0;bottom:2px;z-index:5;font-size:11px}.desk em{bottom:-13px;color:#b8c8da;font-size:9px;font-style:normal}.d1{left:7%;top:41%}.d2{left:27%;top:41%}.d3{left:47%;top:41%}.d4{left:67%;top:41%}.d5{left:19%;top:70%}.d6{left:59%;top:70%}.route{position:absolute;right:9%;bottom:25%;width:48%;border-top:4px dashed #72d8d8aa;border-radius:50%;transform:rotate(-8deg);z-index:1}.walker{position:absolute;left:7%;bottom:16%;display:flex;gap:4px;align-items:end;z-index:5;animation:to-break 17s ease-in-out infinite}.walker .figure{animation:step .42s infinite alternate}.walker span{font-size:10px;padding:4px 7px;background-color:#101b2edb;border:1px solid #38587c;border-radius:8px;white-space:nowrap}.live-board{position:absolute;left:18px;top:58px;z-index:6;max-width:340px;border:1px solid #4a7595;background:#0d192bdc;border-radius:10px;padding:8px 10px;font-size:11px;line-height:1.45;color:#dceafa}.live-board b{color:var(--green);margin-right:6px}.live-board span{color:#a8c0d7}.live-board ul{margin:6px 0 0;padding-left:16px;color:#a8c0d7}.live-board li{margin:2px 0}.note{margin-top:12px;padding:12px 14px;border:1px solid var(--edge);background:#101827;border-radius:12px;color:var(--sub);font-size:12px}.note b{color:var(--ink);margin:0 7px}.dot{display:inline-block;width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 1.8s infinite}.break{background:linear-gradient(#f5cc88 0 46%,#a56d51 46% 48%,#362831 48%)}.break .label{color:#34262c}.break .label span{color:#1e775e}.break-window{position:absolute;left:9%;top:12%;width:245px;height:160px;border:9px solid #fff0ca;background:linear-gradient(#5cd0ef,#c7f3db);font-size:55px;padding:22px 35px}.coffee{position:absolute;right:9%;bottom:19%;width:235px;height:145px;background:#84523a;border:6px solid #5c3729;border-radius:12px 12px 0 0;text-align:center;padding:18px;color:#fff2d7;z-index:2}.coffee b{display:block;font-size:11px;letter-spacing:.1em}.coffee i{display:inline-block;width:22px;height:22px;background:#fadf97;border-radius:50%;margin:11px 7px}.sofa{position:absolute;left:10%;bottom:18%;width:410px;height:175px;z-index:2}.sofa:before,.sofa:after{content:"";position:absolute;left:0;right:0;background:#326b91;border:7px solid #23506d}.sofa:before{top:25px;height:106px;border-radius:45px 45px 15px 15px}.sofa:after{bottom:25px;height:62px;border-radius:12px}.sofa .figure{position:absolute;bottom:62px;z-index:3}.sofa .figure:nth-of-type(1){left:95px}.sofa .figure:nth-of-type(3){left:240px;animation:work 2.8s infinite}.sofa small{position:absolute;bottom:0;left:0;right:0;text-align:center;color:#fff8e9;font-size:10px}.break-walker{position:absolute;right:37%;bottom:17%;z-index:4;animation:coffee-walk 14s ease-in-out infinite}.break-walker .figure{animation:step .4s infinite alternate}.break-walker small{display:block;text-align:center;color:#fff8e9;font-weight:bold}.reading{position:absolute;left:6%;bottom:8%;display:flex;gap:7px;align-items:end;z-index:2}.reading span{font-size:10px;background-color:#fff0c9;color:#34272b;padding:5px;border-radius:6px}.ceo{min-height:400px;background:linear-gradient(#2a3d58 0 47%,#94644c 47% 49%,#2f2730 49%)}.ceo-window{position:absolute;left:9%;top:14%;width:290px;height:180px;border:9px solid #d0ab80;background:linear-gradient(#75d3ec,#e9f7c6);font-size:45px;text-align:right;padding:16px 20px}.ceo-desk{position:absolute;left:50%;bottom:8%;transform:translateX(-50%);width:350px;height:220px;z-index:2}.ceo-desk .figure{position:absolute;left:138px;bottom:38px;z-index:2;animation:work 3s infinite}.ceo-desk:after{content:"";position:absolute;left:0;right:0;bottom:0;height:82px;background:linear-gradient(#b98760,#6c422f);border:7px solid #4b3028;border-radius:10px 10px 0 0;z-index:3}.approval{position:absolute;right:26px;bottom:99px;z-index:4;background:#fff1c5;color:#513923;padding:8px 12px;font-size:11px;border-radius:5px;transform:rotate(4deg)}.approval b{font-size:20px}.bubble{position:absolute;right:6%;bottom:16%;max-width:280px;padding:13px;background:#0b1528e8;border:1px solid #4b6991;border-radius:13px;font-size:12px;line-height:1.6;z-index:5}.chat{margin-top:14px;background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px}.chat h2{font-size:15px;margin:0 0 5px}.chat>p{margin:0;color:var(--sub);font-size:11px}.log{height:118px;margin:12px 0;padding:10px;overflow:auto;background:#0b1120;border:1px solid #253651;border-radius:10px;font-size:12px}.log p{padding:7px 9px;margin:0 0 8px;width:fit-content;max-width:87%;border-radius:8px;line-height:1.45}.boss{background:#17263d}.you{background:#29436c;margin-left:auto!important}.chat-form{display:flex;gap:8px}.chat-form input{min-width:0;flex:1;padding:10px;background:#0b1120;color:#fff;border:1px solid #385072;border-radius:9px}.chat-form button{background:#147fac;border:0;font-weight:700;cursor:pointer}@keyframes work{0%,100%{transform:scale(var(--s,1))}50%{transform:scale(var(--s,1)) translateY(-4px)}}@keyframes step{0%{transform:scale(var(--s,1))}to{transform:scale(var(--s,1)) translateY(-5px) rotate(2deg)}}@keyframes to-break{0%,25%{left:7%;bottom:16%}45%,62%{left:78%;bottom:30%}79%,100%{left:7%;bottom:16%}}@keyframes coffee-walk{0%,25%{right:37%;bottom:17%}44%,63%{right:11%;bottom:22%}80%,100%{right:37%;bottom:17%}}@keyframes pulse{50%{opacity:.3}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}}@media(max-width:760px){body{padding:12px}.head{align-items:flex-start;flex-direction:column}.scene{min-height:720px}.desk{transform:scale(.72);transform-origin:top left}.d1{left:3%;top:38%}.d2{left:37%;top:38%}.d3{left:3%;top:64%}.d4{left:37%;top:64%}.d5,.d6{display:none}.break-window{transform:scale(.7);transform-origin:top left}.coffee{transform:scale(.7);transform-origin:bottom right}.sofa{transform:scale(.7);transform-origin:bottom left}.ceo-window{transform:scale(.7);transform-origin:top left}.bubble{bottom:8%;right:3%;max-width:210px}.ceo-desk{transform:translateX(-50%) scale(.8);transform-origin:bottom center}}
</style>
"""


# MISSION 082: 本格運用向けに、上部ナビゲーションを「主メニュー」4画面+
# 「スペース」(開閉できる補助メニュー)3画面へ整理した。既存URLはすべて
# 変更していない。日常的に使う4画面を先頭に並べ、オフィス・社長室・
# 休憩室は<details>/<summary>(ネイティブの開閉部品)でまとめることで、
# 追加のJSなしでもキーボード操作(Enter/Space)・スクリーンリーダー双方で
# 「スペース」という補助メニューであることと開閉状態が伝わるようにする。
NAV_MAIN_TABS = [
    ("aioffice", "/ai-office", "AIオフィス"),
    ("command", "/command-center", "運用司令室"),
    ("content", "/content-studio", "投稿企画工場"),
    ("revenue", "/revenue", "収益化ボード"),
]
NAV_SPACE_TABS = [
    ("office", "/office", "オフィス"),
    ("ceo", "/office/ceo-office", "社長室"),
    ("break", "/office/break-room", "休憩室"),
]


def _page(room, title, lead, scene, role_hint=None):
  main_nav = "".join(
      f'<a class="{"active" if key == room else ""}" href="{href}" '
      f'aria-current="{"page" if key == room else "false"}">{name}</a>'
      for key, href, name in NAV_MAIN_TABS
  )
  space_nav = "".join(
      f'<a class="{"active" if key == room else ""}" href="{href}" '
      f'aria-current="{"page" if key == room else "false"}">{name}</a>'
      for key, href, name in NAV_SPACE_TABS
  )
  space_keys = {key for key, _href, _name in NAV_SPACE_TABS}
  space_open = " open" if room in space_keys else ""
  role_hint_html = f'<p class="role-hint">{role_hint}</p>' if role_hint else ""
  return render_template_string(
      f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" '
      f'content="width=device-width,initial-scale=1"><title>{title} | AI Hive</title>{STYLE}{LIVE_DATA_STYLE}{DEPTH_STYLE}'
      f'</head><body><header class="head"><div><h1>{title}</h1>{role_hint_html}<p>{lead}</p></div>'
      f'<a href="/">← ダッシュボードへ戻る</a></header>'
      f'<nav class="tabs" aria-label="主要な画面">{main_nav}'
      f'<details class="tabs-space"{space_open}>'
      '<summary>スペース</summary>'
      f'<div class="tabs-space-menu">{space_nav}</div>'
      '</details>'
      f'</nav><main>{scene}</main></body></html>'
  )


# MISSION 029: ローカル収益化ボード。
#
# ここに書く内容は、すべて「社内の企画たたき台」であり、外部への送信・
# 公開や、自動的な実行は一切行わない(表示専用の静的コンテンツ)。将来、
# 検討する事業を差し替える場合は、このデータ構造(REVENUE_FOCUS)の値を
# 書き換えるだけでよく、以下のHTML生成コード自体には手を入れなくてよい
# ように分離している。
REVENUE_FOCUS = {
    "business_name": "AI・ガジェット発信からの楽天ROOM収益化",
    "purpose": "AI初心者・仕事効率化・デスク周り・スマホPC周辺機器に関心がある人へ向けて、"
               "投稿企画工場のテーマを軸に発信し、楽天ROOMでの手動紹介につなげる土台を作る",
    "target_customer": "AI初心者、仕事の効率化に関心がある人、デスク周りを整えたい人、"
                        "スマホ・PC周辺機器を探している人",
    "service_ideas": [
        "投稿企画工場のテーマに沿った発信",
        "公開済みPinterest投稿（5件）・AI Hive関連のnote記事（3本）からの流入育成"
        "（noteアカウントには、この他にも既存記事があります）",
        "楽天ROOMでの手動カテゴリ紹介（AI Hiveで追加した商品投稿17件。"
        "アカウント全体では商品投稿30件）",
    ],
    # MISSION 052: Pinterest・note・楽天ROOMの投稿活動自体は手動ですでに
    # 進行しているため、「すべて未定・検討中」という当初の見出しから、
    # 「金額・成果」(収益そのもの)がまだ未定であることに絞った見出しへ
    # 整理した。各行の値も「検討中」(まだ着手していない)から、実際の
    # 公開・運用状況を示す表現へ更新したが、具体的な金額・成果予測は
    # 一切追加していない。
    # MISSION 055: 「note 3件」だけの表示だとnoteアカウント全体の記事数の
    # ように誤解されるため、「AI Hive関連」であることを明記した。既存記事の
    # 総数・売上・フォロワー数は未確認のため表示・推測しない。
    # MISSION 057: 楽天ROOMは、折りたたみキーボード(1件)に加えて9月13日に
    # 過去購入・使用商品5件、9月14日にショルダー型ガジェットポーチ1件を
    # 投稿し、合計7件となった。売上・クリック数・成果報酬・売れた実績は
    # 未確認のため、件数のみを更新し、反応・売上は引き続き表示しない。
    # MISSION 058: 楽天ROOMアカウント全体の商品数は30件であり、AI Hiveで
    # 追加・記録しているのはそのうち7件だけである。「ROOM投稿7件」とだけ
    # 表示するとアカウント全体の商品数のように誤解されるため、「AI Hiveで
    # 追加した」ことを明記し、アカウント全体の商品数(30件)にも控えめに
    # 触れた。30件という数値は水増ししていない確認済みの事実であり、
    # 売上・クリック数・成果報酬・購入実績は未確認のため表示しない。
    # MISSION 059: 9月16日に10件を追加投稿し、AI Hiveで追加した投稿は
    # 合計17件になった。アカウント全体の商品数(30件)は変更せず、引き続き
    # 区別して表示する。
    "price_note": "楽天ROOMでの紹介はすべて手動登録の想定であり、金額・成果はすべて未確定の"
                  "「たたき台」です。確定した収益・契約内容ではありません。",
    "price_tiers": [
        ("Pinterest経由の流入", "5件公開・手動運用中"),
        ("楽天ROOMでの手動紹介", "AI Hive分17件公開・手動運用中"),
        ("noteでの信頼構築", "AI Hive関連3本公開・手動運用中"),
    ],
    "pipeline_stages": ["テーマ選定", "投稿確認", "ROOM準備", "手動登録"],
    "weekly_priorities": [
        "48時間後を目安にPinterestの反応を確認",
        "noteの反応確認",
        "既存ROOM投稿（AI Hive分17件）の内容・反応を確認",
    ],
}


def _render_revenue_metric_entry_section():
  """収益化ボードの「今日の実績を記録する」入口(MISSION 091)。

  最初に媒体を選ぶと、その媒体に必要な入力欄だけを表示する(他媒体の
  欄は<div hidden>のまま)。数値欄と保存ボタンを中心に置き、注意書き・
  メモ欄は<details>で折りたたむ。保存はこのMac上のアプリ内DB
  (/api/dashboard/metrics)への同一オリジンJSON POSTのみで、外部サービス
  への投稿・送信・ログイン・自動取得・ブラウザ自動操作は一切行わない。
  数値が分からない指標は空欄のまま保存でき、1つも入力が無い場合は保存
  せず画面内に案内を表示する。
  """
  media_options = "".join(
      f'<option value="{m}">{m}</option>' for m in dashboard_db.REVENUE_METRIC_MEDIA_ORDER
  )

  def _field_input(media, field):
    key = field["key"]
    label = field["label"]
    input_id = f"rm-metric-{media}-{key}"
    if key == "posted":
      return (
          f'<div><label for="{input_id}">{label}</label>'
          f'<select id="{input_id}" class="revenue-metric-input" '
          f'data-metric="{key}" data-no-diff="1">'
          '<option value="">未選択</option>'
          '<option value="1">あり</option>'
          '<option value="0">なし</option>'
          '</select></div>'
      )
    placeholder = "（任意）" if key == "reactions" else "実際に確認できた数字だけを入力"
    return (
        f'<div><label for="{input_id}">{label}</label>'
        f'<input type="number" step="any" id="{input_id}" '
        f'class="revenue-metric-input" data-metric="{key}" '
        f'placeholder="{placeholder}"></div>'
    )

  field_groups = "".join(
      f'<div class="revenue-metric-fieldgroup" data-media="{media}" hidden>'
      '<div class="cc-decision-fields">'
      + "".join(_field_input(media, f) for f in dashboard_db.REVENUE_METRIC_FIELDS[media])
      + '</div></div>'
      for media in dashboard_db.REVENUE_METRIC_MEDIA_ORDER
  )

  return (
      '<section class="revenue-metric-entry cc-decision-box" '
      'id="revenue-metric-entry" aria-label="今日の実績を記録する">'
      '<h2 class="cc-section-title">今日の実績を記録する</h2>'
      '<div class="cc-decision-fields">'
      '<div><label for="rm-date">日付</label>'
      '<input type="date" id="rm-date"></div>'
      '<div><label for="rm-media">媒体</label>'
      f'<select id="rm-media"><option value="">選択してください</option>'
      f'{media_options}</select></div>'
      '</div>'
      f'<div id="revenue-metric-fieldgroups">{field_groups}</div>'
      '<p class="cc-decision-note" id="rm-fieldgroup-hint">媒体を選ぶと、'
      'その媒体に必要な入力欄が表示されます。</p>'
      '<details class="cc-work-ledger-detail">'
      '<summary>注意書き・メモ（任意）</summary>'
      '<p class="cc-decision-note">数字が分からない指標は空欄のままで'
      '保存できます。利用者が実際に確認できた数字だけを入力してください。'
      'このアプリが外部サービスから自動で数字を取得することはありません。'
      '</p>'
      '<div class="cc-decision-fields">'
      '<div><label for="rm-note">メモ（任意）</label>'
      '<input type="text" id="rm-note" maxlength="200" '
      'placeholder="確認した画面名など"></div>'
      '</div>'
      '</details>'
      '<button type="button" class="cc-decision-add-btn" id="rm-save-btn">'
      '今日の実績を保存する</button>'
      '<p class="cc-decision-note" id="rm-save-result" aria-live="polite">'
      '</p>'
      '<script>(function(){'
      f'var MEDIA_FIELDS={json.dumps(dashboard_db.REVENUE_METRIC_FIELDS, ensure_ascii=False)};'
      'function todayDateStr(){'
      'var d=new Date();'
      'function pad(n){return n<10?"0"+n:""+n;}'
      'return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());'
      '}'
      'var dateEl=document.querySelector("#rm-date");'
      'if(dateEl&&!dateEl.value)dateEl.value=todayDateStr();'
      'var mediaEl=document.querySelector("#rm-media");'
      'var noteEl=document.querySelector("#rm-note");'
      'var saveBtn=document.querySelector("#rm-save-btn");'
      'var resultEl=document.querySelector("#rm-save-result");'
      'var hintEl=document.querySelector("#rm-fieldgroup-hint");'
      'var groups=document.querySelectorAll(".revenue-metric-fieldgroup");'
      'function showGroupFor(media){'
      'groups.forEach(function(g){g.hidden=(g.dataset.media!==media);});'
      'if(hintEl)hintEl.hidden=Boolean(media);'
      '}'
      'if(mediaEl){'
      'mediaEl.addEventListener("change",function(){'
      'showGroupFor(mediaEl.value);'
      'resultEl.textContent="";'
      '});'
      '}'
      'function collectValues(media){'
      'var values={};'
      'var group=document.querySelector('
      '\'.revenue-metric-fieldgroup[data-media="\'+media+\'"]\');'
      'if(!group)return values;'
      'group.querySelectorAll(".revenue-metric-input").forEach(function(el){'
      'var v=el.value;'
      'if(v===null||v==="")return;'
      'values[el.dataset.metric]=v;'
      '});'
      'return values;'
      '}'
      'if(saveBtn){'
      'saveBtn.addEventListener("click",function(){'
      'var date=dateEl?dateEl.value:"";'
      'var media=mediaEl?mediaEl.value:"";'
      'if(!date||!media){'
      'resultEl.textContent="日付と媒体を選択してください。";'
      'return;'
      '}'
      'var values=collectValues(media);'
      'if(Object.keys(values).length===0){'
      'resultEl.textContent='
      '"数値を1つ以上入力してください（分からない項目は空欄のままで'
      'かまいません）。";'
      'return;'
      '}'
      'saveBtn.disabled=true;'
      'resultEl.textContent="保存しています…";'
      'window.fetch("/api/dashboard/metrics",{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify({'
      'date:date,media:media,values:values,'
      'note:noteEl?noteEl.value:""'
      '})'
      '}).then(function(res){return res.json();}).then(function(data){'
      'saveBtn.disabled=false;'
      'if(data&&data.saved){'
      'var labels=(MEDIA_FIELDS[media]||[]).filter(function(f){'
      'return data.savedMetrics.indexOf(f.key)!==-1;'
      '}).map(function(f){return f.label;});'
      'resultEl.textContent=date+"の"+media+"の「"+labels.join("・")+'
      '"」を記録しました。";'
      '}else{'
      'resultEl.textContent='
      '"数値を1つ以上入力してください（分からない項目は空欄のままで'
      'かまいません）。";'
      '}'
      '}).catch(function(){'
      'saveBtn.disabled=false;'
      'resultEl.textContent='
      '"保存できませんでした。しばらくしてからもう一度お試しください。";'
      '});'
      '});'
      '}'
      '})();</script>'
      '</section>'
  )


def _render_revenue_metric_summary_section():
  """収益化ボードの「媒体ごとの実績記録」(MISSION 091)。

  保存済みのDB実績(/api/dashboard/metrics/summary)だけを使い、最新の記録・
  前回記録との差分・直近の履歴を表示する。初回記録や比較対象が無い指標は
  「比較できる記録はまだありません」と正直に表示し、増減を捏造しない。
  1件も記録の無い媒体は「未記録」と表示する(ゼロ実績として扱わない)。
  """
  cards = "".join(
      f'<div class="revenue-metric-summary-card" data-media="{media}">'
      f'<h3>{media}</h3>'
      '<p class="revenue-metric-summary-body">確認中…</p>'
      '</div>'
      for media in dashboard_db.REVENUE_METRIC_MEDIA_ORDER
  )
  return (
      '<section class="revenue-metric-summary cc-decision-box" '
      'id="revenue-metric-summary" aria-label="媒体ごとの実績記録">'
      '<h2 class="cc-section-title">媒体ごとの実績記録</h2>'
      '<p class="cc-decision-note">ここに表示するのは、上の「今日の実績を'
      '記録する」またはこのMac上のアプリ内データ（SQLite）に保存済みの'
      '数値だけです。デモの売上・クリック・反応・グラフは表示しません。'
      '記録の無い媒体は「未記録」と表示し、0件として扱いません。</p>'
      f'<div class="revenue-metric-summary-grid" id="revenue-metric-summary-grid">'
      f'{cards}</div>'
      '<script>(function(){'
      f'var MEDIA_FIELDS={json.dumps(dashboard_db.REVENUE_METRIC_FIELDS, ensure_ascii=False)};'
      'function escapeHtml(s){'
      'return String(s==null?"":s)'
      '.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");'
      '}'
      'function formatNumber(n){'
      'if(typeof n!=="number")return String(n);'
      'return Number.isInteger(n)?String(n):String(Math.round(n*100)/100);'
      '}'
      'function formatValue(metric,value){'
      'if(metric==="posted")return value===1?"あり":"なし";'
      'return formatNumber(value);'
      '}'
      'function formatDiff(metric,diff){'
      'if(metric==="posted")return "";'
      'if(diff==null)return "比較できる記録はまだありません";'
      'var sign=diff>0?"+":"";'
      'return "前回との差分："+sign+formatNumber(diff);'
      '}'
      'function renderCard(media,summary){'
      'var card=document.querySelector('
      '\'.revenue-metric-summary-card[data-media="\'+media+\'"]\');'
      'if(!card)return;'
      'var body=card.querySelector(".revenue-metric-summary-body");'
      'if(!body)return;'
      'var fields=MEDIA_FIELDS[media]||[];'
      'var hasAny=fields.some(function(f){'
      'return summary&&summary[f.key]&&summary[f.key].latest;'
      '});'
      'if(!hasAny){'
      'body.textContent="未記録";'
      'return;'
      '}'
      'var html="<ul class=\\"revenue-metric-summary-list\\">";'
      'fields.forEach(function(f){'
      'var m=summary[f.key]||{};'
      'if(!m.latest){'
      'html+="<li><b>"+escapeHtml(f.label)+"：</b>未記録</li>";'
      'return;'
      '}'
      'var valueText=formatValue(f.key,m.latest.value);'
      'var diffText=formatDiff(f.key,m.diff);'
      'html+="<li><b>"+escapeHtml(f.label)+"：</b>"+escapeHtml(valueText)+'
      '"（"+escapeHtml(m.latest.date)+"記録）"+'
      '(diffText?"　"+escapeHtml(diffText):"")+"</li>";'
      '});'
      'html+="</ul>";'
      'var historyEntries=[];'
      'fields.forEach(function(f){'
      'var m=summary[f.key]||{};'
      '(m.history||[]).forEach(function(h){'
      'historyEntries.push({date:h.date,label:f.label,'
      'value:formatValue(f.key,h.value)});'
      '});'
      '});'
      'historyEntries.sort(function(a,b){'
      'if(a.date===b.date)return 0;'
      'return a.date<b.date?1:-1;'
      '});'
      'if(historyEntries.length){'
      'html+="<details class=\\"cc-work-ledger-detail\\">"+'
      '"<summary>直近の履歴</summary><ul class=\\"revenue-metric-history\\">";'
      'historyEntries.slice(0,10).forEach(function(h){'
      'html+="<li>"+escapeHtml(h.date)+"　"+escapeHtml(h.label)+"："+'
      'escapeHtml(h.value)+"</li>";'
      '});'
      'html+="</ul></details>";'
      '}'
      'body.innerHTML=html;'
      '}'
      'function loadSummary(){'
      'if(typeof window.fetch!=="function")return;'
      'window.fetch("/api/dashboard/metrics/summary")'
      '.then(function(res){return res.json();})'
      '.then(function(data){'
      'var summary=(data&&data.summary)||{};'
      'Object.keys(summary).forEach(function(media){'
      'renderCard(media,summary[media]);'
      '});'
      '}).catch(function(){});'
      '}'
      'loadSummary();'
      '})();</script>'
      '</section>'
  )


def _render_revenue_scene(focus):
  """収益化ボードのカード群を、REVENUE_FOCUSのデータから組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・外部通信への
  アクセスは一切行わない。
  """
  service_items = "".join(f"<li>{item}</li>" for item in focus["service_ideas"])
  price_items = "".join(
      f"<li><span>{label}</span><b>{value}</b></li>"
      for label, value in focus["price_tiers"]
  )
  pipeline_items = "".join(f"<li>{stage}</li>" for stage in focus["pipeline_stages"])
  priority_items = "".join(
      f"<li>{item}</li>" for item in focus["weekly_priorities"]
  )
  return (
      '<section class="revenue-board" aria-label="収益化ボード">'
      '<div class="revenue-notice">'
      '<b>社内の企画たたき台です（参考表示）。</b>'
      'ここに表示する事業の目的・お客さま像・収益の柱などの説明は検討中の'
      '案（参考表示）であり、外部への送信・公開、自動的な実行は一切行われ'
      'ません。数値の実績は、下の「今日の実績を記録する」から保存した、'
      'このMac上のアプリ内データ（SQLite）の記録だけを表示します。'
      '</div>'
      + _render_revenue_metric_entry_section()
      + _render_revenue_metric_summary_section() +
      '<div class="revenue-card revenue-focus">'
      '<span class="revenue-tag">第一優先事業</span>'
      f'<h2>{focus["business_name"]}</h2>'
      '</div>'
      '<div class="revenue-grid">'
      '<div class="revenue-card"><h3>事業の目的</h3>'
      f'<p>{focus["purpose"]}</p></div>'
      '<div class="revenue-card"><h3>想定するお客さま像</h3>'
      f'<p>{focus["target_customer"]}</p></div>'
      '<div class="revenue-card"><h3>収益化の柱（案）</h3>'
      f'<ul>{service_items}</ul></div>'
      '<div class="revenue-card"><h3>収益の入り口候補（金額・成果はすべて未確定）</h3>'
      f'<p class="revenue-price-note">{focus["price_note"]}</p>'
      f'<ul class="revenue-price-tiers">{price_items}</ul></div>'
      '<div class="revenue-card"><h3>ROOM登録までの段階</h3>'
      f'<ol class="revenue-pipeline">{pipeline_items}</ol></div>'
      '<div class="revenue-card"><h3>今週の優先行動</h3>'
      f'<ol class="revenue-priorities">{priority_items}</ol></div>'
      '</div>'
      + _render_room_prep_section(
          ROOM_PREP_CATEGORIES, ROOM_PREP_STATUS_LABELS, ROOM_PUBLISHED_POSTS,
          ROOM_ACCOUNT_TOTAL_NOTE,
      ) +
      '<p class="revenue-footnote">この画面はlocalhost限定で表示される'
      '社内検討用の資料です。送信・公開・自動実行は行われません。</p>'
      '</section>'
  )


# MISSION 040: 投稿企画工場を、現在実際に使っているPinterest・note・
# 楽天ROOM運用だけに整理し直したもの。
#
# 旧バージョン(MISSION 030/031)では、実際には使っていないInstagram・
# Threads案、未確認の商品ジャンル候補チップ、5案の改善・採点ワークフロー
# を表示していたが、実態と合わなくなったため全面的に削除した。ここに
# 書く内容は「社内向けの下書き」であり、投稿・公開・送信の実行は一切
# 行わない(表示専用の静的コンテンツ)。将来テーマ・切り口を差し替える
# 場合は、このデータ構造(CONTENT_STUDIO_PLANS)を編集するだけでよい。
CONTENT_STUDIO_THEME = "AIとガジェットで、仕事と暮らしを少しラクにする"

# 楽天ROOMリンクの扱いに関する、画面共通の方針文言。
CONTENT_STUDIO_ROOM_LINK_POLICY = (
    "楽天ROOMの商品投稿ページを、柴犬社長が手動で確認できた場合のみ、"
    "Pinterestへリンクを追加します。確認できていない間はリンクを追加しません。"
)

# MISSION 046: 今後作成するnote記事・Pinterest投稿案の文章品質をそろえる
# ための作成基準。表示専用の静的な参照情報であり、この基準に沿って過去の
# 記事・投稿キューの内容をさかのぼって書き換えるものではない。将来基準を
# 差し替える場合は、このデータ構造(CONTENT_STUDIO_WRITING_STANDARDS)を
# 編集するだけでよい。
CONTENT_STUDIO_WRITING_STANDARDS_HEADING = (
    "文章の作成基準（読者が続きを読みたくなる、人間味のある文章）"
)
CONTENT_STUDIO_WRITING_STANDARDS_INTRO = (
    "今後作成するnote記事・Pinterest投稿案は、次の基準を満たすように作成します。"
    "公開済みのnote記事・既存のPinterest投稿・投稿キューの内容をさかのぼって"
    "書き換えるものではありません。"
)
CONTENT_STUDIO_WRITING_STANDARDS = [
    "タイトルは、読者が抱えそうな困りごと・場面・気づきが伝わる表現にする",
    "「必ず」「絶対」「これだけで成功」など、過剰なクリック誘導や断定は使わない",
    "note記事本文は日本語で4,500〜5,500文字程度を目安にする",
    "冒頭は解説から始めず、読者が想像できる具体的な場面・困りごと・問いかけから始める",
    "実体験がないことを、本人の経験として書かない",
    "説明書のような箇条書きだけにせず、自然な会話調と具体例を交える",
    "読者が次の段落を読みたくなる流れを意識する",
    "Pinterestのタイトルは画像内の文字と矛盾させない",
]

# MISSION 047: 今後作成するPinterest投稿画像・note見出し画像の作りをそろえる
# ための作成基準。テーマが一目で伝わり、同じような「おしゃれな机」の画像が
# 連続しないようにするための参照情報。表示専用の静的コンテンツであり、この
# 基準に沿って過去の記事・投稿キューの既存画像を差し替えるものではない。
# 将来基準を差し替える場合は、このデータ構造(CONTENT_STUDIO_IMAGE_STANDARDS)
# を編集するだけでよい。
CONTENT_STUDIO_IMAGE_STANDARDS_HEADING = (
    "画像の作成基準（テーマが一目で伝わり、同じ構図が続かない画像）"
)
CONTENT_STUDIO_IMAGE_STANDARDS_INTRO = (
    "今後作成するPinterest投稿画像・note見出し画像は、次の基準を満たすように作成します。"
    "公開済みのnote記事・既存のPinterest投稿・投稿キューの既存画像をさかのぼって"
    "作り直すものではありません。"
)
CONTENT_STUDIO_IMAGE_STANDARDS = [
    "画像は装飾を増やすことより、最初に目が行く主役を1つ決める",
    "テーマごとに主役を変える（スマホ記事：スマートフォンを主役にする／AIの使い方記事："
    "考える・入力する・見直す場面が伝わる構図にする／デスク記事：机全体ではなく、"
    "困りごとや改善点が伝わる部分を主役にする）",
    "同じ夜の木目デスク・同じ構図を連続使用しない",
    "Pinterest用画像は、テーマが一目で分かるタイトルを画像本体に焼き込む",
    "note用見出し画像は、タイトルを重ねず、写真だけでも記事テーマが感じられる構図にする",
    "ロゴ、読める商品名、実在サービス画面、楽天市場の商品画像は入れない",
    "商品紹介でない画像に商品タグを付けない",
    "画像内の文字はスマホでも読みやすい大きさにする",
    "画像は縦横比・用途・altテキストを先に決めてから作る",
]

# MISSION 048: 既存のPinterest投稿4本(メール下書き・デスク配線・周辺機器
# 選び・スマホでのAI下書き)とnote記事2本(AI初心者の最初の3つの使い方・
# スマホでのAI下書き)の内容を踏まえ、次に作る「AI初心者向け」記事・投稿の
# 候補を3つ整理した企画メモ。表示専用の静的コンテンツであり、記事・画像・
# 投稿はまだ作成していない(検討段階)。将来候補を差し替える場合は、この
# データ構造(CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES)を編集するだけでよい。
# MISSION 054: 候補2「AIとの会話がかみ合わないときに見直す3つ」は、
# 2026年9月12日までにPinterest投稿「AIが「なんか違う」ときに見直す3つ」と
# note記事「AIに聞いても「なんか違う」と感じる人へ」として実際に公開済みに
# なったため、企画メモから削除した(公開済み記事を改めて「次に作る候補」
# として提案するのは実態と食い違うため)。残る候補を2つに整理した。
CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_HEADING = (
    "次のnote記事・Pinterest投稿の候補（AI初心者向け・企画メモ）"
)
CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_INTRO = (
    "公開済みのPinterest投稿5件・AI Hive関連のnote記事3件の内容を踏まえ、次に作る候補を"
    "2つ整理した企画メモです。ここに書いた内容は下書き作成前の検討段階であり、記事・"
    "画像・投稿はまだ作成していません。メール下書き・スマホでのAI下書き・デスク配線・"
    "一般的なAIの使い方（メール・要約・壁打ち）・AIとの会話がかみ合わないときの見直しとは"
    "重複しないテーマだけを選んでいます。"
)
CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES = [
    {
        "theme": "候補1：AIに調べ物を頼む前に確認する3つ",
        "pain_point": (
            "分からないことをAIに聞いて出てきた答えを、そのまま信じてよいのか、どう"
            "扱えばよいのか分からず不安に感じている。"
        ),
        "note_title_candidates": [
            "AIに調べ物を頼むとき、答えを鵜呑みにしないために確認する3つ",
            "AIの答えをどこまで信じていいか分からない人へ、調べ物を頼む前の3つの習慣",
            "AIに聞いた答えが本当か不安なときに見直したい3つのポイント",
        ],
        "pinterest_title": "AIに調べ物を頼む前に確認する3つ",
        "opening_hook": (
            "仕事の合間に、ちょっとした疑問をAIに聞いてみたら、思っていたよりずっと"
            "自然な答えが返ってきた——そんな経験はないでしょうか。ただ、その答えを見"
            "ながら「これ、本当に合っているのかな」と、少し不安になったことはありませ"
            "んか。AIの返事はいつも自信ありげに見えるため、間違っていても気づきにくい"
            "ことがあります。周りに聞ける人がいない場面ほど、その答えをそのまま信じて"
            "しまいがちです。この記事では、AIに調べ物を頼む前に、あらかじめ決めておく"
            "と答えとの付き合い方が変わる3つのポイントを紹介します。"
        ),
        "heading_outline": [
            "はじめに（AIの答えをそのまま信じそうになった経験）",
            "1. 聞く前に「答え合わせができるか」を考える",
            "2. 断定口調でも、根拠がある内容かどうかを見分ける",
            "3. 重要な判断には、必ず別の情報源で確認する",
            "まとめ",
        ],
        "image_subject_and_composition": (
            "画像の作成基準の「AIの使い方記事」に沿い、答えを見直す場面を主役にする。"
            "スマホやタブレットの画面を覗き込みながら、手元のノートやメモと照らし合わ"
            "せている様子を中心に置き、デスク全体は写さない。"
        ),
        "pinterest_vs_note_image_difference": (
            "Pinterest用画像には、タイトル「AIに調べ物を頼む前に確認する3つ」と3項目"
            "を画像本体に焼き込む。note用見出し画像は文字を重ねず、確認している空気感"
            "が写真だけで伝わる構図にする。"
        ),
        "reason": (
            "メール下書き・スマホでのAI下書き・デスク配線・一般的なAIの使い方（メール・"
            "要約・壁打ち）のいずれとも異なり、AIの回答をどう受け止めるかという、AI"
            "初心者が早い段階でつまずきやすい「情報の扱い方」に焦点を当てているため。"
        ),
    },
    {
        "theme": "候補2：AIに1日の優先順位を整理してもらう前の3つ",
        "pain_point": (
            "在宅ワークでやることが多く優先順位がつけられず、AIに整理を手伝ってもら"
            "いたいが、何をどう伝えればよいか分からない。"
        ),
        "note_title_candidates": [
            "在宅ワーク中、AIに1日の優先順位を整理してもらう前に決めておきたい3つ",
            "やることが多すぎる日に、AIと一緒に優先順位を整理する3つのコツ",
            "AIに「今日何からやるか」を相談する前に準備したい3つ",
        ],
        "pinterest_title": "AIに1日の優先順位を整理してもらう前の3つ",
        "opening_hook": (
            "在宅ワークをしていると、やらなければいけないことが次々に頭に浮かび、結局"
            "どれから手をつけていいか分からなくなる——そんな日はないでしょうか。そんな"
            "とき、AIに1日のタスクを相談してみるという方法があります。ただし、思いつく"
            "ままに伝えてしまうと、AIも整理しきれず、かえって頭の中がごちゃついたまま"
            "になることがあります。整理してもらった結果を見て、逆に迷ってしまうことも"
            "あるかもしれません。この記事では、AIに優先順位の整理を頼む前に、決めて"
            "おきたい3つのポイントを紹介します。"
        ),
        "heading_outline": [
            "はじめに（やることが多すぎて優先順位がつけられない日）",
            "1. その日の「絶対に外せない予定」を先に洗い出す",
            "2. タスクを頼む前に、ざっくりでも締め切りを添える",
            "3. 整理してもらった順番を、そのまま鵜呑みにせず自分の体調と照らし合わせる",
            "まとめ",
        ],
        "image_subject_and_composition": (
            "「デスク記事」ではなく「AIの使い方記事」に近い性格のため、考える・入力"
            "する場面を主役にする。ノートに書き出したタスクリストと、スマホやタブレッ"
            "トの画面を見比べている手元を中心に置く。既存のデスク配線投稿とは異なる"
            "構図・時間帯（例えば日中の明るい光）にして、同じ夜の木目デスクの連続使用"
            "を避ける。"
        ),
        "pinterest_vs_note_image_difference": (
            "Pinterest用画像には、タイトルと3項目を画像本体に焼き込む。note用見出し"
            "画像は文字を重ねず、タスク整理をしている空気感が伝わる写真のみにする。"
        ),
        "reason": (
            "既存のPinterest投稿5件・AI Hive関連のnote記事3件はいずれも「AIに文章の"
            "下書きを頼む」「AIとの会話を見直す」といった場面が中心だが、この候補は"
            "「AIにタスク・優先順位の整理を頼む」という、文章作成・対話の見直し以外の使い方を扱って"
            "おり、テーマが重複しない。在宅ワーカーという想定読者にも刺さりやすい。"
        ),
    },
]
CONTENT_STUDIO_NEXT_ARTICLE_RECOMMENDATION = (
    "候補1「AIに調べ物を頼む前に確認する3つ」をおすすめします。仕事・在宅ワークに限らず"
    "誰にでも当てはまる場面であり、既存投稿と同じ「頼む前に確認する3つ」という型を"
    "踏襲できるため、読者にとって見慣れた形で試しやすいこと、AIの回答をどう受け止める"
    "かという、初心者が早い段階で感じやすい不安に応えられることが理由です。候補2も"
    "重複のない有力なテーマのため、続けて検討する価値があります。"
)

# 現在公開済みのnote記事(note初回記事)に合う2テーマだけを残した。他の
# テーマ(デスク周り・スマホPC周辺機器・買う前に確認したいガジェット選び)
# は、現在の運用(Pinterest・note・楽天ROOM)に対応する準備がまだできて
# いないため、この画面には表示しない。
CONTENT_STUDIO_PLANS = [
    {
        "title": "AI初心者が最初に試す便利な使い方",
        "pinterest_angle": (
            "タイトル案:「AI初心者向け・最初にやること3選」／説明文案: 迷いがちな"
            "最初の一歩を3つに絞って紹介する保存用ピン。"
        ),
        "note_angle": (
            "見出し案:「AIを何となく怖いと思っている人が、最初の一歩を踏み出すための"
            "3つのステップ」"
        ),
        "room_link_handling": "今回はなし",
    },
    {
        "title": "仕事の文章作成・要約をラクにするAI活用",
        "pinterest_angle": (
            "タイトル案:「文章作成が苦手な人のためのAI活用メモ」／説明文案: 要約・"
            "下書き・整文の3場面での使い分けを紹介する保存用ピン。"
        ),
        "note_angle": "見出し案:「文章が苦手でも大丈夫。AIと役割分担して仕事を進める考え方」",
        "room_link_handling": "今回はなし",
    },
]


def _render_content_studio_scene(
    theme, plans, room_link_policy,
    writing_standards_heading, writing_standards_intro, writing_standards,
    image_standards_heading, image_standards_intro, image_standards,
    next_candidates_heading, next_candidates_intro, next_candidates,
    next_candidates_recommendation,
):
  """投稿企画工場のカード群を、CONTENT_STUDIO_PLANSのデータから組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・外部通信への
  アクセスは一切行わない。Pinterest・noteの2媒体だけを扱い、各テーマに
  つき「Pinterest用の切り口」「note用の切り口」「楽天ROOMリンクの扱い」
  の3項目だけを簡潔に示す。

  MISSION 046: writing_standards_heading/writing_standards_intro/
  writing_standards(リスト)は、今後の下書き作成基準を表示するための
  参照情報。公開済みのnote記事・既存のPinterest投稿・投稿キューの内容を
  書き換えるものではない。

  MISSION 047: image_standards_heading/image_standards_intro/
  image_standards(リスト)は、今後の画像作成基準を表示するための参照情報。
  同様に、既存の画像を書き換えるものではない。

  MISSION 048: next_candidates_heading/next_candidates_intro/
  next_candidates(候補の辞書のリスト)/next_candidates_recommendation は、
  次に作るnote記事・Pinterest投稿の候補3つを示す企画メモ。記事・画像・
  投稿はまだ作成しておらず、既存のnote記事・Pinterest投稿・投稿キューを
  書き換えるものではない。
  """
  plan_cards = "".join(
      '<div class="cs-plan-card">'
      f'<h3>{plan["title"]}</h3>'
      '<dl class="cs-plan-fields">'
      '<dt>Pinterest用の切り口</dt>'
      f'<dd>{plan["pinterest_angle"]}</dd>'
      '<dt>note用の切り口</dt>'
      f'<dd>{plan["note_angle"]}</dd>'
      '<dt>楽天ROOMリンクの扱い</dt>'
      f'<dd>{plan["room_link_handling"]}</dd>'
      '</dl>'
      '</div>'
      for plan in plans
  )
  # MISSION 046: 今後の下書き作成基準を、既存の楽天ROOMリンク方針と同じ
  # 見せ方(見出し+一覧)で追加する。チェックボックス操作の対象ではない静的な
  # 参照情報のため、既存のfp-checklistのカードスタイルだけを再利用し、
  # 入力欄は含めない。
  writing_standard_items = "".join(f'<li>{item}</li>' for item in writing_standards)
  writing_standards_html = (
      f'<h3 class="fp-section-title">{writing_standards_heading}</h3>'
      f'<p class="cs-theme">{writing_standards_intro}</p>'
      f'<ul class="fp-checklist">{writing_standard_items}</ul>'
  )
  # MISSION 047: 画像の作成基準を、文章の作成基準と同じ見せ方(見出し+一覧)で
  # 追加する。同じくfp-checklistのカードスタイルだけを再利用する。
  image_standard_items = "".join(f'<li>{item}</li>' for item in image_standards)
  image_standards_html = (
      f'<h3 class="fp-section-title">{image_standards_heading}</h3>'
      f'<p class="cs-theme">{image_standards_intro}</p>'
      f'<ul class="fp-checklist">{image_standard_items}</ul>'
  )
  # MISSION 048: 次に作る記事・投稿の候補3つを、既存のplan_cardsと同じ
  # cs-plan-cardのカードスタイルで表示する。候補ごとに項目数が多いため、
  # note記事タイトル案・見出し構成はカード内の<dd>に<ul>/<ol>で並べる
  # (新規CSSは追加せず、ブラウザ標準のリスト表示にまかせる)。
  candidate_cards = "".join(
      '<div class="cs-plan-card">'
      f'<h3>{c["theme"]}</h3>'
      '<dl class="cs-plan-fields">'
      '<dt>読者の困りごと</dt>'
      f'<dd>{c["pain_point"]}</dd>'
      '<dt>note記事タイトル案（3つ）</dt>'
      '<dd><ul>' + "".join(f'<li>{t}</li>' for t in c["note_title_candidates"]) + '</ul></dd>'
      '<dt>Pinterest用タイトル案</dt>'
      f'<dd>{c["pinterest_title"]}</dd>'
      '<dt>記事冒頭のつかみ案</dt>'
      f'<dd>{c["opening_hook"]}</dd>'
      '<dt>5,000字記事にする場合の見出し構成</dt>'
      '<dd><ol>' + "".join(f'<li>{h}</li>' for h in c["heading_outline"]) + '</ol></dd>'
      '<dt>画像の主役と構図案</dt>'
      f'<dd>{c["image_subject_and_composition"]}</dd>'
      '<dt>Pinterest用画像とnote用見出し画像の違い</dt>'
      f'<dd>{c["pinterest_vs_note_image_difference"]}</dd>'
      '<dt>今回このテーマを候補にする理由</dt>'
      f'<dd>{c["reason"]}</dd>'
      '</dl>'
      '</div>'
      for c in next_candidates
  )
  next_candidates_html = (
      f'<h3 class="fp-section-title">{next_candidates_heading}</h3>'
      f'<p class="cs-theme">{next_candidates_intro}</p>'
      + candidate_cards +
      f'<div class="cs-room-policy"><b>次に作るなら。</b>{next_candidates_recommendation}</div>'
  )
  # MISSION 086: 初見でも迷わないよう、最上部に「今日の一歩」カード
  # (今日やること+進めるボタンだけ)を置き、既存の詳しい候補フォーム・
  # 注意事項はすべて削除せず<details>(詳細設定・注意事項)に折りたたむ。
  # MISSION 089: 表示内容はJS側で、このMac上のアプリ内DB(/api/dashboard/
  # candidates、読み取り専用GET)を参照して決める。「今日」に設定した
  # 楽天ROOM候補(未完了)があればその先頭1件を大きく表示し、無ければ
  # 「保留の候補を1件選んで今日に入れる」と案内する。候補が1件も無い
  # (DBが空の)初回状態では、従来どおり候補作成を案内する。
  today_step_card = (
      '<div class="cs-today-step" id="cs-today-step">'
      '<div class="cs-today-step-label">今日の一歩</div>'
      '<p class="cs-today-step-task" id="cs-today-step-task">読み込み中…</p>'
      '<a class="cs-today-step-button" id="cs-today-step-button" '
      'href="/content-studio/room-daily-candidates">候補を作成する</a>'
      '</div>'
  )
  today_step_script = (
      '<script>(function(){'
      'var taskEl=document.querySelector("#cs-today-step-task");'
      'var btnEl=document.querySelector("#cs-today-step-button");'
      'function setStep(task,label,href){'
      'if(taskEl)taskEl.textContent=task;'
      'if(btnEl){btnEl.textContent=label;btnEl.href=href;}'
      '}'
      'function showNoCandidate(){'
      'setStep("楽天ROOMの投稿候補を1件作る","候補を作成する",'
      '"/content-studio/room-daily-candidates");'
      '}'
      'if(typeof window.fetch!=="function"){showNoCandidate();return;}'
      'window.fetch("/api/dashboard/candidates").then(function(res){'
      'return res.json();'
      '}).then(function(data){'
      'var list=(data&&Array.isArray(data.candidates))?data.candidates:[];'
      'var active=list.filter(function(c){'
      'return c.media==="楽天ROOM"&&!c.manual_posted;'
      '});'
      'var todayList=active.filter(function(c){return c.bucket==="today";});'
      'if(todayList.length>0){'
      'var c=todayList[0];'
      'var name=c.product_name||c.genre||"候補";'
      'setStep(name+"を確認し、手動で投稿する","候補を確認する",'
      '"/content-studio/room-daily-candidates?date="+'
      'encodeURIComponent(c.target_date||""));'
      'return;'
      '}'
      'if(active.length>0){'
      'setStep("保留の候補を1件選んで今日に入れる","候補を確認する",'
      '"/content-studio/room-daily-candidates");'
      'return;'
      '}'
      'showNoCandidate();'
      '}).catch(showNoCandidate);'
      '})();</script>'
  )
  return (
      '<section class="content-studio" aria-label="投稿企画工場">'
      + today_step_card +
      '<details class="cs-details">'
      '<summary>詳細設定・注意事項</summary>'
      '<div class="cs-details-body">'
      '<div class="revenue-notice">'
      '<b>この画面は投稿企画の手動準備用です。</b>'
      'この画面は投稿企画の手動準備用であり、外部サービスへの投稿・送信・連携は'
      '行わない。'
      '</div>'
      f'<p class="cs-theme">対象テーマ：<b>{theme}</b></p>'
      f'<div class="cs-room-policy"><b>楽天ROOMリンクについて。</b>{room_link_policy}</div>'
      + writing_standards_html
      + image_standards_html +
      '<a class="cs-first-post-link" href="/content-studio/first-post">'
      '→ 初回手動投稿パッケージを見る（Pinterest向け）</a> '
      '<a class="cs-first-post-link" href="/content-studio/weekly-plan">'
      '→ 7日間コンテンツ計画を見る</a> '
      '<a class="cs-first-post-link" href="/content-studio/desk-setup-post">'
      '→ デスク環境投稿パッケージを見る（楽天ROOM向け）</a> '
      '<a class="cs-first-post-link" href="/content-studio/publish-queue">'
      '→ 投稿キューを見る（社長承認待ち）</a> '
      '<a class="cs-first-post-link" href="/content-studio/note-first-article">'
      '→ note初回記事を見る</a> '
      '<a class="cs-first-post-link" href="/content-studio/note-daily-candidates">'
      '→ note記事候補（毎日2本の下書き）を見る</a> '
      '<a class="cs-first-post-link" href="/revenue#room-prep">'
      '→ 楽天ROOM投稿準備を見る</a>'
      + plan_cards
      + next_candidates_html +
      '<p class="cs-footnote">この画面はlocalhost限定で表示される社内検討用の'
      '資料です。SNS投稿・note投稿・広告出稿・営業送信は行われません。</p>'
      '</div>'
      '</details>'
      + today_step_script +
      '</section>'
  )


# MISSION 032: 初回手動投稿パッケージ(Pinterest向け・ローカル専用)。
#
# ここに書く内容も、これまでの投稿企画工場と同様「社内向けの下書き」で
# あり、SNSへの投稿・送信・連携は一切行わない(表示専用の静的コンテンツ、
# 画像もローカルの画面内SVGのみで外部画像は使わない)。楽天アフィリエイト
# リンクはまだ付けず、「今回の商品紹介はなし」であることを明記する。
# 将来テーマ・文面・SVGの中身を差し替える場合は、このデータ構造
# (FIRST_POST_PACKAGE)を編集するだけでよい。
FIRST_POST_PACKAGE = {
    "theme": "AI初心者が仕事で最初に試す3つの使い方",
    "pin": {
        "title": "仕事がラクになる、AIの使い方3選（AI初心者向け）",
        "description": (
            "メールの下書き・長い文章の要約・アイデア出しの壁打ち。AIを初めて使う人が、"
            "今日から試せる3つの使い方をまとめました。特定の商品の紹介はありません。"
        ),
        "alt_text": (
            "仕事がラクになるAIの使い方3選のイラスト。1. メールの下書きを1文で頼む "
            "2. 長い文章を要約してもらう 3. アイデア出しの壁打ち相手にする。"
            "AI初心者向けの使い方紹介画像で、特定の商品は写っていません。"
        ),
        "svg_headline": ["仕事がラクになる", "AIの使い方 3選"],
        "svg_subtitle": "AI初心者向け",
        "svg_items": [
            {"number": "1", "lines": ["メールの下書きを", "1文で頼む"], "icon": "mail"},
            {"number": "2", "lines": ["長い文章を", "要約してもらう"], "icon": "summary"},
            {"number": "3", "lines": ["アイデア出しの", "壁打ち相手にする"], "icon": "idea"},
        ],
        "svg_footer": "毎日の仕事に、AIをひとつまみ。",
    },
    "checklist": [
        "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
        "商品名・価格・ランキング・実績などの未確認情報が含まれていないか確認した",
        "画像内の文字が読みやすいか（誤字・はみ出しがないか）確認した",
        "altテキストが画像の内容を正しく説明しているか確認した",
        "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
    ],
    "no_product_note": "今回の商品紹介はなし（楽天アフィリエイトリンクは未設定です）。",
    "manual_post_note": (
        "この投稿は、柴犬社長がPinterestで手動投稿してください。投稿後、実際のURLや"
        "反応（保存数・クリック数など）を確認したうえで、次にどこまで自動化するかを"
        "判断します。現時点では自動投稿・自動連携は行いません。"
    ),
}

# SVGアイコン(装飾のみ・画面内完結・外部素材なし)。
_FIRST_POST_ICONS = {
    "mail": (
        '<rect x="-26" y="-18" width="52" height="36" rx="6" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<path d="M-26 -14 L0 4 L26 -14" fill="none" stroke="#38bdf8" stroke-width="3" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "summary": (
        '<rect x="-24" y="-26" width="48" height="52" rx="6" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<line x1="-14" y1="-12" x2="14" y2="-12" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="-14" y1="0" x2="14" y2="0" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="-14" y1="12" x2="6" y2="12" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
    ),
    "idea": (
        '<circle cx="0" cy="-6" r="22" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<line x1="-8" y1="20" x2="8" y2="20" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="-5" y1="27" x2="5" y2="27" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
    ),
}


def _render_first_post_pin_svg(pin):
  """Pinterest用の縦長2:3(1000x1500)ローカルSVG画像を組み立てる。

  外部画像・外部フォント・外部素材は一切使わず、すべて画面内SVGの図形と
  テキストだけで構成する。商品名・価格・実績・ランキング・断定的な
  成果表現は一切含めない。
  """
  headline_lines = "".join(
      f'<tspan x="500" dy="{0 if i == 0 else 70}">{line}</tspan>'
      for i, line in enumerate(pin["svg_headline"])
  )
  item_blocks = []
  card_height = 280
  gap = 36
  start_y = 430
  for index, item in enumerate(pin["svg_items"]):
    card_y = start_y + index * (card_height + gap)
    icon_shape = _FIRST_POST_ICONS[item["icon"]]
    label_lines = "".join(
        f'<tspan x="220" dy="{0 if i == 0 else 46}">{line}</tspan>'
        for i, line in enumerate(item["lines"])
    )
    item_blocks.append(
        f'<g transform="translate(0,{card_y})">'
        '<rect x="60" y="0" width="880" height="' + str(card_height) + '" rx="28" '
        'fill="#101a30" stroke="#293958" stroke-width="2"/>'
        '<circle cx="150" cy="' + str(card_height // 2) + '" r="46" fill="#0b2540" '
        'stroke="#38bdf8" stroke-width="3"/>'
        '<text x="150" y="' + str(card_height // 2 + 16) + '" text-anchor="middle" '
        f'font-size="44" font-weight="700" fill="#38bdf8">{item["number"]}</text>'
        f'<g transform="translate(80,{card_height // 2})">{icon_shape}</g>'
        f'<text x="220" y="{card_height // 2 - 20}" font-size="40" font-weight="700" '
        f'fill="#f1f5f9">{label_lines}</text>'
        '</g>'
    )
  return (
      '<svg viewBox="0 0 1000 1500" xmlns="http://www.w3.org/2000/svg" '
      'role="img" aria-labelledby="pin-svg-title pin-svg-desc">'
      f'<title id="pin-svg-title">{pin["title"]}</title>'
      f'<desc id="pin-svg-desc">{pin["alt_text"]}</desc>'
      '<defs><linearGradient id="pinBg" x1="0" y1="0" x2="0" y2="1">'
      '<stop offset="0%" stop-color="#0b1220"/><stop offset="100%" stop-color="#1b2c4a"/>'
      '</linearGradient></defs>'
      '<rect width="1000" height="1500" fill="url(#pinBg)"/>'
      '<text x="500" y="160" text-anchor="middle" font-size="64" font-weight="800" '
      f'fill="#f1f5f9">{headline_lines}</text>'
      '<text x="500" y="330" text-anchor="middle" font-size="30" font-weight="600" '
      f'fill="#38bdf8">{pin["svg_subtitle"]}</text>'
      + "".join(item_blocks) +
      '<text x="500" y="1440" text-anchor="middle" font-size="26" fill="#a3b2c6">'
      f'{pin["svg_footer"]}</text>'
      '</svg>'
  )


# MISSION 032.1: Pinterest用PNG(1000x1500・2:3)。
#
# 画面内SVGプレビュー(_render_first_post_pin_svg)と同じ
# FIRST_POST_PACKAGE["pin"]のデータから生成するため、内容・見た目は常に
# 一致する。このPNGはあらかじめ生成してstatic/images/へ書き出した静的
# ファイルであり、Flaskアプリの起動・リクエスト処理では画像生成を一切
# 行わない(通常の静的ファイル配信のみ)。生成コード自体は将来テーマや
# 文言を差し替えた際に再生成できるよう残しているが、Pillow(PIL)を遅延
# importしているため、office_views.py自体のimportや通常のアプリ起動には
# Pillowのインストールを必要としない。
FIRST_POST_PNG_RELATIVE_PATH = "images/first-post-pin-2x3.png"
_FIRST_POST_PNG_FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def _draw_first_post_icon(draw, cx, cy, kind, color):
  """PNG版アイコン(装飾のみ)を描画する。SVG版と同じ3種類の図形。"""
  if kind == "mail":
    draw.rectangle([cx - 26, cy - 18, cx + 26, cy + 18], outline=color, width=3)
    draw.line(
        [(cx - 26, cy - 14), (cx, cy + 4), (cx + 26, cy - 14)],
        fill=color, width=3, joint="curve",
    )
  elif kind == "summary":
    draw.rectangle([cx - 24, cy - 26, cx + 24, cy + 26], outline=color, width=3)
    draw.line([(cx - 14, cy - 12), (cx + 14, cy - 12)], fill=color, width=3)
    draw.line([(cx - 14, cy), (cx + 14, cy)], fill=color, width=3)
    draw.line([(cx - 14, cy + 12), (cx + 6, cy + 12)], fill=color, width=3)
  elif kind == "idea":
    draw.ellipse([cx - 22, cy - 28, cx + 22, cy + 16], outline=color, width=3)
    draw.line([(cx - 8, cy + 34), (cx + 8, cy + 34)], fill=color, width=3)
    draw.line([(cx - 5, cy + 41), (cx + 5, cy + 41)], fill=color, width=3)


def generate_first_post_pin_png(pin, out_path=None):
  """Pinterest用PNG(1000x1500)を生成し、ファイルへ保存する(開発時専用)。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。テーマや
  文言(FIRST_POST_PACKAGE)を差し替えた場合、この関数を手動で再実行して
  PNGを作り直すこと。実行にはPillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; \\
          o.generate_first_post_pin_png(o.FIRST_POST_PACKAGE['pin'])"
  """
  from PIL import Image, ImageDraw, ImageFont  # 遅延import(開発時専用)

  width, height = 1000, 1500
  bg_top, bg_bottom = (11, 18, 32), (27, 44, 74)
  white, blue, sub = (241, 245, 249), (56, 189, 248), (163, 178, 198)
  card_bg, card_edge, badge_bg = (16, 26, 48), (41, 57, 88), (11, 37, 64)

  img = Image.new("RGB", (width, height), bg_top)
  draw = ImageDraw.Draw(img)
  for y in range(height):
    t = y / (height - 1)
    draw.line(
        [(0, y), (width, y)],
        fill=tuple(int(bg_top[i] + (bg_bottom[i] - bg_top[i]) * t) for i in range(3)),
    )

  headline_font = ImageFont.truetype(_FIRST_POST_PNG_FONT_PATH, 62)
  subtitle_font = ImageFont.truetype(_FIRST_POST_PNG_FONT_PATH, 30)
  number_font = ImageFont.truetype(_FIRST_POST_PNG_FONT_PATH, 42)
  label_font = ImageFont.truetype(_FIRST_POST_PNG_FONT_PATH, 38)
  footer_font = ImageFont.truetype(_FIRST_POST_PNG_FONT_PATH, 26)

  cx = width // 2
  y = 110
  for line in pin["svg_headline"]:
    draw.text((cx, y), line, font=headline_font, fill=white, anchor="ma")
    y += 76
  draw.text((cx, y + 20), pin["svg_subtitle"], font=subtitle_font, fill=blue, anchor="ma")

  card_h, gap, start_y = 280, 36, 430
  for index, item in enumerate(pin["svg_items"]):
    card_y = start_y + index * (card_h + gap)
    draw.rounded_rectangle(
        [60, card_y, 940, card_y + card_h], radius=28,
        fill=card_bg, outline=card_edge, width=2,
    )
    badge_cy = card_y + card_h // 2
    draw.ellipse(
        [150 - 46, badge_cy - 46, 150 + 46, badge_cy + 46],
        fill=badge_bg, outline=blue, width=3,
    )
    draw.text((150, badge_cy), item["number"], font=number_font, fill=blue, anchor="mm")
    _draw_first_post_icon(draw, 260, badge_cy, item["icon"], blue)
    ly = badge_cy - 26
    for line in item["lines"]:
      draw.text((320, ly), line, font=label_font, fill=white, anchor="lm")
      ly += 46

  draw.text((cx, 1440), pin["svg_footer"], font=footer_font, fill=sub, anchor="mm")

  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static", FIRST_POST_PNG_RELATIVE_PATH
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def _render_first_post_scene(package):
  """初回手動投稿パッケージ(Pinterest向け)のHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・外部通信への
  アクセスは一切行わない。コピー用ボタンはクライアント側JSのみで完結し、
  クリップボード操作が失敗しても例外を伝播させず、安全なフォールバック
  表示にする(register_office_views側のスクリプトで実装)。
  """
  pin = package["pin"]
  svg_markup = _render_first_post_pin_svg(pin)
  checklist_items = "".join(
      f'<li><input type="checkbox" id="fp-check-{i}"><label for="fp-check-{i}">{item}</label></li>'
      for i, item in enumerate(package["checklist"])
  )
  return (
      '<section class="first-post-board" aria-label="初回手動投稿パッケージ">'
      '<div class="fp-notice"><b>社内向けの投稿パッケージです。</b>'
      'SNSへの投稿・送信・連携は一切行われません。柴犬社長が内容を確認し、'
      '手動でPinterestへ投稿するための準備画面です。</div>'
      f'<p class="fp-theme">対象テーマ：<b>{package["theme"]}</b></p>'
      f'<div class="fp-note fp-note-warn"><b>商品紹介について。</b>{package["no_product_note"]}</div>'
      f'<div class="fp-note fp-note-warn"><b>手動投稿について。</b>{package["manual_post_note"]}</div>'
      '<h3 class="fp-section-title">Pinterest投稿素材</h3>'
      '<div class="fp-pin-layout">'
      f'<div><div class="fp-svg-wrap">{svg_markup}</div>'
      '<p class="fp-svg-ratio">縦長 2:3（画面内SVG・外部画像なし）</p>'
      # MISSION 032.1: 通常のダウンロードリンク(<a href download>)のみで
      # 保存する。外部通信・JavaScript必須の処理は行わない。あらかじめ
      # 生成済みのローカルPNGファイル(static/配下)を指すだけであり、
      # クリックしてもSNSへの投稿・送信・連携は一切発生しない。
      f'<a class="fp-png-download" href="/static/{FIRST_POST_PNG_RELATIVE_PATH}" '
      'download="pinterest-first-post.png">Pinterest用PNGを保存</a>'
      '<p class="fp-png-hint">保存したPNGをPinterestで手動アップロードしてください。'
      'このボタンからの投稿・送信・連携は行われません。</p></div>'
      '<div class="fp-fields">'
      '<div class="fp-field"><div class="fp-field-head"><h4>タイトル</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="fp-title">コピー</button></div>'
      f'<p id="fp-title">{pin["title"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>説明文</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="fp-description">コピー</button></div>'
      f'<p id="fp-description">{pin["description"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>altテキスト</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="fp-alt">コピー</button></div>'
      f'<p id="fp-alt">{pin["alt_text"]}</p></div>'
      '</div>'
      '</div>'
      '<h3 class="fp-section-title">投稿前チェックリスト</h3>'
      f'<ul class="fp-checklist">{checklist_items}</ul>'
      # MISSION 032: コピー操作はクライアント側JSのみで完結し、外部通信
      # は行わない。navigator.clipboardが使えない/失敗する環境でも、
      # 例外を投げずに安全な文言へフォールバックする。
      '<script>document.querySelectorAll(".fp-copy-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'const el=document.getElementById(btn.dataset.copyTarget);'
      'if(!el)return;'
      'const original=btn.textContent;'
      'const showResult=ok=>{btn.textContent=ok?"コピーしました":"コピーできませんでした";'
      'setTimeout(()=>{btn.textContent=original;},1800);};'
      'try{'
      'if(navigator.clipboard&&navigator.clipboard.writeText){'
      'navigator.clipboard.writeText(el.textContent).then(()=>showResult(true))'
      '.catch(()=>showResult(false));'
      '}else{showResult(false);}'
      '}catch(e){showResult(false);}'
      '});'
      '});</script>'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の資料です。'
      'Pinterest・楽天ROOM・noteへの投稿・送信・連携は行われません。</p>'
      '</section>'
  )


# MISSION 033: 7日間コンテンツ計画(ローカル専用・確認用の見取り図)。
#
# 新しい投稿企画を考案するのではなく、既存の投稿企画(CONTENT_STUDIO_TOPICS
# ・FIRST_POST_PACKAGE)だけを使って、7日分の「テーマ・想定媒体・目的・
# 状態・投稿前に確認すること」を並べた見取り図。予約投稿・自動投稿の
# スケジュールではなく、あくまで下書き・計画段階の一覧であることを
# 明記する。1日目のみ、初回Pinterest投稿(FIRST_POST_PACKAGE)を
# 「公開済み」として記録するが、反応数・成果は一切表示・推測しない。
# 将来、日ごとの割り当てを差し替える場合は、このデータ構造
# (WEEKLY_PLAN)を編集するだけでよい。
#
# MISSION 050: 現在の実際の運用状況に合わせて整理し直した。2日目
# (note初回記事)は実際にはすでに柴犬社長が手動で公開済みのため、
# status を draft から published へ更新した。6日目・7日目は、MISSION 040
# で投稿企画工場の表示から外れた未実施の汎用ガジェットテーマ(「デスク
# 周りを整える便利ガジェット」「スマホ・PC作業を快適にする周辺機器」)を
# 参照したまま古くなっていたため、投稿キューのデスク配線・周辺機器選びの
# 2テーマへ差し替えた。3〜5日目は、投稿企画工場(CONTENT_STUDIO_PLANS)に
# いまも残っている未着手の候補テーマのままで変わっていないため、手動投稿
# 候補のまま維持している。
#
# MISSION 054修正: 6日目・7日目が参照する投稿キューのデスク配線・周辺機器
# 選びテーマは、実際には柴犬社長がまだPinterestへ投稿していない
# ("awaiting_president")ことが判明したため、statusをpublishedから
# manual_candidateへ戻した(投稿キュー側の公開状況と食い違わないように
# するため)。
WEEKLY_PLAN_POST_PUBLISH_CHECKS = [
    "表示回数（インプレッション）をPinterest上で手動確認する",
    "保存数をPinterest上で手動確認する",
    "クリック数をPinterest上で手動確認する",
]

WEEKLY_PLAN = [
    {
        "day": 1,
        "theme": "AI初心者が仕事で最初に試す3つの使い方",
        "medium": "Pinterest",
        "purpose": "保存・検索からの流入（初回投稿）",
        "status": "published",
        "note": (
            "初回手動投稿パッケージ（/content-studio/first-post）の内容を、"
            "柴犬社長が手動でPinterestへ投稿済みとして記録しています。"
            "表示回数・保存数・クリック数などの反応・成果は、この画面では"
            "一切表示・推測しません。"
        ),
    },
    {
        "day": 2,
        "theme": "AI初心者が仕事で最初に試す3つの使い方",
        "medium": "note",
        "purpose": "初回投稿の内容を、もう少し詳しく解説する",
        "status": "published",
        "note": (
            "note初回記事（/content-studio/note-first-article）の内容を、"
            "柴犬社長が手動でnoteへ貼り付けて公開済みとして記録しています。"
            "閲覧数・スキ数などの反応・成果は、この画面では一切表示・推測しません。"
        ),
    },
    {
        "day": 3,
        "theme": "AI初心者が最初に試す便利な使い方",
        "medium": "Pinterest",
        "purpose": "保存・検索からの流入",
        "status": "manual_candidate",
        "checks": ["誰向けかが明確か", "誇大表現・断定的な言い回しがないか"],
    },
    {
        "day": 4,
        "theme": "AI初心者が最初に試す便利な使い方",
        "medium": "note",
        "purpose": "深く読んでもらい信頼を積み上げる",
        "status": "manual_candidate",
        "checks": ["見出しが内容を正しく表しているか", "誇大表現がないか"],
    },
    {
        "day": 5,
        "theme": "仕事の文章作成・要約をラクにするAI活用",
        "medium": "Pinterest",
        "purpose": "保存・検索からの流入",
        "status": "manual_candidate",
        "checks": ["タイトルが検索されやすいか", "altテキストが正しいか"],
    },
    {
        # MISSION 054修正: 投稿キューのデスク配線テーマ(desk-wiring-3points)は
        # 実際には未公開("awaiting_president")のため、published表現をやめ、
        # 他の手動投稿候補日と同じ"manual_candidate"に戻した。
        "day": 6,
        "theme": "デスクが狭いときに配線を見直す3つのポイント",
        "medium": "Pinterest",
        "purpose": "保存・検索からの流入",
        "status": "manual_candidate",
        "checks": ["誰向けかが明確か", "誇大表現・断定的な言い回しがないか"],
    },
    {
        # MISSION 054修正: 投稿キューの周辺機器選びテーマ(peripheral-choice-
        # 3points)は実際には未公開("awaiting_president")のため、published
        # 表現をやめ、他の手動投稿候補日と同じ"manual_candidate"に戻した。
        "day": 7,
        "theme": "スマホ・PC作業をラクにする周辺機器の選び方",
        "medium": "Pinterest",
        "purpose": "保存・検索からの流入",
        "status": "manual_candidate",
        "checks": ["タイトルが検索されやすいか", "altテキストが正しいか"],
    },
]

WEEKLY_PLAN_STATUS_LABELS = {
    # MISSION 050: 公開済みの投稿が1日目(初回投稿)以外にも複数あるため、
    # 「（初回投稿）」の限定を外し、汎用の「公開済み」ラベルへ整理した。
    "published": "公開済み",
    "draft": "下書き",
    "review": "確認待ち",
    "manual_candidate": "手動投稿候補",
}


def _render_weekly_plan_scene(plan, status_labels, publish_checks):
  """7日間コンテンツ計画のHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・外部通信への
  アクセスは一切行わない。予約投稿・自動投稿は行っておらず、2日目以降は
  すべて下書き・計画段階であることを明記する。
  """
  day_cards = []
  for entry in plan:
    status_key = entry["status"]
    status_label = status_labels[status_key]
    is_published = status_key == "published"
    card_class = "wp-day-card is-published" if is_published else "wp-day-card"
    meta = (
        f'<div class="wp-day-meta">'
        f'<span>想定媒体：<b>{entry["medium"]}</b></span>'
        f'<span>目的：<b>{entry["purpose"]}</b></span>'
        '</div>'
    )
    if is_published:
      body = f'<p class="wp-day-note">{entry["note"]}</p>'
    else:
      checks_html = "".join(f'<li>{item}</li>' for item in entry["checks"])
      body = (
          '<p class="wp-day-note">投稿・公開・送信は行われていません（下書き・計画段階です）。</p>'
          f'<ul class="wp-day-checks">{checks_html}</ul>'
      )
    day_cards.append(
        f'<div class="{card_class}">'
        '<div class="wp-day-head">'
        f'<h3>{entry["day"]}日目：{entry["theme"]}</h3>'
        f'<span class="wp-day-status status-{status_key}">{status_label}</span>'
        '</div>'
        f'{meta}{body}'
        '</div>'
    )

  publish_checks_html = "".join(f'<li>{item}</li>' for item in publish_checks)

  return (
      '<section class="weekly-plan-board" aria-label="7日間コンテンツ計画">'
      '<div class="wp-notice"><b>社内向けの確認用計画です。</b>'
      'ここに表示する7日分の内容は、実際に柴犬社長が手動で公開済みの投稿・'
      '記事の記録と、まだ下書き・候補段階の内容が混在した計画表です。'
      'この画面から予約投稿・自動投稿は一切行われません。既存の投稿企画'
      '（投稿企画工場・投稿キュー・note記事下書き）だけを使って構成して'
      'います。</div>'
      '<div class="wp-callout"><b>公開後24時間で確認すること（1日目・初回投稿）</b>'
      f'<ul>{publish_checks_html}</ul></div>'
      '<a class="cs-first-post-link" href="/revenue#room-prep">'
      '→ 楽天ROOM投稿準備を見る</a>'
      + "".join(day_cards) +
      # MISSION 050: 「実績を見てから2日目以降の自動化を判断する」という
      # 当初の見通しから、実際の運用が固まった(Pinterest・楽天ROOM・noteは
      # 引き続き手動、Threadsのみ別管理のDify自動投稿)ため、その内容へ
      # 更新した。投稿キュー・note記事の最新の全件リストは、それぞれの
      # 画面で確認できる旨を明記する。
      '<p class="wp-footnote">Pinterest・楽天ROOM・noteは、柴犬社長による手動運用を'
      '継続しています。Threadsのみ、Difyを使った別管理の自動投稿を運用していますが、'
      'この画面（このダッシュボード）からの自動投稿・予約投稿・広告出稿・営業送信は'
      '一切行われません。最新の投稿状況は、投稿キュー（/content-studio/publish-queue）'
      'とnote記事（/content-studio/note-first-article）でご確認ください。'
      'この画面はlocalhost限定で表示される社内検討用の資料です。</p>'
      '</section>'
  )


# MISSION 034: 楽天ROOM投稿準備(ローカル専用・確認用の下ごしらえ)。
#
# 実在の商品名・価格・ランキング・在庫・成果予測は一切表示しない。
# CONTENT_STUDIO_TOPICSに既に登録済みの商品ジャンル候補
# (product_genre_ideas)だけを再利用した「カテゴリ候補」を並べる
# ことで、新しい商品リサーチを行わずに準備状況を見渡せるようにする。
# 「見送り」ステータスのテーマ(CONTENT_STUDIO_TOPICS[4])は対象に含めない。
# 楽天ROOMへの登録・Pinterestへの公開は、いずれも社長の確認・承認を
# 経てから手動で行う運用である旨を画面内に明記し、自動投稿・予約投稿・
# API連携・スクレイピング・商品情報取得は一切実装しない。将来カテゴリを
# 差し替える場合は、このデータ構造(ROOM_PREP_CATEGORIES)を編集する
# だけでよい。
ROOM_PREP_STATUS_LABELS = {
    "planning": "企画中",
    "awaiting_president": "社長確認待ち",
    "manual_registration": "手動でROOM登録",
}

ROOM_PREP_CATEGORIES = [
    {
        "audience_problem": "AIを使ったことがなく、何から始めればいいか分からない人向け",
        "pinterest_theme_idea": "AI初心者向け・最初にやること3選（初回手動投稿パッケージと同じテーマ）",
        "genre_ideas": ["AIアシスタント対応スマートスピーカー", "音声入力対応キーボード"],
        "room_manual_checks": [
            "ROOM内で該当カテゴリのアイテムが見つかるか手動で確認する",
            "掲載できる画像がROOM上に用意されているか確認する（画像の保存・加工はしない）",
        ],
        "pre_write_checks": [
            "実際に試用していない前提で、断定的な効果を書いていないか",
            "誇大表現・未確認の実績を書いていないか",
            "商品提供・クーポン・広告主とのやり取りがある場合、PR表記が必要か確認したか",
        ],
        "status": "awaiting_president",
    },
    {
        "audience_problem": "日々の文章作成・要約に時間がかかっている人向け",
        "pinterest_theme_idea": "文章作成が苦手な人のためのAI活用メモ",
        "genre_ideas": ["音声文字起こしデバイス", "ノートPC用外付けマイク"],
        "room_manual_checks": [
            "ROOM内で該当カテゴリのアイテムが見つかるか手動で確認する",
            "掲載できる画像がROOM上に用意されているか確認する（画像の保存・加工はしない）",
        ],
        "pre_write_checks": [
            "実際に試用していない前提で、断定的な効果を書いていないか",
            "誇大表現・未確認の実績を書いていないか",
            "商品提供・クーポン・広告主とのやり取りがある場合、PR表記が必要か確認したか",
        ],
        "status": "planning",
    },
]

# MISSION 052: 「デスク周り」テーマ（旧カテゴリ3）はMISSION 040で投稿企画工場の
# 対象から外れ、「スマホ・PC周辺機器ジャンルまとめ」（旧カテゴリ4）も未確認の
# 商品候補の列挙にとどまり実際の運用と合わなくなったため、両カテゴリは削除した。
# 代わりに、実際に手動投稿済みの折りたたみキーボード投稿を事実のみで示す
# ROOM_PUBLISHED_POSTS を新設する。ここには金額・在庫・ランキング・未確認の
# レビューは一切含めない。
# MISSION 057: 9月13日に過去購入・使用商品5件、9月14日にショルダー型
# ガジェットポーチ1件を追加投稿し、AI Hiveで追加した投稿は合計7件になった。
# いずれも#オリジナル写真を使用しない通常投稿であり、AI生成の使用イメージは
# 実物写真ではないため、オリジナル写真実績としては数えない。売上・クリック数・
# 成果報酬・商品が売れた実績は未確認のため、件数以外は表示しない
# (next_stepは、現在の優先事項を示す最新の1件にだけ設定する)。
# MISSION 058: 楽天ROOMアカウント全体の商品数は30件で、そのうちAI Hiveで
# 追加・記録しているのは7件だけである。「ROOM投稿7件」とだけ表示すると
# アカウント全体の商品数のように誤解されるため、「AI Hiveで追加した」旨を
# 明記し、アカウント全体の商品数(30件)にも控えめに触れる。30件という数値は
# 社長から確認できた事実であり、この画面以外では推測・水増ししない。
# MISSION 059: 9月16日に10件を追加投稿し、AI Hiveで追加した投稿は合計17件
# になった。アカウント全体の商品数(30件)は変更せず、引き続き区別して表示
# する。売上・クリック数・成果報酬・購入実績は未確認のため表示しない。
ROOM_ACCOUNT_TOTAL_NOTE = (
    "楽天ROOMアカウント全体では商品投稿が30件あり、このうちAI Hiveで"
    "追加・記録しているのは17件です。"
)

ROOM_PUBLISHED_POSTS = [
    {
        "item_label": "折りたたみキーボード",
        "status_text": "楽天ROOMへ手動投稿済み（1件）",
    },
    {
        "item_label": "過去に購入・使用した商品",
        "status_text": "9月13日に楽天ROOMへ手動投稿済み（5件、#オリジナル写真を使用しない通常投稿）",
    },
    {
        "item_label": "ショルダー型ガジェットポーチ",
        "status_text": (
            "9月14日に楽天ROOMへ手動投稿済み（1件、公開情報・購入者レビューを参考に"
            "した通常投稿。#オリジナル写真は使用していません）"
        ),
    },
    {
        "item_label": "追加投稿分",
        "status_text": "9月16日に楽天ROOMへ手動投稿済み（10件）",
        "next_step": (
            "商品候補をさらに増やす前に、このAI Hive分17件の内容と反応を手動で確認する"
            "段階です。売上・クリック数・成果報酬・商品が売れた実績は未確認のため"
            "表示していません。"
        ),
    },
]


def _render_room_prep_section(
    categories, status_labels, published_posts=None, account_total_note=None
):
  """楽天ROOM投稿準備のカード群を、ROOM_PREP_CATEGORIESのデータから組み立てる。

  published_posts（ROOM_PUBLISHED_POSTS）が渡された場合は、既に手動投稿
  済みの事実のみを先頭に表示する。金額・在庫・ランキング・未確認の
  レビューは一切表示しない。

  MISSION 058: account_total_note（ROOM_ACCOUNT_TOTAL_NOTE）が渡された
  場合は、「AI Hiveで追加した件数」と「アカウント全体の商品数」を混同
  しないよう、公開済み一覧の直後に一度だけ表示する。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・楽天API・
  外部通信へのアクセスは一切行わない。楽天市場の商品画像は保存・加工・
  表示せず、使用する画像は既存のローカル素材のみである。
  """
  published_posts = published_posts or []
  # MISSION 057: 複数件を投稿済みになったため、next_stepは現在の優先事項を
  # 示す最新の投稿にだけ設定する運用にした(過去の投稿に古い「次のステップ」
  # 文言を重複表示しないため)。next_stepが無い投稿はステータスのみ表示する。
  published_items = "".join(
      '<li class="room-published-item">'
      f'<b>{post["item_label"]}</b>：{post["status_text"]}'
      + (
          f'<br><span class="room-published-next">次のステップ：{post["next_step"]}</span>'
          if "next_step" in post else ""
      )
      + '</li>'
      for post in published_posts
  )
  account_total_html = (
      f'<p class="room-prep-account-note">{account_total_note}</p>'
      if account_total_note else ""
  )
  published_block = (
      '<div class="room-prep-published">'
      '<h3>公開済みの楽天ROOM投稿（AI Hiveで追加した17件）</h3>'
      f'<ul>{published_items}</ul>'
      f'{account_total_html}'
      '</div>'
  ) if published_posts else ""
  category_cards = []
  for category in categories:
    status_key = category["status"]
    status_label = status_labels[status_key]
    genre_items = "".join(f"<li>{genre}</li>" for genre in category["genre_ideas"])
    room_check_items = "".join(
        f"<li>{item}</li>" for item in category["room_manual_checks"]
    )
    pre_write_items = "".join(
        f"<li>{item}</li>" for item in category["pre_write_checks"]
    )
    category_cards.append(
        '<div class="room-prep-card">'
        '<div class="room-prep-head">'
        f'<h3>{category["audience_problem"]}</h3>'
        f'<span class="room-prep-status status-{status_key}">{status_label}</span>'
        '</div>'
        f'<p class="room-prep-meta">Pinterest投稿のテーマ案：'
        f'<b>{category["pinterest_theme_idea"]}</b></p>'
        '<p class="room-prep-meta">カテゴリ候補（実在の商品名・価格・ランキング・'
        '在庫・成果予測は表示しません）</p>'
        f'<ul class="room-prep-genres">{genre_items}</ul>'
        '<div class="room-prep-checks">'
        '<h4>ROOMで手動確認する項目</h4>'
        f'<ul>{room_check_items}</ul>'
        '<h4>商品紹介文を作る前の確認項目</h4>'
        f'<ul>{pre_write_items}</ul>'
        '</div>'
        '</div>'
    )
  return (
      '<section class="room-prep-section" id="room-prep" aria-label="楽天ROOM投稿準備">'
      '<h2>ROOM投稿準備</h2>'
      '<div class="room-prep-notice">'
      '<b>ROOMへの登録は手動です。Pinterestへの公開も、社長の承認後に行います。</b>'
      '<ul>'
      '<li>楽天ROOM・SNSへの自動投稿、予約投稿、API連携、スクレイピング、'
      '商品情報取得は一切行いません。</li>'
      '<li>楽天市場の商品画像は保存・加工・表示しません。使用する画像は'
      '既存のローカル素材のみです。</li>'
      '</ul>'
      '</div>'
      '<div class="room-prep-pr-note">'
      '<b>PR表記について：</b>'
      '商品提供・クーポン・広告主とのやり取りがある場合は、投稿前にPR表記が'
      '必要かどうかを確認してください。'
      '</div>'
      + published_block
      + "".join(category_cards) +
      '<a class="cs-first-post-link" href="/content-studio/room-daily-candidates">'
      '→ 楽天ROOM 毎日の投稿候補（下書き）を見る</a>'
      '</section>'
  )


# MISSION 060: 楽天ROOMの「毎日5件・投稿候補下書き」機能。
#
# ♡(いいね)が10以上ついた投稿があるジャンルを優先し、1日あたり最大5件の
# 投稿候補を下書きできるようにする。実際の♡数・コメント数・確認日は、
# 柴犬社長がROOM上で目視確認して手動入力する想定であり、このアプリが
# 自動取得・推測することは一切ない(このデータ構造にも架空の反応実績・
# 購入体験・口コミは一切含めない)。入力内容はブラウザのlocalStorageに
# のみ保存し(このアプリのDB・バックアップ・サーバーへの送信は一切ない。
# ブラウザを変える/localStorageを消すと内容は失われる)、楽天ROOM・楽天
# アフィリエイト・Pinterest・note・Threadsへの投稿・送信・ログイン・
# 外部API通信・ブラウザ自動操作は一切行わない。「ROOMで投稿する」は
# チェック欄であり、外部への投稿を実行するボタンではない(実際の投稿は
# 利用者がROOM上で手動で行う)。商品画像の取得・生成画像の自動アップロード
# ・#オリジナル写真の自動付与も行わない(この画面に画像アップロード欄・
# 画像プレビューは存在しない)。将来ルールを差し替える場合は、この
# データ構造を編集するだけでよい。
ROOM_CANDIDATE_HEART_THRESHOLD = 10
ROOM_CANDIDATE_MAX_PER_DAY = 5
ROOM_CANDIDATE_HASHTAG_COUNT = 5
# MISSION 087: ハッシュタグは#楽天ROOMを含め3〜5個にする(以前は常に5個へ
# 埋めていたが、無理に汎用タグで埋めない)。
ROOM_CANDIDATE_HASHTAG_MIN_COUNT = 3
# MISSION 087: 生成する紹介文は、読者がそのまま読める120〜180字程度の
# 文章にする(社内向けの「下書き」感を消すため、以前の220〜300字という
# 長い目安から短縮した)。
ROOM_CANDIDATE_INTRO_MIN_LENGTH = 120
ROOM_CANDIDATE_INTRO_TARGET_LENGTH = 180
# 現在、♡10以上の投稿が確認できている有力ジャンル(社長確認済みの事実)。
# 具体的な♡数・コメント数は、候補ごとに柴犬社長が手動入力するため、ここ
# には含めない(架空の数値を書かないため)。
ROOM_CANDIDATE_PRIORITY_GENRES = ["バッグの中の整理", "スマホ周辺の持ち運び収納"]

# MISSION 061: 「紹介文とハッシュタグを作成」ボタン用のテンプレート辞書。
# 入力済みのジャンル・商品名・♡数・コメント数「だけ」から紹介文と
# ハッシュタグをその場で組み立てる(=クライアント側JSのテンプレート
# 生成であり、外部API・AI APIへの送信は一切ない)。実際に使用した・
# 購入した・効果があった・口コミで高評価・最安値といった、入力から
# 確認できない事実は書かない。価格・商品仕様・レビュー数・商品ページの
# 内容をURLから取得することもしない。ジャンルに合わせたハッシュタグ候補
# はこの辞書にないジャンルではROOM_CANDIDATE_FALLBACK_HASHTAGSを使う。
ROOM_CANDIDATE_GENRE_HASHTAGS = {
    "バッグの中の整理": ["#バッグの中身", "#持ち物整理", "#収納アイデア"],
    "スマホ周辺の持ち運び収納": ["#スマホ収納", "#ガジェット収納", "#持ち運びグッズ"],
}
ROOM_CANDIDATE_FALLBACK_HASHTAGS = ["#暮らしを整える", "#便利グッズ", "#収納アイデア"]
ROOM_CANDIDATE_BASE_HASHTAG = "#楽天ROOM"

# MISSION 087: 紹介文を、社内向けの説明が混ざらない読者向けの文章へ
# 作り直すためのジャンル別テンプレート。「困りごと・使う場面(hook)」
# 「商品カテゴリが役立ちそうな場面(scene、{product}に商品名が入る)」
# 「購入前に見るポイントの案内(check)」の3文構成に固定する。反応数・
# コメント数、断定的な使用体験・効果・レビュー・最安値・在庫には一切
# 触れない(入力から確認できない事実のため)。辞書にないジャンルは
# ROOM_CANDIDATE_INTRO_FALLBACK_*を使う。
ROOM_CANDIDATE_INTRO_TEMPLATES = {
    "バッグの中の整理": {
        "hook": "バッグの中で物がごちゃつきがちな方へ。",
        "scene": (
            "{product}は、小物をまとめて整理したいときに役立ちそうな"
            "アイテムです。必要なものをあらかじめ分けておくと、バッグの中で"
            "探す手間も減らせそうです。"
        ),
        "check": "サイズや仕切りの数など、購入前に商品ページで確認してみてください。",
    },
    "スマホ周辺の持ち運び収納": {
        "hook": "バッグの中で充電ケーブルやモバイルバッテリーが絡まりがちな方へ。",
        "scene": (
            "{product}は、スマホ周辺の小物をまとめて持ち運びたいときに"
            "便利そうなアイテムです。仕事の日や旅行の準備で必要なものを"
            "分けておくと、バッグの中を探す手間も減らせそうです。"
        ),
        "check": (
            "手持ちの充電器や小物が入るか、サイズ・収納部分の仕様は"
            "商品ページで確認してみてください。"
        ),
    },
}
ROOM_CANDIDATE_INTRO_FALLBACK_HOOK = "{genre}で気になることがある方へ。"
ROOM_CANDIDATE_INTRO_FALLBACK_SCENE = (
    "{product}は、{genre}の場面で役立ちそうなアイテムです。必要なものを"
    "あらかじめまとめておくと、日々の準備や片付けの手間を減らせそうです。"
)
ROOM_CANDIDATE_INTRO_FALLBACK_CHECK = (
    "気になる方は、サイズや仕様など、購入前に商品ページで確認してみてください。"
)


def _render_room_daily_candidates_scene():
  """楽天ROOMの「毎日5件・投稿候補下書き」画面のHTMLを組み立てる。

  純粋な表示用マークアップ+クライアント側JSのみで構成する。DB・API・
  楽天ROOM・楽天アフィリエイト・Pinterest・note・Threadsへの通信は一切
  行わない。入力値の保存先はブラウザのlocalStorageのみで、フォーム
  送信(<form method="POST">等)や外部へのfetch/XHRは一切使わない。
  「ROOMで投稿する」はチェックボックスであり、クリックしても外部投稿は
  発生しない。
  """
  genre_options = "".join(
      f'<option value="{genre}"></option>' for genre in ROOM_CANDIDATE_PRIORITY_GENRES
  )
  priority_genre_items = "".join(
      f"<li>{genre}</li>" for genre in ROOM_CANDIDATE_PRIORITY_GENRES
  )

  def _candidate_card(slot):
    hashtag_inputs = "".join(
        f'<input type="text" class="rc-hashtag" data-slot="{slot}" '
        f'data-hashtag-index="{i}" placeholder="#タグ{i + 1}">'
        for i in range(ROOM_CANDIDATE_HASHTAG_COUNT)
    )
    return (
        f'<div class="room-candidate-card" data-slot="{slot}">'
        '<div class="room-candidate-head">'
        f'<h3>候補 {slot + 1}</h3>'
        f'<span class="room-candidate-verifying-badge" data-slot="{slot}" hidden>検証中</span>'
        '</div>'
        # MISSION 089: 候補を「今日・今週・保留」に分類する操作。選択結果は
        # このMac上のアプリ内DBへ保存し、再読み込み後も保持する(ページ
        # 読み込み時にJS側でDBから現在の区分を読み戻し、ここを更新する)。
        # 新規候補・未保存の候補は、DBに行が無い間は「保留」表示のままで
        # (既存候補を勝手に「今日」へ割り当てない)、実際にボタンを押した
        # ときだけDBへ保存される。
        f'<div class="room-candidate-bucket-row" data-slot="{slot}">'
        '<span class="room-candidate-bucket-label">区分：'
        f'<b class="room-candidate-bucket-current" data-slot="{slot}">保留</b></span>'
        '<div class="room-candidate-bucket-buttons">'
        f'<button type="button" class="room-candidate-bucket-btn" '
        f'data-slot="{slot}" data-bucket="today">今日にする</button>'
        f'<button type="button" class="room-candidate-bucket-btn" '
        f'data-slot="{slot}" data-bucket="week">今週にする</button>'
        f'<button type="button" class="room-candidate-bucket-btn is-active" '
        f'data-slot="{slot}" data-bucket="hold">保留にする</button>'
        '</div>'
        '</div>'
        # MISSION 087: 最初に表示する入力は、ジャンル・商品名・楽天市場URL
        # の3つだけに絞る。未入力のまま作成を押したときは、ブラウザの
        # window.alertだけに頼らず、各欄のすぐ下に不足している項目名を
        # 表示する(rc-field-error、JS側でhidden切り替え)。
        '<div class="room-candidate-field">'
        '<label>ジャンル（♡10以上の投稿があるジャンルを優先）</label>'
        f'<input type="text" class="rc-genre" data-slot="{slot}" '
        f'list="room-candidate-genre-options" placeholder="例：{ROOM_CANDIDATE_PRIORITY_GENRES[0]}">'
        f'<p class="rc-field-error" data-slot="{slot}" data-field="genre" hidden>'
        'ジャンルを入力してください</p>'
        '</div>'
        '<div class="room-candidate-field">'
        '<label>商品名</label>'
        f'<input type="text" class="rc-product-name" data-slot="{slot}" placeholder="商品名を入力">'
        f'<p class="rc-field-error" data-slot="{slot}" data-field="product-name" hidden>'
        '商品名を入力してください</p>'
        '</div>'
        '<div class="room-candidate-field">'
        '<label>楽天市場URL（貼り付けのみ。このアプリからのアクセス・取得は行いません）</label>'
        f'<input type="text" class="rc-product-url" data-slot="{slot}" '
        'placeholder="https://item.rakuten.co.jp/...">'
        f'<p class="rc-field-error" data-slot="{slot}" data-field="product-url" hidden>'
        '楽天市場URLを入力してください</p>'
        '</div>'
        '<div class="room-candidate-generate-row">'
        f'<button type="button" class="room-candidate-generate-btn rc-generate-draft" '
        f'data-slot="{slot}">紹介文とハッシュタグを作成</button>'
        '</div>'
        '<div class="room-candidate-field">'
        f'<label>紹介文（{ROOM_CANDIDATE_INTRO_MIN_LENGTH}〜'
        f'{ROOM_CANDIDATE_INTRO_TARGET_LENGTH}字程度の目安。実際に使用していない商品について、'
        '断定的な使用体験・口コミは書かないでください）'
        f'<span class="room-candidate-intro-count" data-slot="{slot}">0字</span></label>'
        f'<textarea class="rc-intro" data-slot="{slot}" rows="5" maxlength="600"></textarea>'
        '</div>'
        '<div class="room-candidate-checks">'
        f'<label><input type="checkbox" class="rc-manual-checked" data-slot="{slot}"> 手動確認済み</label>'
        f'<label><input type="checkbox" class="rc-post-in-room" data-slot="{slot}"> ROOMで投稿する'
        '（このチェックは手動投稿の確認記録であり、ここから楽天ROOMへの投稿・送信は'
        '行われません。実際の投稿は利用者がROOM上で手動で行ってください。）</label>'
        '</div>'
        # MISSION 087: ♡数・コメント数・確認日・ハッシュタグの細かな編集は
        # 「詳細設定」に折りたたみ、最初の画面を簡潔にする。
        '<details class="room-candidate-advanced">'
        '<summary>詳細設定</summary>'
        '<div class="room-candidate-advanced-body">'
        '<div class="room-candidate-field">'
        '<label>参考にした反応実績（ROOM上で確認した内容を手動入力）</label>'
        '<div class="room-candidate-reaction-inputs">'
        f'<label>♡数<input type="number" min="0" class="rc-hearts" data-slot="{slot}"></label>'
        f'<label>コメント数<input type="number" min="0" class="rc-comments" data-slot="{slot}"></label>'
        f'<label>確認日<input type="date" class="rc-checked-date" data-slot="{slot}"></label>'
        '</div>'
        '</div>'
        '<div class="room-candidate-field">'
        f'<label>ハッシュタグ（{ROOM_CANDIDATE_HASHTAG_MIN_COUNT}〜'
        f'{ROOM_CANDIDATE_HASHTAG_COUNT}個）</label>'
        f'<div class="room-candidate-hashtags">{hashtag_inputs}</div>'
        '</div>'
        '</div>'
        '</details>'
        f'{_manual_post_complete_box_html(slot)}'
        '</div>'
    )

  candidate_cards = "".join(
      _candidate_card(slot) for slot in range(ROOM_CANDIDATE_MAX_PER_DAY)
  )

  return (
      '<section class="room-candidate-board" aria-label="楽天ROOM 毎日の投稿候補（下書き）">'
      # MISSION 089: 投稿完了していない楽天ROOM候補を「今日・今週・保留」
      # で件数表示する。このMac上のアプリ内DBを読み取り専用で参照する
      # (件数は全ての対象日をまたいで集計する)。
      '<div class="room-candidate-bucket-summary" id="rc-bucket-summary" '
      'aria-live="polite">'
      '<div class="rc-bucket-chip" data-bucket="today">'
      '<b id="rc-bucket-count-today">0</b><span>今日</span></div>'
      '<div class="rc-bucket-chip" data-bucket="week">'
      '<b id="rc-bucket-count-week">0</b><span>今週</span></div>'
      '<div class="rc-bucket-chip" data-bucket="hold">'
      '<b id="rc-bucket-count-hold">0</b><span>保留</span></div>'
      '</div>'
      '<p class="room-candidate-bucket-note">件数は、まだ投稿が完了していない楽天ROOM候補を、'
      'このMac上のアプリ内データ（SQLite）から数えたものです。外部への送信は行いません。</p>'
      '<div class="room-prep-notice">'
      '<b>この画面はローカルのみで動作する下書きツールです。</b>'
      '<ul>'
      '<li>楽天ROOM・楽天アフィリエイト・Pinterest・note・Threadsへの投稿・送信・'
      'ログイン・外部API通信・ブラウザ自動操作は一切行いません。</li>'
      '<li>「ROOMで投稿する」はチェック欄であり、外部投稿を実行するボタンでは'
      'ありません。実際の投稿は、利用者がROOM上で内容を確認したうえで手動で'
      '行ってください。</li>'
      '<li>入力内容は、まずお使いのブラウザのlocalStorageに保存されます。'
      '「手動投稿を完了した」を押すと、その時点の内容がこのMac上のアプリ内'
      'データ（SQLite）にも保存され、運用司令室・AIオフィスから参照できる'
      'ようになります。どちらも外部のサービスへは送信されません。'
      'ブラウザや端末を変えたり、ブラウザのデータを消去してlocalStorageが'
      '失われても、アプリ内データに保存済みの内容は残ります。</li>'
      '<li>「今日にする」「今週にする」「保留にする」は、候補を整理するための'
      '区分であり、押すとその時点の内容がこのMac上のアプリ内データに保存されます。'
      '外部サービスへの投稿・送信は行いません。既存の候補は、自分で区分を'
      '選ぶまで「保留」のままです。</li>'
      '<li>商品画像の取得・生成画像の自動アップロード・#オリジナル写真の自動付与は'
      '行いません。実際に使用していない商品についての購入・使用体験や口コミは'
      '書かないでください。</li>'
      '<li>「紹介文とハッシュタグを作成」「まとめて紹介文を作成する」は、入力済みの'
      'ジャンル・商品名だけをもとに、このブラウザの中だけで文章を組み立てる機能です。'
      '外部API・AI APIへの送信は行わず、実際に使用した・購入した・効果があった・'
      '口コミで高評価・最安値といった、入力から確認できない内容は書きません。'
      'すでに紹介文やハッシュタグが入力されている場合は、上書き前に確認が表示されます。</li>'
      '</ul>'
      '</div>'
      '<div class="room-candidate-rules">'
      '<b>候補の選び方（優先ルール）</b>'
      f'♡が{ROOM_CANDIDATE_HEART_THRESHOLD}以上ついた投稿があるジャンルを最優先にします。'
      '現在、確認できている有力ジャンルは次のとおりです（具体的な♡数・コメント数は、'
      '候補ごとに手動で記録してください）。'
      f'<ul>{priority_genre_items}</ul>'
      f'反応実績（♡数）が{ROOM_CANDIDATE_HEART_THRESHOLD}未満、または未入力の候補は、'
      '「検証中」と表示されます。'
      '</div>'
      f'<datalist id="room-candidate-genre-options">{genre_options}</datalist>'
      '<div class="room-candidate-date-nav">'
      '<button type="button" id="rc-prev-day">← 前日</button>'
      '<label for="rc-date-input" class="sr-only">対象日</label>'
      '<input type="date" id="rc-date-input">'
      '<button type="button" id="rc-today">今日</button>'
      '<button type="button" id="rc-next-day">翌日 →</button>'
      '<span id="rc-date-label"></span>'
      '</div>'
      '<div class="room-candidate-bulk-actions">'
      '<button type="button" id="rc-generate-all">まとめて紹介文を作成する</button>'
      '<p>ジャンル・商品名・楽天市場URLを入力した候補すべてに、紹介文とハッシュタグを'
      'まとめて自動入力します（外部への投稿・送信は行いません）。入力済みの紹介文・'
      'ハッシュタグは確認のうえ上書きされます。</p>'
      '</div>'
      f'{candidate_cards}'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の下書き'
      'ツールです。楽天ROOM・楽天アフィリエイト・Pinterest・note・Threadsへの投稿・'
      '送信・ログインは行われません。</p>'
      '<script>'
      '(function(){'
      'const MAX_SLOTS=' + str(ROOM_CANDIDATE_MAX_PER_DAY) + ';'
      'const HEART_THRESHOLD=' + str(ROOM_CANDIDATE_HEART_THRESHOLD) + ';'
      'const HASHTAG_COUNT=' + str(ROOM_CANDIDATE_HASHTAG_COUNT) + ';'
      'const HASHTAG_MIN_COUNT=' + str(ROOM_CANDIDATE_HASHTAG_MIN_COUNT) + ';'
      'const BASE_HASHTAG=' + json.dumps(ROOM_CANDIDATE_BASE_HASHTAG) + ';'
      'const GENRE_HASHTAGS=' + json.dumps(ROOM_CANDIDATE_GENRE_HASHTAGS, ensure_ascii=False) + ';'
      'const FALLBACK_HASHTAGS=' + json.dumps(ROOM_CANDIDATE_FALLBACK_HASHTAGS, ensure_ascii=False) + ';'
      'const INTRO_TEMPLATES=' + json.dumps(ROOM_CANDIDATE_INTRO_TEMPLATES, ensure_ascii=False) + ';'
      'const INTRO_FALLBACK_HOOK=' + json.dumps(ROOM_CANDIDATE_INTRO_FALLBACK_HOOK, ensure_ascii=False) + ';'
      'const INTRO_FALLBACK_SCENE=' + json.dumps(ROOM_CANDIDATE_INTRO_FALLBACK_SCENE, ensure_ascii=False) + ';'
      'const INTRO_FALLBACK_CHECK=' + json.dumps(ROOM_CANDIDATE_INTRO_FALLBACK_CHECK, ensure_ascii=False) + ';'
      'const STORAGE_PREFIX="ai-hive-room-candidate:";'
      'const dateInput=document.querySelector("#rc-date-input");'
      'const dateLabel=document.querySelector("#rc-date-label");'
      'function toIsoDate(d){'
      'const y=d.getFullYear();'
      'const m=String(d.getMonth()+1).padStart(2,"0");'
      'const day=String(d.getDate()).padStart(2,"0");'
      'return y+"-"+m+"-"+day;'
      '}'
      'function fieldsForSlot(slot){'
      'return {'
      'genre:document.querySelector(\'.rc-genre[data-slot="\'+slot+\'"]\'),'
      'productName:document.querySelector(\'.rc-product-name[data-slot="\'+slot+\'"]\'),'
      'productUrl:document.querySelector(\'.rc-product-url[data-slot="\'+slot+\'"]\'),'
      'hearts:document.querySelector(\'.rc-hearts[data-slot="\'+slot+\'"]\'),'
      'comments:document.querySelector(\'.rc-comments[data-slot="\'+slot+\'"]\'),'
      'checkedDate:document.querySelector(\'.rc-checked-date[data-slot="\'+slot+\'"]\'),'
      'intro:document.querySelector(\'.rc-intro[data-slot="\'+slot+\'"]\'),'
      'manualChecked:document.querySelector(\'.rc-manual-checked[data-slot="\'+slot+\'"]\'),'
      'postInRoom:document.querySelector(\'.rc-post-in-room[data-slot="\'+slot+\'"]\'),'
      'hashtags:Array.from(document.querySelectorAll(\'.rc-hashtag[data-slot="\'+slot+\'"]\'))'
      '.sort((a,b)=>Number(a.dataset.hashtagIndex)-Number(b.dataset.hashtagIndex)),'
      '};'
      '}'
      'function storageKey(iso,slot){return STORAGE_PREFIX+iso+":"+slot;}'
      'function updateVerifyingBadge(slot,fields){'
      'const badge=document.querySelector(\'.room-candidate-verifying-badge[data-slot="\'+slot+\'"]\');'
      'if(!badge)return;'
      'const hearts=fields.hearts.value;'
      'const isVerifying=hearts===""||Number(hearts)<HEART_THRESHOLD;'
      'badge.hidden=!isVerifying;'
      '}'
      'function updateIntroCount(slot,fields){'
      'const counter=document.querySelector(\'.room-candidate-intro-count[data-slot="\'+slot+\'"]\');'
      'if(!counter)return;'
      'counter.textContent=(fields.intro.value||"").length+"字";'
      '}'
      'function loadSlot(iso,slot){'
      'const fields=fieldsForSlot(slot);'
      'let saved={};'
      'try{'
      'const raw=window.localStorage.getItem(storageKey(iso,slot));'
      'saved=raw?JSON.parse(raw):{};'
      '}catch(e){saved={};}'
      'fields.genre.value=saved.genre||"";'
      'fields.productName.value=saved.productName||"";'
      'fields.productUrl.value=saved.productUrl||"";'
      'fields.hearts.value=saved.hearts||"";'
      'fields.comments.value=saved.comments||"";'
      'fields.checkedDate.value=saved.checkedDate||"";'
      'fields.intro.value=saved.intro||"";'
      'fields.manualChecked.checked=Boolean(saved.manualChecked);'
      'fields.postInRoom.checked=Boolean(saved.postInRoom);'
      'const savedHashtags=saved.hashtags||[];'
      'fields.hashtags.forEach((el,i)=>{el.value=savedHashtags[i]||"";});'
      'updateVerifyingBadge(slot,fields);'
      'updateIntroCount(slot,fields);'
      '}'
      'function saveSlot(iso,slot){'
      'const fields=fieldsForSlot(slot);'
      'const data={'
      'genre:fields.genre.value,'
      'productName:fields.productName.value,'
      'productUrl:fields.productUrl.value,'
      'hearts:fields.hearts.value,'
      'comments:fields.comments.value,'
      'checkedDate:fields.checkedDate.value,'
      'intro:fields.intro.value,'
      'manualChecked:fields.manualChecked.checked,'
      'postInRoom:fields.postInRoom.checked,'
      'hashtags:fields.hashtags.map(el=>el.value),'
      '};'
      'try{'
      'window.localStorage.setItem(storageKey(iso,slot),JSON.stringify(data));'
      '}catch(e){/* localStorageが使えない環境でも画面は壊さない */}'
      'updateVerifyingBadge(slot,fields);'
      'updateIntroCount(slot,fields);'
      '}'
      'function isFilledSlot(fields){'
      'return Boolean(fields.genre.value.trim())&&Boolean(fields.productName.value.trim())&&'
      'Boolean(fields.productUrl.value.trim());'
      '}'
      'function hasAnyContent(fields){'
      'return Boolean(fields.genre.value.trim())||Boolean(fields.productName.value.trim())||'
      'Boolean(fields.productUrl.value.trim());'
      '}'
      'function hasDraftContent(fields){'
      'return Boolean(fields.intro.value.trim())||fields.hashtags.some(el=>el.value.trim());'
      '}'
      # MISSION 087: ジャンル・商品名・楽天市場URLが未入力のときは、
      # window.alertだけに頼らず、各欄のすぐ下に不足している項目名を
      # 表示する(読み上げでも伝わるよう通常のテキストとして表示する)。
      'function setFieldError(slot,field,show){'
      'const el=document.querySelector('
      '\'.rc-field-error[data-slot="\'+slot+\'"][data-field="\'+field+\'"]\');'
      'if(el)el.hidden=!show;'
      '}'
      'function validateSlot(slot,fields){'
      'const genreOk=Boolean(fields.genre.value.trim());'
      'const nameOk=Boolean(fields.productName.value.trim());'
      'const urlOk=Boolean(fields.productUrl.value.trim());'
      'setFieldError(slot,"genre",!genreOk);'
      'setFieldError(slot,"product-name",!nameOk);'
      'setFieldError(slot,"product-url",!urlOk);'
      'return genreOk&&nameOk&&urlOk;'
      '}'
      # MISSION 087: ハッシュタグは#楽天ROOMとジャンルに沿うものを含む
      # 3〜5個にする(以前は汎用タグで必ず5個まで埋めていたが、最低3個の
      # 下限だけにする)。
      'function generateHashtags(genre){'
      'const tags=[BASE_HASHTAG];'
      'const g=(genre||"").trim();'
      'if(g){'
      'const cleaned=g.replace(/[\\s#]+/g,"");'
      'if(cleaned&&!tags.includes("#"+cleaned))tags.push("#"+cleaned);'
      '}'
      'const extra=GENRE_HASHTAGS[g]||FALLBACK_HASHTAGS;'
      'for(const t of extra){'
      'if(tags.length>=HASHTAG_COUNT)break;'
      'if(!tags.includes(t))tags.push(t);'
      '}'
      'let i=0;'
      'while(tags.length<HASHTAG_MIN_COUNT&&i<FALLBACK_HASHTAGS.length){'
      'if(!tags.includes(FALLBACK_HASHTAGS[i]))tags.push(FALLBACK_HASHTAGS[i]);'
      'i++;'
      '}'
      'return tags.slice(0,HASHTAG_COUNT);'
      '}'
      # MISSION 087: 紹介文は、困りごと・使う場面(hook)→商品カテゴリが
      # 役立ちそうな場面(scene)→購入前に見るポイントの案内(check)、の
      # 3文構成だけで組み立てる。候補・下書き・記録・入力・アプリ・この
      # 画面・ローカル・データベースといった社内向けの語や、♡数・
      # コメント数、未確認の使用体験・効果・レビュー・最安値・在庫には
      # 一切触れない(すべて入力から確認できる事実の範囲のみ)。
      'function generateIntro(genre,productName){'
      'const g=(genre||"").trim();'
      'const p=(productName||"").trim()||"この商品";'
      'const tmpl=INTRO_TEMPLATES[g];'
      'let hook,scene,check;'
      'if(tmpl){'
      'hook=tmpl.hook;'
      'scene=tmpl.scene.replace("{product}",p);'
      'check=tmpl.check;'
      '}else{'
      'const gLabel=g||"気になるジャンル";'
      'hook=INTRO_FALLBACK_HOOK.replace("{genre}",gLabel);'
      'scene=INTRO_FALLBACK_SCENE.replace("{product}",p).replace("{genre}",gLabel);'
      'check=INTRO_FALLBACK_CHECK;'
      '}'
      'return [hook,scene,check].join("\\n\\n");'
      '}'
      'function dispatchInput(el){el.dispatchEvent(new Event("input",{bubbles:true}));}'
      'function applyDraftToSlot(slot,fields){'
      'const genre=fields.genre.value.trim();'
      'const productName=fields.productName.value.trim();'
      'fields.intro.value=generateIntro(genre,productName);'
      'const tags=generateHashtags(genre);'
      'fields.hashtags.forEach((el,i)=>{el.value=tags[i]||"";});'
      'dispatchInput(fields.intro);'
      'fields.hashtags.forEach(dispatchInput);'
      'saveSlot(dateInput.value,slot);'
      '}'
      'function generateForSlot(slot){'
      'const fields=fieldsForSlot(slot);'
      'if(!validateSlot(slot,fields))return;'
      'if(hasDraftContent(fields)){'
      'const ok=window.confirm('
      '"すでに入力されている紹介文・ハッシュタグを上書きします。よろしいですか？");'
      'if(!ok)return;'
      '}'
      'applyDraftToSlot(slot,fields);'
      '}'
      'function generateForAllFilled(){'
      'const targets=[];'
      'let anyPartial=false;'
      'for(let slot=0;slot<MAX_SLOTS;slot++){'
      'const fields=fieldsForSlot(slot);'
      'if(!hasAnyContent(fields)){'
      'setFieldError(slot,"genre",false);'
      'setFieldError(slot,"product-name",false);'
      'setFieldError(slot,"product-url",false);'
      'continue;'
      '}'
      'anyPartial=true;'
      'if(validateSlot(slot,fields))targets.push({slot:slot,fields:fields});'
      '}'
      'if(targets.length===0){'
      'if(!anyPartial){'
      'window.alert("ジャンル・商品名・楽天市場URLを入力した候補がありません。");'
      '}'
      'return;'
      '}'
      'const hasExisting=targets.some(t=>hasDraftContent(t.fields));'
      'if(hasExisting){'
      'const ok=window.confirm('
      '"入力済みの候補の中に、すでに紹介文・ハッシュタグが入力されているものが'
      'あります。上書きします。よろしいですか？");'
      'if(!ok)return;'
      '}'
      'targets.forEach(t=>applyDraftToSlot(t.slot,t.fields));'
      '}'
      # MISSION 089: 候補を「今日・今週・保留」に整理する機能。選択結果は
      # このMac上のアプリ内DB(/api/dashboard/candidates)へ保存し、
      # 再読み込み後も保持する(外部サービスへの投稿・送信・ログインは
      # 一切行わない、同一オリジンのローカルAPIのみ)。
      'const BUCKET_LABELS={today:"今日",week:"今週",hold:"保留"};'
      'let slotBucketState={};'
      'function updateBucketRow(slot,bucket){'
      'const normalized=BUCKET_LABELS[bucket]?bucket:"hold";'
      'const label=document.querySelector('
      '\'.room-candidate-bucket-current[data-slot="\'+slot+\'"]\');'
      'if(label)label.textContent=BUCKET_LABELS[normalized];'
      'document.querySelectorAll('
      '\'.room-candidate-bucket-btn[data-slot="\'+slot+\'"]\').forEach(btn=>{'
      'btn.classList.toggle("is-active",btn.dataset.bucket===normalized);'
      '});'
      '}'
      # 既存候補は、DBにまだ区分が保存されていない間は「保留」として扱う
      # (勝手に「今日」へ割り当てない)。
      'function loadSlotBucketsForDate(iso){'
      'slotBucketState={};'
      'for(let slot=0;slot<MAX_SLOTS;slot++){updateBucketRow(slot,"hold");}'
      'if(typeof window.fetch!=="function")return;'
      'window.fetch("/api/dashboard/candidates?targetDate="+encodeURIComponent(iso))'
      '.then(res=>res.json()).then(data=>{'
      'const list=(data&&Array.isArray(data.candidates))?data.candidates:[];'
      'list.forEach(c=>{'
      'if(c.media!=="楽天ROOM"||c.slot===null||c.slot===undefined)return;'
      'slotBucketState[c.slot]={bucket:c.bucket||"hold",manualPosted:Boolean(c.manual_posted)};'
      'updateBucketRow(c.slot,c.bucket||"hold");'
      '});'
      '}).catch(()=>{});'
      '}'
      'function refreshBucketSummary(){'
      'if(typeof window.fetch!=="function")return;'
      'window.fetch("/api/dashboard/candidates").then(res=>res.json()).then(data=>{'
      'const list=(data&&Array.isArray(data.candidates))?data.candidates:[];'
      'const counts={today:0,week:0,hold:0};'
      'list.forEach(c=>{'
      'if(c.media!=="楽天ROOM"||c.manual_posted)return;'
      'const b=BUCKET_LABELS[c.bucket]?c.bucket:"hold";'
      'counts[b]++;'
      '});'
      '["today","week","hold"].forEach(b=>{'
      'const el=document.querySelector("#rc-bucket-count-"+b);'
      'if(el)el.textContent=String(counts[b]);'
      '});'
      '}).catch(()=>{});'
      '}'
      'function setBucketForSlot(slot,bucket){'
      'const fields=fieldsForSlot(slot);'
      'const genre=fields.genre.value.trim();'
      'const productName=fields.productName.value.trim();'
      'const productUrl=fields.productUrl.value.trim();'
      'const intro=fields.intro.value;'
      'const hashtags=fields.hashtags.map(el=>el.value.trim()).filter(v=>v);'
      'const manualChecked=fields.manualChecked.checked;'
      'const existing=slotBucketState[slot]||{};'
      'updateBucketRow(slot,bucket);'
      'slotBucketState[slot]={bucket:bucket,manualPosted:Boolean(existing.manualPosted)};'
      'if(typeof window.fetch!=="function")return;'
      'window.fetch("/api/dashboard/candidates",{'
      'method:"POST",headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify({'
      'targetDate:dateInput.value,media:"楽天ROOM",slot:slot,genre:genre,'
      'productName:productName,url:productUrl,intro:intro,hashtags:hashtags,'
      'manualChecked:manualChecked,manualPosted:Boolean(existing.manualPosted),'
      'bucket:bucket'
      '})'
      '}).then(()=>{refreshBucketSummary();}).catch(()=>{});'
      '}'
      'document.querySelectorAll(".room-candidate-bucket-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'setBucketForSlot(Number(btn.dataset.slot),btn.dataset.bucket);'
      '});'
      '});'
      'function loadAllSlots(){'
      'const iso=dateInput.value;'
      'dateLabel.textContent=iso;'
      'for(let slot=0;slot<MAX_SLOTS;slot++){loadSlot(iso,slot);}'
      'loadSlotBucketsForDate(iso);'
      '}'
      'function bindSlotEvents(){'
      'for(let slot=0;slot<MAX_SLOTS;slot++){'
      'const fields=fieldsForSlot(slot);'
      'const inputs=[fields.genre,fields.productName,fields.productUrl,fields.hearts,'
      'fields.comments,fields.checkedDate,fields.intro,fields.manualChecked,'
      'fields.postInRoom,...fields.hashtags];'
      'inputs.forEach(el=>{'
      'if(!el)return;'
      'el.addEventListener("input",()=>saveSlot(dateInput.value,slot));'
      'el.addEventListener("change",()=>saveSlot(dateInput.value,slot));'
      '});'
      # MISSION 087: 不足項目を入力し始めたら、その場でエラー表示を消す。
      'fields.genre.addEventListener("input",()=>setFieldError(slot,"genre",false));'
      'fields.productName.addEventListener("input",()=>'
      'setFieldError(slot,"product-name",false));'
      'fields.productUrl.addEventListener("input",()=>'
      'setFieldError(slot,"product-url",false));'
      '}'
      '}'
      'function shiftDate(days){'
      'const current=dateInput.value?new Date(dateInput.value+"T00:00:00"):new Date();'
      'current.setDate(current.getDate()+days);'
      'dateInput.value=toIsoDate(current);'
      'loadAllSlots();'
      '}'
      'const today=new Date();'
      # MISSION 089: AIオフィス・投稿企画工場の「今日の一歩」から、特定の
      # 候補が入っている対象日へ直接移動できるよう、?date=YYYY-MM-DDを
      # 初期表示日として受け付ける(無効な値は無視して今日の日付を使う)。
      'const urlParams=new URLSearchParams(window.location.search);'
      'const dateParam=urlParams.get("date");'
      'const isValidDateParam=dateParam&&/^\\d{4}-\\d{2}-\\d{2}$/.test(dateParam);'
      'dateInput.value=isValidDateParam?dateParam:toIsoDate(today);'
      'bindSlotEvents();'
      'loadAllSlots();'
      'refreshBucketSummary();'
      'document.querySelector("#rc-prev-day").addEventListener("click",()=>shiftDate(-1));'
      'document.querySelector("#rc-next-day").addEventListener("click",()=>shiftDate(1));'
      'document.querySelector("#rc-today").addEventListener("click",()=>{'
      'dateInput.value=toIsoDate(new Date());'
      'loadAllSlots();'
      '});'
      'dateInput.addEventListener("change",loadAllSlots);'
      'document.querySelectorAll(".rc-generate-draft").forEach(btn=>{'
      'btn.addEventListener("click",()=>generateForSlot(Number(btn.dataset.slot)));'
      '});'
      'document.querySelector("#rc-generate-all")'
      '.addEventListener("click",generateForAllFilled);'
      '})();'
      '</script>'
      f'<script>{_manual_post_complete_script("楽天ROOM", ".rc-product-name", ".rc-product-url", genre_selector=".rc-genre", intro_selector=".rc-intro", hashtag_selector=".rc-hashtag", manual_checked_selector=".rc-manual-checked", date_input_id="rc-date-input")}</script>'
      '</section>'
  )


# MISSION 062: note向け「毎日2本の記事候補・下書き」機能。
#
# AI初心者向けnoteのテーマから、1日あたり最大2本の記事候補(タイトル・想定
# 読者・無料/有料区分・導入3行・見出し・2,500〜3,500字の下書き・ハッシュ
# タグ5個)を下書きできるようにする。「今日の2記事候補を作成」ボタンは、
# テーマ一覧(NOTE_CANDIDATE_THEMES)から日付に応じて2件を選び、固定の
# テンプレート文からブラウザ内だけで文章を組み立てる(外部API・AI APIへの
# 送信は一切ない)。実際の購入・使用・収益・売上・体験談・口コミ・成果は
# 書かず、価格・投資・法律・医療・健康について断定的な表現も使わない。
# 他者の記事・画像・文章のコピーも行わない。「無料記事か、有料記事候補か」
# は生成時は常に「無料記事」を選択し、自動で有料記事候補にすることはない
# (有料記事候補にするかどうかは、複数の無料記事を公開して反応を確認した
# あとに利用者が手動で選び直す運用)。入力内容はブラウザのlocalStorageに
# のみ保存し(このアプリのDB・バックアップ・サーバーへの送信は一切ない。
# ブラウザを変える/localStorageを消すと内容は失われる)、note・Pinterest・
# Threads・楽天ROOM・楽天アフィリエイトへのアクセス・送信・ログイン・
# 投稿・外部API通信・ブラウザ自動操作は一切行わない。「noteで手動公開する」
# はチェック欄であり、外部への公開を実行するボタンではない(実際の公開は
# 利用者がnote上で手動で行う)。
# MISSION 063: 本文を1,200〜1,800字から2,500〜3,500字へ拡張し、見出しを
# 3〜5個から5〜7個へ増やした。本文は「読者が感じやすい悩み→うまくいかない
# 原因→今日からできる手順→AIへ伝える具体例→よくある失敗と避け方→試すとき
# に意識したいポイント→まとめと最初の一歩」という一般的な構成(見出し7個)
# で組み立てる。この構成はどの記事にも使われる一般的な型であり、他者の
# note記事・ブログ・書籍・SNS投稿の文章そのものを取得・転載・要約・
# 言い換え・模倣することは行わない(テンプレート文はすべて自作)。
NOTE_CANDIDATE_MAX_PER_DAY = 2
NOTE_CANDIDATE_HEADING_MIN = 5
NOTE_CANDIDATE_HEADING_MAX = 7
NOTE_CANDIDATE_BODY_MIN_LENGTH = 2500
NOTE_CANDIDATE_BODY_MAX_LENGTH = 3500
NOTE_CANDIDATE_HASHTAG_COUNT = 5
NOTE_CANDIDATE_BASE_HASHTAG = "#AI活用"
# 既存の公開・下書き済みnote記事(NOTE_FIRST_ARTICLE、NOTE_SECOND_ARTICLE_
# DRAFT、NOTE_THIRD_ARTICLE_DRAFT)と題材が重ならないよう選んだ5テーマ。
# 具体的な記事本文はテンプレート生成時にJS側で組み立てるため、ここには
# タイトル・想定読者・見出し・ハッシュタグ・本文組み立て用の言い換え語
# (action_noun・example_task)という「編集可能な下書きの型」だけを置き、
# 架空の実績・体験談は一切含めない。見出しはMISSION 063の共通構成
# (悩み→原因→手順→具体例→失敗と回避→意識したいポイント→まとめ)に沿う
# 7個で統一している。
NOTE_CANDIDATE_THEMES = [
    {
        "key": "writing-basics",
        "label": "AI初心者の文章作成",
        "title": "AIに文章を書いてもらう前に、初心者が決めておきたいこと",
        "audience": "AIを使って文章を書いたことがなく、何から始めればいいか分からない人",
        "headings": [
            "文章作成でよくある悩み",
            "うまくいかない原因",
            "今日からできる手順",
            "AIに伝えるときの具体例",
            "よくある失敗と避け方",
            "試すときに意識したいポイント",
            "まとめと最初の一歩",
        ],
        "hashtags": ["#AI初心者", "#文章作成", "#ライティング", "#仕事の効率化"],
        "action_noun": "文章作成",
        "example_task": "メールの下書き",
    },
    {
        "key": "research-prep",
        "label": "AIに調べ物を頼む前の準備",
        "title": "AIに調べ物を頼む前に、確認しておきたいこと",
        "audience": "AIに情報収集や下調べを手伝ってもらいたいが、使い方に不安がある人",
        "headings": [
            "調べ物でよくある悩み",
            "うまくいかない原因",
            "今日からできる手順",
            "AIに伝えるときの具体例",
            "よくある失敗と避け方",
            "試すときに意識したいポイント",
            "まとめと最初の一歩",
        ],
        "hashtags": ["#AI初心者", "#情報収集", "#リサーチ", "#仕事の効率化"],
        "action_noun": "調べ物の依頼",
        "example_task": "資料に使う情報の下調べ",
    },
    {
        "key": "task-priority",
        "label": "タスク整理・優先順位付け",
        "title": "AIと一緒にタスクを整理し、優先順位を考える方法",
        "audience": "やることが多くて何から手をつければいいか迷いやすい人",
        "headings": [
            "タスク整理でよくある悩み",
            "うまくいかない原因",
            "今日からできる手順",
            "AIに伝えるときの具体例",
            "よくある失敗と避け方",
            "試すときに意識したいポイント",
            "まとめと最初の一歩",
        ],
        "hashtags": ["#タスク管理", "#優先順位", "#仕事術", "#AI初心者"],
        "action_noun": "タスク整理",
        "example_task": "今日やることの洗い出しと優先順位づけ",
    },
    {
        "key": "smartphone-ai",
        "label": "スマホでのAI活用",
        "title": "スマートフォンでAIを使うときに意識したいポイント",
        "audience": "パソコンよりスマートフォンでAIを使う機会が多い人",
        "headings": [
            "スマホでのAI活用でよくある悩み",
            "うまくいかない原因",
            "今日からできる手順",
            "AIに伝えるときの具体例",
            "よくある失敗と避け方",
            "試すときに意識したいポイント",
            "まとめと最初の一歩",
        ],
        "hashtags": ["#スマホ活用", "#AI初心者", "#仕事術", "#外出先での活用"],
        "action_noun": "スマホでのAI活用",
        "example_task": "外出先でのちょっとしたメモの整理",
    },
    {
        "key": "email-time-saving",
        "label": "メール下書き・仕事の時短",
        "title": "AIでメール作成の時間を短くするための考え方",
        "audience": "毎日のメール作成に時間がかかっていると感じる会社員",
        "headings": [
            "メール作成でよくある悩み",
            "うまくいかない原因",
            "今日からできる手順",
            "AIに伝えるときの具体例",
            "よくある失敗と避け方",
            "試すときに意識したいポイント",
            "まとめと最初の一歩",
        ],
        "hashtags": ["#メール術", "#時短", "#仕事の効率化", "#AI初心者"],
        "action_noun": "メール作成",
        "example_task": "取引先への確認メールの下書き",
    },
]


def _render_note_daily_candidates_scene():
  """note向け「毎日2本の記事候補・下書き」画面のHTMLを組み立てる。

  純粋な表示用マークアップ+クライアント側JSのみで構成する。DB・API・
  note・Pinterest・Threads・楽天ROOM・楽天アフィリエイトへの通信は一切
  行わない。入力値の保存先はブラウザのlocalStorageのみで、フォーム
  送信(<form method="POST">等)や外部へのfetch/XHRは一切使わない。
  「noteで手動公開する」はチェックボックスであり、クリックしても外部公開は
  発生しない。
  """
  theme_items = "".join(
      f'<li>{theme["label"]}</li>' for theme in NOTE_CANDIDATE_THEMES
  )

  def _candidate_card(slot):
    heading_inputs = "".join(
        f'<input type="text" class="nc-heading" data-slot="{slot}" '
        f'data-heading-index="{i}" placeholder="見出し{i + 1}">'
        for i in range(NOTE_CANDIDATE_HEADING_MAX)
    )
    hashtag_inputs = "".join(
        f'<input type="text" class="nc-hashtag" data-slot="{slot}" '
        f'data-hashtag-index="{i}" placeholder="#タグ{i + 1}">'
        for i in range(NOTE_CANDIDATE_HASHTAG_COUNT)
    )
    return (
        f'<div class="note-candidate-card" data-slot="{slot}">'
        '<div class="note-candidate-head">'
        f'<h3>候補 {slot + 1}</h3>'
        '</div>'
        '<div class="note-candidate-field">'
        '<label>記事タイトル</label>'
        f'<input type="text" class="nc-title" data-slot="{slot}" placeholder="記事タイトルを入力">'
        '</div>'
        '<div class="note-candidate-field">'
        '<label>想定読者</label>'
        f'<input type="text" class="nc-audience" data-slot="{slot}" placeholder="想定読者を入力">'
        '</div>'
        '<div class="note-candidate-field">'
        '<label>無料記事か、有料記事候補か</label>'
        f'<select class="nc-price-type" data-slot="{slot}">'
        '<option value="free">無料記事</option>'
        '<option value="paid-candidate">有料記事候補（複数の無料記事の反応を確認できたテーマのみ）</option>'
        '</select>'
        '<p class="note-candidate-price-note">有料記事候補は、無料記事を複数公開して反応が確認できた'
        'テーマだけを対象にしてください。この画面から自動で有料公開されることはありません。</p>'
        '</div>'
        '<div class="note-candidate-field">'
        '<label>導入3行</label>'
        f'<textarea class="nc-intro" data-slot="{slot}" rows="3" maxlength="600"></textarea>'
        '</div>'
        '<div class="note-candidate-field">'
        f'<label>見出し（{NOTE_CANDIDATE_HEADING_MIN}〜{NOTE_CANDIDATE_HEADING_MAX}個）</label>'
        f'<div class="note-candidate-headings">{heading_inputs}</div>'
        '</div>'
        '<div class="note-candidate-field">'
        f'<label>下書き本文（{NOTE_CANDIDATE_BODY_MIN_LENGTH}〜'
        f'{NOTE_CANDIDATE_BODY_MAX_LENGTH}字程度の目安。実際の購入・使用・収益・売上・'
        '体験談・口コミ・成果は書かず、価格・投資・法律・医療・健康について断定的な'
        '表現は使わないでください。他者の記事・画像・文章はコピーしないでください）'
        f'<span class="note-candidate-count" data-slot="{slot}">0字</span></label>'
        f'<textarea class="nc-body" data-slot="{slot}" rows="18" maxlength="6000"></textarea>'
        '</div>'
        '<div class="note-candidate-field">'
        f'<label>ハッシュタグ（{NOTE_CANDIDATE_HASHTAG_COUNT}個）</label>'
        f'<div class="note-candidate-hashtags">{hashtag_inputs}</div>'
        '</div>'
        '<div class="note-candidate-checks">'
        f'<label><input type="checkbox" class="nc-manual-checked" data-slot="{slot}"> 手動確認済み</label>'
        f'<label><input type="checkbox" class="nc-post-in-note" data-slot="{slot}"> noteで手動公開する'
        '（このチェックは手動公開の確認記録であり、ここからnoteへの投稿・送信は'
        '行われません。実際の公開は利用者がnote上で手動で行ってください。）</label>'
        '</div>'
        f'{_manual_post_complete_box_html(slot)}'
        '</div>'
    )

  candidate_cards = "".join(
      _candidate_card(slot) for slot in range(NOTE_CANDIDATE_MAX_PER_DAY)
  )

  return (
      '<section class="note-candidate-board" aria-label="note記事候補（毎日2本の下書き）">'
      '<div class="room-prep-notice">'
      '<b>この画面はローカルのみで動作する下書きツールです。</b>'
      '<ul>'
      '<li>noteへのログイン・下書き保存・公開・送信・外部API通信・ブラウザ自動操作は'
      '一切行いません。Pinterest・Threads・楽天ROOM・楽天アフィリエイトへのアクセス・'
      '送信・ログイン・投稿も一切行いません。</li>'
      '<li>「noteで手動公開する」はチェック欄であり、外部公開を実行するボタンでは'
      'ありません。実際の公開は、利用者がnote上で内容を確認したうえで手動で'
      '行ってください。</li>'
      '<li>入力内容は、まずお使いのブラウザのlocalStorageに保存されます。'
      '「手動投稿を完了した」を押すと、その時点の内容がこのMac上のアプリ内'
      'データ（SQLite）にも保存され、運用司令室・AIオフィスから参照できる'
      'ようになります。どちらも外部のサービスへは送信されません。'
      'ブラウザや端末を変えたり、ブラウザのデータを消去してlocalStorageが'
      '失われても、アプリ内データに保存済みの内容は残ります。</li>'
      '<li>実際の購入・使用・収益・売上・体験談・口コミ・成果は架空で書きません。'
      '価格・投資・法律・医療・健康について断定的な判断は行いません。他者のnote記事・'
      'ブログ・書籍・SNS投稿の取得・転載・要約・言い換え・模倣は行わず、本文はすべて'
      '自作のテンプレート文です。</li>'
      '<li>「有料記事候補」は、無料記事を複数公開して反応が確認できたテーマだけを'
      '対象にする運用です。この画面が自動で有料記事を公開することはありません。</li>'
      '</ul>'
      '</div>'
      '<div class="room-candidate-rules">'
      '<b>候補のテーマについて</b>'
      '「今日の2記事候補を作成」を押すと、次の5つのテーマから、既存のnote記事と'
      '題材が重ならないように選んだ2つをもとに下書きを作成します（具体的な'
      'タイトル・見出し・本文は候補ごとに編集できます）。'
      f'<ul>{theme_items}</ul>'
      '本文は「読者が感じやすい悩み→うまくいかない原因→今日からできる手順→AIへ'
      '伝える具体例→よくある失敗と避け方→試すときに意識したいポイント→まとめと'
      '最初の一歩」という、どのテーマにも使える一般的な構成（見出し7個）で組み立て'
      'ます。この構成は一般的な型を参考にしているだけで、他者の記事の文章そのものは'
      '使いません。'
      '</div>'
      '<div class="note-candidate-date-nav">'
      '<button type="button" id="nc-prev-day">← 前日</button>'
      '<label for="nc-date-input" class="sr-only">対象日</label>'
      '<input type="date" id="nc-date-input">'
      '<button type="button" id="nc-today">今日</button>'
      '<button type="button" id="nc-next-day">翌日 →</button>'
      '<span id="nc-date-label"></span>'
      '</div>'
      '<div class="note-candidate-generate-actions">'
      '<button type="button" id="nc-generate-today">今日の2記事候補を作成</button>'
      '<p>表示中の日付のテーマにもとづいて、2件の候補にタイトル・想定読者・導入・'
      '見出し・下書き本文・ハッシュタグをまとめて自動入力します。入力済みの内容は'
      '確認のうえ上書きされます。</p>'
      '</div>'
      f'{candidate_cards}'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の下書き'
      'ツールです。note・Pinterest・Threads・楽天ROOM・楽天アフィリエイトへの投稿・'
      '送信・ログインは行われません。</p>'
      '<script>'
      '(function(){'
      'const MAX_SLOTS=' + str(NOTE_CANDIDATE_MAX_PER_DAY) + ';'
      'const HEADING_MAX=' + str(NOTE_CANDIDATE_HEADING_MAX) + ';'
      'const HASHTAG_COUNT=' + str(NOTE_CANDIDATE_HASHTAG_COUNT) + ';'
      'const BASE_HASHTAG=' + json.dumps(NOTE_CANDIDATE_BASE_HASHTAG) + ';'
      'const THEMES=' + json.dumps(NOTE_CANDIDATE_THEMES, ensure_ascii=False) + ';'
      'const STORAGE_PREFIX="ai-hive-note-candidate:";'
      'const dateInput=document.querySelector("#nc-date-input");'
      'const dateLabel=document.querySelector("#nc-date-label");'
      'function toIsoDate(d){'
      'const y=d.getFullYear();'
      'const m=String(d.getMonth()+1).padStart(2,"0");'
      'const day=String(d.getDate()).padStart(2,"0");'
      'return y+"-"+m+"-"+day;'
      '}'
      'function dayIndexForDate(iso){'
      'const parts=iso.split("-").map(Number);'
      'return Math.floor(Date.UTC(parts[0],parts[1]-1,parts[2])/86400000);'
      '}'
      'function themeForSlot(iso,slot){'
      'const n=THEMES.length;'
      'const idx=((dayIndexForDate(iso)+slot)%n+n)%n;'
      'return THEMES[idx];'
      '}'
      'function fieldsForSlot(slot){'
      'return {'
      'title:document.querySelector(\'.nc-title[data-slot="\'+slot+\'"]\'),'
      'audience:document.querySelector(\'.nc-audience[data-slot="\'+slot+\'"]\'),'
      'priceType:document.querySelector(\'.nc-price-type[data-slot="\'+slot+\'"]\'),'
      'intro:document.querySelector(\'.nc-intro[data-slot="\'+slot+\'"]\'),'
      'body:document.querySelector(\'.nc-body[data-slot="\'+slot+\'"]\'),'
      'manualChecked:document.querySelector(\'.nc-manual-checked[data-slot="\'+slot+\'"]\'),'
      'postInNote:document.querySelector(\'.nc-post-in-note[data-slot="\'+slot+\'"]\'),'
      'headings:Array.from(document.querySelectorAll(\'.nc-heading[data-slot="\'+slot+\'"]\'))'
      '.sort((a,b)=>Number(a.dataset.headingIndex)-Number(b.dataset.headingIndex)),'
      'hashtags:Array.from(document.querySelectorAll(\'.nc-hashtag[data-slot="\'+slot+\'"]\'))'
      '.sort((a,b)=>Number(a.dataset.hashtagIndex)-Number(b.dataset.hashtagIndex)),'
      '};'
      '}'
      'function storageKey(iso,slot){return STORAGE_PREFIX+iso+":"+slot;}'
      'function updateBodyCount(slot,fields){'
      'const counter=document.querySelector(\'.note-candidate-count[data-slot="\'+slot+\'"]\');'
      'if(!counter)return;'
      'counter.textContent=(fields.body.value||"").length+"字";'
      '}'
      'function loadSlot(iso,slot){'
      'const fields=fieldsForSlot(slot);'
      'let saved={};'
      'try{'
      'const raw=window.localStorage.getItem(storageKey(iso,slot));'
      'saved=raw?JSON.parse(raw):{};'
      '}catch(e){saved={};}'
      'fields.title.value=saved.title||"";'
      'fields.audience.value=saved.audience||"";'
      'fields.priceType.value=saved.priceType||"free";'
      'fields.intro.value=saved.intro||"";'
      'fields.body.value=saved.body||"";'
      'fields.manualChecked.checked=Boolean(saved.manualChecked);'
      'fields.postInNote.checked=Boolean(saved.postInNote);'
      'const savedHeadings=saved.headings||[];'
      'fields.headings.forEach((el,i)=>{el.value=savedHeadings[i]||"";});'
      'const savedHashtags=saved.hashtags||[];'
      'fields.hashtags.forEach((el,i)=>{el.value=savedHashtags[i]||"";});'
      'updateBodyCount(slot,fields);'
      '}'
      'function saveSlot(iso,slot){'
      'const fields=fieldsForSlot(slot);'
      'const data={'
      'title:fields.title.value,'
      'audience:fields.audience.value,'
      'priceType:fields.priceType.value,'
      'intro:fields.intro.value,'
      'body:fields.body.value,'
      'manualChecked:fields.manualChecked.checked,'
      'postInNote:fields.postInNote.checked,'
      'headings:fields.headings.map(el=>el.value),'
      'hashtags:fields.hashtags.map(el=>el.value),'
      '};'
      'try{'
      'window.localStorage.setItem(storageKey(iso,slot),JSON.stringify(data));'
      '}catch(e){/* localStorageが使えない環境でも画面は壊さない */}'
      'updateBodyCount(slot,fields);'
      '}'
      'function loadAllSlots(){'
      'const iso=dateInput.value;'
      'dateLabel.textContent=iso;'
      'for(let slot=0;slot<MAX_SLOTS;slot++){loadSlot(iso,slot);}'
      '}'
      'function bindSlotEvents(){'
      'for(let slot=0;slot<MAX_SLOTS;slot++){'
      'const fields=fieldsForSlot(slot);'
      'const inputs=[fields.title,fields.audience,fields.priceType,fields.intro,'
      'fields.body,fields.manualChecked,fields.postInNote,'
      '...fields.headings,...fields.hashtags];'
      'inputs.forEach(el=>{'
      'if(!el)return;'
      'el.addEventListener("input",()=>saveSlot(dateInput.value,slot));'
      'el.addEventListener("change",()=>saveSlot(dateInput.value,slot));'
      '});'
      '}'
      '}'
      'function hasDraftContent(fields){'
      'return Boolean(fields.title.value.trim())||Boolean(fields.intro.value.trim())||'
      'Boolean(fields.body.value.trim())||fields.headings.some(el=>el.value.trim())||'
      'fields.hashtags.some(el=>el.value.trim());'
      '}'
      'function dispatchInput(el){el.dispatchEvent(new Event("input",{bubbles:true}));}'
      'function buildIntro(theme){'
      'return ['
      '"『"+theme.title+"』というテーマの記事候補です。",'
      '"想定読者は、"+theme.audience+"です。",'
      '"この下書きは社内確認用であり、内容は公開前に必ずご確認ください。",'
      '].join("\\n");'
      '}'
      'function sectionWorry(theme){'
      'return "■"+theme.headings[0]+"\\n"+'
      'theme.label+"に興味はあっても、いざ始めようとすると「何から手をつければいいのか"+'
      '"分からない」「自己流で進めて遠回りしそう」といった悩みを感じる人は少なくありません。"+'
      'theme.audience+"にとっては、まとまった学習時間を確保しにくいことも、こうした悩みを"+'
      '"さらに大きくしている要因のひとつだと考えられます。周りの人がどんなふうにAIを使って"+'
      '"いるのか分からず、自分のやり方が正しいのか判断できないまま、不安だけが先に立って"+'
      '"しまうこともあるでしょう。特別な知識がなくても始められる方法があるとわかれば、"+'
      '"気負わずに最初の一歩を踏み出しやすくなるはずです。この記事では、そうした悩みを"+'
      '"少しずつほどいていくための考え方を、悩みの正体・原因・今日から試せる手順・"+'
      '"伝え方の例・避けたい失敗という流れで、順を追って紹介していきます。難しい専門"+'
      '"用語は使わず、はじめてAIに触れる人でも読み進められるようにまとめています。";'
      '}'
      'function sectionCause(theme){'
      'return "■"+theme.headings[1]+"\\n"+'
      'theme.action_noun+"がうまくいかないと感じるとき、その原因は特別なスキル不足という"+'
      '"よりも、進め方が整理できていないことにあるケースが多いようです。たとえば、目的を"+'
      '"はっきりさせないままAIに相談してしまったり、一度にたくさんのことを求めすぎて"+'
      '"しまったりすると、返ってくる内容がぼんやりしたものになりがちです。また、AIに任せる"+'
      '"部分と自分で判断する部分の線引きがあいまいなままだと、結果に納得できなかったり、"+'
      '"手直しに余計な時間がかかったりすることにもつながります。もうひとつ見落としやすい"+'
      '"のが、最初のやり取りだけで判断してしまうことです。一度で理想の答えが返ってこな"+'
      '"かったとしても、それだけで「自分には向いていない」と結論づけてしまうのは、少し"+'
      '"早すぎるかもしれません。原因を一つひとつ切り分けて考えることが、改善への近道に"+'
      '"なります。";'
      '}'
      'function sectionSteps(theme){'
      'return "■"+theme.headings[2]+"\\n"+'
      '"今日から試せる手順として、まず目的を1つだけに絞って書き出してみましょう。あれも"+'
      '"これもと欲張らず、「今回はこれだけを解決したい」という範囲を決めることが最初の"+'
      '"ポイントです。次に、その目的を達成するために必要な情報や条件を、思いつく範囲で"+'
      '"かまわないので箇条書きにしておきます。完璧にそろえる必要はなく、あとから足りない"+'
      '"部分に気づいたら、その都度書き足していけば十分です。準備ができたら、"+'
      'theme.example_task+"のように身近で試しやすい場面を選び、AIに投げかけてみてください。"+'
      '"返ってきた内容をそのまま使うのではなく、自分の状況に合っているかを確認しながら、"+'
      '"必要な部分だけを取り入れる進め方がおすすめです。最初はうまく言葉にできなくても、"+'
      '"何度かやり取りするうちに、少しずつ伝え方のコツがつかめてきます。小さく試して、"+'
      '"自分のペースで慣れていく意識を持つとよいでしょう。";'
      '}'
      'function sectionExample(theme){'
      'return "■"+theme.headings[3]+"\\n"+'
      '"AIに伝えるときは、目的・前提・欲しい形式の3つを簡単な言葉で伝えると、返ってくる"+'
      '"内容がイメージに近づきやすくなります。たとえばテンプレートとして、「目的は"+'
      'theme.action_noun+"です。前提は〇〇で、△△という条件があります。□□の形式で、"+'
      '"簡潔にまとめてください」のように整理して伝える方法があります。〇〇・△△・□□の"+'
      '"部分に、自分の状況に合わせた言葉を当てはめて使ってみてください。項目を分けて伝える"+'
      '"だけでも、AIが受け取る情報の量と質が変わり、返ってくる内容の的外れ感が減っていく"+'
      '"はずです。うまく伝わらないと感じたときは、前提や条件を1つずつ足しながら、何度か"+'
      '"聞き直してみるのも有効です。一度に完璧な指示を作ろうとせず、対話を重ねながら少しずつ"+'
      '"近づけていくという姿勢で取り組んでみてください。";'
      '}'
      'function sectionMistakes(theme){'
      'return "■"+theme.headings[4]+"\\n"+'
      '"よくある失敗として、AIから返ってきた内容をそのまま使ってしまい、あとから事実関係の"+'
      '"誤りや状況とのズレに気づく、というケースが挙げられます。これを避けるには、内容を"+'
      '"そのまま受け取るのではなく、自分の目で一度確認してから使う習慣をつけることが大切です。"+'
      '"また、一度で完璧な答えを求めすぎてしまうことも失敗につながりやすいポイントです。"+'
      '"最初から理想の結果を求めるのではなく、何度かやり取りしながら少しずつ近づけていく"+'
      '"つもりで取り組むと、無理なく続けやすくなります。ほかにも、背景や前提を伝えずに"+'
      '"質問だけを投げてしまい、当たり前のことしか返ってこなかった、という失敗もよく"+'
      '"見られます。伝える情報が少ないほど、返ってくる内容も一般的なものになりやすいと"+'
      '"覚えておくとよいでしょう。焦らず、少しずつ条件を足しながら調整していく進め方を"+'
      '"意識してみてください。";'
      '}'
      'function sectionMindset(theme){'
      'return "■"+theme.headings[5]+"\\n"+'
      '"実際に試すときは、結果の良し悪しだけで判断せず、「今回はどこまで自分の言葉で"+'
      '"伝えられたか」という視点でも振り返ってみると、次に活かしやすくなります。"+'
      'theme.audience+"であっても、はじめから上手に使いこなす必要はありません。1回の"+'
      '"やり取りで終わらせず、気になったところを聞き直したり、言葉を変えて伝え直したり"+'
      '"しながら、少しずつ自分に合った使い方を見つけていく意識が大切です。うまくいった"+'
      '"ときのやり取りを覚えておき、次に似た場面で参考にするのもおすすめです。";'
      '}'
      'function sectionSummary(theme){'
      'return "■"+theme.headings[6]+"\\n"+'
      '"ここまで、"+theme.label+"について、悩みが生まれやすい理由から、今日から試せる"+'
      '"手順、AIへの伝え方の例、避けたい失敗までを整理してきました。どの内容も、特別な"+'
      '"準備や知識がなくても、今日から少しずつ試せるものばかりです。この記事は情報提供を"+'
      '"目的とした下書きであり、効果や成果を保証するものではありません。価格・投資・法律・"+'
      '"医療・健康について断定的な判断は行っておらず、実際の購入・使用・収益に関する体験談や"+'
      '"口コミも含んでいません。まずは、今日紹介した手順の中から1つだけを選んで、気負わずに"+'
      '"試してみるところから始めてみてください。小さな一歩を積み重ねていくことが、無理のない"+'
      '"上達につながっていくはずです。内容は公開前に必ず読み返し、必要に応じて手直しした"+'
      '"うえでnoteへ手動で公開してください。";'
      '}'
      'function buildBody(theme){'
      'return ['
      'sectionWorry(theme),sectionCause(theme),sectionSteps(theme),'
      'sectionExample(theme),sectionMistakes(theme),sectionMindset(theme),'
      'sectionSummary(theme),'
      '].join("\\n\\n");'
      '}'
      'function buildHashtags(theme){'
      'const tags=[BASE_HASHTAG];'
      'theme.hashtags.forEach(function(t){'
      'if(tags.length<HASHTAG_COUNT&&!tags.includes(t))tags.push(t);'
      '});'
      'return tags.slice(0,HASHTAG_COUNT);'
      '}'
      'function applyThemeToSlot(slot,theme){'
      'const fields=fieldsForSlot(slot);'
      'fields.title.value=theme.title;'
      'fields.audience.value=theme.audience;'
      'fields.priceType.value="free";'
      'fields.intro.value=buildIntro(theme);'
      'fields.body.value=buildBody(theme);'
      'const headings=theme.headings;'
      'fields.headings.forEach((el,i)=>{el.value=headings[i]||"";});'
      'const tags=buildHashtags(theme);'
      'fields.hashtags.forEach((el,i)=>{el.value=tags[i]||"";});'
      'dispatchInput(fields.title);'
      'dispatchInput(fields.intro);'
      'dispatchInput(fields.body);'
      'fields.headings.forEach(dispatchInput);'
      'fields.hashtags.forEach(dispatchInput);'
      'saveSlot(dateInput.value,slot);'
      '}'
      'function generateToday(){'
      'const iso=dateInput.value;'
      'const targets=[];'
      'for(let slot=0;slot<MAX_SLOTS;slot++){'
      'targets.push({slot:slot,fields:fieldsForSlot(slot),theme:themeForSlot(iso,slot)});'
      '}'
      'const hasExisting=targets.some(t=>hasDraftContent(t.fields));'
      'if(hasExisting){'
      'const ok=window.confirm('
      '"入力済みのタイトル・本文・見出し・ハッシュタグがある候補は上書きされます。'
      'よろしいですか？");'
      'if(!ok)return;'
      '}'
      'targets.forEach(t=>applyThemeToSlot(t.slot,t.theme));'
      '}'
      'function shiftDate(days){'
      'const current=dateInput.value?new Date(dateInput.value+"T00:00:00"):new Date();'
      'current.setDate(current.getDate()+days);'
      'dateInput.value=toIsoDate(current);'
      'loadAllSlots();'
      '}'
      'const today=new Date();'
      'dateInput.value=toIsoDate(today);'
      'bindSlotEvents();'
      'loadAllSlots();'
      'document.querySelector("#nc-prev-day").addEventListener("click",()=>shiftDate(-1));'
      'document.querySelector("#nc-next-day").addEventListener("click",()=>shiftDate(1));'
      'document.querySelector("#nc-today").addEventListener("click",()=>{'
      'dateInput.value=toIsoDate(new Date());'
      'loadAllSlots();'
      '});'
      'dateInput.addEventListener("change",loadAllSlots);'
      'document.querySelector("#nc-generate-today").addEventListener("click",generateToday);'
      '})();'
      '</script>'
      f'<script>{_manual_post_complete_script("note", ".nc-title", intro_selector=".nc-intro", hashtag_selector=".nc-hashtag", manual_checked_selector=".nc-manual-checked", date_input_id="nc-date-input")}</script>'
      '</section>'
  )


# MISSION 035: デスク環境Pinterest投稿パッケージ(ローカル専用・楽天ROOM連携用)。
#
# 楽天市場の商品画像・商品写真・商品ロゴは一切使わず、文字と図形のみで
# 構成したオリジナルPinterest画像(画面内SVG・PNG両方)を用意する。説明文には
# 「紹介アイテムは楽天ROOMに掲載しています」と明記するが、価格・在庫・
# 性能・ランキング・成果は一切断定しない。楽天ROOMの商品URLは柴犬社長が
# Pinterest投稿画面へ手動で貼り付ける前提であり、URLの取得・保存・外部
# 連携はこのアプリでは一切行わない。将来テーマ・文面・SVGの中身を差し替える
# 場合は、このデータ構造(DESK_SETUP_POST_PACKAGE)を編集するだけでよい。
DESK_SETUP_POST_PACKAGE = {
    "theme": "デスクが狭い人へ　画面まわりを整える3つの見直し",
    "pin": {
        "title": "デスクが狭い人へ。画面まわりを整える3つの見直し",
        "description": (
            "モニター位置・机上スペース・配線の3つを見直すだけで、狭いデスクでも"
            "作業スペースは変わります。紹介アイテムは楽天ROOMに掲載しています。"
            "価格・在庫・性能・ランキング・成果については、この画面では断定しません。"
        ),
        "alt_text": (
            "デスクが狭い人へ向けた、画面まわりを整える3つの見直しのイラスト。"
            "1. モニター位置を見直す 2. 机上スペースを見直す 3. 配線を見直す。"
            "商品写真・楽天市場の画像は使用していません。"
        ),
        "svg_headline": ["デスクが狭い人へ", "画面まわりを整える", "3つの見直し"],
        "svg_subtitle": "デスク環境の整え方",
        "svg_items": [
            {"number": "1", "lines": ["モニター位置を", "見直す"], "icon": "monitor"},
            {"number": "2", "lines": ["机上スペースを", "見直す"], "icon": "desk_space"},
            {"number": "3", "lines": ["配線を", "見直す"], "icon": "cable"},
        ],
        "svg_footer": "紹介アイテムは楽天ROOMに掲載しています。",
    },
    "checklist": [
        "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
        "価格・在庫・性能・ランキング・成果を断定していないか確認した",
        "画像内の文字が読みやすいか（誤字・はみ出しがないか）確認した",
        "altテキストが画像の内容を正しく説明しているか確認した",
        "楽天ROOMの商品URLを、Pinterest投稿画面へ手動で貼り付ける準備ができている",
        "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
    ],
    "room_product_note": (
        "紹介アイテムは楽天ROOMに掲載しています。価格・在庫・性能・ランキング・"
        "成果については、この画面では断定しません。"
    ),
    "room_url_note": (
        "楽天ROOMの商品URLは、柴犬社長がPinterestへ投稿する際に手動で貼り付けて"
        "ください。URLの取得・保存・外部連携は、この画面では一切行いません。"
    ),
    "manual_post_note": (
        "この投稿は、柴犬社長がPinterestで手動投稿してください。Pinterest・楽天ROOM"
        "への自動投稿・予約投稿・API連携・外部通信は一切行いません。"
    ),
}

# SVGアイコン(装飾のみ・画面内完結・外部素材なし・商品写真やロゴは使わない)。
_DESK_SETUP_ICONS = {
    "monitor": (
        '<rect x="-28" y="-22" width="56" height="36" rx="6" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<line x1="0" y1="14" x2="0" y2="26" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="-14" y1="26" x2="14" y2="26" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
    ),
    "desk_space": (
        '<line x1="-28" y1="10" x2="28" y2="10" stroke="#38bdf8" stroke-width="4" stroke-linecap="round"/>'
        '<rect x="-24" y="-26" width="16" height="32" rx="2" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<rect x="2" y="-20" width="18" height="26" rx="2" fill="none" stroke="#38bdf8" stroke-width="3"/>'
    ),
    "cable": (
        '<path d="M-26 -6 Q -13 -20 0 -6 T 26 -6" fill="none" stroke="#38bdf8" stroke-width="3" '
        'stroke-linecap="round"/>'
        '<circle cx="0" cy="20" r="16" fill="none" stroke="#38bdf8" stroke-width="3"/>'
    ),
}


def _render_desk_setup_pin_svg(pin):
  """Pinterest用の縦長2:3(1000x1500)ローカルSVG画像を組み立てる。

  外部画像・外部フォント・外部素材、楽天市場の商品画像・商品写真・商品ロゴは
  一切使わず、すべて画面内SVGの図形とテキストだけで構成する。価格・在庫・
  性能・ランキング・成果の断定的な表現は一切含めない。
  """
  headline_start_y = 130
  headline_line_h = 66
  headline_lines = "".join(
      f'<tspan x="500" dy="{0 if i == 0 else headline_line_h}">{line}</tspan>'
      for i, line in enumerate(pin["svg_headline"])
  )
  subtitle_y = headline_start_y + headline_line_h * (len(pin["svg_headline"]) - 1) + 90

  item_blocks = []
  card_height = 280
  gap = 36
  start_y = 460
  for index, item in enumerate(pin["svg_items"]):
    card_y = start_y + index * (card_height + gap)
    icon_shape = _DESK_SETUP_ICONS[item["icon"]]
    label_lines = "".join(
        f'<tspan x="220" dy="{0 if i == 0 else 46}">{line}</tspan>'
        for i, line in enumerate(item["lines"])
    )
    item_blocks.append(
        f'<g transform="translate(0,{card_y})">'
        '<rect x="60" y="0" width="880" height="' + str(card_height) + '" rx="28" '
        'fill="#101a30" stroke="#293958" stroke-width="2"/>'
        '<circle cx="150" cy="' + str(card_height // 2) + '" r="46" fill="#0b2540" '
        'stroke="#38bdf8" stroke-width="3"/>'
        '<text x="150" y="' + str(card_height // 2 + 16) + '" text-anchor="middle" '
        f'font-size="44" font-weight="700" fill="#38bdf8">{item["number"]}</text>'
        f'<g transform="translate(80,{card_height // 2})">{icon_shape}</g>'
        f'<text x="220" y="{card_height // 2 - 20}" font-size="40" font-weight="700" '
        f'fill="#f1f5f9">{label_lines}</text>'
        '</g>'
    )
  return (
      '<svg viewBox="0 0 1000 1500" xmlns="http://www.w3.org/2000/svg" '
      'role="img" aria-labelledby="dsp-svg-title dsp-svg-desc">'
      f'<title id="dsp-svg-title">{pin["title"]}</title>'
      f'<desc id="dsp-svg-desc">{pin["alt_text"]}</desc>'
      '<defs><linearGradient id="dspBg" x1="0" y1="0" x2="0" y2="1">'
      '<stop offset="0%" stop-color="#0b1220"/><stop offset="100%" stop-color="#1b2c4a"/>'
      '</linearGradient></defs>'
      '<rect width="1000" height="1500" fill="url(#dspBg)"/>'
      f'<text x="500" y="{headline_start_y}" text-anchor="middle" font-size="56" font-weight="800" '
      f'fill="#f1f5f9">{headline_lines}</text>'
      f'<text x="500" y="{subtitle_y}" text-anchor="middle" font-size="30" font-weight="600" '
      f'fill="#38bdf8">{pin["svg_subtitle"]}</text>'
      + "".join(item_blocks) +
      '<text x="500" y="1440" text-anchor="middle" font-size="26" fill="#a3b2c6">'
      f'{pin["svg_footer"]}</text>'
      '</svg>'
  )


DESK_SETUP_PNG_RELATIVE_PATH = "images/desk-setup-pin-2x3.png"
_DESK_SETUP_PNG_FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def _draw_desk_setup_icon(draw, cx, cy, kind, color):
  """PNG版アイコン(装飾のみ)を描画する。SVG版と同じ3種類の図形。"""
  if kind == "monitor":
    draw.rounded_rectangle([cx - 28, cy - 22, cx + 28, cy + 14], radius=6, outline=color, width=3)
    draw.line([(cx, cy + 14), (cx, cy + 26)], fill=color, width=3)
    draw.line([(cx - 14, cy + 26), (cx + 14, cy + 26)], fill=color, width=3)
  elif kind == "desk_space":
    draw.line([(cx - 28, cy + 10), (cx + 28, cy + 10)], fill=color, width=4)
    draw.rounded_rectangle([cx - 24, cy - 26, cx - 8, cy + 6], radius=2, outline=color, width=3)
    draw.rounded_rectangle([cx + 2, cy - 20, cx + 20, cy + 6], radius=2, outline=color, width=3)
  elif kind == "cable":
    draw.line(
        [(cx - 26, cy - 6), (cx - 13, cy - 20), (cx, cy - 6), (cx + 13, cy - 20), (cx + 26, cy - 6)],
        fill=color, width=3, joint="curve",
    )
    draw.ellipse([cx - 16, cy + 4, cx + 16, cy + 36], outline=color, width=3)


def generate_desk_setup_pin_png(pin, out_path=None):
  """デスク環境Pinterest用PNG(1000x1500)を生成し、ファイルへ保存する(開発時専用)。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。テーマや
  文言(DESK_SETUP_POST_PACKAGE)を差し替えた場合、この関数を手動で再実行して
  PNGを作り直すこと。実行にはPillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; \\
          o.generate_desk_setup_pin_png(o.DESK_SETUP_POST_PACKAGE['pin'])"
  """
  from PIL import Image, ImageDraw, ImageFont  # 遅延import(開発時専用)

  width, height = 1000, 1500
  bg_top, bg_bottom = (11, 18, 32), (27, 44, 74)
  white, blue, sub = (241, 245, 249), (56, 189, 248), (163, 178, 198)
  card_bg, card_edge, badge_bg = (16, 26, 48), (41, 57, 88), (11, 37, 64)

  img = Image.new("RGB", (width, height), bg_top)
  draw = ImageDraw.Draw(img)
  for y in range(height):
    t = y / (height - 1)
    draw.line(
        [(0, y), (width, y)],
        fill=tuple(int(bg_top[i] + (bg_bottom[i] - bg_top[i]) * t) for i in range(3)),
    )

  headline_font = ImageFont.truetype(_DESK_SETUP_PNG_FONT_PATH, 56)
  subtitle_font = ImageFont.truetype(_DESK_SETUP_PNG_FONT_PATH, 30)
  number_font = ImageFont.truetype(_DESK_SETUP_PNG_FONT_PATH, 42)
  label_font = ImageFont.truetype(_DESK_SETUP_PNG_FONT_PATH, 38)
  footer_font = ImageFont.truetype(_DESK_SETUP_PNG_FONT_PATH, 26)

  cx = width // 2
  headline_start_y = 130
  headline_line_h = 66
  y = headline_start_y
  for line in pin["svg_headline"]:
    draw.text((cx, y), line, font=headline_font, fill=white, anchor="ma")
    y += headline_line_h
  subtitle_y = headline_start_y + headline_line_h * (len(pin["svg_headline"]) - 1) + 90
  draw.text((cx, subtitle_y), pin["svg_subtitle"], font=subtitle_font, fill=blue, anchor="ma")

  card_h, gap, start_y = 280, 36, 460
  for index, item in enumerate(pin["svg_items"]):
    card_y = start_y + index * (card_h + gap)
    draw.rounded_rectangle(
        [60, card_y, 940, card_y + card_h], radius=28,
        fill=card_bg, outline=card_edge, width=2,
    )
    badge_cy = card_y + card_h // 2
    draw.ellipse(
        [150 - 46, badge_cy - 46, 150 + 46, badge_cy + 46],
        fill=badge_bg, outline=blue, width=3,
    )
    draw.text((150, badge_cy), item["number"], font=number_font, fill=blue, anchor="mm")
    _draw_desk_setup_icon(draw, 260, badge_cy, item["icon"], blue)
    ly = badge_cy - 26
    for line in item["lines"]:
      draw.text((320, ly), line, font=label_font, fill=white, anchor="lm")
      ly += 46

  draw.text((cx, 1440), pin["svg_footer"], font=footer_font, fill=sub, anchor="mm")

  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static", DESK_SETUP_PNG_RELATIVE_PATH
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def _render_desk_setup_scene(package):
  """デスク環境Pinterest投稿パッケージのHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・楽天API・外部
  通信への アクセスは一切行わない。楽天ROOMの商品URLの取得・保存・外部
  連携も行わない(社長が手動でPinterest投稿画面へ貼り付ける前提)。コピー
  用ボタンはクライアント側JSのみで完結し、クリップボード操作が失敗しても
  例外を伝播させず、安全なフォールバック表示にする。
  """
  pin = package["pin"]
  svg_markup = _render_desk_setup_pin_svg(pin)
  checklist_items = "".join(
      f'<li><input type="checkbox" id="dsp-check-{i}"><label for="dsp-check-{i}">{item}</label></li>'
      for i, item in enumerate(package["checklist"])
  )
  return (
      '<section class="desk-setup-board" aria-label="デスク環境Pinterest投稿パッケージ">'
      '<div class="fp-notice"><b>社内向けの投稿パッケージです。</b>'
      'SNSへの投稿・送信・連携は一切行われません。柴犬社長が内容を確認し、'
      '手動でPinterestへ投稿するための準備画面です。</div>'
      f'<p class="fp-theme">対象テーマ：<b>{package["theme"]}</b></p>'
      f'<div class="fp-note fp-note-warn"><b>紹介アイテムについて。</b>{package["room_product_note"]}</div>'
      f'<div class="fp-note fp-note-warn"><b>ROOM商品URLについて。</b>{package["room_url_note"]}</div>'
      f'<div class="fp-note fp-note-warn"><b>手動投稿について。</b>{package["manual_post_note"]}</div>'
      '<h3 class="fp-section-title">Pinterest投稿素材</h3>'
      '<div class="fp-pin-layout">'
      f'<div><div class="fp-svg-wrap">{svg_markup}</div>'
      '<p class="fp-svg-ratio">縦長 2:3（画面内SVG・外部画像なし、商品写真・楽天市場画像・'
      '商品ロゴは使用していません）</p>'
      # MISSION 035: 通常のダウンロードリンク(<a href download>)のみで
      # 保存する。外部通信・JavaScript必須の処理は行わない。あらかじめ
      # 生成済みのローカルPNGファイル(static/配下)を指すだけであり、
      # クリックしてもPinterest・楽天ROOMへの投稿・送信・連携は一切発生しない。
      f'<a class="fp-png-download" href="/static/{DESK_SETUP_PNG_RELATIVE_PATH}" '
      'download="pinterest-desk-setup-post.png">Pinterest用PNGを保存</a>'
      '<p class="fp-png-hint">保存したPNGをPinterestで手動アップロードし、楽天ROOMの'
      '商品URLも手動で貼り付けてください。このボタンからの投稿・送信・連携は'
      '行われません。</p></div>'
      '<div class="fp-fields">'
      '<div class="fp-field"><div class="fp-field-head"><h4>タイトル</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="dsp-title">コピー</button></div>'
      f'<p id="dsp-title">{pin["title"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>説明文</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="dsp-description">コピー</button></div>'
      f'<p id="dsp-description">{pin["description"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>altテキスト</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="dsp-alt">コピー</button></div>'
      f'<p id="dsp-alt">{pin["alt_text"]}</p></div>'
      '</div>'
      '</div>'
      '<h3 class="fp-section-title">投稿前チェックリスト</h3>'
      f'<ul class="fp-checklist">{checklist_items}</ul>'
      # MISSION 035: コピー操作はクライアント側JSのみで完結し、外部通信は
      # 行わない。navigator.clipboardが使えない/失敗する環境でも、例外を
      # 投げずに安全な文言へフォールバックする(初回手動投稿パッケージと同じ方式)。
      '<script>document.querySelectorAll(".fp-copy-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'const el=document.getElementById(btn.dataset.copyTarget);'
      'if(!el)return;'
      'const original=btn.textContent;'
      'const showResult=ok=>{btn.textContent=ok?"コピーしました":"コピーできませんでした";'
      'setTimeout(()=>{btn.textContent=original;},1800);};'
      'try{'
      'if(navigator.clipboard&&navigator.clipboard.writeText){'
      'navigator.clipboard.writeText(el.textContent).then(()=>showResult(true))'
      '.catch(()=>showResult(false));'
      '}else{showResult(false);}'
      '}catch(e){showResult(false);}'
      '});'
      '});</script>'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の資料です。'
      'Pinterest・楽天ROOMへの投稿・送信・連携は行われません。</p>'
      '</section>'
  )


# MISSION 036: Pinterest向け・手動承認つき投稿キュー(ローカル専用)。
#
# 投稿候補を「社長承認待ち」としてまとめて表示する(当初3件、MISSION 042で
# 4件目を追加)。各投稿の画像は文字と図形のみで構成し(商品写真・楽天市場
# 画像・商品ロゴ・外部素材は
# 使わない)、商品名・価格・在庫・ランキング・性能・成果予測は一切表示
# しない。楽天ROOMリンク欄は常に空欄で、「社長が手動で貼る」旨のみを
# 表示する(URLの取得・保存・外部連携は行わない)。公開は社長がPinterestで
# 手動実行する運用であることを、各カードに明記する。将来投稿内容を
# 差し替える場合は、このデータ構造(PUBLISH_QUEUE_POSTS)を編集するだけで
# よい。
# MISSION 054: 「status」を自由文字列から状態キーへ変更した。
# MISSION 054修正: 実際の公開状況は、メール下書き・スマホでのAI下書き・
# 「なんか違う」投稿(ai-mismatch-3points)の3件が柴犬社長により手動で
# Pinterestへ投稿済み("published")であり、デスク配線(desk-wiring-3points)・
# 周辺機器選び(peripheral-choice-3points)の2件は未公開のまま
# ("awaiting_president")である。公開済みPinterest5件の内訳は、この3件に
# 別データ構造のFIRST_POST_PACKAGE・DESK_SETUP_POST_PACKAGEを加えた5件。
# スマホでのAI下書きは対応するnote記事下書き(NOTE_SECOND_ARTICLE_DRAFT)が
# まだ下書きのままだが、Pinterest投稿自体は公開済みのため、両者のstatusは
# 独立して扱う。
PUBLISH_QUEUE_STATUS_LABELS = {
    "awaiting_president": "社長承認待ち",
    "published": "公開済み",
}

PUBLISH_QUEUE_POSTS = [
    {
        "id": "email-draft-3points",
        "status": "published",
        "pin": {
            "title": "AIにメールの下書きを頼む前に決める3つ",
            "description": (
                "AIにメールの下書きを頼む前に、決めておくと結果が変わる3つのポイントを"
                "まとめました。宛先・要点・トーンを先に決めるだけで、AIへの指示がぐっと"
                "具体的になります。特定の商品の紹介はありません。"
            ),
            # MISSION 039: 画像を図形イラストから高精細な写真に差し替えたため、
            # 実際の画像内容(夜のホームオフィス・ノートPC・ノート・マグカップ・
            # 観葉植物のある木目のデスク)と矛盾しないaltテキストへ更新した。
            # ロゴ・読める文字・実在サービスの画面は写っていない。
            # MISSION 039.2: 画像本体にタイトル文字を焼き込んだため、「読める
            # 文字は写っていません」という文言を、実態に合わせて修正した
            # (ロゴ・実在サービスの画面は引き続き写っていない)。
            "alt_text": (
                "AIにメールの下書きを頼む前に決める3つ、というテーマのイメージ写真。夜の"
                "ホームオフィスで、ノートパソコン・ノート・マグカップ・観葉植物が置かれた"
                "木目のデスクの様子。左上にタイトル文字を配置している。ロゴ・実在サービスの"
                "画面は写っていません。"
            ),
        },
        # MISSION 039.2: このカードだけ、図形イラスト(SVG生成)ではなく、あらかじめ
        # 用意した高精細な画像(v3.png)を<img>で表示する。タイトル文字は
        # generate_publish_queue_email_draft_v3_png()で画像本体に焼き込み済み
        # であり、Pinterestへ保存されるPNGにもそのまま含まれる(MISSION 039時点
        # ではHTML側で重ねるだけだったが、保存したPNGに文字が入らない問題が
        # あったため、039.2で画像焼き込み方式に切り替えた)。他の2件の投稿
        # (desk-wiring-3points・peripheral-choice-3points)は引き続き
        # svg_headline等のデータからSVG/PNGを生成する既存方式のまま。
        "hero_image_relative_path": "images/publish-queue-email-draft-v3.png",
        "hero_image_download_filename": "pinterest-publish-queue-email-draft-v3.png",
        # 画像焼き込み(generate_publish_queue_email_draft_v3_png)に使う元の
        # データ。連結すると"pin"."title"と完全に一致する(内容は変更せず、
        # 画像への焼き込み方法だけを変更している)。
        "hero_title_lines": ["AIにメールの下書きを", "頼む前に決める3つ"],
        # MISSION 039: 公開済みのnote記事へのPinterestリンク先。手動でPinterestの
        # 投稿画面に貼り付ける想定であり、このアプリからのアクセス・取得・保存・
        # 自動連携は一切行わない(クリックは人間の手動操作としてのみ機能する)。
        "pinterest_link_url": "https://note.com/legal_crow9879/n/nf7af35ac8c28",
        "pinterest_topic_candidates": ["AI活用術", "仕事効率化", "ビジネスメール"],
        "checklist": [
            "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
            "商品名・価格・在庫・ランキング・性能・成果予測が含まれていないか確認した",
            "画像内の文字が読みやすいか（誤字・はみ出しがないか）確認した",
            "altテキストが画像の内容を正しく説明しているか確認した",
            "リンク先のnote記事が正しく公開されているか確認した",
            "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
        ],
    },
    {
        "id": "desk-wiring-3points",
        "status": "awaiting_president",
        "pin": {
            "title": "デスクが狭いときに配線を見直す3つのポイント",
            "description": (
                "机の上や周りがごちゃつく原因の多くはケーブルです。使用頻度でまとめる・"
                "通すルートを決める・コンセント位置を確認する、この3つを見直すだけで見た目も"
                "スペースも変わります。紹介アイテムは楽天ROOMに掲載しています。価格・在庫・"
                "性能・ランキング・成果については、この画面では断定しません。"
            ),
            "alt_text": (
                "デスクが狭いときに配線を見直す3つのポイントのイラスト。1. 使用頻度で"
                "配線をまとめる 2. 机の下を通すルートを決める 3. コンセント位置を確認する。"
                "商品写真・楽天市場の画像は使用していません。"
            ),
            "svg_headline": ["デスクが狭いときに", "配線を見直す", "3つのポイント"],
            "svg_subtitle": "デスク環境の整え方",
            "svg_items": [
                {"number": "1", "lines": ["使用頻度で", "配線をまとめる"], "icon": "bundle"},
                {"number": "2", "lines": ["机の下を通す", "ルートを決める"], "icon": "route"},
                {"number": "3", "lines": ["コンセント位置を", "確認する"], "icon": "outlet"},
            ],
            "svg_footer": "紹介アイテムは楽天ROOMに掲載しています。",
        },
        "pinterest_topic_candidates": ["デスク環境", "配線収納", "在宅ワーク"],
        "checklist": [
            "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
            "価格・在庫・性能・ランキング・成果を断定していないか確認した",
            "画像内の文字が読みやすいか（誤字・はみ出しがないか）確認した",
            "altテキストが画像の内容を正しく説明しているか確認した",
            "楽天ROOMリンク欄が空欄のままであることを確認した（社長が手動で貼り付ける）",
            "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
        ],
        "png_relative_path": "images/publish-queue-desk-wiring-2x3.png",
        "png_download_filename": "pinterest-publish-queue-desk-wiring.png",
    },
    {
        "id": "peripheral-choice-3points",
        "status": "awaiting_president",
        "pin": {
            "title": "スマホ・PC作業をラクにする周辺機器の選び方",
            "description": (
                "周辺機器選びで失敗しないために、購入前に決めておきたい3つの視点を"
                "まとめました。用途・使う場所・手放せない基準を先に決めるだけで、選びやすく"
                "なります。紹介アイテムは楽天ROOMに掲載しています。価格・在庫・性能・"
                "ランキング・成果については、この画面では断定しません。"
            ),
            "alt_text": (
                "スマホ・PC作業をラクにする周辺機器の選び方のイラスト。1. 使う目的を"
                "1つ決める 2. 使う場所を想定する 3. 手放せない基準を1つ決める。"
                "商品写真・楽天市場の画像は使用していません。"
            ),
            "svg_headline": ["スマホ・PC作業を", "ラクにする周辺機器", "の選び方"],
            "svg_subtitle": "購入前に決めたい3つの視点",
            "svg_items": [
                {"number": "1", "lines": ["使う目的を", "1つ決める"], "icon": "purpose"},
                {"number": "2", "lines": ["使う場所を", "想定する"], "icon": "location"},
                {"number": "3", "lines": ["手放せない基準を", "1つ決める"], "icon": "scale"},
            ],
            "svg_footer": "紹介アイテムは楽天ROOMに掲載しています。",
        },
        "pinterest_topic_candidates": ["周辺機器", "ガジェット選び", "在宅ワーク"],
        "checklist": [
            "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
            "価格・在庫・性能・ランキング・成果を断定していないか確認した",
            "画像内の文字が読みやすいか（誤字・はみ出しがないか）確認した",
            "altテキストが画像の内容を正しく説明しているか確認した",
            "楽天ROOMリンク欄が空欄のままであることを確認した（社長が手動で貼り付ける）",
            "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
        ],
        "png_relative_path": "images/publish-queue-peripherals-2x3.png",
        "png_download_filename": "pinterest-publish-queue-peripherals.png",
    },
    {
        # MISSION 042: スマホ・タブレットでAIにメール/メモの下書きを頼む
        # 初心者向け。前日公開済みの折りたたみキーボードの楽天ROOM投稿と、
        # 社長が手動で結び付けられる状態にする(このアプリからは投稿URLを
        # 取得・保存・自動連携しない)。
        "id": "smartphone-ai-draft-3points",
        "status": "published",
        "pin": {
            "title": "スマホでAIに下書きを頼む前に確認する3つ",
            "description": (
                "スマホやタブレットでAIにメールやメモの下書きを頼む前に、確認して"
                "おくと入力がスムーズになる3つのポイントをまとめました。使う端末・"
                "文字入力の方法・読み返す場所を先に決めておくだけで、指示や確認が"
                "しやすくなります。特定の商品の紹介やレビューではありません。"
            ),
            # MISSION 042: 実写真は支給されていないため、note-hero-imageと
            # 同じ手法(グラデーション+図形の重ね合わせ)で描いたイラスト調の
            # 擬似写真ビジュアル。ロゴ・読める商品名・実在サービスの画面・
            # 楽天市場の商品画像は写っていない。タイトルと3項目は画像本体に
            # 焼き込み済み。
            "alt_text": (
                "スマホでAIに下書きを頼む前に確認する3つ、というテーマのイメージ"
                "ビジュアル。木目のデスクにスマートフォン・タブレット・折りたたみ"
                "キーボードが置かれた様子。上部に「1. 使う端末を決める」「2. 文字"
                "入力の方法を決める」「3. 読み返す場所を決める」の3項目とタイトルを"
                "焼き込んでいる。ロゴ・読める商品名・実在サービスの画面・楽天市場の"
                "商品画像は写っていません。"
            ),
        },
        "hero_image_relative_path": "images/publish-queue-smartphone-ai-draft-2x3.png",
        "hero_image_download_filename": "pinterest-publish-queue-smartphone-ai-draft.png",
        "hero_title_lines": ["スマホでAIに下書きを", "頼む前に確認する3つ"],
        "hero_item_lines": [
            "1. 使う端末を決める",
            "2. 文字入力の方法を決める",
            "3. 読み返す場所を決める",
        ],
        # MISSION 042: 楽天ROOMリンク欄は空欄のまま、公開済みの折りたたみ
        # キーボード投稿URLを社長が手動で貼る想定であることを明記する
        # (このアプリはURLの取得・保存・自動連携を一切行わない)。
        "custom_room_link_note": (
            "楽天ROOMリンク：（空欄）公開済みの折りたたみキーボード投稿URLを、"
            "社長が手動で貼り付けてください。URLの取得・保存・外部連携は、この"
            "画面では一切行いません。"
        ),
        "pinterest_topic_candidates": ["AI活用術", "スマホ活用", "在宅ワーク"],
        "checklist": [
            "タイトル・説明文に「自分で使った」「おすすめ」「効率が上がる」"
            "「成果が出る」等の断定表現がないか確認した",
            "価格・在庫・性能・ランキング・レビュー・成果を記載していないか確認した",
            "画像内の文字（タイトル・3項目）が読みやすいか（誤字・はみ出しがないか）"
            "確認した",
            "altテキストが画像の内容を正しく説明しているか確認した",
            "楽天ROOMリンク欄が空欄のままであることを確認した（社長が公開済みの"
            "折りたたみキーボード投稿URLを手動で貼り付ける）",
            "この画像がAIで加工（タイトル・3項目の文字焼き込み）した画像であり、"
            "Pinterest側で必要な「AIで修正済み」等の画像ラベル設定が必要である"
            "ことを確認した",
            "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
        ],
    },
    {
        # MISSION 049: 「AIに聞いても『なんか違う』と感じる人へ」note記事下書きと
        # 対応するPinterest投稿。楽天ROOMの商品紹介は行わないため、リンク欄は
        # 汎用の空欄注記(PUBLISH_QUEUE_ROOM_LINK_NOTE)のままにする。
        # MISSION 054: 2026年9月12日までに柴犬社長が手動でPinterestへ投稿済み。
        # リンク先も、実際に公開されたnote記事(NOTE_THIRD_ARTICLE)のURLへ
        # 更新した(email-draft-3pointsと同じ扱い)。
        "id": "ai-mismatch-3points",
        "status": "published",
        "pinterest_link_url": "https://note.com/legal_crow9879/n/nb2a21a842387",
        "pin": {
            "title": "AIが「なんか違う」ときに見直す3つ",
            "description": (
                "AIに聞いても「なんか違う」と感じたときに見直したい3つのポイントを"
                "まとめました。目的を先に伝える・前提や条件を足す・一度で終わらせず"
                "聞き返す、を先に意識しておくだけで、やり取りがスムーズになることが"
                "あります。特定の商品の紹介やレビューではありません。"
            ),
            # MISSION 049.2: 画像を図形中心のイラストから、支給された写真風
            # ビジュアル(スマホとメモ帳・書き直しを感じる手元)へ差し替えた。
            # 焼き込む文字もタイトルのみに変更した(3項目は焼き込まない)ため、
            # altテキストを実際の画像内容に合わせて更新した。
            "alt_text": (
                "AIが「なんか違う」ときに見直す3つ、というテーマのイメージビジュアル。"
                "明るい昼間の室内で、スマートフォンを片手に持ちながら、もう片方の手で"
                "ノートに書き直している様子。上部の明るい余白にタイトルを焼き込んで"
                "いる。ロゴ・読める商品名・実在サービスの画面・人物の顔は写っていません。"
            ),
        },
        "hero_image_relative_path": "images/publish-queue-ai-mismatch-2x3.png",
        "hero_image_download_filename": "pinterest-publish-queue-ai-mismatch.png",
        "hero_title_lines": ["AIが「なんか違う」ときに", "見直す3つ"],
        "hero_item_lines": [
            "1. 目的を先に伝える",
            "2. 前提や条件を足す",
            "3. 一度で終わらせず聞き返す",
        ],
        "pinterest_topic_candidates": ["AI活用術", "AIとの対話術", "仕事効率化"],
        "checklist": [
            "タイトル・説明文に「自分で使った」「おすすめ」「効率が上がる」"
            "「成果が出る」等の断定表現がないか確認した",
            "価格・在庫・性能・ランキング・レビュー・成果を記載していないか確認した",
            "画像内の文字（タイトル・3項目）が読みやすいか（誤字・はみ出しがないか）"
            "確認した",
            "altテキストが画像の内容を正しく説明しているか確認した",
            "リンク先のnote記事が正しく公開されているか確認した",
            "この画像がAIで生成・加工した画像であり、Pinterest側で必要な「AIで"
            "修正済み」等の画像ラベル設定が必要であることを確認した",
            "Pinterestアカウントにログインした状態で、手動で投稿できる準備ができている",
        ],
    },
]

PUBLISH_QUEUE_ROOM_LINK_NOTE = (
    "楽天ROOMリンク：（空欄）社長がPinterestへ投稿する際に手動で貼り付けてください。"
    "URLの取得・保存・外部連携は、この画面では一切行いません。"
)
PUBLISH_QUEUE_MANUAL_POST_NOTE = (
    "公開は社長がPinterestで手動実行します。Pinterest・楽天ROOM・noteへの"
    "自動投稿・予約投稿・外部通信は一切行いません。"
)

# SVGアイコン(装飾のみ・画面内完結・外部素材なし・商品写真やロゴは使わない)。
# 「AIでメールの下書き」投稿分は初回手動投稿パッケージと同じ3種類の
# アイコン(mail/summary/idea)を再利用し、それ以外の6種類はこのミッション用に
# 新規追加する。
_PUBLISH_QUEUE_ICONS = dict(_FIRST_POST_ICONS)
_PUBLISH_QUEUE_ICONS.update({
    "bundle": (
        '<line x1="-20" y1="-16" x2="-20" y2="16" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="0" y1="-20" x2="0" y2="20" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="20" y1="-16" x2="20" y2="16" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<rect x="-26" y="-6" width="52" height="12" rx="6" fill="none" stroke="#38bdf8" stroke-width="3"/>'
    ),
    "route": (
        '<path d="M-26 -20 L-26 6 L0 6 L0 20 L26 20" fill="none" stroke="#38bdf8" stroke-width="3" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "outlet": (
        '<rect x="-22" y="-24" width="44" height="48" rx="8" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<circle cx="-8" cy="0" r="4" fill="#38bdf8"/>'
        '<circle cx="8" cy="0" r="4" fill="#38bdf8"/>'
    ),
    "purpose": (
        '<circle cx="0" cy="0" r="22" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<path d="M-10 0 L-2 10 L14 -10" fill="none" stroke="#38bdf8" stroke-width="3" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "location": (
        '<circle cx="0" cy="-8" r="14" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<path d="M-10 2 L0 24 L10 2 Z" fill="none" stroke="#38bdf8" stroke-width="3" stroke-linejoin="round"/>'
    ),
    "scale": (
        '<line x1="-22" y1="0" x2="22" y2="0" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>'
        '<circle cx="-22" cy="0" r="8" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        '<circle cx="22" cy="0" r="8" fill="none" stroke="#38bdf8" stroke-width="3"/>'
    ),
})


def _render_publish_queue_pin_svg(pin):
  """Pinterest用の縦長2:3(1000x1500)ローカルSVG画像を組み立てる(投稿キュー共通)。

  外部画像・外部フォント・外部素材、楽天市場の商品画像・商品写真・商品ロゴは
  一切使わず、すべて画面内SVGの図形とテキストだけで構成する。商品名・価格・
  在庫・性能・ランキング・成果予測は一切含めない。
  """
  headline_start_y = 130
  headline_line_h = 66
  headline_lines = "".join(
      f'<tspan x="500" dy="{0 if i == 0 else headline_line_h}">{line}</tspan>'
      for i, line in enumerate(pin["svg_headline"])
  )
  subtitle_y = headline_start_y + headline_line_h * (len(pin["svg_headline"]) - 1) + 90

  item_blocks = []
  card_height = 280
  gap = 36
  start_y = 460
  for index, item in enumerate(pin["svg_items"]):
    card_y = start_y + index * (card_height + gap)
    icon_shape = _PUBLISH_QUEUE_ICONS[item["icon"]]
    label_lines = "".join(
        f'<tspan x="220" dy="{0 if i == 0 else 46}">{line}</tspan>'
        for i, line in enumerate(item["lines"])
    )
    item_blocks.append(
        f'<g transform="translate(0,{card_y})">'
        '<rect x="60" y="0" width="880" height="' + str(card_height) + '" rx="28" '
        'fill="#101a30" stroke="#293958" stroke-width="2"/>'
        '<circle cx="150" cy="' + str(card_height // 2) + '" r="46" fill="#0b2540" '
        'stroke="#38bdf8" stroke-width="3"/>'
        '<text x="150" y="' + str(card_height // 2 + 16) + '" text-anchor="middle" '
        f'font-size="44" font-weight="700" fill="#38bdf8">{item["number"]}</text>'
        f'<g transform="translate(80,{card_height // 2})">{icon_shape}</g>'
        f'<text x="220" y="{card_height // 2 - 20}" font-size="40" font-weight="700" '
        f'fill="#f1f5f9">{label_lines}</text>'
        '</g>'
    )
  return (
      '<svg viewBox="0 0 1000 1500" xmlns="http://www.w3.org/2000/svg" '
      'role="img" aria-labelledby="pq-svg-title pq-svg-desc">'
      f'<title id="pq-svg-title">{pin["title"]}</title>'
      f'<desc id="pq-svg-desc">{pin["alt_text"]}</desc>'
      '<defs><linearGradient id="pqBg" x1="0" y1="0" x2="0" y2="1">'
      '<stop offset="0%" stop-color="#0b1220"/><stop offset="100%" stop-color="#1b2c4a"/>'
      '</linearGradient></defs>'
      '<rect width="1000" height="1500" fill="url(#pqBg)"/>'
      f'<text x="500" y="{headline_start_y}" text-anchor="middle" font-size="56" font-weight="800" '
      f'fill="#f1f5f9">{headline_lines}</text>'
      f'<text x="500" y="{subtitle_y}" text-anchor="middle" font-size="30" font-weight="600" '
      f'fill="#38bdf8">{pin["svg_subtitle"]}</text>'
      + "".join(item_blocks) +
      '<text x="500" y="1440" text-anchor="middle" font-size="26" fill="#a3b2c6">'
      f'{pin["svg_footer"]}</text>'
      '</svg>'
  )


def _draw_publish_queue_icon(draw, cx, cy, kind, color):
  """PNG版アイコン(装飾のみ)を描画する。SVG版と同じ図形。

  「mail」「summary」「idea」は初回手動投稿パッケージのPNG描画関数を
  そのまま再利用する。
  """
  if kind in ("mail", "summary", "idea"):
    _draw_first_post_icon(draw, cx, cy, kind, color)
    return
  if kind == "bundle":
    draw.line([(cx - 20, cy - 16), (cx - 20, cy + 16)], fill=color, width=3)
    draw.line([(cx, cy - 20), (cx, cy + 20)], fill=color, width=3)
    draw.line([(cx + 20, cy - 16), (cx + 20, cy + 16)], fill=color, width=3)
    draw.rounded_rectangle([cx - 26, cy - 6, cx + 26, cy + 6], radius=6, outline=color, width=3)
  elif kind == "route":
    draw.line(
        [(cx - 26, cy - 20), (cx - 26, cy + 6), (cx, cy + 6), (cx, cy + 20), (cx + 26, cy + 20)],
        fill=color, width=3, joint="curve",
    )
  elif kind == "outlet":
    draw.rounded_rectangle([cx - 22, cy - 24, cx + 22, cy + 24], radius=8, outline=color, width=3)
    draw.ellipse([cx - 12, cy - 4, cx - 4, cy + 4], fill=color)
    draw.ellipse([cx + 4, cy - 4, cx + 12, cy + 4], fill=color)
  elif kind == "purpose":
    draw.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=color, width=3)
    draw.line([(cx - 10, cy), (cx - 2, cy + 10), (cx + 14, cy - 10)], fill=color, width=3, joint="curve")
  elif kind == "location":
    draw.ellipse([cx - 14, cy - 22, cx + 14, cy + 6], outline=color, width=3)
    draw.polygon([(cx - 10, cy + 10), (cx, cy + 32), (cx + 10, cy + 10)], outline=color, width=3)
  elif kind == "scale":
    draw.line([(cx - 22, cy), (cx + 22, cy)], fill=color, width=3)
    draw.ellipse([cx - 30, cy - 8, cx - 14, cy + 8], outline=color, width=3)
    draw.ellipse([cx + 14, cy - 8, cx + 30, cy + 8], outline=color, width=3)


def generate_publish_queue_pin_png(pin, out_path):
  """投稿キュー用PNG(1000x1500)を生成し、ファイルへ保存する(開発時専用)。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。テーマや
  文言(PUBLISH_QUEUE_POSTS)を差し替えた場合、この関数を手動で再実行して
  PNGを作り直すこと。実行にはPillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; \\
          [o.generate_publish_queue_pin_png(p['pin'], o.os.path.join(\\
              o.os.path.dirname(o.os.path.abspath(o.__file__)), 'static', p['png_relative_path']\\
          )) for p in o.PUBLISH_QUEUE_POSTS]"
  """
  from PIL import Image, ImageDraw, ImageFont  # 遅延import(開発時専用)

  width, height = 1000, 1500
  bg_top, bg_bottom = (11, 18, 32), (27, 44, 74)
  white, blue, sub = (241, 245, 249), (56, 189, 248), (163, 178, 198)
  card_bg, card_edge, badge_bg = (16, 26, 48), (41, 57, 88), (11, 37, 64)

  img = Image.new("RGB", (width, height), bg_top)
  draw = ImageDraw.Draw(img)
  for y in range(height):
    t = y / (height - 1)
    draw.line(
        [(0, y), (width, y)],
        fill=tuple(int(bg_top[i] + (bg_bottom[i] - bg_top[i]) * t) for i in range(3)),
    )

  font_path = "/System/Library/Fonts/Hiragino Sans GB.ttc"
  headline_font = ImageFont.truetype(font_path, 56)
  subtitle_font = ImageFont.truetype(font_path, 30)
  number_font = ImageFont.truetype(font_path, 42)
  label_font = ImageFont.truetype(font_path, 38)
  footer_font = ImageFont.truetype(font_path, 26)

  cx = width // 2
  headline_start_y = 130
  headline_line_h = 66
  y = headline_start_y
  for line in pin["svg_headline"]:
    draw.text((cx, y), line, font=headline_font, fill=white, anchor="ma")
    y += headline_line_h
  subtitle_y = headline_start_y + headline_line_h * (len(pin["svg_headline"]) - 1) + 90
  draw.text((cx, subtitle_y), pin["svg_subtitle"], font=subtitle_font, fill=blue, anchor="ma")

  card_h, gap, start_y = 280, 36, 460
  for index, item in enumerate(pin["svg_items"]):
    card_y = start_y + index * (card_h + gap)
    draw.rounded_rectangle(
        [60, card_y, 940, card_y + card_h], radius=28,
        fill=card_bg, outline=card_edge, width=2,
    )
    badge_cy = card_y + card_h // 2
    draw.ellipse(
        [150 - 46, badge_cy - 46, 150 + 46, badge_cy + 46],
        fill=badge_bg, outline=blue, width=3,
    )
    draw.text((150, badge_cy), item["number"], font=number_font, fill=blue, anchor="mm")
    _draw_publish_queue_icon(draw, 260, badge_cy, item["icon"], blue)
    ly = badge_cy - 26
    for line in item["lines"]:
      draw.text((320, ly), line, font=label_font, fill=white, anchor="lm")
      ly += 46

  draw.text((cx, 1440), pin["svg_footer"], font=footer_font, fill=sub, anchor="mm")

  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


# MISSION 039.2: 「AIにメールの下書きを頼む前に決める3つ」投稿用PNGに、
# タイトル文字を確実に焼き込む。
#
# MISSION 039では見出し文字をHTML側(.note-hero-overlay)で重ねるだけ
# だったため、「Pinterest用PNGを保存」でダウンロードした画像そのものには
# 文字が入っておらず、Pinterestへそのままアップロードできる状態ではな
# かった。この関数は、既存の高品質背景写真(publish-queue-email-draft-
# v2.png)をベースに、タイトルを白・太字で左上の暗い余白へ直接描画した
# 新しいPNG(publish-queue-email-draft-v3.png)を生成する。v2.pngと旧
# publish-queue-email-draft-2x3.pngはどちらも削除・上書きしない。
PUBLISH_QUEUE_EMAIL_DRAFT_V2_RELATIVE_PATH = "images/publish-queue-email-draft-v2.png"
PUBLISH_QUEUE_EMAIL_DRAFT_V3_RELATIVE_PATH = "images/publish-queue-email-draft-v3.png"
_PUBLISH_QUEUE_EMAIL_DRAFT_FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

# MISSION 042: 「スマホでAIに下書きを頼む前に確認する3つ」投稿用の縦長
# (1024x1536, 2:3)画像。
# MISSION 042.1: 社長から高品質な写真風ビジュアル(publish-queue-
# smartphone-ai-photo-base.png、夜の木目デスクにスマホ・タブレット・
# 折りたたみキーボードが自然に置かれた構図)の支給を受け、MISSION 042
# 時点のPillow製イラスト(グラデーション+単純な図形描画)からこちらへ
# 差し替えた。タイトルと画像内の3項目は、支給された元写真の上に直接
# 焼き込む(HTML側では重ねない)。元写真にはロゴ・読める商品名・実在
# サービスの画面・楽天市場の商品画像・人物は写っていないことを目視確認
# 済み。元写真ファイル自体は削除・上書きしない。
PUBLISH_QUEUE_SMARTPHONE_AI_PHOTO_BASE_RELATIVE_PATH = (
    "images/publish-queue-smartphone-ai-photo-base.png"
)
PUBLISH_QUEUE_SMARTPHONE_AI_DRAFT_RELATIVE_PATH = (
    "images/publish-queue-smartphone-ai-draft-2x3.png"
)

# MISSION 049: 「AIが『なんか違う』ときに見直す3つ」投稿用の縦長
# (1024x1536, 2:3)画像。
# MISSION 049.2: 図形中心のPillowイラストは一覧で目を引かないとの指摘を
# 受け、社長支給の高品質な写真風ビジュアル(publish-queue-ai-mismatch-
# photo-base.png。明るい昼間の室内で、スマホとメモ帳・書き直しを感じる
# 手元が主役。ロゴ・読める商品名・実在サービスの画面・人物の顔は写って
# いないことを目視確認済み)を土台に切り替えた。タイトル(2行)のみを画像
# 上部の明るい余白へ直接焼き込む(HTML側では重ねない。MISSION 049時点とは
# 異なり、画像内の3項目は焼き込まない)。noteの見出し画像(スマホの画面を
# 見直す手元)とは構図を変えている。元写真ファイル自体は削除・上書きしない。
PUBLISH_QUEUE_AI_MISMATCH_PHOTO_BASE_RELATIVE_PATH = (
    "images/publish-queue-ai-mismatch-photo-base.png"
)
PUBLISH_QUEUE_AI_MISMATCH_RELATIVE_PATH = "images/publish-queue-ai-mismatch-2x3.png"


def generate_publish_queue_email_draft_v3_png(out_path=None):
  """v2.pngにタイトル文字を焼き込んだv3.pngを生成し、ファイルへ保存する

  (開発時専用)。Flaskアプリの起動・リクエスト処理からは一切呼び出さない。
  タイトルの行分け(PUBLISH_QUEUE_POSTSの"email-draft-3points"エントリの
  hero_title_lines)を差し替えた場合、この関数を手動で再実行してPNGを
  作り直すこと。実行にはPillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; o.generate_publish_queue_email_draft_v3_png()"
  """
  from PIL import Image, ImageDraw, ImageFont  # 遅延import(開発時専用)

  base_path = os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      PUBLISH_QUEUE_EMAIL_DRAFT_V2_RELATIVE_PATH,
  )
  img = Image.open(base_path).convert("RGB")
  draw = ImageDraw.Draw(img)

  post = next(
      p for p in PUBLISH_QUEUE_POSTS if p["id"] == "email-draft-3points"
  )
  lines = post["hero_title_lines"]

  font = ImageFont.truetype(_PUBLISH_QUEUE_EMAIL_DRAFT_FONT_PATH, 60)
  x, y = 56, 92
  line_h = 78
  shadow_color = (0, 0, 0)
  white = (255, 255, 255)
  for line in lines:
    # 太字フォントを別途用意していないため、同じ文字を1px刻みでずらして
    # 複数回描画する疑似ボールド。加えて影を描き、暗い背景写真の上でも
    # 確実なコントラストを確保する。
    for dx, dy in ((3, 3), (-2, 2), (2, -2), (-2, -2), (2, 2)):
      draw.text((x + dx, y + dy), line, font=font, fill=shadow_color)
    for dx in (0, 1):
      for dy in (0, 1):
        draw.text((x + dx, y + dy), line, font=font, fill=white)
    y += line_h

  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      PUBLISH_QUEUE_EMAIL_DRAFT_V3_RELATIVE_PATH,
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def generate_publish_queue_smartphone_ai_draft_png(out_path=None):
  """「スマホでAIに下書きを頼む前に確認する3つ」投稿用の縦長画像

  (1024x1536, 2:3)を生成し、ファイルへ保存する(開発時専用)。

  MISSION 042.1: 社長から支給された高品質な写真風ビジュアル(元写真、
  PUBLISH_QUEUE_SMARTPHONE_AI_PHOTO_BASE_RELATIVE_PATH。夜の木目デスクに
  スマホ・タブレット・折りたたみキーボードが自然に置かれた構図。ロゴ・
  読める商品名・実在サービスの画面・楽天市場の商品画像・人物は写って
  いないことを目視確認済み)を土台に、タイトル(2行)と画像内の3項目を
  この画像自体へ直接焼き込む(HTML側では重ねない)。元写真の左上には
  もともと夜空の暗い領域があるため、そこに白抜き文字を配置し、念のため
  薄い暗色のスクリム(グラデーション)を重ねて、写真の内容によらず文字が
  確実に読める状態にする。元写真ファイル自体は削除・上書きしない。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。文言を
  差し替えたい場合、この関数を手動で再実行してPNGを作り直すこと。実行には
  Pillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; o.generate_publish_queue_smartphone_ai_draft_png()"
  """
  from PIL import Image, ImageDraw, ImageFont  # 遅延import(開発時専用)

  base_path = os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      PUBLISH_QUEUE_SMARTPHONE_AI_PHOTO_BASE_RELATIVE_PATH,
  )
  img = Image.open(base_path).convert("RGB")
  width, height = img.size

  # 元写真の左上(夜空の暗い領域)に、念のため薄い暗色スクリムを重ねて
  # 可読性を確実にする(元写真の明るさに文字の可読性を左右されないため)。
  scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  scrim_draw = ImageDraw.Draw(scrim)
  scrim_bottom = 540
  for y in range(scrim_bottom):
    t = y / scrim_bottom
    alpha = int(120 * (1 - t))
    scrim_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
  img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

  draw = ImageDraw.Draw(img)

  # タイトル(2行・大)+ 画像内の3項目(小)を、元写真の左上(夜空の暗い
  # 領域)へ焼き込む。太字フォントを別途用意していないため、疑似ボールド
  # (数px刻みでずらして複数回描画)+影で、写真の上でも確実なコントラスト
  # を確保する(既存のgenerate_publish_queue_email_draft_v3_pngと同じ手法)。
  title_font = ImageFont.truetype(_PUBLISH_QUEUE_EMAIL_DRAFT_FONT_PATH, 66)
  item_font = ImageFont.truetype(_PUBLISH_QUEUE_EMAIL_DRAFT_FONT_PATH, 42)
  shadow_color = (0, 0, 0)
  white = (255, 255, 255)

  def _draw_baked_text(text, xy, font):
    x, y = xy
    for dx, dy in ((3, 3), (-2, 2), (2, -2), (-2, -2), (2, 2)):
      draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)
    for dx in (0, 1):
      for dy in (0, 1):
        draw.text((x + dx, y + dy), text, font=font, fill=white)

  title_lines = ["スマホでAIに下書きを", "頼む前に確認する3つ"]
  x, y = 56, 60
  for line in title_lines:
    _draw_baked_text(line, (x, y), title_font)
    y += 84

  y += 30
  item_lines = ["1. 使う端末を決める", "2. 文字入力の方法を決める", "3. 読み返す場所を決める"]
  for line in item_lines:
    _draw_baked_text(line, (x, y), item_font)
    y += 62

  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      PUBLISH_QUEUE_SMARTPHONE_AI_DRAFT_RELATIVE_PATH,
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def generate_publish_queue_ai_mismatch_png(out_path=None):
  """「AIが『なんか違う』ときに見直す3つ」投稿用の縦長画像

  (1024x1536, 2:3)を生成し、ファイルへ保存する(開発時専用)。

  MISSION 049.2: 図形中心のPillowイラストは一覧で目を引かないとの指摘を
  受け、社長から支給された高品質な写真風ビジュアル(元写真、
  PUBLISH_QUEUE_AI_MISMATCH_PHOTO_BASE_RELATIVE_PATH。明るい昼間の室内で、
  スマホとメモ帳・書き直しを感じる手元が主役の構図。ロゴ・読める商品名・
  実在サービスの画面・人物の顔は写っていないことを目視確認済み)を土台に、
  タイトル(2行)だけをこの画像自体へ直接焼き込む(HTML側では重ねない。
  MISSION 049時点とは異なり、画像内の3項目は焼き込まない)。元写真の上部
  には明るい空・窓の余白があるため、そこに半透明の白いスクリム帯を敷き、
  文字は白い縁取り+濃紺の塗り(疑似太字+アウトライン)で、背景の明るさに
  左右されず確実に読める状態にする。元写真ファイル自体は削除・上書きしない。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。文言を
  差し替えたい場合、この関数を手動で再実行してPNGを作り直すこと。実行には
  Pillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; o.generate_publish_queue_ai_mismatch_png()"
  """
  from PIL import Image, ImageDraw, ImageFont  # 遅延import(開発時専用)

  base_path = os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      PUBLISH_QUEUE_AI_MISMATCH_PHOTO_BASE_RELATIVE_PATH,
  )
  img = Image.open(base_path).convert("RGB")
  width, height = img.size

  # 元写真の上部(明るい空・窓の余白)に、念のため半透明の白いスクリム帯を
  # 敷いて可読性を確実にする(元写真の明るさに文字の可読性を左右されない
  # ため)。
  scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  scrim_draw = ImageDraw.Draw(scrim)
  scrim_draw.rounded_rectangle([28, 28, width - 28, 300], radius=28, fill=(255, 255, 255, 150))
  img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
  draw = ImageDraw.Draw(img)

  # タイトル(2行・大)を、元写真上部の明るい余白へ焼き込む。太字フォントを
  # 別途用意していないため、疑似太字(白い縁取りを複数方向にずらして描画)+
  # 濃紺の塗りで、写真の上でも確実なコントラストを確保する。
  title_font = ImageFont.truetype(_PUBLISH_QUEUE_EMAIL_DRAFT_FONT_PATH, 66)
  ink = (17, 24, 39)
  white = (255, 255, 255)

  def _draw_baked_text(text, xy, font):
    x, y = xy
    for dx, dy in ((2, 2), (-2, 2), (2, -2), (-2, -2), (0, 2), (0, -2), (2, 0), (-2, 0)):
      draw.text((x + dx, y + dy), text, font=font, fill=white)
    draw.text((x, y), text, font=font, fill=ink)

  title_lines = ["AIが「なんか違う」ときに", "見直す3つ"]
  x, y = 56, 78
  for line in title_lines:
    _draw_baked_text(line, (x, y), title_font)
    y += 84

  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      PUBLISH_QUEUE_AI_MISMATCH_RELATIVE_PATH,
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def _render_publish_queue_scene(posts, room_link_note, manual_post_note, status_labels):
  """Pinterest向け・手動承認つき投稿キューのHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・楽天API・外部
  通信への アクセスは一切行わない。楽天ROOMリンク欄は常に空欄で表示し、
  URLの取得・保存・外部連携は行わない。コピー用ボタンはクライアント側JS
  のみで完結し、クリップボード操作が失敗しても例外を伝播させず、安全な
  フォールバック表示にする。

  MISSION 054: statusは自由文字列ではなく状態キー("published"/
  "awaiting_president")になったため、status_labels(PUBLISH_QUEUE_STATUS_
  LABELS)で日本語ラベルへ変換し、状態ごとに異なる配色のバッジ
  (pq-status-badge status-{key})で表示する。
  """
  post_cards = []
  for post in posts:
    pin = post["pin"]
    post_id = post["id"]
    topic_chips = "".join(
        f'<li>{topic}</li>' for topic in post["pinterest_topic_candidates"]
    )
    checklist_items = "".join(
        f'<li><input type="checkbox" id="pq-check-{post_id}-{i}">'
        f'<label for="pq-check-{post_id}-{i}">{item}</label></li>'
        for i, item in enumerate(post["checklist"])
    )

    if "hero_image_relative_path" in post:
      # MISSION 039.2: ダウンロードしたPNGにタイトル文字が入っていない問題を
      # 修正するため、見出し文字をHTML側で重ねる方式(MISSION 039時点)から、
      # あらかじめ画像本体にタイトルを焼き込む方式(generate_publish_queue_
      # email_draft_v3_png)へ切り替えた。そのため、画面上でもHTML側の見出し
      # 重ね表示(.note-hero-overlay等)は行わない(保存画像と画面表示の二重
      # 表示を避けるため)。<img>のalt属性には、画像内にタイトル文字が写って
      # いることを含めて説明する。
      image_block = (
          f'<div class="note-hero"><img class="note-hero-img" '
          f'src="/static/{post["hero_image_relative_path"]}" alt="{pin["alt_text"]}"></div>'
          '<p class="fp-svg-ratio">縦長 2:3（高精細画像。タイトル文字を画像本体に焼き込み'
          '済みです。ロゴ・実在サービスの画面は写っていません）</p>'
          # MISSION 039: 通常のダウンロードリンク(<a href download>)のみで
          # 保存する。外部通信・JavaScript必須の処理は行わない。あらかじめ
          # 用意したローカル画像ファイル(static/配下)を指すだけであり、
          # クリックしてもPinterestへの投稿・送信・連携は一切発生しない。
          f'<a class="fp-png-download" href="/static/{post["hero_image_relative_path"]}" '
          f'download="{post["hero_image_download_filename"]}">Pinterest用PNGを保存</a>'
          '<p class="fp-png-hint">保存した画像をPinterestで手動アップロードしてください。'
          'このボタンからの投稿・送信・連携は行われません。</p>'
      )
    else:
      svg_markup = _render_publish_queue_pin_svg(pin)
      image_block = (
          f'<div class="fp-svg-wrap">{svg_markup}</div>'
          '<p class="fp-svg-ratio">縦長 2:3（画面内SVG・外部画像なし、商品写真・楽天市場画像・'
          '商品ロゴは使用していません）</p>'
          # MISSION 036: 通常のダウンロードリンク(<a href download>)のみで
          # 保存する。外部通信・JavaScript必須の処理は行わない。あらかじめ
          # 生成済みのローカルPNGファイル(static/配下)を指すだけであり、
          # クリックしてもPinterest・楽天ROOMへの投稿・送信・連携は一切発生しない。
          f'<a class="fp-png-download" href="/static/{post["png_relative_path"]}" '
          f'download="{post["png_download_filename"]}">Pinterest用PNGを保存</a>'
          '<p class="fp-png-hint">保存したPNGをPinterestで手動アップロードしてください。'
          'このボタンからの投稿・送信・連携は行われません。</p>'
      )

    fields_html = (
        '<div class="fp-field"><div class="fp-field-head"><h4>タイトル</h4>'
        f'<button type="button" class="fp-copy-btn" data-copy-target="pq-title-{post_id}">'
        'コピー</button></div>'
        f'<p id="pq-title-{post_id}">{pin["title"]}</p></div>'
        '<div class="fp-field"><div class="fp-field-head"><h4>説明文</h4>'
        f'<button type="button" class="fp-copy-btn" data-copy-target="pq-description-{post_id}">'
        'コピー</button></div>'
        f'<p id="pq-description-{post_id}">{pin["description"]}</p></div>'
        '<div class="fp-field"><div class="fp-field-head"><h4>altテキスト</h4>'
        f'<button type="button" class="fp-copy-btn" data-copy-target="pq-alt-{post_id}">'
        'コピー</button></div>'
        f'<p id="pq-alt-{post_id}">{pin["alt_text"]}</p></div>'
    )
    if "pinterest_link_url" in post:
      link_url = post["pinterest_link_url"]
      # MISSION 039: リンク先はコピー用テキストとして表示するとともに、
      # 社長が手動で内容を確認できるよう、通常のリンク(新規タブで開く・
      # noopener/noreferrer)としても提供する。クリックはブラウザを操作する
      # 人間の手動操作であり、このアプリ自身が外部へアクセス・取得・送信
      # することはない。
      fields_html += (
          '<div class="fp-field"><div class="fp-field-head"><h4>リンク先</h4>'
          f'<button type="button" class="fp-copy-btn" data-copy-target="pq-link-{post_id}">'
          'コピー</button></div>'
          f'<p id="pq-link-{post_id}">'
          f'<a href="{link_url}" target="_blank" rel="noopener noreferrer">{link_url}</a>'
          '</p></div>'
      )
    fields_html = f'<div class="fp-fields">{fields_html}</div>'

    if "pinterest_link_url" in post:
      # MISSION 039: このカードはPinterestのリンク先が確定しているため、
      # 「楽天ROOMリンク欄は空欄」という汎用の注記は表示しない(空欄では
      # なくなったため)。
      link_or_room_note_html = ""
    elif "custom_room_link_note" in post:
      # MISSION 042: このカードは、既存の別投稿(折りたたみキーボード)の
      # 楽天ROOM投稿URLと手動で結び付けられる想定のため、汎用の空欄注記
      # ではなく、どのURLを貼るべきかを明記した専用の文言を表示する。
      link_or_room_note_html = f'<div class="pq-room-link">{post["custom_room_link_note"]}</div>'
    else:
      link_or_room_note_html = f'<div class="pq-room-link">{room_link_note}</div>'

    if "hero_image_relative_path" in post:
      # MISSION 039: ヒーロー画像はnote初回記事と同じ横幅いっぱいのレイアウト
      # で表示する(他2件のSVGプレビュー用280px固定カラムでは、重ねる見出し
      # 文字が窮屈になり折り返し崩れの原因になるため)。フィールド類は画像の
      # 下に縦に並べる。
      media_and_fields_html = f'{image_block}{fields_html}'
    else:
      media_and_fields_html = (
          '<div class="fp-pin-layout">'
          f'<div>{image_block}</div>'
          f'{fields_html}'
          '</div>'
      )

    post_cards.append(
        '<div class="pq-card">'
        '<div class="pq-card-head">'
        f'<h3>{pin["title"]}</h3>'
        f'<span class="pq-status-badge status-{post["status"]}">'
        f'{status_labels[post["status"]]}</span>'
        '</div>'
        f'{media_and_fields_html}'
        '<p class="pq-topics-label">Pinterestのトピック候補</p>'
        f'<ul class="pq-topics">{topic_chips}</ul>'
        f'{link_or_room_note_html}'
        f'<div class="pq-manual-note"><b>公開について。</b>{manual_post_note}</div>'
        '<h4 class="fp-section-title">投稿前チェックリスト</h4>'
        f'<ul class="fp-checklist">{checklist_items}</ul>'
        '</div>'
    )
  return (
      '<section class="publish-queue-board" aria-label="投稿キュー">'
      '<div class="fp-notice"><b>社内向けの投稿キューです。</b>'
      'SNSへの投稿・送信・連携は一切行われません。柴犬社長が内容を確認し、'
      '手動でPinterestへ投稿するための準備画面です。</div>'
      + "".join(post_cards) +
      # MISSION 036: コピー操作はクライアント側JSのみで完結し、外部通信は
      # 行わない。navigator.clipboardが使えない/失敗する環境でも、例外を
      # 投げずに安全な文言へフォールバックする(既存の投稿パッケージ画面と同じ方式)。
      '<script>document.querySelectorAll(".fp-copy-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'const el=document.getElementById(btn.dataset.copyTarget);'
      'if(!el)return;'
      'const original=btn.textContent;'
      'const showResult=ok=>{btn.textContent=ok?"コピーしました":"コピーできませんでした";'
      'setTimeout(()=>{btn.textContent=original;},1800);};'
      'try{'
      'if(navigator.clipboard&&navigator.clipboard.writeText){'
      'navigator.clipboard.writeText(el.textContent).then(()=>showResult(true))'
      '.catch(()=>showResult(false));'
      '}else{showResult(false);}'
      '}catch(e){showResult(false);}'
      '});'
      '});</script>'
      '<a class="cs-first-post-link" href="/content-studio/desk-setup-post">'
      '→ デスク環境投稿パッケージを見る（楽天ROOM向け）</a> '
      '<a class="cs-first-post-link" href="/content-studio/weekly-plan">'
      '→ 7日間コンテンツ計画を見る</a>'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の資料です。'
      'Pinterest・楽天ROOM・noteへの投稿・送信・連携は行われません。</p>'
      '</section>'
  )


# MISSION 037.1: note初回記事の手動投稿パッケージ(長文・高品質版、ローカル専用)。
#
# MISSION 037の短い記事パッケージは公開用として使わず、本文4,500〜5,500字
# 程度の実用的な長文記事に作り直したもの。断定的な成果・収入・作業時間・
# 性能比較は一切含めず、実体験でないことを実体験のように書かない。初回
# 記事には商品紹介・楽天ROOMリンク・アフィリエイトリンクを含めず、将来
# リンクを追加する場合は社長が手動確認し、必要に応じて広告・PR表記を
# 確認する運用であることを明記する。見出し画像は日本語文字・ロゴ・実在
# サービスの画面を一切含まない横長のオリジナルビジュアル(木目のデスク・
# ノートPC・ノート・暖色のデスクライト・控えめな青いAIの抽象表現)で、
# 見出し文字はHTML側で重ねる(画像そのものには文字を焼き込まない)。
# note・SNSへの投稿・自動投稿・予約投稿・ログイン操作・API連携・外部
# 通信は一切行わない。将来テーマ・文面・画像の中身を差し替える場合は、
# このデータ構造(NOTE_FIRST_ARTICLE)を編集するだけでよい。
NOTE_FIRST_ARTICLE = {
    "theme": "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
    "title": "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
    "intro": (
        "「AIを仕事で使ってみたい」と思っても、何から手をつければいいのか分からず、結局そのまま"
        "にしている人は多いのではないでしょうか。とくに、日々の業務に追われながら子育てや家庭の"
        "ことも同時にこなしている会社員にとって、新しいツールを一から勉強する時間を作るのは"
        "簡単ではありません。\n\n"
        "この記事では、AIをまったく触ったことがない人でも、今日から無理なく試せる3つの使い方を"
        "紹介します。特別なソフトの導入も、専門知識も必要ありません。スマートフォンやパソコンで"
        "使えるAIチャットに、話しかけるように文章を打ち込むだけで始められます。休憩時間や通勤の"
        "隙間時間のような、ほんの数分でも試すことができます。\n\n"
        "紹介する3つの使い方は、メールの下書き・長い文章の要約・アイデア出しの壁打ちです。どれも"
        "「AIに丸ごと任せる」のではなく、「AIに下準備を手伝ってもらい、最終的な判断は自分で行う」"
        "という考え方が土台になっています。この記事を読み終えたときには、AIを仕事の中でどう"
        "位置づければいいか、具体的なイメージを持てるはずです。"
    ),
    "prep": {
        "heading": "はじめる前に",
        "body": (
            "はじめる前に、特別な準備は必要ありません。スマートフォンやパソコンで使える無料の"
            "AIチャットサービスであれば、今すぐ試せる状態です。アカウント登録が必要な場合も"
            "ありますが、氏名とメールアドレス程度の簡単な手続きで済むことがほとんどです。どの"
            "サービスを選ぶかで迷う場合は、まずは手元の端末にすでに入っているものや、周囲の人が"
            "使っているものから触ってみるのがおすすめです。大切なのは「どのAIを使うか」よりも、"
            "「どう話しかけるか」であり、この記事で紹介する3つの使い方は、ほとんどのAIチャット"
            "サービスに共通して応用できます。"
        ),
    },
    "sections": [
        {
            "heading": "1. メールの下書きを1文で頼む",
            "usage": (
                "メールを書くという作業は、内容そのものを考える時間よりも、言葉づかいや構成を"
                "整える時間のほうが長くかかることがあります。とくに、お礼の連絡、謝罪を含む連絡、"
                "初めての相手への依頼など、言い回しに気を使う場面では、書き始めるまでに時間が"
                "かかりがちです。こうした場面こそ、AIに下書き作成を手伝ってもらう使いどころです。"
                "ゼロから文章を組み立てるのではなく、「伝えたいことの骨組み」をAIに渡し、たたき台を"
                "出してもらう、という使い方をします。定型的な連絡だけでなく、少し気を使う場面ほど、"
                "下書きの助けがあると気持ちの負担が軽くなります。"
            ),
            "input_example": (
                "入力の仕方はむずかしく考える必要はありません。たとえば、次のように話しかけるように"
                "打ち込むだけで十分です。\n\n"
                "「取引先の◯◯様へ、来週の打ち合わせを1時間ほど遅らせてほしいとお願いするメールの"
                "下書きを作ってください。丁寧だけど堅苦しすぎない文章でお願いします。」\n\n"
                "このように、誰に・何を・どんなトーンで伝えたいかを1〜2文にまとめて渡すと、AIは"
                "その情報をもとに文章の形に整えてくれます。宛先の名前や具体的な日時など、細かい"
                "情報も一緒に伝えておくと、修正の手間が少なくなります。"
            ),
            "output_check": (
                "AIが作った下書きは、そのまま送信せず、必ず次の3点を確認しましょう。まず、事実"
                "関係が正しいかどうかです。日時や金額、固有名詞などは、AIが文脈から推測して補って"
                "しまうことがあるため、自分が伝えたい情報と一致しているか一つずつ照らし合わせます。"
                "次に、言葉づかいが相手や場面に合っているかどうかです。AIの文章は丁寧すぎたり、"
                "逆にカジュアルすぎたりすることがあるため、実際の関係性に合わせて調整します。最後に、"
                "自分の言葉として違和感がないかどうかです。下書きをそのまま使うのではなく、語尾や"
                "言い回しを少し直すだけで、自分らしい文章に近づきます。"
            ),
        },
        {
            "heading": "2. 長い文章を要約してもらう",
            "usage": (
                "会議の議事録、長めの報告書、複数人でやり取りしたメールの履歴など、内容を把握する"
                "ために目を通さなければならない文章は、日々の業務の中で意外と多くあります。時間を"
                "かけて全部を読み込む余裕がないとき、AIに要点を先にまとめてもらい、全体像をつかんで"
                "から必要な部分だけ読み込む、という使い方が有効です。読む作業をゼロにするのでは"
                "なく、読む順番と優先度を整理するための使いどころだと考えると、扱いやすくなります。"
                "移動中や子どもの寝かしつけの合間など、まとまった時間が取りにくいタイミングでも"
                "取り入れやすい使い方です。"
            ),
            "input_example": (
                "要約を頼むときは、文章そのものと一緒に、どのような形でまとめてほしいかを伝えると、"
                "より使いやすい結果になります。\n\n"
                "「以下の議事録を、決定事項・保留事項・次回までの宿題の3つに分けて、それぞれ"
                "箇条書きで3行以内にまとめてください。」\n\n"
                "このように、まとめ方の枠組みをこちらから指定することで、AIが自由に要約するよりも、"
                "実際の業務で使いやすい形に整理されます。情報量が多い場合は、一度に全部を渡そうと"
                "せず、章や日付ごとに分けて渡すと、精度が安定しやすくなります。"
            ),
            "output_check": (
                "要約の結果を確認するときにもっとも大切なのは、「要約はあくまで参考情報である」と"
                "いう前提を崩さないことです。AIの要約は、文章全体の中で重要そうに見える部分を抜き"
                "出す仕組みのため、実際には重要な但し書きや例外事項が抜け落ちてしまうことがあります。"
                "特に、金額や納期、責任の所在に関わる記述は、要約された文章だけで判断せず、必ず"
                "原文に戻って確認しましょう。要約はあくまで「読む優先順位をつけるための地図」として"
                "使い、最終的な判断材料は原文から得る、という順番を守ることが大切です。"
            ),
        },
        {
            "heading": "3. アイデア出しの壁打ち相手にする",
            "usage": (
                "企画や改善案を考えるとき、一人で考え続けていると同じ発想の中をぐるぐる回って"
                "しまうことがあります。そんなときは、AIを「否定せずに付き合ってくれる壁打ち相手」"
                "として使う方法があります。人に相談するほどではない、まだ形になっていない段階の"
                "アイデアでも、AIには気軽に投げかけることができます。出てきた案をすべて採用する"
                "必要はなく、自分では思いつかなかった切り口に気づくためのきっかけとして使うのが"
                "ポイントです。周囲に相談できる相手がいない時間帯でも、一人で抱え込まずに考えを"
                "整理する手段になります。"
            ),
            "input_example": (
                "壁打ちをするときは、状況と制約条件を伝えると、より実用的な案が返ってきやすく"
                "なります。\n\n"
                "「子育て世代の会社員向けに、平日夜でも参加しやすい30分程度のオンライン相談会を"
                "企画したいです。テーマの案を5つ挙げてください。」\n\n"
                "このように、対象者・条件・欲しい案の数を具体的に伝えることで、漠然とした問いかけ"
                "よりも活用しやすい返答が得られます。出てきた案に対して「もう少し身近な言葉で」"
                "「他の切り口も」と重ねて聞き返すことで、案を育てていくこともできます。"
            ),
            "output_check": (
                "壁打ちで得られた案は、あくまで「たたき台」であることを忘れないようにしましょう。"
                "AIが提案する案の中には、実際の社内事情や過去の経緯、対象者の細かい状況を踏まえて"
                "いないものも含まれます。出てきた案をそのまま採用するのではなく、自分たちの状況に"
                "合っているか、実現できる範囲かを一つずつ検討したうえで、最終的な企画に落とし込む"
                "ことが必要です。壁打ちの目的は答えをもらうことではなく、考えを広げるきっかけを"
                "作ることだと捉えると、使い方の軸がぶれにくくなります。"
            ),
        },
    ],
    "closing_sections": [
        {
            "heading": "失敗しやすい点",
            "body": (
                "AIを使い始めたばかりのころによくある失敗として、次のようなものが挙げられます。\n\n"
                "一つ目は、出てきた文章や要約をそのまま確認せずに使ってしまうことです。AIの出力は"
                "自然な文章に見えるため、つい信用しすぎてしまいがちですが、事実関係の誤りや情報の"
                "抜け漏れが含まれている可能性は常にあります。\n\n"
                "二つ目は、指示があいまいなまま頼んでしまうことです。「いい感じにまとめて」のような"
                "漠然とした依頼では、期待した結果が返ってきにくくなります。誰に・何のために・どんな"
                "形でという条件を、できるだけ具体的に伝えることが、使いこなす近道です。\n\n"
                "三つ目は、一度の指示で満足のいく結果が出なかったときに、そこで使うのをやめて"
                "しまうことです。AIとのやり取りは、一往復で完成させるものではなく、出てきた結果を"
                "見ながら「ここをもう少し」と伝え直す、対話に近い使い方をすると、結果が安定し"
                "やすくなります。\n\n"
                "四つ目は、AIに聞けば何でも解決すると思い込み、自分で考える機会そのものを手放して"
                "しまうことです。AIはあくまで下準備を手伝う道具であり、考える主体は自分自身で"
                "あるという感覚を保っておくことが、長く付き合っていくうえで大切です。"
            ),
        },
        {
            "heading": "機密情報の注意",
            "body": (
                "AIに文章を渡すときは、機密情報や個人情報の取り扱いに注意が必要です。取引先の氏名や"
                "連絡先、契約金額、社外に出していない社内資料の内容などを、そのままAIに入力すること"
                "は避けましょう。多くのAIサービスは入力内容を学習やサービス改善に利用する場合があり、"
                "意図せず情報が外部に残ってしまうリスクがあります。\n\n"
                "どうしても具体的な文脈が必要な場合は、固有名詞をA社・B様のように置き換える、金額や"
                "日付を仮の数字にするなど、特定できない形に加工してから入力する習慣をつけましょう。"
                "たとえば「取引先の田中様へ、契約金額150万円について」と入力する代わりに、「取引先の"
                "A様へ、契約金額について」のように抽象化するだけでも、リスクを大きく減らせます。"
                "会社によっては、AIツールの利用そのものに社内ルールが定められていることもあるため、"
                "業務で使う前に自分の会社の方針を確認しておくことも大切です。"
            ),
        },
        {
            "heading": "AIに任せない判断",
            "body": (
                "AIは便利な下準備の道具ですが、任せてはいけない判断もあります。たとえば、謝罪や"
                "重要な意思決定を含む連絡の最終的な言葉選びと送信の判断、契約条件や金額に関わる"
                "最終確認、社内外の人間関係に影響する微妙なニュアンスの調整などは、AIの提案を参考に"
                "しつつも、最終的には自分の目と経験で判断する必要があります。\n\n"
                "たとえば、取引先へのお詫びの連絡であれば、AIが作った下書きの構成や言葉づかいを"
                "参考にすることはできても、「実際にどこまで謝罪の言葉を重ねるか」「どのタイミングで"
                "送るか」といった判断は、これまでの関係性を知っている自分にしかできません。AIが出す"
                "文章は、一見もっともらしく見えても、その場の空気や相手との関係性、過去のやり取りの"
                "積み重ねまでは理解していません。「下書きや叩き台を作ってもらう」ところまでをAIに"
                "任せ、「最終的にどう伝えるか」を決めるのは常に自分自身である、という役割分担を"
                "意識することが、AIとうまく付き合っていくための基本になります。"
            ),
        },
        {
            "heading": "まとめ",
            "body": (
                "この記事では、AI初心者が仕事で最初に試しやすい3つの使い方として、メールの下書き・"
                "長い文章の要約・アイデア出しの壁打ちを紹介しました。どの使い方にも共通しているのは、"
                "AIに全部を任せるのではなく、下準備の部分だけを手伝ってもらい、最終的な確認と判断は"
                "自分で行うという姿勢です。この考え方さえ押さえておけば、大きな失敗をすることなく、"
                "AIを日々の仕事に少しずつ取り入れていくことができます。忙しい毎日の中でも、AIをうまく"
                "使い分けることで、考える時間そのものを自分の手元に取り戻していくことができるはず"
                "です。"
            ),
        },
        {
            "heading": "次の一歩",
            "body": (
                "まずは、今日中に送る予定のメールを1通、AIに下書きを頼んでみることから始めてみて"
                "ください。完璧な文章を求める必要はありません。「思っていたより早く書けた」「言葉"
                "づかいのヒントになった」と感じられれば、それで十分な一歩です。慣れてきたら、要約や"
                "壁打ちにも少しずつ範囲を広げてみましょう。無理に毎日使おうとせず、自分のペースで"
                "少しずつ試していくことが、AIと長く付き合っていくコツです。"
            ),
        },
    ],
    "tag_candidates": ["AI活用", "AI初心者", "仕事効率化", "生成AI", "業務効率化"],
    "future_link_note": (
        "この記事には、商品紹介や楽天ROOMリンク・アフィリエイトリンクを含めていません。将来リンクを"
        "追加する場合は、柴犬社長が内容を手動で確認し、必要に応じて広告・PR表記が必要かどうかを"
        "確認したうえで追加します。"
    ),
    "manual_post_note": (
        "この記事は、柴犬社長がnoteへ手動でコピー＆ペーストして公開してください。note・SNSへの"
        "自動投稿・予約投稿・ログイン操作・API連携・外部通信は一切行いません。"
    ),
    "checklist": [
        "本文が4,500〜5,500字の目安に収まっているか確認した",
        "断定的な時短効果・収益・性能・ランキングの表現が含まれていないか確認した",
        "実体験でないことを実体験のように書いていないか確認した",
        "機密情報・個人情報の実例をそのまま書いていないか確認した",
        "見出し画像に日本語文字・ロゴ・実在サービスの画面が写っていないか確認した",
        "タグ候補が記事内容と合っているか確認した",
        "noteアカウントにログインした状態で、手動で貼り付けて公開できる準備ができている",
    ],
    "hero_image_alt": (
        "落ち着いた夜のホームオフィスのイメージ。木目のデスクにノートパソコンとノートが置かれ、"
        "暖色のデスクライトが手元を照らしている。右上には控えめな青い光の粒子が浮かぶ抽象的な"
        "演出があるが、実在のロゴ・製品名・画面表示・文字は含まれていない。"
    ),
    # MISSION 037.1微修正: 見出し画像に重ねるタイトルの改行位置を固定する。
    # ブラウザの自動折り返しに任せると、幅によって「メール」が「メー」
    # 「ル」のように単語の途中で分割されてしまうことがあるため、4行の
    # 区切り位置をあらかじめ指定する。この4行を連結すると"title"と完全に
    # 一致する(内容は変更せず、見せ方だけを固定している)。
    "hero_title_lines": [
        "AI初心者が仕事で最初に試",
        "す3つの使い方",
        "──メール・要約・壁打ちを失敗し",
        "ない形で始める",
    ],
}

NOTE_HERO_IMAGE_RELATIVE_PATH = "images/note-first-article-hero.png"
# MISSION 037.1修正: Pillow製の図形イラストから、高精細なオリジナル
# ビジュアル(1672x941)へ差し替えた。この画像はそのまま使用しており、
# SVG/Pillowでの再描画は行っていない(generate_note_hero_image_pngは
# 開発時の代替手段として残しているが、現在配信している画像の生成には
# 使われていない)。
NOTE_HERO_IMAGE_WIDTH = 1672
NOTE_HERO_IMAGE_HEIGHT = 941


def _note_article_body_plain_text(article):
  """記事本文(タイトルを除く、導入〜次の一歩まで)のプレーンテキストを組み立てる。

  見出し画像・タグ候補・チェックリストは含めない。段落の区切りは実際の
  改行(\\n\\n)で表現し、コピー用の非表示要素と文字数検証の両方で同じ
  テキストを共有することで、表示・コピー・テストの間で内容がずれない
  ようにしている。
  """
  parts = [article["intro"], f'{article["prep"]["heading"]}\n{article["prep"]["body"]}']
  for section in article["sections"]:
    parts.append(section["heading"])
    parts.append(f'使いどころ\n{section["usage"]}')
    parts.append(f'入力例\n{section["input_example"]}')
    parts.append(f'出力確認\n{section["output_check"]}')
  for closing in article["closing_sections"]:
    parts.append(f'{closing["heading"]}\n{closing["body"]}')
  return "\n\n".join(parts)


def _note_article_full_copy_text(article):
  """タイトルを含む、note投稿用のコピー全文を組み立てる。"""
  return f'{article["title"]}\n\n{_note_article_body_plain_text(article)}'


def _paragraphs_html(text):
  """改行(\\n\\n)区切りのプレーンテキストを<p>タグの並びに変換する。"""
  return "".join(f'<p>{paragraph}</p>' for paragraph in text.split("\n\n"))


def generate_note_hero_image_png(out_path=None):
  """note記事用の横長ヒーロービジュアル(NOTE_HERO_IMAGE_WIDTH x

  NOTE_HERO_IMAGE_HEIGHT)を生成し、ファイルへ保存する(開発時専用)。
  MISSION 037.1修正で、実際に配信している画像は高精細なオリジナル
  ビジュアル(1672x941)に差し替えられており、この関数はもう配信中の
  画像の生成には使われていない。将来Pillow製イラストに戻す場合の
  代替手段として残している。落ち着いた夜のホームオフィス・木目のデスク・
  ノートPC・
  ノート・暖色のデスクライト・控えめな青いAIの抽象表現を、グラデーション
  と図形の重ね合わせだけで表現する。ロゴ・製品名・読める文字・透かし・
  実在サービスの画面は一切描画しない。見出し文字は画像に焼き込まず、HTML
  側で重ねる(_render_note_article_sceneのnote-hero-overlay)。左側は
  タイトルを重ねる余白として、意図的に要素を減らしている。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。ビジュアルの
  構図を差し替えたい場合、この関数を手動で再実行してPNGを作り直すこと。
  実行にはPillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; o.generate_note_hero_image_png()"
  """
  import random
  from PIL import Image, ImageDraw, ImageFilter  # 遅延import(開発時専用)

  width, height = NOTE_HERO_IMAGE_WIDTH, NOTE_HERO_IMAGE_HEIGHT
  rng = random.Random(2037)

  # 背景: 夜のホームオフィスを思わせる、上が濃紺・下がわずかに暖かい
  # 縦グラデーション。
  top_color, bottom_color = (7, 9, 17), (24, 17, 15)
  base = Image.new("RGB", (width, height), top_color)
  draw = ImageDraw.Draw(base)
  for y in range(height):
    t = y / (height - 1)
    draw.line(
        [(0, y), (width, y)],
        fill=tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3)),
    )
  img = base.convert("RGBA")

  # 暖色のデスクライトの光だまり(右寄り)をぼかして重ねる。
  warm_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  warm_draw = ImageDraw.Draw(warm_layer)
  lamp_cx, lamp_cy = int(width * 0.74), int(height * 0.40)
  warm_draw.ellipse(
      [lamp_cx - 260, lamp_cy - 200, lamp_cx + 260, lamp_cy + 200], fill=(255, 176, 90, 130)
  )
  warm_layer = warm_layer.filter(ImageFilter.GaussianBlur(75))
  img = Image.alpha_composite(img, warm_layer)

  # 控えめな青いAIの気配(画面まわりの淡い光)をぼかして重ねる。
  blue_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  blue_draw = ImageDraw.Draw(blue_layer)
  ai_cx, ai_cy = int(width * 0.80), int(height * 0.30)
  blue_draw.ellipse([ai_cx - 190, ai_cy - 150, ai_cx + 190, ai_cy + 150], fill=(56, 189, 248, 80))
  blue_layer = blue_layer.filter(ImageFilter.GaussianBlur(65))
  img = Image.alpha_composite(img, blue_layer)

  draw = ImageDraw.Draw(img)

  # 木目のデスク(下部32%程度の暖色グラデーション帯)。
  desk_top_y = int(height * 0.68)
  desk_top_color, desk_bottom_color = (76, 50, 31), (36, 23, 14)
  for y in range(desk_top_y, height):
    t = (y - desk_top_y) / (height - desk_top_y - 1)
    c = tuple(
        int(desk_top_color[i] + (desk_bottom_color[i] - desk_top_color[i]) * t) for i in range(3)
    )
    draw.line([(0, y), (width, y)], fill=c + (255,))
  # 木目を思わせる、ごく控えめな濃淡の横線(具象的な模様にはしない)。
  for _ in range(16):
    gy = rng.randint(desk_top_y + 8, height - 8)
    shade = rng.randint(-16, 12)
    color = tuple(max(0, min(255, desk_top_color[i] + shade)) for i in range(3))
    draw.line([(0, gy), (width, gy + rng.randint(-3, 3))], fill=color + (55,), width=1)

  # ノートPC(デスク中央よりやや右)。画面はロゴ・文字のない単色の
  # ほのかな発光のみ。
  laptop_cx = int(width * 0.66)
  base_w, base_h = 420, 22
  base_y = desk_top_y + 46
  draw.rounded_rectangle(
      [laptop_cx - base_w // 2, base_y, laptop_cx + base_w // 2, base_y + base_h],
      radius=7, fill=(20, 20, 24, 255),
  )
  screen_w, screen_h = 340, 220
  screen_x0 = laptop_cx - screen_w // 2
  screen_y1 = base_y
  screen_y0 = screen_y1 - screen_h
  draw.rounded_rectangle(
      [screen_x0, screen_y0, screen_x0 + screen_w, screen_y1], radius=12, fill=(13, 13, 17, 255)
  )
  inner_pad = 12
  draw.rounded_rectangle(
      [screen_x0 + inner_pad, screen_y0 + inner_pad, screen_x0 + screen_w - inner_pad,
       screen_y1 - inner_pad],
      radius=6, fill=(29, 42, 58, 255),
  )

  # ノート(ノートPCの左、デスクに平置き)。罫線のみで文字は書かない。
  nb_w, nb_h = 170, 120
  nb_x0 = laptop_cx - base_w // 2 - 190
  nb_y0 = desk_top_y + 78
  draw.rounded_rectangle(
      [nb_x0, nb_y0, nb_x0 + nb_w, nb_y0 + nb_h], radius=6, fill=(233, 226, 211, 255)
  )
  for i in range(5):
    ly = nb_y0 + 28 + i * 17
    draw.line([(nb_x0 + 18, ly), (nb_x0 + nb_w - 18, ly)], fill=(188, 179, 162, 255), width=2)
  draw.line(
      [(nb_x0 + 22, nb_y0 + nb_h - 16), (nb_x0 + nb_w - 34, nb_y0 + nb_h - 34)],
      fill=(58, 58, 62, 255), width=6,
  )

  # デスクライト(単純な腕とシェードのシルエットのみ)。
  lamp_base_x = int(width * 0.93)
  lamp_base_y = desk_top_y + 34
  draw.line([(lamp_base_x, lamp_base_y), (lamp_base_x - 46, lamp_base_y - 180)],
            fill=(28, 24, 20, 255), width=9)
  draw.line([(lamp_base_x - 46, lamp_base_y - 180), (lamp_base_x - 160, lamp_base_y - 236)],
            fill=(28, 24, 20, 255), width=9)
  draw.polygon(
      [(lamp_base_x - 214, lamp_base_y - 262), (lamp_base_x - 108, lamp_base_y - 262),
       (lamp_base_x - 136, lamp_base_y - 214), (lamp_base_x - 186, lamp_base_y - 214)],
      fill=(38, 32, 26, 255),
  )

  # 青いAIの抽象表現(ノード+接続線)。ロゴ・アイコンではなく、単なる
  # 光の粒子のネットワークとして描く。
  nodes = [
      (width * 0.80, height * 0.15), (width * 0.87, height * 0.23), (width * 0.92, height * 0.13),
      (width * 0.83, height * 0.29), (width * 0.96, height * 0.21),
  ]
  nodes = [(int(x), int(y)) for x, y in nodes]
  for i in range(len(nodes) - 1):
    draw.line([nodes[i], nodes[i + 1]], fill=(56, 189, 248, 90), width=2)
  draw.line([nodes[0], nodes[3]], fill=(56, 189, 248, 70), width=2)
  for nx, ny in nodes:
    draw.ellipse([nx - 6, ny - 6, nx + 6, ny + 6], fill=(125, 211, 252, 255))
    draw.ellipse([nx - 11, ny - 11, nx + 11, ny + 11], outline=(56, 189, 248, 150), width=2)

  # 周辺を軽く落として、中央〜右側の被写体に視線が集まるようにする
  # (左側はタイトルを重ねる余白として、あえて明るさを残す)。
  vignette_mask = Image.new("L", (width, height), 0)
  vm_draw = ImageDraw.Draw(vignette_mask)
  vm_draw.ellipse(
      [-int(width * 0.25), -int(height * 0.25), int(width * 1.25), int(height * 1.25)], fill=255
  )
  vignette_mask = vignette_mask.filter(ImageFilter.GaussianBlur(200))
  vignette_mask = vignette_mask.point(lambda p: 255 - p)
  vignette_mask = vignette_mask.point(lambda p: int(p * 0.32))
  black = Image.new("RGBA", (width, height), (0, 0, 0, 255))
  img = Image.composite(black, img, vignette_mask)

  img = img.convert("RGB")
  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static", NOTE_HERO_IMAGE_RELATIVE_PATH
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def generate_note_ai_mismatch_hero_image_png(out_path=None):
  """「AIに聞いても『なんか違う』と感じる人へ」note記事下書き用の横長

  ヒーロービジュアル(NOTE_THIRD_ARTICLE_DRAFT_COVER_WIDTH x
  NOTE_THIRD_ARTICLE_DRAFT_COVER_HEIGHT、1672x941)を生成し、ファイルへ
  保存する(開発時専用)。既存のnote初回記事・スマホAI下書き記事の見出し
  画像はどちらも夜の暗い配色のため、この画像は明確に区別できる明るい昼間の
  配色(やわらかい水色→暖かいクリーム色の縦グラデーション)にする。木目の
  デスク・デスクライト・観葉植物は使わず、スマートフォンを斜めに持ち直して
  いる手元(指先だけの簡略化した図形)を主役にした構図にする。ロゴ・文字・
  実在サービスの画面・人物の顔は一切描画しない。見出し文字はHTML側でも
  画像側でも一切重ねない・焼き込まない(タイトルなしの写真的な構図のみ)。

  Flaskアプリの起動・リクエスト処理からは一切呼び出さない。構図を差し替え
  たい場合、この関数を手動で再実行してPNGを作り直すこと。実行には
  Pillowが必要(pip install Pillow)。

  実行例:
      source venv/bin/activate && pip install Pillow
      python -c "import office_views as o; o.generate_note_ai_mismatch_hero_image_png()"
  """
  from PIL import Image, ImageDraw, ImageFilter  # 遅延import(開発時専用)

  width, height = NOTE_THIRD_ARTICLE_DRAFT_COVER_WIDTH, NOTE_THIRD_ARTICLE_DRAFT_COVER_HEIGHT

  # 背景: 明るい昼間を思わせる、上がやわらかい水色・下が暖かいクリーム色の
  # 縦グラデーション(既存の夜の配色の見出し画像とは明確に区別する)。
  top_color, bottom_color = (219, 234, 254), (255, 247, 230)
  base = Image.new("RGB", (width, height), top_color)
  draw = ImageDraw.Draw(base)
  for y in range(height):
    t = y / (height - 1)
    draw.line(
        [(0, y), (width, y)],
        fill=tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3)),
    )
  img = base.convert("RGBA")

  # 窓から差し込む日差しを思わせる、やわらかい光だまりを2箇所ぼかして重ねる。
  for cx_ratio, cy_ratio, radius, color in (
      (0.16, 0.22, 260, (255, 250, 230, 150)),
      (0.86, 0.78, 220, (191, 219, 254, 110)),
  ):
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    gx, gy = int(width * cx_ratio), int(height * cy_ratio)
    glow_draw.ellipse([gx - radius, gy - radius, gx + radius, gy + radius], fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    img = Image.alpha_composite(img, glow)

  draw = ImageDraw.Draw(img)

  # スマートフォンを斜めに持ち直している手元。フォンは中央やや右寄りに
  # 傾けて配置し、下側から2本の指先(簡略化した図形)が画面に触れている
  # 様子を表現する。人物の顔・腕全体は描かず、指先だけの抽象的な表現に
  # とどめる。
  phone_layer = Image.new("RGBA", (520, 900), (0, 0, 0, 0))
  phone_draw = ImageDraw.Draw(phone_layer)
  # 本体の影(ほんのり)。
  phone_draw.rounded_rectangle([50, 60, 470, 860], radius=52, fill=(20, 20, 24, 40))
  # 本体。
  phone_draw.rounded_rectangle([40, 40, 460, 840], radius=52, fill=(28, 28, 33, 255))
  # 画面(空白・無地、文字やアイコンは描かない)。
  phone_draw.rounded_rectangle([64, 70, 436, 810], radius=34, fill=(214, 226, 242, 255))
  # 画面にごくわずかな上下の明暗差を付け、フラットになりすぎないようにする。
  shade = Image.new("RGBA", (520, 900), (0, 0, 0, 0))
  shade_draw = ImageDraw.Draw(shade)
  shade_draw.rounded_rectangle([64, 70, 436, 460], radius=34, fill=(255, 255, 255, 40))
  phone_layer = Image.alpha_composite(phone_layer, shade)
  phone_draw = ImageDraw.Draw(phone_layer)

  # 指先(親指2本を簡略化した、丸みを帯びた図形)を画面下部に配置する。
  finger_color = (233, 195, 165, 255)
  phone_draw.ellipse([120, 700, 230, 900], fill=finger_color)
  phone_draw.ellipse([300, 680, 410, 900], fill=finger_color)
  # 指先のハイライト(立体感を少しだけ加える)。
  phone_draw.ellipse([140, 715, 190, 780], fill=(245, 214, 188, 160))
  phone_draw.ellipse([320, 695, 370, 760], fill=(245, 214, 188, 160))

  phone_layer = phone_layer.rotate(-13, resample=Image.BICUBIC, expand=True)
  paste_x = int(width * 0.52)
  paste_y = int(height * 0.06)
  img.alpha_composite(phone_layer, (paste_x, paste_y))

  # 周辺をごくわずかに落として、被写体(スマホと指先)に視線が集まるように
  # する。明るい配色を保つため、暗く落としすぎない。
  vignette_mask = Image.new("L", (width, height), 0)
  vm_draw = ImageDraw.Draw(vignette_mask)
  vm_draw.ellipse(
      [-int(width * 0.25), -int(height * 0.25), int(width * 1.25), int(height * 1.25)], fill=255
  )
  vignette_mask = vignette_mask.filter(ImageFilter.GaussianBlur(220))
  vignette_mask = vignette_mask.point(lambda p: 255 - p)
  vignette_mask = vignette_mask.point(lambda p: int(p * 0.16))
  dark_overlay = Image.new("RGBA", (width, height), (40, 30, 20, 255))
  img = Image.composite(dark_overlay, img, vignette_mask)

  img = img.convert("RGB")
  out_path = out_path or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "static",
      NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH,
  )
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  img.save(out_path)
  return out_path


def _render_note_article_scene(article):
  """note初回記事の手動投稿パッケージのHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・note・外部
  通信への アクセスは一切行わない。見出しビジュアルはローカル生成済み
  PNG(static/配下)を<img>で表示し、タイトル文字はHTML側で重ねる
  (画像そのものには文字を焼き込まない)。記事本文のコピー用ボタンは、
  表示用マークアップとは別に用意した非表示のプレーンテキスト(改行付き)
  をコピー対象にすることで、見出し・段落の区切りを保ったまま貼り付け
  られるようにする。クリップボード操作が失敗しても例外を伝播させず、
  安全なフォールバック表示にする。
  """
  visible_parts = [
      _paragraphs_html(article["intro"]),
      f'<h3 class="note-section-heading">{article["prep"]["heading"]}</h3>'
      + _paragraphs_html(article["prep"]["body"]),
  ]
  for section in article["sections"]:
    visible_parts.append(f'<h3 class="note-section-heading">{section["heading"]}</h3>')
    visible_parts.append(
        '<h4 class="note-subheading">使いどころ</h4>' + _paragraphs_html(section["usage"])
    )
    visible_parts.append(
        '<h4 class="note-subheading">入力例</h4>' + _paragraphs_html(section["input_example"])
    )
    visible_parts.append(
        '<h4 class="note-subheading">出力確認</h4>' + _paragraphs_html(section["output_check"])
    )
  for closing in article["closing_sections"]:
    body_html = _paragraphs_html(closing["body"])
    if closing["heading"] in ("まとめ", "次の一歩"):
      visible_parts.append(
          f'<h3 class="note-section-heading">{closing["heading"]}</h3>'
          f'<div class="note-article-conclusion">{body_html}</div>'
      )
    else:
      visible_parts.append(f'<h3 class="note-section-heading">{closing["heading"]}</h3>{body_html}')

  visible_body = (
      f'<h2 class="note-article-title">{article["title"]}</h2>' + "".join(visible_parts)
  )
  copy_text = _note_article_full_copy_text(article)

  tag_chips = "".join(f'<li>{tag}</li>' for tag in article["tag_candidates"])
  checklist_items = "".join(
      f'<li><input type="checkbox" id="note-check-{i}"><label for="note-check-{i}">{item}</label></li>'
      for i, item in enumerate(article["checklist"])
  )

  # MISSION 037.1微修正: 見出し画像に重ねるタイトルは、ブラウザの自動
  # 折り返しに任せず、hero_title_linesで指定した4行に固定する(「メール」
  # が行の途中で分割されるのを防ぐため)。連結結果がtitleと一致しない場合は
  # 表示内容が食い違ってしまうため、その場で検出する。
  hero_title_lines = article["hero_title_lines"]
  assert "".join(hero_title_lines) == article["title"], (
      "hero_title_lines must reconstruct title exactly"
  )
  hero_title_html = "<br>".join(hero_title_lines)

  return (
      '<section class="note-article-board" aria-label="note初回記事の手動投稿パッケージ">'
      '<div class="fp-notice"><b>社内向けの投稿パッケージです。</b>'
      'noteへの投稿・送信・連携は一切行われません。柴犬社長が内容を確認し、'
      '手動でnoteへ貼り付けて公開するための準備画面です。</div>'
      f'<p class="fp-theme">対象テーマ：<b>{article["theme"]}</b></p>'
      f'<div class="fp-note fp-note-warn"><b>商品紹介について。</b>{article["future_link_note"]}</div>'
      f'<div class="fp-note fp-note-warn"><b>手動投稿について。</b>{article["manual_post_note"]}</div>'
      '<h3 class="fp-section-title">見出し画像</h3>'
      '<div class="note-hero">'
      f'<img class="note-hero-img" src="/static/{NOTE_HERO_IMAGE_RELATIVE_PATH}" '
      f'alt="{article["hero_image_alt"]}">'
      '<div class="note-hero-scrim"></div>'
      f'<div class="note-hero-overlay"><h1 class="note-hero-title">{hero_title_html}</h1></div>'
      '</div>'
      f'<p class="fp-svg-ratio">横長 {NOTE_HERO_IMAGE_WIDTH}×{NOTE_HERO_IMAGE_HEIGHT}'
      '（ローカル生成画像・外部素材なし。見出し文字はHTML側で重ねています）</p>'
      # MISSION 037.1: 通常のダウンロードリンク(<a href download>)のみで
      # 保存する。外部通信・JavaScript必須の処理は行わない。あらかじめ
      # 生成済みのローカルPNGファイル(static/配下)を指すだけであり、
      # クリックしてもnoteへの投稿・送信・連携は一切発生しない。
      f'<a class="fp-png-download" href="/static/{NOTE_HERO_IMAGE_RELATIVE_PATH}" '
      'download="note-first-article-hero.png">見出し画像PNGを保存</a>'
      '<p class="fp-png-hint">保存したPNGをnoteの見出し画像として手動アップロードしてください。'
      'このボタンからの投稿・送信・連携は行われません。</p>'
      '<h3 class="fp-section-title">記事</h3>'
      '<div class="fp-field">'
      '<div class="fp-field-head"><h4>記事本文</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note-article-body-copy">'
      'コピー</button></div>'
      f'<div class="note-article-visible">{visible_body}</div>'
      f'<pre id="note-article-body-copy" class="note-article-copy-source">{copy_text}</pre>'
      '</div>'
      '<h3 class="fp-section-title">note向けタグ候補</h3>'
      f'<ul class="note-tags">{tag_chips}</ul>'
      '<h3 class="fp-section-title">投稿前チェックリスト</h3>'
      f'<ul class="fp-checklist">{checklist_items}</ul>'
      # MISSION 037.1: コピー操作はクライアント側JSのみで完結し、外部通信は
      # 行わない。navigator.clipboardが使えない/失敗する環境でも、例外を
      # 投げずに安全な文言へフォールバックする(既存の投稿パッケージ画面と同じ方式)。
      '<script>document.querySelectorAll(".fp-copy-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'const el=document.getElementById(btn.dataset.copyTarget);'
      'if(!el)return;'
      'const original=btn.textContent;'
      'const showResult=ok=>{btn.textContent=ok?"コピーしました":"コピーできませんでした";'
      'setTimeout(()=>{btn.textContent=original;},1800);};'
      'try{'
      'if(navigator.clipboard&&navigator.clipboard.writeText){'
      'navigator.clipboard.writeText(el.textContent).then(()=>showResult(true))'
      '.catch(()=>showResult(false));'
      '}else{showResult(false);}'
      '}catch(e){showResult(false);}'
      '});'
      '});</script>'
      '<a class="cs-first-post-link" href="/content-studio/publish-queue">'
      '→ 投稿キューを見る（社長承認待ち）</a>'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の資料です。'
      'note・SNS・楽天ROOMへの投稿・送信・連携は行われません。</p>'
      '</section>'
  )


# MISSION 043: Pinterestの新テーマ「スマホでAIに下書きを頼む前に確認する
# 3つ」(投稿キューのsmartphone-ai-draft-3points)と内容が一致するnote記事の
# 下書き。公開済みのNOTE_FIRST_ARTICLE(パソコンでのメール下書き・要約・
# 壁打ち)とは重複させず、スマホ・タブレットでの下書き依頼に焦点を絞る。
# note・SNSへの投稿・自動投稿・予約投稿・ログイン操作・API連携・外部通信は
# 一切行わない(下書き表示のみ)。将来文面を差し替える場合は、このデータ
# 構造(NOTE_SECOND_ARTICLE_DRAFT)を編集するだけでよい。
# MISSION 044: あらかじめ用意された見出し画像(NOTE_SECOND_ARTICLE_DRAFT_
# COVER_RELATIVE_PATH。1672x941の横長)を、このnote記事下書きにだけ表示
# する。画像は新規作成・差し替えを行わず、既存ファイルをそのまま使う。
# 見出し文字はHTML側で重ねない(画像そのものにも文字は焼き込まれていない)。
NOTE_SECOND_ARTICLE_DRAFT_COVER_RELATIVE_PATH = "images/note-smartphone-ai-draft-cover.png"
NOTE_SECOND_ARTICLE_DRAFT_COVER_WIDTH = 1672
NOTE_SECOND_ARTICLE_DRAFT_COVER_HEIGHT = 941

NOTE_SECOND_ARTICLE_DRAFT = {
    "theme": "スマホでAIに下書きを頼む前に確認する3つ",
    "title": "スマホでAIに下書きを頼む前に確認する3つ──端末・入力・読み返しを先に決める",
    # MISSION 044: あらかじめ用意された見出し画像のaltテキスト(社長指定の
    # 文言をそのまま使用)。
    "hero_image_alt": (
        "夜の木目デスクにスマートフォン、タブレット、折りたたみキーボード、ノートが置かれた様子。"
        "ロゴや実在サービスの画面は写っていません。"
    ),
    "overview": (
        "AI初心者がスマートフォンやタブレットで、AIにメール・メモ・短い文章の下書きを頼む場面を"
        "想定し、入力前に決めておくと入力や読み返しがしやすくなる3つのポイント（使う端末・文字"
        "入力の方法・読み返す場所）を、具体例を交えて紹介する記事の下書きです。すでに公開している"
        "パソコン向けのメール下書き記事とは内容を重複させず、スマホ・タブレットでの使い方に焦点を"
        "当てています。"
    ),
    "intro": (
        "スマートフォンやタブレットでAIにメールやメモの下書きを頼もうとして、思ったよりも入力に"
        "手間取ってしまった、という経験はないでしょうか。パソコンの大きな画面とキーボードに慣れて"
        "いると、スマホの小さな画面での文字入力や、送信前の読み返しに、想像以上に時間がかかる"
        "ことがあります。\n\n"
        "この記事では、AIをまだ使い始めたばかりの人が、スマートフォンやタブレットでメール・メモ・"
        "短い文章の下書きを頼む前に、あらかじめ決めておくと入力や確認がしやすくなる3つのポイント"
        "を紹介します。以前の記事ではパソコンでのメール下書きの頼み方を取り上げましたが、今回は"
        "スマホ・タブレットならではの使い方に絞って説明します。\n\n"
        "紹介する3つのポイントは、使う端末を決める・文字入力の方法を決める・読み返す場所を決める、"
        "です。どれも特別な設定や新しいアプリの導入は必要なく、AIに話しかける前に少し考えておく"
        "だけで実践できます。\n\n"
        "スマホやタブレットでAIを使う場面は、通勤中のすきま時間、家事や子どもの世話の合間、外出先で"
        "の待ち時間など、パソコンに向かうときよりも幅広くなりがちです。場面が変わるたびに端末や"
        "入力方法を一から選び直していると、それだけで気持ちの負担が増えてしまいます。あらかじめ"
        "自分なりのパターンをいくつか用意しておくことで、AIに下書きを頼むこと自体を、日々の"
        "ちょっとした作業の一つとして取り入れやすくなります。"
    ),
    "sections": [
        {
            "heading": "1. 使う端末を決める",
            "body": (
                "スマホでAIに下書きを頼むときは、まず「スマホだけで完結させるのか、タブレットや"
                "外部キーボードも使うのか」を先に決めておくと、途中で入力方法に迷わずに済みます。"
                "\n\n"
                "たとえば、移動中や外出先でちょっとしたメモの下書きを頼みたいときは、スマホ単体で"
                "十分なことがほとんどです。片手で持ったまま、AIのアプリやブラウザに用件を話しかける"
                "ように打ち込むだけで、短いメモ程度の下書きは作れます。\n\n"
                "一方、帰宅後に少し長めのメールや、複数の要点を含む文章の下書きを頼みたいときは、"
                "タブレットや折りたたみ式のキーボードを組み合わせたほうが、画面を広く使えて文章"
                "全体を確認しやすくなります。たとえば、自宅の机に座って作業する場面では、スマホを"
                "机に置いたまま操作するより、タブレットを目の高さに立てて表示し、キーボードで入力"
                "するほうが、姿勢も文字の見やすさも安定します。\n\n"
                "大切なのは「毎回どの端末を使うか迷う」状態を減らすことです。短い下書きはスマホ、"
                "少し長い下書きは机でタブレット＋キーボード、というように、自分なりの目安を先に"
                "決めておくと、AIに下書きを頼むたびに端末選びで立ち止まらずに済みます。\n\n"
                "端末を組み合わせる場合は、途中で作業を引き継げるかどうかも意識しておくと安心です。"
                "たとえば、外出先でスマホから下書きを頼んでおき、帰宅後にタブレットで続きを確認して"
                "仕上げる、という流れであれば、移動時間も無駄にせず、落ち着いた環境で最終確認もでき"
                "ます。逆に、毎回どの端末で何をどこまでやったか分からなくなってしまうと、同じ指示を"
                "二度打ち込むような手間が発生しがちです。「外出先ではスマホで下書きの依頼まで」「机に"
                "戻ったらタブレットで仕上げの確認まで」のように、端末ごとの役割をおおまかに決めて"
                "おくと、作業の引き継ぎもスムーズになります。"
            ),
        },
        {
            "heading": "2. 文字入力の方法を決める",
            "body": (
                "スマホでAIに指示を打ち込む方法は一つではありません。画面のソフトウェアキーボードで"
                "フリック入力やローマ字入力をする方法、音声入力でしゃべった内容をそのまま文字にする"
                "方法、外部の折りたたみキーボードを接続してパソコンに近い感覚で打つ方法など、いく"
                "つかの選択肢があります。\n\n"
                "どれが良いかは、そのときの状況によって変わります。たとえば、電車の中や人前など声を"
                "出しにくい場所では、指先だけで操作できるフリック入力や、画面キーボードでのローマ字"
                "入力が向いています。短い指示であれば、数十秒程度で打ち終えられることも多く、片手"
                "操作でも扱いやすい方法です。\n\n"
                "一方、自宅や静かな場所で、伝えたい内容が多いときは、音声入力を使うと、長い文章でも"
                "手で打つより早く伝えられることがあります。「取引先の◯◯様へ、来週の打ち合わせを"
                "1時間ほど遅らせてほしいとお願いするメールの下書きを作ってください」のように、話し"
                "かけるように内容を伝えるだけで、AIへの指示として成立します。ただし、音声入力は"
                "固有名詞や数字を誤って変換してしまうことがあるため、話し終えたあとに、変換された"
                "文字を一度目で確認してからAIに送る、という一手間を挟んでおくと安心です。\n\n"
                "さらに、机に向かって腰を据えて作業できるときは、折りたたみキーボードを接続すると、"
                "長い指示文や、複数の条件を含んだ依頼でも、画面キーボードより落ち着いて打ち込め"
                "ます。持ち運びできる小型のキーボードであれば、外出先のカフェなどでも同じように"
                "使えます。\n\n"
                "入力方法を状況に合わせて使い分けられるように、あらかじめ「声を出しにくい場所では"
                "フリック入力」「静かな場所では音声入力」「腰を据えて作業するときは外部キーボード」"
                "のように、自分なりの使い分けを決めておくと、そのつど迷わずに済みます。\n\n"
                "また、複数の入力方法を試したうえで、自分にとって一番指示が伝わりやすい方法を1つ"
                "見つけておくのも有効です。人によっては、フリック入力よりも音声入力のほうが、思って"
                "いることをそのまま言葉にしやすいと感じることもありますし、逆に、声に出すと言葉が"
                "まとまらず、画面に文字を打つほうが考えを整理しやすいと感じる人もいます。数回試して"
                "みて、自分にとって指示が組み立てやすい方法を基本の入力方法として決めておくと、AIへの"
                "依頼そのものにかかる時間も安定してきます。基本の方法を1つ決めておいたうえで、状況に"
                "応じて他の方法に切り替えられるようにしておくと、無理なく使い分けを続けられます。"
            ),
        },
        {
            "heading": "3. 読み返す場所を決める",
            "body": (
                "AIが作った下書きは、そのまま使うのではなく、必ず読み返して確認する必要があります。"
                "ここで意外と見落とされがちなのが、「どこで読み返すか」という点です。スマホの小さな"
                "画面で読み返すと、行間や文字が詰まって見えて、誤字や事実関係の間違いに気づきにくく"
                "なることがあります。\n\n"
                "たとえば、短いメモやチャットの返信程度であれば、スマホの画面のままで読み返しても"
                "大きな支障はありません。書いた直後にそのまま目を通し、宛先や日時など間違えやすい"
                "部分だけ指で追いながら確認する、という読み方で十分なことが多いです。\n\n"
                "一方、取引先へのメールや、複数の要点を含む文章など、内容の正確さがより重要な下書き"
                "については、画面を切り替えて読み返すことをおすすめします。たとえば、スマホで下書き"
                "を作ったあと、同じ内容をタブレットの大きな画面に表示し直して読み返す、あるいは一度"
                "声に出して読んでみる、といった方法です。画面を変えたり読み方を変えたりするだけで、"
                "書いているときには気づかなかった言い回しの違和感や、抜けている情報に気づきやすく"
                "なります。\n\n"
                "また、送信のような後戻りしにくい操作をする前に、少し時間を置いてから読み返す習慣も"
                "有効です。書いた直後は文章に慣れてしまい、細かい間違いを見逃しやすくなります。数分"
                "でも間を置いてから読み返す場所を用意しておくだけで、確認の精度が変わってきます。\n\n"
                "読み返す場所をあらかじめ決めておくことは、確認そのものを後回しにしないためにも"
                "役立ちます。「下書きができたら、いったん置いておいて、あとで読み返そう」と考えている"
                "うちに、そのまま送ってしまったり、読み返す前に別の作業に気を取られてしまったりする"
                "ことは珍しくありません。「短い下書きはその場のスマホ画面で」「重要な下書きは机に"
                "戻ってタブレットで」のように、読み返す場所と内容の重さを先に結び付けておくと、確認の"
                "抜け漏れを減らしやすくなります。"
            ),
        },
        {
            "heading": "3つを組み合わせるときに気をつけたいこと",
            "body": (
                "使う端末・文字入力の方法・読み返す場所は、それぞれ別々に決めるものではなく、"
                "セットで考えると使いやすくなります。たとえば、外出先でスマホと音声入力を組み合わせて"
                "下書きの依頼だけ済ませておき、帰宅後にタブレットに切り替えて、外部キーボードで細かい"
                "言い回しを直しながら読み返す、というように、場面ごとに3つの組み合わせをあらかじめ"
                "セットにしておくと、そのつど考え直す手間が減ります。\n\n"
                "また、音声入力を使うときは、周囲に人がいる場所で機密性の高い内容や、取引先の氏名・"
                "金額などを声に出さないよう注意が必要です。声に出した内容が周囲に聞こえてしまう"
                "可能性があるため、公共の場では、具体的な固有名詞や数字を避けて「取引先のA社へ」の"
                "ように抽象化して伝える、あるいは声を出しにくい場所ではフリック入力に切り替える、"
                "といった使い分けをしておくと安心です。\n\n"
                "端末・入力方法・読み返す場所の3つは、一度決めたら固定しなければならないものでは"
                "ありません。実際に使ってみて、しっくりこなければ組み合わせを見直してかまいません。"
                "大切なのは、AIに下書きを頼むたびに一から考え直すのではなく、自分にとって扱いやすい"
                "パターンをいくつか持っておくことです。\n\n"
                "組み合わせを見直す目安としては、「入力に時間がかかりすぎていないか」「読み返しを"
                "省略してしまっていないか」の2点を振り返ってみるとよいでしょう。たとえば、音声入力を"
                "選んだつもりが、周囲を気にして結局フリック入力に切り替えることが多い場合は、最初"
                "からフリック入力を基本にしたほうが手間が少なくなります。同じように、タブレットで"
                "読み返すつもりが、面倒でスマホの画面のまま送ってしまうことが続く場合は、読み返す"
                "場所の基準を「重要度」ではなく「そのとき実際にできる範囲」に合わせて決め直すのも"
                "一つの方法です。"
            ),
        },
    ],
    "closing_heading": "まとめ",
    "closing_body": (
        "この記事では、スマホやタブレットでAIにメールやメモの下書きを頼む前に決めておきたい3つの"
        "ポイントとして、使う端末を決める・文字入力の方法を決める・読み返す場所を決める、を紹介"
        "しました。以前の記事で紹介したパソコンでのメール下書きの頼み方と組み合わせると、場面に"
        "応じてスマホとパソコンを使い分けられるようになります。\n\n"
        "どのポイントも、特別な準備や新しいアプリの導入を必要とするものではありません。次にスマホ"
        "でAIに下書きを頼むときは、まず「今回はどの端末で、どう入力して、どこで読み返すか」を"
        "一呼吸置いて決めてみてください。入力や確認で迷う場面が、これまでより少し減っているかも"
        "しれません。\n\n"
        "最初から完璧な組み合わせを見つける必要はありません。まずは1つの場面、たとえば「移動中に"
        "スマホと音声入力でメモの下書きを頼み、帰宅後にタブレットで読み返す」というパターンだけ"
        "試してみて、使いやすければ他の場面にも広げていく、という進め方で十分です。少しずつ自分に"
        "合ったやり方を見つけていくことが、AIをスマホやタブレットで無理なく使い続けるコツになり"
        "ます。"
    ),
    "pinterest_description": (
        "スマホやタブレットでAIに下書きを頼むとき、入力前に決めておくと整理しやすくなる3つの"
        "ポイントをnote記事でまとめました。使う端末・文字入力の方法・読み返す場所について、具体例"
        "を交えて紹介しています。特定の商品の紹介やレビューは含みません。"
    ),
    # MISSION 045夜間点検: MISSION 044で見出し画像(上記「見出し画像」欄)を
    # 実際に表示するようになったため、末尾の文言を「画像は新規作成して
    # いない」という古い説明(MISSION 043時点のもの)から、既に表示済みの
    # 見出し画像とPinterest投稿キューの対応投稿を指す説明へ修正した(内容の
    # 矛盾を解消するための最小限の文言修正で、altテキスト案としての役割・
    # 3項目の要約内容は変更していない)。
    "alt_text_draft": (
        "スマホでAIに下書きを頼む前に確認する3つ、というテーマのnote記事用altテキスト案。木目の"
        "デスクにスマートフォン・タブレット・折りたたみキーボードが置かれた写真のイメージを想定し、"
        "記事の3項目（使う端末・文字入力の方法・読み返す場所）を要約した説明文。note記事本体の"
        "見出し画像は上記のとおり表示済みで、この案はPinterest投稿キューの同テーマ投稿と合わせて"
        "使う場合の候補です。"
    ),
    "manual_post_note": (
        "この記事はまだ下書きであり、noteへは投稿していません。柴犬社長が内容を確認し、必要に応じて"
        "手動でnoteへ貼り付けて公開する場合に備えた下書きです。note・SNSへの自動投稿・予約投稿・"
        "ログイン操作・API連携・外部通信は一切行いません。"
    ),
    "checklist": [
        "本文が4,500〜5,500字の目安に収まっているか確認した",
        "「必ず効率が上がる」「成果が出る」等の断定表現が含まれていないか確認した",
        "実在サービス画面・商品名・価格・在庫・ランキング・成果数値・レビューを記載していないか"
        "確認した",
        "楽天ROOMの商品紹介・リンクを含めていないか確認した",
        "公開済みのメール下書き記事(NOTE_FIRST_ARTICLE)と文章が重複していないか確認した",
        "Pinterest用説明文案が500字以内に収まっているか確認した",
        "見出し画像に日本語文字・ロゴ・実在サービスの画面が写っていないか確認した",
        "noteアカウントにログインした状態で、手動で貼り付けて公開できる準備ができている",
    ],
}


def _note_second_article_draft_body_plain_text(article):
  """NOTE_SECOND_ARTICLE_DRAFTの本文(導入〜まとめ)のプレーンテキストを組み立てる。

  概要・Pinterest説明文案・altテキスト案・チェックリストは含めない。段落の
  区切りは実際の改行(\\n\\n)で表現し、表示用マークアップと文字数検証の両方で
  同じテキストを共有する(NOTE_FIRST_ARTICLE用の_note_article_body_plain_text
  と同じ方式)。
  """
  parts = [article["intro"]]
  for section in article["sections"]:
    parts.append(f'{section["heading"]}\n{section["body"]}')
  parts.append(f'{article["closing_heading"]}\n{article["closing_body"]}')
  return "\n\n".join(parts)


def _render_note_second_article_draft_scene(article):
  """MISSION 043/044: スマホAI下書きテーマのnote記事下書きのHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・note・外部通信への
  アクセスは一切行わない。見出し画像は、あらかじめ用意された既存ファイル
  (NOTE_SECOND_ARTICLE_DRAFT_COVER_RELATIVE_PATH)をそのまま<img>で表示する
  だけで、新規作成・差し替えは行わない。タイトル文字はHTML側で重ねず、画像
  そのものにも焼き込まれていない(プレーンな写真としてそのまま表示する)。
  コピー用ボタンはクライアント側JSのみで完結し、クリップボード操作が失敗
  しても例外を伝播させず、安全なフォールバック表示にする。
  """
  visible_parts = [_paragraphs_html(article["intro"])]
  for section in article["sections"]:
    visible_parts.append(f'<h4 class="note-subheading">{section["heading"]}</h4>')
    visible_parts.append(_paragraphs_html(section["body"]))
  visible_parts.append(f'<h4 class="note-subheading">{article["closing_heading"]}</h4>')
  visible_parts.append(_paragraphs_html(article["closing_body"]))
  visible_body = "".join(visible_parts)

  body_copy_text = _note_second_article_draft_body_plain_text(article)
  checklist_items = "".join(
      f'<li><input type="checkbox" id="note2-check-{i}">'
      f'<label for="note2-check-{i}">{item}</label></li>'
      for i, item in enumerate(article["checklist"])
  )

  return (
      '<section class="note-article-board" aria-label="スマホAI下書きテーマのnote記事下書き">'
      '<div class="fp-notice"><b>社内向けの下書き確認画面です。</b>'
      'noteへの投稿・送信・連携は一切行われません。柴犬社長が内容を確認するための'
      '下書き表示です。</div>'
      f'<p class="fp-theme">対象テーマ：<b>{article["theme"]}</b>'
      '（Pinterest投稿キューの「スマホでAIに下書きを頼む前に確認する3つ」と対応）</p>'
      f'<div class="fp-note fp-note-warn"><b>下書きについて。</b>{article["manual_post_note"]}</div>'
      # MISSION 044: あらかじめ用意された見出し画像をそのまま<img>で表示する。
      # HTML側でタイトル文字を重ねる処理は行わない(画像本体にも文字は焼き
      # 込まれていない、プレーンな写真)。通常のダウンロードリンクのみで
      # 保存し、外部通信・JavaScript必須の処理は行わない。クリックしても
      # note・SNSへの投稿・送信・連携は一切発生しない。
      '<h3 class="fp-section-title">見出し画像</h3>'
      '<div class="note-hero">'
      f'<img class="note-hero-img" src="/static/{NOTE_SECOND_ARTICLE_DRAFT_COVER_RELATIVE_PATH}" '
      f'alt="{article["hero_image_alt"]}">'
      '</div>'
      f'<p class="fp-svg-ratio">横長 {NOTE_SECOND_ARTICLE_DRAFT_COVER_WIDTH}×'
      f'{NOTE_SECOND_ARTICLE_DRAFT_COVER_HEIGHT}'
      '（あらかじめ用意した画像・見出し文字はHTML側で重ねていません）</p>'
      f'<a class="fp-png-download" href="/static/{NOTE_SECOND_ARTICLE_DRAFT_COVER_RELATIVE_PATH}" '
      'download="note-smartphone-ai-draft-cover.png">見出し画像PNGを保存</a>'
      '<p class="fp-png-hint">保存したPNGをnoteの見出し画像として手動アップロードしてください。'
      'このボタンからの投稿・送信・連携は行われません。</p>'
      '<div class="fp-field"><div class="fp-field-head"><h4>タイトル</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note2-title">'
      'コピー</button></div>'
      f'<p id="note2-title">{article["title"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>概要</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note2-overview">'
      'コピー</button></div>'
      f'<p id="note2-overview">{article["overview"]}</p></div>'
      '<h3 class="fp-section-title">記事本文</h3>'
      '<div class="fp-field">'
      '<div class="fp-field-head"><h4>本文</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note2-body-copy">'
      'コピー</button></div>'
      f'<div class="note-article-visible">{visible_body}</div>'
      f'<pre id="note2-body-copy" class="note-article-copy-source">{body_copy_text}</pre>'
      '</div>'
      '<h3 class="fp-section-title">Pinterest用説明文案・altテキスト案</h3>'
      '<div class="fp-field"><div class="fp-field-head"><h4>Pinterest用説明文案</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note2-pinterest-description">'
      'コピー</button></div>'
      f'<p id="note2-pinterest-description">{article["pinterest_description"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>altテキスト案</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note2-alt-text">'
      'コピー</button></div>'
      f'<p id="note2-alt-text">{article["alt_text_draft"]}</p></div>'
      '<h3 class="fp-section-title">投稿前チェックリスト</h3>'
      f'<ul class="fp-checklist">{checklist_items}</ul>'
      # MISSION 043: コピー操作はクライアント側JSのみで完結し、外部通信は行わない。
      # navigator.clipboardが使えない/失敗する環境でも、例外を投げずに安全な
      # 文言へフォールバックする(既存の投稿パッケージ画面と同じ方式)。
      '<script>document.querySelectorAll(".fp-copy-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'const el=document.getElementById(btn.dataset.copyTarget);'
      'if(!el)return;'
      'const original=btn.textContent;'
      'const showResult=ok=>{btn.textContent=ok?"コピーしました":"コピーできませんでした";'
      'setTimeout(()=>{btn.textContent=original;},1800);};'
      'try{'
      'if(navigator.clipboard&&navigator.clipboard.writeText){'
      'navigator.clipboard.writeText(el.textContent).then(()=>showResult(true))'
      '.catch(()=>showResult(false));'
      '}else{showResult(false);}'
      '}catch(e){showResult(false);}'
      '});'
      '});</script>'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の資料です。'
      'note・SNS・楽天ROOMへの投稿・送信・連携は行われません。</p>'
      '</section>'
  )


# MISSION 049: 「AIに聞いても『なんか違う』と感じる人へ」note記事下書き。
# Pinterest投稿キューのai-mismatch-3points投稿と内容が一致する。公開済みの
# NOTE_FIRST_ARTICLE(パソコンでのメール下書き・要約・壁打ち)・
# NOTE_SECOND_ARTICLE_DRAFT(スマホでのAI下書き)とは異なり、AIに質問した後、
# 答えが期待と違ったときに会話そのものを見直す視点に焦点を当てる。note・
# SNSへの投稿・自動投稿・予約投稿・ログイン操作・API連携・外部通信は一切
# 行わない(下書き表示のみ)。将来文面を差し替える場合は、このデータ構造
# (NOTE_THIRD_ARTICLE_DRAFT)を編集するだけでよい。
# MISSION 049.2: 見出し画像を、MISSION 049時点のPillow製イラスト
# (note-ai-mismatch-hero.png。図形中心で一覧性に欠けるとの指摘を受けた)から、
# 社長支給の高品質な写真風ビジュアル(note-ai-mismatch-hero-photo.png。
# 明るい昼間の室内で、スマホを持ち入力内容を見直す手元が主役。木目デスク・
# 白・淡い青を基調とし、夜のデスク・ランプ・観葉植物・顔・ロゴ・読める
# 画面文字は写っていないことを目視確認済み)へ差し替えた。旧イラストファイル
# 自体は削除・上書きしていない(参照しなくなっただけ)。1672x941の横長・
# 文字なしのまま。
NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH = "images/note-ai-mismatch-hero-photo.png"
NOTE_THIRD_ARTICLE_DRAFT_COVER_WIDTH = 1672
NOTE_THIRD_ARTICLE_DRAFT_COVER_HEIGHT = 941

NOTE_THIRD_ARTICLE_DRAFT = {
    "theme": "AIに聞いても「なんか違う」と感じる人へ。話がかみ合わないとき、まず見直す3つ",
    "title": "AIに聞いても「なんか違う」と感じる人へ。話がかみ合わないとき、まず見直す3つ",
    "hero_image_alt": (
        "明るい昼間の室内で、スマートフォンの画面に文字を入力し直している手元のイメージ。"
        "柔らかい光がやわらかく差し込む様子を表現しており、ロゴ・読める文字・人物の顔・"
        "実在サービスの画面は写っていません。"
    ),
    "overview": (
        "AIに質問しても「なんか違う」と感じる場面を想定し、会話がかみ合わないときに見直したい"
        "3つのポイント（目的を先に伝える・前提や条件を足す・一度で終わらせず聞き返す）を、具体例"
        "を交えて紹介する記事の下書きです。既存のメール下書き・スマホでのAI下書き・デスク環境・"
        "AI初心者向け3つの使い方の記事とは内容を重複させず、AIとの対話そのものの質を見直す視点に"
        "焦点を当てています。"
    ),
    "intro": (
        "仕事の合間に、ちょっとした疑問をAIに投げかけてみた。ところが、返ってきた答えを読んで、"
        "思わず「あれ、なんか違うな」とつぶやいてしまった——そんな経験はないでしょうか。\n\n"
        "たとえば、明日の会議で使う資料の構成案が欲しくてAIに相談したのに、返ってきたのは当たり前"
        "のことをふんわりと並べただけの一般論だった。あるいは、一言で答えてほしかっただけなのに、"
        "聞いてもいない背景説明まで長々と続いて、結局欲しかった答えにたどり着くまで時間がかかって"
        "しまった。そんなとき、「AIってこんなものなのか」「自分の聞き方が悪いのかもしれないけれど、"
        "どう直せばいいか分からない」と、モヤモヤした気持ちになった人は少なくないはずです。\n\n"
        "この記事は、そんな「なんか違う」を何度も味わってきた人に向けて書いています。AIとの会話が"
        "かみ合わないと感じたときに見直したい3つのポイント——目的を先に伝える、前提や条件を足す、"
        "一度で終わらせず聞き返す——を、具体例を交えながら紹介します。どれも難しい知識は必要なく、"
        "次にAIに話しかけるときからすぐに試せることばかりです。\n\n"
        "こうしたモヤモヤは、AIの使い方に慣れていない人だけが感じるものではありません。ある程度"
        "使い慣れてきたつもりでも、忙しいときほど指示が雑になり、結果として「なんか違う」を繰り"
        "返してしまうことは珍しくないのです。自分の聞き方を一つひとつ振り返る余裕がないときこそ、"
        "この3つのポイントをチェックリストのように思い出してもらえたらと思います。"
    ),
    "sections": [
        {
            "heading": "1. 目的を先に伝える",
            "body": (
                "AIに何かを頼むとき、多くの人はまず「やってほしいこと」だけを伝えます。たとえば"
                "「この文章を短くして」「このデータをまとめて」といった具合です。ところが、AIに"
                "とっては「何のために短くするのか」「まとめた結果を誰がどう使うのか」が分からない"
                "まま作業することになり、こちらが期待していた仕上がりと違う結果が返ってきやすく"
                "なります。\n\n"
                "たとえば、「このメモを短くまとめてください」とだけ頼むと、AIはどの情報を残すべき"
                "か自分で判断するしかありません。結果として、あなたが重要だと思っていた部分が削ら"
                "れてしまうことがあります。ここに「上司への報告用に、決定事項だけ分かるように短く"
                "してください」と目的を添えるだけで、AIは残すべき情報の優先順位を理解しやすくなり、"
                "仕上がりがぐっと変わってきます。\n\n"
                "目的を伝えるときは、難しく考える必要はありません。「誰に」「何のために」「どんな"
                "場面で使うのか」を、ひとこと添えるだけで十分です。たとえば「取引先に送るので、"
                "丁寧な言い回しにしてください」「自分用のメモなので、要点だけ簡潔にまとめてくださ"
                "い」のように、使う相手や場面を一言加えるだけで、AIが選ぶ言葉づかいや情報の取捨"
                "選択が大きく変わります。「なんか違う」と感じたときほど、実は目的を伝え忘れている"
                "ことが多いものです。\n\n"
                "目的を伝える習慣がついてくると、頼み方そのものが少しずつ変わってきます。「これを"
                "やって」ではなく、「これを、こういう理由でやってほしい」という形が自然に口から出る"
                "ようになると、AIに限らず、人に何かを頼むときの伝え方も整理されやすくなるという"
                "副次的な効果を感じる人もいます。最初は面倒に感じても、決まり文句のように「これは"
                "何のために使うか」を一言添える癖をつけてみると、次第に苦にならなくなっていきます。"
                "\n\n"
                "もう一つの例を挙げると、企画のアイデア出しを頼むときにも、目的を伝える効果は大きく"
                "現れます。「新商品のアイデアを5つ考えて」とだけ頼むと、AIはごく一般的な案を並べる"
                "だけになりがちです。一方で「20代の一人暮らし向けに、忙しい平日でも続けやすい商品の"
                "アイデアを5つ考えて」のように、想定する相手や状況まで伝えると、案の方向性がぐっと"
                "絞り込まれ、そのまま使える案が増えていきます。"
            ),
        },
        {
            "heading": "2. 前提や条件を足す",
            "body": (
                "目的を伝えても、まだ「なんか違う」と感じることがあります。その場合、次に見直し"
                "たいのが、前提や条件が足りているかどうかです。AIは、あなたの頭の中にある状況や"
                "制約を、勝手に読み取ってくれるわけではありません。伝えていない情報は、存在しない"
                "ものとして扱われてしまいます。\n\n"
                "たとえば、「来週の打ち合わせの案内メールを書いてください」とだけ頼むと、AIはごく"
                "一般的な案内文を作ります。しかし実際には、「オンラインなのか対面なのか」「参加者は"
                "社内だけなのか取引先も含むのか」「すでに一度延期している打ち合わせなのか」といった"
                "条件によって、書くべき文章は大きく変わるはずです。こうした条件を伝えないまま「なん"
                "か違う」と感じてしまうのは、ある意味当然のことなのです。\n\n"
                "コツは、自分が当たり前だと思っている前提こそ、あえて言葉にしてみることです。「オン"
                "ライン開催で、取引先の方も含めて5名が参加します」「前回一度延期しているので、その旨"
                "も一言添えてください」のように、状況を具体的に伝えるほど、AIの返答はあなたが本当に"
                "欲しかった内容に近づいていきます。最初の指示が短すぎたと感じたら、まずは前提条件を"
                "1つか2つ足してみることから始めてみてください。\n\n"
                "どこまで前提を伝えればよいか迷ったときは、「自分が初めて会う人にこの作業を頼むとし"
                "たら、何を説明しておくか」を想像してみると考えやすくなります。相手の名前も知らない"
                "新人アルバイトの方に仕事を頼むときには、状況や背景をある程度説明するはずです。AIに"
                "対しても、同じくらいの気持ちで前提を添えてみると、抜け漏れに気づきやすくなります。"
                "\n\n"
                "前提を足しすぎて、指示が長くなりすぎるのではと心配になる人もいるかもしれません。"
                "ただ、実際には箇条書きのように短い言葉を並べるだけでも十分です。「オンライン」"
                "「取引先含む5名」「一度延期済み」のように、単語を並べるだけでも、AIはそこから必要な"
                "情報を読み取ってくれます。文章として整える必要はなく、思いついた条件をそのまま"
                "並べるくらいの気軽さで構いません。"
            ),
        },
        {
            "heading": "3. 一度で終わらせず聞き返す",
            "body": (
                "目的も前提も伝えたのに、それでも「なんか違う」と感じることはあります。ここで大切"
                "なのは、一度の返答で会話を終わらせないことです。AIとのやり取りは、一往復で完成さ"
                "せるものではなく、返ってきた答えを見ながら「ここをもう少し」と伝え直す、対話に近い"
                "使い方をすると、結果が安定しやすくなります。\n\n"
                "たとえば、AIが作った文章の言い回しが硬すぎると感じたら、「もう少し柔らかい言い方に"
                "してください」と伝え直すだけで、印象はかなり変わります。情報が足りないと感じたら、"
                "「◯◯についても触れてください」と付け加えるだけで、必要な内容を補ってもらえます。"
                "一度目の答えを「正解」か「不正解」かで判断するのではなく、「たたき台」として受け"
                "取り、そこから育てていくという感覚を持つと、AIとのやり取りがぐっと楽になります。"
                "\n\n"
                "聞き返すときは、何が違うのかをできるだけ具体的に伝えることがポイントです。「なんか"
                "違う」とだけ伝えても、AIはどこを直せばよいか判断できません。「もっと短くしてほし"
                "い」「もっと具体的な例がほしい」「この部分は不要」のように、直してほしい点を一言"
                "添えるだけで、次の返答は驚くほど近づいてきます。かみ合わないと感じたときほど、一度"
                "で諦めず、もう一往復だけ会話を重ねてみてください。\n\n"
                "聞き返すことに、遠慮はいりません。AIは同じ質問を何度言い直しても、面倒くさがった"
                "り、態度を変えたりすることはありません。人に何度も聞き返すのは気が引けても、AIが"
                "相手であれば、納得がいくまで気兼ねなくやり取りを重ねられます。この気軽さこそ、AIと"
                "の会話ならではの強みだと捉えると、聞き返す一往復が、それほど大きな負担には感じられ"
                "なくなるはずです。\n\n"
                "たとえば要約を頼んだときに、思っていたより大事な部分が抜け落ちていたとします。その"
                "場合も、最初からやり直す必要はありません。「さきほどの要約に、◯◯についての一文を"
                "足してください」と伝えるだけで、AIはそれまでのやり取りを踏まえて調整してくれます。"
                "ゼロから頼み直すのではなく、直前の答えを土台にして少しずつ整えていく、という感覚を"
                "持つと、聞き返すことへの抵抗感も薄れていきます。"
            ),
        },
        {
            "heading": "3つを試しても違うと感じたら",
            "body": (
                "目的を伝え、前提を足し、聞き返しても、それでも「なんか違う」が解消しないことは"
                "あります。そんなときは、無理にAIとのやり取りだけで解決しようとしなくてもかまいませ"
                "ん。専門性が高すぎる話題や、最新の状況が絡む話題、答えが一つに定まらない相談ごとで"
                "は、AIよりも、詳しい人に直接聞いたほうが早いこともあります。\n\n"
                "また、時間を置いてから聞き直すだけで、意外とすんなり欲しい答えにたどり着くこともあ"
                "ります。一度目のやり取りで頭の中が整理されて、二度目に聞くときには、自分でも気づか"
                "ないうちに目的や前提がはっきりしていることがあるからです。「なんか違う」と感じても"
                "焦らず、少し時間を置いてから、もう一度話しかけてみるのも一つの手です。\n\n"
                "大切なのは、「AIとの会話がかみ合わない=自分の使い方が全部間違っている」と思い込ま"
                "ないことです。目的・前提・聞き返しの3つを意識したうえでも解決しない場合は、それは"
                "単にその話題がAIに向いていなかっただけかもしれません。3つの見直しは、うまくいく"
                "確率を上げるための工夫であって、絶対に解決する魔法ではない、という前提で気楽に使って"
                "みてください。\n\n"
                "それでも、多くの場合は目的・前提・聞き返しの3つを一つずつ確認していくだけで、"
                "「なんか違う」と感じる回数はかなり減っていきます。うまくいかない例外があることを"
                "頭の片隅に置いておきつつ、まずはこの3つを日々のやり取りの中で試してみることから"
                "始めてみてください。試しているうちに、自分なりの「これを聞くときはここまで伝える"
                "とうまくいく」という感覚が、少しずつ身についてくるはずです。その感覚さえつかめれば、"
                "毎回3つすべてを意識しなくても、自然と「なんか違う」に出会う回数そのものが減って"
                "いきます。"
            ),
        },
    ],
    "closing_heading": "まとめ",
    "closing_body": (
        "この記事では、AIとの会話がかみ合わないと感じたときに見直したい3つのポイントとして、目的"
        "を先に伝える・前提や条件を足す・一度で終わらせず聞き返す、を紹介しました。どれも、AIに"
        "完璧な指示を出すためのテクニックというより、人に何かを頼むときと同じように、相手が判断"
        "しやすい材料を渡してあげる、という考え方に近いものです。\n\n"
        "次にAIに何かを聞いて「なんか違う」と感じたときは、AIの性能を疑う前に、この3つのうちどれ"
        "か1つでも見直してみてください。ほんの一言を加えるだけで、それまでモヤモヤしていたやり"
        "取りが、驚くほどスムーズになることがあります。\n\n"
        "最初からすべてを完璧にこなそうとしなくても大丈夫です。まずは次に「なんか違う」と感じた"
        "瞬間に、この記事のどれか一つを思い出してみてください。その積み重ねが、AIとの会話を少し"
        "ずつ、自分にとって使いやすいものに変えていってくれるはずです。"
    ),
    "pinterest_description": (
        "AIに聞いても「なんか違う」と感じたときに見直したい3つのポイントをnote記事でまとめました。"
        "目的を先に伝える・前提や条件を足す・一度で終わらせず聞き返す、について具体例を交えて紹介"
        "しています。特定の商品の紹介やレビューは含みません。"
    ),
    "alt_text_draft": (
        "AIに聞いても「なんか違う」と感じる人へ、というテーマのnote記事用altテキスト案。会話が"
        "かみ合わないときに見直したい3項目（目的を先に伝える・前提や条件を足す・一度で終わらせず"
        "聞き返す）を要約した説明文。note記事本体の見出し画像は明るい昼間の雰囲気でスマホに入力し"
        "直す手元を主役にしており、Pinterest投稿キューには別途、縦長でタイトルを焼き込んだ画像を"
        "用意しています。"
    ),
    # MISSION 054: 2026年9月12日までに柴犬社長が手動でnoteへ貼り付けて公開済み。
    # 実際に公開されたタイトルは、下書き時点の案から一部変更されている
    # （"theme"/"title"を参照）。以下は公開時に使用した内容の記録である。
    "manual_post_note": (
        "この記事は柴犬社長が手動でnoteへ貼り付けて公開済みです。"
        "実際の記事URL：https://note.com/legal_crow9879/n/nb2a21a842387 "
        "note・SNSへの自動投稿・予約投稿・ログイン操作・API連携・外部通信は"
        "一切行いません。"
    ),
    "checklist": [
        "本文が4,500〜5,500字の目安に収まっているか確認した",
        "「必ず」「絶対」等の断定表現や、成果を保証する表現が含まれていないか確認した",
        "実体験でないことを実体験のように書いていないか確認した",
        "実在サービス画面・商品名・価格・在庫・ランキング・成果数値・レビューを記載していないか"
        "確認した",
        "楽天ROOMの商品紹介・リンクを含めていないか確認した",
        "公開済みのメール下書き・スマホAI下書き・デスク環境・AI初心者3選の記事と内容が重複して"
        "いないか確認した",
        "Pinterest用説明文案が500字以内に収まっているか確認した",
        "見出し画像に日本語文字・ロゴ・実在サービスの画面・人物の顔が写っていないか確認した",
        "noteアカウントにログインした状態で、手動で貼り付けて公開できる準備ができている",
    ],
}


def _note_third_article_draft_body_plain_text(article):
  """NOTE_THIRD_ARTICLE_DRAFTの本文(導入〜まとめ)のプレーンテキストを組み立てる。

  概要・Pinterest説明文案・altテキスト案・チェックリストは含めない。段落の
  区切りは実際の改行(\\n\\n)で表現し、表示用マークアップと文字数検証の両方で
  同じテキストを共有する(NOTE_SECOND_ARTICLE_DRAFT用の
  _note_second_article_draft_body_plain_textと同じ方式)。
  """
  parts = [article["intro"]]
  for section in article["sections"]:
    parts.append(f'{section["heading"]}\n{section["body"]}')
  parts.append(f'{article["closing_heading"]}\n{article["closing_body"]}')
  return "\n\n".join(parts)


def _render_note_third_article_draft_scene(article):
  """MISSION 049: AIとの会話の見直しテーマのnote記事のHTMLを組み立てる。

  MISSION 054: この記事は2026年9月12日までに公開済みとなったため、関数名・
  データ構造名(NOTE_THIRD_ARTICLE_DRAFT)は変更していないが、画面表示は
  「下書き」ではなく「公開済みの記録」として組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・note・外部通信への
  アクセスは一切行わない。見出し画像は、あらかじめ生成された既存ファイル
  (NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH)をそのまま<img>で表示する
  だけで、タイトル文字はHTML側で重ねない(画像そのものにも文字は焼き込まれて
  いない)。コピー用ボタンはクライアント側JSのみで完結し、クリップボード操作
  が失敗しても例外を伝播させず、安全なフォールバック表示にする。
  """
  visible_parts = [_paragraphs_html(article["intro"])]
  for section in article["sections"]:
    visible_parts.append(f'<h4 class="note-subheading">{section["heading"]}</h4>')
    visible_parts.append(_paragraphs_html(section["body"]))
  visible_parts.append(f'<h4 class="note-subheading">{article["closing_heading"]}</h4>')
  visible_parts.append(_paragraphs_html(article["closing_body"]))
  visible_body = "".join(visible_parts)

  body_copy_text = _note_third_article_draft_body_plain_text(article)
  checklist_items = "".join(
      f'<li><input type="checkbox" id="note3-check-{i}">'
      f'<label for="note3-check-{i}">{item}</label></li>'
      for i, item in enumerate(article["checklist"])
  )

  return (
      '<section class="note-article-board" aria-label="AIとの会話の見直しテーマのnote記事（公開済み）">'
      '<div class="fp-notice"><b>公開済み記事の記録画面です。</b>'
      'この画面からのnoteへの投稿・送信・連携は一切行われません。柴犬社長が実際に'
      '公開した内容を、そのまま記録として表示しています。</div>'
      f'<p class="fp-theme">対象テーマ：<b>{article["theme"]}</b>'
      '（Pinterest投稿キューの「AIが「なんか違う」ときに見直す3つ」と対応）</p>'
      f'<div class="fp-note fp-note-warn"><b>公開状況について。</b>{article["manual_post_note"]}</div>'
      '<h3 class="fp-section-title">見出し画像</h3>'
      '<div class="note-hero">'
      f'<img class="note-hero-img" src="/static/{NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH}" '
      f'alt="{article["hero_image_alt"]}">'
      '</div>'
      f'<p class="fp-svg-ratio">横長 {NOTE_THIRD_ARTICLE_DRAFT_COVER_WIDTH}×'
      f'{NOTE_THIRD_ARTICLE_DRAFT_COVER_HEIGHT}'
      '（あらかじめ用意した画像・見出し文字はHTML側で重ねていません）</p>'
      f'<a class="fp-png-download" href="/static/{NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH}" '
      'download="note-ai-mismatch-hero-photo.png">見出し画像PNGを保存</a>'
      '<p class="fp-png-hint">保存したPNGをnoteの見出し画像として手動アップロードしてください。'
      'このボタンからの投稿・送信・連携は行われません。</p>'
      '<div class="fp-field"><div class="fp-field-head"><h4>タイトル</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note3-title">'
      'コピー</button></div>'
      f'<p id="note3-title">{article["title"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>概要</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note3-overview">'
      'コピー</button></div>'
      f'<p id="note3-overview">{article["overview"]}</p></div>'
      '<h3 class="fp-section-title">記事本文</h3>'
      '<div class="fp-field">'
      '<div class="fp-field-head"><h4>本文</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note3-body-copy">'
      'コピー</button></div>'
      f'<div class="note-article-visible">{visible_body}</div>'
      f'<pre id="note3-body-copy" class="note-article-copy-source">{body_copy_text}</pre>'
      '</div>'
      '<h3 class="fp-section-title">Pinterest用説明文案・altテキスト案</h3>'
      '<div class="fp-field"><div class="fp-field-head"><h4>Pinterest用説明文案</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note3-pinterest-description">'
      'コピー</button></div>'
      f'<p id="note3-pinterest-description">{article["pinterest_description"]}</p></div>'
      '<div class="fp-field"><div class="fp-field-head"><h4>altテキスト案</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="note3-alt-text">'
      'コピー</button></div>'
      f'<p id="note3-alt-text">{article["alt_text_draft"]}</p></div>'
      '<h3 class="fp-section-title">投稿前チェックリスト</h3>'
      f'<ul class="fp-checklist">{checklist_items}</ul>'
      # MISSION 049: コピー操作はクライアント側JSのみで完結し、外部通信は行わない。
      # navigator.clipboardが使えない/失敗する環境でも、例外を投げずに安全な
      # 文言へフォールバックする(既存の投稿パッケージ画面と同じ方式)。
      '<script>document.querySelectorAll(".fp-copy-btn").forEach(btn=>{'
      'btn.addEventListener("click",()=>{'
      'const el=document.getElementById(btn.dataset.copyTarget);'
      'if(!el)return;'
      'const original=btn.textContent;'
      'const showResult=ok=>{btn.textContent=ok?"コピーしました":"コピーできませんでした";'
      'setTimeout(()=>{btn.textContent=original;},1800);};'
      'try{'
      'if(navigator.clipboard&&navigator.clipboard.writeText){'
      'navigator.clipboard.writeText(el.textContent).then(()=>showResult(true))'
      '.catch(()=>showResult(false));'
      '}else{showResult(false);}'
      '}catch(e){showResult(false);}'
      '});'
      '});</script>'
      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の資料です。'
      'note・SNS・楽天ROOMへの投稿・送信・連携は行われません。</p>'
      '</section>'
  )


# MISSION 066: 運用司令室(/command-center)。
#
# 資料室(company_knowledge/)と担当チーム(company_knowledge/departments/)で
# 定めた運用ルールを、毎日の確認・判断・記録として見える化するローカル専用
# 画面。楽天ROOM・楽天アフィリエイト・note・Pinterest・Threadsへのアクセス・
# ログイン・投稿・送信・削除は一切行わない。実数値の初期値は空欄で開始し、
# 実績・売上・反応を捏造しない(company_knowledge/00_company_rules.mdの
# 「数字や実績を推測で入力しない」に対応)。入力内容はブラウザのlocalStorage
# にのみ保存し、このアプリのDB・バックアップへは一切保存しない。ブラウザや
# 端末を変えたり、ブラウザのデータを消去すると内容は失われる。
#
# 「今日の確認ボード」の各媒体・「担当チーム状況」の5担当・「判断メモ」の
# 媒体選択肢は、company_knowledge/01_channels.md・04_metrics.md・
# departments/*.md の内容と矛盾しないように保つ。担当カードの説明文は
# departments/*.md の役割説明の要約であり、実在の人間や自動稼働のプログラム
# ではなく「仮想チーム」であることを明記する。
COMMAND_CENTER_CHECK_CATEGORIES = [
    {
        "key": "room",
        "label": "楽天ROOM",
        "confirm_label": "確認済み",
        "fields": [
            ("item_count", "商品数"),
            ("hearts", "♡"),
            ("comments", "コメント"),
        ],
    },
    {
        "key": "affiliate",
        "label": "楽天アフィリエイト",
        "confirm_label": "確認済み",
        "fields": [
            ("clicks", "クリック数"),
            ("sales", "売上"),
            ("commission", "成果報酬"),
        ],
    },
    {
        "key": "note",
        "label": "note",
        "confirm_label": "確認済み",
        "fields": [
            ("pv", "PV"),
            ("likes", "スキ"),
            ("followers", "フォロワー"),
        ],
    },
    {
        "key": "pinterest",
        "label": "Pinterest",
        "confirm_label": "確認済み",
        "fields": [
            ("monthly_views", "月間表示"),
            ("saves", "保存"),
            ("link_clicks", "リンククリック"),
        ],
    },
    {
        "key": "threads",
        "label": "Threads",
        "confirm_label": "20時投稿を確認した",
        "fields": [],
    },
]

# company_knowledge/departments/*.md の内容と矛盾しない範囲で要約した説明文。
# 各担当は「仮想チーム」であり、提案・下書き・記録までを担う(実際の外部公開・
# 送信・ログイン・削除は行わない)ことを、カードの説明文とは別に明記する。
COMMAND_CENTER_DEPARTMENT_CARDS = [
    {
        "key": "operations_lead",
        "label": "運用責任者",
        "summary": "各担当の状況を横断的に確認し、今日・今週の確認項目と優先順位を"
                   "整理します。投稿の最終実行は行いません。",
    },
    {
        "key": "room",
        "label": "ROOM担当",
        "summary": "商品数・♡・コメントを確認し、反応のあるジャンルを候補として"
                   "提案します。実際の投稿は行いません。",
    },
    {
        "key": "note",
        "label": "note担当",
        "summary": "記事候補や公開済み記事のPV・スキを整理し、次のテーマ候補を"
                   "まとめます。記事の公開は行いません。",
    },
    {
        "key": "pinterest",
        "label": "Pinterest担当",
        "summary": "Pinの表示・保存・リンククリックを記録し、note記事などへの"
                   "導線候補を提案します。Pinの投稿は行いません。",
    },
    {
        "key": "analytics",
        "label": "分析担当",
        "summary": "媒体ごとの数字を比較し、確認済みの事実と推測を分けて週次の"
                   "判断案を作ります。",
    },
]

# company_knowledge/05_decision_log.md の様式(日付・媒体・観測した数字・判断・
# 次にすること・保留理由)に対応する媒体の選択肢。01_channels.mdの並びに揃える。
COMMAND_CENTER_DECISION_MEDIA_OPTIONS = [
    "楽天ROOM", "楽天アフィリエイト", "note", "Pinterest", "Threads",
]

# MISSION 080: 「本日の運用記録」用の媒体選択肢。判断メモ(上記)とは別に、
# 部署をまたぐ引き継ぎ(彩の担当)を記録できるよう「共通」を追加する。
COMMAND_CENTER_DAILY_RECORD_MEDIA_OPTIONS = COMMAND_CENTER_DECISION_MEDIA_OPTIONS + ["共通"]

# MISSION 080: 「本日の運用記録」の種別。company_knowledge/00_company_rules.md
# の「提案・下書き・記録まで。最終承認と外部公開は利用者本人」という範囲に
# 沿い、実行・公開そのものを表す種別は置かない(「投稿済み」は、利用者が
# 実際に投稿した"事実"を記録するだけで、この画面から投稿を行うものでは
# ない)。
COMMAND_CENTER_DAILY_RECORD_TYPES = ["確認", "下書き", "投稿済み", "数字記録", "承認待ち"]

# MISSION 080: 運用司令室の「本日の運用記録」とAIオフィスの実績反映は、
# 同じlocalStorageキーを読み書きする。キー文字列がずれると連携できなく
# なるため、Python側の定数を両画面のJSへ埋め込んで一致させる。
# MISSION 088: 「手動投稿を完了した」・運用記録の保存操作では、同じ内容を
# このMac上のアプリ内DB(/api/dashboard/daily-records、127.0.0.1限定・
# 無認証のローカルAPI)へもベストエフォートで書き込む。外部サービスへの
# 送信・ログインは行わない。
AI_OFFICE_COMMAND_CENTER_STORAGE_PREFIX = "ai-hive-command-center:"
AI_OFFICE_DAILY_RECORD_STORAGE_KEY = (
    AI_OFFICE_COMMAND_CENTER_STORAGE_PREFIX + "daily-record-log"
)
ROOM_CANDIDATE_STORAGE_PREFIX = "ai-hive-room-candidate:"
NOTE_CANDIDATE_STORAGE_PREFIX = "ai-hive-note-candidate:"

DATA_STORAGE_LOCAL_NOTE = (
    "運用記録・投稿候補をこのアプリに保存します。保存先はこのMac上の"
    "アプリ内データ（SQLite）で、外部のサービスへは送信されません。"
)


def _render_work_ledger_section():
  """運用司令室の「作業台帳」セクション(MISSION 090)。

  Pinterest・note・楽天ROOMなど媒体を問わず、利用者が手動で作業を追加できる
  画面。保存先はこのMac上のアプリ内データ(SQLite、/api/dashboard/
  work-items)のみで、外部サービスへの投稿・送信・ログイン・自動ブラウザ
  操作は一切行わない。最初に表示する項目は媒体・作業名・担当社員・状態の
  4つだけに絞り、優先度などの詳細項目は<details>で折りたたむ。作業の完了は、
  利用者が明示的に「完了にする」を押した場合だけDBに保存する(外部投稿の
  有無を推測・自動判定しない)。

  既存の楽天ROOM投稿候補(post_candidates)のうち「今日・今週」に割り当て
  済みの未完了候補は、ここで新規に作り直すのではなく、サーバー側
  (dashboard_db.sync_candidate_work_items)で自動的に連携され、この一覧にも
  表示される(出どころ「候補連携」の行は、ここでは削除も完了操作もできる)。
  """
  staff_options = "".join(
      f'<option value="{key}">{AI_OFFICE_STAFF_BY_KEY[key]["name"]}</option>'
      for key in AI_OFFICE_ALL_STAFF_KEYS
  )
  media_options = "".join(
      f'<option value="{m}">{m}</option>'
      for m in COMMAND_CENTER_DAILY_RECORD_MEDIA_OPTIONS
  )
  return (
      '<section class="cc-work-ledger" aria-label="作業台帳" '
      'id="cc-work-ledger">'
      '<h2 class="cc-section-title">作業台帳</h2>'
      '<p class="cc-decision-note">媒体を問わず、今日・今週やろうとしている'
      '作業をここに記録できます。保存先はこのMac上のアプリ内データ'
      '（SQLite）だけで、外部サービスへの投稿・送信・ログイン・自動操作は'
      '一切行いません。作業の完了は、実際に完了したときに「完了にする」を'
      '押した場合だけ記録されます（自動では完了になりません）。楽天ROOM'
      'の投稿候補で「今日・今週」に設定した未完了候補は、自動的にこの'
      '一覧にも連携されます。</p>'
      '<div class="cc-decision-box">'
      '<div class="cc-decision-fields">'
      '<div><label for="wl-media">媒体</label>'
      f'<select id="wl-media"><option value="">選択してください</option>'
      f'{media_options}</select></div>'
      '<div><label for="wl-task-name">作業名</label>'
      '<input type="text" id="wl-task-name" maxlength="200" '
      'placeholder="例：新商品のPin画像を作る"></div>'
      '</div>'
      '<div class="cc-decision-fields">'
      '<div><label for="wl-assignee">担当社員</label>'
      f'<select id="wl-assignee"><option value="">選択してください</option>'
      f'{staff_options}</select></div>'
      '<div><label for="wl-status">状態</label>'
      '<select id="wl-status">'
      '<option value="today">今日</option>'
      '<option value="week">今週</option>'
      '<option value="hold">保留</option>'
      '</select></div>'
      '</div>'
      '<details class="cc-work-ledger-detail">'
      '<summary>詳細項目（任意）</summary>'
      '<div class="cc-decision-fields">'
      '<div><label for="wl-priority">優先度（数字が小さいほど優先・1〜9）'
      '</label>'
      '<input type="number" id="wl-priority" min="1" max="9" step="1" '
      'placeholder="5"></div>'
      '</div>'
      '</details>'
      '<button type="button" class="cc-decision-add-btn" id="wl-add-btn">'
      'この作業を作業台帳に追加する</button>'
      '<p class="cc-decision-note" id="wl-add-result" aria-live="polite">'
      '</p>'
      '<div class="cc-decision-log-list" id="cc-work-ledger-list">'
      '<p class="cc-decision-log-empty" id="cc-work-ledger-empty">まだ'
      '作業台帳に登録された作業はありません。</p>'
      '</div>'
      '</div>'
      '<script>(function(){'
      f'var STAFF_NAMES={json.dumps({k: AI_OFFICE_STAFF_BY_KEY[k]["name"] for k in AI_OFFICE_ALL_STAFF_KEYS}, ensure_ascii=False)};'
      f'var STATUS_LABELS={json.dumps(WORK_ITEM_STATUS_LABELS, ensure_ascii=False)};'
      'var mediaEl=document.querySelector("#wl-media");'
      'var taskNameEl=document.querySelector("#wl-task-name");'
      'var assigneeEl=document.querySelector("#wl-assignee");'
      'var statusEl=document.querySelector("#wl-status");'
      'var priorityEl=document.querySelector("#wl-priority");'
      'var addBtn=document.querySelector("#wl-add-btn");'
      'var resultEl=document.querySelector("#wl-add-result");'
      'var listEl=document.querySelector("#cc-work-ledger-list");'
      'var emptyEl=document.querySelector("#cc-work-ledger-empty");'
      'function escapeHtml(s){'
      'return String(s==null?"":s)'
      '.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");'
      '}'
      'function renderList(items){'
      'listEl.querySelectorAll(".cc-work-ledger-item").forEach(function(el){el.remove();});'
      'if(!items||items.length===0){'
      'emptyEl.hidden=false;'
      'return;'
      '}'
      'emptyEl.hidden=true;'
      'items.forEach(function(item){'
      'var div=document.createElement("div");'
      'div.className="cc-decision-log-entry cc-work-ledger-item";'
      'var ownerName=STAFF_NAMES[item.assignee]||item.assignee;'
      'var statusLabel=STATUS_LABELS[item.status]||item.status;'
      'var html="<div><b>媒体：</b>"+escapeHtml(item.media)+"</div>"+'
      '"<div><b>作業名：</b>"+escapeHtml(item.task_name)+"</div>"+'
      '"<div><b>担当社員：</b>"+escapeHtml(ownerName)+"</div>"+'
      '"<div><b>状態：</b>"+escapeHtml(statusLabel)+"</div>";'
      'div.innerHTML=html;'
      'if(item.status!=="done"){'
      'var btn=document.createElement("button");'
      'btn.type="button";'
      'btn.className="wl-complete-btn";'
      'btn.textContent="完了にする";'
      'btn.addEventListener("click",function(){'
      'btn.disabled=true;'
      'window.fetch("/api/dashboard/work-items",{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify({id:item.id})'
      '}).then(function(){return loadList();}).catch(function(){'
      'btn.disabled=false;'
      '});'
      '});'
      'div.appendChild(btn);'
      '}'
      'listEl.appendChild(div);'
      '});'
      '}'
      'function loadList(){'
      'if(typeof window.fetch!=="function")return Promise.resolve();'
      'return window.fetch("/api/dashboard/work-items")'
      '.then(function(res){return res.json();})'
      '.then(function(data){'
      'renderList((data&&data.workItems)||[]);'
      '}).catch(function(){});'
      '}'
      'if(addBtn){'
      'addBtn.addEventListener("click",function(){'
      'var payload={'
      'media:mediaEl.value,'
      'taskName:taskNameEl.value,'
      'assignee:assigneeEl.value,'
      'status:statusEl.value,'
      'priority:priorityEl.value'
      '};'
      'if(!payload.media||!payload.taskName||!payload.assignee){'
      'resultEl.textContent="媒体・作業名・担当社員は必須です。";'
      'return;'
      '}'
      'addBtn.disabled=true;'
      'resultEl.textContent="保存しています…";'
      'window.fetch("/api/dashboard/work-items",{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify(payload)'
      '}).then(function(res){return res.json();}).then(function(data){'
      'if(data&&data.inserted){'
      'resultEl.textContent="作業台帳に追加しました。";'
      'taskNameEl.value="";'
      '}else{'
      'resultEl.textContent="同じ内容がすでに本日分として登録済みです。";'
      '}'
      'addBtn.disabled=false;'
      'return loadList();'
      '}).catch(function(){'
      'resultEl.textContent='
      '"保存できませんでした。しばらくしてからもう一度お試しください。";'
      'addBtn.disabled=false;'
      '});'
      '});'
      '}'
      'loadList();'
      '})();</script>'
      '</section>'
  )


def _render_data_storage_section():
  """運用司令室の「データ保存」セクションのHTML+JSを返す。

  MISSION 088: ブラウザのlocalStorageにある運用記録・投稿候補を、利用者が
  明示的に押す操作でこのMac上のアプリ内DBへ取り込めるようにする。
  localStorage側のデータは削除しない。何度実行しても、同じ内容は重複して
  保存されない(サーバー側のdedup_keyで判定)。外部サービスへの送信・
  ログイン・API通信は一切行わない(/api/dashboard/* は同一オリジンの
  ローカルAPI)。
  """
  return (
      '<section class="cc-data-storage" aria-label="データ保存" '
      'id="cc-data-storage">'
      '<h2>データ保存</h2>'
      f'<p class="cc-data-storage-note">{DATA_STORAGE_LOCAL_NOTE}</p>'
      '<div class="cc-data-storage-counts">'
      '<p>このブラウザに保存されている運用記録：'
      '<b id="cc-local-record-count">0</b>件</p>'
      '<p>このブラウザに保存されている投稿候補：'
      '<b id="cc-local-candidate-count">0</b>件</p>'
      '</div>'
      '<button type="button" id="cc-migrate-btn">'
      'このブラウザの記録をこのアプリに保存する</button>'
      '<p class="cc-data-storage-result" id="cc-migrate-result" '
      'aria-live="polite"></p>'
      '<p class="cc-data-storage-hint">「手動投稿を完了した」を押したときや、'
      'このページで本日の運用記録を保存したときは、このボタンを押さなくても'
      '自動的にこのアプリ内データへ保存されます。このボタンは、それより前に'
      '入力していた分をまとめて取り込みたいときに使います。</p>'
      '<script>(function(){'
      f'var RECORD_KEY={json.dumps(AI_OFFICE_DAILY_RECORD_STORAGE_KEY, ensure_ascii=False)};'
      f'var ROOM_PREFIX={json.dumps(ROOM_CANDIDATE_STORAGE_PREFIX, ensure_ascii=False)};'
      f'var NOTE_PREFIX={json.dumps(NOTE_CANDIDATE_STORAGE_PREFIX, ensure_ascii=False)};'
      'function safeGet(key){'
      'try{return window.localStorage.getItem(key);}catch(e){return null;}'
      '}'
      'function collectLocalRecords(){'
      'try{'
      'var raw=safeGet(RECORD_KEY);'
      'var list=raw?JSON.parse(raw):[];'
      'return Array.isArray(list)?list:[];'
      '}catch(e){return [];}'
      '}'
      # MISSION 088: localStorageのキー一覧から、ROOM・noteの候補
      # (ai-hive-room-candidate:<日付>:<枠番号> / ai-hive-note-candidate:
      # <日付>:<枠番号>)だけを拾い、DBのcandidates形式へ変換する。
      # 保存されている内容をそのまま読み取るだけで、外部への取得・送信は
      # 行わない。
      'function collectLocalCandidates(){'
      'var candidates=[];'
      'try{'
      'for(var i=0;i<window.localStorage.length;i++){'
      'var key=window.localStorage.key(i);'
      'if(!key)continue;'
      'var media=null;'
      'if(key.indexOf(ROOM_PREFIX)===0)media="楽天ROOM";'
      'else if(key.indexOf(NOTE_PREFIX)===0)media="note";'
      'else continue;'
      'var rest=key.slice((media==="楽天ROOM"?ROOM_PREFIX:NOTE_PREFIX).length);'
      'var parts=rest.split(":");'
      'if(parts.length<2)continue;'
      'var targetDate=parts[0];'
      'var slot=Number(parts[1]);'
      'var raw=safeGet(key);'
      'var data=null;'
      'try{data=raw?JSON.parse(raw):null;}catch(e){data=null;}'
      'if(!data)continue;'
      'if(media==="楽天ROOM"){'
      'if(!data.genre&&!data.productName)continue;'
      'candidates.push({'
      'targetDate:targetDate,media:media,slot:slot,'
      'genre:data.genre||"",productName:data.productName||"",'
      'url:data.productUrl||"",intro:data.intro||"",'
      'hashtags:data.hashtags||[],'
      'manualChecked:Boolean(data.manualChecked),'
      'manualPosted:Boolean(data.postInRoom)'
      '});'
      '}else{'
      'if(!data.title)continue;'
      'candidates.push({'
      'targetDate:targetDate,media:media,slot:slot,'
      'genre:"",productName:data.title||"",url:"",'
      'intro:data.intro||"",hashtags:data.hashtags||[],'
      'manualChecked:Boolean(data.manualChecked),'
      'manualPosted:Boolean(data.postInNote)'
      '});'
      '}'
      '}'
      '}catch(e){}'
      'return candidates;'
      '}'
      'function updateLocalCounts(){'
      'var recEl=document.querySelector("#cc-local-record-count");'
      'var candEl=document.querySelector("#cc-local-candidate-count");'
      'if(recEl)recEl.textContent=String(collectLocalRecords().length);'
      'if(candEl)candEl.textContent=String(collectLocalCandidates().length);'
      '}'
      'updateLocalCounts();'
      'var migrateBtn=document.querySelector("#cc-migrate-btn");'
      'var resultEl=document.querySelector("#cc-migrate-result");'
      'if(migrateBtn){'
      'migrateBtn.addEventListener("click",function(){'
      'var payload={'
      'records:collectLocalRecords(),'
      'candidates:collectLocalCandidates()'
      '};'
      'if(resultEl)resultEl.textContent="保存しています…";'
      'migrateBtn.disabled=true;'
      'window.fetch("/api/dashboard/migrate",{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify(payload)'
      '}).then(function(res){return res.json();}).then(function(data){'
      'var r=(data&&data.records)||{inserted:0,skipped:0};'
      'var c=(data&&data.candidates)||{inserted:0,skipped:0};'
      'var skipped=(r.skipped||0)+(c.skipped||0);'
      'var message="運用記録"+r.inserted+"件、投稿候補"+c.inserted+'
      '"件をこのアプリに保存しました。";'
      'if(skipped>0){'
      'message+="（すでに保存済みだった"+skipped+"件はそのままにしました）";'
      '}'
      'if(resultEl)resultEl.textContent=message;'
      'migrateBtn.disabled=false;'
      '}).catch(function(){'
      'if(resultEl)resultEl.textContent='
      '"保存できませんでした。しばらくしてからもう一度お試しください。";'
      'migrateBtn.disabled=false;'
      '});'
      '});'
      '}'
      '})();</script>'
      '</section>'
  )


def _render_data_protection_section():
  """運用司令室の「データ保護」セクション(MISSION 092、MISSION 093で復元を追加)。

  ai_company.dbのローカル世代バックアップ(hive_backup.py・SQLite Online
  Backup API経由)の状態を表示する。最初に見える範囲は、最終バックアップ
  日時・保存済み世代数・「今すぐバックアップを作成」ボタン・直近一覧
  (日時とファイルサイズのみ)に絞り、詳しい注意事項は<details>で折りたたむ。
  一覧にはDBの中身・認証情報は一切表示しない。

  MISSION 093: 「バックアップから復元」を追加する。整合性が実際に再確認
  できたバックアップだけを候補として選べ、選んだだけでは復元は始まらない。
  復元の実行には、確認欄に確認文言(RESTORE_CONFIRMATION_PHRASE)を正確に
  入力する必要があり、ブラウザ側の入力チェックだけでなくサーバー側
  (/api/dashboard/backups/restore)でも必ず再検証する。
  """
  restore_phrase_json = json.dumps(
      dashboard_db.RESTORE_CONFIRMATION_PHRASE, ensure_ascii=False
  )
  return (
      '<section class="cc-data-protection" aria-label="データ保護" '
      'id="cc-data-protection">'
      '<h2 class="cc-section-title">データ保護</h2>'
      '<div class="cc-decision-box">'
      '<div class="cc-data-protection-summary">'
      '<p>最終バックアップ：<b id="cc-backup-last">確認中…</b></p>'
      '<p>保存済み世代数：<b id="cc-backup-count">確認中…</b></p>'
      '</div>'
      '<button type="button" class="cc-decision-add-btn" '
      'id="cc-backup-now-btn">今すぐバックアップを作成</button>'
      '<p class="cc-decision-note" id="cc-backup-result" aria-live="polite">'
      '</p>'
      '<div class="cc-decision-log-list" id="cc-backup-list">'
      '<p class="cc-decision-log-empty" id="cc-backup-list-empty">確認中…'
      '</p>'
      '</div>'
      '<details class="cc-work-ledger-detail">'
      '<summary>詳細・注意事項</summary>'
      '<p class="cc-decision-note">バックアップは、このMac上の'
      'backups/フォルダへ、作成日時が分かる名前で保存されます'
      '（書き込み中でも壊れない、SQLite公式のバックアップ機能を使用し、'
      '単純なファイルコピーは行いません）。外部への送信・クラウド同期は'
      '一切行いません。保存するのは直近'
      f'{dashboard_db.BACKUP_RETENTION_COUNT}世代までで、新しいバックアップ'
      'の正常性を確認したうえで、それより古い世代（このアプリが作成した'
      'ものに限る）を自動的に整理します。運用記録・投稿候補・作業台帳・'
      '実績数値の保存を書き込むたびに、当日分のバックアップがまだなければ'
      '自動で1回作成されます。</p>'
      '</details>'
      '</div>'

      # MISSION 093: バックアップから復元。
      '<div class="cc-decision-box cc-restore-box" id="cc-restore-box">'
      '<h3 class="cc-restore-title">バックアップから復元</h3>'
      '<p class="cc-decision-note">整合性を再確認できたバックアップだけを'
      '選べます。選んだだけでは復元は始まりません。</p>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-restore-select">復元するバックアップ</label>'
      '<select id="cc-restore-select"><option value="">確認中…</option>'
      '</select></div>'
      '</div>'
      '<details class="cc-work-ledger-detail">'
      '<summary>復元前の注意事項</summary>'
      '<p class="cc-decision-note">復元を実行すると、現在のデータは'
      '「復元前バックアップ」として自動的に保存されたうえで、選んだ'
      'バックアップの内容に置き換わります。復元元・復元前バックアップは'
      '世代整理（直近'
      f'{dashboard_db.BACKUP_RETENTION_COUNT}世代保持）から保護され、'
      '整理で消えることはありません。復元の実行には、確認欄に'
      f'「{dashboard_db.RESTORE_CONFIRMATION_PHRASE}」と正確に入力する'
      '必要があります。外部への送信・クラウド同期・自動的なページ再読み込み'
      'は行いません。</p>'
      '</details>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-restore-confirm">確認のため'
      f'「{dashboard_db.RESTORE_CONFIRMATION_PHRASE}」と入力してください'
      '</label>'
      f'<input type="text" id="cc-restore-confirm" '
      f'placeholder="{dashboard_db.RESTORE_CONFIRMATION_PHRASE}"></div>'
      '</div>'
      '<button type="button" class="cc-decision-add-btn" '
      'id="cc-restore-btn" disabled>このバックアップから復元する</button>'
      '<p class="cc-decision-note" id="cc-restore-result" aria-live="polite">'
      '</p>'
      '</div>'

      '<script>(function(){'
      f'var RESTORE_PHRASE={restore_phrase_json};'
      'var lastEl=document.querySelector("#cc-backup-last");'
      'var countEl=document.querySelector("#cc-backup-count");'
      'var listEl=document.querySelector("#cc-backup-list");'
      'var listEmptyEl=document.querySelector("#cc-backup-list-empty");'
      'var nowBtn=document.querySelector("#cc-backup-now-btn");'
      'var resultEl=document.querySelector("#cc-backup-result");'
      'function escapeHtml(s){'
      'return String(s==null?"":s)'
      '.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");'
      '}'
      'function formatBytes(n){'
      'if(typeof n!=="number")return "-";'
      'if(n<1024)return n+"B";'
      'if(n<1024*1024)return Math.round(n/1024)+"KB";'
      'return (Math.round(n/1024/1024*10)/10)+"MB";'
      '}'
      'function renderStatus(data){'
      'if(!data||!data.lastBackupAt){'
      'if(lastEl)lastEl.textContent="まだバックアップはありません";'
      'if(countEl)countEl.textContent="0件";'
      'if(listEmptyEl){'
      'listEmptyEl.textContent="まだバックアップはありません。";'
      'listEmptyEl.hidden=false;'
      '}'
      'return;'
      '}'
      'if(lastEl)lastEl.textContent=data.lastBackupAt;'
      'if(countEl){'
      'countEl.textContent=data.generationCount+"件（保持上限"+'
      'data.retentionCount+"件）";'
      '}'
      'listEl.querySelectorAll(".cc-backup-item").forEach(function(el){'
      'el.remove();'
      '});'
      'if(!data.recent||data.recent.length===0){'
      'if(listEmptyEl){'
      'listEmptyEl.textContent="まだバックアップはありません。";'
      'listEmptyEl.hidden=false;'
      '}'
      'return;'
      '}'
      'if(listEmptyEl)listEmptyEl.hidden=true;'
      'data.recent.forEach(function(b){'
      'var div=document.createElement("div");'
      'div.className="cc-decision-log-entry cc-backup-item";'
      'div.innerHTML='
      '"<div><b>作成日時：</b>"+escapeHtml(b.createdAt||"-")+"</div>"+'
      '"<div><b>サイズ：</b>"+escapeHtml(formatBytes(b.sizeBytes))+"</div>";'
      'listEl.appendChild(div);'
      '});'
      '}'
      'function loadStatus(){'
      'if(typeof window.fetch!=="function")return;'
      'window.fetch("/api/dashboard/backups")'
      '.then(function(res){return res.json();})'
      '.then(renderStatus)'
      '.catch(function(){});'
      '}'
      'if(nowBtn){'
      'nowBtn.addEventListener("click",function(){'
      'nowBtn.disabled=true;'
      'resultEl.textContent="バックアップを作成しています…";'
      'window.fetch("/api/dashboard/backups",{method:"POST"})'
      '.then(function(res){return res.json();})'
      '.then(function(data){'
      'nowBtn.disabled=false;'
      'if(data&&data.created){'
      'resultEl.textContent='
      '"バックアップを作成しました（"+(data.createdAt||"")+"）。";'
      'loadStatus();'
      '}else{'
      'resultEl.textContent='
      '"バックアップを作成できませんでした。しばらくしてからもう一度'
      'お試しください。";'
      '}'
      '}).catch(function(){'
      'nowBtn.disabled=false;'
      'resultEl.textContent='
      '"バックアップを作成できませんでした。しばらくしてからもう一度'
      'お試しください。";'
      '});'
      '});'
      '}'
      # MISSION 093: バックアップから復元。
      'var restoreSelect=document.querySelector("#cc-restore-select");'
      'var restoreConfirm=document.querySelector("#cc-restore-confirm");'
      'var restoreBtn=document.querySelector("#cc-restore-btn");'
      'var restoreResultEl=document.querySelector("#cc-restore-result");'
      'var RESTORE_REASON_TEXT={'
      'confirmation_mismatch:"確認文言が正しくありません。",'
      'invalid_identifier:"復元するバックアップを選んでください。",'
      'not_a_valid_candidate:"選択したバックアップは復元候補として確認'
      'できませんでした。一覧を更新してからもう一度お試しください。",'
      'restore_error:"復元に失敗しました。現在のDBは変更していません。",'
      'os_error:"復元に失敗しました。現在のDBは変更していません。"'
      '};'
      'function updateRestoreBtnState(){'
      'if(!restoreBtn)return;'
      'var hasSelection=Boolean(restoreSelect&&restoreSelect.value);'
      'var confirmOk=Boolean('
      'restoreConfirm&&restoreConfirm.value===RESTORE_PHRASE);'
      'restoreBtn.disabled=!(hasSelection&&confirmOk);'
      '}'
      'if(restoreSelect){'
      'restoreSelect.addEventListener("change",updateRestoreBtnState);'
      '}'
      'if(restoreConfirm){'
      'restoreConfirm.addEventListener("input",updateRestoreBtnState);'
      '}'
      'function loadRestoreCandidates(){'
      'if(!restoreSelect||typeof window.fetch!=="function")return;'
      'window.fetch("/api/dashboard/backups/restore-candidates")'
      '.then(function(res){return res.json();})'
      '.then(function(data){'
      'var candidates=(data&&data.candidates)||[];'
      'restoreSelect.innerHTML="";'
      'if(candidates.length===0){'
      'var emptyOpt=document.createElement("option");'
      'emptyOpt.value="";'
      'emptyOpt.textContent="復元できるバックアップはまだありません";'
      'restoreSelect.appendChild(emptyOpt);'
      'restoreSelect.disabled=true;'
      'updateRestoreBtnState();'
      'return;'
      '}'
      'restoreSelect.disabled=false;'
      'var placeholderOpt=document.createElement("option");'
      'placeholderOpt.value="";'
      'placeholderOpt.textContent="選択してください";'
      'restoreSelect.appendChild(placeholderOpt);'
      'candidates.forEach(function(c){'
      'var opt=document.createElement("option");'
      'opt.value=c.identifier;'
      'var integrityText=c.integrityCheck==="ok"?"OK":'
      '(c.integrityCheck||"不明");'
      'opt.textContent=(c.createdAt||"-")+"・"+'
      'formatBytes(c.sizeBytes)+"・整合性："+integrityText;'
      'restoreSelect.appendChild(opt);'
      '});'
      'updateRestoreBtnState();'
      '}).catch(function(){});'
      '}'
      'if(restoreBtn){'
      'restoreBtn.addEventListener("click",function(){'
      'var identifier=restoreSelect?restoreSelect.value:"";'
      'var confirmation=restoreConfirm?restoreConfirm.value:"";'
      'if(!identifier||confirmation!==RESTORE_PHRASE){'
      'if(restoreResultEl){'
      'restoreResultEl.textContent='
      '"復元するバックアップを選び、確認欄に「"+RESTORE_PHRASE+'
      '"」と正確に入力してください。";'
      '}'
      'return;'
      '}'
      'restoreBtn.disabled=true;'
      'if(restoreResultEl)restoreResultEl.textContent="復元しています…";'
      'window.fetch("/api/dashboard/backups/restore",{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify({identifier:identifier,confirmation:confirmation})'
      '}).then(function(res){return res.json();}).then(function(data){'
      'if(data&&data.restored){'
      'if(restoreResultEl){'
      'restoreResultEl.textContent='
      '"復元前バックアップ（"+(data.preRestoreBackupCreatedAt||"-")+'
      '"）を作成したうえで、"+(data.restoredFromCreatedAt||"-")+'
      '"のバックアップから復元しました。ページを再読み込みすると'
      '復元後のデータが表示されます。";'
      '}'
      'if(restoreConfirm)restoreConfirm.value="";'
      'loadStatus();'
      'loadRestoreCandidates();'
      '}else{'
      'if(restoreResultEl){'
      'restoreResultEl.textContent=(data&&RESTORE_REASON_TEXT[data.reason])||'
      '"復元できませんでした。しばらくしてからもう一度お試しください。";'
      '}'
      'updateRestoreBtnState();'
      '}'
      '}).catch(function(){'
      'if(restoreResultEl){'
      'restoreResultEl.textContent='
      '"復元できませんでした。しばらくしてからもう一度お試しください。";'
      '}'
      'updateRestoreBtnState();'
      '});'
      '});'
      '}'
      'loadRestoreCandidates();'
      'loadStatus();'
      '})();</script>'
      '</section>'
  )


def _render_command_center_scene():
  """運用司令室(/command-center)画面のHTMLを組み立てる。

  純粋な表示用マークアップ+クライアント側JSのみで構成する。DB・API・
  楽天ROOM・楽天アフィリエイト・note・Pinterest・Threadsへの通信・アクセス・
  ログイン・投稿・送信・削除は一切行わない。入力値の保存先はブラウザの
  localStorageのみで、フォーム送信(<form method="POST">等)や外部への
  fetch/XHRは一切使わない。
  """

  def _check_category_card(cat):
    field_inputs = "".join(
        f'<label>{label}<input type="text" class="cc-check-field" '
        f'data-category="{cat["key"]}" data-field="{key}"></label>'
        for key, label in cat["fields"]
    )
    fields_block = f'<div class="cc-check-fields">{field_inputs}</div>' if cat["fields"] else ""
    return (
        f'<div class="cc-check-category" data-category="{cat["key"]}">'
        f'<h3>{cat["label"]}</h3>'
        f'{fields_block}'
        '<label class="cc-confirmed-row">'
        f'<input type="checkbox" class="cc-check-confirmed" data-category="{cat["key"]}"> '
        f'{cat["confirm_label"]}</label>'
        '</div>'
    )

  check_cards = "".join(
      _check_category_card(cat) for cat in COMMAND_CENTER_CHECK_CATEGORIES
  )

  dept_cards = "".join(
      f'<div class="cc-dept-card"><h3>{d["label"]}</h3><p>{d["summary"]}</p></div>'
      for d in COMMAND_CENTER_DEPARTMENT_CARDS
  )

  media_options = "".join(
      f'<option value="{m}">{m}</option>' for m in COMMAND_CENTER_DECISION_MEDIA_OPTIONS
  )

  # MISSION 080: 「本日の運用記録」の媒体・種別の選択肢。
  record_media_options = "".join(
      f'<option value="{m}">{m}</option>'
      for m in COMMAND_CENTER_DAILY_RECORD_MEDIA_OPTIONS
  )
  record_type_options = "".join(
      f'<option value="{t}">{t}</option>' for t in COMMAND_CENTER_DAILY_RECORD_TYPES
  )

  return (
      '<section class="command-center" aria-label="運用司令室">'
      '<div class="cc-topbar">'
      '<p><span class="cc-approver">最終承認者：利用者本人</span></p>'
      '<p><b>この画面はローカルのみで動作する確認・記録・判断用の画面です。</b> '
      '楽天ROOM・楽天アフィリエイト・note・Pinterest・Threadsへのアクセス・'
      'ログイン・投稿・送信・削除は一切行いません。</p>'
      '<p>入力内容は、まずお使いのブラウザのlocalStorageに保存されます。'
      'このページ下部の「データ保存」から、このMac上のアプリ内データ'
      '（SQLite）へも保存できます。どちらも外部のサービスへは送信されません。'
      'ブラウザや端末を変えたり、ブラウザのデータを消去してlocalStorageが'
      '失われても、アプリ内データに保存済みの内容は残ります。</p>'
      '</div>'

      '<h2 class="cc-section-title">今日の確認ボード</h2>'
      '<p class="cc-pending-note">各項目は空欄から始まります。実際にそれぞれの'
      '管理画面で確認した数字だけを入力してください。確認したら「確認済み」に'
      'チェックを入れてください。</p>'
      f'<div class="cc-check-grid">{check_cards}</div>'

      '<h2 class="cc-section-title">承認待ち・投稿状況</h2>'
      '<div class="cc-pending-box">'
      '<p class="cc-pending-empty" id="cc-pending-empty">現在、承認待ちの項目は'
      'ありません。</p>'
      '<label for="cc-pending-memo" class="sr-only">承認待ち・投稿状況メモ</label>'
      '<textarea id="cc-pending-memo" rows="4" maxlength="2000" '
      'placeholder="承認待ちの項目や、投稿状況について気になることがあれば、'
      'ここに短くメモしてください。"></textarea>'
      '<p class="cc-pending-note">提案・下書き・確認まで。公開操作は利用者'
      '本人が行う。</p>'
      '</div>'

      '<h2 class="cc-section-title">担当チーム状況</h2>'
      '<p class="cc-dept-note">以下はAI Hive OS内の仮想チームです。実在する'
      '人物や自動で稼働するプログラムではなく、提案・下書き・記録までを担当'
      'します。外部サービスへの実際の投稿・送信・ログイン・削除は行わず、'
      '最終判断・実行は利用者本人が行います。</p>'
      f'<div class="cc-dept-grid">{dept_cards}</div>'

      '<h2 class="cc-section-title">判断メモ</h2>'
      '<div class="cc-decision-box">'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-decision-date">日付</label>'
      '<input type="date" id="cc-decision-date"></div>'
      '<div><label for="cc-decision-media">媒体</label>'
      f'<select id="cc-decision-media"><option value="">選択してください</option>{media_options}</select></div>'
      '</div>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-decision-observed">観測した数字</label>'
      '<textarea id="cc-decision-observed" rows="2" maxlength="600" '
      'placeholder="実際に確認できた数字だけを書いてください（未確認の項目は'
      '「未確認」と書く）"></textarea></div>'
      '<div><label for="cc-decision-judgement">判断</label>'
      '<textarea id="cc-decision-judgement" rows="2" maxlength="600" '
      'placeholder="数字から受け取った気づきや状況の整理（断定は避ける）">'
      '</textarea></div>'
      '</div>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-decision-next">次にすること</label>'
      '<textarea id="cc-decision-next" rows="2" maxlength="600"></textarea></div>'
      '<div><label for="cc-decision-hold">保留理由</label>'
      '<textarea id="cc-decision-hold" rows="2" maxlength="600" '
      'placeholder="判断・実行を保留する場合の理由（該当する場合のみ）">'
      '</textarea></div>'
      '</div>'
      '<button type="button" class="cc-decision-add-btn" id="cc-decision-add">'
      'この判断メモを記録に追加する</button>'
      '<p class="cc-decision-note">推測と確認済み事実を分けて記録する。数字は'
      '未確認のまま断定的な判断を書かないでください。</p>'
      '<div class="cc-decision-log-list" id="cc-decision-log-list">'
      '<p class="cc-decision-log-empty" id="cc-decision-log-empty">まだ記録は'
      'ありません。</p>'
      '</div>'
      '</div>'

      # MISSION 080: 「本日の運用記録」。利用者がローカルで確認・下書き・
      # 投稿・記録・承認待ちにした実績を入力すると、AIオフィス
      # (/ai-office)側で該当する担当社員の対面報告として反映される
      # (詳しい対応はAI_OFFICE_DAILY_RECORD_*定数を参照)。ここでの保存も
      # localStorageのみで、投稿・送信・ログイン・削除は行わない。
      '<h2 class="cc-section-title">本日の運用記録</h2>'
      '<div class="cc-decision-box">'
      '<p class="cc-decision-note">ここに入力した内容は、AIオフィス'
      '（/ai-office）にも、該当する担当の対面報告として反映されます'
      '（同じブラウザのlocalStorage内でのみ連携し、外部への送信は'
      '行いません）。今日の日付で記録がない場合、AIオフィスは引き続き'
      'デモ表示のままです。</p>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-record-date">日付</label>'
      '<input type="date" id="cc-record-date"></div>'
      '<div><label for="cc-record-media">媒体</label>'
      f'<select id="cc-record-media"><option value="">選択してください</option>{record_media_options}</select></div>'
      '</div>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-record-type">種別</label>'
      f'<select id="cc-record-type"><option value="">選択してください</option>{record_type_options}</select></div>'
      '<div><label for="cc-record-metric">数字メモ（任意）</label>'
      '<input type="text" id="cc-record-metric" maxlength="200" '
      'placeholder="実際に確認できた数字だけを書いてください"></div>'
      '</div>'
      '<div class="cc-decision-fields">'
      '<div><label for="cc-record-content">内容</label>'
      '<textarea id="cc-record-content" rows="2" maxlength="600" '
      'placeholder="確認・下書き・記録した内容を短く書いてください">'
      '</textarea></div>'
      '<div><label for="cc-record-reference">URLまたは参照先（任意）</label>'
      '<input type="text" id="cc-record-reference" maxlength="300" '
      'placeholder="参照した画面名やURLなど（このアプリからは開きません）">'
      '</div>'
      '</div>'
      '<button type="button" class="cc-decision-add-btn" id="cc-record-add">'
      '本日の運用記録を保存する</button>'
      '<p class="cc-decision-note">実際に確認・作業した内容だけを記録して'
      'ください。このアプリが自動で実績を作成することはありません。</p>'
      '<div class="cc-decision-log-list" id="cc-record-log-list">'
      '<p class="cc-decision-log-empty" id="cc-record-log-empty">まだ本日の'
      '運用記録はありません。</p>'
      '</div>'
      '</div>'

      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の'
      '確認・記録・判断ツールです。楽天ROOM・楽天アフィリエイト・note・'
      'Pinterest・Threadsへの投稿・送信・ログイン・削除は行われません。</p>'
      '<script>'
      '(function(){'
      'const STORAGE_PREFIX="ai-hive-command-center:";'
      'function safeGet(key){'
      'try{return window.localStorage.getItem(key);}catch(e){return null;}'
      '}'
      'function safeSet(key,value){'
      'try{window.localStorage.setItem(key,value);}'
      'catch(e){/* localStorageが使えない環境でも画面は壊さない */}'
      '}'
      # --- 今日の確認ボード ---
      'function checkStorageKey(category){return STORAGE_PREFIX+"check:"+category;}'
      'function loadCheckCategory(el){'
      'const category=el.dataset.category;'
      'let saved={};'
      'try{'
      'const raw=safeGet(checkStorageKey(category));'
      'saved=raw?JSON.parse(raw):{};'
      '}catch(e){saved={};}'
      'el.querySelectorAll(".cc-check-field").forEach(function(input){'
      'input.value=(saved.fields&&saved.fields[input.dataset.field])||"";'
      '});'
      'const confirmedBox=el.querySelector(".cc-check-confirmed");'
      'if(confirmedBox)confirmedBox.checked=Boolean(saved.confirmed);'
      '}'
      'function saveCheckCategory(el){'
      'const category=el.dataset.category;'
      'const fields={};'
      'el.querySelectorAll(".cc-check-field").forEach(function(input){'
      'fields[input.dataset.field]=input.value;'
      '});'
      'const confirmedBox=el.querySelector(".cc-check-confirmed");'
      'const data={fields:fields,confirmed:confirmedBox?confirmedBox.checked:false};'
      'safeSet(checkStorageKey(category),JSON.stringify(data));'
      '}'
      'document.querySelectorAll(".cc-check-category").forEach(function(el){'
      'loadCheckCategory(el);'
      'el.querySelectorAll(".cc-check-field,.cc-check-confirmed").forEach(function(input){'
      'input.addEventListener("input",function(){saveCheckCategory(el);});'
      'input.addEventListener("change",function(){saveCheckCategory(el);});'
      '});'
      '});'
      # --- 承認待ち・投稿状況メモ ---
      'const pendingKey=STORAGE_PREFIX+"pending-memo";'
      'const pendingMemo=document.querySelector("#cc-pending-memo");'
      'const pendingEmpty=document.querySelector("#cc-pending-empty");'
      'function updatePendingEmptyState(){'
      'pendingEmpty.hidden=Boolean(pendingMemo.value.trim());'
      '}'
      'pendingMemo.value=safeGet(pendingKey)||"";'
      'updatePendingEmptyState();'
      'pendingMemo.addEventListener("input",function(){'
      'safeSet(pendingKey,pendingMemo.value);'
      'updatePendingEmptyState();'
      '});'
      # --- 判断メモ（決定ログ） ---
      'const decisionLogKey=STORAGE_PREFIX+"decision-log";'
      'const decisionDate=document.querySelector("#cc-decision-date");'
      'const decisionMedia=document.querySelector("#cc-decision-media");'
      'const decisionObserved=document.querySelector("#cc-decision-observed");'
      'const decisionJudgement=document.querySelector("#cc-decision-judgement");'
      'const decisionNext=document.querySelector("#cc-decision-next");'
      'const decisionHold=document.querySelector("#cc-decision-hold");'
      'const decisionLogList=document.querySelector("#cc-decision-log-list");'
      'const decisionLogEmpty=document.querySelector("#cc-decision-log-empty");'
      'function loadDecisionLog(){'
      'try{'
      'const raw=safeGet(decisionLogKey);'
      'return raw?JSON.parse(raw):[];'
      '}catch(e){return [];}'
      '}'
      'function escapeHtml(s){'
      'return String(s==null?"":s)'
      '.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");'
      '}'
      'function renderDecisionLog(){'
      'const entries=loadDecisionLog();'
      'decisionLogList.querySelectorAll(".cc-decision-log-entry").forEach(function(el){el.remove();});'
      'if(entries.length===0){'
      'decisionLogEmpty.hidden=false;'
      'return;'
      '}'
      'decisionLogEmpty.hidden=true;'
      'entries.slice().reverse().forEach(function(entry){'
      'const div=document.createElement("div");'
      'div.className="cc-decision-log-entry";'
      'div.innerHTML='
      '"<div><b>日付：</b>"+escapeHtml(entry.date||"未入力")+"</div>"+'
      '"<div><b>媒体：</b>"+escapeHtml(entry.media||"未選択")+"</div>"+'
      '"<div><b>観測した数字：</b>"+escapeHtml(entry.observed||"未確認")+"</div>"+'
      '"<div><b>判断：</b>"+escapeHtml(entry.judgement||"")+"</div>"+'
      '"<div><b>次にすること：</b>"+escapeHtml(entry.next||"")+"</div>"+'
      '"<div><b>保留理由：</b>"+escapeHtml(entry.hold||"")+"</div>";'
      'decisionLogList.appendChild(div);'
      '});'
      '}'
      'document.querySelector("#cc-decision-add").addEventListener("click",function(){'
      'const entry={'
      'date:decisionDate.value,'
      'media:decisionMedia.value,'
      'observed:decisionObserved.value,'
      'judgement:decisionJudgement.value,'
      'next:decisionNext.value,'
      'hold:decisionHold.value,'
      '};'
      'const hasContent=entry.date||entry.media||entry.observed.trim()||'
      'entry.judgement.trim()||entry.next.trim()||entry.hold.trim();'
      'if(!hasContent){'
      'window.alert("記録する内容を、いずれかの項目に入力してください。");'
      'return;'
      '}'
      'const entries=loadDecisionLog();'
      'entries.push(entry);'
      'safeSet(decisionLogKey,JSON.stringify(entries));'
      'renderDecisionLog();'
      'decisionObserved.value="";'
      'decisionJudgement.value="";'
      'decisionNext.value="";'
      'decisionHold.value="";'
      '});'
      'renderDecisionLog();'
      # --- MISSION 080: 本日の運用記録(AIオフィスの実績表示と連携) ---
      'const recordLogKey=STORAGE_PREFIX+"daily-record-log";'
      'const recordDate=document.querySelector("#cc-record-date");'
      'const recordMedia=document.querySelector("#cc-record-media");'
      'const recordType=document.querySelector("#cc-record-type");'
      'const recordMetric=document.querySelector("#cc-record-metric");'
      'const recordContent=document.querySelector("#cc-record-content");'
      'const recordReference=document.querySelector("#cc-record-reference");'
      'const recordLogList=document.querySelector("#cc-record-log-list");'
      'const recordLogEmpty=document.querySelector("#cc-record-log-empty");'
      'function loadRecordLog(){'
      'try{'
      'const raw=safeGet(recordLogKey);'
      'const list=raw?JSON.parse(raw):[];'
      'return Array.isArray(list)?list:[];'
      '}catch(e){return [];}'
      '}'
      'function renderRecordLog(){'
      'const entries=loadRecordLog();'
      'recordLogList.querySelectorAll(".cc-decision-log-entry").forEach(function(el){el.remove();});'
      'if(entries.length===0){'
      'recordLogEmpty.hidden=false;'
      'return;'
      '}'
      'recordLogEmpty.hidden=true;'
      'entries.slice().reverse().forEach(function(entry){'
      'const div=document.createElement("div");'
      'div.className="cc-decision-log-entry";'
      'div.innerHTML='
      '"<div><b>日付：</b>"+escapeHtml(entry.date||"未入力")+"</div>"+'
      '"<div><b>媒体：</b>"+escapeHtml(entry.media||"未選択")+"</div>"+'
      '"<div><b>種別：</b>"+escapeHtml(entry.type||"未選択")+"</div>"+'
      '"<div><b>内容：</b>"+escapeHtml(entry.content||"")+"</div>"+'
      '"<div><b>数字メモ：</b>"+escapeHtml(entry.metric||"")+"</div>"+'
      '"<div><b>参照先：</b>"+escapeHtml(entry.reference||"")+"</div>";'
      'recordLogList.appendChild(div);'
      '});'
      '}'
      'document.querySelector("#cc-record-add").addEventListener("click",function(){'
      'const entry={'
      'date:recordDate.value,'
      'media:recordMedia.value,'
      'type:recordType.value,'
      'content:recordContent.value,'
      'metric:recordMetric.value,'
      'reference:recordReference.value,'
      '};'
      'if(!entry.date||!entry.media||!entry.type||!entry.content.trim()){'
      'window.alert("日付・媒体・種別・内容は、本日の運用記録として保存する'
      'ために入力してください。");'
      'return;'
      '}'
      'const entries=loadRecordLog();'
      'entries.push(entry);'
      'safeSet(recordLogKey,JSON.stringify(entries));'
      'renderRecordLog();'
      # MISSION 088: 保存した記録を、ブラウザのlocalStorageに加えて
      # このMac上のアプリ内DBにも保存する(ベストエフォート。失敗しても
      # localStorageへの保存・画面表示には影響させない)。これにより
      # AIオフィスの本日の指示・実行キュー・直近の実績で即時に読み取れる
      # ようになる。
      'try{'
      'window.fetch("/api/dashboard/daily-records",{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify(entry)'
      '}).catch(function(){});'
      '}catch(e){/* fetch未対応環境でも画面は壊さない */}'
      'recordContent.value="";'
      'recordMetric.value="";'
      'recordReference.value="";'
      '});'
      'renderRecordLog();'
      '})();'
      '</script>'
      + _render_work_ledger_section()
      + _render_data_storage_section()
      + _render_data_protection_section() +
      '</section>'
  )


# MISSION 067: AIオフィス(/ai-office)。
#
# 資料室(company_knowledge/)と担当チーム(company_knowledge/departments/)が、
# どの役割で何を確認し、どこまで進んでいるかを見える化する「デモ表示のみ」
# の画面。運用司令室(/command-center)が「数字の確認・判断・記録」の場で
# あるのに対し、AIオフィスは「役割・進行状況・活動の見える化」に役割を
# 絞っており、内容は重複させない。
#
# この段階では実データ接続・外部サービスへのアクセス・ログイン・投稿・
# 送信・削除・ブラウザ自動操作・API連携・外部AIへの問い合わせは一切実装
# しない。画面内のすべての数値・状態・チャット・活動フィードは、あらかじめ
# 用意した明示的なデモデータであり、実際のROOM・楽天アフィリエイト・note・
# Pinterest・Threadsの実績・反応・取得日時を捏造しない(常に「デモ」「未接続」
# であることが分かる表示にする)。フォーム・入力欄・投稿/公開/送信/ログイン/
# 削除を行うボタンは置かず、localStorageへの保存も行わない(このページは
# 完全に表示専用)。
#
# 5部署の役割・「提案・下書き・記録まで。最終承認と外部公開は利用者本人」
# という範囲は、company_knowledge/departments/*.mdの内容と矛盾しないように
# 保つこと。
#
# MISSION 069: オフィスフロアマップを、CSSだけで描いたカード型から、
# ピクセルアート調のイラスト画像(static/images/ai-office-floor-map.png)を
# 中心にした表示へ差し替えた。画像は装飾ではなくAIオフィスの中心として
# 扱い、画像の直下に5部署の状態(すべてデモ)を対応付けた一覧を表示する。
# 画像に対するクリック操作・状態変更機能は今回実装しない(案内文のみ)。
#
# MISSION 072: 背景画像(ai-office-floor-map.png)にはロボットのイラストが
# 描き込まれており、その上に社員スプライトを重ねると背景ロボットと重複
# して見えてしまう不具合があった。ロボット・人物を取り除いた
# ai-office-floor-map-empty.pngを新たに追加し、実際にフロアマップとして
# 表示するのはこちらに差し替えた。ai-office-floor-map.png自体は削除・
# 変更しない(過去のミッションで追加した画像を保持するため)。
AI_OFFICE_SCOPE_STATEMENT = "提案・下書き・記録まで。最終承認と外部公開は利用者本人。"
AI_OFFICE_FLOOR_MAP_IMAGE_RELATIVE_PATH = "images/ai-office-floor-map.png"
AI_OFFICE_FLOOR_MAP_EMPTY_IMAGE_RELATIVE_PATH = "images/ai-office-floor-map-empty.png"

# 各担当の状態(demo_status)は、後の段階で確認AI等の読み取り結果と連携できる
# よう、"working"(稼働中)/"pending"(確認待ち)/"waiting"(待機中)/
# "demo_done"(デモ完了)という固定キーで表現する(表示文言は
# AI_OFFICE_STATUS_LABELSで一元管理)。MISSION 068でオフィスフロアマップに
# AI社員キャラクターの状態表示を追加するため、"working"を追加した。
# どの状態も実際の自動稼働を示すものではなく、常にデモ表示である。
AI_OFFICE_STATUS_LABELS = {
    "working": "稼働中",
    "pending": "確認待ち",
    "waiting": "待機中",
    "demo_done": "デモ完了",
}

# staff_nameはMISSION 068で追加した、各部署に1人ずつ配置するAI社員の
# 名称(フィクションのキャラクターであり、実在の人物ではない)。MISSION 071で、
# フロアマップ上に表示するスプライト画像(static/images/ai-office-team-
# sprites.png、2列×4行)における各キャラクターの位置(sprite.row/col)を
# 追加した。
AI_OFFICE_DEPARTMENTS = [
    {
        "key": "operations_lead",
        "desk_label": "指令デスク",
        "role_label": "運用責任者",
        "symbol": "指令",
        "staff_name": "柴犬社長",
        "sprite": {"row": 0, "col": 0},
        "role_summary": "各担当の状況を横断的に確認し、今日・今週の優先順位を整理します。",
        "demo_status": "working",
        "idle_type": "typing",
    },
    {
        "key": "room",
        "desk_label": "ROOM運用席",
        "role_label": "ROOM担当",
        "symbol": "ROOM",
        "staff_name": "里奈",
        "sprite": {"row": 2, "col": 0},
        "role_summary": "商品数・♡・コメントを確認し、反応のあるジャンルを候補として提案します。",
        "demo_status": "pending",
        "idle_type": "typing",
    },
    {
        "key": "note",
        "desk_label": "note編集席",
        "role_label": "note担当",
        "symbol": "note",
        "staff_name": "海",
        "sprite": {"row": 1, "col": 0},
        "role_summary": "記事候補やPV・スキを整理し、次のテーマ候補をまとめます。",
        "demo_status": "waiting",
        "idle_type": "typing",
    },
    {
        "key": "pinterest",
        "desk_label": "Pinterest企画席",
        "role_label": "Pinterest担当",
        "symbol": "Pin",
        "staff_name": "美咲",
        "sprite": {"row": 0, "col": 2},
        "role_summary": "画像テーマ・Pin候補を整理し、Pinの表示・保存・リンククリックを"
                        "記録します。",
        "demo_status": "demo_done",
        "idle_type": "reading",
    },
    {
        "key": "analytics",
        "desk_label": "分析ラボ",
        "role_label": "分析担当",
        "symbol": "分析",
        "staff_name": "葵",
        "sprite": {"row": 2, "col": 1},
        "role_summary": "媒体ごとの数字を比較し、確認済みの事実と推測を分けて判断案を作ります。",
        "demo_status": "waiting",
        "idle_type": "analyzing",
    },
]

# MISSION 071で追加、MISSION 073で7人(蒼・伊織・彩(役割更新)・凛・悠・
# 結・蓮)へ拡張した、部署に紐づかない拡張担当。フロアマップ上に自席を
# 持ち、控えめな頻度で他部署・休憩スペースへの交流・確認デモを行う。
# 5部署カードとは別枠だが、MISSION 073で「社員名簿」セクションへ全員
# 統合して一覧表示する(zone_labelがその表示グループ名)。
AI_OFFICE_EXTENDED_STAFF = [
    {
        "key": "sou",
        "name": "蒼",
        "zone_label": "技術・品質スペース",
        "role_label": "技術担当",
        "role_summary": "AIオフィスの画面・動作確認を行います。",
        "sprite": {"row": 0, "col": 1},
        "pos": {"left": 68, "top": 22},
        "idle_type": "typing",
    },
    {
        "key": "iori",
        "name": "伊織",
        "zone_label": "技術・品質スペース",
        "role_label": "品質確認",
        "role_summary": "表示内容と注意書きの確認を行います。",
        "sprite": {"row": 1, "col": 1},
        "pos": {"left": 84, "top": 22},
        "idle_type": "reading",
    },
    {
        "key": "aya",
        "name": "彩",
        "zone_label": "Pinterest企画席",
        "role_label": "連携担当（社内コーディネーター）",
        "role_summary": "各部署の報告を指令デスクへつなぎ、確認待ちを整理します。"
                        "休憩スペースや他部署への訪問で、相談・交流のきっかけを"
                        "つくります。外部サービスへの投稿・送信・判断は行いません。",
        "sprite": {"row": 1, "col": 2},
        "pos": {"left": 52, "top": 76},
        "idle_type": "waiting",
    },
    {
        "key": "rin",
        "name": "凛",
        "zone_label": "note編集席",
        "role_label": "資料室管理",
        "role_summary": "資料室の内容を確認し、note編集席と行き来します。",
        "sprite": {"row": 2, "col": 2},
        "pos": {"left": 36, "top": 58},
        "idle_type": "reading",
    },
    {
        "key": "yu",
        "name": "悠",
        "zone_label": "指令デスク",
        "role_label": "進行管理",
        "role_summary": "指令デスクと各部署の間を回り、進行状況を確認します。",
        "sprite": {"row": 3, "col": 0},
        "pos": {"left": 36, "top": 22},
        "idle_type": "reading",
    },
    {
        "key": "yui",
        "name": "結",
        "zone_label": "分析ラボ",
        "role_label": "情報源の鮮度確認",
        "role_summary": "分析ラボと情報源モニターの間で、情報の鮮度を確認します。",
        "sprite": {"row": 3, "col": 1},
        "pos": {"left": 84, "top": 58},
        "idle_type": "analyzing",
    },
    {
        "key": "ren",
        "name": "蓮",
        "zone_label": "指令デスク",
        "role_label": "安全・承認確認",
        "role_summary": "報告のあとに、安全・承認確認の状態を表示します。",
        "sprite": {"row": 3, "col": 2},
        "pos": {"left": 20, "top": 58},
        "idle_type": "waiting",
    },
    # MISSION 089: 楽天ROOM投稿候補を「今日・今週・保留」に整理する候補
    # 管理チーム3名を追加。新しい画像素材は生成・追加せず、既存の
    # スプライトシート(12コマ)の中から、役割の近いコマを再利用する
    # (紬→結のコマ、凪→彩のコマ、陽菜→里奈のコマを流用。実在のコマ数は
    # 12のまま変わらない)。どのコマを再利用するかはAI_OFFICE_SPRITE_
    # REUSE_MAPで管理し、clip-pathも再利用元と同じものを使う。
    {
        "key": "tsumugi",
        "name": "紬",
        "zone_label": "候補管理スペース",
        "role_label": "候補整理席",
        "role_summary": "楽天ROOM候補を「今日・今週・保留」に分類し、進める順番を整理します。",
        "sprite": {"row": 3, "col": 1},
        # MISSION 089: 既存12人の座席(AI_OFFICE_FLOOR_POSITIONS)・拡張担当
        # の座席・訪問者スロット(AI_OFFICE_VISITOR_SLOTS)のどれとも重ならない
        # よう、空いている床の隅を使う(グリッド上の空きマスはすべて
        # 訪問者スロットと重なってしまうため、グリッド外の位置を選んだ)。
        "pos": {"left": 12, "top": 97},
        "idle_type": "analyzing",
    },
    {
        "key": "nagi",
        "name": "凪",
        "zone_label": "候補管理スペース",
        "role_label": "商品確認席",
        "role_summary": "楽天ROOM候補の商品名・URL・紹介文を確認します。",
        "sprite": {"row": 1, "col": 2},
        "pos": {"left": 68, "top": 40},
        "idle_type": "reading",
    },
    {
        "key": "hina",
        "name": "陽菜",
        "zone_label": "候補管理スペース",
        "role_label": "投稿準備席",
        "role_summary": "投稿前の最終確認を行います。実際の投稿はROOM上で利用者本人が行います。",
        "sprite": {"row": 2, "col": 0},
        "pos": {"left": 96, "top": 97},
        "idle_type": "waiting",
    },
]

# MISSION 089: 上記3名が使い回すスプライトコマの再利用元(新しい画像を
# 生成・追加しないための対応表)。AI_OFFICE_SPRITE_CLIP_PATHSは12コマ分
# (既存12人分)のまま追加せず、再利用先の人物にはこのマップで元のclip-path
# を引き当てる(同じコマ=同じ輪郭のため、そのまま使い回せる)。
AI_OFFICE_SPRITE_REUSE_MAP = {
    "tsumugi": "yui",
    "nagi": "aya",
    "hina": "room",
}


def _ai_office_clip_path_for(key):
  """personKeyのclip-pathを返す。新しいコマを持たない人物
  (AI_OFFICE_SPRITE_REUSE_MAP参照)は、再利用元のclip-pathをそのまま返す。
  """
  source_key = AI_OFFICE_SPRITE_REUSE_MAP.get(key, key)
  return AI_OFFICE_SPRITE_CLIP_PATHS[source_key]


# MISSION 075: 全12人に常時の小さな「生きている」動きを付けるための、
# idle_typeごとのCSSアニメーション名マッピング。全員が同じ周期にならない
# よう、_floor_token側で人物ごとにanimation-delay/durationをずらす。
AI_OFFICE_IDLE_ANIMATION_BY_TYPE = {
    "typing": "ai-office-idle-typing",
    "reading": "ai-office-idle-reading",
    "analyzing": "ai-office-idle-analyzing",
    "waiting": "ai-office-idle-waiting",
}

# MISSION 083: オフィス・社長室・休憩室の3スペースで、部署担当・拡張担当を
# 問わず1つの辞書から社員情報(名前・スプライト位置・idle種別)を引けるように
# する(AIオフィス本体の_render_ai_office_scene内のローカル変数staff_names
# などとは別に、モジュールレベルで公開する)。
AI_OFFICE_STAFF_BY_KEY = {
    d["key"]: {
        "name": d["staff_name"], "sprite": d["sprite"], "idle_type": d["idle_type"],
    }
    for d in AI_OFFICE_DEPARTMENTS
}
AI_OFFICE_STAFF_BY_KEY.update({
    s["key"]: {"name": s["name"], "sprite": s["sprite"], "idle_type": s["idle_type"]}
    for s in AI_OFFICE_EXTENDED_STAFF
})

# MISSION 090: 作業台帳の担当選択・AIオフィスの全15人状態反映で、常に
# 同じ並び順(部署5人→拡張10人)を共有するための一覧。
AI_OFFICE_ALL_STAFF_KEYS = [d["key"] for d in AI_OFFICE_DEPARTMENTS] + [
    s["key"] for s in AI_OFFICE_EXTENDED_STAFF
]

# MISSION 090: 作業台帳(work_items)のstatus値→日本語ラベル。
WORK_ITEM_STATUS_LABELS = {"today": "今日", "week": "今週", "hold": "保留", "done": "完了"}

# 12人分のidleアニメーションの周期をずらすための通し番号(表示順に意味は
# ない)。_render_ai_office_scene内のidle_index_by_keyと同じ考え方を、
# オフィス・社長室・休憩室でも使えるようモジュールレベルに公開する。
AI_OFFICE_IDLE_ORDER = [d["key"] for d in AI_OFFICE_DEPARTMENTS] + [
    s["key"] for s in AI_OFFICE_EXTENDED_STAFF
]
AI_OFFICE_IDLE_INDEX_BY_KEY = {key: i for i, key in enumerate(AI_OFFICE_IDLE_ORDER)}


def _ai_office_idle_style(key):
  idx = AI_OFFICE_IDLE_INDEX_BY_KEY[key]
  delay = -(idx * 0.37 + 0.2)
  duration = 3.4 + (idx % 5) * 0.3
  return f'animation-delay:{delay:.2f}s;animation-duration:{duration:.2f}s'


def _ai_office_space_token(scope, key, pos, status_key="waiting", phase_text=""):
  """MISSION 083: オフィス・社長室・休憩室で使う、AIオフィスと同じ立体
  スプライト社員トークン。

  AIオフィスのフロアマップで使っているものと同じCSSクラス
  (ai-office-floormap-token/-sprite/-footstep/-report-ring/-nameplate)を
  再利用するため、黒いカード背景・モヤ・四角い背景・過剰な発光は追加で
  発生せず、足元の細い状態リングと小さな名前表示だけになる。各スペース
  独自のシーン(position:relativeの.scene)の中に、左上を基準とした
  left/top%の絶対配置でそのまま置ける。
  """
  person = AI_OFFICE_STAFF_BY_KEY[key]
  name = person["name"]
  idle_class = AI_OFFICE_IDLE_ANIMATION_BY_TYPE[person["idle_type"]]
  clip_path = AI_OFFICE_SPRITE_CLIP_PATHS[key]
  status_label = AI_OFFICE_STATUS_LABELS[status_key]
  mode_label = "実績表示" if status_key == "working" else "デモ表示"
  phase_html = (
      f'<span class="ai-office-nameplate-phase">{phase_text}</span>'
      if phase_text else ""
  )
  uid = f"{scope}-{key}"
  return (
      f'<span class="ai-office-floormap-token {idle_class} '
      f'ai-office-floormap-token-{status_key}" '
      f'id="space-token-{uid}" data-person="{key}" '
      f'role="img" aria-label="{name}" '
      f'style="left:{pos["left"]}%;top:{pos["top"]}%;{_ai_office_idle_style(key)}">'
      f'<span class="ai-office-floormap-sprite" id="space-sprite-{uid}" '
      f'style="background-position:{_ai_office_sprite_position(person["sprite"])};'
      f'clip-path:{clip_path};-webkit-clip-path:{clip_path}"></span>'
      '<span class="ai-office-footstep"></span>'
      '<span class="ai-office-report-ring" aria-hidden="true"></span>'
      f'<span class="ai-office-nameplate" id="space-nameplate-{uid}">'
      f'<i class="ai-office-nameplate-dot ai-office-nameplate-dot-{status_key}" '
      f'id="space-nameplate-dot-{uid}"></i>'
      f'<span id="space-nameplate-name-{uid}">{name}</span>'
      f'{phase_html}'
      f'<span class="sr-only" id="space-nameplate-status-{uid}"> '
      f'{status_label}（{mode_label}）</span>'
      '</span>'
      '</span>'
  )


# フロアマップ画像の中央通路(光る地球儀のあたり)を、交流デモ用の
# 「休憩スペース」として扱う。
AI_OFFICE_LOUNGE_POSITION = {"left": 50, "top": 55}

# パーツ1: 今日のタスク(デモ)。実在の投稿・売上・作業結果ではないことを
# 画面上で常に明示する(_render_ai_office_scene内でデモタグを添える)。
AI_OFFICE_TODAY_TASKS = [
    {"department": "room", "text": "楽天ROOMの反応が良いジャンルを確認する"},
    {"department": "note", "text": "note記事候補の見出し構成を確認する"},
    {"department": "pinterest", "text": "Pinterestの保存数を記録する"},
    {"department": "analytics", "text": "今週の数字を比較して判断メモ案を作る"},
]

# パーツ2: 動いている仕事と結果(デモ)。statusはAI_OFFICE_STATUS_LABELSの
# キーを使い、実稼働・自動実行を装わない。
AI_OFFICE_RUNNING_WORK = [
    {"department": "room", "item": "ROOM候補ジャンルの確認", "status": "pending"},
    {"department": "note", "item": "note下書きの見出し確認", "status": "waiting"},
    {"department": "pinterest", "item": "Pin導線候補の整理", "status": "demo_done"},
    {"department": "analytics", "item": "週次比較のデモ判断案", "status": "waiting"},
]

# パーツ3: AIとのチャット窓口(デモ)。外部AI APIへの送信・自動応答は行わず、
# あらかじめ用意した会話例を静的に表示するだけ。
AI_OFFICE_CHAT_DEMO_MESSAGES = [
    {"speaker": "you", "text": "今日確認することを教えて。"},
    {
        "speaker": "boss",
        "text": "（デモ）ROOMの反応確認とnote見出しの整理が候補です。実際の"
                "やり取りはまだ接続されていません。",
    },
]

# パーツ4: 情報源の鮮度モニター(デモ)。実際の取得日時は表示せず、全項目を
# 「未接続・デモ」で統一する。
AI_OFFICE_SOURCE_CHANNELS = ["楽天ROOM", "楽天アフィリエイト", "note", "Pinterest", "Threads"]

# パーツ5: 成果物一覧。実在するページ・フォルダだけを案内し、実在しない
# ファイルを実在するように見せない。hrefがNoneの項目はFlaskで配信していない
# リポジトリ内フォルダ(資料室)であることを示す。
AI_OFFICE_DELIVERABLES = [
    {
        "label": "資料室",
        "description": "会社の共通ルールと担当チームの仕事マニュアル"
                        "（company_knowledge/ フォルダ内）",
        "href": None,
    },
    {
        "label": "ROOM投稿候補の下書き",
        "description": "楽天ROOM 毎日の投稿候補（下書き）画面",
        "href": "/content-studio/room-daily-candidates",
    },
    {
        "label": "note記事候補の下書き",
        "description": "note記事候補（毎日2本の下書き）画面",
        "href": "/content-studio/note-daily-candidates",
    },
    {
        "label": "判断メモ",
        "description": "運用司令室の判断メモ（記録ログ）",
        "href": "/command-center",
    },
]

# パーツ6: 活動フィード(デモ)。実際のAI作業ログではないことを明記する。
AI_OFFICE_ACTIVITY_FEED = [
    "デモ：担当チームの役割を読み込みました",
    "デモ：資料室のルールを確認しました",
    "デモ：今日のタスク候補を表示しました",
]
AI_OFFICE_ACTIVITY_FEED_MAX_ITEMS = 5

# MISSION 070: オフィスフロアマップ上でAI社員が1人ずつ「自席で作業→指令デスク
# へ報告→自席へ戻る」を巡回するデモアニメーション用データ。すべてローカルの
# CSSアニメーション+JavaScriptで完結し、外部通信・fetch・XMLHttpRequest・
# WebSocket・localStorageへの保存は一切行わない(ページ再読み込みで初期状態に
# 戻ってよい)。ここに書く会話文・活動フィード文言は、実行済みの投稿・送信・
# 売上・反応数と誤認されない、明示的なデモ用の文言に限定する。
#
# 座標(left/top)は、フロアマップ画像(1254×1254、正方形)に対する百分率で、
# 各部署の机にいるAI社員キャラクターのおおよその位置を示す。
# MISSION 074: 全身の立体キャラクターを大きく表示するようになったため、
# 12人が重ならないよう、各部屋の実際の家具配置に合わせて座標を再計算した
# (指令デスク3人・技術品質2人・note2人・ROOM1人・Pinterest2人・分析2人)。
# MISSION 075: 常時の巡回・交流デモが増え、他部署への「訪問」中も
# 訪問先の在席者と重ならない必要が出てきたため、12人分の座席を
# 4列(left=20/36/52/68/84)×3行(top=22/40/58/76、いずれも列・行の
# 間隔がキャラクター1体分以上空くよう計算済み)の格子上に再配置し、
# 各部署の「訪問者スロット」(AI_OFFICE_VISITOR_SLOTS)も同じ格子の
# 空きマスに割り当てた。ズームやキャラクターサイズが変わった場合は、
# この間隔(列は16%以上、行は18%以上)を目安に再計算すること。
AI_OFFICE_FLOOR_POSITIONS = {
    "operations_lead": {"left": 20, "top": 22},
    "note": {"left": 20, "top": 40},
    "pinterest": {"left": 20, "top": 76},
    "room": {"left": 52, "top": 40},
    "analytics": {"left": 68, "top": 58},
}

# MISSION 076: 対面報告の「訪問者スロット」(AI_OFFICE_VISITOR_SLOTS)は
# 報告"先"(受け手)ごとに1つ定義する。報告する本人は必ずこのスロットへ
# 歩いて行き、受け手本人の座席とは重ならない位置で向かい合う。
# MISSION 070〜075の全社員報告(指令デスクへの直接報告)は廃止し、
# 悠・彩・伊織・蓮・柴犬社長など、役割ごとの受け手へ個別に報告する形へ
# 変更した(AI_OFFICE_REPORT_ROUTES)。noteは、悠・彩たちとは別に、
# 凛が資料室確認で立ち寄る先(AI_OFFICE_INTERACTION_SCENES)としても
# 引き続き使うため、訪問者スロットを維持する。
# MISSION 077: 伊織→蓮の報告ルートを追加したため、蓮用の訪問者スロットを
# 追加した(指令デスク3人・空きマスの1つを使用、12人・既存スロットいずれ
# とも列16%以上または行18%以上離れている)。
AI_OFFICE_VISITOR_SLOTS = {
    "operations_lead": {"left": 36, "top": 40},
    "analytics": {"left": 84, "top": 76},
    "note": {"left": 36, "top": 76},
    "yu": {"left": 52, "top": 22},
    "aya": {"left": 68, "top": 76},
    "iori": {"left": 84, "top": 40},
    "ren": {"left": 52, "top": 58},
}

# MISSION 076: AIオフィスの報告演出を、「指令デスクへ移動するだけ」から、
# 報告先の社員の前まで歩いて対面で会話する形に変更した。報告先は柴犬社長
# だけに集中させず、役割に応じて悠(進行管理・一次報告)・彩(連携・部署間
# 引き継ぎ)・伊織(品質確認)・蓮(安全・承認確認)へ分散し、柴犬社長は
# 悠・蓮から上がる重要なまとめ報告だけを受ける。各ルートは
# mover(報告する本人)→receiver(報告を受ける本人)の対面会話として
# 表現し、mover_line(報告者のセリフ)→receiver_line(受け手の返答)の
# 順に吹き出し・会話ログへ表示する。feed_textは活動フィード用の要約で、
# 「誰が誰へ何を報告したか」が分かる文言に統一する。
AI_OFFICE_REPORT_ROUTES = [
    {
        "key": "room_to_yu",
        "mover": "room",
        "receiver": "yu",
        "mover_line": "ROOM候補を整理しました",
        "receiver_line": "受け取りました。次の確認へ進めます",
        "feed_text": "里奈が悠へROOM候補の報告をしました",
    },
    {
        "key": "note_to_aya",
        "mover": "note",
        "receiver": "aya",
        "mover_line": "見出し構成をまとめました",
        "receiver_line": "美咲にも共有して方向性をそろえます",
        "feed_text": "海が彩へ見出し構成の報告をしました",
    },
    {
        "key": "pinterest_to_aya",
        "mover": "pinterest",
        "receiver": "aya",
        "mover_line": "画像テーマ候補を用意しました",
        "receiver_line": "noteの見出しと合わせて確認します",
        "feed_text": "美咲が彩へ画像テーマ候補の報告をしました",
    },
    {
        "key": "sou_to_iori",
        "mover": "sou",
        "receiver": "iori",
        "mover_line": "画面表示を確認しました",
        "receiver_line": "品質観点で確認します",
        "feed_text": "蒼が伊織へ画面表示の報告をしました",
    },
    {
        "key": "yui_to_analytics",
        "mover": "yui",
        "receiver": "analytics",
        "mover_line": "情報源の鮮度を確認しました",
        "receiver_line": "比較メモへ反映します",
        "feed_text": "結が葵へ情報源の鮮度の報告をしました",
    },
    {
        "key": "analytics_to_yu",
        "mover": "analytics",
        "receiver": "yu",
        "mover_line": "確認済みの数字を比較しました",
        "receiver_line": "判断メモとして整理します",
        "feed_text": "葵が悠へ数字比較の報告をしました",
    },
    {
        "key": "yu_to_president",
        "mover": "yu",
        "receiver": "operations_lead",
        "mover_line": "各部署の報告をまとめました",
        "receiver_line": "受け取りました。利用者の確認待ちにします",
        "feed_text": "悠が柴犬社長へまとめ報告をしました",
    },
    {
        "key": "ren_to_president",
        "mover": "ren",
        "receiver": "operations_lead",
        "mover_line": "安全・承認確認を終えました",
        "receiver_line": "確認しました。外部操作は利用者判断です",
        "feed_text": "蓮が柴犬社長へ安全・承認確認の報告をしました",
    },
    # MISSION 077: 凛(資料室管理)→海・伊織(品質確認)→蓮・彩(連携担当)→悠の
    # 3ルートを追加し、社長へ直接報告するのは悠・蓮の2人だけであることを
    # さらに明確にした(残り9ルートはすべて悠・彩・伊織・蓮のいずれかへ
    # 報告する)。
    {
        "key": "rin_to_note",
        "mover": "rin",
        "receiver": "note",
        "mover_line": "資料室の内容を確認しました",
        "receiver_line": "確認ありがとう。記事に反映します",
        "feed_text": "凛が海へ資料室確認の報告をしました",
    },
    {
        "key": "iori_to_ren",
        "mover": "iori",
        "receiver": "ren",
        "mover_line": "表示内容の品質確認を終えました",
        "receiver_line": "安全・承認の観点で確認します",
        "feed_text": "伊織が蓮へ品質確認の報告をしました",
    },
    {
        "key": "aya_to_yu",
        "mover": "aya",
        "receiver": "yu",
        "mover_line": "部署間の連携状況を共有しました",
        "receiver_line": "進行管理に反映します",
        "feed_text": "彩が悠へ連携状況の報告をしました",
    },
]

# MISSION 080: 運用司令室の「本日の運用記録」に入力された実績を、AIオフィス
# 上でどの社員の対面報告として表示するかのマッピング。種別による判定
# (数字記録→葵の数字確認・比較、承認待ち→蓮の安全・承認確認)を、媒体による
# 判定(Pinterest→美咲、note→海、楽天ROOM→里奈、共通→彩の部署間引き継ぎ)
# より先に見る。いずれにも当てはまらない場合(楽天アフィリエイト・
# Threadsで、確認/下書き/投稿済みの記録など、専任担当がいない媒体)は、
# 進行管理の悠がまとめて受け持つ(「全体進行・最終報告 → 悠、必要時のみ
# 柴犬社長」)。悠・蓮はそれぞれ既存の対面報告ルート(yu_to_president・
# ren_to_president)で柴犬社長へ報告するため、柴犬社長への表示は「必要時
# (悠・蓮が実績を持つとき)のみ」に自然となる。
AI_OFFICE_DAILY_RECORD_TYPE_OWNERS = {
    "承認待ち": "ren",
    "数字記録": "analytics",
}
AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS = {
    "Pinterest": "pinterest",
    "note": "note",
    "楽天ROOM": "room",
    "共通": "aya",
}
AI_OFFICE_DAILY_RECORD_FALLBACK_OWNER = "yu"

# MISSION 080: 実績の種別ごとに、受け手が返す短い確認の相づち。利用者が
# 入力した内容そのものに対する返答は用意できないため、種別に対する定型の
# 確認応答とする(断定・評価はしない)。
AI_OFFICE_DAILY_RECORD_TYPE_ACK = {
    "確認": "確認ありがとうございます。記録しました",
    "下書き": "下書きを確認しました",
    "投稿済み": "投稿済みとして記録しました",
    "数字記録": "数字を記録として確認しました",
    "承認待ち": "承認待ちとして記録しました",
}

# MISSION 084: 「今日の実行キュー」(/ai-office)専用の媒体→担当割り当て。
# 既存の対面報告ルート向けAI_OFFICE_DAILY_RECORD_MEDIA_OWNERSでは
# 媒体「共通」を彩(aya、部署間の引き継ぎ役)に割り当てているが、この
# キューでは要件どおり「共通・その他 → 悠」にするため、専用の媒体
# マッピングを別に持つ(Pinterest・note・楽天ROOMの3媒体は共通)。
# 種別(数字記録→分析担当・承認待ち→蓮)の割り当てと、どれにも該当しない
# 場合のfallback(悠)は、既存のAI_OFFICE_DAILY_RECORD_TYPE_OWNERS /
# AI_OFFICE_DAILY_RECORD_FALLBACK_OWNERをそのまま再利用する。
AI_OFFICE_QUEUE_MEDIA_OWNERS = {
    "Pinterest": "pinterest",
    "note": "note",
    "楽天ROOM": "room",
}

# 種別ごとに、利用者へ誤解を与えない「現在の状態」表現。「投稿済み」は
# 利用者自身が記録した場合にのみこの状態になり、AIオフィス側が独自に
# 外部投稿の成否を判断・断定することはない(すべて読み取り専用)。
AI_OFFICE_QUEUE_STATUS_BY_TYPE = {
    "下書き": "手動投稿待ち",
    "投稿済み": "反応確認待ち",
    "数字記録": "数値を確認済み",
    "承認待ち": "確認・承認待ち",
    "確認": "確認済み",
}

AI_OFFICE_QUEUE_NEXT_ACTION_BY_TYPE = {
    "下書き": "下書きを確認し、準備ができたら手動で投稿してください。",
    "投稿済み": "外部サービスで実際の反応（保存数・クリック・スキなど）を確認してください。",
    "数字記録": "記録した数字を分析ラボの比較メモに反映してください。",
    "承認待ち": "内容を確認し、承認するかどうかを判断してください。",
    "確認": "追加の対応は不要です。必要であれば次の記録を残してください。",
}

AI_OFFICE_QUEUE_DEFAULT_STATUS = "記録を確認してください"
AI_OFFICE_QUEUE_DEFAULT_NEXT_ACTION = "内容を確認し、必要な対応を判断してください。"
AI_OFFICE_QUEUE_EMPTY_MESSAGE = (
    "本日の記録はまだありません。運用司令室で記録するとここに表示されます。"
)

# MISSION 085: 「直近の実績」(当日より前の運用記録、新しい順で最大5件)。
# 種別ごとに「記録した」という事実だけを述べ、外部での実行結果を断定
# しない表現にする(「投稿済み」だけは、利用者本人が投稿済みとして記録
# したことを明示する「利用者が投稿済みとして記録」という文言にする)。
AI_OFFICE_RECENT_LABEL_BY_TYPE = {
    "投稿済み": "利用者が投稿済みとして記録",
    "下書き": "下書きとして記録",
    "数字記録": "数字を記録",
    "承認待ち": "承認待ちとして記録",
    "確認": "確認として記録",
}
AI_OFFICE_RECENT_MAX_ITEMS = 5
AI_OFFICE_RECENT_EMPTY_MESSAGE = "直近の運用記録はまだありません"

# MISSION 086: 「柴犬社長からの本日の指示」カード用の優先ルール(上から
# 順に最初に当てはまったものだけを使う)。常に1件だけを表示し、行動
# ボタンも1つだけにする。「投稿済み」は利用者が投稿済みとして記録した
# 場合にのみ判定に使い、外部投稿の成否をAI側が推測・断定することはない
# (すべて読み取り専用でlocalStorageを参照するだけ)。
AI_OFFICE_DIRECTIVE_RULES = [
    {
        "key": "draft",
        "task": "下書きを確認し、手動で投稿してください",
        "reason": "本日の下書き記録があります",
        "href": "/content-studio",
        "label": "投稿企画工場を開く",
    },
    {
        "key": "posted",
        "task": "投稿の反応を確認してください",
        "reason": "本日投稿済みの記録があります",
        "href": "/command-center",
        "label": "運用司令室を開く",
    },
    {
        "key": "approval",
        "task": "承認待ちの内容を確認してください",
        "reason": "本日の承認待ち記録があります",
        "href": "/command-center",
        "label": "運用司令室を開く",
    },
    {
        "key": "prepare",
        "task": "今日は投稿候補を1件だけ用意してください",
        "reason": "過去の運用記録はありますが、本日の記録がまだありません",
        "href": "/content-studio",
        "label": "投稿企画工場を開く",
    },
    {
        "key": "start",
        "task": "まず運用司令室で、今日の作業を1件記録してください",
        "reason": "運用記録がまだ1件もありません",
        "href": "/command-center",
        "label": "運用司令室を開く",
    },
]


def _ai_office_daily_record_reader_script():
  """MISSION 083: オフィス・社長室・休憩室の3スペースで共通に使う、運用
  司令室の「本日の運用記録」localStorageを読み取るためのJS断片(読み取り
  専用。書き込み・削除は一切行わない)。

  AIオフィス本体のbuildRealRecordQueueと同じ判定順(種別→媒体→fallback)
  を、書き込みを伴わない小さな関数群として切り出したもの。
  """
  data = json.dumps(
      {
          "recordKey": AI_OFFICE_DAILY_RECORD_STORAGE_KEY,
          "typeOwners": AI_OFFICE_DAILY_RECORD_TYPE_OWNERS,
          "mediaOwners": AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS,
          "fallbackOwner": AI_OFFICE_DAILY_RECORD_FALLBACK_OWNER,
      },
      ensure_ascii=False,
  )
  return (
      f'var SPACE_RECORD_DATA={data};'
      'function spaceTodayDateStr(){'
      'var d=new Date();'
      'function pad(n){return n<10?"0"+n:""+n;}'
      'return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());'
      '}'
      'function spaceLoadTodayRecords(){'
      'var raw=null;'
      'try{raw=window.localStorage.getItem(SPACE_RECORD_DATA.recordKey);}catch(e){raw=null;}'
      'var list=[];'
      'try{list=raw?JSON.parse(raw):[];}catch(e){list=[];}'
      'if(!Array.isArray(list))list=[];'
      'var today=spaceTodayDateStr();'
      'return list.filter(function(r){return r&&r.date===today&&r.content&&'
      'String(r.content).trim();});'
      '}'
      'function spaceOwnerForRecord(rec){'
      'return SPACE_RECORD_DATA.typeOwners[rec.type]||'
      'SPACE_RECORD_DATA.mediaOwners[rec.media]||SPACE_RECORD_DATA.fallbackOwner;'
      '}'
  )


# MISSION 081: 「手動投稿を完了した」ボタン(楽天ROOM候補・note記事候補、
# 将来のPinterest候補にも再利用する共通部品)。押すと、運用司令室の
# 「本日の運用記録」と同じlocalStorageキー(AI_OFFICE_DAILY_RECORD_
# STORAGE_KEY)へ、種別「投稿済み」の記録を1件追記する。外部投稿・送信・
# ログイン・API通信は一切行わず、投稿の成否も検知しない。実際に外部画面で
# 投稿を確認した利用者本人が押すことを前提にした、ローカル記録専用の
# ボタンである。
AI_OFFICE_MANUAL_POST_COMPLETE_NOTE = (
    "このボタンは外部へ投稿しません。実際の投稿を確認した後、社内の運用"
    "記録へ保存します。"
)


def _manual_post_complete_box_html(slot):
  """候補カード内に置く「手動投稿を完了した」ボタン一式のHTMLを返す。

  content_selector/url_selectorは、_manual_post_complete_script側で
  ボタンの祖先カード([data-slot]を持つ要素)内から値を読み取るために使う
  CSSセレクタ文字列で、呼び出し側(ROOM・note・将来のPinterest)ごとに
  異なる入力欄クラスを渡せるようにする。
  """
  return (
      '<div class="manual-post-complete-box">'
      f'<button type="button" class="manual-post-complete-btn" '
      f'data-slot="{slot}">手動投稿を完了した</button>'
      f'<p class="manual-post-complete-note">{AI_OFFICE_MANUAL_POST_COMPLETE_NOTE}</p>'
      f'<p class="manual-post-complete-status" id="manual-post-status-{slot}" '
      'aria-live="polite"></p>'
      '</div>'
  )


def _manual_post_complete_script(
    media_label, content_selector, url_selector=None,
    genre_selector=None, intro_selector=None, hashtag_selector=None,
    manual_checked_selector=None, date_input_id=None,
):
  """「手動投稿を完了した」ボタンのクリック処理(JS)を返す。

  media_label: 保存するentry.mediaの値(例:"楽天ROOM"、"note")。
  content_selector: ボタンの祖先カード内で、内容(商品名・タイトル)を
    読み取る入力欄のCSSセレクタ(例:".rc-product-name")。
  url_selector: 同様にURLを読み取るCSSセレクタ。候補にURL欄がない場合は
    Noneを渡す(noteの記事候補など)。
  genre_selector/intro_selector/hashtag_selector/manual_checked_selector/
    date_input_id: MISSION 088で追加。アプリ内DB(/api/dashboard/*)へ
    候補の現在の状態(ジャンル・紹介文・ハッシュタグ・手動確認状態・
    対象日)もあわせて保存するために使う(候補にその項目がない場合は
    Noneのままでよい)。
  """
  url_selector_js = (
      json.dumps(url_selector, ensure_ascii=False) if url_selector else "null"
  )
  genre_selector_js = (
      json.dumps(genre_selector, ensure_ascii=False) if genre_selector else "null"
  )
  intro_selector_js = (
      json.dumps(intro_selector, ensure_ascii=False) if intro_selector else "null"
  )
  hashtag_selector_js = (
      json.dumps(hashtag_selector, ensure_ascii=False) if hashtag_selector else "null"
  )
  manual_checked_selector_js = (
      json.dumps(manual_checked_selector, ensure_ascii=False)
      if manual_checked_selector else "null"
  )
  date_input_id_js = (
      json.dumps(date_input_id, ensure_ascii=False) if date_input_id else "null"
  )
  return (
      '(function(){'
      f'var RECORD_KEY={json.dumps(AI_OFFICE_DAILY_RECORD_STORAGE_KEY, ensure_ascii=False)};'
      f'var MEDIA_LABEL={json.dumps(media_label, ensure_ascii=False)};'
      f'var CONTENT_SELECTOR={json.dumps(content_selector, ensure_ascii=False)};'
      f'var URL_SELECTOR={url_selector_js};'
      f'var GENRE_SELECTOR={genre_selector_js};'
      f'var INTRO_SELECTOR={intro_selector_js};'
      f'var HASHTAG_SELECTOR={hashtag_selector_js};'
      f'var MANUAL_CHECKED_SELECTOR={manual_checked_selector_js};'
      f'var DATE_INPUT_ID={date_input_id_js};'
      'function safeGetRecord(){'
      'try{return window.localStorage.getItem(RECORD_KEY);}catch(e){return null;}'
      '}'
      'function safeSetRecord(v){'
      'try{window.localStorage.setItem(RECORD_KEY,v);}catch(e){'
      '/* localStorageが使えない環境でも画面は壊さない */'
      '}'
      '}'
      'function todayStr(){'
      'var d=new Date();'
      'function pad(n){return n<10?"0"+n:""+n;}'
      'return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());'
      '}'
      'function loadRecordEntries(){'
      'try{'
      'var raw=safeGetRecord();'
      'var list=raw?JSON.parse(raw):[];'
      'return Array.isArray(list)?list:[];'
      '}catch(e){return [];}'
      '}'
      # MISSION 088: アプリ内DB(同一オリジンのローカルAPI)への保存は、
      # 失敗してもローカル保存・画面表示には一切影響させない
      # (fetchをcatchで握りつぶすだけの「ベストエフォート」書き込み)。
      # 外部サービスへの送信・ログイン・API通信は行わない。
      'function postJsonSafe(url,payload){'
      'try{'
      'window.fetch(url,{'
      'method:"POST",'
      'headers:{"Content-Type":"application/json"},'
      'body:JSON.stringify(payload)'
      '}).catch(function(){});'
      '}catch(e){/* fetch未対応環境でも画面は壊さない */}'
      '}'
      'document.querySelectorAll(".manual-post-complete-btn").forEach(function(btn){'
      'btn.addEventListener("click",function(){'
      'var card=btn.parentElement?btn.parentElement.closest("[data-slot]"):null;'
      'var slot=btn.dataset.slot;'
      'var statusEl=document.querySelector("#manual-post-status-"+slot);'
      'var contentEl=card?card.querySelector(CONTENT_SELECTOR):null;'
      'var content=contentEl?contentEl.value.trim():"";'
      'if(!content){'
      'if(statusEl)statusEl.textContent='
      '"商品名・タイトルを入力してから押してください。";'
      'return;'
      '}'
      'var urlEl=(URL_SELECTOR&&card)?card.querySelector(URL_SELECTOR):null;'
      'var url=urlEl?urlEl.value.trim():"";'
      'var today=todayStr();'
      'var entries=loadRecordEntries();'
      'var isDuplicate=entries.some(function(e){'
      'return e&&e.date===today&&e.media===MEDIA_LABEL&&e.content===content;'
      '});'
      'if(isDuplicate){'
      'if(statusEl)statusEl.textContent="本日すでに記録済みです。";'
      'return;'
      '}'
      'entries.push({'
      'date:today,media:MEDIA_LABEL,type:"投稿済み",content:content,'
      'metric:"",reference:url'
      '});'
      'safeSetRecord(JSON.stringify(entries));'
      'if(statusEl)statusEl.textContent='
      '"運用記録に保存しました（AIオフィスにも反映されます）。";'
      # MISSION 088: 「手動投稿を完了した」を押したタイミングで、既存の
      # 候補・運用記録をアプリ内DBへも保存する(読み取り専用ではなく、
      # この操作の結果だけを書き込む)。
      'postJsonSafe("/api/dashboard/daily-records",{'
      'date:today,media:MEDIA_LABEL,type:"投稿済み",content:content,'
      'metric:"",reference:url'
      '});'
      'var genreEl=(GENRE_SELECTOR&&card)?card.querySelector(GENRE_SELECTOR):null;'
      'var genre=genreEl?genreEl.value.trim():"";'
      'var introEl=(INTRO_SELECTOR&&card)?card.querySelector(INTRO_SELECTOR):null;'
      'var intro=introEl?introEl.value:"";'
      'var hashtagEls=(HASHTAG_SELECTOR&&card)?'
      'card.querySelectorAll(HASHTAG_SELECTOR):[];'
      'var hashtags=Array.prototype.map.call(hashtagEls,function(el){'
      'return el.value.trim();'
      '}).filter(function(v){return v;});'
      'var checkedEl=(MANUAL_CHECKED_SELECTOR&&card)?'
      'card.querySelector(MANUAL_CHECKED_SELECTOR):null;'
      'var manualChecked=checkedEl?checkedEl.checked:false;'
      'var dateInputEl=DATE_INPUT_ID?document.getElementById(DATE_INPUT_ID):null;'
      'var targetDate=(dateInputEl&&dateInputEl.value)?dateInputEl.value:today;'
      'postJsonSafe("/api/dashboard/candidates",{'
      'targetDate:targetDate,media:MEDIA_LABEL,slot:Number(slot),genre:genre,'
      'productName:content,url:url,intro:intro,hashtags:hashtags,'
      'manualChecked:manualChecked,manualPosted:true'
      '});'
      '});'
      '});'
      '})();'
  )

# MISSION 077: 進行バナー(「対面報告中 悠（進行管理） → 柴犬社長
# （最終確認）」)に使う、報告の文脈での短い役割ラベル。desk_label・
# role_labelとは別に、バナーの文字数を短く保つための専用ラベルを持つ
# (柴犬社長は運用責任者ではなく「最終確認」という、報告を受け取る側の
# 役割として表示する)。
AI_OFFICE_REPORT_ROLE_LABELS = {
    "operations_lead": "最終確認",
    "room": "ROOM担当",
    "note": "note担当",
    "pinterest": "Pinterest担当",
    "analytics": "分析担当",
    "sou": "技術担当",
    "iori": "品質確認",
    "aya": "連携担当",
    "rin": "資料室管理",
    "yu": "進行管理",
    "yui": "鮮度確認",
    "ren": "安全・承認確認",
}

# MISSION 077: 名前札の「◯◯さんへ報告中」表記を短く保つための略称
# (柴犬社長のみ「社長」と略す。他は元の名前で十分短いためそのまま使う)。
AI_OFFICE_SHORT_NAMES = {
    "operations_lead": "社長",
}

# MISSION 071: 社員本人が歩いて回るフロアマップ用のスプライト画像
# (2列×4行、8人)。MISSION 073で、より立体的な3Dキャラクター調の
# スプライト(static/images/ai-office-team-3d.png、3列×4行、12人)へ
# 全面更新し、AIオフィス画面ではこちらだけを表示する。旧スプライト
# ファイル自体は削除せず残すが、画面には使用しない
# (AI_OFFICE_LEGACY_SPRITE_SHEET_RELATIVE_PATHとしてのみ参照を保持)。
AI_OFFICE_LEGACY_SPRITE_SHEET_RELATIVE_PATH = "images/ai-office-team-sprites.png"
AI_OFFICE_SPRITE_SHEET_RELATIVE_PATH = "images/ai-office-team-3d.png"
AI_OFFICE_SPRITE_COLS = 3
AI_OFFICE_SPRITE_ROWS = 4

# MISSION 079: スプライトシートの各コマには、暗いビネット背景(グラ
# デーション)が描き込まれており、MISSION 074〜078のradial-gradientマスク
# (フェード)や状態別のfilter:drop-shadowでは、単純な楕円で切り取るだけ
# だったため、体・持ち物からはみ出た背景がまだ見えていた。ここでは
# 各コマの画像を解析し(背景の滑らかなグラデーションからの差分で人物領域を
# 検出→最大の連結領域→行ごとの左右端をたどる)、12人それぞれの輪郭に沿った
# clip-path用の多角形をあらかじめ計算して埋め込んでいる(生成手順は
# コミットに含めていない一時スクリプトによるもので、この定数が最終結果)。
# 単純な四角形・円形ではなく、頭・肩・腕・持ち物・足・足元の光るリング
# (スプライト自体に描かれているもの)まで含めた輪郭になっている。
AI_OFFICE_SPRITE_CLIP_PATHS = {
    "operations_lead": "polygon(41.6% 3.9%,69.8% 6.2%,71.0% 8.9%,72.4% 11.7%,73.0% 14.3%,74.8% 17.2%,76.8% 19.8%,77.1% 22.7%,77.1% 25.3%,76.2% 28.1%,81.5% 30.7%,83.0% 33.6%,83.6% 36.2%,83.0% 39.1%,81.8% 41.7%,80.4% 44.5%,80.4% 47.1%,79.5% 50.0%,78.6% 52.9%,75.4% 55.5%,76.0% 58.3%,78.0% 60.9%,76.8% 63.8%,74.5% 66.4%,74.2% 69.3%,73.6% 71.9%,72.7% 74.7%,72.1% 77.3%,72.1% 80.2%,85.0% 82.8%,86.8% 85.7%,86.8% 88.3%,84.8% 91.1%,84.8% 93.8%,25.2% 91.1%,22.6% 88.3%,16.4% 85.7%,16.1% 82.8%,15.5% 80.2%,19.1% 77.3%,22.0% 74.7%,25.2% 71.9%,34.6% 69.3%,28.7% 66.4%,26.4% 63.8%,25.8% 60.9%,25.2% 58.3%,24.9% 55.5%,24.9% 52.9%,25.8% 50.0%,27.6% 47.1%,35.8% 44.5%,34.9% 41.7%,33.7% 39.1%,33.7% 36.2%,33.7% 33.6%,36.7% 30.7%,36.1% 28.1%,36.1% 25.3%,36.4% 22.7%,37.2% 19.8%,38.1% 17.2%,38.1% 14.3%,38.7% 11.7%,39.6% 8.9%,41.6% 6.2%)",
    "room": "polygon(32.3% 0.0%,75.1% 1.3%,74.5% 4.4%,75.7% 7.6%,77.4% 10.7%,79.5% 13.8%,79.8% 16.9%,76.2% 20.1%,76.2% 23.2%,74.5% 26.3%,82.4% 29.4%,80.1% 32.6%,80.1% 35.7%,77.7% 38.8%,77.7% 41.9%,76.8% 45.1%,75.4% 48.2%,66.9% 51.3%,66.6% 54.4%,66.6% 57.6%,66.3% 60.7%,66.0% 63.8%,65.7% 66.9%,65.7% 70.1%,73.9% 73.2%,80.9% 76.3%,81.5% 79.4%,80.4% 82.6%,71.6% 85.7%,60.7% 88.8%,62.2% 91.9%,65.1% 95.1%,67.4% 98.2%,67.4% 99.7%,31.7% 98.2%,35.5% 95.1%,38.1% 91.9%,39.0% 88.8%,31.7% 85.7%,21.7% 82.6%,20.2% 79.4%,21.1% 76.3%,34.3% 73.2%,34.6% 70.1%,35.2% 66.9%,37.0% 63.8%,38.4% 60.7%,40.2% 57.6%,36.4% 54.4%,36.1% 51.3%,36.7% 48.2%,37.8% 45.1%,34.9% 41.9%,34.6% 38.8%,35.5% 35.7%,37.5% 32.6%,34.9% 29.4%,33.7% 26.3%,34.3% 23.2%,36.4% 20.1%,34.3% 16.9%,34.3% 13.8%,33.4% 10.7%,33.7% 7.6%,33.4% 4.4%,32.3% 1.3%)",
    "note": "polygon(37.0% 0.0%,76.5% 1.3%,64.2% 4.2%,66.0% 7.0%,70.1% 9.9%,70.1% 12.8%,69.2% 15.6%,71.3% 18.5%,74.8% 21.4%,74.8% 24.2%,73.9% 27.1%,76.0% 29.9%,77.7% 32.8%,78.0% 35.7%,78.9% 38.5%,78.9% 41.4%,72.7% 44.3%,72.4% 47.1%,71.3% 50.0%,68.3% 52.9%,68.9% 55.7%,67.2% 58.6%,68.0% 61.5%,68.9% 64.3%,69.8% 67.2%,78.9% 70.1%,86.5% 72.9%,91.2% 75.8%,91.2% 78.6%,89.4% 81.5%,84.2% 84.4%,81.5% 87.2%,74.2% 90.4%,74.2% 93.0%,41.6% 90.4%,26.7% 87.2%,23.5% 84.4%,23.8% 81.5%,25.8% 78.6%,31.4% 75.8%,30.8% 72.9%,31.7% 70.1%,36.1% 67.2%,37.2% 64.3%,37.8% 61.5%,38.7% 58.6%,36.4% 55.7%,36.7% 52.9%,34.9% 50.0%,32.6% 47.1%,27.9% 44.3%,26.1% 41.4%,27.9% 38.5%,26.7% 35.7%,24.6% 32.8%,24.6% 29.9%,25.2% 27.1%,25.5% 24.2%,27.0% 21.4%,29.3% 18.5%,29.6% 15.6%,30.2% 12.8%,31.1% 9.9%,32.6% 7.0%,35.5% 4.2%,37.0% 1.3%)",
    "pinterest": "polygon(0.0% 0.0%,9.7% 1.3%,38.1% 4.4%,50.4% 7.6%,59.8% 10.7%,62.2% 13.8%,63.9% 16.9%,66.6% 20.1%,66.9% 23.2%,66.6% 26.3%,66.0% 29.4%,69.8% 32.6%,72.4% 35.7%,74.2% 38.8%,75.4% 41.9%,71.6% 45.1%,72.4% 48.2%,73.0% 51.3%,73.0% 54.4%,65.7% 57.6%,63.0% 60.7%,63.9% 63.8%,63.9% 66.9%,61.6% 70.1%,73.6% 73.2%,78.3% 76.3%,78.6% 79.4%,81.8% 82.6%,81.8% 85.7%,79.2% 88.8%,77.4% 91.9%,76.2% 95.1%,72.7% 98.2%,72.7% 99.7%,15.0% 98.2%,13.2% 95.1%,6.7% 91.9%,11.7% 88.8%,8.2% 85.7%,7.3% 82.6%,10.0% 79.4%,12.6% 76.3%,15.0% 73.2%,22.0% 70.1%,26.7% 66.9%,26.7% 63.8%,23.2% 60.7%,25.5% 57.6%,22.6% 54.4%,17.3% 51.3%,13.8% 48.2%,9.7% 45.1%,6.7% 41.9%,0.0% 38.8%,0.0% 35.7%,0.0% 32.6%,0.0% 29.4%,0.0% 26.3%,0.0% 23.2%,0.0% 20.1%,0.0% 16.9%,0.0% 13.8%,0.0% 10.7%,0.0% 7.6%,0.0% 4.4%,0.0% 1.3%)",
    "analytics": "polygon(7.0% 0.0%,82.1% 1.3%,79.5% 3.9%,78.0% 6.8%,77.4% 9.4%,75.1% 12.2%,78.9% 14.8%,79.2% 17.7%,81.2% 20.3%,82.7% 23.2%,83.3% 26.0%,81.5% 28.6%,82.1% 31.5%,82.1% 34.1%,83.9% 37.0%,83.9% 39.6%,80.9% 42.4%,79.2% 45.3%,68.6% 47.9%,60.1% 50.8%,59.2% 53.4%,58.9% 56.2%,59.5% 58.9%,60.4% 61.7%,61.3% 64.3%,75.1% 67.2%,76.8% 70.1%,76.8% 72.7%,76.5% 75.5%,78.3% 78.1%,78.3% 81.0%,82.7% 83.6%,79.8% 86.5%,79.8% 89.1%,31.1% 86.5%,20.5% 83.6%,18.2% 81.0%,18.2% 78.1%,19.9% 75.5%,25.8% 72.7%,21.7% 70.1%,22.9% 67.2%,26.7% 64.3%,28.7% 61.7%,33.1% 58.9%,33.4% 56.2%,33.1% 53.4%,29.9% 50.8%,29.9% 47.9%,29.9% 45.3%,23.5% 42.4%,19.4% 39.6%,12.9% 37.0%,12.9% 34.1%,12.9% 31.5%,10.6% 28.6%,9.4% 26.0%,17.6% 23.2%,18.2% 20.3%,21.7% 17.7%,21.7% 14.8%,20.5% 12.2%,17.6% 9.4%,17.6% 6.8%,8.8% 3.9%,7.0% 1.3%)",
    "sou": "polygon(37.2% 3.9%,59.5% 6.2%,62.2% 9.1%,65.1% 12.2%,67.2% 15.1%,70.4% 18.0%,71.3% 21.1%,71.6% 24.0%,68.9% 27.1%,65.1% 29.9%,78.9% 32.8%,78.3% 35.9%,77.4% 38.8%,76.5% 41.7%,75.7% 44.8%,74.8% 47.7%,71.8% 50.8%,68.9% 53.6%,64.8% 56.5%,65.1% 59.6%,61.9% 62.5%,57.5% 65.4%,57.8% 68.5%,61.0% 71.4%,73.6% 74.5%,79.2% 77.3%,80.4% 80.2%,80.4% 83.3%,86.2% 86.2%,85.6% 89.1%,83.9% 92.2%,78.0% 95.1%,75.4% 98.2%,75.4% 99.7%,23.5% 98.2%,22.9% 95.1%,20.5% 92.2%,16.7% 89.1%,16.7% 86.2%,15.2% 83.3%,17.6% 80.2%,18.2% 77.3%,17.9% 74.5%,22.6% 71.4%,25.2% 68.5%,31.1% 65.4%,30.5% 62.5%,29.3% 59.6%,27.6% 56.5%,23.5% 53.6%,22.9% 50.8%,22.9% 47.7%,24.6% 44.8%,25.2% 41.7%,25.2% 38.8%,25.8% 35.9%,25.8% 32.8%,29.6% 29.9%,26.4% 27.1%,26.7% 24.0%,26.4% 21.1%,25.8% 18.0%,26.7% 15.1%,27.3% 12.2%,32.0% 9.1%,37.2% 6.2%)",
    "iori": "polygon(32.0% 0.0%,58.4% 1.3%,55.4% 4.4%,58.9% 7.6%,59.2% 10.7%,58.7% 13.8%,61.3% 16.9%,63.3% 20.1%,63.6% 23.2%,69.2% 26.3%,76.2% 29.4%,77.1% 32.6%,77.1% 35.7%,76.2% 38.8%,75.4% 41.9%,73.3% 45.1%,73.0% 48.2%,70.4% 51.3%,66.9% 54.4%,66.6% 57.6%,66.3% 60.7%,65.7% 63.8%,65.1% 66.9%,65.4% 70.1%,78.6% 73.2%,81.8% 76.3%,83.9% 79.4%,86.8% 82.6%,88.0% 85.7%,85.6% 88.8%,82.1% 91.9%,78.0% 95.1%,67.4% 98.2%,67.4% 99.7%,22.9% 98.2%,22.3% 95.1%,18.2% 91.9%,17.0% 88.8%,16.4% 85.7%,16.1% 82.6%,18.2% 79.4%,20.2% 76.3%,27.9% 73.2%,29.9% 70.1%,35.8% 66.9%,37.8% 63.8%,38.7% 60.7%,35.2% 57.6%,27.0% 54.4%,24.6% 51.3%,24.6% 48.2%,24.6% 45.1%,22.6% 41.9%,21.1% 38.8%,20.8% 35.7%,17.6% 32.6%,15.8% 29.4%,15.2% 26.3%,15.8% 23.2%,18.2% 20.1%,19.1% 16.9%,22.0% 13.8%,23.5% 10.7%,25.5% 7.6%,27.6% 4.4%,32.0% 1.3%)",
    "aya": "polygon(27.3% 0.0%,73.3% 1.3%,56.3% 4.4%,61.0% 7.6%,61.3% 10.7%,62.2% 13.8%,63.3% 16.9%,64.2% 20.1%,66.3% 23.2%,72.7% 26.3%,78.0% 29.4%,84.2% 32.6%,84.2% 35.7%,74.2% 38.8%,74.2% 41.9%,72.7% 45.1%,69.8% 48.2%,68.3% 51.3%,66.0% 54.4%,64.5% 57.6%,63.9% 60.7%,63.0% 63.8%,62.8% 66.9%,61.6% 70.1%,59.8% 73.2%,66.6% 76.3%,75.4% 79.4%,76.8% 82.6%,76.5% 85.7%,73.0% 88.8%,56.6% 91.9%,51.3% 95.1%,63.6% 98.2%,63.6% 99.7%,32.8% 98.2%,39.9% 95.1%,30.5% 91.9%,19.4% 88.8%,13.5% 85.7%,13.2% 82.6%,15.8% 79.4%,18.5% 76.3%,23.2% 73.2%,27.6% 70.1%,25.2% 66.9%,25.2% 63.8%,24.6% 60.7%,25.2% 57.6%,22.0% 54.4%,19.9% 51.3%,19.4% 48.2%,18.5% 45.1%,18.8% 41.9%,17.3% 38.8%,17.3% 35.7%,17.0% 32.6%,17.3% 29.4%,16.7% 26.3%,17.3% 23.2%,18.5% 20.1%,19.4% 16.9%,21.7% 13.8%,25.2% 10.7%,26.7% 7.6%,28.2% 4.4%,27.3% 1.3%)",
    "rin": "polygon(26.4% 0.0%,63.9% 1.3%,62.8% 4.4%,63.0% 7.6%,66.6% 10.7%,66.9% 13.8%,67.7% 16.9%,67.7% 20.1%,66.3% 23.2%,68.6% 26.3%,69.2% 29.4%,69.2% 32.6%,69.2% 35.7%,73.9% 38.8%,74.2% 41.9%,72.7% 45.1%,63.0% 48.2%,61.0% 51.3%,61.0% 54.4%,59.8% 57.6%,60.4% 60.7%,61.0% 63.8%,61.9% 66.9%,62.2% 70.1%,69.2% 73.2%,76.5% 76.3%,77.1% 79.4%,76.8% 82.6%,71.8% 85.7%,49.9% 88.8%,57.2% 91.9%,60.1% 95.1%,62.8% 98.2%,62.8% 99.7%,28.4% 98.2%,30.2% 95.1%,34.3% 91.9%,43.7% 88.8%,22.9% 85.7%,15.2% 82.6%,13.8% 79.4%,15.2% 76.3%,24.0% 73.2%,19.6% 70.1%,21.7% 66.9%,24.3% 63.8%,24.3% 60.7%,24.9% 57.6%,27.6% 54.4%,27.0% 51.3%,28.2% 48.2%,28.4% 45.1%,26.1% 41.9%,25.5% 38.8%,24.6% 35.7%,24.3% 32.6%,24.3% 29.4%,19.1% 26.3%,17.0% 23.2%,17.3% 20.1%,19.4% 16.9%,20.8% 13.8%,23.2% 10.7%,25.8% 7.6%,27.3% 4.4%,26.4% 1.3%)",
    "yu": "polygon(27.6% 0.0%,85.3% 1.3%,78.0% 3.9%,75.1% 6.5%,73.6% 9.1%,78.9% 11.7%,78.9% 14.6%,78.9% 17.2%,84.2% 19.8%,85.3% 22.4%,89.4% 25.0%,91.8% 27.9%,90.0% 30.5%,85.3% 33.1%,82.1% 35.7%,82.1% 38.5%,79.2% 41.1%,80.1% 43.8%,82.1% 46.4%,83.0% 49.0%,79.8% 51.8%,65.1% 54.4%,65.4% 57.0%,65.7% 59.6%,66.3% 62.5%,66.6% 65.1%,67.2% 67.7%,67.7% 70.3%,79.5% 72.9%,82.4% 75.8%,83.0% 78.4%,83.0% 81.0%,78.0% 83.6%,78.0% 86.2%,20.5% 83.6%,17.6% 81.0%,17.6% 78.4%,18.2% 75.8%,20.2% 72.9%,23.8% 70.3%,26.4% 67.7%,32.3% 65.1%,32.8% 62.5%,33.4% 59.6%,34.6% 57.0%,35.2% 54.4%,36.1% 51.8%,34.3% 49.0%,27.9% 46.4%,25.5% 43.8%,25.5% 41.1%,33.4% 38.5%,25.2% 35.7%,23.8% 33.1%,23.5% 30.5%,22.9% 27.9%,23.5% 25.0%,22.9% 22.4%,24.0% 19.8%,25.2% 17.2%,25.5% 14.6%,33.1% 11.7%,29.6% 9.1%,28.7% 6.5%,27.9% 3.9%,27.6% 1.3%)",
    "yui": "polygon(26.7% 0.0%,87.4% 1.3%,87.1% 3.9%,85.6% 6.5%,85.6% 9.1%,85.0% 12.0%,82.7% 14.6%,80.4% 17.2%,77.4% 19.8%,74.2% 22.7%,75.7% 25.3%,75.4% 27.9%,74.5% 30.5%,72.1% 33.3%,71.6% 35.9%,67.7% 38.5%,66.0% 41.1%,66.3% 44.0%,66.9% 46.6%,66.6% 49.2%,63.9% 51.8%,63.9% 54.7%,63.0% 57.3%,62.8% 59.9%,62.8% 62.5%,62.8% 65.4%,62.8% 68.0%,62.2% 70.6%,75.7% 73.2%,79.2% 76.0%,79.5% 78.6%,78.9% 81.2%,73.6% 83.9%,73.6% 86.5%,21.7% 83.9%,17.3% 81.2%,16.7% 78.6%,17.3% 76.0%,20.5% 73.2%,23.5% 70.6%,29.0% 68.0%,30.5% 65.4%,33.1% 62.5%,35.5% 59.9%,37.0% 57.3%,27.6% 54.7%,26.1% 51.8%,24.9% 49.2%,25.2% 46.6%,25.5% 44.0%,27.3% 41.1%,28.7% 38.5%,28.4% 35.9%,27.0% 33.3%,27.0% 30.5%,29.0% 27.9%,27.0% 25.3%,27.3% 22.7%,25.8% 19.8%,26.1% 17.2%,25.5% 14.6%,25.8% 12.0%,26.4% 9.1%,28.2% 6.5%,28.2% 3.9%,26.7% 1.3%)",
    "ren": "polygon(24.9% 0.0%,71.8% 1.3%,68.9% 3.9%,69.8% 6.5%,70.1% 9.1%,71.3% 11.7%,70.7% 14.6%,75.7% 17.2%,78.6% 19.8%,82.7% 22.4%,82.7% 25.0%,84.8% 27.9%,84.2% 30.5%,82.4% 33.1%,83.0% 35.7%,83.0% 38.5%,80.6% 41.1%,79.5% 43.8%,77.7% 46.4%,75.1% 49.0%,72.1% 51.8%,61.6% 54.4%,61.6% 57.0%,62.2% 59.6%,61.9% 62.5%,62.2% 65.1%,62.8% 67.7%,63.3% 70.3%,76.0% 72.9%,78.3% 75.8%,78.9% 78.4%,78.6% 81.0%,75.1% 83.6%,75.1% 86.2%,16.4% 83.6%,13.2% 81.0%,12.9% 78.4%,14.1% 75.8%,16.4% 72.9%,25.2% 70.3%,26.1% 67.7%,27.0% 65.1%,27.6% 62.5%,28.4% 59.6%,28.4% 57.0%,27.9% 54.4%,25.5% 51.8%,27.0% 49.0%,17.3% 46.4%,15.2% 43.8%,15.0% 41.1%,14.4% 38.5%,12.0% 35.7%,11.4% 33.1%,12.6% 30.5%,17.6% 27.9%,23.8% 25.0%,24.3% 22.4%,26.1% 19.8%,34.3% 17.2%,26.7% 14.6%,26.4% 11.7%,27.0% 9.1%,28.2% 6.5%,26.1% 3.9%,24.9% 1.3%)",
}

# 部署間・休憩スペースでの、控えめな頻度で挟まる交流デモ(対面報告では
# ない、社内コミュニケーションのデモ表示)。"mover"が自席から"location"へ
# 歩いて行き、"speaker"のセリフを表示してから自席へ戻る。locationは
# 部署キー(AI_OFFICE_FLOOR_POSITIONS)・拡張担当キー
# (AI_OFFICE_EXTENDED_STAFF)・"lounge"のいずれか。
# MISSION 076: 美咲と海の交流(旧misaki_umi_pinterest)・伊織と蒼の交流
# (旧iori_sou_desk)・悠の巡回(旧yu_progress_check)・結の情報源モニター
# 確認(旧yui_monitor_check)は、対面報告ルート(AI_OFFICE_REPORT_ROUTES)
# として役割ごとの受け手に報告する形へ統合したため、ここでは対面報告に
# 該当しない彩(休憩スペース)・凛(資料室↔note)の2件のみを残す。
AI_OFFICE_INTERACTION_SCENES = [
    {
        "key": "aya_lounge",
        "mover": "aya",
        "location": "lounge",
        "speaker": "aya",
        "line": "ひと息ついたら続けます",
        "feed_text": "彩が休憩スペースで社員に声をかけました",
    },
    {
        "key": "rin_note_visit",
        "mover": "rin",
        "location": "note",
        "speaker": "rin",
        "line": "資料を確認して戻ります",
        "feed_text": "凛が資料室とnote編集席を行き来しました",
    },
    # MISSION 089: 候補管理チームの引き継ぎ(紬→凪)をデモの交流として
    # 追加する。「今日・今週・保留」への分類後、商品確認を依頼する短い
    # やり取りで、候補管理の役割の流れが伝わるようにする。
    {
        "key": "tsumugi_nagi_handoff",
        "mover": "tsumugi",
        "location": "nagi",
        "speaker": "tsumugi",
        "line": "今日の候補を確認してもらえますか",
        "feed_text": "紬が凪に、今日の候補の確認を依頼しました",
    },
]


def _ai_office_all_positions():
  """部署・拡張担当・休憩スペース等の座標を、1つの辞書にまとめて返す。

  フロアマップ画像は正方形(1254×1254)なので、left/topの百分率は縦横で
  同じ縮尺になる。
  """
  positions = dict(AI_OFFICE_FLOOR_POSITIONS)
  for staff in AI_OFFICE_EXTENDED_STAFF:
    positions[staff["key"]] = staff["pos"]
  positions["lounge"] = AI_OFFICE_LOUNGE_POSITION
  return positions


def _ai_office_sprite_position(sprite):
  """スプライトシート上の(row,col)から、background-positionの値を作る。"""
  col_pct = (sprite["col"] / (AI_OFFICE_SPRITE_COLS - 1)) * 100
  row_pct = (sprite["row"] / (AI_OFFICE_SPRITE_ROWS - 1)) * 100
  return f'{col_pct:.2f}% {row_pct:.2f}%'


def _render_ai_office_scene():
  """AIオフィス(/ai-office)画面のHTMLを組み立てる(デモ表示のみ)。

  純粋な表示用マークアップのみで構成し、JS・フォーム・localStorageへの
  保存は一切使わない。DB・API・楽天ROOM・楽天アフィリエイト・note・
  Pinterest・Threadsへの通信・アクセス・ログイン・投稿・送信・削除は
  一切行わない。投稿・公開・送信・ログイン・削除を実行するボタンは置かない。
  """
  department_by_key = {d["key"]: d for d in AI_OFFICE_DEPARTMENTS}
  all_positions = _ai_office_all_positions()

  def _sprite_avatar_style_attr(person):
    return f'background-position:{_ai_office_sprite_position(person["sprite"])}'

  # MISSION 090: 社員の状態(稼働中/待機中)は、作業台帳(work_items)に基づく
  # 実績表示へ切り替える。サーバー側はDBの中身を知り得ないため、初期表示は
  # 「確認中…」のニュートラルな状態にしておき、JS側のapplyStaffRealState()
  # が取得直後に実データへ書き換える(架空の稼働中/待機中を決め打ちしない)。
  def _status_strip_chip(dept):
    status_key = "waiting"
    return (
        f'<li class="ai-office-strip-chip" data-department="{dept["key"]}">'
        '<span class="ai-office-char-avatar ai-office-sprite-avatar '
        f'ai-office-char-avatar-{status_key}" role="img" '
        f'aria-label="{dept["staff_name"]}" '
        f'style="{_sprite_avatar_style_attr(dept)}"></span>'
        '<span class="ai-office-strip-info">'
        f'<b>{dept["desk_label"]}（{dept["staff_name"]}）</b>'
        f'<span class="ai-office-status-badge ai-office-status-{status_key}" '
        f'data-suffix="確認中">確認中…</span>'
        '</span>'
        '</li>'
    )

  status_strip = "".join(_status_strip_chip(d) for d in AI_OFFICE_DEPARTMENTS)

  def _desk_card(dept):
    status_key = "waiting"
    return (
        f'<div class="ai-office-desk" data-department="{dept["key"]}">'
        '<div class="ai-office-desk-symbol ai-office-sprite-avatar" '
        f'role="img" aria-label="{dept["staff_name"]}" '
        f'style="{_sprite_avatar_style_attr(dept)}"></div>'
        f'<h3>{dept["desk_label"]}</h3>'
        f'<p class="ai-office-desk-role">{dept["role_label"]}（{dept["staff_name"]}）</p>'
        f'<p class="ai-office-desk-summary">{dept["role_summary"]}</p>'
        f'<p class="ai-office-desk-scope">{AI_OFFICE_SCOPE_STATEMENT}</p>'
        f'<span class="ai-office-status-badge ai-office-status-{status_key}" '
        f'data-suffix="確認中">確認中…</span>'
        '</div>'
    )

  def _extended_desk_card(staff):
    status_key = "waiting"
    return (
        f'<div class="ai-office-desk" data-department="{staff["key"]}">'
        '<div class="ai-office-desk-symbol ai-office-sprite-avatar" '
        f'role="img" aria-label="{staff["name"]}" '
        f'style="{_sprite_avatar_style_attr(staff)}"></div>'
        f'<h3>{staff["name"]}</h3>'
        f'<p class="ai-office-desk-role">{staff["role_label"]}（{staff["zone_label"]}）</p>'
        f'<p class="ai-office-desk-summary">{staff["role_summary"]}</p>'
        f'<p class="ai-office-desk-scope">{AI_OFFICE_SCOPE_STATEMENT}</p>'
        f'<span class="ai-office-status-badge ai-office-status-{status_key}" '
        f'data-suffix="確認中">確認中…</span>'
        '</div>'
    )

  desk_cards = "".join(_desk_card(d) for d in AI_OFFICE_DEPARTMENTS) + "".join(
      _extended_desk_card(s) for s in AI_OFFICE_EXTENDED_STAFF
  )

  # MISSION 075: 全12人が常に少しずつ動いて見えるよう、idle_typeごとの
  # アイドルアニメーションを付与する。全員が同じ周期で動くと不自然なので、
  # 名簿内の通し番号(idle_index)からanimation-delay/durationを少しずつ
  # ずらす(delayは負の値にして、初回表示時点からすでに周期の途中にいる
  # ように見せる)。
  idle_order = [d["key"] for d in AI_OFFICE_DEPARTMENTS] + [
      s["key"] for s in AI_OFFICE_EXTENDED_STAFF
  ]
  idle_index_by_key = {key: i for i, key in enumerate(idle_order)}
  idle_type_by_key = {d["key"]: d["idle_type"] for d in AI_OFFICE_DEPARTMENTS}
  idle_type_by_key.update({s["key"]: s["idle_type"] for s in AI_OFFICE_EXTENDED_STAFF})

  def _idle_style(key):
    idx = idle_index_by_key[key]
    delay = -(idx * 0.37 + 0.2)
    duration = 3.4 + (idx % 5) * 0.3
    return f'animation-delay:{delay:.2f}s;animation-duration:{duration:.2f}s'

  def _floor_token(key, name, sprite, pos, status_key, department_key=None):
    # MISSION 074: フロアマップ上の社員は、黒いアイコン枠(ai-office-char-
    # avatarの円形カード)を使わず、専用のai-office-floormap-token(+状態別
    # の発光をfilter:drop-shadowで表現するai-office-floormap-token-*)だけで
    # 描画する。円形カード・状態バッジ調のスタイルは、下の「社員名簿」
    # (ai-office-char-avatar)側にだけ残す。
    # MISSION 075: さらにai-office-idle-{idle_type}を常時付与し、待機中でも
    # 常に小さく動いているように見せる(is-working/is-moving付与時は、後の
    # CSSソース順で上書きされるため、動作・移動時はそちらが優先される)。
    # MISSION 076: 対面報告時に「向き」を変えられるよう、スプライト本体を
    # 内側のai-office-floormap-sprite(向き反転はここだけに適用)へ分離した。
    # 外側のai-office-floormap-token側は位置・常時アニメーションの担当を
    # 維持し、向きの反転が既存のアイドル・稼働中アニメーションと競合しない
    # ようにする。対面報告中・応答中・移動中・帰席中は、名前札内の
    # ai-office-nameplate-phaseへ短いラベルを表示する(JS側で更新)。
    # MISSION 079: スプライトのコマに描き込まれた暗いビネット背景を隠す
    # ため、単純な楕円マスクではなく、人物(頭・肩・腕・持ち物・足元の光る
    # リングまで)の輪郭に沿ったclip-path(AI_OFFICE_SPRITE_CLIP_PATHS、
    # 人物ごとに個別)を使う。scaleX(-1)による向き反転はclip-path適用後の
    # 座標系にもそのまま効くため、反転時も輪郭がずれない。
    dept_attr = f' data-department="{department_key}"' if department_key else ""
    idle_type = idle_type_by_key[key]
    idle_class = AI_OFFICE_IDLE_ANIMATION_BY_TYPE[idle_type]
    clip_path = _ai_office_clip_path_for(key)
    return (
        f'<span class="ai-office-floormap-token {idle_class} '
        f'ai-office-floormap-token-{status_key}" '
        f'id="ai-office-token-{key}" data-person="{key}" data-idle="{idle_type}"'
        f'{dept_attr} '
        f'role="img" aria-label="{name}" '
        f'style="left:{pos["left"]}%;top:{pos["top"]}%;{_idle_style(key)}">'
        f'<span class="ai-office-floormap-sprite" id="ai-office-sprite-{key}" '
        f'style="background-position:{_ai_office_sprite_position(sprite)};'
        f'clip-path:{clip_path};-webkit-clip-path:{clip_path}"></span>'
        '<span class="ai-office-footstep"></span>'
        # MISSION 077: 対面報告中、報告者・受け手の足元に同じ色の発光リングを
        # 出す(is-report-mover/is-report-receiverはJS側で付与)。
        '<span class="ai-office-report-ring" aria-hidden="true"></span>'
        f'<span class="ai-office-nameplate" id="ai-office-nameplate-{key}">'
        f'<i class="ai-office-nameplate-dot ai-office-nameplate-dot-{status_key}" '
        f'id="ai-office-nameplate-dot-{key}"></i>{name}'
        f'<span class="ai-office-nameplate-phase" '
        f'id="ai-office-nameplate-phase-{key}"></span>'
        f'<span class="sr-only" id="ai-office-nameplate-status-{key}"> '
        '確認中…</span>'
        '</span>'
        '</span>'
    )

  # MISSION 090: フロアトークンの初期状態も、desk_card等と同じくニュートラル
  # な「確認中」にしておき、作業台帳のデータ取得後にJS側で実データへ切り替え
  # る(demo_statusは、サーバー側で架空の稼働中/待機中を決め打ちしないよう、
  # ここでは使わない)。
  floor_tokens = "".join(
      _floor_token(
          d["key"], d["staff_name"], d["sprite"], all_positions[d["key"]],
          "waiting", department_key=d["key"],
      )
      for d in AI_OFFICE_DEPARTMENTS
  ) + "".join(
      _floor_token(s["key"], s["name"], s["sprite"], all_positions[s["key"]], "waiting")
      for s in AI_OFFICE_EXTENDED_STAFF
  )

  # MISSION 075: モニターの控えめな明滅演出を、4部署に加えて技術席(蒼)・
  # 分析ラボ担当(結)にも拡張する。
  monitor_glow_keys = ["room", "note", "pinterest", "analytics", "sou", "yui"]
  monitor_glows = "".join(
      f'<span class="ai-office-monitor-glow ai-office-monitor-glow-ambient" '
      f'id="ai-office-monitor-{key}" '
      f'style="left:{all_positions[key]["left"]}%;'
      f'top:{all_positions[key]["top"]}%;'
      f'animation-delay:-{(i * 0.6):.2f}s"></span>'
      for i, key in enumerate(monitor_glow_keys)
  )

  cmd_pos = all_positions["operations_lead"]
  # MISSION 076: 報告者(mover)の吹き出しと、報告を受ける本人(receiver)の
  # 返答の吹き出しを別要素にし、色・矢印を変えて対面会話を分かりやすくする
  # (CSS側でai-office-floormap-bubble-receiverが配色を上書きする)。
  # 部署巡回(旧Track A/報告ルート)と部署間交流(Track B)を同時並行で動かす
  # ため、mover用の吹き出しも2つ用意し、互いの表示を上書きしないようにする。
  floor_bubble = (
      '<div class="ai-office-floormap-bubble" id="ai-office-floormap-bubble" '
      f'style="left:{cmd_pos["left"]}%;top:{cmd_pos["top"]}%"></div>'
  )
  floor_bubble_receiver = (
      '<div class="ai-office-floormap-bubble ai-office-floormap-bubble-receiver" '
      f'id="ai-office-floormap-bubble-receiver" '
      f'style="left:{cmd_pos["left"]}%;top:{cmd_pos["top"]}%"></div>'
  )
  floor_bubble_b = (
      '<div class="ai-office-floormap-bubble" id="ai-office-floormap-bubble-b" '
      f'style="left:{cmd_pos["left"]}%;top:{cmd_pos["top"]}%"></div>'
  )

  lounge_pos = AI_OFFICE_LOUNGE_POSITION
  # MISSION 075: 休憩スペースに、常時ゆっくり立ち上るコーヒーの湯気(CSSのみ)
  # を追加する。新規画像・ライブラリは使わない。
  lounge_decor = (
      '<span class="ai-office-lounge-decor" '
      f'style="left:{lounge_pos["left"]}%;top:{lounge_pos["top"]}%" '
      'aria-hidden="true">'
      '<span class="ai-office-lounge-cup"></span>'
      '<span class="ai-office-lounge-steam ai-office-lounge-steam-1"></span>'
      '<span class="ai-office-lounge-steam ai-office-lounge-steam-2"></span>'
      '</span>'
  )

  # MISSION 075: 指令デスク周辺の短い通知光(報告到着時に点灯)。
  command_pulse = (
      '<span class="ai-office-command-pulse" id="ai-office-command-pulse" '
      f'style="left:{cmd_pos["left"]}%;top:{cmd_pos["top"]}%" '
      'aria-hidden="true"></span>'
  )

  # MISSION 075: 指令デスクの「本日の進行状況」ミニボード。フロアマップ
  # 左上に固定表示し、稼働中・移動中・相談中の人数をデモとして表示する
  # (「今のオフィス」の短いステータス行を兼ねる)。座標依存ではないため、
  # モバイルでもキャラクター・吹き出し・名前札と重ならない。
  progress_board = (
      '<div class="ai-office-progress-board" id="ai-office-progress-board" '
      'aria-live="polite">'
      '<b>本日の進行状況（指令デスク・デモ）</b>'
      '<span id="ai-office-progress-board-line">現在：確認中です（デモ）</span>'
      '</div>'
  )

  # MISSION 077: 対面報告中の2人を、細い点線+矢印で結ぶ(報告の方向が
  # 分かるように、報告者→受け手の向きで矢印を出す)。JS側で
  # 位置・長さ・角度を計算して表示する(初期状態は非表示)。
  report_connector = (
      '<span class="ai-office-report-connector" id="ai-office-report-connector" '
      'aria-hidden="true"></span>'
  )

  task_items = "".join(
      '<li>'
      f'<span><span class="ai-office-task-dept">'
      f'{department_by_key[t["department"]]["desk_label"]}</span>{t["text"]}</span>'
      '<span class="ai-office-demo-tag">デモ</span>'
      '</li>'
      for t in AI_OFFICE_TODAY_TASKS
  )

  work_items = "".join(
      '<li>'
      f'<span><span class="ai-office-task-dept">'
      f'{department_by_key[w["department"]]["desk_label"]}</span>{w["item"]}</span>'
      f'<span class="ai-office-status-badge ai-office-status-{w["status"]}">'
      f'{AI_OFFICE_STATUS_LABELS[w["status"]]}</span>'
      '</li>'
      for w in AI_OFFICE_RUNNING_WORK
  )

  chat_bubbles = "".join(
      f'<p class="{"you" if m["speaker"] == "you" else "boss"}">{m["text"]}</p>'
      for m in AI_OFFICE_CHAT_DEMO_MESSAGES
  )

  freshness_cards = "".join(
      f'<div class="ai-office-freshness-card"><b>{ch}</b>'
      '<span class="ai-office-freshness-status">未接続・参考表示</span></div>'
      for ch in AI_OFFICE_SOURCE_CHANNELS
  )

  deliverable_items = "".join(
      '<li>'
      f'<span><b>{d["label"]}</b>：{d["description"]}'
      + (f'<a href="{d["href"]}">→ 開く</a>' if d["href"] else "")
      + '</span>'
      '</li>'
      for d in AI_OFFICE_DELIVERABLES
  )

  activity_items = "".join(f"<li>{a}</li>" for a in AI_OFFICE_ACTIVITY_FEED)

  staff_names = {d["key"]: d["staff_name"] for d in AI_OFFICE_DEPARTMENTS}
  staff_names.update({s["key"]: s["name"] for s in AI_OFFICE_EXTENDED_STAFF})

  js_data = json.dumps(
      {
          "positions": all_positions,
          "reportRoutes": AI_OFFICE_REPORT_ROUTES,
          "reportRoleLabels": AI_OFFICE_REPORT_ROLE_LABELS,
          "shortNames": AI_OFFICE_SHORT_NAMES,
          "statusLabels": AI_OFFICE_STATUS_LABELS,
          "staffNames": staff_names,
          "interactions": AI_OFFICE_INTERACTION_SCENES,
          "visitorSlots": AI_OFFICE_VISITOR_SLOTS,
          "maxFeedItems": AI_OFFICE_ACTIVITY_FEED_MAX_ITEMS,
          # MISSION 080: 運用司令室の「本日の運用記録」(localStorage)を
          # 読み取り、実績があれば対応する社員の対面報告として表示する。
          "dailyRecordStorageKey": AI_OFFICE_DAILY_RECORD_STORAGE_KEY,
          "dailyRecordTypeOwners": AI_OFFICE_DAILY_RECORD_TYPE_OWNERS,
          "dailyRecordMediaOwners": AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS,
          "dailyRecordFallbackOwner": AI_OFFICE_DAILY_RECORD_FALLBACK_OWNER,
          "dailyRecordTypeAck": AI_OFFICE_DAILY_RECORD_TYPE_ACK,
          # MISSION 084: 「今日の実行キュー」専用のデータ。
          "queueMediaOwners": AI_OFFICE_QUEUE_MEDIA_OWNERS,
          "queueStatusByType": AI_OFFICE_QUEUE_STATUS_BY_TYPE,
          "queueNextActionByType": AI_OFFICE_QUEUE_NEXT_ACTION_BY_TYPE,
          "queueDefaultStatus": AI_OFFICE_QUEUE_DEFAULT_STATUS,
          "queueDefaultNextAction": AI_OFFICE_QUEUE_DEFAULT_NEXT_ACTION,
          # MISSION 085: 「直近の実績」専用のデータ。
          "recentLabelByType": AI_OFFICE_RECENT_LABEL_BY_TYPE,
          "recentMaxItems": AI_OFFICE_RECENT_MAX_ITEMS,
          # MISSION 086: 「柴犬社長からの本日の指示」専用のデータ。
          "directiveRules": AI_OFFICE_DIRECTIVE_RULES,
          # MISSION 090: 作業台帳(work_items)に基づく「本日の指示」「今日の
          # 実行キュー」「社員の状態」専用のデータ。
          "allStaffKeys": AI_OFFICE_ALL_STAFF_KEYS,
          "workStatusLabels": WORK_ITEM_STATUS_LABELS,
          # MISSION 091: 分析ラボ(葵)の実データ化専用のデータ。
          "metricFieldLabels": dashboard_db.REVENUE_METRIC_FIELDS,
      },
      ensure_ascii=False,
  )

  return (
      '<section class="ai-office" aria-label="AIオフィス">'
      # MISSION 086: 最初に読むべき「柴犬社長からの本日の指示」カード。
      # 常に1件・ボタン1つだけを表示する。実際の値はJS側で、運用司令室の
      # localStorageを読み取り専用で参照して決める(サーバー側は中身を
      # 知り得ないため、初期表示は読み込み中の文言にしておく)。
      '<div class="ai-office-directive-card" id="ai-office-directive-card">'
      '<div class="ai-office-directive-label">🐕 柴犬社長からの本日の指示</div>'
      '<p class="ai-office-directive-task" id="ai-office-directive-task">'
      '読み込み中…</p>'
      '<p class="ai-office-directive-reason" id="ai-office-directive-reason"></p>'
      '<a class="ai-office-directive-button" id="ai-office-directive-button" '
      'href="/command-center">運用司令室を開く</a>'
      '</div>'
      '<div class="ai-office-demo-banner">実績表示と参考表示が混在しています'
      '<span>「本日の指示」「今日の実行キュー」「社員の状態（稼働中/待機中）」'
      'は、運用司令室の作業台帳（このMac上のSQLite DB）に基づく実績表示です。'
      'それ以外のチャット・タスク一覧・活動フィード・フロアマップ上の'
      '動き/会話/報告アニメーションは、あらかじめ用意した参考表示（デモ）'
      'であり、AI社員が実際に自動稼働しているものではありません。'
      '</span></div>'
      # MISSION 080: 「デモ表示」か「実績表示」かを画面上で明確に判別できる
      # ようにするバッジ。実際の値はJS側で、運用司令室のlocalStorageに本日
      # 付の運用記録があるかどうかを見て書き換える(サーバー側はlocalStorage
      # の中身を知り得ないため、初期表示は読み込み中の文言にしておく)。
      '<div class="ai-office-record-mode-badge" id="ai-office-record-mode-badge">'
      '読み込み中…（デモ表示）</div>'
      # MISSION 091: 分析ラボ(葵)からの報告。当日に実績スナップショットが
      # 記録されているかどうかだけをもとに、DBに保存済みの事実を短く
      # 表示する(推測・比較・架空の分析は行わない)。サーバー側はDBの
      # 中身を知り得ないため、初期表示は確認中の文言にしておく。
      '<div class="ai-office-analytics-report" id="ai-office-analytics-report">'
      '<b>分析ラボ（葵）からの報告</b>'
      '<p id="ai-office-analytics-report-text">確認中…</p>'
      '</div>'
      '<div class="ai-office-role-diff">'
      '<p><b>運用司令室</b>（/command-center）は、数字の確認・判断・記録を'
      '行う画面です。<b>AIオフィス</b>（このページ）は、役割・進行状況・'
      '活動を見える化する画面であり、役割は重複していません。</p>'
      '<p>このページには、投稿・公開・送信・ログイン・削除を行うボタンは'
      '一切ありません。すべての実行判断は利用者本人が行います。</p>'
      '</div>'

      '<div class="ai-office-floormap" aria-label="オフィスフロアマップ（デモ表示）">'
      # MISSION 077: フロアマップ最上部に、対面報告中の報告者・受け手・
      # 役割が一目で分かる大きな進行バナーを表示する。対面報告が始まる
      # 前や、停止後も直前の内容がそのまま読み取れるよう、JS側では
      # 「消す」のではなく次の対面報告が始まるまで内容を保持する。
      '<div class="ai-office-report-banner" id="ai-office-report-banner" '
      'aria-live="polite">対面報告中の社員はまだいません（デモ）</div>'
      '<p class="ai-office-floormap-caption"><b>オフィスフロアマップ（実績表示'
      '＋参考表示）</b><br>'
      'AIオフィスの全体像を1枚のイラストの上に、立体的なゲームキャラクター'
      '風の社員15人本人を重ねて表示しています。稼働中はシアン、待機中は'
      '控えめな青で名前札の色を示しますが、この色分けは作業台帳（DB）に'
      '基づく実績表示です。一方、キャラクターの移動・会話・報告アニメー'
      'ション自体は、実際にAIが自動稼働しているものではなく、演出用の'
      '参考表示（デモ）です。</p>'
      '<div class="ai-office-floormap-image-wrap">'
      '<div class="ai-office-floormap-stage">'
      f'<img class="ai-office-floormap-image" '
      f'src="/static/{AI_OFFICE_FLOOR_MAP_EMPTY_IMAGE_RELATIVE_PATH}" '
      'width="1254" height="1254" loading="lazy" '
      'alt="AIオフィスの間取りを表すピクセルアート風のイラスト（デモ表示）。'
      '指令デスク・ROOM運用席・note編集席・Pinterest企画席・分析ラボなどの'
      '区画のみが描かれた空のオフィスで、ロボットや人物は描かれていません。'
      '社員キャラクターは、この画像の上に別途重ねて表示しています。実際の'
      'オフィスの写真や、AIが実際に稼働している様子を撮影したものでは'
      'ありません。">'
      f'<div class="ai-office-floormap-overlay" id="ai-office-floormap-overlay">'
      f'{progress_board}{monitor_glows}{lounge_decor}{command_pulse}'
      f'{report_connector}'
      f'{floor_tokens}{floor_bubble}{floor_bubble_receiver}{floor_bubble_b}</div>'
      '</div>'
      '<p class="ai-office-floormap-hint">各部屋を選択すると下の詳細を確認'
      'できます。（今回はクリック操作・状態変更は実装しておらず、詳細は'
      'この下の「社員の稼働状況」でご確認いただけます。）</p>'
      # MISSION 077: 対面報告中の2人の会話を「報告者 → 受け手「セリフ」」の
      # 形式で並べる会話パネル。フロアマップの真下(固定位置)に置くことで、
      # モバイルでもキャラクターの座標に関係なく画面内に収まる。
      '<div class="ai-office-report-panel" id="ai-office-report-panel" '
      'aria-live="polite">'
      '<p class="ai-office-report-panel-line" '
      'id="ai-office-report-panel-mover">対面報告が始まると、ここに会話が'
      '表示されます（デモ）</p>'
      '<p class="ai-office-report-panel-line" '
      'id="ai-office-report-panel-receiver"></p>'
      '</div>'
      # MISSION 077: 全員が社長へ直接行くわけではないことを示す、短い
      # 案内文。
      '<p class="ai-office-report-legend">通常報告 → 悠・彩・伊織・蓮'
      ' ／ 最終報告 → 柴犬社長</p>'
      '</div>'
      '<div class="ai-office-floormap-controls">'
      '<button type="button" class="ai-office-anim-toggle" '
      'id="ai-office-anim-toggle">アニメーションを停止</button>'
      '</div>'
      '<div class="ai-office-floormap-speech" id="ai-office-floormap-speech" '
      'aria-live="polite"><b>柴犬社長</b>「オフィスの様子を確認しています」'
      '（デモ会話）</div>'
      '<p class="ai-office-floormap-speech-note">会話はすべてデモ用のデータ'
      'であり、実際のAI稼働ログではありません。</p>'
      f'<ul class="ai-office-floormap-status-strip">{status_strip}</ul>'
      '</div>'

      # MISSION 084: 運用司令室の本日の運用記録を、読み取り専用で
      # 「次に何をすればよいか」の実行キューとして表示する。記録がない
      # 場合は、実在しない作業を作らず、その旨を明記した空メッセージの
      # ままにする(JS側でrecords.length===0のときは書き換えない)。
      '<div class="ai-office-section">'
      '<h2>今日の実行キュー</h2>'
      '<p class="ai-office-floormap-hint">運用司令室（'
      '<a href="/command-center">/command-center</a>'
      '）に入力した本日の運用記録を、次に行うべきことの一覧として表示'
      'します。ここから外部サービスへの投稿・送信・ログイン・承認は'
      '一切行いません。</p>'
      '<ul class="ai-office-queue-list" id="ai-office-queue-list">'
      '<li class="ai-office-queue-empty" id="ai-office-queue-empty">'
      f'{AI_OFFICE_QUEUE_EMPTY_MESSAGE}</li>'
      '</ul>'
      '</div>'

      # MISSION 085: 当日より前の運用記録を、新しい順で最大5件、読み取り
      # 専用で表示する。今日の実行キューとは対象期間を分け、当日分は
      # 混ぜない(JS側でtodayDateStrより前のdateだけを対象にする)。記録が
      # ない場合は、実在しない実績を作らず、空メッセージのままにする。
      '<div class="ai-office-section">'
      '<h2>直近の実績</h2>'
      '<p class="ai-office-floormap-hint">運用司令室に記録した、本日より'
      '前の運用記録を新しい順で最大5件表示します。今日の実行キューには'
      '含めません。ここから外部サービスへの投稿・送信・ログイン・承認は'
      '一切行いません。</p>'
      '<ul class="ai-office-recent-list" id="ai-office-recent-list">'
      '<li class="ai-office-queue-empty" id="ai-office-recent-empty">'
      f'{AI_OFFICE_RECENT_EMPTY_MESSAGE}</li>'
      '</ul>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>社員名簿（15人・状態一覧）</h2>'
      '<p class="ai-office-floormap-hint">柴犬社長を含む15人の役割・配置・'
      '状態をまとめた一覧です。状態（稼働中/待機中）は作業台帳（DB）に基づく'
      '実績表示、役割・配置の説明文はご案内用の参考表示です。</p>'
      f'<div class="ai-office-floor"><div class="ai-office-floor-grid">{desk_cards}</div></div>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>今日のタスク（参考表示）</h2>'
      f'<ul class="ai-office-task-list">{task_items}</ul>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>動いている仕事と結果（参考表示）</h2>'
      f'<ul class="ai-office-work-list">{work_items}</ul>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>AIとのチャット窓口（参考表示）</h2>'
      f'<div class="ai-office-chat-demo"><div class="log">{chat_bubbles}</div>'
      '<p class="ai-office-chat-note">この窓口は現在、参考表示の会話例のみで、'
      '次の段階で接続を予定しています。外部AI APIへの送信や自動応答は'
      '行っていません。</p></div>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>情報源の鮮度モニター（参考表示）</h2>'
      f'<div class="ai-office-freshness-grid">{freshness_cards}</div>'
      '<p class="ai-office-freshness-note">実際の取得日時は表示していません'
      '（未実装）。すべて「未接続・参考表示」の表示です。</p>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>成果物一覧</h2>'
      f'<ul class="ai-office-deliverables-list">{deliverable_items}</ul>'
      '</div>'

      '<div class="ai-office-section">'
      '<h2>活動フィード（参考表示）</h2>'
      f'<ul class="ai-office-activity-feed" id="ai-office-activity-feed-list">'
      f'{activity_items}</ul>'
      '<p class="ai-office-chat-note">これは演出用の参考表示であり、実際の'
      'AI作業ログではありません。</p>'
      '</div>'

      '<p class="fp-footnote">この画面はlocalhost限定で表示される社内検討用の'
      'デモ画面です。楽天ROOM・楽天アフィリエイト・note・Pinterest・Threads'
      'への投稿・送信・ログイン・削除は行われません。</p>'
      '<script>'
      '(function(){'
      f'var DATA={js_data};'
      'var POSITIONS=DATA.positions,REPORT_ROUTES=DATA.reportRoutes,'
      'REPORT_ROLES=DATA.reportRoleLabels,SHORT_NAMES=DATA.shortNames,'
      'STATUS_LABELS=DATA.statusLabels,'
      'STAFF_NAMES=DATA.staffNames,'
      'INTERACTIONS=DATA.interactions,MAX_FEED=DATA.maxFeedItems,'
      'VISITOR_SLOTS=DATA.visitorSlots,'
      'RECORD_KEY=DATA.dailyRecordStorageKey,'
      'RECORD_TYPE_OWNERS=DATA.dailyRecordTypeOwners,'
      'RECORD_MEDIA_OWNERS=DATA.dailyRecordMediaOwners,'
      'RECORD_FALLBACK_OWNER=DATA.dailyRecordFallbackOwner,'
      'RECORD_TYPE_ACK=DATA.dailyRecordTypeAck,'
      'QUEUE_MEDIA_OWNERS=DATA.queueMediaOwners,'
      'QUEUE_STATUS_BY_TYPE=DATA.queueStatusByType,'
      'QUEUE_NEXT_ACTION_BY_TYPE=DATA.queueNextActionByType,'
      'QUEUE_DEFAULT_STATUS=DATA.queueDefaultStatus,'
      'QUEUE_DEFAULT_NEXT_ACTION=DATA.queueDefaultNextAction,'
      'RECENT_LABEL_BY_TYPE=DATA.recentLabelByType,'
      'RECENT_MAX_ITEMS=DATA.recentMaxItems,'
      'DIRECTIVE_RULES=DATA.directiveRules,'
      'ALL_STAFF_KEYS=DATA.allStaffKeys,'
      'WORK_STATUS_LABELS=DATA.workStatusLabels,'
      'METRIC_FIELD_LABELS=DATA.metricFieldLabels;'
      'function shortName(key){return SHORT_NAMES[key]||STAFF_NAMES[key];}'
      # MISSION 080: 運用司令室の「本日の運用記録」(localStorage)を読み、
      # 今日の日付の記録だけを、対応する社員の対面報告に変換する。
      # AIオフィス自体はこのキーへ書き込まない(読み取り専用)。
      'var recordModeBadgeEl=document.querySelector("#ai-office-record-mode-badge");'
      'function todayDateStr(){'
      'var d=new Date();'
      'function pad(n){return n<10?"0"+n:""+n;}'
      'return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());'
      '}'
      # MISSION 088: 「直近の実績」は、ブラウザごとのlocalStorageではなく、
      # このMac上のアプリ内DB(同一オリジンの/api/dashboard/daily-records、
      # 読み取り専用でGETするだけ)を参照する。対面報告(buildRealRecordQueue)
      # ・対面アニメーションは、このミッションの対象外であり、既存どおり
      # localStorage(loadTodayRecords)を使い続ける。MISSION 090で「本日の
      # 指示」「今日の実行キュー」は作業台帳(work_items)側へ移ったため、
      # ここではDB_RECORDS_CACHEだけを保持する。
      'var DB_RECORDS_CACHE=[];'
      # MISSION 090: 「本日の指示」「今日の実行キュー」「社員の状態」は、
      # 媒体共通の作業台帳(work_items、/api/dashboard/work-items、読み取り
      # 専用GET)を参照する。楽天ROOM候補の「今日・今週」連携は、サーバー側
      # (dashboard_db.sync_candidate_work_items)ですでにwork_itemsへ反映
      # 済みのため、ここでpost_candidatesを個別に読む必要はない。
      'var DB_WORK_ITEMS_CACHE=[];'
      'function loadTodayWorkItems(){'
      'var items=DB_WORK_ITEMS_CACHE.filter(function(w){'
      'return w&&w.status==="today";'
      '});'
      'items.sort(function(a,b){'
      'var pa=(typeof a.priority==="number")?a.priority:5;'
      'var pb=(typeof b.priority==="number")?b.priority:5;'
      'if(pa!==pb)return pa-pb;'
      'return (a.id||0)-(b.id||0);'
      '});'
      'return items;'
      '}'
      'function loadTodayRecords(){'
      'var raw=null;'
      'try{raw=window.localStorage.getItem(RECORD_KEY);}catch(e){raw=null;}'
      'var list=[];'
      'try{list=raw?JSON.parse(raw):[];}catch(e){list=[];}'
      'if(!Array.isArray(list))list=[];'
      'var today=todayDateStr();'
      'return list.filter(function(r){return r&&r.date===today&&r.content&&'
      'String(r.content).trim();});'
      '}'
      'function ownerForRecord(rec){'
      'return RECORD_TYPE_OWNERS[rec.type]||RECORD_MEDIA_OWNERS[rec.media]||'
      'RECORD_FALLBACK_OWNER;'
      '}'
      # MISSION 080: 実績のある記録だけを、既存の対面報告ルート
      # (mover=ownerのもの)へ差し替えて再利用する(訪問者スロット・向き・
      # リング・コネクタなどの仕組みはそのまま使う)。対応するルートが
      # ない担当(専任担当のいない実績)は、安全のためスキップする。
      'function buildRealRecordQueue(){'
      'var records=loadTodayRecords();'
      'var queue=[];'
      'records.forEach(function(rec){'
      'var owner=ownerForRecord(rec);'
      'var baseRoute=null;'
      'for(var i=0;i<REPORT_ROUTES.length;i++){'
      'if(REPORT_ROUTES[i].mover===owner){baseRoute=REPORT_ROUTES[i];break;}'
      '}'
      'if(!baseRoute)return;'
      'var typeLabel=rec.type||"記録";'
      'var contentText=(rec.content||rec.metric||"").toString();'
      'queue.push({'
      'key:baseRoute.key+"__real"+queue.length,'
      'mover:baseRoute.mover,'
      'receiver:baseRoute.receiver,'
      'mover_line:typeLabel+"："+contentText,'
      'receiver_line:RECORD_TYPE_ACK[rec.type]||"記録として確認しました",'
      'feed_text:STAFF_NAMES[owner]+"が「"+contentText+"」を記録しました",'
      'isReal:true'
      '});'
      '});'
      'return queue;'
      '}'
      'var REAL_RECORD_QUEUE=buildRealRecordQueue();'
      'var DEMO_MODE_ACTIVE=REAL_RECORD_QUEUE.length===0;'
      'if(recordModeBadgeEl){'
      'if(DEMO_MODE_ACTIVE){'
      'recordModeBadgeEl.textContent="本日：運用記録の入力はまだありません'
      '（デモ表示）";'
      'recordModeBadgeEl.classList.remove("is-real");'
      '}else{'
      'recordModeBadgeEl.textContent="本日：あなたが記録した運用実績を表示'
      '中（実績表示・"+REAL_RECORD_QUEUE.length+"件、他の社員は通常の'
      '待機表示です）";'
      'recordModeBadgeEl.classList.add("is-real");'
      '}'
      '}'
      # MISSION 084: 「今日の実行キュー」。媒体の担当割り当ては、既存の
      # 対面報告ルート向けownerForRecordとは別に、要件どおり「共通・
      # その他→悠」となるQUEUE_MEDIA_OWNERSを使う(種別の割り当てと
      # fallbackは既存のRECORD_TYPE_OWNERS/RECORD_FALLBACK_OWNERを再利用)。
      'function queueOwnerForRecord(rec){'
      'return RECORD_TYPE_OWNERS[rec.type]||QUEUE_MEDIA_OWNERS[rec.media]||'
      'RECORD_FALLBACK_OWNER;'
      '}'
      # MISSION 089: 実行キューの<li>を組み立てる共通処理(運用記録由来・
      # 楽天ROOM候補由来のどちらからも使う)。
      'function buildQueueItem(mediaLabel,content,ownerName,status,nextAction,'
      'linkHref,linkText){'
      'var li=document.createElement("li");'
      'li.className="ai-office-queue-item";'
      'var mediaEl=document.createElement("span");'
      'mediaEl.className="ai-office-queue-media";'
      'mediaEl.textContent=mediaLabel||"媒体未設定";'
      'var contentEl=document.createElement("p");'
      'contentEl.className="ai-office-queue-content";'
      'contentEl.textContent=content;'
      'var metaEl=document.createElement("p");'
      'metaEl.className="ai-office-queue-meta";'
      'var ownerLabel=document.createElement("b");'
      'ownerLabel.textContent="担当：";'
      'metaEl.append(ownerLabel,document.createTextNode(ownerName+"　"));'
      'var statusLabel=document.createElement("b");'
      'statusLabel.textContent="状態：";'
      'metaEl.append(statusLabel,document.createTextNode(status));'
      'var nextEl=document.createElement("p");'
      'nextEl.className="ai-office-queue-next";'
      'var nextLabel=document.createElement("b");'
      'nextLabel.textContent="次の行動：";'
      'nextEl.append(nextLabel,document.createTextNode(nextAction));'
      'var linkEl=document.createElement("a");'
      'linkEl.className="ai-office-queue-link";'
      'linkEl.href=linkHref;'
      'linkEl.textContent=linkText;'
      'li.append(mediaEl,contentEl,metaEl,nextEl,linkEl);'
      'return li;'
      '}'
      # MISSION 090: 「今日の実行キュー」は、作業台帳(work_items)の「今日」
      # 未完了作業だけを一覧表示する(優先度の高い順)。運用記録由来の項目は
      # 混ぜない(運用記録の実績は「直近の実績」「対面報告」側で引き続き
      # 扱う)。
      'function renderExecutionQueue(){'
      'var listEl=document.querySelector("#ai-office-queue-list");'
      'if(!listEl)return;'
      'var items=loadTodayWorkItems();'
      # 作業が無い場合は、既存の空メッセージ<li>をそのまま残す(実在しない
      # 作業を作らない)。
      'if(items.length===0)return;'
      'listEl.innerHTML="";'
      'items.forEach(function(item){'
      'var ownerName=STAFF_NAMES[item.assignee]||item.assignee;'
      'listEl.appendChild(buildQueueItem('
      'item.media,item.task_name,ownerName,'
      'WORK_STATUS_LABELS[item.status]||item.status,'
      '"完了したら運用司令室の「作業台帳」で「完了にする」を押して'
      'ください。",'
      '"/command-center","運用司令室へ移動する"'
      '));'
      '});'
      '}'
      # MISSION 088: renderExecutionQueue/renderRecentRecords/renderDirective
      # の呼び出しは、アプリ内DBからの読み込み(非同期fetch)完了後にまとめて
      # 行う(initDashboardDrivenSections、このIIFEの末尾付近で定義)。
      # MISSION 085: 「直近の実績」。当日より前の記録だけを対象にし、
      # 新しい順(日付の文字列比較。YYYY-MM-DD形式は辞書順=時系列順に
      # なるため単純比較で足りる)に並べて最大5件だけ表示する。今日の
      # 実行キュー(MISSION 090からは作業台帳work_items由来)とは対象期間が
      # 異なるため、当日分は混ざらない。MISSION 088でDB_RECORDS_CACHE
      # (アプリ内DB由来)を参照するようになった。
      'function loadAllRecords(){'
      'return DB_RECORDS_CACHE.filter(function(r){return r&&r.date&&'
      'r.content&&String(r.content).trim();});'
      '}'
      'function loadRecentRecords(){'
      'var today=todayDateStr();'
      'var past=loadAllRecords().filter(function(r){return r.date<today;});'
      'past.sort(function(a,b){'
      'if(a.date===b.date)return 0;'
      'return a.date<b.date?1:-1;'
      '});'
      'return past.slice(0,RECENT_MAX_ITEMS);'
      '}'
      'function renderRecentRecords(){'
      'var listEl=document.querySelector("#ai-office-recent-list");'
      'if(!listEl)return;'
      'var records=loadRecentRecords();'
      # 記録がない場合は、既存の空メッセージ<li>をそのまま残す(架空の
      # 実績を作らない)。
      'if(records.length===0)return;'
      'listEl.innerHTML="";'
      'records.forEach(function(rec){'
      'var owner=queueOwnerForRecord(rec);'
      'var ownerName=STAFF_NAMES[owner]||owner;'
      'var typeLabel=rec.type||"記録";'
      'var recordLabel=RECENT_LABEL_BY_TYPE[rec.type]||(typeLabel+"として記録");'
      'var content=(rec.content||rec.metric||"").toString();'
      'var li=document.createElement("li");'
      'li.className="ai-office-recent-item";'
      'var headerEl=document.createElement("div");'
      'headerEl.className="ai-office-recent-header";'
      'var dateEl=document.createElement("span");'
      'dateEl.className="ai-office-recent-date";'
      'dateEl.textContent=rec.date;'
      'var mediaEl=document.createElement("span");'
      'mediaEl.className="ai-office-queue-media";'
      'mediaEl.textContent=rec.media||"媒体未設定";'
      'headerEl.append(dateEl,mediaEl);'
      'var contentEl=document.createElement("p");'
      'contentEl.className="ai-office-queue-content";'
      'contentEl.textContent=content;'
      'var metaEl=document.createElement("p");'
      'metaEl.className="ai-office-queue-meta";'
      'var ownerLabel=document.createElement("b");'
      'ownerLabel.textContent="担当：";'
      'metaEl.append(ownerLabel,document.createTextNode(ownerName+"　"));'
      'var typeLabelEl=document.createElement("b");'
      'typeLabelEl.textContent="種別：";'
      'metaEl.append(typeLabelEl,document.createTextNode(typeLabel+'
      '"（"+recordLabel+"）"));'
      'var linkEl=document.createElement("a");'
      'linkEl.className="ai-office-queue-link";'
      'linkEl.href="/command-center";'
      'linkEl.textContent="運用司令室へ移動する";'
      'li.append(headerEl,contentEl,metaEl,linkEl);'
      'listEl.appendChild(li);'
      '});'
      '}'
      # MISSION 090: 「柴犬社長からの本日の指示」は、作業台帳(work_items)で
      # 「今日」の未完了作業のうち、優先度が最も高い(priorityの数字が最小の)
      # 先頭1件をそのまま指示として表示する。該当作業が1件もない場合は、
      # 実在しない指示を作らず、その旨を正直に表示する。
      'function pickDirective(){'
      'var items=loadTodayWorkItems();'
      'if(items.length===0){'
      'return {'
      'task:"今日の未完了作業はありません",'
      'reason:"運用司令室の「作業台帳」で、今日やる作業を追加できます。",'
      'href:"/command-center",'
      'label:"運用司令室を開く"'
      '};'
      '}'
      'var top=items[0];'
      'var ownerName=STAFF_NAMES[top.assignee]||top.assignee;'
      'return {'
      'task:top.task_name,'
      'reason:"作業台帳で「今日」に割り当てられた、優先度が最も高い未完了'
      '作業です（媒体："+top.media+"／担当："+ownerName+"）",'
      'href:"/command-center",'
      'label:"運用司令室を開く"'
      '};'
      '}'
      'function renderDirective(){'
      'var d=pickDirective();'
      'var taskEl=document.querySelector("#ai-office-directive-task");'
      'var reasonEl=document.querySelector("#ai-office-directive-reason");'
      'var btnEl=document.querySelector("#ai-office-directive-button");'
      'if(taskEl)taskEl.textContent=d.task;'
      'if(reasonEl)reasonEl.textContent=d.reason;'
      'if(btnEl){btnEl.href=d.href;btnEl.textContent=d.label;}'
      '}'
      # MISSION 090: 既存15名全員の状態を、作業台帳(work_items)の「今日」の
      # 未完了作業の担当(assignee)から決める。担当する作業がある社員だけ
      # 「稼働中（実績表示）」にし、無い社員は「待機中（実績なし）」と正直に
      # 表示する(架空の稼働・実績を作らない)。社員名簿カード・フロア
      # トークン・上部ステータスストリップの3箇所をまとめて更新する。
      # MISSION 091: 分析ラボ(葵/"analytics")だけは例外で、作業台帳の担当
      # 割り当てではなく「当日に実績スナップショットがDBへ記録されたか」
      # だけで稼働中/待機中を決める(要件どおり、作業台帳の割り当てとは
      # 切り離す)。
      'function applyStaffRealState(todayItems,metricsToday){'
      'var workingKeys={};'
      'todayItems.forEach(function(item){'
      'if(item&&item.assignee)workingKeys[item.assignee]=true;'
      '});'
      'workingKeys.analytics=Boolean(metricsToday&&metricsToday.length);'
      'ALL_STAFF_KEYS.forEach(function(key){'
      'var working=Boolean(workingKeys[key]);'
      'var statusKey=working?"working":"waiting";'
      'var label=(STATUS_LABELS[statusKey]||(working?"稼働中":"待機中"))+'
      '(working?"（実績表示）":"（実績なし）");'
      'document.querySelectorAll('
      '\'.ai-office-desk[data-department="\'+key+\'"] .ai-office-status-badge,\''
      '+\'.ai-office-strip-chip[data-department="\'+key+\'"] .ai-office-status-badge\''
      ').forEach(function(badge){'
      'badge.classList.remove("ai-office-status-working","ai-office-status-waiting",'
      '"ai-office-status-pending","ai-office-status-demo_done");'
      'badge.classList.add("ai-office-status-"+statusKey);'
      'badge.textContent=label;'
      'badge.dataset.suffix=working?"実績表示":"実績なし";'
      '});'
      'var token=document.querySelector("#ai-office-token-"+key);'
      'if(token){'
      'token.classList.remove("ai-office-floormap-token-working",'
      '"ai-office-floormap-token-waiting","ai-office-floormap-token-pending",'
      '"ai-office-floormap-token-demo_done");'
      'token.classList.add("ai-office-floormap-token-"+statusKey);'
      '}'
      'var dot=document.querySelector("#ai-office-nameplate-dot-"+key);'
      'if(dot){'
      'dot.classList.remove("ai-office-nameplate-dot-working",'
      '"ai-office-nameplate-dot-waiting","ai-office-nameplate-dot-pending",'
      '"ai-office-nameplate-dot-demo_done");'
      'dot.classList.add("ai-office-nameplate-dot-"+statusKey);'
      '}'
      'var statusText=document.querySelector("#ai-office-nameplate-status-"+key);'
      'if(statusText)statusText.textContent=" "+label;'
      '});'
      '}'
      # MISSION 091: 分析ラボ(葵)の報告。DBに保存済みの事実(当日に記録
      # された、最後に保存された1件の媒体・指標)だけを短く表示する。数値
      # そのものや、推測・比較は一切含めない。記録が無い日は、架空の分析・
      # 成果・会話を作らず、正直に待機中の文言を出す。
      'var analyticsReportEl=document.querySelector("#ai-office-analytics-report");'
      'var analyticsReportTextEl=document.querySelector('
      '"#ai-office-analytics-report-text");'
      'function metricLabel(media,metric){'
      'var fields=METRIC_FIELD_LABELS[media]||[];'
      'for(var i=0;i<fields.length;i++){'
      'if(fields[i].key===metric)return fields[i].label;'
      '}'
      'return metric;'
      '}'
      'function renderAnalyticsReport(metricsToday){'
      'if(!analyticsReportTextEl)return;'
      'if(!metricsToday||!metricsToday.length){'
      'analyticsReportTextEl.textContent="本日の実績記録はまだありません'
      '（待機中）";'
      'if(analyticsReportEl)analyticsReportEl.classList.remove("is-real");'
      'return;'
      '}'
      'var latest=metricsToday[metricsToday.length-1];'
      'var label=metricLabel(latest.media,latest.metric);'
      'var text=latest.media+"の"+label+"を記録しました";'
      'if(metricsToday.length>1){'
      'text+="（他"+(metricsToday.length-1)+"件も記録しました）";'
      '}'
      'analyticsReportTextEl.textContent=text;'
      'if(analyticsReportEl)analyticsReportEl.classList.add("is-real");'
      '}'
      # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」は、
      # このMac上のアプリ内DBを読み取り専用GETで1回取得してから、まとめて
      # 描画する。取得前・取得失敗時はDB_RECORDS_CACHEが空のままなので、
      # 既存の「記録がまだありません」という空状態表示に安全に収まる
      # (架空の実績を作らない)。fetchが使えない環境でも描画自体は行う。
      # MISSION 090: 作業台帳(/api/dashboard/work-items)もあわせて取得し、
      # 「本日の指示」「今日の実行キュー」「社員の状態」の実データ化に使う。
      # MISSION 091: 実績スナップショット(/api/dashboard/metrics、当日分の
      # み)もあわせて取得し、分析ラボ(葵)の状態・報告の実データ化に使う。
      'function initDashboardDrivenSections(){'
      'if(typeof window.fetch!=="function"){'
      'renderDirective();renderExecutionQueue();renderRecentRecords();'
      'applyStaffRealState([],[]);'
      'renderAnalyticsReport([]);'
      'return;'
      '}'
      'var recordsPromise=window.fetch("/api/dashboard/daily-records")'
      '.then(function(res){return res.json();}).then(function(data){'
      'DB_RECORDS_CACHE=(data&&Array.isArray(data.records))?data.records:[];'
      '}).catch(function(){DB_RECORDS_CACHE=[];});'
      'var workItemsPromise=window.fetch("/api/dashboard/work-items")'
      '.then(function(res){return res.json();}).then(function(data){'
      'DB_WORK_ITEMS_CACHE=(data&&Array.isArray(data.workItems))?data.workItems:[];'
      '}).catch(function(){DB_WORK_ITEMS_CACHE=[];});'
      'var metricsTodayPromise=window.fetch('
      '"/api/dashboard/metrics?date="+todayDateStr())'
      '.then(function(res){return res.json();})'
      '.then(function(data){'
      'return (data&&Array.isArray(data.metrics))?data.metrics.slice().reverse():[];'
      '}).catch(function(){return [];});'
      'Promise.all([recordsPromise,workItemsPromise,metricsTodayPromise])'
      '.then(function(results){'
      'var metricsToday=results[2];'
      'renderDirective();'
      'renderExecutionQueue();'
      'renderRecentRecords();'
      'applyStaffRealState(loadTodayWorkItems(),metricsToday);'
      'renderAnalyticsReport(metricsToday);'
      '});'
      '}'
      'initDashboardDrivenSections();'
      'var bubbleEl=document.querySelector("#ai-office-floormap-bubble");'
      # MISSION 076: 対面報告の「報告者の吹き出し」と「受け手の返答の
      # 吹き出し」を別要素にする(bubbleElReceiver、CSSで配色を変える)。
      # 部署間交流(Track B)は引き続き、もう1つの吹き出し(bubbleElB)を
      # 同時並行で使う。
      'var bubbleElReceiver=document.querySelector("#ai-office-floormap-bubble-receiver");'
      'var bubbleElB=document.querySelector("#ai-office-floormap-bubble-b");'
      'var speechEl=document.querySelector("#ai-office-floormap-speech");'
      'var feedListEl=document.querySelector("#ai-office-activity-feed-list");'
      'var toggleBtn=document.querySelector("#ai-office-anim-toggle");'
      'var overlayEl=document.querySelector("#ai-office-floormap-overlay");'
      'var commandPulseEl=document.querySelector("#ai-office-command-pulse");'
      'var progressLineEl=document.querySelector("#ai-office-progress-board-line");'
      # MISSION 077: 「誰が誰へ報告しているか」を一目で分かるようにする、
      # 進行バナー・対面会話パネル・報告方向の点線コネクタ用の要素。
      'var reportBannerEl=document.querySelector("#ai-office-report-banner");'
      'var reportPanelMoverEl=document.querySelector("#ai-office-report-panel-mover");'
      'var reportPanelReceiverEl=document.querySelector("#ai-office-report-panel-receiver");'
      'var reportConnectorEl=document.querySelector("#ai-office-report-connector");'
      'var STATUS_KEYS=Object.keys(STATUS_LABELS);'
      # MISSION 076: いま誰かとの対面報告・交流に参加している人物のキーを
      # 記録する(報告者・受け手の双方)。同じ人物を、報告ルート(Track A)と
      # 部署間交流(Track B)で二重に動かさないための共有フラグ集合。
      'var busy={};'
      'function markBusy(key,val){if(val){busy[key]=true;}else{delete busy[key];}}'
      'function isBusy(key){return !!busy[key];}'
      # MISSION 076: 対面報告中、報告者・受け手がお互いのほうへ「向き」を
      # 変える(スプライトをscaleX反転)。位置・常時アニメーションを担う
      # 外側のai-office-floormap-tokenには触れず、内側のスプライトだけを
      # 反転させることで、既存のアイドル・稼働中・移動中アニメーションと
      # 競合しない。
      'function faceTowards(personKey,refLeft){'
      'var sprite=document.querySelector("#ai-office-sprite-"+personKey);'
      'var tokenEl=document.querySelector("#ai-office-token-"+personKey);'
      'if(!sprite||!tokenEl)return;'
      'var myLeft=parseFloat(tokenEl.style.left);'
      'sprite.classList.remove("is-facing-left","is-facing-right");'
      'sprite.classList.add(refLeft<myLeft?"is-facing-left":"is-facing-right");'
      '}'
      'function resetFacing(personKey){'
      'var sprite=document.querySelector("#ai-office-sprite-"+personKey);'
      'if(sprite)sprite.classList.remove("is-facing-left","is-facing-right");'
      '}'
      # MISSION 076: 名前札に「移動中」「対面報告中」「応答中」「帰席中」を
      # 短く表示する。
      'function setPhase(personKey,text){'
      'var el=document.querySelector("#ai-office-nameplate-phase-"+personKey);'
      'if(el)el.textContent=text?("・"+text):"";'
      '}'
      # MISSION 077: フロアマップ最上部の進行バナーを更新する。対面報告が
      # 終わっても次の対面報告が始まるまで内容を保持する(停止時にも
      # 「誰が誰へ報告中だったか」が読み取れるようにするため、明示的な
      # クリア処理は行わない)。
      # MISSION 080: 実績(localStorageの運用記録)による対面報告は、デモの
      # 対面報告と画面上で明確に区別できるよう「実績報告中」と表示する。
      'function updateReportBanner(route){'
      'var verb=route.isReal?"実績報告中":"対面報告中";'
      'reportBannerEl.textContent=verb+"　"+STAFF_NAMES[route.mover]+'
      '"（"+REPORT_ROLES[route.mover]+"） → "+STAFF_NAMES[route.receiver]+'
      '"（"+REPORT_ROLES[route.receiver]+"）"+(route.isReal?"（実績）":"");'
      '}'
      # MISSION 077: 対面会話パネル(左に報告者、右に受け手)。バナーと同様、
      # 次の対面報告が始まるまで内容を保持する。
      'function setReportPanelLine(el,speakerKey,receiverKey,text){'
      'el.textContent="";'
      'var b=document.createElement("b");'
      'b.textContent=STAFF_NAMES[speakerKey]+" → "+STAFF_NAMES[receiverKey];'
      'el.appendChild(b);'
      'el.appendChild(document.createTextNode("「"+text+"」"));'
      '}'
      # MISSION 077: 報告者→受け手を、細い点線+矢印で結ぶ(報告の方向が
      # 分かるように、矢印は受け手側を指す)。
      'function showReportConnector(fromPos,toPos){'
      'var dx=toPos.left-fromPos.left,dy=toPos.top-fromPos.top;'
      'var length=Math.sqrt(dx*dx+dy*dy);'
      'var angle=Math.atan2(dy,dx)*180/Math.PI;'
      'reportConnectorEl.style.left=fromPos.left+"%";'
      'reportConnectorEl.style.top=fromPos.top+"%";'
      'reportConnectorEl.style.width=length+"%";'
      'reportConnectorEl.style.transform="rotate("+angle+"deg)";'
      'reportConnectorEl.classList.add("is-visible");'
      '}'
      'function hideReportConnector(){reportConnectorEl.classList.remove("is-visible");}'
      # MISSION 075: 「今のオフィス」の短いステータス行(稼働中・移動中・
      # 相談中の人数)を、状態が変わるたびに更新する。
      'function refreshOfficeStatusLine(){'
      'var w=document.querySelectorAll(".ai-office-floormap-token.is-working").length;'
      'var mv=document.querySelectorAll(".ai-office-floormap-token.is-moving").length;'
      'var c=trackBTalking?1:0;'
      'progressLineEl.textContent="現在：稼働中"+w+"人・移動中"+mv+"人・相談中"+c+"人（デモ）";'
      '}'
      'function setStatus(personKey,statusKey){'
      'var label=STATUS_LABELS[statusKey];'
      'document.querySelectorAll(\'[data-department="\'+personKey+\'"]\').forEach(function(el){'
      'var avatar=el.classList.contains("ai-office-char-avatar")?el:'
      'el.querySelector(".ai-office-char-avatar");'
      'if(avatar){'
      'STATUS_KEYS.forEach(function(s){avatar.classList.remove("ai-office-char-avatar-"+s);});'
      'avatar.classList.add("ai-office-char-avatar-"+statusKey);'
      '}'
      'var badge=el.querySelector(".ai-office-status-badge");'
      'if(badge){'
      'STATUS_KEYS.forEach(function(s){badge.classList.remove("ai-office-status-"+s);});'
      'badge.classList.add("ai-office-status-"+statusKey);'
      'badge.textContent=label+"（"+badge.dataset.suffix+"）";'
      '}'
      '});'
      # MISSION 074: フロアマップ上の社員本人は、黒いアイコン枠(ai-office-
      # char-avatar)ではなく、専用のai-office-floormap-token-*で発光させる。
      'var token=document.querySelector("#ai-office-token-"+personKey);'
      'if(token){'
      'STATUS_KEYS.forEach(function(s){token.classList.remove("ai-office-floormap-token-"+s);});'
      'token.classList.add("ai-office-floormap-token-"+statusKey);'
      '}'
      'var dot=document.querySelector("#ai-office-nameplate-dot-"+personKey);'
      'if(dot){'
      'STATUS_KEYS.forEach(function(s){dot.classList.remove("ai-office-nameplate-dot-"+s);});'
      'dot.classList.add("ai-office-nameplate-dot-"+statusKey);'
      '}'
      'var statusText=document.querySelector("#ai-office-nameplate-status-"+personKey);'
      'if(statusText)statusText.textContent=" "+label+"（デモ）";'
      '}'
      'function setWorking(personKey,working){'
      'var token=document.querySelector("#ai-office-token-"+personKey);'
      'if(token)token.classList.toggle("is-working",working);'
      'refreshOfficeStatusLine();'
      '}'
      'function setMoving(personKey,moving){'
      'var token=document.querySelector("#ai-office-token-"+personKey);'
      'if(token)token.classList.toggle("is-moving",moving);'
      'refreshOfficeStatusLine();'
      '}'
      'function setMonitorActive(personKey,active){'
      'var glow=document.querySelector("#ai-office-monitor-"+personKey);'
      'if(glow)glow.classList.toggle("is-active",active);'
      '}'
      # MISSION 076: 報告者(mover)は、訪問先(atKey)にVISITOR_SLOTSが
      # 定義されていればその位置(=本人が実際に立っている場所)に、
      # なければatKey本人の座席に吹き出しを出す。
      'function showBubble(text,atKey){'
      'var pos=VISITOR_SLOTS[atKey]||POSITIONS[atKey];'
      'bubbleEl.style.left=pos.left+"%";'
      'bubbleEl.style.top=pos.top+"%";'
      'bubbleEl.textContent=text;'
      'bubbleEl.classList.add("is-visible");'
      '}'
      'function hideBubble(){bubbleEl.classList.remove("is-visible");}'
      # MISSION 076: 受け手(receiver)は自席から動かないため、常に本人の
      # 座席そのものへ吹き出しを出す。
      'function showBubbleReceiver(text,atKey){'
      'var pos=POSITIONS[atKey];'
      'bubbleElReceiver.style.left=pos.left+"%";'
      'bubbleElReceiver.style.top=pos.top+"%";'
      'bubbleElReceiver.textContent=text;'
      'bubbleElReceiver.classList.add("is-visible");'
      '}'
      'function hideBubbleReceiver(){bubbleElReceiver.classList.remove("is-visible");}'
      'function showBubbleB(text,atKey){'
      'var pos=VISITOR_SLOTS[atKey]||POSITIONS[atKey];'
      'bubbleElB.style.left=pos.left+"%";'
      'bubbleElB.style.top=pos.top+"%";'
      'bubbleElB.textContent=text;'
      'bubbleElB.classList.add("is-visible");'
      '}'
      'function hideBubbleB(){bubbleElB.classList.remove("is-visible");}'
      'function showSpeech(personKey,text){'
      'speechEl.textContent="";'
      'var b=document.createElement("b");'
      'b.textContent=STAFF_NAMES[personKey];'
      'speechEl.appendChild(b);'
      'speechEl.appendChild(document.createTextNode("「"+text+"」（デモ会話）"));'
      '}'
      'function pushFeed(text){'
      'var li=document.createElement("li");'
      'li.textContent=text;'
      'feedListEl.insertBefore(li,feedListEl.firstChild);'
      'while(feedListEl.children.length>MAX_FEED){'
      'feedListEl.removeChild(feedListEl.lastChild);'
      '}'
      '}'
      # MISSION 075: 他の人の自席を訪ねる際、相手の座標にぴったり重なって
      # 表示されてしまうと、常時の移動デモが増えたことでキャラクター同士の
      # 重なりが目立ちやすくなる。訪問先にVISITOR_SLOTS(部屋の中で他の
      # 在席者と重ならない位置)が定義されている場合はそちらへ立ち、
      # 休憩スペースなど専用の待ち合わせ地点や、自席への帰宅時はそのままの
      # 座標を使う。
      'function moveToken(personKey,atKey){'
      'var tokenEl=document.querySelector("#ai-office-token-"+personKey);'
      'var pos=POSITIONS[atKey];'
      'if(atKey!==personKey&&VISITOR_SLOTS[atKey]){'
      'pos=VISITOR_SLOTS[atKey];'
      '}'
      'tokenEl.style.left=pos.left+"%";'
      'tokenEl.style.top=pos.top+"%";'
      '}'
      # MISSION 075: 報告到着時に指令デスク周辺で短く点灯する通知光。
      'function pulseCommandDesk(){'
      'commandPulseEl.classList.remove("is-active");'
      'void commandPulseEl.offsetWidth;'
      'commandPulseEl.classList.add("is-active");'
      '}'
      'var paused=false,pendingFn=null,pendingTimer=null;'
      'function scheduleNext(fn,delay){'
      'pendingFn=fn;'
      'if(paused)return;'
      'pendingTimer=setTimeout(function(){'
      'pendingTimer=null;'
      'var f=pendingFn;'
      'pendingFn=null;'
      'if(f)f();'
      '},delay);'
      '}'
      # MISSION 075: Track B(部署間交流)専用の、もう1本の予約タイマー。
      # pausedフラグはTrack Aと共有し、停止ボタン1つで両方止める。
      'var pendingFnB=null,pendingTimerB=null;'
      'function scheduleNextB(fn,delay){'
      'pendingFnB=fn;'
      'if(paused)return;'
      'pendingTimerB=setTimeout(function(){'
      'pendingTimerB=null;'
      'var f=pendingFnB;'
      'pendingFnB=null;'
      'if(f)f();'
      '},delay);'
      '}'
      'toggleBtn.addEventListener("click",function(){'
      'paused=!paused;'
      # MISSION 075: 停止時はフロアマップ全体のCSSアニメーション
      # (常時のアイドルモーション・モニター明滅・湯気・通知光を含む)も
      # 一括で停止する。
      'overlayEl.classList.toggle("is-paused",paused);'
      'if(paused){'
      'if(pendingTimer){clearTimeout(pendingTimer);pendingTimer=null;}'
      'if(pendingTimerB){clearTimeout(pendingTimerB);pendingTimerB=null;}'
      'toggleBtn.textContent="アニメーションを再生";'
      '}else{'
      'toggleBtn.textContent="アニメーションを停止";'
      'if(pendingFn){'
      'var f=pendingFn;'
      'pendingFn=null;'
      'pendingTimer=setTimeout(function(){pendingTimer=null;f();},400);'
      '}'
      'if(pendingFnB){'
      'var fb=pendingFnB;'
      'pendingFnB=null;'
      'pendingTimerB=setTimeout(function(){pendingTimerB=null;fb();},700);'
      '}'
      '}'
      '});'
      # --- Track A: 対面報告ルート(役割ごとの受け手へ報告に行く) ---
      # MISSION 076: 「中央(指令デスク)へ移動するだけ」の演出をやめ、
      # 報告する本人が受け手の前まで歩き、向かい合って会話してから自席へ
      # 戻る流れに変更した。busy{}で報告者・受け手の両方を予約し、
      # Track B(交流デモ)が同じ人物を同時に動かさないようにする。
      # MISSION 080: 報告ルートを配列インデックスではなく、ルート
      # オブジェクトそのもので受け渡すようにした(デモのREPORT_ROUTESと、
      # 本日の運用記録から組み立てたREAL_RECORD_QUEUEの両方を、同じ
      # ステップ関数群で扱えるようにするため)。
      'var reportRouteIdx=0,realRecordIdx=0;'
      'function pickNextReportRoute(){'
      'var pool=DEMO_MODE_ACTIVE?REPORT_ROUTES:REAL_RECORD_QUEUE;'
      'var cursor=DEMO_MODE_ACTIVE?reportRouteIdx:realRecordIdx;'
      'for(var n=0;n<pool.length;n++){'
      'var idx=(cursor+n)%pool.length;'
      'var r=pool[idx];'
      'if(!isBusy(r.mover)&&!isBusy(r.receiver)){'
      'if(DEMO_MODE_ACTIVE)reportRouteIdx=(idx+1)%pool.length;'
      'else realRecordIdx=(idx+1)%pool.length;'
      'return r;'
      '}'
      '}'
      'return pool[cursor];'
      '}'
      'function reportStepTravel(route,onDone){'
      'setStatus(route.mover,"working");'
      'setWorking(route.mover,true);'
      'setMoving(route.mover,true);'
      'setPhase(route.mover,"移動中");'
      'moveToken(route.mover,route.receiver);'
      'scheduleNext(function(){reportStepArrive(route,onDone);},1800);'
      '}'
      # MISSION 076: 到着したら、報告者・受け手の双方が向かい合う(向きを
      # 反転)。報告者の吹き出しで一次のセリフを表示し、指令デスクへの
      # 報告(柴犬社長が受け手)の場合だけ通知光を点灯する。
      # MISSION 077: 「誰が誰へ報告しているか」を一目で分かるようにする、
      # 進行バナー・対面会話パネル(1行目)・発光リング・点線コネクタ・
      # 詳しい名前札を、この時点でまとめて表示する。他の社員を少し
      # 控えめにするため、overlayに is-reporting を付与する。
      'function reportStepArrive(route,onDone){'
      'setMoving(route.mover,false);'
      'setWorking(route.mover,true);'
      'setStatus(route.mover,"pending");'
      'setPhase(route.mover,shortName(route.receiver)+"へ報告中");'
      'setPhase(route.receiver,STAFF_NAMES[route.mover]+"の報告を確認中");'
      'var moverToken=document.querySelector("#ai-office-token-"+route.mover);'
      'var receiverToken=document.querySelector("#ai-office-token-"+route.receiver);'
      'if(moverToken)moverToken.classList.add("is-report-mover");'
      'if(receiverToken)receiverToken.classList.add("is-report-receiver");'
      'overlayEl.classList.add("is-reporting");'
      'var meetPos=VISITOR_SLOTS[route.receiver]||POSITIONS[route.receiver];'
      'faceTowards(route.mover,POSITIONS[route.receiver].left);'
      'faceTowards(route.receiver,meetPos.left);'
      'showReportConnector(meetPos,POSITIONS[route.receiver]);'
      'updateReportBanner(route);'
      'setReportPanelLine(reportPanelMoverEl,route.mover,route.receiver,route.mover_line);'
      'reportPanelReceiverEl.textContent="";'
      'showBubble(route.mover_line,route.receiver);'
      'showSpeech(route.mover,route.mover_line);'
      'if(route.receiver==="operations_lead")pulseCommandDesk();'
      'scheduleNext(function(){reportStepReply(route,onDone);},2200);'
      '}'
      # MISSION 076: 受け手が応答する。報告者の吹き出しは消し、受け手専用の
      # 吹き出し(配色違い)で返答を表示してから、活動フィードへ記録する。
      # MISSION 077: 対面会話パネルの2行目(受け手の返答)もここで表示する。
      # MISSION 080: 実績による報告は「デモ：」ではなく「実績：」として
      # 活動フィードへ記録し、デモと明確に区別できるようにする。
      'function reportStepReply(route,onDone){'
      'hideBubble();'
      'setWorking(route.receiver,true);'
      'setReportPanelLine(reportPanelReceiverEl,route.receiver,route.mover,route.receiver_line);'
      'showBubbleReceiver(route.receiver_line,route.receiver);'
      'showSpeech(route.receiver,route.receiver_line);'
      'pushFeed((route.isReal?"実績：":"デモ：")+route.feed_text);'
      'refreshOfficeStatusLine();'
      'scheduleNext(function(){reportStepReturn(route,onDone);},2200);'
      '}'
      # MISSION 077: 対面報告が終わったら、発光リング・点線コネクタ・
      # 他の社員を控えめにする表示(is-reporting)は解除する(進行バナー・
      # 会話パネル・名前札の「誰が誰へ報告したか」は、次の対面報告が
      # 始まるまでそのまま残す)。
      'function reportStepReturn(route,onDone){'
      'hideBubbleReceiver();'
      'hideReportConnector();'
      'overlayEl.classList.remove("is-reporting");'
      'var moverToken=document.querySelector("#ai-office-token-"+route.mover);'
      'var receiverToken=document.querySelector("#ai-office-token-"+route.receiver);'
      'if(moverToken)moverToken.classList.remove("is-report-mover");'
      'if(receiverToken)receiverToken.classList.remove("is-report-receiver");'
      'setWorking(route.receiver,false);'
      'setPhase(route.receiver,"");'
      'resetFacing(route.receiver);'
      'setPhase(route.mover,"帰席中");'
      'setWorking(route.mover,false);'
      'setMoving(route.mover,true);'
      'moveToken(route.mover,route.mover);'
      'resetFacing(route.mover);'
      'scheduleNext(function(){reportStepSettle(route,onDone);},1800);'
      '}'
      'function reportStepSettle(route,onDone){'
      'setMoving(route.mover,false);'
      'setPhase(route.mover,"");'
      'setStatus(route.mover,"waiting");'
      # MISSION 076: 柴犬社長は常に「稼働中」(全体を見ている状態)へ戻す。
      # それ以外の受け手は「待機中」へ戻す。
      'setStatus(route.receiver,route.receiver==="operations_lead"?"working":"waiting");'
      'onDone();'
      '}'
      # MISSION 080: デモ表示中(DEMO_MODE_ACTIVE)は既存どおりREPORT_ROUTES
      # を巡回し、本日の運用記録がある場合(実績表示)はREAL_RECORD_QUEUEだけ
      # を巡回する。実績のある社員だけが動き、実績のない社員は通常の待機
      # 表示のままになる。
      'function runReportRoute(){'
      'var route=pickNextReportRoute();'
      'markBusy(route.mover,true);'
      'markBusy(route.receiver,true);'
      'reportStepTravel(route,function(){'
      'markBusy(route.mover,false);'
      'markBusy(route.receiver,false);'
      'scheduleNext(runReportRoute,DEMO_MODE_ACTIVE?500:1500);'
      '});'
      '}'
      # --- Track B: 部署間・休憩スペースでの交流デモ(継続ループ) ---
      # MISSION 076: 対面報告に統合されなかった、彩の休憩スペース・凛の
      # 資料室確認の2件だけが残る。busy{}を使い、Track A(対面報告)と
      # 同じ人物を二重に動かさないようにする。
      'var trackBTalking=false,trackBIdx=0;'
      'function pickNextSceneIdx(){'
      'for(var n=0;n<INTERACTIONS.length;n++){'
      'var idx=(trackBIdx+n)%INTERACTIONS.length;'
      'if(!isBusy(INTERACTIONS[idx].mover))return idx;'
      '}'
      'return trackBIdx;'
      '}'
      'function stepInteractionStart(sceneIdx,onDone){'
      'var scene=INTERACTIONS[sceneIdx];'
      'markBusy(scene.mover,true);'
      'setStatus(scene.mover,"working");'
      'setWorking(scene.mover,true);'
      'setMoving(scene.mover,true);'
      'moveToken(scene.mover,scene.location);'
      'scheduleNextB(function(){stepInteractionTalk(sceneIdx,onDone);},1700);'
      '}'
      'function stepInteractionTalk(sceneIdx,onDone){'
      'var scene=INTERACTIONS[sceneIdx];'
      'setWorking(scene.mover,false);'
      'setMoving(scene.mover,false);'
      'trackBTalking=true;'
      'showBubbleB(scene.line,scene.location);'
      'showSpeech(scene.speaker,scene.line);'
      'pushFeed("デモ："+scene.feed_text);'
      'refreshOfficeStatusLine();'
      'scheduleNextB(function(){stepInteractionReturn(sceneIdx,onDone);},2400);'
      '}'
      'function stepInteractionReturn(sceneIdx,onDone){'
      'var scene=INTERACTIONS[sceneIdx];'
      'hideBubbleB();'
      'trackBTalking=false;'
      'setMoving(scene.mover,true);'
      'moveToken(scene.mover,scene.mover);'
      'scheduleNextB(function(){stepInteractionSettle(sceneIdx,onDone);},1700);'
      '}'
      'function stepInteractionSettle(sceneIdx,onDone){'
      'var scene=INTERACTIONS[sceneIdx];'
      'setMoving(scene.mover,false);'
      'setStatus(scene.mover,"waiting");'
      'markBusy(scene.mover,false);'
      'scheduleNextB(function(){onDone();},1200);'
      '}'
      'function runTrackB(){'
      'var sceneIdx=pickNextSceneIdx();'
      'trackBIdx=(sceneIdx+1)%INTERACTIONS.length;'
      'stepInteractionStart(sceneIdx,function(){'
      'scheduleNextB(runTrackB,1400);'
      '});'
      '}'
      'refreshOfficeStatusLine();'
      'scheduleNext(runReportRoute,900);'
      # MISSION 080: 実績表示中(本日の運用記録がある場合)は、デモ専用の
      # 部署間交流(Track B: 彩の休憩・凛の資料室確認)を動かさない
      # (実績のない社員は通常の待機表示のままにするため)。
      'if(DEMO_MODE_ACTIVE)scheduleNextB(runTrackB,3500);'
      '})();'
      '</script>'
      '</section>'
  )


def register_office_views(app):
  """Flaskアプリへ表示専用ルートを登録する。"""
  @app.route("/office")
  def office():
    # MISSION 083: オフィスを「実在12人と無関係な架空キャラクター」から、
    # AIオフィスと同じ社員(里奈・凛・葵・蒼)が実際にそこにいるスペースへ
    # 変更した。他画面(社長室・休憩室)には表示しない、この4人だけを表示
    # する(同じ社員を全画面に常時重複表示しない)。
    desks = (
        ("room", "里奈", "ROOM担当", "楽天ROOMの反応が良いジャンルを確認中", "ROOM"),
        ("rin", "凛", "資料室管理", "資料室の内容を確認中", "資料"),
        ("analytics", "葵", "分析担当", "今週の数字を比較中", "分析"),
        ("sou", "蒼", "技術担当", "画面・動作を確認中", "技術"),
    )
    # トークン(社員本人の立体キャラクター)は、対応するデスクのすぐ上に
    # 置く(トークンの座標はシーン全体に対する%で、デスクのd1〜d4と同じ
    # 列に揃える)。
    token_positions = {
        "room": {"left": 36, "top": 34},
        "rin": {"left": 52, "top": 34},
        "analytics": {"left": 68, "top": 34},
        "sou": {"left": 82, "top": 34},
    }
    # MISSION 025/028: 各デスクをクリック・キーボード操作可能な<button>に
    # している(<button>はEnter/Spaceでの活性化を標準で備えるため、
    # キーボード操作対応を別途実装する必要がない)。
    # MISSION 051: 以前はここに実データ(work_logs、GET /api/logs)を表示
    # していたが、DB内のwork_logsが2026-09-01付けの3件(A8.net提携確認・
    # 美容サロン向けPinterest素材・ラッシュアディクト投稿など、現在の
    # 実際の運用と無関係な古いテスト用データ)しかなく、それをそのまま
    # 「現在の作業」として表示すると実態と食い違ってしまう。DB(work_logs)
    # 自体は変更しないため、このページでは/api/logsの参照をやめ、柴犬社長が
    # 確認した現在の投稿運用状況(Pinterest・note・Threadsの実際の状況)を
    # 静的に表示する。
    # MISSION 083: デスク本体からは人物イラストを取り除き(社員本人は上の
    # フロアトークンとして別に表示する)、役割・現在の作業・状態だけを示す。
    desk_html = "".join(
        f'<button type="button" class="desk d{i + 1} desk-back" '
        f'id="desk-{key}" data-key="{key}" '
        f'data-screen="{screen}" aria-haspopup="true" aria-expanded="false" '
        f'aria-controls="desk-detail-panel">'
        f'<i class="desk-role">{role}</i>'
        f'<em id="desk-task-{key}">{task}</em>'
        f'<i class="status-chip status-pending" id="desk-status-{key}" aria-hidden="true"></i></button>'
        for i, (key, name, role, task, screen) in enumerate(desks)
    )
    desk_info_js = ",".join(
        f'"{key}":{{name:"{name}",role:"{role}"}}' for key, name, role, _t, _s in desks
    )
    floor_tokens = "".join(
        _ai_office_space_token("office", key, token_positions[key], "waiting")
        for key, _n, _r, _t, _s in desks
    )
    status_items = "".join(
        f'<li id="office-status-item-{key}"><b>{name}（{role}）</b>'
        f'<span id="office-status-text-{key}">{task}（デモ表示）</span></li>'
        for key, name, role, task, _s in desks
    )
    scene = (
        '<section class="scene office" aria-label="作業フロア"><div class="label">WEB制作・運用フロア<span>● LIVE</span>'
        '<span class="cast-badge">AI Hive OSの架空キャラクター</span></div>'
        '<div class="live-board" id="office-live-status"><b>現在の投稿運用状況</b>'
        '<ul>'
        '<li>Pinterest：5件公開済み・48時間後を目安に最新投稿の反応を確認予定</li>'
        '<li>note：AI Hive関連の記事3件公開済み・次の記事下書きを準備済み'
        '（このnoteアカウントには、この他にも既存記事があります）</li>'
        '<li>Threads：Difyで別管理の自動投稿を運用中（このアプリからは投稿・ログイン・連携しません）</li>'
        '</ul></div>'
        '<div class="windows" aria-hidden="true"><i></i><i></i><i></i></div><div class="plant" aria-hidden="true">🪴</div>'
        '<div class="lamp" aria-hidden="true"></div>'
        '<div class="door"><b>☕</b><small>BREAK ROOM</small></div><div class="route" aria-hidden="true"></div>' + desk_html + floor_tokens +
        '<div class="meeting" aria-hidden="true"><small>MTG SPACE</small>'
        '<span>🪑</span><span>🪑</span></div>'
        '</section>'
        # MISSION 028/051: デスクの詳細パネル。通常のドキュメントフロー内に
        # 置き、クリック/キーボードで選択したデスクの名前・役割をJSで書き
        # 込んで表示する(初期状態はhiddenで、DB/APIへの副作用は一切ない)。
        # どのデスクを選んでも、個別の担当データではなく、同じ「現在の投稿
        # 運用状況」を表示する旨を必ず明記する(desk-detail-disclaimer)。
        '<div class="desk-detail" id="desk-detail-panel" role="region" '
        'aria-label="デスクの詳細" hidden>'
        '<button type="button" class="desk-detail-close" id="desk-detail-close" '
        'aria-label="詳細を閉じる">×</button>'
        '<h2 id="desk-detail-title">-</h2>'
        '<p class="desk-detail-role" id="desk-detail-role">-</p>'
        '<dl class="desk-detail-facts">'
        '<div><dt>Pinterest</dt><dd>5件公開済み。最新投稿は48時間後を目安に反応を確認予定。</dd></div>'
        '<div><dt>note</dt><dd>AI Hive関連の記事3件公開済み（既存のnoteアカウントには、'
        'この他にも既存記事があります）。次の記事の下書き・見出し画像・Pinterest用画像まで'
        '準備済み。</dd></div>'
        '<div><dt>Threads</dt><dd>Difyを使った別管理の自動投稿を運用中（このアプリでは扱いません）。</dd></div>'
        '</dl>'
        '<p class="desk-detail-disclaimer" id="desk-detail-disclaimer">'
        '※ このデスクに個別に紐づく担当データは存在しないため、どのデスクを選んでも、'
        '柴犬社長が確認した現在の投稿運用状況を表示しています。'
        '実際にこのAIが個人で担当した記録ではありません。</p>'
        '</div>'
        # MISSION 083: 各担当の「実績表示／デモ表示」を一覧できる小さな
        # 一覧。運用司令室の本日の運用記録に該当があれば実績表示へ切り
        # 替わる(JS側でlocalStorageを読み取り専用で参照するだけで、書き
        # 込みは一切行わない)。
        '<div class="ai-office-record-mode-badge" id="office-record-mode-badge">'
        '読み込み中…（デモ表示）</div>'
        f'<ul class="space-status-list" id="office-status-list">{status_items}</ul>'
        '<p class="space-roster-note">本日の運用記録（運用司令室で入力）に該当する担当がいる'
        '場合は「実績表示」に切り替わります。記録がない担当は、通常の待機・確認・入力中の'
        '小さな動きのままです。</p>'
        # MISSION 028/051: クリック/Enter/Spaceでデスクを選択すると、上記の
        # 静的な現在状況を詳細パネルに表示する(DB・APIへのアクセスは
        # 一切行わない)。URLに #desk-<key> が付与されている場合は、該当
        # デスクを視覚的に強調表示し、フォーカスを移し、詳細を自動表示する
        # (社長室の「オフィスへ案内」からの遷移に対応)。
        '<script>'
        f'const deskInfo={{{desk_info_js}}};'
        'let lastFocusedDesk=null;'
        'const reduceMotion=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;'
        'function openDeskDetail(key){'
        'const info=deskInfo[key];'
        'if(!info)return;'
        'const panel=document.querySelector("#desk-detail-panel");'
        'document.querySelector("#desk-detail-title").textContent=info.name;'
        'document.querySelector("#desk-detail-role").textContent=info.role;'
        'panel.hidden=false;'
        'panel.dataset.openFor=key;'
        'const btn=document.querySelector("#desk-"+key);'
        'if(btn)btn.setAttribute("aria-expanded","true");'
        'lastFocusedDesk=btn;'
        'document.querySelector("#desk-detail-close").focus();'
        '}'
        'function closeDeskDetail(){'
        'const panel=document.querySelector("#desk-detail-panel");'
        'if(panel.hidden)return;'
        'const openKey=panel.dataset.openFor;'
        'if(openKey){'
        'const btn=document.querySelector("#desk-"+openKey);'
        'if(btn){btn.setAttribute("aria-expanded","false");btn.classList.remove("is-target");}'
        '}'
        'panel.hidden=true;'
        'if(lastFocusedDesk)lastFocusedDesk.focus();'
        '}'
        'document.querySelectorAll(".desk").forEach(btn=>{'
        'btn.addEventListener("click",()=>openDeskDetail(btn.dataset.key));'
        '});'
        'document.querySelector("#desk-detail-close").addEventListener("click",closeDeskDetail);'
        'document.addEventListener("keydown",e=>{'
        'if(e.key==="Escape")closeDeskDetail();'
        '});'
        'const hashMatch=location.hash.match(/^#desk-([a-z]+)$/);'
        'if(hashMatch&&deskInfo[hashMatch[1]]){'
        'const targetKey=hashMatch[1];'
        'const targetBtn=document.querySelector("#desk-"+targetKey);'
        'if(targetBtn){'
        'targetBtn.classList.add("is-target");'
        'targetBtn.scrollIntoView({behavior:reduceMotion?"auto":"smooth",block:"center"});'
        'openDeskDetail(targetKey);'
        '}'
        '}'
        '</script>'
        # MISSION 083: 里奈(楽天ROOM)・葵(数字記録)は、運用司令室の本日の
        # 運用記録に該当があれば「実績表示」へ切り替える(読み取り専用)。
        # 凛・蒼はどの記録種別・媒体にも直接対応しないため、常に通常の
        # 待機・確認の小さな動きのままになる(これは仕様どおりであり、
        # バグではない)。
        '<script>(function(){'
        + _ai_office_daily_record_reader_script() +
        'var WATCH={'
        '"room":{name:"里奈",demoText:"楽天ROOMの反応が良いジャンルを確認中"},'
        '"analytics":{name:"葵",demoText:"今週の数字を比較中"}'
        '};'
        'var records=spaceLoadTodayRecords();'
        'var byOwner={};'
        'records.forEach(function(rec){'
        'var owner=spaceOwnerForRecord(rec);'
        'if(!byOwner[owner])byOwner[owner]=rec;'
        '});'
        'var anyReal=false;'
        'Object.keys(WATCH).forEach(function(key){'
        'var cfg=WATCH[key];'
        'var rec=byOwner[key];'
        'var textEl=document.querySelector("#office-status-text-"+key);'
        'var tokenEl=document.querySelector("#space-token-office-"+key);'
        'var dotEl=document.querySelector("#space-nameplate-dot-office-"+key);'
        'if(rec){'
        'anyReal=true;'
        'if(textEl){'
        'var content=(rec.content||rec.metric||"").toString();'
        'textEl.textContent=content+"（実績表示）";'
        '}'
        'if(tokenEl){'
        'tokenEl.classList.remove("ai-office-floormap-token-waiting");'
        'tokenEl.classList.add("ai-office-floormap-token-working","is-working");'
        '}'
        'if(dotEl){'
        'dotEl.classList.remove("ai-office-nameplate-dot-waiting");'
        'dotEl.classList.add("ai-office-nameplate-dot-working");'
        '}'
        'var itemEl=document.querySelector("#office-status-item-"+key);'
        'if(itemEl)itemEl.classList.add("is-real");'
        '}'
        '});'
        'var badge=document.querySelector("#office-record-mode-badge");'
        'if(badge){'
        'if(anyReal){'
        'badge.textContent="本日：あなたが記録した運用実績を表示中（実績表示）";'
        'badge.classList.add("is-real");'
        '}else{'
        'badge.textContent="本日はまだ運用記録がありません（デモ表示）";'
        '}'
        '}'
        '})();</script>'
    )
    return _page(
        "office", "ライブオフィス",
        "デスクでの作業と小さな移動を眺められるフロアです。登場する社員は、"
        "AI Hive OSの架空キャラクターです。",
        scene,
    )

  @app.route("/office/break-room")
  def break_room():
    # MISSION 083: 休憩室を、AIオフィスに実在しない架空キャラクター(琴衣等)
    # から、実在12人のうち彩(連携担当)を中心にしたスペースへ変更した。
    # 美咲(Pinterest)・海(note)・里奈(楽天ROOM)・葵(分析)のうち、本日の
    # 運用記録がある担当を優先し、常に「彩+最大2人」だけを表示する(残り
    # 2人はこのページには登場しない=常時全員を置かない)。9秒おきに、
    # ソファの2つの枠に入る担当をJSで入れ替える(時間差で短時間だけ訪れる
    # 演出)。読み取り専用のlocalStorage参照のみで、外部通信・投稿・送信・
    # ログインは一切行わない。
    aya_pos = {"left": 60, "top": 34}
    candidates = [
        ("pinterest", "美咲", "Pinterestの反応、まだ様子見だね"),
        ("note", "海", "note の次の記事、もう準備できてるよ"),
        ("room", "里奈", "楽天ROOMの候補、あとで一緒に見てね"),
        ("analytics", "葵", "今週の数字、あとでまとめて共有するね"),
    ]
    aya_token = _ai_office_space_token("break", "aya", aya_pos, "waiting")

    def _slot_html(slot_num, key, name, demo_line):
      token = _ai_office_space_token("break", key, {"left": 0, "top": 0}, "waiting")
      return (
          f'<div class="sofa-guest sofa-guest-{slot_num}" data-slot="{slot_num}">'
          f'{token}'
          '<span class="sofa-chat">'
          f'<b id="break-slot-name-{slot_num}">{name}</b>'
          f'<span id="break-slot-text-{slot_num}">{demo_line}（デモ表示）</span>'
          '</span>'
          '</div>'
      )

    slot1_html = _slot_html(1, *candidates[0])
    slot2_html = _slot_html(2, *candidates[1])

    candidates_js = json.dumps(
        {
            key: {
                "name": name,
                "spritePos": _ai_office_sprite_position(
                    AI_OFFICE_STAFF_BY_KEY[key]["sprite"]
                ),
                "clipPath": AI_OFFICE_SPRITE_CLIP_PATHS[key],
                "idleClass": AI_OFFICE_IDLE_ANIMATION_BY_TYPE[
                    AI_OFFICE_STAFF_BY_KEY[key]["idle_type"]
                ],
                "demoLine": demo_line,
            }
            for key, name, demo_line in candidates
        },
        ensure_ascii=False,
    )
    pool_order_js = json.dumps([key for key, _n, _l in candidates], ensure_ascii=False)

    scene = (
        '<section class="scene break" aria-label="休憩室">'
        '<div class="label">BREAK ROOM<span>☕ 反応待ち・整理中</span>'
        '<span class="cast-badge">AI Hive OSの架空キャラクター</span></div>'
        '<div class="break-window" aria-hidden="true">☁</div>'
        '<div class="coffee">☕<b>COFFEE BAR</b><i></i><i></i><i></i></div>'
        f'{aya_token}'
        '<div class="sofa">'
        f'{slot1_html}{slot2_html}'
        '<small>ひと息ついたら、また確認へ戻ります</small></div>'
        '<div class="reading"><span aria-hidden="true">☕</span>'
        '<span>彩：部署間の連携状況を、ひと息ついて整理中</span></div>'
        '</section>'
        '<div class="ai-office-record-mode-badge" id="break-record-mode-badge">'
        '読み込み中…（デモ表示）</div>'
        '<p class="space-roster-note">彩を中心に、Pinterest・note・楽天ROOM・分析の担当のうち、'
        '本日の運用記録がある担当を優先して1〜2人だけ、時間差で短時間訪れます。'
        '外部への投稿・送信・ログインは行いません。</p>'
        '<script>(function(){'
        + _ai_office_daily_record_reader_script() +
        f'var CANDIDATES={candidates_js};'
        f'var POOL_ORDER={pool_order_js};'
        'var reduceMotion=window.matchMedia&&'
        'window.matchMedia("(prefers-reduced-motion: reduce)").matches;'
        'var records=spaceLoadTodayRecords();'
        'var realOwners={};'
        'var anyReal=false;'
        'records.forEach(function(rec){'
        'var owner=spaceOwnerForRecord(rec);'
        'if(CANDIDATES[owner]&&!realOwners[owner]){'
        'realOwners[owner]={content:(rec.content||rec.metric||"").toString()};'
        'anyReal=true;'
        '}'
        '});'
        'var badge=document.querySelector("#break-record-mode-badge");'
        'if(badge){'
        'if(anyReal){'
        'badge.textContent="本日：実績のある担当が休憩室に立ち寄っています（実績表示）";'
        'badge.classList.add("is-real");'
        '}else{'
        'badge.textContent="本日はまだ運用記録がありません（デモ表示）";'
        '}'
        '}'
        'var queue=POOL_ORDER.filter(function(k){return realOwners[k];})'
        '.concat(POOL_ORDER.filter(function(k){return !realOwners[k];}));'
        'function renderSlot(slotNum,key){'
        'var info=CANDIDATES[key];'
        'if(!info)return;'
        'var real=!!realOwners[key];'
        'var wrap=document.querySelector(\'.sofa-guest[data-slot="\'+slotNum+\'"]\');'
        'if(!wrap)return;'
        'var token=wrap.querySelector(".ai-office-floormap-token");'
        'var sprite=wrap.querySelector(".ai-office-floormap-sprite");'
        'sprite.style.backgroundPosition=info.spritePos;'
        'sprite.style.clipPath=info.clipPath;'
        'sprite.style.webkitClipPath=info.clipPath;'
        'token.setAttribute("aria-label",info.name);'
        'token.className="ai-office-floormap-token "+info.idleClass+'
        '" ai-office-floormap-token-"+(real?"working":"waiting");'
        'var dot=wrap.querySelector(".ai-office-nameplate-dot");'
        'dot.className="ai-office-nameplate-dot ai-office-nameplate-dot-"+(real?"working":"waiting");'
        'var nameEl=wrap.querySelector(\'.ai-office-nameplate span[id^="space-nameplate-name-"]\');'
        'if(nameEl)nameEl.textContent=info.name;'
        'var slotName=document.querySelector("#break-slot-name-"+slotNum);'
        'if(slotName)slotName.textContent=info.name;'
        'var slotText=document.querySelector("#break-slot-text-"+slotNum);'
        'if(slotText){'
        'slotText.textContent=real?'
        '("さっき「"+realOwners[key].content+"」を確認したよ。（実績表示）"):'
        '(info.demoLine+"（デモ表示）");'
        '}'
        '}'
        'var rotateIndex=0;'
        'function rotate(){'
        'renderSlot(1,queue[rotateIndex%queue.length]);'
        'renderSlot(2,queue[(rotateIndex+1)%queue.length]);'
        'rotateIndex++;'
        '}'
        'rotate();'
        'if(!reduceMotion){setInterval(rotate,9000);}'
        '})();</script>'
    )
    return _page(
        "break", "休憩室",
        "投稿の反応を待ちながら、次の作業を整理する時間を表すスペースです。"
        "登場する社員は、AI Hive OSの架空キャラクターです。",
        scene,
    )

  @app.route("/office/ceo-office")
  def ceo_office():
    # MISSION 051: 社長室(業務司令室)を、実データに乏しいwork_logs
    # (2026-09-01付けの3件、A8.net・美容サロン案件など現在と無関係な
    # 内容)から動的に算出する方式から、柴犬社長が確認した現在の実際の
    # 運用状況を示す静的な表示へ切り替えた。DB・APIへの書き込みは一切
    # 行わない(表示専用)。
    # MISSION 054: 2026年9月12日時点の実態(Pinterest 5件公開済み・note
    # 3件公開済み・次の記事下書き1本、Threadsのみ別管理のDify自動投稿)へ
    # 更新した。「AIが「なんか違う」ときに見直す3つ」は公開済みとなり、
    # 次に確認することは48時間後のPinterest反応確認である。
    # MISSION 053: 柴犬社長を「小さなアイコン」ではなく主役として見せる
    # ため、ceo-desk内の人物をCSS変数--s(DEPTH_STYLE内の.ceo-desk{--s:1.32})
    # で拡大し、背景にスポットライト状のグラデーションを敷く。あわせて、
    # 社長が実際に見ている想定のPinterest・note・Threadsの状況を、
    # 既存の.command-statsと同じ数値のまま、デスク脇の小さな画面
    # (.ceo-monitor)としても表示する(数値・事実は一切増やしていない)。
    # MISSION 083: 社長室に、柴犬社長(常駐)・悠(進行管理)・蓮(安全・承認
    # 確認)を基本配置し、伊織(品質確認)は蒼からの確認をときどき伝える
    # デモの来訪として表示する。本日の運用記録が、既存の対面報告ルート
    # (AI_OFFICE_REPORT_ROUTES)上で最終的に柴犬社長・悠・蓮のいずれかへ
    # 届く内容であれば、そのルートと同じ担当者・受け手・実際の記録内容で
    # 「誰が誰へ何を報告しているか」を表示する(実績表示)。該当する記録が
    # ない場合は、これまでどおりのデモの会話(バブル)のままになる。
    president_token = _ai_office_space_token(
        "ceo", "operations_lead", {"left": 50, "top": 66}, "waiting"
    )
    yu_token = _ai_office_space_token("ceo", "yu", {"left": 24, "top": 58}, "waiting")
    ren_token = _ai_office_space_token("ceo", "ren", {"left": 78, "top": 40}, "waiting")
    iori_token = _ai_office_space_token("ceo", "iori", {"left": 50, "top": 22}, "waiting")

    staff_names_json = json.dumps(
        {k: v["name"] for k, v in AI_OFFICE_STAFF_BY_KEY.items()}, ensure_ascii=False
    )
    route_receiver_json = json.dumps(
        {r["mover"]: r["receiver"] for r in AI_OFFICE_REPORT_ROUTES}, ensure_ascii=False
    )
    type_ack_json = json.dumps(AI_OFFICE_DAILY_RECORD_TYPE_ACK, ensure_ascii=False)

    scene = (
        '<section class="scene ceo" aria-label="柴犬社長の執務室"><div class="label">PRESIDENT’S OFFICE<span>承認デスク</span>'
        '<span class="cast-badge">AI Hive OSの主役キャラクター</span></div>'
        '<div class="ceo-window" aria-hidden="true">☀</div>'
        '<div class="ceo-spotlight" aria-hidden="true"></div>'
        '<div class="ceo-monitor" aria-hidden="true"><b>いま確認している状況</b>'
        '<div><span>Pinterest</span><span>5件公開</span></div>'
        '<div><span>note(今回)</span><span>3件公開</span></div>'
        '<div><span>Threads</span><span>Dify運用</span></div>'
        '</div>'
        '<div class="ceo-desk"><div class="approval">承認デスク</div></div>'
        f'{iori_token}{yu_token}{president_token}{ren_token}'
        '<div class="bubble" id="ceo-bubble">「Pinterestの反応、確認できた？次の投稿タイミングを一緒に考えよう。」</div></section>'
        '<div class="ai-office-record-mode-badge" id="ceo-record-mode-badge">'
        '読み込み中…（デモ表示）</div>'
        '<div class="ai-office-report-banner" id="ceo-report-banner">'
        '対面報告中の担当はまだいません（デモ表示）</div>'
        '<div class="ai-office-report-panel" id="ceo-report-panel">'
        '<p class="ai-office-report-panel-line" id="ceo-report-panel-mover">'
        '対面報告が始まると、ここに会話が表示されます（デモ表示）</p>'
        '<p class="ai-office-report-panel-line" id="ceo-report-panel-receiver"></p>'
        '</div>'
        '<p class="space-roster-note">実績がある日は、既存の対面報告ルールと同じ担当者が'
        '柴犬社長または悠・蓮へ報告します。伊織（品質確認）は、蒼からの確認をときどき'
        '伝えに顔を出す、デモの来訪として表示しています。</p>'
        '<section class="command" aria-label="業務司令室"><h2 class="sr-only">業務司令室</h2>'
        '<div class="command-stats">'
        '<div class="stat"><b>5件</b><span>Pinterest公開済み</span></div>'
        '<div class="stat"><b>3件</b><span>今回のnote公開済み</span></div>'
        '<div class="stat"><b>48時間</b><span>Pinterest反応確認の目安</span></div>'
        '</div>'
        '<p class="command-note">note次の記事の下書き・見出し画像・Pinterest用画像も準備済みです。'
        'Threadsのみ、Difyを使った別管理の自動投稿を運用していますが、'
        'この画面（このダッシュボード）からの投稿・ログイン・連携は一切行いません。'
        '<br>※noteの件数はAI Hive関連の記事のみを示しています。このnoteアカウントには、'
        'この他にも既存記事があります。</p>'
        '<div class="command-block"><h3>最新の仕事（最大3件）</h3>'
        '<ul>'
        '<li>Pinterest：「AIが「なんか違う」ときに見直す3つ」を公開済み</li>'
        '<li>note：「AIに聞いても「なんか違う」と感じる人へ」を公開済み</li>'
        '<li>公開済みのPinterest投稿の反応を確認中（48時間ほど様子を見る段階）</li>'
        '</ul></div>'
        '<div class="command-block"><h3>いま優先すること</h3>'
        '<p>48時間後を目安にPinterestの反応を確認すること</p></div>'
        '</section>'
        '<section class="chat" aria-labelledby="chat-title"><h2 id="chat-title">柴犬社長に話しかける</h2><p>進捗・相談・次の一歩を入力できます。内容は保存・送信されません。</p>'
        # MISSION 027/051: 業務サポート会話の4ボタン。「オフィスへ案内」
        # 以外の3つは、上記の静的な現在状況を柴犬社長の会話欄へ表示する
        # だけであり、DB・API・外部通信は一切使わない。「オフィスへ案内」
        # は/officeへの通常の同一オリジンリンク(固定href)であり、JSによる
        # リダイレクト先の書き換え等は行わない(安全な遷移)。
        '<div class="quick-actions" role="group" aria-label="よく使う質問">'
        '<button type="button" class="qa-btn" id="qa-today">今日の進捗</button>'
        '<button type="button" class="qa-btn" id="qa-priority">いま優先する仕事</button>'
        '<button type="button" class="qa-btn" id="qa-done">完了した仕事</button>'
        '<a class="qa-btn" id="qa-office" href="/office">オフィスへ案内</a>'
        '</div>'
        '<div id="log" class="log" aria-live="polite">'
        '<p class="boss">🐕 柴犬社長：Pinterestの反応、確認できた？次の投稿タイミングを一緒に考えよう。</p></div>'
        '<form id="chat-form" class="chat-form"><label class="sr-only" for="chat-input">柴犬社長へのメッセージ</label><input id="chat-input" maxlength="120" autocomplete="off" placeholder="例：今日の進捗を相談したい"><button>話しかける</button></form></section>'
        '<script>const f=document.querySelector("#chat-form");f.addEventListener("submit",e=>{e.preventDefault();const i=document.querySelector("#chat-input"),t=i.value.trim();if(!t)return;const l=document.querySelector("#log"),u=document.createElement("p"),r=document.createElement("p");u.className="you";u.textContent="あなた："+t;r.className="boss";r.textContent=/進捗|状況/.test(t)?"🐕 柴犬社長：次の一歩を小さく決めれば大丈夫。いま一番進めたいことからいこう。":/相談|困/.test(t)?"🐕 柴犬社長：急ぎ・大事・あとで考える、の3つに分けてみよう。":/ありがとう|おつかれ/.test(t)?"🐕 柴犬社長：こちらこそありがとう。ひと息ついて、また一緒に進めよう。":"🐕 柴犬社長：聞かせてくれてありがとう。今日は何を一番前に進めたい？";l.append(u,r);i.value="";l.scrollTop=l.scrollHeight;});</script>'
        '<script>'
        'function qaAppendBoss(text){'
        'const l=document.querySelector("#log");'
        'const r=document.createElement("p");'
        'r.className="boss";'
        'r.textContent=text;'
        'l.append(r);'
        'l.scrollTop=l.scrollHeight;'
        '}'
        'document.querySelector("#qa-today").addEventListener("click",()=>{'
        'qaAppendBoss("🐕 柴犬社長：Pinterestは5件、noteはAI Hive関連の記事が3件、'
        '公開済みだよ。次の記事下書きも準備できているよ。");'
        '});'
        'document.querySelector("#qa-priority").addEventListener("click",()=>{'
        'qaAppendBoss("🐕 柴犬社長：いま優先するのは、48時間後を目安にした'
        'Pinterestの反応確認だよ。");'
        '});'
        'document.querySelector("#qa-done").addEventListener("click",()=>{'
        'qaAppendBoss("🐕 柴犬社長：Pinterestは5件、noteはAI Hive関連の記事が3件、'
        '公開まで完了しているよ。");'
        '});'
        '</script>'
        # MISSION 083: 本日の運用記録を読み取り(読み取り専用)、既存の
        # 対面報告ルートで柴犬社長・悠・蓮のいずれかへ届く内容があれば、
        # 実際の担当者・受け手・記録内容で対面報告バナー・会話パネルを
        # 実績表示に切り替える。該当がなければデモ表示のままにする。
        '<script>(function(){'
        + _ai_office_daily_record_reader_script() +
        f'var STAFF_NAMES={staff_names_json};'
        f'var ROUTE_RECEIVER={route_receiver_json};'
        f'var TYPE_ACK={type_ack_json};'
        'var CEO_RECEIVERS={"yu":1,"ren":1,"operations_lead":1};'
        'var records=spaceLoadTodayRecords();'
        'var reportEntry=null;'
        'for(var i=0;i<records.length;i++){'
        'var rec=records[i];'
        'var owner=spaceOwnerForRecord(rec);'
        'var receiver=ROUTE_RECEIVER[owner];'
        'if(receiver&&CEO_RECEIVERS[receiver]){'
        'reportEntry={owner:owner,receiver:receiver,rec:rec};break;'
        '}'
        '}'
        'function setTokenReal(key){'
        'var token=document.querySelector("#space-token-ceo-"+key);'
        'var dot=document.querySelector("#space-nameplate-dot-ceo-"+key);'
        'if(token){'
        'token.classList.remove("ai-office-floormap-token-waiting");'
        'token.classList.add("ai-office-floormap-token-working","is-working");'
        '}'
        'if(dot){'
        'dot.classList.remove("ai-office-nameplate-dot-waiting");'
        'dot.classList.add("ai-office-nameplate-dot-working");'
        '}'
        '}'
        'var badge=document.querySelector("#ceo-record-mode-badge");'
        'var banner=document.querySelector("#ceo-report-banner");'
        'var panelMover=document.querySelector("#ceo-report-panel-mover");'
        'var panelReceiver=document.querySelector("#ceo-report-panel-receiver");'
        'if(reportEntry){'
        'var content=(reportEntry.rec.content||reportEntry.rec.metric||"").toString();'
        'var typeLabel=reportEntry.rec.type||"記録";'
        'var ownerName=STAFF_NAMES[reportEntry.owner]||reportEntry.owner;'
        'var receiverName=STAFF_NAMES[reportEntry.receiver]||"柴犬社長";'
        'var ack=TYPE_ACK[reportEntry.rec.type]||"確認しました";'
        'setTokenReal(reportEntry.receiver);'
        'if(reportEntry.owner==="yu"||reportEntry.owner==="ren")setTokenReal(reportEntry.owner);'
        'if(banner)banner.textContent=ownerName+"が"+receiverName+"へ報告中（実績表示）";'
        'if(panelMover)panelMover.textContent=ownerName+" → "+receiverName+"「"+typeLabel+"："+content+"」";'
        'if(panelReceiver)panelReceiver.textContent=receiverName+"「"+ack+"」";'
        'if(badge){'
        'badge.textContent="本日："+ownerName+"が"+receiverName+"へ報告しています（実績表示）";'
        'badge.classList.add("is-real");'
        '}'
        '}else if(badge){'
        'badge.textContent="本日はまだ運用記録がありません（デモ表示）";'
        '}'
        '})();</script>'
    )
    return _page(
        "ceo", "社長室",
        "柴犬社長と、Pinterest・noteの投稿準備や反応確認について気軽に話せる小さな部屋です。"
        "柴犬社長も、AI Hive OSの架空キャラクターです。",
        scene,
    )

  @app.route("/revenue")
  def revenue_board():
    scene = _render_revenue_scene(REVENUE_FOCUS)
    return _page(
        "revenue", "収益化ボード",
        "外部公開・営業送信の前に、収益化の方針と今週の優先行動を確認するための"
        "社内検討用ボードです。",
        scene,
        role_hint="週次でクリック・売上・成果報酬を確認する",
    )

  @app.route("/content-studio")
  def content_studio():
    scene = _render_content_studio_scene(
        CONTENT_STUDIO_THEME, CONTENT_STUDIO_PLANS, CONTENT_STUDIO_ROOM_LINK_POLICY,
        CONTENT_STUDIO_WRITING_STANDARDS_HEADING, CONTENT_STUDIO_WRITING_STANDARDS_INTRO,
        CONTENT_STUDIO_WRITING_STANDARDS,
        CONTENT_STUDIO_IMAGE_STANDARDS_HEADING, CONTENT_STUDIO_IMAGE_STANDARDS_INTRO,
        CONTENT_STUDIO_IMAGE_STANDARDS,
        CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_HEADING,
        CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_INTRO,
        CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES,
        CONTENT_STUDIO_NEXT_ARTICLE_RECOMMENDATION,
    )
    return _page(
        "content", "投稿企画工場",
        "Pinterest・noteへ展開する前に、1つのテーマから投稿案を確認する"
        "社内検討用ボードです。",
        scene,
        role_hint="下書きを作り、手動投稿後の完了を記録する",
    )

  @app.route("/content-studio/first-post")
  def content_studio_first_post():
    scene = _render_first_post_scene(FIRST_POST_PACKAGE)
    return _page(
        "content", "初回手動投稿パッケージ",
        "柴犬社長がPinterestへ手動投稿するための、最初の投稿素材一式を"
        "確認する画面です。",
        scene,
    )

  @app.route("/content-studio/weekly-plan")
  def content_studio_weekly_plan():
    scene = _render_weekly_plan_scene(
        WEEKLY_PLAN, WEEKLY_PLAN_STATUS_LABELS, WEEKLY_PLAN_POST_PUBLISH_CHECKS
    )
    return _page(
        "content", "7日間コンテンツ計画",
        "初回Pinterest投稿の反応を待つ間に、次の投稿候補と確認順を"
        "柴犬社長が見渡すための社内検討用の計画表です。",
        scene,
    )

  @app.route("/content-studio/desk-setup-post")
  def content_studio_desk_setup_post():
    scene = _render_desk_setup_scene(DESK_SETUP_POST_PACKAGE)
    return _page(
        "content", "デスク環境投稿パッケージ",
        "楽天ROOMでの紹介につなげる、デスク環境を整えるためのオリジナル"
        "Pinterest投稿素材を確認する画面です。",
        scene,
    )

  @app.route("/content-studio/publish-queue")
  def content_studio_publish_queue():
    scene = _render_publish_queue_scene(
        PUBLISH_QUEUE_POSTS, PUBLISH_QUEUE_ROOM_LINK_NOTE, PUBLISH_QUEUE_MANUAL_POST_NOTE,
        PUBLISH_QUEUE_STATUS_LABELS,
    )
    return _page(
        "content", "投稿キュー（社長承認待ち）",
        # MISSION 054修正: 5件中3件(メール下書き・スマホでのAI下書き・
        # 「なんか違う」投稿)はすでに柴犬社長が手動でPinterestへ投稿済み
        # (公開済み)であり、社長承認待ちのまま残っているのはデスク配線・
        # 周辺機器選びの2件。画像・タイトル・説明文・altテキスト・確認項目は、
        # 公開済みの投稿についても、実際に使用した内容の記録としてそのまま
        # 確認できる。
        "Pinterest投稿の準備・公開状況を、画像・タイトル・説明文・altテキスト・"
        "確認項目までまとめて確認する画面です。公開は社長がPinterestで手動実行します。"
        "公開済みの投稿についても、使用した内容の記録として表示しています。",
        scene,
    )

  @app.route("/content-studio/room-daily-candidates")
  def content_studio_room_daily_candidates():
    scene = _render_room_daily_candidates_scene()
    return _page(
        "content", "楽天ROOM 毎日の投稿候補（下書き）",
        "♡10以上の反応があるジャンルを参考に、1日あたり最大5件の投稿候補を"
        "下書きできる画面です。入力はブラウザ内にのみ保存され、楽天ROOMへの"
        "投稿・送信・ログインは一切行いません。",
        scene,
    )

  @app.route("/content-studio/note-daily-candidates")
  def content_studio_note_daily_candidates():
    scene = _render_note_daily_candidates_scene()
    return _page(
        "content", "note記事候補（毎日2本の下書き）",
        "AI初心者向けnoteのテーマから、1日あたり最大2本の記事候補を下書き"
        "できる画面です。入力はブラウザ内にのみ保存され、noteへの投稿・"
        "送信・ログインは一切行いません。",
        scene,
    )

  @app.route("/content-studio/note-first-article")
  def content_studio_note_first_article():
    scene = _render_note_article_scene(NOTE_FIRST_ARTICLE)
    # MISSION 043: 既存の初回記事(NOTE_FIRST_ARTICLE)の下に、Pinterestの新
    # テーマ「スマホでAIに下書きを頼む前に確認する3つ」と対応するnote記事
    # 下書きを追加する。既存の初回記事セクションの内容・構成は変更しない。
    second_draft_scene = _render_note_second_article_draft_scene(NOTE_SECOND_ARTICLE_DRAFT)
    # MISSION 049: さらにその下へ、「AIに聞いても『なんか違う』と感じる人へ」
    # note記事を追加する。既存の2件のセクションの内容・構成は変更しない。
    # MISSION 054: この記事は2026年9月12日までに公開済みとなったため、
    # 見出しを「下書き」から「公開済み」へ更新した。
    third_draft_scene = _render_note_third_article_draft_scene(NOTE_THIRD_ARTICLE_DRAFT)
    return _page(
        "content", "note初回記事",
        "柴犬社長がnoteへ手動で貼り付けて公開するための、初回記事・公開済み"
        "記事(AIとの会話の見直し)・記事下書き(スマホAI下書き)の見出し・本文・"
        "見出し画像・タグ候補を確認する画面です。",
        f'{scene}<h2 class="fp-section-title">次のnote記事下書き</h2>'
        f'{second_draft_scene}'
        '<h2 class="fp-section-title">公開済みのnote記事</h2>'
        f'{third_draft_scene}',
    )

  @app.route("/command-center")
  def command_center():
    scene = _render_command_center_scene()
    return _page(
        "command", "運用司令室",
        "資料室と担当チームのルールにもとづいて、今日の確認・承認待ちの"
        "状況・担当チーム状況・判断メモを見渡す画面です。入力はブラウザ内に"
        "のみ保存され、外部サービスへの投稿・送信・ログイン・削除は一切"
        "行いません。",
        scene,
        role_hint="確認・判断・運用記録を残す",
    )

  @app.route("/ai-office")
  def ai_office():
    scene = _render_ai_office_scene()
    return _page(
        "aioffice", "AIオフィス",
        "資料室と担当チームの役割・進行状況・活動をデモ表示で見える化する"
        "画面です。実データ接続・外部サービスへのアクセス・ログイン・投稿・"
        "送信・削除は一切行っていません。",
        scene,
        role_hint="今日の実績・社員の報告を見る",
    )
