"""AI Hive のライブオフィス画面。

すべてブラウザ内だけで描画する表示演出。DB/API/監査ログ/外部通信は使わず、
社長室の会話も保存されないローカルの定型リアクションである。
"""

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
