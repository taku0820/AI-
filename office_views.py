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
.content-studio{max-width:1000px;margin:0 auto}
.cs-theme{font-size:12px;color:var(--sub);margin:0 0 16px}
.cs-theme b{color:var(--ink)}
.cs-legend{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 16px}
.cs-legend-item{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--sub);background:var(--panel);border:1px solid var(--edge);border-radius:999px;padding:5px 12px}
.cs-status-badge{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px}
.cs-status-badge.status-candidate{background:#063d2c;color:var(--green)}
.cs-status-badge.status-review{background:#3d3106;color:#fbbf24}
.cs-status-badge.status-pass{background:#2a2f3d;color:#94a3b8}
.cs-topic-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px 18px;margin-bottom:16px}
.cs-topic-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.cs-topic-head h3{margin:0;font-size:16px}
.cs-status-note{margin:0 0 10px;font-size:11px;color:var(--sub);line-height:1.5}
.cs-genre-label{font-size:11px;color:var(--sub);margin:0 0 6px}
.cs-genre-chips{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px}
.cs-genre-chip{background:#0f1a2c;border:1px solid var(--edge);border-radius:999px;padding:4px 10px;font-size:11px;color:var(--ink)}
.cs-media-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.cs-media-card{background:#0f1524;border:1px solid var(--edge);border-radius:12px;padding:10px 12px}
.cs-media-card h4{margin:0 0 6px;font-size:11px;color:var(--blue);font-weight:700;letter-spacing:.03em}
.cs-media-card p{margin:0;font-size:12px;line-height:1.6;color:var(--ink)}
.cs-footnote{margin-top:16px;font-size:11px;color:var(--sub);text-align:center}
@media(max-width:760px){.cs-topic-head{flex-direction:column}}
.cs-refine-section{margin-top:24px;padding-top:20px;border-top:1px solid var(--edge)}
.cs-refine-title{margin:0 0 6px;font-size:16px}
.cs-refine-intro{font-size:12px;color:var(--sub);line-height:1.6;margin:0 0 6px}
.cs-refine-disclaimer{background:#1c2c1f;border:1px solid #2f5136;color:#bfe8c6;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.6;margin:8px 0}
.cs-refine-disclaimer b{color:#eafff0}
.cs-refine-auto-note{background:#2c1f1c;border:1px solid #513629;color:#f0c9a5;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.6;margin:8px 0 18px}
.cs-refine-auto-note b{color:#ffe9d6}
.cs-refine-summary{font-size:12px;color:var(--sub);margin:0 0 16px}
.cs-refine-summary b{color:var(--green)}
.cs-iteration-card{background:var(--panel);border:1px solid var(--edge);border-radius:16px;padding:16px 18px;margin-bottom:16px}
.cs-iteration-card.is-candidate{border:2px solid var(--green)}
.cs-iteration-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.cs-iteration-head h4{margin:0;font-size:15px}
.cs-verdict-badge{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:999px}
.cs-verdict-badge.verdict-candidate{background:#063d2c;color:var(--green)}
.cs-verdict-badge.verdict-review{background:#3d3106;color:#fbbf24}
.cs-score{font-size:11px;color:var(--sub)}
.cs-verdict-reason{font-size:12px;color:var(--ink);margin:0 0 10px;line-height:1.5}
.cs-criteria-list{list-style:none;padding:0;margin:0 0 12px;display:grid;gap:6px}
.cs-criteria-list li{display:flex;gap:8px;font-size:11px;line-height:1.5;background:#0f1a2c;border:1px solid var(--edge);border-radius:8px;padding:6px 10px}
.cs-criteria-mark{flex-shrink:0;font-weight:700}
.cs-criteria-mark.mark-pass{color:var(--green)}
.cs-criteria-mark.mark-fail{color:#fbbf24}
.cs-first-post-link{display:inline-block;margin:0 0 18px;font-size:12px;background:#0b2540;color:var(--blue);border:1px solid var(--blue);border-radius:999px;padding:8px 14px;text-decoration:none}
.cs-first-post-link:hover{background:#123258}
.first-post-board{max-width:1000px;margin:0 auto}
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
.fp-threads-card{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:12px 14px;font-size:13px;line-height:1.6}
.fp-footnote{margin-top:18px;font-size:11px;color:var(--sub);text-align:center}
@media(max-width:760px){.fp-pin-layout{grid-template-columns:1fr}.fp-svg-wrap{max-width:280px;margin:0 auto}}
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
    "business_name": "美容サロン向けWeb制作",
    "purpose": "美容サロンの集客・予約導線を整えるWeb制作支援",
    "target_customer": "地域の美容サロン、小規模店、Web集客を改善したい事業者",
    "service_ideas": [
        "LP制作",
        "既存サイト改善",
        "予約導線・SNS導線の整理",
    ],
    "price_note": "価格帯はすべて未確定の「たたき台」です。確定した金額・契約内容ではありません。",
    "price_tiers": [
        ("エントリー帯", "未定"),
        ("スタンダード帯", "未定"),
        ("プレミアム帯", "未定"),
    ],
    "pipeline_stages": ["準備", "提案", "商談", "受注"],
    "weekly_priorities": [
        "ポートフォリオ整理",
        "提案テンプレート作成",
        "見込みサロンの条件整理",
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
      '<div class="revenue-card"><h3>サービス案</h3>'
      f'<ul>{service_items}</ul></div>'
      '<div class="revenue-card"><h3>価格帯（たたき台）</h3>'
      f'<p class="revenue-price-note">{focus["price_note"]}</p>'
      f'<ul class="revenue-price-tiers">{price_items}</ul></div>'
      '<div class="revenue-card"><h3>受注までの段階</h3>'
      f'<ol class="revenue-pipeline">{pipeline_items}</ol></div>'
      '<div class="revenue-card"><h3>今週の優先行動</h3>'
      f'<ol class="revenue-priorities">{priority_items}</ol></div>'
      '</div>'
      '<p class="revenue-footnote">この画面はlocalhost限定で表示される'
      '社内検討用の資料です。送信・公開・自動実行は行われません。</p>'
      '</section>'
  )


# MISSION 030: 投稿企画工場(ローカル専用のコンテンツ企画たたき台)。
#
# ここに書く内容もREVENUE_FOCUSと同様、すべて「社内向けの下書き」で
# あり、投稿・公開・送信・商品紹介の実行は一切行わない(表示専用の
# 静的コンテンツ)。楽天アフィリエイトにつながり得る商品ジャンルの
# 候補は入れてよいが、商品名・価格・ランキング・成果(クリック数等)は
# 一切含めない(候補ジャンルの言葉だけを列挙する)。将来テーマ・媒体・
# 文章案を差し替える場合は、このデータ構造(CONTENT_STUDIO_TOPICS)を
# 編集するだけでよく、HTML生成コードには手を入れなくてよいように
# 分離している。
CONTENT_STUDIO_THEME = "AIとガジェットで、仕事と暮らしを少しラクにする"

# 3段階の凡例。表示のみに使う値であり、実際の投稿判断・承認フローとは
# 独立している(この画面から投稿が実行されることはない)。
CONTENT_STUDIO_STATUS_LABELS = {
    "candidate": "投稿候補",
    "review": "要確認",
    "pass": "見送り",
}

CONTENT_STUDIO_TOPICS = [
    {
        "title": "AI初心者が最初に試す便利な使い方",
        "status": "candidate",
        "status_note": "初心者向けの導入コンテンツとして反応が見込みやすいたたき台。",
        "product_genre_ideas": ["AIアシスタント対応スマートスピーカー", "音声入力対応キーボード"],
        "drafts": {
            "Instagram": "リール構成案：①「AI使ったことない人へ」で入る ②実際の画面操作を3カットで見せる "
                          "③最後に「保存して後で試してね」で締める。",
            "Threads": "「AIって結局なにに使えるの？」とゆるく問いかける短文投稿案。コメント欄で使い方の実例を"
                       "集める設計にする。",
            "Pinterest": "タイトル案:「AI初心者向け・最初にやること3選」／説明文案: 迷いがちな最初の一歩を"
                         "3つに絞って紹介する保存用ピン。",
            "note": "見出し案:「AIを何となく怖いと思っている人が、最初の一歩を踏み出すための3つのステップ」",
        },
    },
    {
        "title": "仕事の文章作成・要約をラクにするAI活用",
        "status": "candidate",
        "status_note": "実務に直結し保存されやすいテーマとして優先度が高いたたき台。",
        "product_genre_ideas": ["音声文字起こしデバイス", "ノートPC用外付けマイク"],
        "drafts": {
            "Instagram": "カルーセル構成案：1枚目「その文章、AIに手伝わせよう」 2〜4枚目で下書き→要約→"
                          "整文のビフォーアフター例 5枚目でまとめ。",
            "Threads": "「長文の要約、皆どうしてる？」と実務あるあるを軽く投げかける短文投稿案。",
            "Pinterest": "タイトル案:「文章作成が苦手な人のためのAI活用メモ」／説明文案: 要約・下書き・"
                         "整文の3場面での使い分けを紹介する保存用ピン。",
            "note": "見出し案:「文章が苦手でも大丈夫。AIと役割分担して仕事を進める考え方」",
        },
    },
    {
        "title": "デスク周りを整える便利ガジェット",
        "status": "review",
        "status_note": "紹介する商品ジャンルの選定基準を先に整理したいため要確認。",
        "product_genre_ideas": ["モニターアーム", "デスクライト", "ケーブル収納グッズ"],
        "drafts": {
            "Instagram": "リール構成案：①散らかったデスクのビフォー ②ガジェット導入 ③整ったデスクの"
                          "アフターで見せる構成。",
            "Threads": "「デスク周りで一番効果があった小物は？」と気軽に聞く短文投稿案。",
            "Pinterest": "タイトル案:「作業がはかどるデスク周りグッズまとめ」／説明文案: ジャンル別に"
                         "整理して探しやすくする保存用ピン。",
            "note": "見出し案:「机の上を変えるだけで集中力が変わる、デスク環境の整え方」",
        },
    },
    {
        "title": "スマホ・PC作業を快適にする周辺機器",
        "status": "review",
        "status_note": "対象ガジェットの範囲が広く、切り口の絞り込みが必要なため要確認。",
        "product_genre_ideas": ["USB-Cハブ", "ワイヤレス充電スタンド", "ノートPCスタンド"],
        "drafts": {
            "Instagram": "カルーセル構成案：用途別(充電/接続/持ち運び)に周辺機器の役割を1枚ずつ紹介する構成。",
            "Threads": "「地味だけど手放せない周辺機器」をテーマにした短文投稿案。",
            "Pinterest": "タイトル案:「スマホ・PC作業がはかどる周辺機器ジャンルまとめ」／説明文案: "
                         "用途別に整理した保存用ピン。",
            "note": "見出し案:「持ち物を少し変えるだけで、外出先の作業効率は変わる」",
        },
    },
    {
        "title": "買う前に確認したいAI対応ガジェットの選び方",
        "status": "pass",
        "status_note": "情報の鮮度管理が必要で、継続更新の体制が整うまで一旦保留。",
        "product_genre_ideas": ["AI搭載イヤホン", "スマートディスプレイ"],
        "drafts": {
            "Instagram": "リール構成案：①よくある失敗例 ②確認すべきポイント3つ ③選び方のまとめ、で"
                          "構成する案。",
            "Threads": "「AI対応と書いてあると迷う」という共感から入る短文投稿案。",
            "Pinterest": "タイトル案:「買う前にチェック・AI対応ガジェットの選び方」／説明文案: "
                         "購入前に確認したい観点を整理した保存用ピン。",
            "note": "見出し案:「『AI対応』の表示だけで選ばない。後悔しないガジェット選びの基準」",
        },
    },
]


# MISSION 031: 最初のテーマ「AI初心者が最初に試す便利な使い方」向けの、
# 最大5案(初稿→改善1→改善2→改善3→改善4)の改善・採点ワークフロー。
#
# ここでの「採点」は投稿が伸びることを保証する予測ではなく、公開前の
# 編集チェック(誰向けか・具体性・誇大表現の有無など)である。自動投稿は
# 実装しておらず、最初の手動投稿の確認と媒体別の公式連携が完了するまで
# 有効化しない方針を明記している。将来、対象テーマや案の中身を差し替える
# 場合は、このデータ構造(CONTENT_STUDIO_REFINEMENT)を編集するだけでよい。
CONTENT_STUDIO_REFINEMENT = {
    "topic_title": "AI初心者が最初に試す便利な使い方",
    "intro": "公開前に、初稿から最大4回まで改善しながら比較するための編集ワークフローです。",
    "scoring_disclaimer": (
        "この採点は、投稿が伸びることを保証する予測ではありません。あくまで公開前の"
        "編集チェック（誰向けか・具体性・誇大表現の有無などの確認）です。"
    ),
    "auto_post_note": (
        "自動投稿は、最初の手動投稿の内容を確認し、Instagram・Threads・Pinterest・"
        "noteそれぞれの公式連携（API等）が完了したあとに有効化します。現時点では"
        "自動投稿は行いません。"
    ),
    "criteria": [
        ("audience", "誰向けかが明確か"),
        ("opening_value", "冒頭で悩みや得られる価値が分かるか"),
        ("concreteness", "実際に試せる具体性があるか"),
        ("pinterest_title", "Pinterestで保存・検索されやすいタイトルになっているか"),
        ("no_hype", "誇大表現・断定・未確認の商品情報がないか"),
    ],
    "iterations": [
        {
            "label": "初稿",
            "drafts": {
                "Instagram": "AIって便利らしいけど何をすればいいかわからない人向けのリール構成案"
                              "（具体的な操作手順は未定）。",
                "Threads": "「AIって結局なにに使えるの？」とゆるく聞いてみる投稿案。",
                "Pinterest": "タイトル案「AIの使い方」／説明文案「AIについて紹介します。」",
                "note": "見出し案「AIを使ってみよう」",
            },
            "scores": {
                "audience": False, "opening_value": True, "concreteness": False,
                "pinterest_title": False, "no_hype": True,
            },
            "score_reasons": {
                "audience": "「AI初心者」とだけで具体的な状況が示されておらず、誰向けか曖昧です。",
                "opening_value": "「何をすればいいかわからない人向け」という悩みへの言及があります。",
                "concreteness": "「触ってみよう」だけで、実際に試せる操作手順が示されていません。",
                "pinterest_title": "「AIの使い方」は検索されにくい一般的なタイトルです。",
                "no_hype": "誇大表現や断定的な言い回しは見られません。",
            },
            "verdict": "review",
            "verdict_reason": "誰向けかと具体的な手順が弱いため、次の改善案へ進みます。",
        },
        {
            "label": "改善1",
            "drafts": {
                "Instagram": "「毎日の事務作業、まだ全部手作業ですか？」から入り、AI初心者向けの"
                              "最初の一歩を紹介するリール構成案。",
                "Threads": "毎日の事務作業でAIを使ったことがない人へ、「まず何から始める？」と"
                           "問いかける短文投稿案。",
                "Pinterest": "タイトル案「AI初心者向けの使い方」／説明文案「AI初心者向けに使い方を"
                             "紹介します。」",
                "note": "見出し案「事務作業でAIを使ったことがない人へ」",
            },
            "scores": {
                "audience": True, "opening_value": True, "concreteness": False,
                "pinterest_title": False, "no_hype": True,
            },
            "score_reasons": {
                "audience": "「毎日の事務作業でAIを使ったことがない人」と対象を具体化しました。",
                "opening_value": "冒頭の問いかけで悩みへの言及を維持しています。",
                "concreteness": "「最初の一歩」への言及はあるものの、具体的な操作手順がまだありません。",
                "pinterest_title": "「AI初心者向けの使い方」もまだ一般的で、検索されやすいとは言えません。",
                "no_hype": "誇大表現や断定的な言い回しはありません。",
            },
            "verdict": "review",
            "verdict_reason": "具体的な手順とPinterestタイトルの検索されやすさがまだ弱いため、"
                               "次の改善案へ進みます。",
        },
        {
            "label": "改善2",
            "drafts": {
                "Instagram": "①「まだ全部手作業ですか？」で入る ②メール下書きをAIに1文で依頼する"
                              "画面操作を見せる ③「今日から1つだけ試してみて」で締めるリール構成案。",
                "Threads": "毎日の事務作業でAIを使ったことがない人へ、「メールの下書きを1文で"
                           "頼むだけでも変わるよ」と具体例を添える短文投稿案。",
                "Pinterest": "タイトル案「AI初心者向けの使い方」／説明文案「メールの下書きを1文で"
                             "頼む方法など、具体的な手順を紹介します。」",
                "note": "見出し案「事務作業でAIを使ったことがない人が、最初にメール下書きを"
                        "1文で頼んでみる話」",
            },
            "scores": {
                "audience": True, "opening_value": True, "concreteness": True,
                "pinterest_title": False, "no_hype": True,
            },
            "score_reasons": {
                "audience": "対象は引き続き明確です。",
                "opening_value": "冒頭の問いかけを維持しています。",
                "concreteness": "「メール下書きを1文で依頼する」という具体的な操作手順を追加しました。",
                "pinterest_title": "タイトルは「AI初心者向けの使い方」のままで、まだ検索されやすいとは"
                                    "言えません。",
                "no_hype": "誇大表現や断定的な言い回しはありません。",
            },
            "verdict": "review",
            "verdict_reason": "Pinterestタイトルがまだ一般的で検索されにくいため、次の改善案へ進みます。",
        },
        {
            "label": "改善3",
            "drafts": {
                "Instagram": "①「まだ全部手作業ですか？」で入る ②メール下書きをAIに1文で依頼する"
                              "画面操作を見せる ③「これで誰でも絶対うまくいく！」で締めるリール構成案。",
                "Threads": "毎日の事務作業でAIを使ったことがない人へ、「メールの下書きを1文で"
                           "頼むだけでも変わるよ」と具体例を添える短文投稿案。",
                "Pinterest": "タイトル案「AI初心者向け・メール下書きを1文で頼む方法」／説明文案"
                             "「メールの下書きを1文で頼む方法など、具体的な手順を紹介します。」",
                "note": "見出し案「事務作業でAIを使ったことがない人が、最初にメール下書きを"
                        "1文で頼んでみる話」",
            },
            "scores": {
                "audience": True, "opening_value": True, "concreteness": True,
                "pinterest_title": True, "no_hype": False,
            },
            "score_reasons": {
                "audience": "対象は引き続き明確です。",
                "opening_value": "冒頭の問いかけを維持しています。",
                "concreteness": "具体的な操作手順を維持しています。",
                "pinterest_title": "「メール下書きを1文で頼む方法」と具体化し、検索されやすいタイトルに"
                                    "なりました。",
                "no_hype": "「これで誰でも絶対うまくいく！」という断定的な表現が残っています。",
            },
            "verdict": "review",
            "verdict_reason": "断定的な表現が残っているため、次の改善案へ進みます。",
        },
        {
            "label": "改善4",
            "drafts": {
                "Instagram": "①「まだ全部手作業ですか？」で入る ②メール下書きをAIに1文で依頼する"
                              "画面操作を見せる ③「今日から1つだけ試してみて」で締めるリール構成案。",
                "Threads": "毎日の事務作業でAIを使ったことがない人へ、「メールの下書きを1文で"
                           "頼むだけでも変わるよ」と具体例を添える短文投稿案。",
                "Pinterest": "タイトル案「AI初心者向け・メール下書きを1文で頼む方法」／説明文案"
                             "「メールの下書きを1文で頼む方法など、具体的な手順を紹介します。効果を"
                             "保証するものではありません。」",
                "note": "見出し案「事務作業でAIを使ったことがない人が、最初にメール下書きを"
                        "1文で頼んでみる話」",
            },
            "scores": {
                "audience": True, "opening_value": True, "concreteness": True,
                "pinterest_title": True, "no_hype": True,
            },
            "score_reasons": {
                "audience": "対象は引き続き明確です。",
                "opening_value": "冒頭の問いかけを維持しています。",
                "concreteness": "具体的な操作手順を維持しています。",
                "pinterest_title": "検索されやすいタイトルを維持しています。",
                "no_hype": "断定的な表現を取り除き、効果を保証しない言い回しに修正しました。",
            },
            "verdict": "candidate",
            "verdict_reason": "5つの基準をすべて満たしたため、手動投稿候補とします。",
        },
    ],
}


def _render_refinement_section(refinement, criteria_labels_by_key):
  """MISSION 031の改善・採点ワークフローのHTMLを組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・外部通信への
  アクセスは一切行わない。
  """
  candidate_label = next(
      (it["label"] for it in refinement["iterations"] if it["verdict"] == "candidate"),
      None,
  )
  summary = (
      f'現在の手動投稿候補：<b>{candidate_label}</b>'
      if candidate_label else "現在、5つの基準をすべて満たした案はまだありません。"
  )

  iteration_cards = []
  for iteration in refinement["iterations"]:
    scores = iteration["scores"]
    reasons = iteration["score_reasons"]
    score_count = sum(1 for v in scores.values() if v)
    total = len(refinement["criteria"])
    is_candidate = iteration["verdict"] == "candidate"
    verdict_label = "手動投稿候補" if is_candidate else "要改善"
    verdict_class = "verdict-candidate" if is_candidate else "verdict-review"

    criteria_items = "".join(
        '<li><span class="cs-criteria-mark '
        + ("mark-pass" if scores[key] else "mark-fail") + '">'
        + ("✓" if scores[key] else "△") + '</span>'
        f'<span><b>{label}</b>：{reasons[key]}</span></li>'
        for key, label in criteria_labels_by_key
    )
    media_cards = "".join(
        f'<div class="cs-media-card"><h4>{medium}</h4><p>{draft}</p></div>'
        for medium, draft in iteration["drafts"].items()
    )
    card_class = "cs-iteration-card is-candidate" if is_candidate else "cs-iteration-card"
    iteration_cards.append(
        f'<div class="{card_class}">'
        '<div class="cs-iteration-head">'
        f'<h4>{iteration["label"]}</h4>'
        f'<span><span class="cs-verdict-badge {verdict_class}">{verdict_label}</span> '
        f'<span class="cs-score">{score_count}/{total} 基準クリア</span></span>'
        '</div>'
        f'<p class="cs-verdict-reason">{iteration["verdict_reason"]}</p>'
        f'<ul class="cs-criteria-list">{criteria_items}</ul>'
        f'<div class="cs-media-grid">{media_cards}</div>'
        '</div>'
    )

  return (
      '<section class="cs-refine-section" aria-label="投稿改善ワークフロー">'
      f'<h3 class="cs-refine-title">投稿改善ワークフロー：{refinement["topic_title"]}'
      '（最大5案）</h3>'
      f'<p class="cs-refine-intro">{refinement["intro"]}</p>'
      f'<div class="cs-refine-disclaimer"><b>採点についての注意。</b>'
      f'{refinement["scoring_disclaimer"]}</div>'
      f'<div class="cs-refine-auto-note"><b>自動投稿について。</b>'
      f'{refinement["auto_post_note"]}</div>'
      f'<p class="cs-refine-summary">{summary}</p>'
      + "".join(iteration_cards) +
      '</section>'
  )


def _render_content_studio_scene(theme, topics, status_labels, refinement=None):
  """投稿企画工場のカード群を、CONTENT_STUDIO_TOPICSのデータから組み立てる。

  純粋な表示用マークアップの生成のみを行う。DB・API・SNS・外部通信への
  アクセスは一切行わない。
  """
  legend_items = "".join(
      f'<span class="cs-legend-item"><span class="cs-status-badge status-{key}">'
      f'{label}</span></span>'
      for key, label in status_labels.items()
  )
  topic_cards = []
  for topic in topics:
    status_key = topic["status"]
    status_label = status_labels[status_key]
    genre_chips = "".join(
        f'<span class="cs-genre-chip">{genre}</span>'
        for genre in topic["product_genre_ideas"]
    )
    media_cards = "".join(
        f'<div class="cs-media-card"><h4>{medium}</h4><p>{draft}</p></div>'
        for medium, draft in topic["drafts"].items()
    )
    topic_cards.append(
        '<div class="cs-topic-card">'
        '<div class="cs-topic-head">'
        f'<h3>{topic["title"]}</h3>'
        f'<span class="cs-status-badge status-{status_key}">{status_label}</span>'
        '</div>'
        f'<p class="cs-status-note">{topic["status_note"]}</p>'
        '<p class="cs-genre-label">関連商品ジャンル候補（価格・順位・実績は未確定・未記載）</p>'
        f'<div class="cs-genre-chips">{genre_chips}</div>'
        f'<div class="cs-media-grid">{media_cards}</div>'
        '</div>'
    )
  return (
      '<section class="content-studio" aria-label="投稿企画工場">'
      '<div class="revenue-notice">'
      '<b>社内向けの投稿企画たたき台です。</b>'
      'ここに表示する内容はすべて下書きであり、投稿・公開・送信・商品紹介は'
      '一切実行されません。'
      '</div>'
      f'<p class="cs-theme">対象テーマ：<b>{theme}</b></p>'
      '<a class="cs-first-post-link" href="/content-studio/first-post">'
      '→ 初回手動投稿パッケージを見る（Pinterest向け）</a>'
      f'<div class="cs-legend">{legend_items}</div>'
      + "".join(topic_cards)
      + (
          _render_refinement_section(refinement, refinement["criteria"])
          if refinement else ""
      ) +
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
    "threads_draft": (
        "AIって結局なにに使えばいいの？って人へ。まずはメールの下書きを1文で頼む"
        "ところから始めてみませんか。長い文章の要約やアイデア出しの壁打ちにも使えます。"
    ),
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
  """初回手動投稿パッケージ(Pinterest+Threads)のHTMLを組み立てる。

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
      '<h3 class="fp-section-title">Threads投稿案（同テーマ）</h3>'
      '<div class="fp-threads-card"><div class="fp-field-head"><h4>Threads下書き</h4>'
      '<button type="button" class="fp-copy-btn" data-copy-target="fp-threads">コピー</button></div>'
      f'<p id="fp-threads">{package["threads_draft"]}</p></div>'
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
      'Pinterest・Instagram・Threads・note・楽天への投稿・送信・連携は行われません。</p>'
      '</section>'
  )


def register_office_views(app):
  """Flaskアプリへ3つの表示専用ルートを登録する。"""
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
        CONTENT_STUDIO_THEME, CONTENT_STUDIO_TOPICS, CONTENT_STUDIO_STATUS_LABELS,
        refinement=CONTENT_STUDIO_REFINEMENT,
    )
    return _page(
        "content", "投稿企画工場",
        "Instagram・Threads・Pinterest・noteへ展開する前に、1つのテーマから"
        "媒体別の投稿案を比較する社内検討用ボードです。",
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
