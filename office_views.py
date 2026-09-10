"""AI Hive のライブオフィス画面。

すべてブラウザ内だけで描画する表示演出。DB/API/監査ログ/外部通信は使わず、
社長室の会話も保存されないローカルの定型リアクションである。
"""

import os

from flask import render_template_string


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
@media(max-width:760px){.revenue-grid{grid-template-columns:1fr}}
.room-prep-section{margin-top:24px}
.room-prep-section h2{font-size:16px;margin:0 0 10px}
.room-prep-notice{background:#101827;border:1px solid var(--blue);color:var(--ink);padding:12px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:12px}
.room-prep-notice b{color:var(--blue);display:block;margin-bottom:4px;font-size:13px}
.room-prep-notice ul{margin:6px 0 0;padding-left:18px}
.room-prep-pr-note{background:#3d3106;border:1px solid #fbbf24;color:#fde68a;padding:10px 14px;border-radius:12px;font-size:12px;line-height:1.6;margin-bottom:14px}
.room-prep-pr-note b{color:#fde68a}
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
.pq-status-badge{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px;background:#3d3106;color:#fbbf24;flex-shrink:0}
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
</style>
"""


STYLE = """
<style>
:root{--bg:#090c15;--panel:#121a2c;--edge:#293958;--ink:#f1f5f9;--sub:#a3b2c6;--blue:#38bdf8;--green:#34d399}*{box-sizing:border-box}body{margin:0;padding:20px;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.head,.tabs,main{max-width:1240px;margin:auto}.head{display:flex;justify-content:space-between;gap:12px;align-items:center;border-bottom:1px solid #202d47;padding-bottom:15px}.head h1{font-size:21px;margin:0 0 4px}.head p{margin:0;font-size:12px;color:var(--sub)}a,.chat-form button{color:var(--ink);text-decoration:none;font-size:12px;border:1px solid var(--edge);border-radius:9px;padding:8px 12px;background:#142039}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px;margin-bottom:15px}.tabs a.active,.tabs a:hover{border-color:var(--blue);color:var(--blue);background:#1b2d4b}.scene{position:relative;min-height:590px;overflow:hidden;border:1px solid var(--edge);border-radius:20px;background:#142038;box-shadow:0 18px 45px #0007}.label{position:absolute;top:16px;left:18px;font-size:12px;font-weight:800;letter-spacing:.08em;z-index:6}.label span{color:var(--green);font-size:10px;margin-left:8px}.figure{display:block;width:74px;height:99px;background:url('/static/images/office-avatars-v1.png?v=2') no-repeat;background-size:400% 200%;filter:drop-shadow(0 7px 7px #0008)}.avatar-president{background-position:0 0}.avatar-ayaka{background-position:33.333% 0}.avatar-kotoe{background-position:66.666% 0}.avatar-aoi{background-position:100% 0}.avatar-misaki{background-position:0 100%}.avatar-umi{background-position:33.333% 100%}.avatar-minato{background-position:66.666% 100%}.avatar-ito{background-position:100% 100%}.office{background:linear-gradient(#263b5b 0 44%,#c18c5e 44% 46%,#233247 46%)}.office:after{content:"";position:absolute;inset:46% 0 0;background:repeating-linear-gradient(90deg,#ffffff08 0 2px,transparent 2px 85px),linear-gradient(135deg,#28394e,#172235);z-index:0}.windows{position:absolute;left:9%;right:10%;top:11%;height:145px;display:flex;gap:15px}.windows i{flex:1;border:8px solid #354861;background:linear-gradient(#56c8ed 0 60%,#c4f3e9 60%);box-shadow:inset 0 0 0 3px #152237}.door{position:absolute;right:6%;top:27%;width:88px;height:180px;border:5px solid #3e2d25;border-radius:8px 8px 0 0;background:#784b38;text-align:center;padding-top:50px;z-index:3}.door b{display:block;font-size:24px}.door small{font-size:9px}.plant{position:absolute;bottom:20%;left:4%;font-size:48px;z-index:4}.desk{position:absolute;width:145px;height:165px;text-align:center;z-index:3}.desk .figure{position:absolute;left:36px;bottom:29px;animation:work 3.2s ease-in-out infinite}.desk:after{content:"";position:absolute;left:0;right:0;bottom:23px;height:44px;background:linear-gradient(#d8ad80,#7f4e32);border-top:5px solid #ffe0b3;border-radius:5px 5px 11px 11px;z-index:2}.desk:before{content:attr(data-screen);position:absolute;left:49px;bottom:66px;width:44px;height:32px;line-height:25px;color:#eaffff;background:#286da0;border:4px solid #111d2e;border-radius:5px;z-index:4;font:bold 13px monospace}.desk b,.desk em{position:absolute;left:0;right:0;bottom:2px;z-index:5;font-size:11px}.desk em{bottom:-13px;color:#b8c8da;font-size:9px;font-style:normal}.d1{left:7%;top:41%}.d2{left:27%;top:41%}.d3{left:47%;top:41%}.d4{left:67%;top:41%}.d5{left:19%;top:70%}.d6{left:59%;top:70%}.route{position:absolute;right:9%;bottom:25%;width:48%;border-top:4px dashed #72d8d8aa;border-radius:50%;transform:rotate(-8deg);z-index:1}.walker{position:absolute;left:7%;bottom:16%;display:flex;gap:4px;align-items:end;z-index:5;animation:to-break 17s ease-in-out infinite}.walker .figure{animation:step .42s infinite alternate}.walker span{font-size:10px;padding:4px 7px;background:#101b2edb;border:1px solid #38587c;border-radius:8px;white-space:nowrap}.live-board{position:absolute;left:18px;top:58px;z-index:6;max-width:340px;border:1px solid #4a7595;background:#0d192bdc;border-radius:10px;padding:8px 10px;font-size:11px;line-height:1.45;color:#dceafa}.live-board b{color:var(--green);margin-right:6px}.live-board span{color:#a8c0d7}.note{margin-top:12px;padding:12px 14px;border:1px solid var(--edge);background:#101827;border-radius:12px;color:var(--sub);font-size:12px}.note b{color:var(--ink);margin:0 7px}.dot{display:inline-block;width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 1.8s infinite}.break{background:linear-gradient(#f5cc88 0 46%,#a56d51 46% 48%,#362831 48%)}.break .label{color:#34262c}.break .label span{color:#1e775e}.break-window{position:absolute;left:9%;top:12%;width:245px;height:160px;border:9px solid #fff0ca;background:linear-gradient(#5cd0ef,#c7f3db);font-size:55px;padding:22px 35px}.coffee{position:absolute;right:9%;bottom:19%;width:235px;height:145px;background:#84523a;border:6px solid #5c3729;border-radius:12px 12px 0 0;text-align:center;padding:18px;color:#fff2d7;z-index:2}.coffee b{display:block;font-size:11px;letter-spacing:.1em}.coffee i{display:inline-block;width:22px;height:22px;background:#fadf97;border-radius:50%;margin:11px 7px}.sofa{position:absolute;left:10%;bottom:18%;width:410px;height:175px;z-index:2}.sofa:before,.sofa:after{content:"";position:absolute;left:0;right:0;background:#326b91;border:7px solid #23506d}.sofa:before{top:25px;height:106px;border-radius:45px 45px 15px 15px}.sofa:after{bottom:25px;height:62px;border-radius:12px}.sofa .figure{position:absolute;bottom:62px;z-index:3}.sofa .figure:nth-of-type(1){left:95px}.sofa .figure:nth-of-type(3){left:240px;animation:work 2.8s infinite}.sofa small{position:absolute;bottom:0;left:0;right:0;text-align:center;color:#fff8e9;font-size:10px}.break-walker{position:absolute;right:37%;bottom:17%;z-index:4;animation:coffee-walk 14s ease-in-out infinite}.break-walker .figure{animation:step .4s infinite alternate}.break-walker small{display:block;text-align:center;color:#2f252b;font-weight:bold}.reading{position:absolute;left:6%;bottom:8%;display:flex;gap:7px;align-items:end;z-index:2}.reading span{font-size:10px;background:#fff0c9;color:#34272b;padding:5px;border-radius:6px}.ceo{min-height:400px;background:linear-gradient(#2a3d58 0 47%,#94644c 47% 49%,#2f2730 49%)}.ceo-window{position:absolute;left:9%;top:14%;width:290px;height:180px;border:9px solid #d0ab80;background:linear-gradient(#75d3ec,#e9f7c6);font-size:45px;text-align:right;padding:16px 20px}.ceo-desk{position:absolute;left:50%;bottom:8%;transform:translateX(-50%);width:350px;height:220px;z-index:2}.ceo-desk .figure{position:absolute;left:138px;bottom:38px;z-index:2;animation:work 3s infinite}.ceo-desk:after{content:"";position:absolute;left:0;right:0;bottom:0;height:82px;background:linear-gradient(#b98760,#6c422f);border:7px solid #4b3028;border-radius:10px 10px 0 0;z-index:3}.approval{position:absolute;right:26px;bottom:99px;z-index:4;background:#fff1c5;color:#513923;padding:8px 12px;font-size:11px;border-radius:5px;transform:rotate(4deg)}.approval b{font-size:20px}.bubble{position:absolute;right:6%;bottom:16%;max-width:280px;padding:13px;background:#0b1528e8;border:1px solid #4b6991;border-radius:13px;font-size:12px;line-height:1.6}.chat{margin-top:14px;background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px}.chat h2{font-size:15px;margin:0 0 5px}.chat>p{margin:0;color:var(--sub);font-size:11px}.log{height:118px;margin:12px 0;padding:10px;overflow:auto;background:#0b1120;border:1px solid #253651;border-radius:10px;font-size:12px}.log p{padding:7px 9px;margin:0 0 8px;width:fit-content;max-width:87%;border-radius:8px;line-height:1.45}.boss{background:#17263d}.you{background:#29436c;margin-left:auto!important}.chat-form{display:flex;gap:8px}.chat-form input{min-width:0;flex:1;padding:10px;background:#0b1120;color:#fff;border:1px solid #385072;border-radius:9px}.chat-form button{background:#147fac;border:0;font-weight:700;cursor:pointer}@keyframes work{50%{transform:translateY(-4px)}}@keyframes step{to{transform:translateY(-5px) rotate(2deg)}}@keyframes to-break{0%,25%{left:7%;bottom:16%}45%,62%{left:78%;bottom:30%}79%,100%{left:7%;bottom:16%}}@keyframes coffee-walk{0%,25%{right:37%;bottom:17%}44%,63%{right:11%;bottom:22%}80%,100%{right:37%;bottom:17%}}@keyframes pulse{50%{opacity:.3}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}}@media(max-width:760px){body{padding:12px}.head{align-items:flex-start;flex-direction:column}.scene{min-height:720px}.desk{transform:scale(.72);transform-origin:top left}.d1{left:3%;top:38%}.d2{left:37%;top:38%}.d3{left:3%;top:64%}.d4{left:37%;top:64%}.d5,.d6{display:none}.break-window{transform:scale(.7);transform-origin:top left}.coffee{transform:scale(.7);transform-origin:bottom right}.sofa{transform:scale(.7);transform-origin:bottom left}.ceo-window{transform:scale(.7);transform-origin:top left}.bubble{bottom:8%;right:3%;max-width:210px}.ceo-desk{transform:translateX(-50%) scale(.8);transform-origin:bottom center}}
</style>
"""


def _page(room, title, lead, scene):
  tabs = [
      ("office", "/office", "オフィス"),
      ("break", "/office/break-room", "休憩室"),
      ("ceo", "/office/ceo-office", "社長室"),
      ("revenue", "/revenue", "収益化ボード"),
      ("content", "/content-studio", "投稿企画工場"),
  ]
  nav = "".join(
      f'<a class="{"active" if key == room else ""}" href="{href}" '
      f'aria-current="{"page" if key == room else "false"}">{name}</a>'
      for key, href, name in tabs
  )
  return render_template_string(
      f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" '
      f'content="width=device-width,initial-scale=1"><title>{title} | AI Hive</title>{STYLE}{LIVE_DATA_STYLE}'
      f'</head><body><header class="head"><div><h1>{title}</h1><p>{lead}</p></div>'
      f'<a href="/">← ダッシュボードへ戻る</a></header><nav class="tabs" aria-label="部屋を選ぶ">{nav}'
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
        "初回Pinterest投稿からの流入育成",
        "楽天ROOMでの手動カテゴリ紹介",
    ],
    "price_note": "楽天ROOMでの紹介はすべて手動登録の想定であり、金額・成果はすべて未確定の"
                  "「たたき台」です。確定した収益・契約内容ではありません。",
    "price_tiers": [
        ("Pinterest経由の流入", "検討中"),
        ("楽天ROOMでの手動紹介", "検討中"),
        ("noteでの信頼構築", "検討中"),
    ],
    "pipeline_stages": ["テーマ選定", "投稿確認", "ROOM準備", "手動登録"],
    "weekly_priorities": [
        "投稿企画工場のテーマ整理",
        "初回Pinterest投稿の実績確認",
        "ROOM投稿準備の下ごしらえ",
    ],
}


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
      '<b>社内の企画たたき台です。</b>'
      'ここに表示する内容は検討中の案であり、外部への送信・公開、'
      '自動的な実行は一切行われません。'
      '</div>'
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
      '<div class="revenue-card"><h3>収益の入り口候補（すべて未定・検討中）</h3>'
      f'<p class="revenue-price-note">{focus["price_note"]}</p>'
      f'<ul class="revenue-price-tiers">{price_items}</ul></div>'
      '<div class="revenue-card"><h3>ROOM登録までの段階</h3>'
      f'<ol class="revenue-pipeline">{pipeline_items}</ol></div>'
      '<div class="revenue-card"><h3>今週の優先行動</h3>'
      f'<ol class="revenue-priorities">{priority_items}</ol></div>'
      '</div>'
      + _render_room_prep_section(ROOM_PREP_CATEGORIES, ROOM_PREP_STATUS_LABELS) +
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


def _render_content_studio_scene(theme, plans, room_link_policy):
  """投稿企画工場のカード群を、CONTENT_STUDIO_PLANSのデータから組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・外部通信への
  アクセスは一切行わない。Pinterest・noteの2媒体だけを扱い、各テーマに
  つき「Pinterest用の切り口」「note用の切り口」「楽天ROOMリンクの扱い」
  の3項目だけを簡潔に示す。
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
  return (
      '<section class="content-studio" aria-label="投稿企画工場">'
      '<div class="revenue-notice">'
      '<b>この画面は投稿企画の手動準備用です。</b>'
      'この画面は投稿企画の手動準備用であり、外部サービスへの投稿・送信・連携は'
      '行わない。'
      '</div>'
      f'<p class="cs-theme">対象テーマ：<b>{theme}</b></p>'
      f'<div class="cs-room-policy"><b>楽天ROOMリンクについて。</b>{room_link_policy}</div>'
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
      '<a class="cs-first-post-link" href="/revenue#room-prep">'
      '→ 楽天ROOM投稿準備を見る</a>'
      + plan_cards +
      '<p class="cs-footnote">この画面はlocalhost限定で表示される社内検討用の'
      '資料です。SNS投稿・note投稿・広告出稿・営業送信は行われません。</p>'
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
        "status": "draft",
        "checks": ["断定的な表現になっていないか", "初回投稿の内容と矛盾していないか"],
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
        "day": 6,
        "theme": "デスク周りを整える便利ガジェット",
        "medium": "note",
        "purpose": "紹介する商品ジャンルについて整理して解説する",
        "status": "review",
        "checks": ["紹介する商品ジャンルの選定基準が整理されているか（要確認事項）"],
    },
    {
        "day": 7,
        "theme": "スマホ・PC作業を快適にする周辺機器",
        "medium": "Pinterest",
        "purpose": "保存・検索からの流入",
        "status": "review",
        "checks": ["対象ガジェットの切り口が絞り込まれているか（要確認事項）"],
    },
]

WEEKLY_PLAN_STATUS_LABELS = {
    "published": "公開済み（初回投稿）",
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
      'ここに表示する7日分の内容はすべて下書き・計画段階であり、予約投稿・'
      '自動投稿は一切行われません。既存の投稿企画（投稿企画工場・初回手動'
      '投稿パッケージ）だけを使って構成しています。</div>'
      '<div class="wp-callout"><b>公開後24時間で確認すること（1日目・初回投稿）</b>'
      f'<ul>{publish_checks_html}</ul></div>'
      '<a class="cs-first-post-link" href="/revenue#room-prep">'
      '→ 楽天ROOM投稿準備を見る</a>'
      + "".join(day_cards) +
      '<p class="wp-footnote">初回投稿の実績（表示回数・保存数・クリック数など）を柴犬社長が'
      '確認したうえで、2日目以降のどの内容をどこまで自動化するかを判断します。'
      'この画面はlocalhost限定で表示される社内検討用の資料であり、'
      'SNS投稿・予約投稿・広告出稿・営業送信は行われません。</p>'
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
    {
        "audience_problem": "デスク周りが散らかりがちで集中しづらい人向け",
        "pinterest_theme_idea": "作業がはかどるデスク周りグッズまとめ",
        "genre_ideas": ["モニターアーム", "デスクライト", "ケーブル収納グッズ"],
        "room_manual_checks": [
            "紹介する商品ジャンルの選定基準が整理されているか確認する（要確認事項）",
            "掲載できる画像がROOM上に用意されているか確認する（画像の保存・加工はしない）",
        ],
        "pre_write_checks": [
            "実際に試用していない前提で、断定的な効果を書いていないか",
            "誇大表現・未確認の実績を書いていないか",
            "商品提供・クーポン・広告主とのやり取りがある場合、PR表記が必要か確認したか",
        ],
        "status": "planning",
    },
    {
        "audience_problem": "外出先でもスマホ・PC作業を快適にしたい人向け",
        "pinterest_theme_idea": "スマホ・PC作業がはかどる周辺機器ジャンルまとめ",
        "genre_ideas": ["USB-Cハブ", "ワイヤレス充電スタンド", "ノートPCスタンド"],
        "room_manual_checks": [
            "対象ガジェットの切り口が絞り込まれているか確認する（要確認事項）",
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


def _render_room_prep_section(categories, status_labels):
  """楽天ROOM投稿準備のカード群を、ROOM_PREP_CATEGORIESのデータから組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・楽天API・
  外部通信へのアクセスは一切行わない。楽天市場の商品画像は保存・加工・
  表示せず、使用する画像は既存のローカル素材のみである。
  """
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
      + "".join(category_cards) +
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
# 3件の投稿候補を「社長承認待ち」としてまとめて表示する。各投稿の画像は
# 文字と図形のみで構成し(商品写真・楽天市場画像・商品ロゴ・外部素材は
# 使わない)、商品名・価格・在庫・ランキング・性能・成果予測は一切表示
# しない。楽天ROOMリンク欄は常に空欄で、「社長が手動で貼る」旨のみを
# 表示する(URLの取得・保存・外部連携は行わない)。公開は社長がPinterestで
# 手動実行する運用であることを、各カードに明記する。将来投稿内容を
# 差し替える場合は、このデータ構造(PUBLISH_QUEUE_POSTS)を編集するだけで
# よい。
PUBLISH_QUEUE_POSTS = [
    {
        "id": "email-draft-3points",
        "status": "社長承認待ち",
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
        "status": "社長承認待ち",
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
        "status": "社長承認待ち",
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
        "status": "社長承認待ち",
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


def _render_publish_queue_scene(posts, room_link_note, manual_post_note):
  """Pinterest向け・手動承認つき投稿キューのHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・楽天API・外部
  通信への アクセスは一切行わない。楽天ROOMリンク欄は常に空欄で表示し、
  URLの取得・保存・外部連携は行わない。コピー用ボタンはクライアント側JS
  のみで完結し、クリップボード操作が失敗しても例外を伝播させず、安全な
  フォールバック表示にする。
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
        f'<span class="pq-status-badge">{post["status"]}</span>'
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
    "alt_text_draft": (
        "スマホでAIに下書きを頼む前に確認する3つ、というテーマのnote記事用altテキスト案。木目の"
        "デスクにスマートフォン・タブレット・折りたたみキーボードが置かれた写真のイメージを想定し、"
        "記事の3項目（使う端末・文字入力の方法・読み返す場所）を要約した説明文。実際の画像は、この"
        "記事下書きでは新規作成していません。"
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


def register_office_views(app):
  """Flaskアプリへ表示専用ルートを登録する。"""
  @app.route("/office")
  def office():
    desks = (
        ("misaki", "美咲", "WEBディレクター", "進行を整理中", "&lt;/&gt;"),
        ("umi", "海", "UIデザイナー", "デザイン調整中", "✦"),
        ("minato", "湊", "フロントエンド", "実装中", "▍_"),
        ("ito", "伊藤", "QA・SEO", "テスト中", "✓"),
        ("kotoe", "琴衣", "運用チーム", "確認中", "▣"),
        ("aoi", "蒼", "運用チーム", "投稿準備中", "●"),
    )
    # MISSION 025/028: 各デスクをクリック・キーボード操作可能な<button>に
    # している(<button>はEnter/Spaceでの活性化を標準で備えるため、
    # キーボード操作対応を別途実装する必要がない)。<em>と状態チップの
    # IDは、後続のスクリプトから実データ(/api/logs)で書き換えるために
    # 使う。IDが無い状態(=JS未実行/フェッチ失敗)でも、元の役割文言が
    # そのまま表示され続けるフォールバックとなる。
    desk_html = "".join(
        f'<button type="button" class="desk d{i + 1}" id="desk-{key}" data-key="{key}" '
        f'data-screen="{screen}" aria-haspopup="true" aria-expanded="false" '
        f'aria-controls="desk-detail-panel">{figure(key, name)}<b>{name}</b>'
        f'<em id="desk-task-{key}">{task}</em>'
        f'<i class="status-chip status-pending" id="desk-status-{key}" aria-hidden="true"></i></button>'
        for i, (key, name, role, task, screen) in enumerate(desks)
    )
    desk_keys_js = ",".join(f'"{key}"' for key, _n, _r, _t, _s in desks)
    desk_info_js = ",".join(
        f'"{key}":{{name:"{name}",role:"{role}"}}' for key, name, role, _t, _s in desks
    )
    scene = (
        '<section class="scene office" aria-label="作業フロア"><div class="label">WEB制作・運用フロア<span>● LIVE</span></div>'
        '<div class="live-board" id="office-live-status" aria-live="polite"><b>実データを確認中</b><span>作業ログを読み込んでいます…</span></div>'
        '<div class="windows" aria-hidden="true"><i></i><i></i><i></i></div><div class="plant" aria-hidden="true">🪴</div>'
        '<div class="door"><b>☕</b><small>BREAK ROOM</small></div><div class="route" aria-hidden="true"></div>' + desk_html +
        f'<div class="walker">{figure("ayaka", "彩・休憩へ移動中")}<span>彩・休憩へ</span></div></section>'
        # MISSION 028: デスクの詳細パネル。通常のドキュメントフロー内に置き、
        # クリック/キーボードで選択したデスクの情報をJSで書き込んで表示する
        # (初期状態はhiddenで、DB/APIへの副作用は一切ない)。個別の担当データが
        # 実在しない旨の注記(desk-detail-disclaimer)を必ず含める。
        '<div class="desk-detail" id="desk-detail-panel" role="region" '
        'aria-label="デスクの詳細" hidden>'
        '<button type="button" class="desk-detail-close" id="desk-detail-close" '
        'aria-label="詳細を閉じる">×</button>'
        '<h2 id="desk-detail-title">-</h2>'
        '<p class="desk-detail-role" id="desk-detail-role">-</p>'
        '<dl class="desk-detail-facts">'
        '<div><dt>現在の状態</dt><dd id="desk-detail-status">-</dd></div>'
        '<div><dt>最新の作業内容</dt><dd id="desk-detail-task">-</dd></div>'
        '<div><dt>更新時刻</dt><dd id="desk-detail-time">-</dd></div>'
        '</dl>'
        '<p class="desk-detail-disclaimer" id="desk-detail-disclaimer">'
        '※ このデスク専用に紐づく個別の担当データは存在しないため、既存の'
        '作業ログを順番に表示している演出です。実際にこのAIが個人で担当した'
        '記録ではありません。</p>'
        '</div>'
        # MISSION 025/028: 既存 GET /api/logs (読み取り専用・work_logs) のみを
        # 参照する。書き込み系メソッド・他のAPIエンドポイントは一切呼び出さ
        # ない。実データが6デスク分に満たない場合は、既存ログを巡回して割り
        # 当てる(件数が足りない分は元の役割文言のまま=フォールバック)。
        # 「完了」以外の状態はすべて進行中扱いとして安全側に倒す。
        # デスクをクリック/Enter/Spaceで選択すると、その時点で取得済みの
        # 実データを詳細パネルへ表示する(取得前・失敗時は安全なフォール
        # バック文言)。URLに #desk-<key> が付与されている場合は、該当デスク
        # を視覚的に強調表示し、フォーカスを移し、詳細を自動表示する
        # (社長室の「オフィスへ案内」からの遷移に対応)。
        '<script>'
        f'const deskInfo={{{desk_info_js}}};'
        'let deskData={};'
        'let lastFocusedDesk=null;'
        'const reduceMotion=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;'
        'function fmtTime(ts){return ts?String(ts):"―";}'
        'function openDeskDetail(key){'
        'const info=deskInfo[key];'
        'if(!info)return;'
        'const panel=document.querySelector("#desk-detail-panel");'
        'document.querySelector("#desk-detail-title").textContent=info.name;'
        'document.querySelector("#desk-detail-role").textContent=info.role;'
        'const data=deskData[key];'
        'if(data){'
        'document.querySelector("#desk-detail-status").textContent=data.status;'
        'document.querySelector("#desk-detail-task").textContent=data.theme;'
        'document.querySelector("#desk-detail-time").textContent=fmtTime(data.time);'
        '}else{'
        'document.querySelector("#desk-detail-status").textContent="データを取得できませんでした";'
        'document.querySelector("#desk-detail-task").textContent="データを取得できませんでした";'
        'document.querySelector("#desk-detail-time").textContent="―";'
        '}'
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
        'fetch("/api/logs").then(r=>r.ok?r.json():Promise.reject()).then(logs=>{'
        'const board=document.querySelector("#office-live-status");'
        'if(!logs.length){board.innerHTML="<b>実データ</b><span>表示できる作業ログはまだありません。</span>";}'
        'else{const latest=logs[0];board.innerHTML="<b>実データ</b><span>最新ログ："+latest[2]+"（"+latest[4]+"）</span>";}'
        f'const keys=[{desk_keys_js}];'
        'keys.forEach((key,i)=>{'
        'const em=document.querySelector("#desk-task-"+key);'
        'const chip=document.querySelector("#desk-status-"+key);'
        'if(!logs.length){if(chip)chip.className="status-chip status-none";deskData[key]=null;return;}'
        'const log=logs[i%logs.length];'
        'const done=log[4]==="完了";'
        'deskData[key]={theme:log[2],status:log[4],time:log[1]};'
        'if(!em||!chip)return;'
        'const theme=log[2].length>8?log[2].slice(0,8)+"…":log[2];'
        'em.textContent=theme+"（"+log[4]+"）";'
        'em.title=log[2]+"（"+log[4]+"）";'
        'chip.className="status-chip "+(done?"status-done":"status-progress");'
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
        '}).catch(()=>{'
        'document.querySelector("#office-live-status").innerHTML="<b>実データ</b><span>作業ログを取得できませんでした。</span>";'
        'document.querySelectorAll(".status-chip").forEach(c=>{c.className="status-chip status-none";});'
        f'const keys=[{desk_keys_js}];'
        'keys.forEach(key=>{deskData[key]=null;});'
        '});'
        '</script>'
        '<p class="note"><span class="dot"></span><b>いまの様子</b>彩が経理デスクから休憩室へ向かい、しばらくするとフロアへ戻ります。</p>'
    )
    return _page("office", "ライブオフィス", "デスクでの作業と小さな移動を眺められるフロアです。", scene)

  @app.route("/office/break-room")
  def break_room():
    scene = (
        '<section class="scene break" aria-label="休憩室"><div class="label">BREAK ROOM<span>☕ ひと息つき中</span></div>'
        '<div class="break-window" aria-hidden="true">☁</div><div class="coffee">☕<b>COFFEE BAR</b><i></i><i></i><i></i></div>'
        f'<div class="sofa">{figure("kotoe", "琴衣・休憩中")}{figure("umi", "海・休憩中")}<small>琴衣と海がひと息</small></div>'
        f'<div class="break-walker">{figure("aoi", "蒼・ドリンクを取りに移動中")}<small>蒼</small></div>'
        f'<div class="reading">{figure("ito", "伊藤・チェックリストを確認中")}<span>チェックリストを確認中</span></div></section>'
        # MISSION 028: 「休憩理由」「戻る予定」に相当する文言(誰が何を
        # している/どこへ向かっているという表現)は、いずれも実データに
        # 基づかない画面演出であることを明記する。
        '<p class="note"><span class="dot"></span><b>小休憩中</b>移動・休憩理由・戻る予定はすべて画面演出であり、'
        '実データに基づくものではありません。勤怠・タスク・データは変更されません。</p>'
    )
    return _page("break", "休憩室", "作業の合間に、メンバーが順番に小休憩するスペースです。", scene)

  @app.route("/office/ceo-office")
  def ceo_office():
    scene = (
        '<section class="scene ceo" aria-label="柴犬社長の執務室"><div class="label">PRESIDENT’S OFFICE<span>承認デスク</span></div>'
        '<div class="ceo-window" aria-hidden="true">☀</div>'
        f'<div class="ceo-desk">{figure("president", "柴犬社長")}'
        '<div class="approval">承認デスク</div></div>'
        '<div class="bubble">「おつかれさま。今日は何を一緒に整理しようか？」</div></section>'
        # MISSION 026: 社長室を「業務司令室」として拡張し、今日の作業件数・
        # 完了件数・進行中件数、最新の仕事(最大3件)、いま優先することを、
        # 既存 GET /api/logs (読み取り専用・work_logs) だけから表示する。
        # 「完了」以外はすべて「進行中」として扱う判定基準は、ライブオフィス
        # の各デスク(office())の判定基準(log[4]==="完了")と完全に一致させて
        # おり、フロア側の表示と矛盾しないようにしている。書き込みは一切
        # 行わない。「今日」はこのページを開いたブラウザのローカル日付で
        # 判定する(サーバー側の状態は変更しない)。
        '<section class="command" aria-label="業務司令室"><h2 class="sr-only">業務司令室</h2>'
        '<div class="command-stats" aria-live="polite">'
        '<div class="stat"><b id="ceo-today-count">-</b><span>今日の作業</span></div>'
        '<div class="stat"><b id="ceo-today-done">-</b><span>完了</span></div>'
        '<div class="stat"><b id="ceo-today-progress">-</b><span>進行中</span></div>'
        '</div>'
        '<p class="command-note" id="ceo-total-note">記録全体を確認中…</p>'
        '<div class="command-block"><h3>最新の仕事（最大3件）</h3>'
        '<ul id="ceo-recent-list" aria-live="polite"><li>読み込んでいます…</li></ul></div>'
        '<div class="command-block"><h3>いま優先すること</h3>'
        '<p id="ceo-priority" aria-live="polite">確認しています…</p></div>'
        '</section>'
        # MISSION 028: 「オフィスへ案内」のリンク先を、実データ上「いま
        # 優先すること」に対応するデスクのハッシュ(#desk-<key>)へ動的に
        # 差し替える。deskKeysの並び順はoffice()側のdesksタプルと同一に
        # しており、両画面のデスク割り当て(logs[i % logs.length])が
        # 一致するようにしている。あくまで通常の<a href>属性を書き換える
        # だけであり、location.href等によるJS遷移は行わない。
        '<script>const deskKeys=["misaki","umi","minato","ito","kotoe","aoi"];'
        'fetch("/api/logs").then(r=>r.ok?r.json():Promise.reject()).then(logs=>{'
        'const isDone=l=>l[4]==="完了";'
        'const todayStr=new Date().toISOString().slice(0,10);'
        'const todayLogs=logs.filter(l=>String(l[1]).slice(0,10)===todayStr);'
        'const todayDone=todayLogs.filter(isDone).length;'
        'const todayProgress=todayLogs.length-todayDone;'
        'const totalDone=logs.filter(isDone).length;'
        'document.querySelector("#ceo-today-count").textContent=todayLogs.length;'
        'document.querySelector("#ceo-today-done").textContent=todayDone;'
        'document.querySelector("#ceo-today-progress").textContent=todayProgress;'
        'document.querySelector("#ceo-total-note").textContent='
        '"記録全体："+logs.length+"件（完了 "+totalDone+"件）";'
        'const recentList=document.querySelector("#ceo-recent-list");'
        'recentList.innerHTML=logs.length?'
        'logs.slice(0,3).map(l=>"<li>"+l[2]+"（"+l[4]+"）</li>").join(""):'
        '"<li>表示できる作業ログはまだありません。</li>";'
        'const priorityEl=document.querySelector("#ceo-priority");'
        'const nextUp=logs.find(l=>!isDone(l));'
        'priorityEl.textContent=nextUp?'
        'nextUp[2]+"を進めましょう（現在："+nextUp[4]+"）":'
        '(logs.length?"記録されている作業はすべて完了しています。":'
        '"表示できる作業ログはまだありません。");'
        'if(nextUp){'
        'const idx=logs.indexOf(nextUp);'
        'const targetKey=deskKeys[idx%deskKeys.length];'
        'document.querySelector("#qa-office").setAttribute("href","/office#desk-"+targetKey);'
        '}'
        '}).catch(()=>{'
        'document.querySelector("#ceo-today-count").textContent="―";'
        'document.querySelector("#ceo-today-done").textContent="―";'
        'document.querySelector("#ceo-today-progress").textContent="―";'
        'document.querySelector("#ceo-total-note").textContent="作業ログを取得できませんでした。";'
        'document.querySelector("#ceo-recent-list").innerHTML='
        '"<li>作業ログを取得できませんでした。</li>";'
        'document.querySelector("#ceo-priority").textContent="作業ログを取得できませんでした。";'
        '});</script>'
        '<section class="chat" aria-labelledby="chat-title"><h2 id="chat-title">柴犬社長に話しかける</h2><p>進捗・相談・次の一歩を入力できます。内容は保存・送信されません。</p>'
        # MISSION 027: 業務サポート会話の4ボタン。「オフィスへ案内」以外の
        # 3つは、既存 GET /api/logs (読み取り専用) だけを使って柴犬社長の
        # 会話欄へ案内を表示する。書き込み・他エンドポイントは一切使わない。
        # 「オフィスへ案内」は/officeへの通常の同一オリジンリンクであり、
        # JSによるリダイレクト先の書き換え等は行わない(安全な遷移)。
        '<div class="quick-actions" role="group" aria-label="よく使う質問">'
        '<button type="button" class="qa-btn" id="qa-today">今日の進捗</button>'
        '<button type="button" class="qa-btn" id="qa-priority">いま優先する仕事</button>'
        '<button type="button" class="qa-btn" id="qa-done">完了した仕事</button>'
        '<a class="qa-btn" id="qa-office" href="/office">オフィスへ案内</a>'
        '</div>'
        '<div id="log" class="log" aria-live="polite"><p class="boss">🐕 柴犬社長：今日の調子はどう？一緒に優先順位を決めよう。</p></div>'
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
        'function qaWithLogs(onOk){'
        'fetch("/api/logs").then(r=>r.ok?r.json():Promise.reject()).then(onOk)'
        '.catch(()=>{qaAppendBoss("🐕 柴犬社長：作業ログを取得できませんでした。");});'
        '}'
        'document.querySelector("#qa-today").addEventListener("click",()=>{'
        'qaWithLogs(logs=>{'
        'const todayStr=new Date().toISOString().slice(0,10);'
        'const todayLogs=logs.filter(l=>String(l[1]).slice(0,10)===todayStr);'
        'const todayDone=todayLogs.filter(l=>l[4]==="完了").length;'
        'const todayProgress=todayLogs.length-todayDone;'
        'qaAppendBoss(todayLogs.length?'
        '"🐕 柴犬社長：今日は"+todayLogs.length+"件の作業ログがあります（完了"+todayDone+"件・進行中"+todayProgress+"件）。":'
        '"🐕 柴犬社長：今日はまだ作業ログの記録がありません。");'
        '});'
        '});'
        'document.querySelector("#qa-priority").addEventListener("click",()=>{'
        'qaWithLogs(logs=>{'
        'const nextUp=logs.find(l=>l[4]!=="完了");'
        'qaAppendBoss(nextUp?'
        '"🐕 柴犬社長：いま優先するのは「"+nextUp[2]+"」です（現在："+nextUp[4]+"）。":'
        '(logs.length?"🐕 柴犬社長：記録されている作業はすべて完了しています！":'
        '"🐕 柴犬社長：表示できる作業ログはまだありません。"));'
        '});'
        '});'
        'document.querySelector("#qa-done").addEventListener("click",()=>{'
        'qaWithLogs(logs=>{'
        'const done=logs.filter(l=>l[4]==="完了");'
        'qaAppendBoss(done.length?'
        '"🐕 柴犬社長：完了した仕事は"+done.length+"件です："+'
        'done.slice(0,3).map(l=>l[2]).join("、")+(done.length>3?" ほか":"")+"。":'
        '"🐕 柴犬社長：まだ完了した作業はありません。");'
        '});'
        '});'
        '</script>'
    )
    return _page("ceo", "社長室", "柴犬社長と、今日の仕事について気軽に話せる小さな部屋です。", scene)

  @app.route("/revenue")
  def revenue_board():
    scene = _render_revenue_scene(REVENUE_FOCUS)
    return _page(
        "revenue", "収益化ボード",
        "外部公開・営業送信の前に、収益化の方針と今週の優先行動を確認するための"
        "社内検討用ボードです。",
        scene,
    )

  @app.route("/content-studio")
  def content_studio():
    scene = _render_content_studio_scene(
        CONTENT_STUDIO_THEME, CONTENT_STUDIO_PLANS, CONTENT_STUDIO_ROOM_LINK_POLICY,
    )
    return _page(
        "content", "投稿企画工場",
        "Pinterest・noteへ展開する前に、1つのテーマから投稿案を確認する"
        "社内検討用ボードです。",
        scene,
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
        PUBLISH_QUEUE_POSTS, PUBLISH_QUEUE_ROOM_LINK_NOTE, PUBLISH_QUEUE_MANUAL_POST_NOTE
    )
    return _page(
        "content", "投稿キュー（社長承認待ち）",
        "次の3本分のPinterest投稿を、画像・タイトル・説明文・altテキスト・"
        "確認項目までまとめて準備する画面です。公開は社長がPinterestで"
        "手動実行します。",
        scene,
    )

  @app.route("/content-studio/note-first-article")
  def content_studio_note_first_article():
    scene = _render_note_article_scene(NOTE_FIRST_ARTICLE)
    # MISSION 043: 既存の初回記事(NOTE_FIRST_ARTICLE)の下に、Pinterestの新
    # テーマ「スマホでAIに下書きを頼む前に確認する3つ」と対応するnote記事
    # 下書きを追加する。既存の初回記事セクションの内容・構成は変更しない。
    second_draft_scene = _render_note_second_article_draft_scene(NOTE_SECOND_ARTICLE_DRAFT)
    return _page(
        "content", "note初回記事",
        "柴犬社長がnoteへ手動で貼り付けて公開するための、初回記事および"
        "スマホAI下書きテーマの記事下書きの見出し・本文・見出し画像・"
        "タグ候補を確認する画面です。",
        f'{scene}<h2 class="fp-section-title">次のnote記事下書き</h2>'
        f'{second_draft_scene}',
    )
