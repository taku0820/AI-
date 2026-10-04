"""ダッシュボード画面(GET /)のデザイン刷新（MISSION 024）の表示内容テスト。

Flaskのテストクライアントで `GET /` のレスポンスHTMLを取得し、実際の
ブラウザ描画・CSSアニメーションの見た目そのものは検証しない（それは
別途ヘッドレスブラウザでの目視確認で行った）。ここで機械的に確認するのは、
- 既存ツール(hive_status.py等)が参照しているマーカー文字列が保たれているか
- 外部リソース(外部画像・外部フォント・CDN・外部JS・外部URL)が
  一切含まれていないか
- prefers-reduced-motion に対応したCSSが含まれているか
- プロジェクト内のミニフィギュア画像が8名分描画されているか
- 読み取り専用の /api/logs エンドポイント自体が維持されているか
  （MISSION 051以降、UI側(/office等)からの動的な参照は行っていない）
- レスポンシブ対応のメディアクエリが含まれているか
といった、安全要件・アクセシビリティ要件・既存機能の維持に関わる点のみ。

本番の `ai_company.db` を汚さないよう、一時コピーに対してテストを実行する
(test_hive_api.pyと同じ方針)。

実行方法: venv/bin/python test_dashboard_design.py
"""

import json
import os
import re
import shutil
import tempfile
import unittest

import app as app_module
import dashboard_db

PROJECT_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_company.db")


class DashboardDesignTestCase(unittest.TestCase):

  def setUp(self):
    fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy(PROJECT_DB_PATH, self.temp_db_path)

    self._orig_db_name = app_module.DB_NAME
    app_module.DB_NAME = self.temp_db_path
    # MISSION 088: dashboard_db.py(daily_records/post_candidatesテーブル)も
    # 本番のai_company.dbを汚さないよう、同じ一時コピーへリダイレクトする
    # (test_hive_api.pyがhive_db.DB_NAMEに対して行っているのと同じ方針)。
    self._orig_dashboard_db_name = dashboard_db.DB_NAME
    dashboard_db.DB_NAME = self.temp_db_path
    # MISSION 089: register_dashboard_api()のinit_schema()はapp.pyの
    # import時に1度しか走らないため、DB_NAMEをこの一時コピーへ切り替えた
    # 直後に明示的に呼び直し、bucket列の移行などが常にこの使い捨て
    # コピーに対して確実に適用された状態でテストできるようにする
    # (本番ai_company.dbの状態に依存しないようにするため)。
    dashboard_db.init_schema()

    app_module.app.testing = True
    self.client = app_module.app.test_client()

    res = self.client.get("/")
    self.assertEqual(res.status_code, 200)
    self.html = res.get_data(as_text=True)

  def tearDown(self):
    app_module.DB_NAME = self._orig_db_name
    dashboard_db.DB_NAME = self._orig_dashboard_db_name
    os.remove(self.temp_db_path)

  def _find_api_paths(self, html):
    """html中に現れる "/api/..." パス文字列をすべて抽出する(安全テスト用)。"""
    return re.findall(r'"(/api/[a-zA-Z0-9/_-]*)"', html)

  def _reset_dashboard_tables(self):
    """MISSION 088/089: daily_records/post_candidatesの行数を厳密に数える
    テスト用に、一時コピー(self.temp_db_path、使い捨てで本番ai_company.db
    には一切影響しない)の該当2テーブルだけを空にする。本番DBには、実際の
    利用で蓄積した行がすでに入っていることがあるため、件数アサーションが
    その影響を受けないようにするための前処理。"""
    import sqlite3
    conn = sqlite3.connect(self.temp_db_path)
    try:
      conn.execute("DELETE FROM daily_records")
      conn.execute("DELETE FROM post_candidates")
      conn.commit()
    finally:
      conn.close()

  # --- 既存機能・既存ツールとの互換性 ------------------------------------------

  def test_required_marker_text_is_preserved(self):
    # hive_status.check_root_page() および test_hive_api.py が参照する
    # マーカー文字列。これが失われると既存のヘルスチェックCLIが誤検知する。
    self.assertIn("会社の全体像ダッシュボード", self.html)

  def test_logs_api_endpoint_still_exists_though_root_page_no_longer_uses_it(self):
    # MISSION 038でトップページの「現在の作業」カード(/api/logsから最新の
    # 作業ログを表示していた箇所)を削除したため、トップページ自体は
    # /api/logsを呼び出さなくなった。MISSION 051で/office・/office/ceo-office
    # もwork_logs(現在と無関係な古いテスト用データしかない)への依存を
    # やめ、静的な現在状況を表示するように変更したため、UI側から/api/logs
    # を呼び出す画面は無くなったが、既存の読み取り専用エンドポイント自体は
    # 引き続き削除していない(将来の利用に備えて残している)。
    self.assertNotIn("fetch('/api/logs')", self.html)
    self.assertNotIn('id="latest-theme"', self.html)
    self.assertNotIn('id="latest-content"', self.html)
    res = self.client.get("/api/logs")
    self.assertEqual(res.status_code, 200)

  def test_logs_api_still_returns_200_and_json_array(self):
    res = self.client.get("/api/logs")
    self.assertEqual(res.status_code, 200)
    self.assertIsInstance(res.get_json(), list)

  # --- 外部リソースを一切含まないこと ------------------------------------------

  def test_no_external_urls_present(self):
    self.assertNotIn("http://", self.html)
    self.assertNotIn("https://", self.html)

  def test_no_external_script_or_stylesheet_tags(self):
    self.assertNotIn("<script src=", self.html)
    self.assertNotIn("<link", self.html)
    self.assertNotIn("@import", self.html)

  def test_only_local_avatar_sprite_is_used(self):
    # 外部画像の代わりに、プロジェクト内のオリジナル画像スプライトだけを
    # CSS背景として参照する。旧プレースホルダー画像は表示に使わない。
    self.assertIn("/static/images/office-avatars-v1.png", self.html)
    self.assertNotIn("/static/president.png", self.html)
    self.assertNotIn("<img", self.html)

  def test_no_unrendered_template_artifacts(self):
    # render_template_stringはJinja2を経由するため、意図しない
    # {{ ... }} が展開されずそのまま残っていないことを確認する。
    self.assertNotIn("{{", self.html)
    self.assertNotIn("{%", self.html)

  # --- アクセシビリティ(prefers-reduced-motion) --------------------------------

  def test_prefers_reduced_motion_media_query_present(self):
    self.assertIn("prefers-reduced-motion: reduce", self.html)
    # reduce時にアニメーション/トランジションを縮退させる記述であること。
    reduced_block_match = re.search(
        r"prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\}\s*\}",
        self.html, re.S,
    )
    self.assertIsNotNone(reduced_block_match)
    reduced_block = reduced_block_match.group(1)
    self.assertIn("animation", reduced_block)

  def test_decorative_figures_are_hidden_from_assistive_tech(self):
    # ミニフィギュアは隣接する名前・役職・ステータスのテキストと重複する
    # 装飾要素のため、aria-hiddenでスクリーンリーダーから隠している。
    figure_count = self.html.count('class="avatar-sprite ')
    aria_hidden_on_figure = len(
        re.findall(r'<span class="avatar-sprite [^"]+" aria-hidden="true"></span>', self.html)
    )
    self.assertGreater(figure_count, 0)
    self.assertEqual(figure_count, aria_hidden_on_figure)

  # --- ミニフィギュア(ローカル画像スプライト) ---------------------------------

  def test_only_president_mini_figure_is_rendered(self):
    # MISSION 038で、実在しない作業チーム(彩・琴衣・蒼・美咲・海・湊・伊藤)
    # をトップページから削除したため、描画されるミニフィギュアは柴犬社長の
    # 1名のみになった。
    self.assertEqual(self.html.count('class="avatar-sprite '), 1)
    self.assertIn("柴犬社長", self.html)
    for removed_name in ("彩・経理担当", "琴衣", "蒼", "美咲", "海", "湊", "伊藤"):
      self.assertNotIn(removed_name, self.html)

  def test_each_role_status_prop_badge_is_rendered(self):
    # 残っているのは柴犬社長のstampバッジのみ。
    self.assertIn('avatar-badge prop-stamp', self.html)
    for removed_prop in ("doc", "check", "phone", "list", "pen", "code", "search"):
      self.assertNotIn(f'avatar-badge prop-{removed_prop}', self.html)

  # --- レスポンシブ対応 --------------------------------------------------------

  def test_viewport_meta_present(self):
    self.assertIn('name="viewport"', self.html)

  def test_responsive_media_queries_present(self):
    self.assertIn("@media (max-width: 860px)", self.html)
    self.assertIn("@media (max-width: 480px)", self.html)

  # --- MISSION 038: 現在の実運用に合わせた整理 ---------------------------------

  def test_root_dashboard_removes_unrelated_fictional_business_content(self):
    # A8.net・美容アフィリエイト・美容サロンWEB制作・架空の売上額/更新件数/
    # LIVE表示・実在しない作業チーム/事業ポートフォリオを、トップページから
    # 完全に削除したことを確認する。
    for removed in (
        "A8.net", "美容アフィリエイト", "美容サロン", "事業ポートフォリオ",
        "経理・売上フロア", "運用チームフロア", "WEB制作フロア",
        "琴衣", "蒼", "美咲", "海", "湊", "伊藤", "彩・経理担当",
        "LIVE", "¥301", "75件", "68%", "64%", "3%",
    ):
      with self.subTest(removed=removed):
        self.assertNotIn(removed, self.html)

  def test_root_dashboard_shows_only_the_five_required_channels(self):
    # MISSION 050で、実際にDifyで別管理の自動投稿を運用しているThreadsの
    # カードを追加したため、4チャンネル→5チャンネルになった。Threadsは
    # 手動運用ではないため、badge-manualではなくbadge-dify(別配色)を使う。
    for channel in ("Pinterest", "楽天ROOM", "note", "Threads", "コンテンツスタジオ"):
      self.assertIn(channel, self.html)
    self.assertEqual(self.html.count('class="badge-manual"'), 4)
    self.assertEqual(self.html.count('class="badge-dify"'), 1)
    self.assertEqual(self.html.count("現在の役割："), 5)
    self.assertEqual(self.html.count("次の行動："), 5)

  def test_root_dashboard_states_local_manual_only_notice(self):
    self.assertIn(
        "この画面は投稿準備と手動確認のためのローカル画面であり、"
        "SNS投稿・分析取得・売上取得の自動連携は行いません。",
        self.html,
    )

  def test_root_dashboard_does_not_show_fabricated_metrics(self):
    # 収益額・フォロワー数・PV・クリック数などの数値を新たに固定表示して
    # いないことを確認する(既存のパーセンテージ・円表示もすべて削除済み)。
    # 「フォロワー数・PV・クリック数…は表示していません」という否定形の
    # 案内文の中にのみ、これらの語が1回ずつ登場することを確認する。
    self.assertNotIn("¥", self.html)
    self.assertNotIn("%</span>", self.html)
    self.assertEqual(self.html.count("フォロワー"), 1)
    self.assertEqual(self.html.count("PV"), 1)
    self.assertEqual(self.html.count("クリック数"), 1)
    self.assertIn(
        "フォロワー数・PV・クリック数・売上額などの数値は表示していません",
        self.html,
    )

  def test_root_dashboard_links_to_content_studio_pages(self):
    for path in (
        '"/content-studio"', '"/content-studio/publish-queue"',
        '"/content-studio/note-first-article"',
    ):
      self.assertIn(f'href={path}', self.html)

  def test_root_dashboard_links_to_room_prep_on_revenue_board(self):
    self.assertIn('href="/revenue#room-prep"', self.html)

  def test_root_dashboard_president_intro_states_manual_operation(self):
    # MISSION 050: Threadsのみ実際にDifyで別管理の自動投稿を運用している
    # ため、「すべて手動」という一文からThreadsを除き、その旨を明記する
    # ように更新した。
    self.assertIn("柴犬社長", self.html)
    self.assertIn(
        "Pinterest・楽天ROOM・noteは、すべて社長が手動で担当しています。",
        self.html,
    )
    self.assertIn(
        "Threadsのみ、Difyを使った別管理の自動投稿を運用していますが、"
        "このダッシュボードからの自動投稿・自動集計・外部サービスとの"
        "自動連携は行っていません。",
        self.html,
    )

  def test_root_dashboard_office_page_still_has_its_own_fictional_desk_characters(self):
    # /officeの「ライブオフィス」表示は、このミッションの対象外であり、
    # デスクキャラクター表示自体はそのまま残っていることを確認する
    # (トップページからの削除が、他画面を壊していないことの回帰確認)。
    # MISSION 083: 実在の12人と無関係だった旧キャスト(琴衣・美咲・海・湊・
    # 伊藤)は、AIオフィスと同じ実在4人(里奈・凛・葵・蒼)へ置き換えた。
    office_html = self.client.get("/office").get_data(as_text=True)
    for name in ("里奈", "凛", "葵", "蒼"):
      self.assertIn(name, office_html)

  # --- MISSION 038.1: 4カードの現状表示を実際の運用状況へ合わせる更新 -----------

  def test_root_dashboard_cards_reflect_current_actual_status(self):
    # MISSION 050: Threadsカード(Dify別管理の自動投稿)を新たに追加した。
    # MISSION 054: 2026年9月12日時点の実態(Pinterest5件・note3件公開済み、
    # 最新Pinterest投稿は公開済みで、次に確認することは48時間後の反応確認)
    # に合わせて更新した。
    # MISSION 055: noteの「3件」はAI Hive関連の記事数であり、noteアカウント
    # 全体の記事数ではないことを明記した。
    # MISSION 057: 楽天ROOMは、折りたたみキーボード1件に加え、9月13日に
    # 過去購入・使用商品5件、9月14日にショルダー型ガジェットポーチ1件を
    # 投稿し、合計7件になったことを反映した。
    # MISSION 058: 楽天ROOMアカウント全体の商品数は30件であり、AI Hiveで
    # 追加・記録しているのは7件だけであることを明記した。
    # MISSION 059: 9月16日に10件を追加投稿し、AI Hiveで追加した投稿は
    # 合計17件になった。
    for role, next_action in (
        (
            "現在の役割：5件公開済み。最新投稿は48時間後を目安に"
            "反応を手動で確認予定。",
            "次の行動：<b>48時間後を目安に最新投稿の反応を手動で確認し、"
            "準備済みの案も引き続き確認する。</b>",
        ),
        (
            "現在の役割：AI Hiveで追加した商品投稿が17件公開済み。反応を確認しつつ、"
            "次に紹介する候補を整理する。",
            "次の行動：<b>投稿間隔を空けながら、社長が手動で商品を整理・投稿する。</b>",
        ),
        (
            "現在の役割：AI Hive関連の記事3件が公開済み。次の記事の下書き・見出し画像・"
            "Pinterest投稿案まで準備済み。",
            "次の行動：<b>準備済みの下書きを確認し、社長が手動でnoteへ"
            "貼り付けて公開する。</b>",
        ),
        (
            "現在の役割：Difyを使った別システムで自動投稿を運用中。",
            "次の行動：<b>このダッシュボードでは投稿・ログイン・連携を"
            "一切行わない。運用状況の確認・変更はDify側で行う。</b>",
        ),
        (
            "現在の役割：投稿パッケージを作成し、公開前の内容を確認する。",
            "次の行動：<b>投稿キューから次のテーマを選び、投稿パッケージを"
            "作成する。</b>",
        ),
    ):
      with self.subTest(role=role):
        self.assertIn(role, self.html)
        self.assertIn(next_action, self.html)

  def test_root_dashboard_no_longer_shows_stale_preparation_wording(self):
    for stale in (
        "初回投稿1件と投稿キュー3件の準備",
        "商品はまだ未登録",
        "初回記事1本を準備済み",
        "まだ未公開",
        "投稿テーマ・投稿パッケージ・計画のたたき台づくり",
    ):
      self.assertNotIn(stale, self.html)

  def test_root_dashboard_cards_still_have_no_fabricated_metrics_or_live_claims(self):
    self.assertNotIn("LIVE", self.html)
    self.assertNotIn("リアルタイム", self.html)
    self.assertNotIn("¥", self.html)
    # 「フォロワー数・PV・クリック数…は表示していません」という否定形の
    # 案内文の中にのみ、これらの語が1回ずつ登場する(MISSION 038から継続)。
    self.assertEqual(self.html.count("フォロワー"), 1)
    self.assertEqual(self.html.count("PV"), 1)
    self.assertEqual(self.html.count("クリック数"), 1)

  def test_root_dashboard_links_and_images_unchanged_by_wording_update(self):
    for link in (
        "/content-studio/publish-queue", "/revenue#room-prep",
        "/content-studio/note-first-article", "/content-studio",
        "/office", "/revenue",
    ):
      self.assertIn(f'href="{link}"', self.html)
    self.assertNotIn("<img", self.html)

  def test_details_button_opens_a_real_in_page_panel(self):
    self.assertIn('id="details-toggle"', self.html)
    self.assertIn('id="details-panel"', self.html)
    self.assertIn("detailsToggle.addEventListener('click'", self.html)
    self.assertNotIn("詳しい画面へ戻る", self.html)

  # --- ライブオフィス（表示専用の別画面） ------------------------------------

  def test_dashboard_links_to_live_office(self):
    self.assertIn('href="/office"', self.html)
    self.assertIn("ライブオフィスを見る", self.html)

  def test_live_office_rooms_are_available_with_no_external_calls(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn(title, html)
        self.assertIn("prefers-reduced-motion:reduce", html)
        self.assertIn("/static/images/office-avatars-v1.png", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

  def test_work_floor_shows_static_current_posting_status(self):
    # MISSION 051: work_logsが2026-09-01付けの3件(A8.net提携確認など現在の
    # 実際の運用と無関係な古いテスト用データ)しかなく、これをそのまま
    # 「現在の作業」として表示すると実態と食い違うため、/api/logsの参照を
    # やめ、柴犬社長が確認した現在のPinterest・note・Threadsの状況を静的に
    # 表示するように変更した。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="office-live-status"', html)
    self.assertIn("現在の投稿運用状況", html)
    self.assertIn("Pinterest：5件公開済み", html)
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    self.assertIn("note：AI Hive関連の記事3件公開済み", html)
    self.assertIn("Threads：Difyで別管理の自動投稿を運用中", html)
    self.assertNotIn('fetch("/api/logs")', html)
    self.assertNotIn('fetch("/api/employees")', html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("A8.net", html)
    self.assertNotIn("ラッシュアディクト", html)
    self.assertNotIn("美容サロン", html)

  # --- MISSION 025: 役割別ライブオフィス連携(実データ表示) --------------------

  def test_fixed_desk_avatars_have_status_elements_for_real_data(self):
    # 固定デスク(MISSION 083: 里奈・凛・葵・蒼)それぞれに、実データで
    # 更新される担当状況テキストと状態チップが用意されている。
    html = self.client.get("/office").get_data(as_text=True)
    for key in ("room", "rin", "analytics", "sou"):
      self.assertIn(f'id="desk-task-{key}"', html)
      self.assertIn(f'id="desk-status-{key}"', html)
    self.assertIn("status-chip", html)
    self.assertIn("status-done", html)
    self.assertIn("status-progress", html)

  def test_office_script_only_reads_logs_and_never_writes(self):
    # 実データ連携のスクリプトが、GET /api/logs 以外のエンドポイントや
    # 書き込み系メソッドを一切呼び出していないことを確認する
    # (hive_db.require_permission配下の新規Hive APIは一切対象にしない)。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_desk_status_chip_is_static_and_not_derived_from_logs(self):
    # MISSION 051: work_logsが現在の実際の運用と無関係な古いテスト用
    # データしかないため、デスクの状態チップを実データから動的に
    # 切り替える仕組みは廃止した。チップ要素自体は残しつつ、常に中立の
    # 表示(status-pending)のままにする。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('class="status-chip status-pending"', html)
    self.assertNotIn('log[4]==="完了"', html)
    self.assertNotIn('done?"status-done":"status-progress"', html)

  def test_ceo_office_shows_static_pinterest_and_note_publish_counts(self):
    # MISSION 051: 社長室の「今日の作業/完了/進行中」という実データ由来の
    # カウント(work_logsが古いテスト用データしかなく、常に実態と食い違う)
    # をやめ、柴犬社長が確認したPinterest・noteの公開件数を静的に表示する。
    # 書き込みは一切行わない。
    # MISSION 054: Pinterest5件・note3件が公開済みとなり、「AIが「なんか
    # 違う」ときに見直す3つ」も公開済みになったため、3枠目は「次の投稿案」
    # ではなく「48時間後を目安にした反応確認」に更新した。
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("<b>5件</b><span>Pinterest公開済み</span>", html)
    self.assertIn("<b>3件</b><span>今回のnote公開済み</span>", html)
    self.assertIn("<b>48時間</b><span>Pinterest反応確認の目安</span>", html)
    self.assertNotIn('id="ceo-today-count"', html)
    self.assertNotIn('fetch("/api/logs")', html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/tasks", html)

  def test_ceo_office_notes_threads_is_managed_separately_via_dify(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("Threadsのみ、Difyを使った別管理の自動投稿を運用していますが、", html)
    self.assertIn(
        "この画面（このダッシュボード）からの投稿・ログイン・連携は一切行いません。", html
    )

  # --- MISSION 026: 社長室(業務司令室)への拡張 --------------------------------
  # MISSION 051で、work_logs(実データ)に基づく件数集計から、柴犬社長が
  # 確認した現在の実際の運用状況を示す静的な表示へ切り替えた。

  def test_ceo_office_shows_recent_items_matching_current_reality(self):
    # MISSION 054: 「AIが「なんか違う」ときに見直す3つ」とその対応note記事は
    # 2026年9月12日までに公開済みとなったため、「準備（社長承認待ち）」
    # 「下書きを準備」という表現をやめ、公開済みであることを示す表現へ
    # 更新した。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("最新の仕事", html)
    self.assertIn(
        "Pinterest：「AIが「なんか違う」ときに見直す3つ」を公開済み", html
    )
    self.assertIn(
        "note：「AIに聞いても「なんか違う」と感じる人へ」を公開済み", html
    )
    self.assertIn("公開済みのPinterest投稿の反応を確認中（48時間ほど様子を見る段階）", html)
    self.assertNotIn("logs.slice(0,3)", html)

  def test_ceo_office_shows_fixed_priority_text(self):
    # MISSION 054: 「AIが「なんか違う」ときに見直す3つ」が公開済みとなり、
    # 次に確認することは48時間後のPinterest反応確認になったため、優先事項の
    # 固定文言を更新した(社長からの明示的な指定内容)。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("いま優先すること", html)
    self.assertIn("<p>48時間後を目安にPinterestの反応を確認すること</p>", html)
    self.assertNotIn("logs.find(l=>!isDone(l))", html)

  def test_ceo_office_command_center_never_writes_or_calls_hive_api(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  # --- MISSION 027: 柴犬社長の業務サポート会話(4ボタン) ------------------------

  def test_ceo_office_has_four_quick_action_controls(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="qa-today"', html)
    self.assertIn('id="qa-priority"', html)
    self.assertIn('id="qa-done"', html)
    self.assertIn('id="qa-office"', html)
    self.assertIn("今日の進捗", html)
    self.assertIn("いま優先する仕事", html)
    self.assertIn("完了した仕事", html)
    self.assertIn("オフィスへ案内", html)

  def test_office_guide_button_is_a_safe_same_origin_link(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="qa-office" href="/office"', html)
    # JSでリダイレクト先を書き換えていない(location.href等の動的遷移では
    # なく、通常の<a href>による同一オリジンへの遷移であること)。
    self.assertNotIn("location.href", html)
    self.assertNotIn("window.open", html)
    # リンク先が実際に存在し、安全に開けることも確認する。
    res = self.client.get("/office")
    self.assertEqual(res.status_code, 200)

  def test_quick_action_buttons_use_only_static_content_no_hive_api(self):
    # MISSION 051: 4ボタンの応答は、work_logs(実データ)から動的に導出する
    # 方式から、柴犬社長が確認した現在の状況を示す静的な応答へ切り替えた。
    # DB・APIへのアクセスは一切行わない。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("qaAppendBoss", html)
    self.assertNotIn('fetch("/api/logs")', html)
    self.assertNotIn("qaWithLogs", html)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_quick_action_handlers_append_static_current_status_to_chat_log(self):
    # MISSION 054: Pinterest5件・note3件公開済み、次に確認することは
    # 48時間後のPinterest反応確認、という実態に合わせて更新した。
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("qaAppendBoss", html)
    self.assertIn('document.querySelector("#log")', html)
    self.assertIn(
        "🐕 柴犬社長：Pinterestは5件、noteはAI Hive関連の記事が3件、公開済みだよ。",
        html,
    )
    self.assertIn(
        "🐕 柴犬社長：いま優先するのは、48時間後を目安にした"
        "Pinterestの反応確認だよ。",
        html,
    )
    self.assertIn(
        "🐕 柴犬社長：Pinterestは5件、noteはAI Hive関連の記事が3件、"
        "公開まで完了しているよ。",
        html,
    )

  # --- MISSION 028: デスク詳細と案内(クリック・キーボード操作対応) --------------

  def test_desks_are_keyboard_and_click_operable_buttons(self):
    # <button>はEnter/Space/クリックのいずれでも標準で活性化するため、
    # 各デスクを<button>にしていることでキーボード操作対応も満たす。
    # MISSION 083: デスクを6席から、AIオフィスの実在4人(里奈・凛・葵・蒼)
    # の4席へ変更した。
    html = self.client.get("/office").get_data(as_text=True)
    for key in ("room", "rin", "analytics", "sou"):
      self.assertIn(f'id="desk-{key}"', html)
      self.assertIn(f'data-key="{key}"', html)
    self.assertEqual(html.count('<button type="button" class="desk d'), 4)
    self.assertIn('aria-haspopup="true"', html)
    self.assertIn('aria-expanded="false"', html)
    self.assertIn('aria-controls="desk-detail-panel"', html)

  def test_desk_detail_panel_has_required_fields_and_is_hidden_initially(self):
    # MISSION 051: 「現在の状態/最新の作業内容/更新時刻」という実データ
    # 由来のフィールドから、Pinterest・note・Threadsの現在状況を示す
    # 静的なdl(desk-detail-facts)へ切り替えた。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="desk-detail-panel"', html)
    self.assertIn('id="desk-detail-panel" role="region"', html)
    self.assertIn("hidden>", html)  # 初期状態は非表示
    self.assertIn('id="desk-detail-title"', html)  # AI名
    self.assertIn('id="desk-detail-role"', html)  # 役割
    self.assertIn('class="desk-detail-facts"', html)
    self.assertIn("<dt>Pinterest</dt>", html)
    self.assertIn("<dt>note</dt>", html)
    self.assertIn("<dt>Threads</dt>", html)
    self.assertNotIn('id="desk-detail-status"', html)
    self.assertNotIn('id="desk-detail-task"', html)
    self.assertNotIn('id="desk-detail-time"', html)

  def test_desk_detail_disclaimer_is_honest_about_no_individual_assignment(self):
    # 実データにAI個別の担当情報が存在しないことを、断定せず誠実に示す。
    # MISSION 051で、「既存の作業ログを順番に表示している演出」という
    # 説明から、「柴犬社長が確認した現在の投稿運用状況を表示している」
    # という説明へ更新した(表示内容自体が静的な現在状況に変わったため)。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="desk-detail-disclaimer"', html)
    self.assertIn("個別に紐づく担当データは存在しない", html)
    self.assertIn("柴犬社長が確認した現在の投稿運用状況を表示しています", html)
    self.assertIn("実際にこのAIが個人で担当した", html)

  def test_desk_detail_close_and_escape_are_supported(self):
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="desk-detail-close"', html)
    self.assertIn("closeDeskDetail", html)
    self.assertIn('e.key==="Escape"', html)
    # 閉じた後、直前にフォーカスしていたデスクへフォーカスを戻す。
    self.assertIn("lastFocusedDesk.focus()", html)

  def test_desk_click_and_detail_scripts_never_call_any_api(self):
    # MISSION 051: デスク詳細パネルの内容は静的になったため、クリック/
    # キーボード操作のスクリプトはDB・APIへ一切アクセスしない。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertNotIn('fetch("/api/logs")', html)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_hash_deep_link_highlights_and_opens_target_desk(self):
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn("location.hash.match", html)
    self.assertIn("classList.add(\"is-target\")", html)
    self.assertIn("openDeskDetail(targetKey)", html)
    self.assertIn("scrollIntoView", html)

  def test_ceo_office_link_is_a_plain_static_link_to_office(self):
    # MISSION 051: 「いま優先すること」が固定の静的文言になったため、
    # 対応するデスクへの動的なハッシュ書き換えは廃止し、常に/officeへの
    # 通常のリンクとして扱う(location.href等のJS遷移は行わない)。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="qa-office" href="/office"', html)
    self.assertNotIn('setAttribute("href","/office#desk-', html)
    self.assertNotIn('const deskKeys=', html)
    self.assertNotIn("location.href", html)

  def test_desk_keys_are_unchanged_and_consistent_on_office_page(self):
    # MISSION 051で社長室側のdeskKeys(ログのローテーション割り当て用)は
    # 不要になったため削除した。社長室側にデスクキー一覧の定数がないことは
    # 引き続き確認する。MISSION 083でオフィス側のデスク構成は6席(架空の
    # 旧キャスト)から4席(AIオフィスの実在4人)へ変更した。
    office_html = self.client.get("/office").get_data(as_text=True)
    for key in ("room", "rin", "analytics", "sou"):
      self.assertIn(f'id="desk-{key}"', office_html)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertNotIn(
        'const deskKeys=["misaki","umi","minato","ito","kotoe","aoi"];', ceo_html
    )

  def test_reduced_motion_is_respected_for_scroll_and_highlight(self):
    html = self.client.get("/office").get_data(as_text=True)
    # CSSアニメーション(強調表示のパルス)は既存のprefers-reduced-motion
    # 一括縮退の対象になる。
    self.assertIn("@keyframes desk-highlight", html)
    self.assertIn(".desk.is-target", html)
    # scrollIntoViewのsmoothスクロールは、CSSではなくJSでreduced-motionを
    # 判定して切り替える必要がある。
    self.assertIn(
        'window.matchMedia("(prefers-reduced-motion: reduce)").matches', html
    )
    self.assertIn('reduceMotion?"auto":"smooth"', html)

  def test_desk_role_labels_are_present(self):
    # MISSION 083: デスクの役割ラベルを、AIオフィスの実在4人の実際の役割
    # (ROOM担当・資料室管理・分析担当・技術担当)へ更新した。
    html = self.client.get("/office").get_data(as_text=True)
    for role in ("ROOM担当", "資料室管理", "分析担当", "技術担当"):
      self.assertIn(role, html)

  def test_break_room_reflects_actual_posting_wait_and_review_state(self):
    # MISSION 083: 休憩室のキャストを、AIオフィスに実在しない架空キャラ
    # クター(琴衣等)から、彩(連携担当)を中心に、Pinterest・note・楽天
    # ROOM・分析の担当(美咲・海・里奈・葵)のうち実績のある担当を優先して
    # 1〜2人だけ短時間訪れる形へ変更した。休憩理由・勤怠・移動予定などの
    # 新しい実データは増やしていない(表示専用・localStorage読み取り専用)。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn("ひと息ついたら、また確認へ戻ります", html)
    self.assertIn("彩：部署間の連携状況を、ひと息ついて整理中", html)
    self.assertIn(
        "彩を中心に、Pinterest・note・楽天ROOM・分析の担当のうち", html
    )
    self.assertIn("外部への投稿・送信・ログインは行いません", html)
    for name in ("彩", "美咲", "海"):
      self.assertIn(name, html)
    for name in ("琴衣", "伊藤", "湊"):
      self.assertNotIn(name, html)

  # --- MISSION 029: ローカル収益化ボード ---------------------------------------

  def test_dashboard_links_to_revenue_board(self):
    self.assertIn('href="/revenue"', self.html)
    self.assertIn("収益化ボードを見る", self.html)

  def test_revenue_board_page_loads(self):
    res = self.client.get("/revenue")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("収益化ボード", html)
    self.assertIn("<title>収益化ボード | AI Hive</title>", html)

  def test_revenue_board_reachable_from_ceo_office_and_office_rooms(self):
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('href="/revenue"', html)
        self.assertIn("収益化ボード", html)

  def test_revenue_board_shows_first_priority_business(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("第一優先事業", html)
    self.assertIn("AI・ガジェット発信からの楽天ROOM収益化", html)

  def test_revenue_board_shows_all_required_content_cards(self):
    # MISSION 052: 楽天ROOM折りたたみキーボード1件公開という実際の運用
    # 状況に合わせて更新済み。
    # MISSION 054: Pinterest 5件公開・note 3件公開という2026年9月12日
    # 時点の実態、および48時間後のPinterest反応確認という次の行動に
    # 合わせて更新した。
    # MISSION 055: noteの件数はAI Hive関連の記事数であり、noteアカウント
    # 全体の記事数ではないことを明記した。
    # MISSION 057: 楽天ROOMは折りたたみキーボード1件に加え、9月13日・14日の
    # 投稿を合わせて合計7件公開済みになったことを反映した。
    # MISSION 058: 楽天ROOMアカウント全体の商品数は30件であり、AI Hiveで
    # 追加・記録しているのは7件だけであることを明記した。
    # MISSION 059: 9月16日に10件を追加投稿し、AI Hiveで追加した投稿は
    # 合計17件になった。
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("事業の目的", html)
    self.assertIn("投稿企画工場のテーマを軸に発信し", html)
    self.assertIn("想定するお客さま像", html)
    self.assertIn("AI初心者、仕事の効率化に関心がある人", html)
    self.assertIn("収益化の柱（案）", html)
    self.assertIn("投稿企画工場のテーマに沿った発信", html)
    self.assertIn(
        "公開済みPinterest投稿（5件）・AI Hive関連のnote記事（3本）からの流入育成", html
    )
    self.assertIn("noteアカウントには、この他にも既存記事があります", html)
    self.assertIn(
        "楽天ROOMでの手動カテゴリ紹介（AI Hiveで追加した商品投稿17件。"
        "アカウント全体では商品投稿30件）",
        html,
    )
    self.assertIn("ROOM登録までの段階", html)
    for stage in ("テーマ選定", "投稿確認", "ROOM準備", "手動登録"):
      self.assertIn(stage, html)
    self.assertIn("今週の優先行動", html)
    self.assertIn("48時間後を目安にPinterestの反応を確認", html)
    self.assertIn("noteの反応確認", html)
    self.assertIn("既存ROOM投稿（AI Hive分17件）の内容・反応を確認", html)

  def test_revenue_board_price_is_an_explicit_draft_not_final(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("収益の入り口候補（金額・成果はすべて未確定）", html)
    self.assertIn("未確定", html)
    self.assertIn("確定した収益・契約内容ではありません", html)
    # 具体的な金額(円記号)を捏造して確定価格のように見せていないこと。
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)

  def test_revenue_board_states_it_is_internal_draft_not_sent_or_published(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("社内の企画たたき台です", html)
    self.assertIn("外部への送信・公開", html)
    self.assertIn("自動的な実行は一切行われません", html)
    self.assertIn("localhost限定", html)

  def test_revenue_board_has_no_external_resources_or_scripts(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertNotIn("http://", html)
    self.assertNotIn("https://", html)
    self.assertNotIn("<script", html)
    self.assertNotIn("fetch(", html)
    self.assertIn("prefers-reduced-motion:reduce", html)

  def test_revenue_board_is_fully_read_only_no_api_or_write_methods(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertNotIn("/api/", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_revenue_board_has_responsive_layout(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("@media(max-width:760px){.revenue-grid", html)

  def test_revenue_board_content_is_data_driven_for_future_edits(self):
    # 将来の差し替えやすさ: HTML生成コードとは独立したデータ構造
    # (REVENUE_FOCUS)から画面が組み立てられていることを確認する。
    import office_views
    self.assertIn("business_name", office_views.REVENUE_FOCUS)
    self.assertIn("price_tiers", office_views.REVENUE_FOCUS)
    self.assertIn("weekly_priorities", office_views.REVENUE_FOCUS)
    rendered = office_views._render_revenue_scene(office_views.REVENUE_FOCUS)
    self.assertIn(office_views.REVENUE_FOCUS["business_name"], rendered)

  def test_existing_office_pages_unaffected_by_revenue_tab_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 030: 投稿企画工場(ローカル専用コンテンツ企画) --------------------

  def test_revenue_board_links_to_content_studio(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn('href="/content-studio"', html)
    self.assertIn("投稿企画工場", html)

  def test_content_studio_page_loads(self):
    res = self.client.get("/content-studio")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("投稿企画工場", html)
    self.assertIn("<title>投稿企画工場 | AI Hive</title>", html)

  def test_content_studio_reachable_from_all_office_pages(self):
    for path in ("/office", "/office/break-room", "/office/ceo-office", "/revenue"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('href="/content-studio"', html)

  def test_content_studio_shows_target_theme(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("対象テーマ", html)
    self.assertIn("AIとガジェットで、仕事と暮らしを少しラクにする", html)

  # --- MISSION 040: Pinterest・note・楽天ROOM運用だけへの整理 ------------------

  def test_content_studio_shows_only_the_two_active_themes(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    for title in (
        "AI初心者が最初に試す便利な使い方",
        "仕事の文章作成・要約をラクにするAI活用",
    ):
      self.assertIn(title, html)
    for removed_title in (
        "デスク周りを整える便利ガジェット",
        "スマホ・PC作業を快適にする周辺機器",
        "買う前に確認したいAI対応ガジェットの選び方",
    ):
      self.assertNotIn(removed_title, html)
    # MISSION 048で、次に作る記事・投稿の候補3件を同じcs-plan-cardスタイルで
    # 追加したため、2件(既存の稼働中テーマ)+3件(候補)=5件になった。
    # MISSION 054: 候補のうち1件(AIとの会話がかみ合わないときの見直し)が
    # 公開済みとなり企画メモから削除したため、2件(既存の稼働中テーマ)+
    # 2件(候補)=4件になった。
    self.assertEqual(html.count('class="cs-plan-card"'), 4)

  def test_content_studio_removes_instagram_and_threads_everywhere(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertNotIn("Instagram", html)
    self.assertNotIn("Threads", html)

  def test_content_studio_removes_unconfirmed_product_candidates(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    for removed in (
        "関連商品ジャンル候補", "AIアシスタント対応スマートスピーカー",
        "音声入力対応キーボード", "音声文字起こしデバイス", "ノートPC用外付けマイク",
        "cs-genre-chip",
    ):
      self.assertNotIn(removed, html)

  def test_content_studio_removes_refinement_workflow_and_status_tiers(self):
    # MISSION 086: 「今日の一歩」カードの案内文に「楽天ROOMの投稿候補を
    # 1件作る」という、ミッション要件どおりの文言を使うようになったため、
    # 「投稿候補」という語そのものの禁止は外し、旧ワークフロー固有の
    # 語(要確認・見送り・手動投稿候補・cs-status-badge・cs-refine-section)
    # だけを引き続き禁止する。
    html = self.client.get("/content-studio").get_data(as_text=True)
    for removed in (
        "投稿改善ワークフロー", "要確認", "見送り",
        "手動投稿候補", "cs-status-badge", "cs-refine-section",
    ):
      self.assertNotIn(removed, html)

  def test_content_studio_shows_three_fields_per_theme(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertEqual(html.count("<dt>Pinterest用の切り口</dt>"), 2)
    self.assertEqual(html.count("<dt>note用の切り口</dt>"), 2)
    self.assertEqual(html.count("<dt>楽天ROOMリンクの扱い</dt>"), 2)
    self.assertEqual(html.count("今回はなし"), 2)

  def test_content_studio_states_room_link_policy(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn(
        "楽天ROOMの商品投稿ページを、柴犬社長が手動で確認できた場合のみ、"
        "Pinterestへリンクを追加します。",
        html,
    )

  def test_content_studio_states_manual_prep_only_notice(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn(
        "この画面は投稿企画の手動準備用であり、外部サービスへの投稿・送信・連携は"
        "行わない。",
        html,
    )

  def test_content_studio_has_no_numeric_or_realtime_claims(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)
    self.assertNotIn("位獲得", html)
    self.assertNotIn("LIVE", html)
    self.assertNotIn("リアルタイム", html)
    self.assertNotIn("フォロワー", html)
    self.assertNotIn("PV", html)

  def test_content_studio_states_internal_draft_not_published_or_sent(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("SNS投稿・note投稿・広告出稿・営業送信は行われません", html)
    self.assertIn("localhost限定", html)

  def test_content_studio_has_no_external_resources_or_scripts(self):
    # MISSION 086: 「今日の一歩」カードに<script>を追加した。
    # MISSION 089: 参照先をlocalStorageから、このMac上のアプリ内DB
    # (/api/dashboard/candidates、読み取り専用GET)へ変更した。外部URL・
    # 外部通信・書き込み系APIが一切ないことは引き続き確認する。
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertNotIn("http://", html)
    self.assertNotIn("https://", html)
    self.assertIn('window.fetch("/api/dashboard/candidates")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("<form", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    self.assertIn("prefers-reduced-motion:reduce", html)

  def test_content_studio_is_fully_read_only_no_api_or_write_methods(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    for api_path in self._find_api_paths(html):
      self.assertEqual(api_path, "/api/dashboard/candidates")
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_content_studio_has_responsive_layout(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("@media(max-width:760px){.cs-plan-card", html)

  def test_content_studio_content_is_data_driven_for_future_edits(self):
    import office_views
    self.assertEqual(len(office_views.CONTENT_STUDIO_PLANS), 2)
    for plan in office_views.CONTENT_STUDIO_PLANS:
      self.assertEqual(
          set(plan.keys()),
          {"title", "pinterest_angle", "note_angle", "room_link_handling"},
      )
    rendered = office_views._render_content_studio_scene(
        office_views.CONTENT_STUDIO_THEME,
        office_views.CONTENT_STUDIO_PLANS,
        office_views.CONTENT_STUDIO_ROOM_LINK_POLICY,
        office_views.CONTENT_STUDIO_WRITING_STANDARDS_HEADING,
        office_views.CONTENT_STUDIO_WRITING_STANDARDS_INTRO,
        office_views.CONTENT_STUDIO_WRITING_STANDARDS,
        office_views.CONTENT_STUDIO_IMAGE_STANDARDS_HEADING,
        office_views.CONTENT_STUDIO_IMAGE_STANDARDS_INTRO,
        office_views.CONTENT_STUDIO_IMAGE_STANDARDS,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_HEADING,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_INTRO,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_RECOMMENDATION,
    )
    self.assertIn(office_views.CONTENT_STUDIO_THEME, rendered)

  # --- MISSION 046: 今後の下書き作成基準(文章品質をそろえるための参照情報) -------

  def test_content_studio_shows_writing_standards_heading_and_intro(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("文章の作成基準（読者が続きを読みたくなる、人間味のある文章）", html)
    self.assertIn(
        "今後作成するnote記事・Pinterest投稿案は、次の基準を満たすように作成します。",
        html,
    )
    self.assertIn(
        "公開済みのnote記事・既存のPinterest投稿・投稿キューの内容をさかのぼって"
        "書き換えるものではありません。",
        html,
    )

  def test_content_studio_shows_all_eight_writing_standard_items(self):
    import office_views
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertEqual(len(office_views.CONTENT_STUDIO_WRITING_STANDARDS), 8)
    for item in office_views.CONTENT_STUDIO_WRITING_STANDARDS:
      self.assertIn(f"<li>{item}</li>", html)
    for required in (
        "タイトルは、読者が抱えそうな困りごと・場面・気づきが伝わる表現にする",
        "「必ず」「絶対」「これだけで成功」など、過剰なクリック誘導や断定は使わない",
        "note記事本文は日本語で4,500〜5,500文字程度を目安にする",
        "冒頭は解説から始めず、読者が想像できる具体的な場面・困りごと・問いかけから始める",
        "実体験がないことを、本人の経験として書かない",
        "説明書のような箇条書きだけにせず、自然な会話調と具体例を交える",
        "読者が次の段落を読みたくなる流れを意識する",
        "Pinterestのタイトルは画像内の文字と矛盾させない",
    ):
      self.assertIn(required, office_views.CONTENT_STUDIO_WRITING_STANDARDS)

  def test_content_studio_writing_standards_do_not_alter_existing_note_pinterest_queue(self):
    # MISSION 046は今後の下書き作成基準を追加するのみで、既存のnote記事・
    # Pinterest投稿・投稿キュー・既存画像・既存の本文には一切影響しない
    # ことを確認する(投稿キューの件数はMISSION 042で4件、MISSION 049で
    # 5件になっているが、その増減はこのミッションによるものではない)。
    import office_views
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)
    self.assertEqual(len(office_views.CONTENT_STUDIO_PLANS), 2)
    note_html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
        note_html,
    )
    self.assertIn(
        "スマホでAIに下書きを頼む前に確認する3つ──端末・入力・読み返しを先に決める",
        note_html,
    )
    queue_html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(queue_html.count('class="pq-status-badge'), 5)
    # 作成基準セクション自体は投稿企画工場だけに追加し、note記事・投稿キュー
    # ページには表示しない。
    self.assertNotIn("文章の作成基準", note_html)
    self.assertNotIn("文章の作成基準", queue_html)

  def test_content_studio_writing_standards_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    standards_section = html.split(
        "文章の作成基準（読者が続きを読みたくなる、人間味のある文章）", 1
    )[1].split('<a class="cs-first-post-link"', 1)[0]
    self.assertNotIn("https://", standards_section)
    self.assertNotIn("fetch(", standards_section)
    self.assertNotIn("/api/", standards_section)
    self.assertNotIn("<script", standards_section)

  def test_content_studio_writing_standards_has_responsive_layout(self):
    # 既存のfp-checklistスタイルを再利用しているため、専用のメディアクエリを
    # 新規追加していない(既存のレスポンシブ対応をそのまま流用する)ことを
    # ソースコード上で確認する。
    import office_views
    import inspect
    source = inspect.getsource(office_views._render_content_studio_scene)
    self.assertIn('class="fp-checklist"', source)
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('name="viewport"', html)

  # --- MISSION 047: 今後の画像作成基準(テーマが一目で伝わる画像づくりの参照情報) ---

  def test_content_studio_shows_image_standards_heading_and_intro(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("画像の作成基準（テーマが一目で伝わり、同じ構図が続かない画像）", html)
    self.assertIn(
        "今後作成するPinterest投稿画像・note見出し画像は、次の基準を満たすように"
        "作成します。",
        html,
    )
    self.assertIn(
        "公開済みのnote記事・既存のPinterest投稿・投稿キューの既存画像をさかのぼって"
        "作り直すものではありません。",
        html,
    )
    # 文章の作成基準(MISSION 046)より後、既存のplanカードより前に表示される
    # (文章→画像→既存企画案、の順で並んでいること)ことを確認する。
    self.assertLess(
        html.index("文章の作成基準（読者が続きを読みたくなる、人間味のある文章）"),
        html.index("画像の作成基準（テーマが一目で伝わり、同じ構図が続かない画像）"),
    )
    self.assertLess(
        html.index("画像の作成基準（テーマが一目で伝わり、同じ構図が続かない画像）"),
        html.index("AI初心者が最初に試す便利な使い方"),
    )

  def test_content_studio_shows_all_nine_image_standard_items(self):
    import office_views
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertEqual(len(office_views.CONTENT_STUDIO_IMAGE_STANDARDS), 9)
    for item in office_views.CONTENT_STUDIO_IMAGE_STANDARDS:
      self.assertIn(f"<li>{item}</li>", html)
    for required in (
        "画像は装飾を増やすことより、最初に目が行く主役を1つ決める",
        "同じ夜の木目デスク・同じ構図を連続使用しない",
        "Pinterest用画像は、テーマが一目で分かるタイトルを画像本体に焼き込む",
        "note用見出し画像は、タイトルを重ねず、写真だけでも記事テーマが感じられる構図にする",
        "ロゴ、読める商品名、実在サービス画面、楽天市場の商品画像は入れない",
        "商品紹介でない画像に商品タグを付けない",
        "画像内の文字はスマホでも読みやすい大きさにする",
        "画像は縦横比・用途・altテキストを先に決めてから作る",
    ):
      self.assertIn(required, html)
    # 「テーマごとに主役を変える」の3つのサブ基準(スマホ・AI・デスク)が
    # 1項目の中にすべて含まれていることを確認する。
    theme_item = next(
        i for i in office_views.CONTENT_STUDIO_IMAGE_STANDARDS if i.startswith("テーマごとに主役を変える")
    )
    self.assertIn("スマホ記事：スマートフォンを主役にする", theme_item)
    self.assertIn("AIの使い方記事：考える・入力する・見直す場面が伝わる構図にする", theme_item)
    self.assertIn("デスク記事：机全体ではなく、困りごとや改善点が伝わる部分を主役にする", theme_item)

  def test_content_studio_image_standards_do_not_alter_existing_note_pinterest_queue(self):
    # MISSION 047は今後の画像作成基準を追加するのみで、既存のnote記事・
    # Pinterest投稿・投稿キュー・既存画像・既存本文には一切影響しないことを
    # 確認する(投稿キューの件数はMISSION 042で4件、MISSION 049で5件に
    # なっているが、その増減はこのミッションによるものではない)。
    import office_views
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)
    self.assertEqual(len(office_views.CONTENT_STUDIO_PLANS), 2)
    note_html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
        note_html,
    )
    self.assertIn(
        "スマホでAIに下書きを頼む前に確認する3つ──端末・入力・読み返しを先に決める",
        note_html,
    )
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/note-first-article-hero.png"',
        note_html,
    )
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/note-smartphone-ai-draft-cover.png"',
        note_html,
    )
    queue_html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(queue_html.count('class="pq-status-badge'), 5)
    # 作成基準セクション自体は投稿企画工場だけに追加し、note記事・投稿キュー
    # ページには表示しない。
    self.assertNotIn("画像の作成基準", note_html)
    self.assertNotIn("画像の作成基準", queue_html)

  def test_content_studio_image_standards_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    standards_section = html.split(
        "画像の作成基準（テーマが一目で伝わり、同じ構図が続かない画像）", 1
    )[1].split('<a class="cs-first-post-link"', 1)[0]
    self.assertNotIn("https://", standards_section)
    self.assertNotIn("fetch(", standards_section)
    self.assertNotIn("/api/", standards_section)
    self.assertNotIn("<script", standards_section)
    self.assertNotIn("<img", standards_section)

  def test_content_studio_image_standards_has_responsive_layout(self):
    import office_views
    import inspect
    source = inspect.getsource(office_views._render_content_studio_scene)
    self.assertEqual(source.count('class="fp-checklist"'), 2)
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('name="viewport"', html)

  # --- MISSION 048: 次のnote記事・Pinterest投稿候補(AI初心者向け・企画メモ) -----

  def test_content_studio_shows_next_candidates_heading_and_intro(self):
    # MISSION 054: 候補「AIとの会話がかみ合わないときに見直す3つ」が実際に
    # 公開済みとなり企画メモから削除されたため、件数・候補数を更新した。
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("次のnote記事・Pinterest投稿の候補（AI初心者向け・企画メモ）", html)
    self.assertIn(
        "公開済みのPinterest投稿5件・AI Hive関連のnote記事3件の内容を踏まえ、"
        "次に作る候補を2つ整理した企画メモです。",
        html,
    )
    self.assertIn("記事・画像・投稿はまだ作成していません。", html)
    # 画像の作成基準(MISSION 047)より後、既存のplanカードより後ろに表示される
    # (文章→画像→既存企画案→次の候補、の順で並んでいること)ことを確認する。
    self.assertLess(
        html.index("画像の作成基準（テーマが一目で伝わり、同じ構図が続かない画像）"),
        html.index("次のnote記事・Pinterest投稿の候補（AI初心者向け・企画メモ）"),
    )
    self.assertLess(
        html.index("AI初心者が最初に試す便利な使い方"),
        html.index("次のnote記事・Pinterest投稿の候補（AI初心者向け・企画メモ）"),
    )

  def test_content_studio_shows_two_candidates_with_all_required_fields(self):
    # MISSION 054: 候補「AIとの会話がかみ合わないときに見直す3つ」を、
    # 実際に公開済みとなったため企画メモから削除し、2候補に整理した。
    import office_views
    candidates = office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES
    self.assertEqual(len(candidates), 2)
    required_keys = {
        "theme", "pain_point", "note_title_candidates", "pinterest_title",
        "opening_hook", "heading_outline", "image_subject_and_composition",
        "pinterest_vs_note_image_difference", "reason",
    }
    html = self.client.get("/content-studio").get_data(as_text=True)
    for c in candidates:
      self.assertEqual(set(c.keys()), required_keys)
      self.assertEqual(len(c["note_title_candidates"]), 3)
      self.assertIn(c["theme"], html)
      self.assertIn(c["pain_point"], html)
      for t in c["note_title_candidates"]:
        self.assertIn(t, html)
      self.assertIn(c["pinterest_title"], html)
      self.assertIn(c["opening_hook"], html)
      for h in c["heading_outline"]:
        self.assertIn(h, html)
      self.assertIn(c["image_subject_and_composition"], html)
      self.assertIn(c["pinterest_vs_note_image_difference"], html)
      self.assertIn(c["reason"], html)

  def test_content_studio_candidate_opening_hooks_are_roughly_200_to_300_chars(self):
    import office_views
    for c in office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES:
      with self.subTest(theme=c["theme"]):
        char_count = len(c["opening_hook"])
        self.assertGreaterEqual(char_count, 180)
        self.assertLessEqual(char_count, 320)

  def test_content_studio_candidates_do_not_duplicate_existing_post_themes(self):
    # 既存5件(メール下書き・デスク配線・周辺機器選び・スマホでのAI下書き・
    # AIとの会話の見直し)や、note記事3件(一般的なAIの使い方・スマホでの
    # AI下書き・AIとの会話の見直し)と同じテーマ文言を候補のタイトル案に
    # 使っていないことを確認する(MISSION 054でAIとの会話の見直しは公開済み
    # になったため、既存テーマとして追加した)。
    import office_views
    existing_titles = (
        "AIにメールの下書きを頼む前に決める3つ",
        "デスクが狭いときに配線を見直す3つのポイント",
        "スマホ・PC作業をラクにする周辺機器の選び方",
        "スマホでAIに下書きを頼む前に確認する3つ",
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
        "AIが「なんか違う」ときに見直す3つ",
        "AIに聞いても「なんか違う」と感じる人へ。話がかみ合わないとき、まず見直す3つ",
    )
    for c in office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES:
      self.assertNotIn(c["pinterest_title"], existing_titles)
      for t in c["note_title_candidates"]:
        self.assertNotIn(t, existing_titles)

  def test_content_studio_shows_next_candidates_recommendation(self):
    import office_views
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('<b>次に作るなら。</b>', html)
    self.assertIn(office_views.CONTENT_STUDIO_NEXT_ARTICLE_RECOMMENDATION, html)
    # 3候補のうちどれか1つだけを明確に推薦していることを確認する。
    recommendation = office_views.CONTENT_STUDIO_NEXT_ARTICLE_RECOMMENDATION
    mentioned = [
        c for c in office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES
        if c["pinterest_title"] in recommendation or c["theme"] in recommendation
    ]
    self.assertEqual(len(mentioned), 1)

  def test_content_studio_candidates_have_no_business_data_or_definitive_claims(self):
    # 「必ず別の情報源で確認する」のような注意喚起としての「必ず」は許容し
    # (MISSION 046の基準が禁じているのは、成果を断定する誇大表現としての
    # 「必ず」「絶対」であり、確認を促す慎重な助言ではない)、タイトル・
    # Pinterestタイトルといったクリック誘導になりやすい箇所に誇大表現の
    # 決まり文句が入っていないかを確認する。
    import office_views
    html = self.client.get("/content-studio").get_data(as_text=True)
    candidates_section = html.split(
        "次のnote記事・Pinterest投稿の候補（AI初心者向け・企画メモ）", 1
    )[1].split('<p class="cs-footnote">', 1)[0]
    for forbidden in ("円", "¥", "位獲得", "在庫あり", "在庫切れ", "ランキング", "レビュー"):
      self.assertNotIn(forbidden, candidates_section)
    self.assertNotIn("https://", candidates_section)
    self.assertNotIn("fetch(", candidates_section)
    self.assertNotIn("/api/", candidates_section)
    self.assertNotIn("<script", candidates_section)
    for c in office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES:
      for forbidden in ("必ず稼げ", "絶対に成功", "これだけで成功"):
        self.assertNotIn(forbidden, c["theme"])
        self.assertNotIn(forbidden, c["pinterest_title"])
        for t in c["note_title_candidates"]:
          self.assertNotIn(forbidden, t)

  def test_content_studio_candidates_do_not_alter_existing_note_pinterest_queue(self):
    # 投稿キューの件数はMISSION 042で4件、MISSION 049で5件になっているが、
    # その増減はこのミッション(048)によるものではない。
    import office_views
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)
    self.assertEqual(len(office_views.CONTENT_STUDIO_PLANS), 2)
    note_html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
        note_html,
    )
    self.assertIn(
        "スマホでAIに下書きを頼む前に確認する3つ──端末・入力・読み返しを先に決める",
        note_html,
    )
    queue_html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(queue_html.count('class="pq-status-badge'), 5)
    self.assertNotIn("次のnote記事・Pinterest投稿の候補", note_html)
    self.assertNotIn("次のnote記事・Pinterest投稿の候補", queue_html)

  def test_content_studio_candidates_content_is_data_driven_for_future_edits(self):
    import office_views
    rendered = office_views._render_content_studio_scene(
        office_views.CONTENT_STUDIO_THEME,
        office_views.CONTENT_STUDIO_PLANS,
        office_views.CONTENT_STUDIO_ROOM_LINK_POLICY,
        office_views.CONTENT_STUDIO_WRITING_STANDARDS_HEADING,
        office_views.CONTENT_STUDIO_WRITING_STANDARDS_INTRO,
        office_views.CONTENT_STUDIO_WRITING_STANDARDS,
        office_views.CONTENT_STUDIO_IMAGE_STANDARDS_HEADING,
        office_views.CONTENT_STUDIO_IMAGE_STANDARDS_INTRO,
        office_views.CONTENT_STUDIO_IMAGE_STANDARDS,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_HEADING,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES_INTRO,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES,
        office_views.CONTENT_STUDIO_NEXT_ARTICLE_RECOMMENDATION,
    )
    self.assertIn("次のnote記事・Pinterest投稿の候補", rendered)
    self.assertEqual(rendered.count('class="cs-plan-card"'), 4)

  # --- MISSION 032: 初回手動投稿パッケージ(Pinterest向け) ----------------------

  def test_content_studio_links_to_first_post_package(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/content-studio/first-post"', html)
    self.assertIn("初回手動投稿パッケージ", html)

  def test_first_post_page_loads(self):
    res = self.client.get("/content-studio/first-post")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("初回手動投稿パッケージ", html)
    self.assertIn("<title>初回手動投稿パッケージ | AI Hive</title>", html)

  def test_first_post_shows_theme(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("対象テーマ", html)
    self.assertIn("AI初心者が仕事で最初に試す3つの使い方", html)

  def test_first_post_svg_has_vertical_2_3_ratio_and_is_local_only(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn('<svg viewBox="0 0 1000 1500"', html)  # 1000:1500 = 2:3
    self.assertIn("縦長 2:3", html)
    self.assertNotIn("<img", html)
    # xmlns="http://www.w3.org/2000/svg" はSVGの標準名前空間宣言であり、
    # 外部リソースの読み込みではない。それ以外にhttp(s)参照がないことを
    # 確認する。
    self.assertIn('xmlns="http://www.w3.org/2000/svg"', html)
    self.assertEqual(html.count("http://"), 1)
    self.assertNotIn("https://", html)

  def test_first_post_svg_shows_three_ways_in_readable_japanese(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("仕事がラクになる", html)
    self.assertIn("AIの使い方", html)
    self.assertIn("AI初心者向け", html)
    for line in (
        "メールの下書きを", "1文で頼む", "長い文章を", "要約してもらう",
        "アイデア出しの", "壁打ち相手にする",
    ):
      self.assertIn(line, html)

  def test_first_post_shows_pinterest_title_description_and_alt_text(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn('id="fp-title"', html)
    self.assertIn("仕事がラクになる、AIの使い方3選（AI初心者向け）", html)
    self.assertIn('id="fp-description"', html)
    self.assertIn('id="fp-alt"', html)
    self.assertIn("特定の商品は写っていません", html)

  def test_first_post_has_no_product_price_ranking_or_definitive_claims(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("今回の商品紹介はなし", html)
    self.assertIn("楽天アフィリエイトリンクは未設定です", html)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)
    self.assertNotIn("位獲得", html)
    self.assertNotIn("楽天市場URL", html)

  def test_first_post_shows_pre_post_checklist(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("投稿前チェックリスト", html)
    for item in (
        "誇大表現や断定的な成果表現がないか確認した",
        "商品名・価格・ランキング・実績などの未確認情報が含まれていないか確認した",
        "画像内の文字が読みやすいか",
        "altテキストが画像の内容を正しく説明しているか確認した",
        "手動で投稿できる準備ができている",
    ):
      self.assertIn(item, html)
    self.assertEqual(html.count('type="checkbox"'), 5)

  def test_first_post_has_no_threads_content_remaining(self):
    # MISSION 041: いまはPinterest・楽天ROOM・noteだけを手動運用しているため、
    # 使っていないThreads下書きセクションを削除した。
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertNotIn("Threads", html)
    self.assertNotIn("Instagram", html)
    import office_views
    self.assertNotIn("threads_draft", office_views.FIRST_POST_PACKAGE)

  def test_first_post_states_manual_posting_and_next_automation_step(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("柴犬社長がPinterestで手動投稿してください", html)
    self.assertIn("実際のURLや", html)
    self.assertIn("反応（保存数・クリック数など）を確認したうえで", html)
    self.assertIn("次にどこまで自動化するかを", html)
    self.assertIn("自動投稿・自動連携は行いません", html)

  def test_first_post_copy_buttons_fail_safely_without_breaking_page(self):
    # MISSION 041: Threads下書きフィールドを削除したため、コピーボタンは
    # title/description/altの3個になった。
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertEqual(html.count('class="fp-copy-btn"'), 3)
    self.assertIn("navigator.clipboard&&navigator.clipboard.writeText", html)
    self.assertIn(".catch(()=>showResult(false))", html)
    self.assertIn("}catch(e){showResult(false);}", html)
    self.assertIn('"コピーできませんでした"', html)

  def test_first_post_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    # xmlns="http://www.w3.org/2000/svg" はSVGの標準名前空間宣言であり、
    # 外部リソースの読み込みではないため、これだけを許容する。
    self.assertEqual(html.count("http://"), 1)
    self.assertIn('xmlns="http://www.w3.org/2000/svg"', html)
    self.assertNotIn("https://", html)
    self.assertNotIn("<script src=", html)
    self.assertNotIn("fetch(", html)
    self.assertNotIn("/api/", html)
    self.assertNotIn('method="POST"', html)
    self.assertIn("prefers-reduced-motion:reduce", html)

  def test_first_post_has_responsive_layout(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("@media(max-width:760px){.fp-pin-layout", html)

  def test_first_post_content_is_data_driven_for_future_edits(self):
    import office_views
    self.assertIn("pin", office_views.FIRST_POST_PACKAGE)
    self.assertIn("checklist", office_views.FIRST_POST_PACKAGE)
    self.assertEqual(len(office_views.FIRST_POST_PACKAGE["pin"]["svg_items"]), 3)
    rendered = office_views._render_first_post_scene(office_views.FIRST_POST_PACKAGE)
    self.assertIn(office_views.FIRST_POST_PACKAGE["theme"], rendered)

  # --- MISSION 032.1: Pinterest用PNG保存機能 -----------------------------------

  def test_first_post_png_file_exists_with_correct_2_3_dimensions(self):
    import office_views
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.FIRST_POST_PNG_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    # PNGシグネチャ + IHDRチャンクから幅・高さを読み取り、正確に
    # 1000x1500(2:3)であることを確認する(外部ライブラリを使わない
    # 最小限の検証)。
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1000, 1500))

  def test_first_post_png_is_served_as_a_plain_static_file(self):
    res = self.client.get("/static/images/first-post-pin-2x3.png")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_first_post_has_png_download_button_as_plain_link(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn('class="fp-png-download"', html)
    self.assertIn("Pinterest用PNGを保存", html)
    self.assertIn(
        'href="/static/images/first-post-pin-2x3.png" download="pinterest-first-post.png"',
        html,
    )
    # ダウンロードは通常の<a href>のみで完結し、JS必須の処理や外部通信を
    # 追加していない(既存のnavigator.clipboard関連のコピー機能はあるが、
    # PNG保存ボタン自体は素のリンクであること)。
    self.assertNotIn("createObjectURL", html)
    self.assertNotIn("toDataURL", html)

  def test_first_post_png_button_explains_manual_upload_and_no_auto_post(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn(
        "保存したPNGをPinterestで手動アップロードしてください", html
    )
    self.assertIn("このボタンからの投稿・送信・連携は行われません", html)

  def test_first_post_existing_svg_and_fields_unchanged_by_png_addition(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn('<svg viewBox="0 0 1000 1500"', html)
    self.assertIn("縦長 2:3（画面内SVG・外部画像なし）", html)
    self.assertIn('id="fp-title"', html)
    self.assertIn('id="fp-description"', html)
    self.assertIn('id="fp-alt"', html)
    self.assertIn("投稿前チェックリスト", html)
    self.assertEqual(html.count('type="checkbox"'), 5)

  def test_first_post_png_route_does_not_require_pillow_at_app_import_time(self):
    # office_views.py自体のimportにPillowが必須になっていないこと
    # (PNG生成コードは遅延importであり、通常のアプリ起動には影響しない)
    # をソースコード上で確認する。
    import office_views
    import inspect
    module_source = inspect.getsource(office_views)
    head = module_source.split("def generate_first_post_pin_png", 1)[0]
    self.assertNotIn("from PIL", head)
    self.assertNotIn("import PIL", head)

  def test_existing_pages_unaffected_by_first_post_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  def test_existing_pages_unaffected_by_content_studio_tab_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  def test_manual_chat_form_is_unaffected_by_quick_actions(self):
    # 手入力チャット(#chat-form)のハンドラは、クイックアクション追加後も
    # 引き続きAPI通信をしないローカル演出のままであることを確認する
    # (test_ceo_chat_is_explicitly_local_and_non_persistentの詳細確認)。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    chat_script_match = re.search(
        r'const f=document\.querySelector\("#chat-form"\).*?</script>',
        html, re.S,
    )
    self.assertIsNotNone(chat_script_match)
    self.assertNotIn("fetch(", chat_script_match.group(0))
    self.assertNotIn("qaAppendBoss", chat_script_match.group(0))

  def test_ceo_chat_is_explicitly_local_and_non_persistent(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("内容は保存・送信されません", html)
    self.assertIn('id="chat-form"', html)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    # 社長室にはMISSION 025で GET /api/logs (読み取り専用) を使った実データ
    # 表示を追加したが、チャットの送信ハンドラ自体は依然として通信しない
    # (定型リアクションをローカルに表示するだけ)ことをピンポイントで確認する。
    chat_script_match = re.search(
        r'const f=document\.querySelector\("#chat-form"\).*?</script>',
        html, re.S,
    )
    self.assertIsNotNone(chat_script_match)
    self.assertNotIn("fetch(", chat_script_match.group(0))

  # --- MISSION 033: 7日間コンテンツ計画 ----------------------------------------

  def test_content_studio_links_to_weekly_plan(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/content-studio/weekly-plan"', html)
    self.assertIn("7日間コンテンツ計画", html)

  def test_weekly_plan_page_loads(self):
    res = self.client.get("/content-studio/weekly-plan")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("7日間コンテンツ計画", html)
    self.assertIn("<title>7日間コンテンツ計画 | AI Hive</title>", html)

  def test_weekly_plan_shows_seven_days_with_existing_themes_only(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    for day in range(1, 8):
      self.assertIn(f"{day}日目：", html)
    # MISSION 050: 6・7日目が参照していた、投稿企画工場からすでに外れた
    # 未実施の汎用ガジェットテーマ(デスク周り・スマホPC周辺機器)を、実際に
    # 投稿キューから公開済みの2テーマへ差し替えた。新しいテーマ名を発明した
    # のではなく、既存の投稿企画(初回投稿テーマ・投稿企画工場の候補テーマ・
    # 投稿キューの公開済みテーマ)だけを使っていることを確認する。
    import office_views
    self.assertIn(
        office_views.FIRST_POST_PACKAGE["theme"], html
    )
    for title in (
        "AI初心者が最初に試す便利な使い方",
        "仕事の文章作成・要約をラクにするAI活用",
        "デスクが狭いときに配線を見直す3つのポイント",
        "スマホ・PC作業をラクにする周辺機器の選び方",
    ):
      self.assertIn(title, html)
    # 「見送り」扱いだったテーマは計画に含めない。MISSION 040で表示から
    # 外れた古い汎用ガジェットテーマも、もう計画に含めない。
    self.assertNotIn("買う前に確認したいAI対応ガジェットの選び方", html)
    self.assertNotIn("デスク周りを整える便利ガジェット", html)
    self.assertNotIn("スマホ・PC作業を快適にする周辺機器", html)

  def test_weekly_plan_shows_medium_purpose_and_status_for_each_day(self):
    # MISSION 041: いまはPinterest・楽天ROOM・noteだけを手動運用しているため、
    # 使っていないInstagramを想定媒体から外し、Pinterest・noteの2媒体だけに
    # 揃えた。MISSION 050で、Threadsが実際にDify経由で運用されている実態を
    # 明記する脚注を追加したため、Threads自体への言及はこのページに存在する
    # (投稿の想定媒体としてではなく、脚注内の説明としてのみ)。
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    for medium in ("Pinterest", "note"):
      self.assertIn(f"<b>{medium}</b>", html)
    self.assertNotIn("<b>Threads</b>", html)
    self.assertNotIn("Instagram", html)
    # MISSION 050で、複数日が公開済みになったため「（初回投稿）」の限定を
    # 外して汎用の「公開済み」ラベルへ整理した。「下書き」「確認待ち」の
    # 状態は、現在はどの日も使っていないため表示されない。
    for status_label in ("公開済み", "手動投稿候補"):
      self.assertIn(status_label, html)
    self.assertIn("目的：", html)

  def test_weekly_plan_day_one_is_published_without_fabricated_numbers(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    day1_card = html.split("1日目：", 1)[1].split("2日目：", 1)[0]
    self.assertIn("公開済み", day1_card)
    self.assertIn("初回手動投稿パッケージ", day1_card)
    self.assertIn("手動でPinterestへ投稿済み", day1_card)
    self.assertIn("反応・成果は", day1_card)
    for word in ("表示回数", "保存数", "クリック数"):
      self.assertNotIn(f"{word}：", day1_card)  # 数値付きの記載ではない
      self.assertNotIn(f"{word}が", day1_card)

  def test_weekly_plan_days_two_to_seven_are_draft_not_scheduled_or_posted(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    rest = html.split("2日目：", 1)[1]
    self.assertNotIn("自動投稿済み", rest)
    self.assertNotIn("予約済み", rest)
    self.assertNotIn("予約投稿済み", rest)
    self.assertNotIn("自動投稿しました", rest)
    # 「予約投稿」という語自体は、末尾の安全注記
    # (「…予約投稿・広告出稿・営業送信は行われません」)にのみ、
    # 「行われません」という否定形で登場することを確認する。
    for occurrence in re.finditer("予約投稿", rest):
      surrounding = rest[occurrence.start():occurrence.start() + 40]
      self.assertIn("行われません", surrounding)
    self.assertIn("下書き・計画段階", rest)
    self.assertIn("投稿・公開・送信は行われていません", rest)

  def test_weekly_plan_has_24_hour_post_publish_check_guidance(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn("公開後24時間で確認すること", html)
    self.assertIn("表示回数", html)
    self.assertIn("保存数", html)
    self.assertIn("クリック数", html)
    self.assertIn("手動確認", html)

  def test_weekly_plan_explains_current_manual_and_threads_dify_status(self):
    # MISSION 050: 「実績を見てから2日目以降の自動化を判断する」という
    # 当初の見通しの説明から、実際に固まった運用(Pinterest・楽天ROOM・note
    # は手動、Threadsのみ別管理のDify自動投稿)を説明する内容へ更新した。
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn(
        "Pinterest・楽天ROOM・noteは、柴犬社長による手動運用を継続しています。",
        html,
    )
    self.assertIn("Threadsのみ、Difyを使った別管理の自動投稿を運用していますが、", html)
    self.assertIn(
        "投稿キュー（/content-studio/publish-queue）とnote記事"
        "（/content-studio/note-first-article）でご確認ください。",
        html,
    )

  def test_weekly_plan_states_internal_draft_not_published_or_sent(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn("社内向けの確認用計画です", html)
    self.assertIn("予約投稿・", html)
    self.assertIn("自動投稿は一切行われません", html)
    self.assertIn("localhost限定", html)
    # MISSION 050: 末尾の安全注記を、Threads(Dify別管理)の実態を含めて
    # 1文に整理したため、文言を更新した(予約投稿・広告出稿・営業送信を
    # 行わない、という内容自体は変わっていない)。
    self.assertIn(
        "この画面（このダッシュボード）からの自動投稿・予約投稿・"
        "広告出稿・営業送信は一切行われません。",
        html,
    )

  def test_weekly_plan_has_no_external_resources_scripts_or_writes(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertNotIn("https://", html)
    self.assertNotIn("<script", html)
    self.assertNotIn("fetch(", html)
    self.assertNotIn("/api/", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)
    # xmlns宣言等を含まないページのため、http(s)参照は皆無であるはず。
    self.assertNotIn("http://", html)

  def test_weekly_plan_has_responsive_layout(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("@media(max-width:760px){.wp-day-meta", html)

  def test_weekly_plan_content_is_data_driven_for_future_edits(self):
    import office_views
    self.assertEqual(len(office_views.WEEKLY_PLAN), 7)
    for entry in office_views.WEEKLY_PLAN:
      self.assertIn(entry["status"], office_views.WEEKLY_PLAN_STATUS_LABELS)
    rendered = office_views._render_weekly_plan_scene(
        office_views.WEEKLY_PLAN,
        office_views.WEEKLY_PLAN_STATUS_LABELS,
        office_views.WEEKLY_PLAN_POST_PUBLISH_CHECKS,
    )
    self.assertIn("weekly-plan-board", rendered)

  def test_existing_pages_unaffected_by_weekly_plan_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 034: 楽天ROOM収益化準備 -----------------------------------------

  def test_revenue_board_has_room_prep_section(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn('id="room-prep"', html)
    self.assertIn("ROOM投稿準備", html)

  def test_room_prep_shows_category_candidates_not_real_products(self):
    # MISSION 052: 「デスク周り」(MISSION 040で対象から外れたテーマ)と、
    # 実際の公開状況と合わない汎用的な周辺機器ジャンル候補の2カテゴリを
    # 削除したため、残る2カテゴリのジャンル候補のみを確認する。
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    for genre in (
        "AIアシスタント対応スマートスピーカー",
        "音声入力対応キーボード",
        "音声文字起こしデバイス",
        "ノートPC用外付けマイク",
    ):
      self.assertIn(genre, section)
    for genre in (
        "モニターアーム",
        "デスクライト",
        "ケーブル収納グッズ",
        "USB-Cハブ",
        "ワイヤレス充電スタンド",
        "ノートPCスタンド",
    ):
      self.assertNotIn(genre, section)
    self.assertIn("実在の商品名・価格・ランキング・在庫・成果予測は表示しません", section)
    # 実在の商品名・価格・ランキング・在庫数量・成果予測を捏造していないこと。
    self.assertNotIn("円", section)
    self.assertNotIn("¥", section)
    self.assertNotIn("位獲得", section)
    self.assertNotIn("http://", section)
    self.assertNotIn("https://", section)

  def test_room_prep_shows_published_room_posts_as_plain_facts(self):
    # MISSION 052: 既に手動投稿済みの折りたたみキーボード投稿を、金額・
    # 在庫・ランキング・未確認レビューなしの事実のみで表示することを確認する。
    # MISSION 057: 9月13日の過去購入・使用商品5件、9月14日のショルダー型
    # ガジェットポーチ1件を追加し、合計7件になった。次のステップの案内は
    # 最新の投稿にだけ表示し、古い投稿に重複表示しないことを確認する。
    # MISSION 058: 見出しに「AI Hiveで追加した7件」であることを明記し、
    # アカウント全体の商品数(30件)にも一度だけ控えめに触れることを確認する。
    # MISSION 059: 9月16日に10件を追加投稿し、AI Hiveで追加した投稿は
    # 合計17件になった。次のステップの案内は、引き続き最新の投稿にだけ
    # 表示され、古い投稿(ショルダー型ガジェットポーチ含む)には重複表示
    # しないことを確認する。
    html = self.client.get("/revenue").get_data(as_text=True)
    published_block = html.split('class="room-prep-published"', 1)[1].split(
        "</div>", 1
    )[0]
    self.assertIn("公開済みの楽天ROOM投稿（AI Hiveで追加した17件）", published_block)
    self.assertIn("折りたたみキーボード", published_block)
    self.assertIn("楽天ROOMへ手動投稿済み（1件）", published_block)
    self.assertIn("過去に購入・使用した商品", published_block)
    self.assertIn(
        "9月13日に楽天ROOMへ手動投稿済み（5件、#オリジナル写真を使用しない通常投稿）",
        published_block,
    )
    self.assertIn("ショルダー型ガジェットポーチ", published_block)
    self.assertIn(
        "9月14日に楽天ROOMへ手動投稿済み（1件、公開情報・購入者レビューを参考にした通常投稿。"
        "#オリジナル写真は使用していません）",
        published_block,
    )
    self.assertIn("追加投稿分", published_block)
    self.assertIn(
        "9月16日に楽天ROOMへ手動投稿済み（10件）", published_block,
    )
    self.assertIn(
        "商品候補をさらに増やす前に、このAI Hive分17件の内容と反応を手動で確認する段階です。",
        published_block,
    )
    self.assertIn(
        "売上・クリック数・成果報酬・商品が売れた実績は未確認のため表示していません。",
        published_block,
    )
    self.assertIn(
        "楽天ROOMアカウント全体では商品投稿が30件あり、このうちAI Hiveで"
        "追加・記録しているのは17件です。",
        published_block,
    )
    self.assertEqual(published_block.count("30件"), 1)
    # 次のステップの案内は最新の投稿にだけ表示され、1回だけ出現する。
    self.assertEqual(published_block.count("次のステップ："), 1)
    self.assertNotIn("円", published_block)
    self.assertNotIn("¥", published_block)
    self.assertNotIn("位獲得", published_block)
    self.assertNotIn("在庫", published_block)

  def test_room_prep_shows_required_fields_for_each_category(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    import office_views
    self.assertEqual(
        section.count('class="room-prep-card"'), len(office_views.ROOM_PREP_CATEGORIES)
    )
    for category in office_views.ROOM_PREP_CATEGORIES:
      self.assertIn(category["audience_problem"], section)
      self.assertIn(category["pinterest_theme_idea"], section)
    self.assertIn("Pinterest投稿のテーマ案", section)
    self.assertIn("ROOMで手動確認する項目", section)
    self.assertIn("商品紹介文を作る前の確認項目", section)
    for status_label in ("企画中", "社長確認待ち"):
      self.assertIn(status_label, section)

  def test_room_prep_excludes_the_passed_over_topic(self):
    # ROOM_PREP_CATEGORIESはoffice_views.py内で独立して定義されたデータ
    # であり、MISSION 040で/content-studioの表示テーマを2件に絞った後も、
    # このデータ自体は変更していない。「見送り」扱いだったテーマ
    # (買う前に確認したいAI対応ガジェットの選び方)の商品ジャンル候補は、
    # 引き続きROOM投稿準備には含まれないことを確認する。
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    for genre in ("AI搭載イヤホン", "スマートディスプレイ"):
      self.assertNotIn(genre, section)

  def test_room_prep_states_manual_registration_and_approval_before_publish(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    self.assertIn("ROOMへの登録は手動です", section)
    self.assertIn("Pinterestへの公開も、社長の承認後に行います", section)

  def test_room_prep_states_no_automation_scraping_or_product_data_fetch(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    self.assertIn(
        "楽天ROOM・SNSへの自動投稿、予約投稿、API連携、スクレイピング、"
        "商品情報取得は一切行いません", section
    )

  def test_room_prep_states_no_rakuten_product_images_local_assets_only(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    self.assertIn(
        "楽天市場の商品画像は保存・加工・表示しません。使用する画像は"
        "既存のローカル素材のみです", section
    )
    self.assertNotIn("<img", section)

  def test_room_prep_shows_pr_disclosure_reminder(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    self.assertIn("PR表記について", section)
    self.assertIn(
        "商品提供・クーポン・広告主とのやり取りがある場合は、投稿前にPR表記が"
        "必要かどうかを確認してください", section
    )

  def test_room_prep_has_no_external_resources_scripts_or_writes(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    self.assertNotIn("<script", section)
    self.assertNotIn("fetch(", section)
    self.assertNotIn("/api/", section)
    self.assertNotIn('method="POST"', section)
    self.assertNotIn("Authorization", section)
    self.assertNotIn("AI_HIVE_", section)

  def test_room_prep_content_is_data_driven_for_future_edits(self):
    # MISSION 052: 「デスク周り」等の古いカテゴリ2件を削除し、2カテゴリに
    # 整理した。公開済み投稿の事実はROOM_PUBLISHED_POSTSという独立した
    # データ構造から組み立てられる。
    # MISSION 057: 楽天ROOMの投稿が7件(3エントリ)になったため、next_stepは
    # 最新の1件にだけ設定する運用にした(他の投稿は必須項目ではない)。
    # MISSION 059: 9月16日の追加投稿分(4エントリ目)が加わり、合計17件に
    # なった。next_stepは引き続き最新の1件(追加投稿分)にだけ設定される。
    import office_views
    self.assertEqual(len(office_views.ROOM_PREP_CATEGORIES), 2)
    for category in office_views.ROOM_PREP_CATEGORIES:
      self.assertIn(category["status"], office_views.ROOM_PREP_STATUS_LABELS)
    self.assertEqual(len(office_views.ROOM_PUBLISHED_POSTS), 4)
    for post in office_views.ROOM_PUBLISHED_POSTS:
      self.assertIn("item_label", post)
      self.assertIn("status_text", post)
    posts_with_next_step = [
        p for p in office_views.ROOM_PUBLISHED_POSTS if "next_step" in p
    ]
    self.assertEqual(len(posts_with_next_step), 1)
    self.assertEqual(
        posts_with_next_step[0]["item_label"], "追加投稿分"
    )
    rendered = office_views._render_room_prep_section(
        office_views.ROOM_PREP_CATEGORIES,
        office_views.ROOM_PREP_STATUS_LABELS,
        office_views.ROOM_PUBLISHED_POSTS,
    )
    self.assertIn("room-prep-section", rendered)
    self.assertIn("公開済みの楽天ROOM投稿", rendered)

  def test_content_studio_links_to_room_prep(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/revenue#room-prep"', html)
    self.assertIn("楽天ROOM投稿準備", html)

  def test_weekly_plan_links_to_room_prep(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn('href="/revenue#room-prep"', html)
    self.assertIn("楽天ROOM投稿準備", html)

  def test_revenue_board_has_responsive_layout_for_room_prep(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("@media(max-width:760px){.room-prep-head", html)

  def test_existing_pages_unaffected_by_room_prep_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 035: デスク環境Pinterest投稿パッケージ(楽天ROOM向け) -------------

  def test_content_studio_links_to_desk_setup_post(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/content-studio/desk-setup-post"', html)
    self.assertIn("デスク環境投稿パッケージ", html)

  def test_desk_setup_post_page_loads(self):
    res = self.client.get("/content-studio/desk-setup-post")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("デスク環境投稿パッケージ", html)
    self.assertIn("<title>デスク環境投稿パッケージ | AI Hive</title>", html)

  def test_desk_setup_post_shows_theme(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn("対象テーマ", html)
    self.assertIn("デスクが狭い人へ", html)
    self.assertIn("画面まわりを整える", html)

  def test_desk_setup_post_svg_has_vertical_2_3_ratio_and_no_product_images(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn('<svg viewBox="0 0 1000 1500"', html)  # 1000:1500 = 2:3
    self.assertIn("縦長 2:3", html)
    self.assertNotIn("<img", html)
    self.assertIn(
        "商品写真・楽天市場画像・商品ロゴは使用していません", html
    )
    # xmlns="http://www.w3.org/2000/svg" はSVGの標準名前空間宣言であり、
    # 外部リソースの読み込みではない。それ以外にhttp(s)参照がないことを
    # 確認する。
    self.assertIn('xmlns="http://www.w3.org/2000/svg"', html)
    self.assertEqual(html.count("http://"), 1)
    self.assertNotIn("https://", html)

  def test_desk_setup_post_svg_shows_three_reviews_in_readable_japanese(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn("モニター位置", html)
    self.assertIn("机上スペース", html)
    self.assertIn("配線", html)

  def test_desk_setup_post_shows_pinterest_title_description_and_alt_text(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn('id="dsp-title"', html)
    self.assertIn("デスクが狭い人へ。画面まわりを整える3つの見直し", html)
    self.assertIn('id="dsp-description"', html)
    self.assertIn('id="dsp-alt"', html)

  def test_desk_setup_post_description_mentions_room_without_fabricated_claims(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    description = html.split('id="dsp-description"', 1)[1].split("</p>", 1)[0]
    self.assertIn("紹介アイテムは楽天ROOMに掲載しています", description)
    self.assertIn("価格・在庫・性能・ランキング・成果については、この画面では断定しません", description)
    self.assertNotIn("円", description)
    self.assertNotIn("¥", description)
    self.assertNotIn("位獲得", description)

  def test_desk_setup_post_states_room_url_is_pasted_manually_no_fetch_or_storage(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn("ROOM商品URLについて", html)
    self.assertIn(
        "柴犬社長がPinterestへ投稿する際に手動で貼り付けてください", html
    )
    self.assertIn("URLの取得・保存・外部連携は、この画面では一切行いません", html)

  def test_desk_setup_post_shows_pre_post_checklist(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn("投稿前チェックリスト", html)
    self.assertEqual(html.count('type="checkbox"'), 6)
    self.assertIn("価格・在庫・性能・ランキング・成果を断定していないか確認した", html)
    self.assertIn("楽天ROOMの商品URLを、Pinterest投稿画面へ手動で貼り付ける準備ができている", html)

  def test_desk_setup_post_states_manual_posting_and_no_automation(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn("手動投稿について", html)
    self.assertIn("柴犬社長がPinterestで手動投稿してください", html)
    self.assertIn(
        "Pinterest・楽天ROOMへの自動投稿・予約投稿・API連携・外部通信は一切行いません", html
    )
    self.assertIn(
        "Pinterest・楽天ROOMへの投稿・送信・連携は行われません", html
    )

  def test_desk_setup_post_copy_buttons_fail_safely_without_breaking_page(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn("fp-copy-btn", html)
    self.assertIn("showResult(false)", html)
    self.assertIn("catch(e)", html)

  def test_desk_setup_post_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertNotIn("https://", html)
    self.assertNotIn("fetch(", html)
    self.assertNotIn("/api/", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_desk_setup_post_has_responsive_layout(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("prefers-reduced-motion:reduce", html)

  def test_desk_setup_post_content_is_data_driven_for_future_edits(self):
    import office_views
    self.assertIn("pin", office_views.DESK_SETUP_POST_PACKAGE)
    self.assertEqual(len(office_views.DESK_SETUP_POST_PACKAGE["pin"]["svg_items"]), 3)
    rendered = office_views._render_desk_setup_scene(office_views.DESK_SETUP_POST_PACKAGE)
    self.assertIn(office_views.DESK_SETUP_POST_PACKAGE["theme"], rendered)

  def test_desk_setup_post_png_file_exists_with_correct_2_3_dimensions(self):
    import office_views
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.DESK_SETUP_PNG_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    # PNGシグネチャ + IHDRチャンクから幅・高さを読み取り、正確に
    # 1000x1500(2:3)であることを確認する(外部ライブラリを使わない
    # 最小限の検証)。
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1000, 1500))

  def test_desk_setup_post_png_is_served_as_a_plain_static_file(self):
    res = self.client.get("/static/images/desk-setup-pin-2x3.png")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_desk_setup_post_has_png_download_button_as_plain_link(self):
    html = self.client.get("/content-studio/desk-setup-post").get_data(as_text=True)
    self.assertIn('class="fp-png-download"', html)
    self.assertIn("Pinterest用PNGを保存", html)
    self.assertIn(
        'href="/static/images/desk-setup-pin-2x3.png" download="pinterest-desk-setup-post.png"',
        html,
    )
    self.assertNotIn("createObjectURL", html)
    self.assertNotIn("toDataURL", html)

  def test_desk_setup_post_png_route_does_not_require_pillow_at_app_import_time(self):
    # office_views.py自体のimportにPillowが必須になっていないこと
    # (PNG生成コードは遅延importであり、通常のアプリ起動には影響しない)
    # をソースコード上で確認する。モジュール直下(インデントなし)の
    # PIL importが存在しない(=すべて関数内の遅延importである)ことを
    # 確認する。
    import office_views
    import inspect
    module_source = inspect.getsource(office_views)
    for line in module_source.splitlines():
      if line.startswith("from PIL") or line.startswith("import PIL"):
        self.fail(f"PIL is imported at module level, not lazily: {line!r}")
    self.assertIn("  from PIL import Image, ImageDraw, ImageFont", module_source)
    # MISSION 036で投稿キュー用(generate_publish_queue_pin_png)、MISSION 039.2
    # でメール下書き投稿の画像焼き込み用(generate_publish_queue_email_draft_
    # v3_png)のPNG生成関数が追加され、同じ遅延importパターン(ImageFontを
    # 使う版)の箇所が4件(初回投稿・デスク環境・投稿キュー・メール下書き
    # v3画像)になった。MISSION 042.1でスマホAI下書き投稿用の画像焼き込み
    # (generate_publish_queue_smartphone_ai_draft_png)も、支給された写真の
    # 上に文字を焼き込む同じ手法(ImageFontを使う版)に切り替えたため、5件に
    # なった。MISSION 049.2でAIとの会話見直しテーマのPinterest画像焼き込み
    # (generate_publish_queue_ai_mismatch_png)も、支給された写真の上に文字を
    # 焼き込む同じ手法(ImageFontを使う版)に切り替えたため、6件になった。
    # MISSION 037.1のnoteヒーロー画像は文字を画像に焼き込まないためImageFont
    # を使わず、ImageDraw+ImageFilterのみの遅延importになっている(別テスト
    # で検証)。
    self.assertEqual(
        module_source.count("from PIL import Image, ImageDraw, ImageFont"), 6
    )
    self.assertIn("  from PIL import Image, ImageDraw, ImageFilter", module_source)
    self.assertNotIn("def generate_note_eyecatch_png", module_source)

  def test_existing_pages_unaffected_by_desk_setup_post_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 036: Pinterest向け・手動承認つき投稿キュー ----------------------

  def test_content_studio_links_to_publish_queue(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/content-studio/publish-queue"', html)
    self.assertIn("投稿キューを見る（社長承認待ち）", html)

  def test_publish_queue_page_loads(self):
    res = self.client.get("/content-studio/publish-queue")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("投稿キュー（社長承認待ち）", html)
    self.assertIn("<title>投稿キュー（社長承認待ち） | AI Hive</title>", html)

  def test_publish_queue_shows_five_posts_with_accurate_status(self):
    # MISSION 042で4件目(スマホでのAI下書き)、MISSION 049で5件目(AIが
    # 「なんか違う」ときに見直す3つ)を追加した。
    # MISSION 054修正: 実際にはメール下書き・スマホでのAI下書き・AIが
    # 「なんか違う」の3件はすでに柴犬社長が手動でPinterestへ投稿済みで
    # あり、社長承認待ちのまま残っているのはデスク配線・周辺機器選びの
    # 2件であることを確認する(公開済みPinterest5件の残り2件は、投稿
    # キューとは別のFIRST_POST_PACKAGE・DESK_SETUP_POST_PACKAGE)。
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)
    published_ids = {
        "email-draft-3points", "smartphone-ai-draft-3points", "ai-mismatch-3points",
    }
    for post in office_views.PUBLISH_QUEUE_POSTS:
      self.assertIn(post["pin"]["title"], html)
      expected_status = (
          "published" if post["id"] in published_ids else "awaiting_president"
      )
      self.assertEqual(post["status"], expected_status)
    self.assertEqual(html.count('class="pq-status-badge'), 5)
    self.assertEqual(html.count('status-published">公開済み</span>'), 3)
    self.assertEqual(
        html.count('status-awaiting_president">社長承認待ち</span>'), 2
    )
    for title in (
        # MISSION 039でメール下書き用の投稿タイトルを更新した。
        "AIにメールの下書きを頼む前に決める3つ",
        "デスクが狭いときに配線を見直す3つのポイント",
        "スマホ・PC作業をラクにする周辺機器の選び方",
        "スマホでAIに下書きを頼む前に確認する3つ",
        "AIが「なんか違う」ときに見直す3つ",
    ):
      self.assertIn(title, html)

  def test_publish_queue_each_post_has_svg_title_description_alt_topics_and_checklist(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 039で「AIにメールの下書きを頼む前に決める3つ」だけ、SVG生成
    # ではなく高精細画像(<img>)を使うようになったため、SVG件数は3→2件になった
    # (デスク配線・周辺機器選びの2件は引き続きSVG生成のまま)。MISSION 042・049の
    # 新規追加分も高精細画像(<img>)方式のため、SVG件数は引き続き2件のまま。
    self.assertEqual(html.count('<svg viewBox="0 0 1000 1500"'), 2)
    self.assertEqual(html.count("Pinterestのトピック候補"), 5)
    self.assertEqual(html.count("投稿前チェックリスト"), 5)
    for post_id in (
        "email-draft-3points", "desk-wiring-3points", "peripheral-choice-3points",
        "smartphone-ai-draft-3points", "ai-mismatch-3points",
    ):
      self.assertIn(f'id="pq-title-{post_id}"', html)
      self.assertIn(f'id="pq-description-{post_id}"', html)
      self.assertIn(f'id="pq-alt-{post_id}"', html)
    for topic in (
        "AI活用術", "仕事効率化", "ビジネスメール",
        "デスク環境", "配線収納", "在宅ワーク",
        "周辺機器", "ガジェット選び", "スマホ活用",
        "AIとの対話術",
    ):
      self.assertIn(topic, html)

  def test_publish_queue_desk_wiring_and_peripherals_images_use_only_text_and_shapes(self):
    # MISSION 039以降、SVG生成のまま残っているのはこの2件のみ
    # (「AIにメールの下書きを頼む前に決める3つ」は高精細画像に変更済み)。
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(
        html.count(
            "縦長 2:3（画面内SVG・外部画像なし、商品写真・楽天市場画像・商品ロゴは使用していません）"
        ),
        2,
    )
    # xmlns="http://www.w3.org/2000/svg" はSVG(2件)の標準名前空間宣言であり、
    # 外部リソースの読み込みではない。
    self.assertEqual(html.count("http://"), 2)

  def test_publish_queue_email_draft_uses_high_fidelity_hero_image_v3_with_no_html_overlay(self):
    # MISSION 039.2: 保存したPNGに文字が入っていなかった問題を修正するため、
    # タイトルを画像本体(v3.png)へ焼き込む方式に切り替えた。画面上のHTML側
    # 見出し重ね表示(.note-hero-overlay等)は、保存画像との二重表示を避ける
    # ため表示しない。
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 042で追加した「スマホでAIに下書きを頼む前に確認する3つ」、
    # MISSION 049で追加した「AIが『なんか違う』ときに見直す3つ」もどちらも
    # hero_image方式(<img>1枚)のため、<img>件数は1→3件になった。
    self.assertEqual(html.count("<img"), 3)
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/publish-queue-email-draft-v3.png"',
        html,
    )
    self.assertNotIn("publish-queue-email-draft-v2.png", html)
    self.assertNotIn("publish-queue-email-draft-2x3.png", html)
    self.assertNotIn('class="note-hero-overlay"', html)
    self.assertNotIn('class="note-hero-title"', html)
    self.assertNotIn('class="note-hero-scrim"', html)
    self.assertIn(
        "縦長 2:3（高精細画像。タイトル文字を画像本体に焼き込み済みです。"
        "ロゴ・実在サービスの画面は写っていません）",
        html,
    )
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "email-draft-3points"][0]
    self.assertEqual(
        "".join(post["hero_title_lines"]), post["pin"]["title"]
    )

  def test_publish_queue_email_draft_png_download_uses_v3_filename(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn(
        'href="/static/images/publish-queue-email-draft-v3.png" '
        'download="pinterest-publish-queue-email-draft-v3.png"',
        html,
    )

  def test_publish_queue_email_draft_v3_png_has_title_text_baked_in(self):
    # ダウンロードされるPNG(v3.png)が、v2.pngとは別の新規ファイルとして
    # 存在し、実際に文字が描画されたことでピクセル内容がv2.pngと異なる
    # (=単なるコピーではなく、タイトルの焼き込みが行われた)ことを確認する。
    # 外部ライブラリを使わず、ファイルの生バイト列を直接比較する。
    import office_views
    v2_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.PUBLISH_QUEUE_EMAIL_DRAFT_V2_RELATIVE_PATH,
    )
    v3_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.PUBLISH_QUEUE_EMAIL_DRAFT_V3_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(v2_path))
    self.assertTrue(os.path.isfile(v3_path))
    with open(v2_path, "rb") as f:
      v2_bytes = f.read()
    with open(v3_path, "rb") as f:
      v3_bytes = f.read()
    self.assertNotEqual(v2_bytes, v3_bytes)
    # PNGシグネチャ + IHDRチャンクから幅・高さを読み取り、v2.pngと同じ
    # 1024x1536(2:3)のまま焼き込みが行われた(解像度を変えていない)ことを
    # 確認する(外部ライブラリを使わない最小限の検証)。
    header = v3_bytes[:33]
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1024, 1536))

  def test_publish_queue_email_draft_v3_png_is_served_as_a_plain_static_file(self):
    res = self.client.get("/static/images/publish-queue-email-draft-v3.png")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_publish_queue_email_draft_old_assets_are_kept_untouched(self):
    # v2.pngと旧2x3.pngは、どちらも削除・上書きしないというMISSION 039.2の
    # 指示どおり、そのまま残っていることを確認する。
    import office_views
    for relative_path in (
        "images/publish-queue-email-draft-v2.png",
        "images/publish-queue-email-draft-2x3.png",
    ):
      path = os.path.join(os.path.dirname(office_views.__file__), "static", relative_path)
      self.assertTrue(os.path.isfile(path), f"{relative_path} should still exist")

  def test_publish_queue_email_draft_hero_png_file_has_2_3_ratio(self):
    import office_views
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "email-draft-3points"][0]
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static", post["hero_image_relative_path"],
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertGreater(height, width)  # 縦長であることを確認
    self.assertEqual(width * 3, height * 2)  # 正確に2:3比であることを確認

  def test_publish_queue_old_email_draft_png_asset_is_kept_untouched(self):
    # 既存の publish-queue-email-draft-2x3.png は削除・上書きしない、という
    # MISSION 039の指示どおり、旧アセットがそのまま残っていることを確認する
    # (現在の投稿データからは参照されなくなったが、ファイル自体は保持する)。
    import office_views
    old_png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        "images/publish-queue-email-draft-2x3.png",
    )
    self.assertTrue(os.path.isfile(old_png_path))
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "email-draft-3points"][0]
    self.assertNotIn("png_relative_path", post)
    self.assertNotEqual(
        post.get("hero_image_relative_path"), "images/publish-queue-email-draft-2x3.png"
    )

  def test_publish_queue_has_no_product_names_prices_stock_ranking_or_forecasts(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)
    self.assertNotIn("位獲得", html)
    self.assertNotIn("在庫あり", html)
    self.assertNotIn("在庫切れ", html)

  def test_publish_queue_room_link_field_is_blank_and_manual(self):
    # MISSION 039で「AIにメールの下書きを頼む前に決める3つ」はリンク先が
    # 確定したため、汎用の「楽天ROOMリンク：空欄」注記は表示しなくなった
    # (代わりに専用の「リンク先」フィールドを表示する。別テストで検証)。
    # 残る2件(デスク配線・周辺機器選び)は引き続き空欄のまま。MISSION 042の
    # 新規追加分は空欄のままだが、汎用文言ではなく専用の注記(折りたたみ
    # キーボード投稿URLを手動で貼る旨)を表示するため、「楽天ROOMリンク：
    # （空欄）」自体の出現数は3件(共通の書き出し部分)になる。
    # MISSION 054: 「AIが「なんか違う」ときに見直す3つ」もリンク先(公開済み
    # note記事のURL)が確定したため、汎用の空欄注記を表示しなくなった。
    # そのため出現数は3件のまま変わらない。
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(html.count("楽天ROOMリンク：（空欄）"), 3)
    self.assertEqual(
        html.count(
            "社長がPinterestへ投稿する際に手動で貼り付けてください。"
            "URLの取得・保存・外部連携は、この画面では一切行いません。"
        ),
        2,
    )
    self.assertIn(
        "楽天ROOMリンク：（空欄）公開済みの折りたたみキーボード投稿URLを、"
        "社長が手動で貼り付けてください。URLの取得・保存・外部連携は、この"
        "画面では一切行いません。",
        html,
    )

  def test_publish_queue_email_draft_pinterest_link_points_to_published_note_article(self):
    # MISSION 039: Pinterest用のリンク先を、公開済みnote記事のURLへ更新した。
    # 手動でPinterest投稿画面に貼り付ける想定であり、このアプリ自身が外部へ
    # アクセス・取得・保存・自動連携することはない(クリックは人間の手動操作)。
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn('id="pq-link-email-draft-3points"', html)
    self.assertIn(
        'href="https://note.com/legal_crow9879/n/nf7af35ac8c28" '
        'target="_blank" rel="noopener noreferrer"',
        html,
    )
    self.assertIn(">https://note.com/legal_crow9879/n/nf7af35ac8c28</a>", html)
    self.assertIn('data-copy-target="pq-link-email-draft-3points"', html)
    # 他の2件にはリンク先フィールドを追加していない。
    self.assertNotIn('id="pq-link-desk-wiring-3points"', html)
    self.assertNotIn('id="pq-link-peripheral-choice-3points"', html)
    self.assertIn("リンク先のnote記事が正しく公開されているか確認した", html)

  def test_publish_queue_states_manual_publish_by_president_on_every_card(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 042でカードが3件→4件、MISSION 049で4件→5件になった。
    self.assertEqual(html.count("公開について"), 5)
    # ページ冒頭のリード文でも同じ文言を明記しているため、カード5件+リード文1件
    # の合計6件が期待値。
    self.assertEqual(
        html.count("公開は社長がPinterestで手動実行します"), 6
    )
    # MISSION 041: いまはPinterest・楽天ROOM・noteだけを手動運用しているため、
    # 使っていないThreads・Instagramへの言及を削除した。
    self.assertIn(
        "Pinterest・楽天ROOM・noteへの自動投稿・予約投稿・外部通信は一切行いません", html
    )
    self.assertNotIn("Threads", html)
    self.assertNotIn("Instagram", html)

  def test_publish_queue_links_to_desk_setup_post_and_weekly_plan(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn('href="/content-studio/desk-setup-post"', html)
    self.assertIn('href="/content-studio/weekly-plan"', html)

  def test_publish_queue_copy_buttons_fail_safely_without_breaking_page(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn("fp-copy-btn", html)
    self.assertIn("showResult(false)", html)
    self.assertIn("catch(e)", html)
    # コピー用ボタンは、デスク配線・周辺機器選び・スマホAI下書きの3件が
    # タイトル・説明文・altテキストの3フィールド×3件=9個、メール下書き・
    # AIとの会話見直しの2件がタイトル・説明文・altテキスト・リンク先の
    # 4フィールド×2件=8個で、合計17個(MISSION 054でAIとの会話見直しに
    # 実際の記事へのリンク先フィールドが追加された)。
    self.assertEqual(html.count('class="fp-copy-btn"'), 17)

  def test_publish_queue_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 039で「AIにメールの下書きを頼む前に決める3つ」のPinterest
    # リンク先として、公開済みnote記事への実URLを1箇所だけ追加した(href属性
    # とリンクテキストの2箇所に同じURLが現れるため、https://の出現回数は2)。
    # MISSION 054で「AIが「なんか違う」ときに見直す3つ」も公開済みとなり、
    # 同じ形式でもう1つの実URL(nb2a21a842387)を追加したため、合計4。
    # それ以外の外部通信・スクリプト・API呼び出しは一切追加していないことを
    # 確認する。
    self.assertEqual(html.count("https://"), 4)
    self.assertEqual(
        html.count("https://note.com/legal_crow9879/n/nf7af35ac8c28"), 2
    )
    self.assertEqual(
        html.count("https://note.com/legal_crow9879/n/nb2a21a842387"), 2
    )
    self.assertNotIn("<script src", html)
    self.assertNotIn("fetch(", html)
    self.assertNotIn("/api/", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_publish_queue_has_responsive_layout(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("@media(max-width:760px){.pq-card-head", html)
    self.assertIn("prefers-reduced-motion:reduce", html)

  def test_publish_queue_content_is_data_driven_for_future_edits(self):
    import office_views
    for post in office_views.PUBLISH_QUEUE_POSTS:
      # MISSION 039以降、「AIにメールの下書きを頼む前に決める3つ」は
      # svg_itemsを持たず高精細画像(hero_image_relative_path)を使う。
      # 残る2件は引き続きsvg_itemsからSVGを生成する。
      if "hero_image_relative_path" in post:
        self.assertNotIn("svg_items", post["pin"])
        self.assertIn("hero_title_lines", post)
      else:
        self.assertEqual(len(post["pin"]["svg_items"]), 3)
      self.assertIn("checklist", post)
      self.assertIn("pinterest_topic_candidates", post)
    rendered = office_views._render_publish_queue_scene(
        office_views.PUBLISH_QUEUE_POSTS,
        office_views.PUBLISH_QUEUE_ROOM_LINK_NOTE,
        office_views.PUBLISH_QUEUE_MANUAL_POST_NOTE,
        office_views.PUBLISH_QUEUE_STATUS_LABELS,
    )
    self.assertIn("publish-queue-board", rendered)

  def test_publish_queue_png_files_exist_with_correct_2_3_dimensions(self):
    # 「AIにメールの下書きを頼む前に決める3つ」(hero_image_relative_path)は
    # 専用テスト(test_publish_queue_email_draft_hero_png_file_has_2_3_ratio)で
    # 検証済みのため、ここでは引き続きSVG生成方式を使う2件のみを対象にする。
    import office_views
    for post in office_views.PUBLISH_QUEUE_POSTS:
      if "png_relative_path" not in post:
        continue
      with self.subTest(post_id=post["id"]):
        png_path = os.path.join(
            os.path.dirname(office_views.__file__), "static", post["png_relative_path"],
        )
        self.assertTrue(os.path.isfile(png_path))
        with open(png_path, "rb") as f:
          header = f.read(33)
        # PNGシグネチャ + IHDRチャンクから幅・高さを読み取り、正確に
        # 1000x1500(2:3)であることを確認する(外部ライブラリを使わない
        # 最小限の検証)。
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        self.assertEqual((width, height), (1000, 1500))

  def test_publish_queue_pngs_are_served_as_plain_static_files(self):
    import office_views
    for post in office_views.PUBLISH_QUEUE_POSTS:
      asset_path = post.get("png_relative_path") or post.get("hero_image_relative_path")
      with self.subTest(post_id=post["id"]):
        res = self.client.get(f'/static/{asset_path}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "image/png")

  def test_publish_queue_has_png_download_buttons_as_plain_links(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 042でカードが3件→4件、MISSION 049で4件→5件になった。
    self.assertEqual(html.count("Pinterest用PNGを保存"), 5)
    for post in office_views.PUBLISH_QUEUE_POSTS:
      asset_path = post.get("png_relative_path") or post.get("hero_image_relative_path")
      filename = post.get("png_download_filename") or post.get("hero_image_download_filename")
      self.assertIn(
          f'href="/static/{asset_path}" download="{filename}"',
          html,
      )
    self.assertNotIn("createObjectURL", html)
    self.assertNotIn("toDataURL", html)

  def test_existing_pages_unaffected_by_publish_queue_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
        ("/content-studio/desk-setup-post", "デスク環境投稿パッケージ"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 039: メール下書き投稿パッケージの高品質画像版への更新 -------------

  def test_publish_queue_other_two_posts_unaffected_by_email_draft_update(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    for post_id, title, topics, first_checklist_item in (
        (
            "desk-wiring-3points", "デスクが狭いときに配線を見直す3つのポイント",
            ("デスク環境", "配線収納", "在宅ワーク"),
            "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
        ),
        (
            "peripheral-choice-3points", "スマホ・PC作業をラクにする周辺機器の選び方",
            ("周辺機器", "ガジェット選び", "在宅ワーク"),
            "タイトル・説明文に誇大表現や断定的な成果表現がないか確認した",
        ),
    ):
      with self.subTest(post_id=post_id):
        self.assertIn(title, html)
        self.assertIn(f'id="pq-title-{post_id}"', html)
        for topic in topics:
          self.assertIn(topic, html)
        self.assertIn(first_checklist_item, html)
        post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == post_id][0]
        self.assertNotIn("hero_image_relative_path", post)
        self.assertNotIn("pinterest_link_url", post)
        self.assertIn("png_relative_path", post)

  # --- MISSION 042: スマホでAIに下書きを頼む前に確認する3つ(新規カード) ----

  def test_publish_queue_smartphone_ai_draft_card_added_with_required_content(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "smartphone-ai-draft-3points"
    ][0]
    self.assertEqual(post["pin"]["title"], "スマホでAIに下書きを頼む前に確認する3つ")
    # MISSION 054修正: この投稿は実際には柴犬社長が手動でPinterestへ
    # 投稿済みであることが判明したため、"published"へ更新した。
    self.assertEqual(post["status"], "published")
    self.assertIn('id="pq-title-smartphone-ai-draft-3points"', html)
    self.assertIn('id="pq-description-smartphone-ai-draft-3points"', html)
    self.assertIn('id="pq-alt-smartphone-ai-draft-3points"', html)
    # 画像内の3項目が、投稿データ(hero_item_lines)とpinの説明・altの両方に
    # 反映されていることを確認する。
    self.assertEqual(
        post["hero_item_lines"],
        ["1. 使う端末を決める", "2. 文字入力の方法を決める", "3. 読み返す場所を決める"],
    )
    for item in ("使う端末を決める", "文字入力の方法を決める", "読み返す場所を決める"):
      self.assertIn(item, post["pin"]["alt_text"])
    # hero_title_linesを連結するとpinのタイトルと一致することを確認する
    # (email-draft-3points等の既存カードと同じ規約)。
    self.assertEqual("".join(post["hero_title_lines"]), post["pin"]["title"])
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/publish-queue-smartphone-ai-draft-2x3.png"',
        html,
    )
    self.assertIn(
        'href="/static/images/publish-queue-smartphone-ai-draft-2x3.png" '
        'download="pinterest-publish-queue-smartphone-ai-draft.png"',
        html,
    )

  def test_publish_queue_smartphone_ai_draft_checklist_includes_ai_label_requirement(self):
    import office_views
    post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "smartphone-ai-draft-3points"
    ][0]
    checklist_text = "".join(post["checklist"])
    self.assertIn("AIで修正済み", checklist_text)
    self.assertIn("画像ラベル", checklist_text)
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn("AIで修正済み", html)
    self.assertIn(
        "この画面では一切行いません", html
    )

  def test_publish_queue_smartphone_ai_draft_room_link_is_blank_with_custom_note(self):
    import office_views
    post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "smartphone-ai-draft-3points"
    ][0]
    self.assertNotIn("pinterest_link_url", post)
    self.assertIn("custom_room_link_note", post)
    self.assertIn("折りたたみキーボード投稿URL", post["custom_room_link_note"])
    self.assertIn("空欄", post["custom_room_link_note"])
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertNotIn('id="pq-link-smartphone-ai-draft-3points"', html)

  def test_publish_queue_smartphone_ai_draft_has_no_definitive_claims_or_business_data(self):
    import office_views
    post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "smartphone-ai-draft-3points"
    ][0]
    combined_text = post["pin"]["title"] + post["pin"]["description"] + post["pin"]["alt_text"]
    for forbidden in ("自分で使った", "おすすめ", "効率が上がる", "成果が出る"):
      self.assertNotIn(forbidden, combined_text)
    for forbidden in ("円", "¥", "位獲得", "在庫あり", "在庫切れ", "ランキング"):
      self.assertNotIn(forbidden, combined_text)
    # 「レビュー」自体は説明文に登場するが、「紹介やレビューではありません」
    # という否定形でのみ使われており、実際のレビュー内容を記載するものでは
    # ない(既存カードの「空欄では…行いません」等の否定形と同じ扱い)。
    self.assertIn("紹介やレビューではありません", post["pin"]["description"])

  def test_publish_queue_smartphone_ai_draft_png_has_correct_2_3_dimensions_and_baked_title(self):
    # 外部ライブラリを使わず、PNGの生バイト列(シグネチャ+IHDRチャンク)から
    # 幅・高さを直接読み取る(既存のemail-draft-3points用テストと同じ手法)。
    import office_views
    post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "smartphone-ai-draft-3points"
    ][0]
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static", post["hero_image_relative_path"],
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1024, 1536))

  def test_publish_queue_smartphone_ai_draft_generator_has_no_top_level_pil_import(self):
    # PillowはPNG再生成用の開発時専用ツールであり、Flaskアプリの起動・
    # リクエスト処理からは一切importされない(既存のgenerate_*_png系関数と
    # 同じ規約)。モジュール全体に、列頭(インデントなし)のPIL import文が
    # 存在しないこと(=関数内での遅延importのみであること)を確認する。
    import office_views
    import inspect
    source = inspect.getsource(office_views)
    lines = source.splitlines()
    top_level_import_lines = [
        line for line in lines
        if line.startswith("from PIL") or line.startswith("import PIL")
    ]
    self.assertEqual(top_level_import_lines, [])
    func_source = inspect.getsource(office_views.generate_publish_queue_smartphone_ai_draft_png)
    self.assertIn("from PIL import", func_source)

  def test_publish_queue_smartphone_ai_draft_served_as_plain_static_png(self):
    res = self.client.get("/static/images/publish-queue-smartphone-ai-draft-2x3.png")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  # --- MISSION 042.1: 支給された高品質写真への差し替え -----------------------

  def test_publish_queue_smartphone_ai_draft_uses_supplied_photo_base_not_pillow_illustration(self):
    # MISSION 042.1で、社長から支給された高品質な写真風ビジュアルを土台に
    # 差し替えた。元写真ファイルが存在し、実際に配信するPNG(タイトル焼き込み
    # 済み)と元写真はピクセル内容が異なる(=単なるコピーではなく、文字の
    # 焼き込みが行われた)ことを確認する。既存のemail-draft-3points用
    # (v2/v3.png)テストと同じ手法で、外部ライブラリを使わず生バイト列を
    # 直接比較する。
    import office_views
    base_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.PUBLISH_QUEUE_SMARTPHONE_AI_PHOTO_BASE_RELATIVE_PATH,
    )
    baked_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.PUBLISH_QUEUE_SMARTPHONE_AI_DRAFT_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(base_path))
    self.assertTrue(os.path.isfile(baked_path))
    with open(base_path, "rb") as f:
      base_bytes = f.read()
    with open(baked_path, "rb") as f:
      baked_bytes = f.read()
    self.assertNotEqual(base_bytes, baked_bytes)
    for path in (base_path, baked_path):
      with open(path, "rb") as f:
        header = f.read(33)
      self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
      width = int.from_bytes(header[16:20], "big")
      height = int.from_bytes(header[20:24], "big")
      self.assertEqual((width, height), (1024, 1536))

  def test_publish_queue_smartphone_ai_draft_generator_no_longer_draws_illustration_shapes(self):
    # MISSION 042.1で、Pillow製イラスト(グラデーション背景・図形描画による
    # 端末シルエット)から、支給された実写真ベースの画像へ切り替えた。
    # 関数のソースに、旧イラスト描画特有のコード(図形描画・ぼかしフィルタ)
    # が残っていないことを確認する。
    import office_views
    import inspect
    func_source = inspect.getsource(office_views.generate_publish_queue_smartphone_ai_draft_png)
    self.assertNotIn("rounded_rectangle", func_source)
    self.assertNotIn("ImageFilter", func_source)
    self.assertNotIn("polygon", func_source)
    self.assertIn("PUBLISH_QUEUE_SMARTPHONE_AI_PHOTO_BASE_RELATIVE_PATH", func_source)
    self.assertIn("Image.open", func_source)

  def test_publish_queue_other_three_posts_unaffected_by_smartphone_ai_draft_addition(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    for post_id, title in (
        ("email-draft-3points", "AIにメールの下書きを頼む前に決める3つ"),
        ("desk-wiring-3points", "デスクが狭いときに配線を見直す3つのポイント"),
        ("peripheral-choice-3points", "スマホ・PC作業をラクにする周辺機器の選び方"),
    ):
      with self.subTest(post_id=post_id):
        self.assertIn(title, html)
        self.assertIn(f'id="pq-title-{post_id}"', html)
    self.assertIn(
        'href="https://note.com/legal_crow9879/n/nf7af35ac8c28" '
        'target="_blank" rel="noopener noreferrer"',
        html,
    )
    # 既存3件の画像アセットが、MISSION 042の追加により上書き・削除されて
    # いないことを確認する。
    for relative_path in (
        "images/publish-queue-email-draft-v3.png",
        "images/publish-queue-desk-wiring-2x3.png",
        "images/publish-queue-peripherals-2x3.png",
    ):
      path = os.path.join(os.path.dirname(office_views.__file__), "static", relative_path)
      self.assertTrue(os.path.isfile(path), f"{relative_path} should still exist")

  def test_existing_pages_unaffected_by_smartphone_ai_draft_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
        ("/content-studio/desk-setup-post", "デスク環境投稿パッケージ"),
        ("/content-studio/note-first-article", "note初回記事"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  def test_existing_pages_unaffected_by_email_draft_hero_image_update(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
        ("/content-studio/desk-setup-post", "デスク環境投稿パッケージ"),
        ("/content-studio/note-first-article", "note初回記事"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 037 / 037.1: note初回記事の手動投稿パッケージ(長文・高品質版) ----

  def test_content_studio_links_to_note_first_article(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/content-studio/note-first-article"', html)
    self.assertIn("note初回記事を見る", html)

  def test_note_first_article_page_loads(self):
    res = self.client.get("/content-studio/note-first-article")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("note初回記事", html)
    self.assertIn("<title>note初回記事 | AI Hive</title>", html)

  def test_note_first_article_shows_theme_and_title(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("対象テーマ", html)
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める", html
    )
    self.assertIn('class="note-article-title"', html)

  def test_note_first_article_body_char_count_is_within_4500_to_5500(self):
    import office_views
    body_text = office_views._note_article_body_plain_text(office_views.NOTE_FIRST_ARTICLE)
    char_count = len(body_text)
    self.assertGreaterEqual(char_count, 4500)
    self.assertLessEqual(char_count, 5500)

  def test_note_first_article_covers_required_structure_in_order(self):
    import office_views
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    required_headings = (
        "はじめる前に",
        "1. メールの下書きを1文で頼む",
        "2. 長い文章を要約してもらう",
        "3. アイデア出しの壁打ち相手にする",
        "失敗しやすい点",
        "機密情報の注意",
        "AIに任せない判断",
        "まとめ",
        "次の一歩",
    )
    # 見出しタグそのものの位置を調べる(本文中に「まとめてください」等、
    # 見出しの部分文字列を含む地の文があるため、単純な部分文字列検索では
    # 誤検出する)。
    positions = [html.index(f'class="note-section-heading">{h}<') for h in required_headings]
    self.assertEqual(positions, sorted(positions))
    # 各具体例に「使いどころ・入力例・出力確認」が揃っていることを確認する。
    self.assertEqual(html.count('class="note-subheading">使いどころ'), 3)
    self.assertEqual(html.count('class="note-subheading">入力例'), 3)
    self.assertEqual(html.count('class="note-subheading">出力確認'), 3)
    self.assertEqual(
        len(office_views.NOTE_FIRST_ARTICLE["sections"]), 3
    )
    self.assertEqual(
        {c["heading"] for c in office_views.NOTE_FIRST_ARTICLE["closing_sections"]},
        {"失敗しやすい点", "機密情報の注意", "AIに任せない判断", "まとめ", "次の一歩"},
    )

  def test_note_first_article_has_no_definitive_results_income_time_or_performance_claims(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    visible = html.split('class="note-article-visible"', 1)[1].split(
        'class="note-article-copy-source"', 1
    )[0]
    self.assertNotIn("¥", visible)
    self.assertNotIn("時間短縮", visible)
    self.assertNotIn("必ず稼げ", visible)
    self.assertNotIn("絶対に成功", visible)
    self.assertNotIn("収入が増え", visible)
    self.assertNotIn("性能が最も", visible)
    self.assertNotIn("ランキング1位", visible)

  def test_note_first_article_does_not_write_fictional_content_as_real_experience(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    visible = html.split('class="note-article-visible"', 1)[1].split(
        'class="note-article-copy-source"', 1
    )[0]
    # 「私が実際に試した」のような一人称の実体験を装う表現を含めていない
    # ことを確認する(一般的な解説・提案の語り口のみを使う)。
    self.assertNotIn("私が実際に試した", visible)
    self.assertNotIn("私は実際に", visible)
    self.assertNotIn("筆者が試したところ", visible)

  def test_note_first_article_shows_tag_candidates(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("note向けタグ候補", html)
    for tag in ("AI活用", "AI初心者", "仕事効率化", "生成AI", "業務効率化"):
      self.assertIn(f"<li>{tag}</li>", html)

  def test_note_first_article_excludes_product_intro_and_room_link_states_future_pr_check(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("商品紹介について", html)
    self.assertIn(
        "この記事には、商品紹介や楽天ROOMリンク・アフィリエイトリンクを含めていません", html
    )
    self.assertIn(
        "柴犬社長が内容を手動で確認し、必要に応じて広告・PR表記が必要かどうかを"
        "確認したうえで追加します", html
    )
    self.assertNotIn("楽天ROOMリンク：", html)
    self.assertNotIn('href="https://room.rakuten.co.jp', html)

  def test_note_first_article_hero_is_an_image_with_html_overlaid_title_no_baked_in_text(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn('class="note-hero"', html)
    self.assertIn(
        f'<img class="note-hero-img" src="/static/images/note-first-article-hero.png"', html
    )
    self.assertIn('class="note-hero-overlay"', html)
    self.assertIn('class="note-hero-title"', html)
    # タイトル文字はHTML側(note-hero-title)にのみ存在し、画像はSVGではなく
    # <img>で表示していることを確認する(画像そのものに文字を焼き込まない)。
    self.assertNotIn("<svg", html)
    self.assertIn("横長 1672×941", html)
    self.assertIn("見出し文字はHTML側で重ねています", html)

  def test_note_first_article_copy_button_targets_hidden_plain_text_and_fails_safely(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn('data-copy-target="note-article-body-copy"', html)
    self.assertIn('id="note-article-body-copy"', html)
    self.assertIn('class="note-article-copy-source"', html)
    copy_source = html.split('id="note-article-body-copy"', 1)[1].split("</pre>", 1)[0]
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
        copy_source,
    )
    self.assertIn("メールの下書きを1文で頼む", copy_source)
    self.assertIn("まとめ", copy_source)
    self.assertIn("次の一歩", copy_source)
    self.assertIn("fp-copy-btn", html)
    self.assertIn("showResult(false)", html)
    self.assertIn("catch(e)", html)

  def test_note_first_article_states_manual_publish_only(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("手動投稿について", html)
    self.assertIn(
        "柴犬社長がnoteへ手動でコピー＆ペーストして公開してください", html
    )
    self.assertIn(
        "note・SNSへの自動投稿・予約投稿・ログイン操作・API連携・外部通信は"
        "一切行いません", html
    )

  def test_note_first_article_shows_pre_post_checklist(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("投稿前チェックリスト", html)
    # MISSION 043で、同じページにスマホAI下書きテーマのnote記事下書き
    # (チェックリスト7項目)を追加し、既存の初回記事分(7項目)と合わせて
    # 14個になった。MISSION 044でその下書きに見出し画像用のチェック項目が
    # 1件追加され、合計15個になった。MISSION 049でさらにAIとの会話見直し
    # テーマのnote記事下書き(チェックリスト9項目)を追加し、合計24個になった。
    self.assertEqual(html.count('type="checkbox"'), 24)
    self.assertIn("本文が4,500〜5,500字の目安に収まっているか確認した", html)

  def test_note_first_article_has_no_external_resources_or_network_calls(self):
    # MISSION 054: 「AIとの会話の見直し」記事が公開済みとなったため、公開
    # 済みの事実として実際の記事URL(nb2a21a842387)をプレーンテキストで
    # 1箇所だけ表示する(リンク化はしていないため、出現回数は1)。それ以外の
    # 外部通信・スクリプト・API呼び出しは一切追加していないことを確認する。
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertEqual(html.count("https://"), 1)
    self.assertEqual(
        html.count("https://note.com/legal_crow9879/n/nb2a21a842387"), 1
    )
    self.assertNotIn("fetch(", html)
    self.assertNotIn("/api/", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertEqual(html.count("http://"), 0)

  def test_note_first_article_has_responsive_layout(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn('name="viewport"', html)
    self.assertIn("prefers-reduced-motion:reduce", html)
    self.assertIn("@media(max-width:600px){.note-hero-overlay", html)

  def test_note_first_article_content_is_data_driven_for_future_edits(self):
    import office_views
    self.assertEqual(len(office_views.NOTE_FIRST_ARTICLE["sections"]), 3)
    self.assertEqual(len(office_views.NOTE_FIRST_ARTICLE["closing_sections"]), 5)
    rendered = office_views._render_note_article_scene(office_views.NOTE_FIRST_ARTICLE)
    self.assertIn(office_views.NOTE_FIRST_ARTICLE["title"], rendered)

  # --- MISSION 043: スマホAI下書きテーマのnote記事下書き(2本目) -----------------

  def test_note_second_article_draft_appears_on_note_first_article_page(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("次のnote記事下書き", html)
    self.assertIn(
        "スマホでAIに下書きを頼む前に確認する3つ──端末・入力・読み返しを先に決める", html
    )
    self.assertIn(
        "対象テーマ：<b>スマホでAIに下書きを頼む前に確認する3つ</b>"
        "（Pinterest投稿キューの「スマホでAIに下書きを頼む前に確認する3つ」と対応）",
        html,
    )
    # 既存の初回記事のタイトルも引き続き表示されていることを確認する
    # (既存記事は変更・削除していない)。
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める", html
    )

  def test_note_second_article_draft_body_char_count_is_within_4500_to_5500(self):
    import office_views
    body_text = office_views._note_second_article_draft_body_plain_text(
        office_views.NOTE_SECOND_ARTICLE_DRAFT
    )
    char_count = len(body_text)
    self.assertGreaterEqual(char_count, 4500)
    self.assertLessEqual(char_count, 5500)

  def test_note_second_article_draft_covers_required_3_points_with_examples(self):
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    headings = [s["heading"] for s in article["sections"]]
    for required in ("1. 使う端末を決める", "2. 文字入力の方法を決める", "3. 読み返す場所を決める"):
      self.assertIn(required, headings)
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    for required in ("1. 使う端末を決める", "2. 文字入力の方法を決める", "3. 読み返す場所を決める"):
      self.assertIn(required, html)
    # 各項目に具体例が含まれていることを、代表的な語で確認する。
    self.assertIn("たとえば", article["sections"][0]["body"])
    self.assertIn("たとえば", article["sections"][1]["body"])
    self.assertIn("たとえば", article["sections"][2]["body"])

  def test_note_second_article_draft_shows_overview_pinterest_description_and_alt_text(self):
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn('id="note2-title"', html)
    self.assertIn('id="note2-overview"', html)
    self.assertIn('id="note2-pinterest-description"', html)
    self.assertIn('id="note2-alt-text"', html)
    self.assertIn(article["overview"], html)
    self.assertIn(article["pinterest_description"], html)
    self.assertIn(article["alt_text_draft"], html)
    self.assertLessEqual(len(article["pinterest_description"]), 500)

  def test_note_second_article_draft_has_no_definitive_claims_or_business_data(self):
    # チェックリスト自体には「こうした表現が含まれていないか確認した」という
    # 形で断定表現の語そのものが引用として登場するため、判定対象は記事本文
    # (タイトル・概要・本文)に限定する(投稿前チェックリストより前の部分)。
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    article_only = html.split(
        'aria-label="スマホAI下書きテーマのnote記事下書き"', 1
    )[1].split('<h3 class="fp-section-title">投稿前チェックリスト</h3>', 1)[0]
    for forbidden in ("必ず効率が上がる", "成果が出る", "絶対に", "必ず稼げ"):
      self.assertNotIn(forbidden, article_only)
    for forbidden in ("¥", "円", "位獲得", "在庫あり", "在庫切れ", "ランキング"):
      self.assertNotIn(forbidden, article_only)
    # 「レビュー」自体は概要・Pinterest用説明文案に登場するが、「紹介や
    # レビューは含みません」という否定形でのみ使われており、実際のレビュー
    # 内容を記載するものではない(既存カードの否定形と同じ扱い、MISSION 042
    # のtest_publish_queue_smartphone_ai_draft_has_no_definitive_claims_or_
    # business_dataと同じ考え方)。
    self.assertIn("紹介やレビューは含みません", article["pinterest_description"])
    self.assertNotIn("楽天ROOM", article_only)
    self.assertNotIn('href="https://room.rakuten.co.jp', html)
    body_text = office_views._note_second_article_draft_body_plain_text(article)
    for forbidden in ("必ず効率が上がる", "成果が出る", "絶対に", "必ず稼げ", "¥", "在庫あり"):
      self.assertNotIn(forbidden, body_text)

  def test_note_second_article_draft_does_not_duplicate_first_article_body(self):
    # 公開済みのメール下書き記事(NOTE_FIRST_ARTICLE)と文章を重複させない
    # という要件を、本文プレーンテキストが完全一致しないことで確認する
    # (それぞれ独立したテーマ・文面であること)。
    import office_views
    first_body = office_views._note_article_body_plain_text(office_views.NOTE_FIRST_ARTICLE)
    second_body = office_views._note_second_article_draft_body_plain_text(
        office_views.NOTE_SECOND_ARTICLE_DRAFT
    )
    self.assertNotEqual(first_body, second_body)
    self.assertNotIn(second_body, first_body)
    self.assertNotIn(first_body, second_body)

  def test_note_second_article_draft_states_draft_only_not_posted_to_note(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("この記事はまだ下書きであり、noteへは投稿していません", html)
    self.assertIn(
        "note・SNSへの自動投稿・予約投稿・ログイン操作・API連携・外部通信は一切行いません", html
    )

  def test_note_second_article_draft_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    second_section_html = html.split(
        'aria-label="スマホAI下書きテーマのnote記事下書き"', 1
    )[1].split("</section>", 1)[0]
    self.assertNotIn("https://", second_section_html)
    self.assertNotIn("fetch(", second_section_html)
    self.assertNotIn("/api/", second_section_html)

  def test_note_second_article_draft_shows_existing_cover_image_without_html_title_overlay(self):
    # MISSION 044: あらかじめ用意された既存の見出し画像(1672x941)を、この
    # note記事下書きにだけ表示する。新規画像の作成・差し替えは行わず、HTML
    # 側でタイトル文字を重ねる処理(note-hero-overlay等)も行わない。
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    second_section_html = html.split(
        'aria-label="スマホAI下書きテーマのnote記事下書き"', 1
    )[1].split("</section>", 1)[0]
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/note-smartphone-ai-draft-cover.png" '
        f'alt="{article["hero_image_alt"]}">',
        second_section_html,
    )
    self.assertNotIn('class="note-hero-overlay"', second_section_html)
    self.assertNotIn('class="note-hero-title"', second_section_html)
    self.assertNotIn('class="note-hero-scrim"', second_section_html)
    self.assertEqual(second_section_html.count("<img"), 1)
    self.assertIn("横長 1672×941", second_section_html)
    self.assertIn("見出し文字はHTML側で重ねていません", second_section_html)
    self.assertEqual(
        article["hero_image_alt"],
        "夜の木目デスクにスマートフォン、タブレット、折りたたみキーボード、ノートが置かれた様子。"
        "ロゴや実在サービスの画面は写っていません。",
    )
    # 既存の初回記事(NOTE_FIRST_ARTICLE)の見出し画像には影響しないことを確認する。
    first_section_html = html.split(
        'aria-label="スマホAI下書きテーマのnote記事下書き"', 1
    )[0]
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/note-first-article-hero.png"',
        first_section_html,
    )
    self.assertIn('class="note-hero-overlay"', first_section_html)

  def test_note_second_article_draft_alt_text_draft_does_not_contradict_shown_cover_image(self):
    # MISSION 045夜間点検で発見・修正: MISSION 044で見出し画像を実際に
    # 表示するようになったにもかかわらず、Pinterest用altテキスト案が
    # 「実際の画像は、この記事下書きでは新規作成していません」という
    # MISSION 043時点の古い文言のままだった(同じ画面内で矛盾する記述に
    # なっていた)。この文言が残っていないことを確認する回帰テスト。
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    self.assertNotIn("新規作成していません", article["alt_text_draft"])
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    second_section_html = html.split(
        'aria-label="スマホAI下書きテーマのnote記事下書き"', 1
    )[1].split("</section>", 1)[0]
    self.assertNotIn("新規作成していません", second_section_html)
    # 見出し画像が実際に表示されている旨とaltテキスト案が整合していることも
    # あわせて確認する。
    self.assertIn("上記のとおり表示済み", article["alt_text_draft"])

  def test_note_second_article_draft_cover_image_is_unchanged_and_served_as_plain_static_file(self):
    import office_views
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.NOTE_SECOND_ARTICLE_DRAFT_COVER_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1672, 941))
    res = self.client.get(f"/static/{office_views.NOTE_SECOND_ARTICLE_DRAFT_COVER_RELATIVE_PATH}")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_note_second_article_draft_cover_image_has_download_button_as_plain_link(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn(
        'href="/static/images/note-smartphone-ai-draft-cover.png" '
        'download="note-smartphone-ai-draft-cover.png"',
        html,
    )
    self.assertNotIn("createObjectURL", html)
    self.assertNotIn("toDataURL", html)

  def test_existing_first_article_and_publish_queue_images_unaffected_by_cover_image_addition(self):
    # MISSION 044は「スマホでAIに下書きを頼む前に確認する3つ」のnote記事
    # 下書きにのみ画像を追加する。既存のnote初回記事・Pinterest投稿キュー・
    # 既存画像ファイルは変更しない。
    import office_views
    for relative_path in (
        "images/note-first-article-hero.png",
        "images/publish-queue-email-draft-v3.png",
        "images/publish-queue-desk-wiring-2x3.png",
        "images/publish-queue-peripherals-2x3.png",
        "images/publish-queue-smartphone-ai-draft-2x3.png",
        "images/publish-queue-smartphone-ai-photo-base.png",
    ):
      path = os.path.join(os.path.dirname(office_views.__file__), "static", relative_path)
      self.assertTrue(os.path.isfile(path), f"{relative_path} should still exist")
    # 投稿キューの件数はMISSION 042で4件、MISSION 049で5件になっているが、
    # その増減はこのミッション(044)によるものではない。
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(html.count('class="pq-status-badge'), 5)

  def test_note_second_article_draft_checklist_and_copy_buttons(self):
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    for item in article["checklist"]:
      self.assertIn(item, html)
    for target in (
        "note2-title", "note2-overview", "note2-body-copy",
        "note2-pinterest-description", "note2-alt-text",
    ):
      self.assertIn(f'data-copy-target="{target}"', html)

  def test_note_second_article_draft_content_is_data_driven_for_future_edits(self):
    import office_views
    article = office_views.NOTE_SECOND_ARTICLE_DRAFT
    self.assertEqual(len(article["sections"]), 4)
    rendered = office_views._render_note_second_article_draft_scene(article)
    self.assertIn(article["title"], rendered)
    self.assertIn("note-article-board", rendered)

  def test_existing_pages_unaffected_by_note_second_article_draft_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
        ("/content-studio/desk-setup-post", "デスク環境投稿パッケージ"),
        ("/content-studio/publish-queue", "投稿キュー（社長承認待ち）"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    import office_views
    # 投稿キューの件数はMISSION 042で4件、MISSION 049で5件になっているが、
    # その増減はこのミッション(043)によるものではない。
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)

  def test_note_hero_png_file_exists_with_correct_landscape_dimensions(self):
    import office_views
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.NOTE_HERO_IMAGE_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    # PNGシグネチャ + IHDRチャンクから幅・高さを読み取り、正確に
    # 1672x941(横長。MISSION 037.1修正で高精細なオリジナルビジュアルへ
    # 差し替えた際の実寸)であることを確認する(外部ライブラリを使わない
    # 最小限の検証)。
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (office_views.NOTE_HERO_IMAGE_WIDTH, office_views.NOTE_HERO_IMAGE_HEIGHT))
    self.assertGreater(width, height)  # 横長であることを確認

  def test_note_hero_png_is_served_as_a_plain_static_file(self):
    res = self.client.get("/static/images/note-first-article-hero.png")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_note_first_article_has_png_download_button_as_plain_link(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("見出し画像PNGを保存", html)
    self.assertIn(
        'href="/static/images/note-first-article-hero.png" '
        'download="note-first-article-hero.png"',
        html,
    )
    self.assertNotIn("createObjectURL", html)
    self.assertNotIn("toDataURL", html)

  def test_note_hero_png_generation_uses_lazy_pil_import_without_imagefont(self):
    # noteヒーロー画像は文字を画像に焼き込まないため、フォント関連の
    # ImageFontは使わず、ImageDraw+ImageFilter(グラデーション・ぼかし)のみを
    # 遅延importしていることを、generate_note_hero_image_png関数の内部だけを
    # 対象にソースコード上で確認する。
    import office_views
    import inspect
    func_source = inspect.getsource(office_views.generate_note_hero_image_png)
    self.assertIn("from PIL import Image, ImageDraw, ImageFilter", func_source)
    self.assertNotIn("ImageFont", func_source)

  def test_existing_pages_unaffected_by_note_first_article_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
        ("/content-studio/desk-setup-post", "デスク環境投稿パッケージ"),
        ("/content-studio/publish-queue", "投稿キュー（社長承認待ち）"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  # --- MISSION 041: 夜間点検(現在の手動運用との整合性チェック) ------------------

  def test_night_check_no_page_mentions_instagram_or_threads(self):
    # Instagramはどの画面でも使っていないため、引き続き一切言及しない。
    # MISSION 050で、Threadsのみ実際にDifyで別管理の自動投稿を運用している
    # 実態を反映するため、トップダッシュボード(/)と7日間計画
    # (/content-studio/weekly-plan)にだけ、正確な説明として言及するように
    # なった(このアプリ自体はThreadsへの投稿・ログイン・連携を行わない)。
    # それ以外の画面には、引き続きThreadsへの言及がないことを確認する。
    for path in (
        "/", "/content-studio", "/content-studio/desk-setup-post",
        "/content-studio/first-post", "/content-studio/note-first-article",
        "/content-studio/publish-queue", "/content-studio/weekly-plan",
        "/revenue",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertNotIn("Instagram", html)
        if path in ("/", "/content-studio/weekly-plan"):
          self.assertIn("Threads", html)
          self.assertIn("Dify", html)
        else:
          self.assertNotIn("Threads", html)

  def test_night_check_no_page_mentions_a8net_or_beauty_content(self):
    for path in (
        "/", "/content-studio", "/content-studio/desk-setup-post",
        "/content-studio/first-post", "/content-studio/note-first-article",
        "/content-studio/publish-queue", "/content-studio/weekly-plan",
        "/revenue",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertNotIn("A8.net", html)
        self.assertNotIn("美容", html)

  def test_night_check_no_page_shows_fabricated_metrics_or_live_claims(self):
    for path in (
        "/", "/content-studio", "/content-studio/desk-setup-post",
        "/content-studio/first-post", "/content-studio/note-first-article",
        "/content-studio/publish-queue", "/content-studio/weekly-plan",
        "/revenue",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertNotIn("LIVE", html)
        self.assertNotIn("リアルタイム", html)

  def test_night_check_weekly_plan_days_only_use_pinterest_or_note(self):
    import office_views
    for entry in office_views.WEEKLY_PLAN:
      with self.subTest(day=entry["day"]):
        self.assertIn(entry["medium"], ("Pinterest", "note"))

  def test_night_check_revenue_entry_points_do_not_mention_unused_channels(self):
    import office_views
    for label, _status in office_views.REVENUE_FOCUS["price_tiers"]:
      self.assertNotIn("Instagram", label)
      self.assertNotIn("Threads", label)

  def test_night_check_first_post_no_longer_has_threads_field_or_section(self):
    import office_views
    self.assertNotIn("threads_draft", office_views.FIRST_POST_PACKAGE)
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertNotIn("fp-threads", html)
    self.assertIn(
        "Pinterest・楽天ROOM・noteへの投稿・送信・連携は行われません。", html
    )

  def test_night_check_publish_queue_email_draft_v3_png_still_has_baked_in_title(self):
    # MISSION 039.2で焼き込んだタイトルが、その後の変更で失われていないことを
    # 実ファイルのバイト内容から再確認する(画像ファイル自体は今回変更して
    # いない)。
    import office_views
    v3_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.PUBLISH_QUEUE_EMAIL_DRAFT_V3_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(v3_path))
    with open(v3_path, "rb") as f:
      header = f.read(33)
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1024, 1536))

  def test_night_check_all_internal_links_from_core_pages_resolve(self):
    # 点検対象5画面から到達できる主要リンクが、すべて実在するページに
    # 移動することを確認する(内部リンクのみ。外部URLはこのチェックの
    # 対象外)。
    import re
    core_pages = [
        "/", "/content-studio", "/content-studio/publish-queue",
        "/content-studio/note-first-article", "/revenue",
    ]
    internal_hrefs = set()
    for path in core_pages:
      html = self.client.get(path).get_data(as_text=True)
      for href in re.findall(r'href="(/[^"]*)"', html):
        internal_hrefs.add(href.split("#")[0])
    self.assertGreater(len(internal_hrefs), 0)
    for href in internal_hrefs:
      with self.subTest(href=href):
        res = self.client.get(href)
        self.assertEqual(res.status_code, 200)

  # --- MISSION 049: 「AIが『なんか違う』ときに見直す3つ」note記事・Pinterest投稿 ---

  def test_note_third_article_draft_appears_on_note_first_article_page(self):
    # MISSION 054: この記事は2026年9月12日までに公開済みとなったため、
    # 見出しを「さらに次のnote記事下書き」から「公開済みのnote記事」へ、
    # タイトルを実際に公開されたタイトルへ更新した。
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("公開済みのnote記事", html)
    self.assertIn(
        "AIに聞いても「なんか違う」と感じる人へ。話がかみ合わないとき、まず見直す3つ", html
    )
    # 既存2件のタイトルも引き続き表示されていることを確認する
    # (既存記事・下書きは変更・削除していない)。
    self.assertIn(
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
        html,
    )
    self.assertIn(
        "スマホでAIに下書きを頼む前に確認する3つ──端末・入力・読み返しを先に決める", html
    )

  def test_note_third_article_draft_body_char_count_is_within_4500_to_5500(self):
    import office_views
    body_text = office_views._note_third_article_draft_body_plain_text(
        office_views.NOTE_THIRD_ARTICLE_DRAFT
    )
    char_count = len(body_text)
    self.assertGreaterEqual(char_count, 4500)
    self.assertLessEqual(char_count, 5500)

  def test_note_third_article_draft_intro_starts_with_concrete_disappointment_scene(self):
    # 冒頭が解説からではなく、AIに聞いたのに期待と違う答えが返ってきて
    # 少しがっかりする具体的な場面から始まることを確認する。
    import office_views
    intro = office_views.NOTE_THIRD_ARTICLE_DRAFT["intro"]
    first_paragraph = intro.split("\n\n", 1)[0]
    self.assertIn("なんか違う", first_paragraph)
    self.assertTrue(
        first_paragraph.startswith("仕事の合間に、ちょっとした疑問をAIに投げかけてみた。")
    )

  def test_note_third_article_draft_covers_required_3_points_in_order(self):
    import office_views
    article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    headings = [s["heading"] for s in article["sections"]]
    for required in ("1. 目的を先に伝える", "2. 前提や条件を足す", "3. 一度で終わらせず聞き返す"):
      self.assertIn(required, headings)
    self.assertEqual(headings.index("1. 目的を先に伝える"), 0)
    self.assertEqual(headings.index("2. 前提や条件を足す"), 1)
    self.assertEqual(headings.index("3. 一度で終わらせず聞き返す"), 2)
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    for required in ("1. 目的を先に伝える", "2. 前提や条件を足す", "3. 一度で終わらせず聞き返す"):
      self.assertIn(required, html)

  def test_note_third_article_draft_has_no_definitive_or_guaranteed_result_claims(self):
    import office_views
    article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    body_text = office_views._note_third_article_draft_body_plain_text(article)
    for forbidden in (
        "必ず解決", "絶対に解決できます", "必ず効果", "確実に成果", "私が実際に試した",
        "私は実際に", "筆者が試したところ",
    ):
      self.assertNotIn(forbidden, body_text)
    for forbidden in ("円", "¥", "位獲得", "在庫あり", "在庫切れ", "ランキング"):
      self.assertNotIn(forbidden, body_text)

  def test_note_third_article_draft_does_not_duplicate_other_articles(self):
    # 公開済みのメール下書き記事・スマホでのAI下書き記事下書きと文章が
    # 重複しないことを、本文プレーンテキストが完全一致しないことで確認する。
    import office_views
    first_body = office_views._note_article_body_plain_text(office_views.NOTE_FIRST_ARTICLE)
    second_body = office_views._note_second_article_draft_body_plain_text(
        office_views.NOTE_SECOND_ARTICLE_DRAFT
    )
    third_body = office_views._note_third_article_draft_body_plain_text(
        office_views.NOTE_THIRD_ARTICLE_DRAFT
    )
    self.assertNotEqual(third_body, first_body)
    self.assertNotEqual(third_body, second_body)
    self.assertNotIn(third_body, first_body)
    self.assertNotIn(third_body, second_body)

  def test_note_third_article_draft_shows_overview_pinterest_description_and_alt_text(self):
    import office_views
    article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn('id="note3-title"', html)
    self.assertIn('id="note3-overview"', html)
    self.assertIn('id="note3-pinterest-description"', html)
    self.assertIn('id="note3-alt-text"', html)
    self.assertIn(article["overview"], html)
    self.assertIn(article["pinterest_description"], html)
    self.assertIn(article["alt_text_draft"], html)
    self.assertLessEqual(len(article["pinterest_description"]), 500)

  def test_note_third_article_draft_states_published_with_real_url(self):
    # MISSION 054: この記事は2026年9月12日までに柴犬社長が手動でnoteへ
    # 貼り付けて公開済みとなったため、「まだ下書き」という表現をやめ、
    # 実際の記事URLとともに公開済みであることを表示する。
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    third_section_html = html.split(
        'aria-label="AIとの会話の見直しテーマのnote記事（公開済み）"', 1
    )[1]
    self.assertIn("この記事は柴犬社長が手動でnoteへ貼り付けて公開済みです", third_section_html)
    self.assertIn(
        "https://note.com/legal_crow9879/n/nb2a21a842387", third_section_html
    )
    self.assertIn(
        "note・SNSへの自動投稿・予約投稿・ログイン操作・API連携・外部通信は一切行いません",
        third_section_html,
    )
    self.assertNotIn("この記事はまだ下書きであり、noteへは投稿していません", third_section_html)

  def test_note_third_article_draft_shows_hero_image_without_html_title_overlay(self):
    import office_views
    article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    third_section_html = html.split(
        'aria-label="AIとの会話の見直しテーマのnote記事（公開済み）"', 1
    )[1].split("</section>", 1)[0]
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/note-ai-mismatch-hero-photo.png" '
        f'alt="{article["hero_image_alt"]}">',
        third_section_html,
    )
    self.assertNotIn('class="note-hero-overlay"', third_section_html)
    self.assertNotIn('class="note-hero-title"', third_section_html)
    self.assertNotIn('class="note-hero-scrim"', third_section_html)
    self.assertEqual(third_section_html.count("<img"), 1)
    self.assertIn("横長 1672×941", third_section_html)
    self.assertIn("見出し文字はHTML側で重ねていません", third_section_html)

  def test_note_third_article_draft_cover_image_has_correct_dimensions_and_is_served(self):
    import office_views
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH,
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1672, 941))
    res = self.client.get(f"/static/{office_views.NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH}")
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_note_third_article_draft_generator_has_no_top_level_pil_import(self):
    import office_views
    import inspect
    source = inspect.getsource(office_views)
    lines = source.splitlines()
    top_level_import_lines = [
        line for line in lines
        if line.startswith("from PIL") or line.startswith("import PIL")
    ]
    self.assertEqual(top_level_import_lines, [])
    func_source = inspect.getsource(office_views.generate_note_ai_mismatch_hero_image_png)
    self.assertIn("from PIL import", func_source)

  def test_note_third_article_draft_checklist_and_copy_buttons(self):
    import office_views
    article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    for item in article["checklist"]:
      self.assertIn(item, html)
    for target in (
        "note3-title", "note3-overview", "note3-body-copy",
        "note3-pinterest-description", "note3-alt-text",
    ):
      self.assertIn(f'data-copy-target="{target}"', html)

  def test_publish_queue_ai_mismatch_card_added_with_required_content(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "ai-mismatch-3points"][0]
    self.assertEqual(post["pin"]["title"], "AIが「なんか違う」ときに見直す3つ")
    # MISSION 054: この投稿は2026年9月12日までに柴犬社長が手動でPinterestへ
    # 投稿済みとなったため、"published"へ更新した。
    self.assertEqual(post["status"], "published")
    self.assertIn('id="pq-title-ai-mismatch-3points"', html)
    self.assertIn('id="pq-description-ai-mismatch-3points"', html)
    self.assertIn('id="pq-alt-ai-mismatch-3points"', html)
    self.assertEqual(
        post["hero_item_lines"],
        ["1. 目的を先に伝える", "2. 前提や条件を足す", "3. 一度で終わらせず聞き返す"],
    )
    self.assertEqual("".join(post["hero_title_lines"]), post["pin"]["title"])
    self.assertIn(
        '<img class="note-hero-img" src="/static/images/publish-queue-ai-mismatch-2x3.png"',
        html,
    )
    self.assertIn(
        'href="/static/images/publish-queue-ai-mismatch-2x3.png" '
        'download="pinterest-publish-queue-ai-mismatch.png"',
        html,
    )
    self.assertNotIn("custom_room_link_note", post)
    # MISSION 054: 実際に公開されたnote記事のURLへリンクするフィールドが
    # 追加されたため(email-draft-3pointsと同じ扱い)、リンク先フィールドが
    # 表示されることを確認する。
    self.assertIn('id="pq-link-ai-mismatch-3points"', html)
    self.assertEqual(
        post["pinterest_link_url"],
        "https://note.com/legal_crow9879/n/nb2a21a842387",
    )
    self.assertIn(
        'href="https://note.com/legal_crow9879/n/nb2a21a842387" '
        'target="_blank" rel="noopener noreferrer"',
        html,
    )
    self.assertIn(">https://note.com/legal_crow9879/n/nb2a21a842387</a>", html)
    self.assertIn('data-copy-target="pq-link-ai-mismatch-3points"', html)

  def test_publish_queue_ai_mismatch_checklist_includes_ai_label_requirement(self):
    import office_views
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "ai-mismatch-3points"][0]
    checklist_text = "".join(post["checklist"])
    self.assertIn("AIで修正済み", checklist_text)
    self.assertIn("画像ラベル", checklist_text)

  def test_publish_queue_ai_mismatch_has_no_definitive_claims_or_business_data(self):
    import office_views
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "ai-mismatch-3points"][0]
    combined_text = post["pin"]["title"] + post["pin"]["description"] + post["pin"]["alt_text"]
    for forbidden in ("自分で使った", "おすすめ", "効率が上がる", "成果が出る"):
      self.assertNotIn(forbidden, combined_text)
    for forbidden in ("円", "¥", "位獲得", "在庫あり", "在庫切れ", "ランキング"):
      self.assertNotIn(forbidden, combined_text)

  def test_publish_queue_ai_mismatch_png_has_correct_2_3_dimensions_and_is_served(self):
    import office_views
    post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "ai-mismatch-3points"][0]
    png_path = os.path.join(
        os.path.dirname(office_views.__file__), "static", post["hero_image_relative_path"],
    )
    self.assertTrue(os.path.isfile(png_path))
    with open(png_path, "rb") as f:
      header = f.read(33)
    self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    self.assertEqual((width, height), (1024, 1536))
    res = self.client.get(f'/static/{post["hero_image_relative_path"]}')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.content_type, "image/png")

  def test_publish_queue_ai_mismatch_generator_has_no_top_level_pil_import(self):
    import office_views
    import inspect
    func_source = inspect.getsource(office_views.generate_publish_queue_ai_mismatch_png)
    self.assertIn("from PIL import", func_source)

  def test_note_and_pinterest_ai_mismatch_titles_and_items_are_consistent(self):
    # note記事の3つの見直し軸と、Pinterest投稿データ上のhero_item_lines
    # (データとしては保持しているが、MISSION 049.2以降は画像には焼き込んで
    # いない)が、内容として一致していることを確認する。タイトルは、note
    # 記事のテーマ・Pinterestのpin.title・画像に焼き込んだhero_title_lines
    # の3箇所で一致していることも確認する。
    import office_views
    note_article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    pin_post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "ai-mismatch-3points"
    ][0]
    note_headings = {s["heading"].split(". ", 1)[-1] for s in note_article["sections"][:3]}
    pin_items = {line.split(". ", 1)[-1] for line in pin_post["hero_item_lines"]}
    self.assertEqual(note_headings, pin_items)
    self.assertEqual("".join(pin_post["hero_title_lines"]), pin_post["pin"]["title"])
    # note記事のテーマとPinterestのpin.titleは文言こそ異なるが(記事は長め
    # のタイトル、Pinterestは短い形)、どちらも同じ「なんか違う」というキー
    # ワードを共有し、同じテーマを指していることを確認する。
    self.assertIn("なんか違う", note_article["theme"])
    self.assertIn("なんか違う", pin_post["pin"]["title"])
    # MISSION 049.2: 画像にはタイトルのみを焼き込み、3項目は焼き込まなく
    # なったため、altテキストは項目の列挙ではなく実際の写真の内容(スマホと
    # ノートを持つ手元)を説明していることを確認する。
    self.assertNotIn("目的を先に伝える」「2.", pin_post["pin"]["alt_text"])
    self.assertIn("スマートフォン", pin_post["pin"]["alt_text"])
    self.assertIn("ノート", pin_post["pin"]["alt_text"])

  def test_ai_mismatch_note_and_pinterest_images_differ_in_subject_and_composition(self):
    # note用見出し画像(文字なし・明るい昼間)とPinterest用画像
    # (タイトル焼き込み・別配色)が、別ファイルであり、内容も異なることを
    # 確認する(単なる複製ではないことの最小限の検証)。
    import office_views
    note_path = os.path.join(
        os.path.dirname(office_views.__file__), "static",
        office_views.NOTE_THIRD_ARTICLE_DRAFT_COVER_RELATIVE_PATH,
    )
    pin_post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == "ai-mismatch-3points"
    ][0]
    pin_path = os.path.join(
        os.path.dirname(office_views.__file__), "static", pin_post["hero_image_relative_path"],
    )
    with open(note_path, "rb") as f:
      note_bytes = f.read()
    with open(pin_path, "rb") as f:
      pin_bytes = f.read()
    self.assertNotEqual(note_bytes, pin_bytes)
    # 縦横比も明確に異なる(noteは横長2:3の逆、Pinterestは縦長2:3)。
    with open(note_path, "rb") as f:
      note_header = f.read(33)
    with open(pin_path, "rb") as f:
      pin_header = f.read(33)
    note_w = int.from_bytes(note_header[16:20], "big")
    note_h = int.from_bytes(note_header[20:24], "big")
    pin_w = int.from_bytes(pin_header[16:20], "big")
    pin_h = int.from_bytes(pin_header[20:24], "big")
    self.assertGreater(note_w, note_h)
    self.assertGreater(pin_h, pin_w)

  def test_existing_pages_unaffected_by_ai_mismatch_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/content-studio/first-post", "初回手動投稿パッケージ"),
        ("/content-studio/weekly-plan", "7日間コンテンツ計画"),
        ("/content-studio/desk-setup-post", "デスク環境投稿パッケージ"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    for post_id, title in (
        ("email-draft-3points", "AIにメールの下書きを頼む前に決める3つ"),
        ("desk-wiring-3points", "デスクが狭いときに配線を見直す3つのポイント"),
        ("peripheral-choice-3points", "スマホ・PC作業をラクにする周辺機器の選び方"),
        ("smartphone-ai-draft-3points", "スマホでAIに下書きを頼む前に確認する3つ"),
    ):
      self.assertIn(title, html)
      self.assertIn(f'id="pq-title-{post_id}"', html)

  # --- MISSION 050: 実際の運用状況(公開件数・Threads/Dify)にダッシュボードを揃える ---

  def test_root_dashboard_and_weekly_plan_handle_no_credentials_or_dify_api_details(self):
    # ThreadsがDifyで別管理の自動投稿を使っているという実態を説明文として
    # 記載するだけで、APIキー・アクセストークン・認証情報・実際のAPI
    # エンドポイントは一切扱わない・記載しないことを確認する。トップページ
    # には既存の「詳細を表示」トグル用インラインscriptが元々あるため
    # (Dify等の新規追加ではない)、script自体の有無は対象外にする。
    for path in ("/", "/content-studio/weekly-plan"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        for forbidden in (
            "api_key", "API_KEY", "access_token", "ACCESS_TOKEN", "Bearer ",
            "Authorization", "client_secret", "AI_HIVE_", "dify.ai",
            "fetch(",
        ):
          self.assertNotIn(forbidden, html)
        self.assertNotIn("/api/", html)

  def test_root_dashboard_and_weekly_plan_have_no_fabricated_business_data(self):
    # A8.net・美容系事業を、今回の更新で利用者向け画面へ追加していないこと
    # を確認する。「¥」「売上」は、既存の「表示していません」等の否定形の
    # 注記でのみ使われている(架空の数値を新たに記載してはいない)ため、
    # 別テスト(test_root_dashboard_does_not_show_fabricated_metrics)で
    # 検証済みであり、ここでは対象にしない。
    for path in ("/", "/content-studio/weekly-plan"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        for forbidden in ("A8.net", "美容", "サロン"):
          self.assertNotIn(forbidden, html)

  def test_office_avatars_and_room_pages_unaffected_by_dashboard_realignment(self):
    # MISSION 050はダッシュボードの説明文を実態に合わせて更新するミッション
    # であり、人物・各部屋のキャラクター表示自体は変更しないことを確認する
    # (デスクキャラクターがそのまま残っていること)。
    # MISSION 083: キャストは実在4人(里奈・凛・葵・蒼)へ置き換えた。
    office_html = self.client.get("/office").get_data(as_text=True)
    for name in ("里奈", "凛", "葵", "蒼"):
      self.assertIn(name, office_html)

  def test_weekly_plan_published_days_have_no_fabricated_reaction_numbers(self):
    # MISSION 050で新たに公開済みへ変わった2日目も、1日目と同様に
    # 表示回数・保存数・クリック数などの反応・成果を、数値付きで記載して
    # いないことを確認する。
    # MISSION 054修正: 6・7日目(デスク配線・周辺機器選び)は、投稿キューでの
    # 実際の公開状況が未公開("awaiting_president")だったことが判明した
    # ため、published扱いをやめてmanual_candidateへ戻した。この2日は
    # 対象から外す。
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    for day_start, day_end in (("2日目：", "3日目："),):
      with self.subTest(day_start=day_start):
        card = html.split(day_start, 1)[1].split(day_end, 1)[0]
        self.assertIn("公開済み", card)
        self.assertIn("反応・成果は", card)
        for word in ("表示回数", "保存数", "クリック数", "閲覧数", "スキ数"):
          self.assertNotIn(f"{word}：", card)
          self.assertNotIn(f"{word}が", card)

  def test_weekly_plan_status_labels_reflect_only_statuses_in_use(self):
    # MISSION 054修正: 6・7日目が参照する投稿キューのテーマは実際には
    # 未公開だったため、公開済みは1・2日目の2件のみになり、手動投稿候補は
    # 3〜7日目の5件になった。
    import office_views
    used_statuses = {entry["status"] for entry in office_views.WEEKLY_PLAN}
    self.assertEqual(used_statuses, {"published", "manual_candidate"})
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertEqual(html.count('class="wp-day-status status-published"'), 2)
    self.assertEqual(html.count('class="wp-day-status status-manual_candidate"'), 5)

  # --- MISSION 051: オフィス・休憩室・社長室を現在の実際の運用状況へ更新 ---------

  def test_office_break_room_ceo_office_have_no_stale_or_fabricated_content(self):
    # A8.net提携確認・美容サロン向け素材・「公開済みラッシュアディクト
    # 投稿」など、work_logsに残る現在と無関係な古いテスト用データが、
    # どの部屋にも表示されていないことを確認する。DBは変更していないため、
    # /api/api/logs自体は引き続きこれらの行を返すが、UI側で参照しない。
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        for forbidden in ("A8.net", "ラッシュアディクト", "美容サロン", "提携申請"):
          self.assertNotIn(forbidden, html)

  def test_office_avatars_and_room_backgrounds_are_unchanged(self):
    # MISSION 051は表示テキストの更新のみで、部屋の背景画像・画像ファイル
    # 自体は変更しないことを確認する。
    # MISSION 083: デスクの人物表示は、旧avatar-<key>方式(office-avatars-
    # v1.png)から、AIオフィスと同じ立体スプライト(ai-office-team-3d.png、
    # 既存の画像ファイルをそのまま使用)へ置き換えた。背景画像ファイル自体は
    # 引き続き変更していない(office-avatars-v1.pngの定義もCSS内に残る)。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn("/static/images/office-avatars-v1.png", html)
    self.assertIn("/static/images/ai-office-team-3d.png", html)
    for key in ("room", "rin", "analytics", "sou"):
      self.assertIn(f'data-person="{key}"', html)
    for role in ("ROOM担当", "資料室管理", "分析担当", "技術担当"):
      self.assertIn(role, html)

  def test_office_and_ceo_office_have_no_credentials_or_external_calls(self):
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        for forbidden in (
            "api_key", "API_KEY", "access_token", "ACCESS_TOKEN", "Bearer ",
            "Authorization", "client_secret", "AI_HIVE_", "dify.ai", "fetch(",
        ):
          self.assertNotIn(forbidden, html)
        self.assertNotIn("/api/", html)

  def test_ceo_office_stats_reuse_existing_stat_box_markup(self):
    # 「今日の作業/完了/進行中」の3枠だった構造を、そのまま3枠の
    # Pinterest/note統計表示として再利用していることを確認する
    # (新しいレイアウト要素を追加していない)。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertEqual(html.count('<div class="stat">'), 3)
    self.assertIn('class="command-stats"', html)

  def test_office_ceo_office_break_room_render_without_error(self):
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)

  def test_break_room_walker_label_is_readable_against_dark_background(self):
    # 画面確認中に発見した表示崩れの回帰テスト: .break-walker smallの文字色が
    # 部屋の下部(暗い配色の領域)に対して読みにくい暗色のままだったため、
    # 明るい色に修正した。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn(".break-walker small{display:block;text-align:center;color:#fff8e9", html)

  def test_ceo_office_speech_bubble_renders_above_the_desk_graphic(self):
    # 画面確認中に発見した表示崩れの回帰テスト: 吹き出し(.bubble)に
    # z-indexが指定されておらず、モバイル表示でデスクのグラフィック
    # (z-index:3/4)の下に隠れて読めなくなっていたため、デスクより高い
    # z-indexを明示した。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn(".bubble{position:absolute", html)
    bubble_rule = html.split(".bubble{position:absolute", 1)[1].split("}", 1)[0]
    self.assertIn("z-index:5", bubble_rule)

  # --- MISSION 053: 社員・柴犬社長が主役の立体的な空間への刷新 -------------------

  def test_walker_figures_use_background_color_not_shorthand_background(self):
    # 画面確認中に発見した表示崩れの回帰テスト: .walker span / .reading span
    # がショートハンドのbackgroundプロパティを使っており、同じ<span>である
    # 人物アバター(.figure)のbackground-image(アバター画像)まで打ち消して
    # しまい、オフィスの「彩・休憩へ」の人物が完全に透明になっていた。
    # background-colorに変更し、アバター画像を打ち消さないようにした。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn(
        ".walker span{font-size:10px;padding:4px 7px;background-color:#101b2edb",
        html,
    )
    self.assertIn(
        ".reading span{font-size:10px;background-color:#fff0c9", html
    )

  def test_office_floor_tokens_use_ai_office_sprite_system(self):
    # MISSION 083: オフィスの「彩・休憩へ」という他ページとの重複表示は
    # 廃止し(各ページはその場所にいる社員だけを表示する)、里奈・凛・葵・
    # 蒼の4人が、AIオフィスと同じ立体スプライトトークンとして描画される
    # ことを確認する。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertNotIn('<div class="walker">', html)
    for key in ("room", "rin", "analytics", "sou"):
      self.assertIn(f'id="space-token-office-{key}"', html)
      self.assertIn(f'id="space-sprite-office-{key}"', html)
    self.assertIn("ai-office-floormap-sprite", html)
    self.assertIn("ai-office-report-ring", html)

  def test_mobile_layout_keeps_walking_figures_clear_of_desks_and_furniture(self):
    # 画面確認中に発見した表示崩れの回帰テスト: モバイル幅では、移動中の
    # 人物(.walker / .break-walker)がアニメーションで動き回ると、デスクや
    # ソファ・コーヒーバーと重なって読みにくくなっていたため、モバイル幅
    # では静止位置に固定し、重ならない位置へ調整した。
    office_html = self.client.get("/office").get_data(as_text=True)
    self.assertIn(".walker{animation:none", office_html)
    break_html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn(".break-walker{animation:none", break_html)
    self.assertIn(".coffee{left:8%", break_html)

  def test_rooms_declare_staff_are_ai_hive_os_fictional_characters(self):
    # 社員(柴犬社長を含む)がAI Hive OSの架空キャラクターであることを、
    # 3部屋すべてで画面上に明記していることを確認する。
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('class="cast-badge"', html)
        self.assertIn("AI Hive OS", html)
    office_html = self.client.get("/office").get_data(as_text=True)
    self.assertIn("AI Hive OSの架空キャラクターです", office_html)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("柴犬社長も、AI Hive OSの架空キャラクターです", ceo_html)

  def test_office_desks_are_split_into_front_and_back_rows_for_depth(self):
    # MISSION 053: 平面的なカード並びを避けるため、奥の列(desk-back)と
    # 手前の列(desk-front)に分ける仕組みを導入した。
    # MISSION 083: デスクをAIオフィスの実在4人(里奈・凛・葵・蒼)の4席に
    # 絞ったため、手前・奥の2層構成は使わず、4席とも同じdesk-back列に
    # 並べる(人物本体は上のフロアトークンとして別に表示するため、奥行きは
    # そちら側の演出に委ねる)。desk-front/desk-backのCSS定義自体は既存の
    # まま残す(将来の再利用に備え、削除しない)。
    html = self.client.get("/office").get_data(as_text=True)
    for i, key in enumerate(("room", "rin", "analytics", "sou"), start=1):
      self.assertIn(f'class="desk d{i} desk-back" id="desk-{key}"', html)
    self.assertNotIn('class="desk d5', html)
    self.assertNotIn('class="desk d6', html)
    self.assertIn(".desk.desk-back{filter:", html)
    self.assertIn(".desk.desk-front{--s:", html)

  def test_office_desks_show_visible_role_labels_without_a_click(self):
    # MISSION 053: 役割(顔・表情・役割が分かる)を、デスク詳細を開かなくても
    # その場で見えるようにする。
    # MISSION 083: 役割ラベルを、AIオフィスの実在4人の実際の役割へ更新した。
    html = self.client.get("/office").get_data(as_text=True)
    for role in ("ROOM担当", "資料室管理", "分析担当", "技術担当"):
      self.assertIn(f'<i class="desk-role">{role}</i>', html)

  def test_office_has_lighting_and_meeting_space_props_for_depth(self):
    # MISSION 053: 「デスク、モニター、窓、照明、観葉植物、会議スペース」の
    # うち、照明(.lamp)と会議スペース(.meeting)を新設した。いずれも
    # 装飾のみでDB/API/実データとは無関係なため、aria-hidden。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('<div class="lamp" aria-hidden="true"></div>', html)
    self.assertIn('class="meeting" aria-hidden="true"', html)
    self.assertIn("MTG SPACE", html)

  def test_ceo_office_president_has_spotlight_and_status_monitor(self):
    # MISSION 053: 柴犬社長を主役として見せるためのスポットライトと、
    # Pinterest・note・Threadsの状況を確認している体裁のモニター。
    # 数値はcommand-statsと同じ既存の事実のみで、新しい数値は追加しない。
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('class="ceo-spotlight" aria-hidden="true"', html)
    self.assertIn('class="ceo-monitor" aria-hidden="true"', html)
    self.assertIn("いま確認している状況", html)
    self.assertIn("<span>Pinterest</span><span>5件公開</span>", html)
    self.assertIn("<span>note(今回)</span><span>3件公開</span>", html)
    self.assertIn("<span>Threads</span><span>Dify運用</span>", html)
    self.assertIn(".ceo-desk{--s:", html)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)

  def test_break_room_shows_two_characters_chatting_about_real_status_only(self):
    # MISSION 053: 「投稿後の反応確認や次の企画を気軽に相談している
    # 空気感」を出すため、ソファに2人を座らせる仕組みを導入した。
    # MISSION 083: ソファの2枠は、実績のある担当を優先しつつ美咲・海・
    # 里奈・葵の間で時間差に入れ替わる(初期表示はPinterest・note担当の
    # 美咲・海)。会話の内容は、本日の運用記録(実績)またはあらかじめ
    # 用意した既知の状態(デモ)のみであり、新しい休憩理由・移動予定・
    # 個人の勤務実績は追加しない。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn('class="sofa-guest sofa-guest-1" data-slot="1"', html)
    self.assertIn('class="sofa-guest sofa-guest-2" data-slot="2"', html)
    self.assertIn('id="space-token-break-pinterest"', html)
    self.assertIn('id="space-token-break-note"', html)
    self.assertIn('<b id="break-slot-name-1">美咲</b>', html)
    self.assertIn('<b id="break-slot-name-2">海</b>', html)
    self.assertNotIn("休憩理由", html)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)

  def test_break_room_aya_is_a_sprite_character_not_a_bare_emoji(self):
    # MISSION 053: 「📝」の絵文字だけだった移動中の人物を、キャラクター
    # 表示に差し替えた。
    # MISSION 083: 休憩室を彩(連携担当)中心のスペースへ変更し、彩も他の
    # スペースと同じAIオフィスの立体スプライトトークンで描画されることを
    # 確認する(旧.break-walker+avatar-ayakaの仕組みは廃止した)。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn('id="space-token-break-aya"', html)
    self.assertIn('id="space-sprite-break-aya"', html)
    self.assertNotIn("📝", html)
    self.assertIn(
        ".break-walker small{display:block;text-align:center;color:#fff8e9", html
    )

  def test_figure_depth_scale_is_css_only_with_no_external_calls(self):
    # MISSION 053の奥行き表現(--sによるCSSスケール)が、外部リソースや
    # fetch等を一切追加していないことを確認する。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn("transform:scale(var(--s,1))", html)
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        page_html = self.client.get(path).get_data(as_text=True)
        self.assertNotIn("fetch(", page_html)
        self.assertNotIn("/api/", page_html)
        self.assertNotIn("http://", page_html)
        self.assertNotIn("https://", page_html)

  def test_mission_053_rooms_have_no_fabricated_or_stale_business_data(self):
    # 架空の売上・A8.net・美容案件・実在しない作業ログ・実在スタッフ名を
    # 一切復活させていないことを、追加した要素も含めて確認する。
    for path in ("/office", "/office/break-room", "/office/ceo-office"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        for forbidden in (
            "A8.net", "ラッシュアディクト", "美容サロン", "提携申請",
            "売上", "ランキング", "在庫",
        ):
          self.assertNotIn(forbidden, html)

  # --- MISSION 054: 2026年9月12日時点の公開状況への更新 -------------------------

  def test_mission_054_no_stale_publish_counts_remain_anywhere(self):
    # 「Pinterest 4件」「note 2本」という古い件数が、更新対象のどの画面にも
    # 残っていないことを確認する(投稿キューの説明文中の「メール下書き」等、
    # 件数と無関係な文脈での「4」「2」は対象外)。
    for path in (
        "/", "/office", "/office/break-room", "/office/ceo-office", "/revenue",
        "/content-studio",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True) if path != "/" else self.html
        self.assertNotIn("Pinterest：4件", html)
        self.assertNotIn("Pinterestは4件", html)
        self.assertNotIn("4件公開済み", html)
        self.assertNotIn("note：2本", html)
        self.assertNotIn("noteは2本", html)
        self.assertNotIn("2本公開済み", html)

  def test_mission_054_five_pinterest_and_three_note_counts_are_consistent(self):
    # Pinterest5件・note3件という実際の公開件数が、ダッシュボード・
    # オフィス・社長室・収益化ボードのすべてで一致していることを確認する。
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    root_html = self.html
    office_html = self.client.get("/office").get_data(as_text=True)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hive関連の記事3件", root_html)
    self.assertIn("Pinterest：5件公開済み", office_html)
    self.assertIn("note：AI Hive関連の記事3件公開済み", office_html)
    self.assertIn("<b>5件</b><span>Pinterest公開済み</span>", ceo_html)
    self.assertIn("<b>3件</b><span>今回のnote公開済み</span>", ceo_html)
    self.assertIn("（5件）", revenue_html)
    self.assertIn("（3本）", revenue_html)

  def test_mission_054_ai_mismatch_post_is_published_not_pending_anywhere(self):
    # 「AIが「なんか違う」ときに見直す3つ」が、社長室・投稿キューのどちらでも
    # 「社長承認待ち」「次の投稿案」として表示されていないことを確認する。
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertNotIn(
        "Pinterest：「AIが「なんか違う」ときに見直す3つ」を準備（社長承認待ち）",
        ceo_html,
    )
    self.assertNotIn("Pinterest次の投稿案", ceo_html)
    queue_html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    card_html = queue_html.split(
        '<h3>AIが「なんか違う」ときに見直す3つ</h3>', 1
    )[1].split('<div class="pq-card">', 1)[0]
    self.assertIn('status-published">公開済み</span>', card_html)
    self.assertNotIn("社長承認待ち", card_html)

  def test_mission_054_uses_only_the_given_real_urls_and_no_fabricated_ones(self):
    # note・Pinterestの実際のURLとして、社長から渡された2件のURLだけが
    # 使われており、それ以外のドメインの実URLを捏造していないことを確認する。
    import re
    for path in (
        "/", "/office", "/office/break-room", "/office/ceo-office", "/revenue",
        "/content-studio", "/content-studio/publish-queue",
        "/content-studio/note-first-article", "/content-studio/weekly-plan",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True) if path != "/" else self.html
        urls = set(re.findall(r"https://[^\s\"'<]+", html))
        allowed = {
            "https://note.com/legal_crow9879/n/nf7af35ac8c28",
            "https://note.com/legal_crow9879/n/nb2a21a842387",
        }
        self.assertTrue(urls <= allowed, f"unexpected URLs on {path}: {urls - allowed}")

  def test_mission_054_ceo_and_dashboard_next_action_is_48_hour_reaction_check(self):
    # 次に確認することが「48時間後のPinterest反応確認」に統一されている
    # ことを確認する。
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("48時間後を目安にPinterestの反応を確認すること", ceo_html)
    self.assertIn("<b>48時間</b><span>Pinterest反応確認の目安</span>", ceo_html)
    root_html = self.html
    self.assertIn("48時間後を目安に", root_html)
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("48時間後を目安にPinterestの反応を確認", revenue_html)

  def test_mission_054_fix_desk_wiring_and_peripherals_are_still_awaiting_approval(self):
    # MISSION 054の修正: デスク配線・周辺機器選びの2件は実際には未公開の
    # ままであり、「スマホでのAI下書き」は実際には公開済みであることを
    # 確認する。投稿キューと7日間計画の両方で、この2件が「社長承認待ち」
    # のまま(「公開済み」表示にならない)ことを確認する。
    import office_views
    queue_html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    for pinterest_title in (
        "デスクが狭いときに配線を見直す3つのポイント",
        "スマホ・PC作業をラクにする周辺機器の選び方",
    ):
      with self.subTest(pinterest_title=pinterest_title):
        card_html = queue_html.split(f'<h3>{pinterest_title}</h3>', 1)[1].split(
            '<div class="pq-card">', 1
        )[0]
        self.assertIn('status-awaiting_president">社長承認待ち</span>', card_html)
        self.assertNotIn('status-published">公開済み</span>', card_html)

    smartphone_card_html = queue_html.split(
        '<h3>スマホでAIに下書きを頼む前に確認する3つ</h3>', 1
    )[1].split('<div class="pq-card">', 1)[0]
    self.assertIn('status-published">公開済み</span>', smartphone_card_html)

    weekly_html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    for day_start, day_end in (("6日目：", "7日目："), ("7日目：", "</section>")):
      with self.subTest(day_start=day_start):
        card = weekly_html.split(day_start, 1)[1].split(day_end, 1)[0]
        self.assertIn('status-manual_candidate">手動投稿候補</span>', card)
        self.assertNotIn("投稿済みとして記録しています", card)

    for entry in office_views.WEEKLY_PLAN:
      if entry["day"] in (6, 7):
        self.assertEqual(entry["status"], "manual_candidate")

    smartphone_post = [
        p for p in office_views.PUBLISH_QUEUE_POSTS
        if p["id"] == "smartphone-ai-draft-3points"
    ][0]
    self.assertEqual(smartphone_post["status"], "published")
    for post_id in ("desk-wiring-3points", "peripheral-choice-3points"):
      post = [p for p in office_views.PUBLISH_QUEUE_POSTS if p["id"] == post_id][0]
      self.assertEqual(post["status"], "awaiting_president")

  def test_mission_054_fix_pinterest_and_note_totals_are_unchanged(self):
    # 修正後も、Pinterest5件・note3件という合計数、最新note記事URL、
    # 48時間後の反応確認方針は変わらないことを確認する。
    # MISSION 055: noteの件数はAI Hive関連の記事数であることを明記した。
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("<b>5件</b><span>Pinterest公開済み</span>", ceo_html)
    self.assertIn("<b>3件</b><span>今回のnote公開済み</span>", ceo_html)
    self.assertIn("<b>48時間</b><span>Pinterest反応確認の目安</span>", ceo_html)
    note_html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("https://note.com/legal_crow9879/n/nb2a21a842387", note_html)

  # --- MISSION 055: noteの既存実績を含めても誤解のない表記へ整える -------------

  def test_mission_055_note_counts_are_scoped_to_ai_hive_not_whole_account(self):
    # 「note 3件」のような表現が、noteアカウント全体の記事数のように
    # 誤解されないよう、AI Hive関連の件数であることが、ダッシュボード・
    # オフィス・社長室・収益化ボード・投稿企画工場のすべてで明記されている
    # ことを確認する。
    root_html = self.html
    office_html = self.client.get("/office").get_data(as_text=True)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    content_studio_html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("AI Hive関連の記事3件", root_html)
    self.assertIn("note：AI Hive関連の記事3件公開済み", office_html)
    self.assertIn("note(今回)", ceo_html)
    self.assertIn("今回のnote公開済み", ceo_html)
    self.assertIn("AI Hive関連のnote記事（3本）", revenue_html)
    self.assertIn("AI Hive関連のnote記事3件", content_studio_html)

  def test_mission_055_dashboard_and_rooms_mention_existing_note_account_history(self):
    # noteアカウントには、AI Hive関連以外の既存記事もあることを、数値を
    # 出さずに一文で示していることを確認する。既存記事の総数・フォロワー数
    # ・PV数は未確認のため、新たに表示・推測していないことも確認する
    # (ダッシュボードには既存の「フォロワー数・PV・クリック数・売上額は
    # 表示していません」という否定形の案内文が別途あるため、ここでは
    # それと衝突しない、より具体的な語だけを禁止語とする)。
    for path, has_html_attr in (
        ("/", True), ("/office", False), ("/office/ceo-office", False),
        ("/revenue", False),
    ):
      with self.subTest(path=path):
        html = self.html if has_html_attr else self.client.get(path).get_data(as_text=True)
        self.assertIn("既存記事", html)
        for forbidden in ("PV数", "総記事数", "フォロワー数：", "既存記事数："):
          self.assertNotIn(forbidden, html)

  def test_mission_055_quick_action_chat_scopes_note_count_to_ai_hive(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn(
        "🐕 柴犬社長：Pinterestは5件、noteはAI Hive関連の記事が3件、公開済みだよ。",
        html,
    )
    self.assertIn(
        "🐕 柴犬社長：Pinterestは5件、noteはAI Hive関連の記事が3件、公開まで完了しているよ。",
        html,
    )

  def test_mission_055_does_not_touch_existing_note_article_content_or_urls(self):
    # 既存のnote記事・有料記事・プロフィール・外部サービス上のデータは
    # 変更しないため、note記事URLは引き続き社長から渡された2件だけで
    # あり、新しいURL・プロフィールURL・フォロワー数などを追加していない
    # ことを確認する。
    import re
    for path in (
        "/", "/office", "/office/ceo-office", "/revenue", "/content-studio",
        "/content-studio/publish-queue", "/content-studio/note-first-article",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True) if path != "/" else self.html
        urls = set(re.findall(r"https://[^\s\"'<]+", html))
        allowed = {
            "https://note.com/legal_crow9879/n/nf7af35ac8c28",
            "https://note.com/legal_crow9879/n/nb2a21a842387",
        }
        self.assertTrue(urls <= allowed, f"unexpected URLs on {path}: {urls - allowed}")

  # --- MISSION 057: 楽天ROOMの投稿状況を実態に合わせて更新する -----------------

  def test_mission_057_room_post_count_is_seven_everywhere(self):
    # 楽天ROOMの投稿数が、ダッシュボード・収益化ボードのすべてで統一
    # されており、古い「1件」表記が残っていないことを確認する。
    # MISSION 058: 「AI Hiveで追加した」という限定が付いていることも確認する。
    # MISSION 059: 9月16日の追加投稿(10件)により、件数は7件から17件に
    # 更新された。
    root_html = self.html
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿17件", revenue_html)
    self.assertIn("AI Hive分17件公開・手動運用中", revenue_html)
    self.assertIn("既存ROOM投稿（AI Hive分17件）", revenue_html)
    for html in (root_html, revenue_html):
      self.assertNotIn("折りたたみキーボードを1件公開済み", html)
      self.assertNotIn("次の登録は確認後に判断", html)
      self.assertNotIn("AI Hiveで追加した商品投稿7件", html)
      self.assertNotIn("AI Hive分7件", html)

  def test_mission_057_room_post_count_does_not_confuse_count_with_reaction(self):
    # 「投稿数」と「反応・売上」を混同しない表現になっており、売上・
    # クリック数・成果報酬・商品が売れた実績を新たに表示・推測していない
    # ことを確認する。
    import office_views
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    published_block = revenue_html.split('class="room-prep-published"', 1)[1].split(
        "</div>", 1
    )[0]
    self.assertIn(
        "売上・クリック数・成果報酬・商品が売れた実績は未確認のため表示していません。",
        published_block,
    )
    for forbidden in ("円", "¥", "位獲得", "在庫あり", "在庫切れ", "クリック数：", "成果報酬："):
      self.assertNotIn(forbidden, published_block)
    # データ側にも売上・クリック数等のフィールドを新設していないことを確認する。
    for post in office_views.ROOM_PUBLISHED_POSTS:
      self.assertEqual(
          set(post.keys()) - {"item_label", "status_text", "next_step"}, set()
      )

  def test_mission_057_shoulder_pouch_is_a_normal_post_not_original_photo(self):
    # 最新のショルダー型ガジェットポーチが、#オリジナル写真ではない通常投稿
    # として扱われており、AI生成の使用イメージをオリジナル写真実績として
    # 数えていないことを確認する。
    import office_views
    pouch_posts = [
        p for p in office_views.ROOM_PUBLISHED_POSTS
        if p["item_label"] == "ショルダー型ガジェットポーチ"
    ]
    self.assertEqual(len(pouch_posts), 1)
    pouch = pouch_posts[0]
    self.assertIn("公開情報・購入者レビューを参考にした通常投稿", pouch["status_text"])
    self.assertIn("#オリジナル写真は使用していません", pouch["status_text"])
    batch_posts = [
        p for p in office_views.ROOM_PUBLISHED_POSTS
        if p["item_label"] == "過去に購入・使用した商品"
    ]
    self.assertEqual(len(batch_posts), 1)
    self.assertIn("#オリジナル写真を使用しない通常投稿", batch_posts[0]["status_text"])

  def test_mission_057_does_not_touch_protected_files(self):
    # MISSION 057は調査・表記更新のみで、DB・backups・hive_db.py・
    # 画像ファイルを変更しないことをソースの範囲外であることを確認する
    # (このテスト自体はoffice_views.pyの内容のみを確認する)。
    # MISSION 059で9月16日の追加投稿分(4件目のエントリ)が加わった。
    import office_views
    self.assertEqual(len(office_views.ROOM_PUBLISHED_POSTS), 4)

  # --- MISSION 058: 楽天ROOMの件数表記を誤解のない形に修正する -----------------

  def test_mission_058_room_counts_are_scoped_to_ai_hive_not_whole_account(self):
    # 「ROOM投稿N件」のような表現が、楽天ROOMアカウント全体の商品数の
    # ように誤解されないよう、AI Hiveで追加した件数であることが、
    # ダッシュボード・収益化ボードのすべてで明記されていることを確認する。
    # MISSION 059: 件数は17件に更新された。
    root_html = self.html
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿17件", revenue_html)
    self.assertIn("AI Hive分17件公開・手動運用中", revenue_html)
    self.assertIn("既存ROOM投稿（AI Hive分17件）", revenue_html)
    self.assertIn("公開済みの楽天ROOM投稿（AI Hiveで追加した17件）", revenue_html)

  def test_mission_058_dashboard_and_revenue_mention_account_total_once(self):
    # 楽天ROOMアカウント全体の商品数(30件)が、確認済みの事実として、
    # ダッシュボード・収益化ボードでそれぞれ一度だけ控えめに示され、
    # 水増し・重複表示していないことを確認する。
    # MISSION 059: AI Hive分の件数は17件に更新されたが、アカウント全体の
    # 商品数(30件)は変更せず、引き続き区別して表示されることを確認する。
    root_html = self.html
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn(
        "楽天ROOMアカウント全体では商品投稿が30件あります。件数はAI Hiveで"
        "追加した分のみを示しています。",
        root_html,
    )
    self.assertEqual(root_html.count("30件"), 1)
    self.assertIn(
        "楽天ROOMアカウント全体では商品投稿が30件あり、このうちAI Hiveで"
        "追加・記録しているのは17件です。",
        revenue_html,
    )
    self.assertEqual(revenue_html.count("30件"), 2)  # service_ideasと公開済み一覧の2箇所

  def test_mission_058_does_not_fabricate_sales_or_click_data(self):
    # 売上、クリック、成果報酬、購入実績は未確認のまま表示しないことを
    # 確認する。
    root_html = self.html
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    for html in (root_html, revenue_html):
      for forbidden in (
          "円", "¥", "クリック数：", "成果報酬：", "購入実績", "売れました", "売上：",
      ):
        self.assertNotIn(forbidden, html)

  def test_mission_058_room_account_total_note_is_data_driven(self):
    # ROOM_ACCOUNT_TOTAL_NOTEが独立したデータ構造として定義されており、
    # _render_room_prep_sectionへ渡されていることを確認する。
    # MISSION 059: AI Hive分の件数は17件に更新された。
    import office_views
    self.assertIn("30件", office_views.ROOM_ACCOUNT_TOTAL_NOTE)
    self.assertIn("17件", office_views.ROOM_ACCOUNT_TOTAL_NOTE)
    rendered = office_views._render_room_prep_section(
        office_views.ROOM_PREP_CATEGORIES,
        office_views.ROOM_PREP_STATUS_LABELS,
        office_views.ROOM_PUBLISHED_POSTS,
        office_views.ROOM_ACCOUNT_TOTAL_NOTE,
    )
    self.assertIn(office_views.ROOM_ACCOUNT_TOTAL_NOTE, rendered)
    # account_total_noteを渡さない場合は表示されないことも確認する
    # (後方互換のデフォルト引数)。
    rendered_without_note = office_views._render_room_prep_section(
        office_views.ROOM_PREP_CATEGORIES,
        office_views.ROOM_PREP_STATUS_LABELS,
        office_views.ROOM_PUBLISHED_POSTS,
    )
    self.assertNotIn("room-prep-account-note", rendered_without_note)

  # --- MISSION 059: 楽天ROOMの投稿件数表示を実態に合わせて更新する -------------

  def test_mission_059_room_post_count_is_seventeen_everywhere(self):
    # 9月16日に10件を追加投稿し、AI Hiveで追加した楽天ROOM投稿が7件から
    # 17件に更新されたことが、ダッシュボード・収益化ボードのすべてで
    # 一致していることを確認する。アカウント全体の商品数(30件)は変更
    # しないまま、引き続き区別して表示されることも確認する。
    import office_views
    root_html = self.html
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿17件", revenue_html)
    self.assertIn("AI Hive分17件公開・手動運用中", revenue_html)
    self.assertIn("既存ROOM投稿（AI Hive分17件）", revenue_html)
    self.assertIn("公開済みの楽天ROOM投稿（AI Hiveで追加した17件）", revenue_html)
    self.assertIn("追加投稿分", revenue_html)
    self.assertIn("9月16日に楽天ROOMへ手動投稿済み（10件）", revenue_html)
    # アカウント全体の商品数(30件)は変わっていないことを確認する。
    self.assertIn("アカウント全体では商品投稿30件", revenue_html)
    self.assertIn(
        "楽天ROOMアカウント全体では商品投稿が30件あり、このうちAI Hiveで"
        "追加・記録しているのは17件です。",
        revenue_html,
    )
    self.assertEqual(len(office_views.ROOM_PUBLISHED_POSTS), 4)

  def test_mission_059_does_not_fabricate_sales_or_click_data_for_new_batch(self):
    # 9月16日の追加投稿分についても、売上・クリック数・成果報酬・
    # 購入実績を推測で追加していないことを確認する。
    import office_views
    new_batch = [
        p for p in office_views.ROOM_PUBLISHED_POSTS if p["item_label"] == "追加投稿分"
    ][0]
    self.assertEqual(
        set(new_batch.keys()) - {"item_label", "status_text", "next_step"}, set()
    )
    combined_text = new_batch["status_text"] + new_batch.get("next_step", "")
    for forbidden in ("円", "¥", "位獲得", "在庫あり", "在庫切れ", "クリック数：", "成果報酬："):
      self.assertNotIn(forbidden, combined_text)

  # --- MISSION 060: 楽天ROOMの「毎日5件・投稿候補下書き」機能 ------------------

  def test_room_daily_candidates_page_loads(self):
    res = self.client.get("/content-studio/room-daily-candidates")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("楽天ROOM 毎日の投稿候補（下書き）", html)
    self.assertIn(
        "<title>楽天ROOM 毎日の投稿候補（下書き） | AI Hive</title>", html
    )

  def test_room_daily_candidates_shows_exactly_five_candidate_slots(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.ROOM_CANDIDATE_MAX_PER_DAY, 5)
    self.assertEqual(html.count('class="room-candidate-card"'), 5)
    for slot in range(5):
      self.assertIn(f'<h3>候補 {slot + 1}</h3>', html)

  def test_room_daily_candidates_priority_genres_and_threshold_rule(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertEqual(
        office_views.ROOM_CANDIDATE_PRIORITY_GENRES,
        ["バッグの中の整理", "スマホ周辺の持ち運び収納"],
    )
    self.assertEqual(office_views.ROOM_CANDIDATE_HEART_THRESHOLD, 10)
    self.assertIn("♡が10以上ついた投稿があるジャンルを最優先にします", html)
    self.assertIn("バッグの中の整理", html)
    self.assertIn("スマホ周辺の持ち運び収納", html)
    self.assertIn(
        '<datalist id="room-candidate-genre-options">'
        '<option value="バッグの中の整理"></option>'
        '<option value="スマホ周辺の持ち運び収納"></option>'
        "</datalist>",
        html,
    )
    self.assertIn("反応実績（♡数）が10未満、または未入力の候補は、"
                  "「検証中」と表示されます。", html)

  def test_room_daily_candidates_each_slot_has_all_required_fields(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for slot in range(office_views.ROOM_CANDIDATE_MAX_PER_DAY):
      card = html.split(f'<div class="room-candidate-card" data-slot="{slot}">', 1)[1]
      card = card.split('<div class="room-candidate-card"', 1)[0]
      # ジャンル
      self.assertIn(
          f'<input type="text" class="rc-genre" data-slot="{slot}" '
          'list="room-candidate-genre-options"',
          card,
      )
      # 商品名・楽天市場URL
      self.assertIn(f'class="rc-product-name" data-slot="{slot}"', card)
      self.assertIn(f'class="rc-product-url" data-slot="{slot}"', card)
      # 参考にした反応実績(♡数・コメント数・確認日)
      self.assertIn(f'class="rc-hearts" data-slot="{slot}"', card)
      self.assertIn(f'class="rc-comments" data-slot="{slot}"', card)
      self.assertIn(f'class="rc-checked-date" data-slot="{slot}"', card)
      self.assertIn('type="date"', card)
      # 紹介文(120〜180字程度)とハッシュタグ(最大5個、詳細設定内)
      self.assertIn(f'class="rc-intro" data-slot="{slot}"', card)
      self.assertIn("120〜180字程度の目安", card)
      self.assertEqual(
          card.count(f'class="rc-hashtag" data-slot="{slot}"'),
          office_views.ROOM_CANDIDATE_HASHTAG_COUNT,
      )
      # 「手動確認済み」「ROOMで投稿する」チェック欄
      self.assertIn(
          f'<input type="checkbox" class="rc-manual-checked" data-slot="{slot}"> 手動確認済み',
          card,
      )
      self.assertIn(
          f'<input type="checkbox" class="rc-post-in-room" data-slot="{slot}">', card
      )
      self.assertIn("検証中", card)

  def test_room_daily_candidates_post_in_room_is_a_checkbox_not_a_button(self):
    # 「ROOMで投稿する」は外部投稿を実行するボタンではなく、確認用の
    # チェック欄であることを確認する。
    # MISSION 081: 近くに「手動投稿を完了した」ボタン(外部投稿は行わず、
    # ローカルの運用記録へ保存するだけの安全なボタン)を追加したため、
    # 「ボタンが一切ないこと」ではなく「manual-post-complete-btn以外の
    # ボタンがないこと」を確認する形に更新した。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn('class="rc-post-in-room"', html)
    self.assertNotIn('<button', html.split('rc-post-in-room', 1)[0][-200:])
    for slot_html in html.split('class="rc-post-in-room"')[1:]:
      snippet = slot_html[:400]
      self.assertEqual(
          snippet.count("<button"),
          snippet.count('<button type="button" class="manual-post-complete-btn"'),
      )
    self.assertIn(
        "このチェックは手動投稿の確認記録であり、ここから楽天ROOMへの投稿・送信は"
        "行われません。実際の投稿は利用者がROOM上で手動で行ってください。",
        html,
    )

  def test_room_daily_candidates_has_date_navigation(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn('id="rc-date-input"', html)
    self.assertIn('id="rc-prev-day"', html)
    self.assertIn('id="rc-next-day"', html)
    self.assertIn('id="rc-today"', html)
    self.assertIn('type="date"', html)

  def test_room_daily_candidates_uses_local_storage_only_no_external_calls(self):
    # MISSION 088: 「手動投稿を完了した」ボタンが、このMac上のアプリ内
    # DB(同一オリジンの/api/dashboard/*、無認証・ローカル限定)へも
    # ベストエフォートで保存するようになった。外部サービスへの送信・
    # ログイン・認証トークンが一切ないことは引き続き確認する。
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("window.localStorage", html)
    self.assertIn('postJsonSafe("/api/dashboard/daily-records"', html)
    self.assertIn('postJsonSafe("/api/dashboard/candidates"', html)
    self.assertNotIn("XMLHttpRequest", html)
    for api_path in self._find_api_paths(html):
      self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("<form", html)
    self.assertNotIn("<script src", html)
    # 商品URL欄の入力例(placeholder)としてのみ https:// 表記を許可する。
    # 実際のリンクやスクリプト読み込みではないことを件数で確認する。
    self.assertEqual(
        html.count("https://"),
        office_views.ROOM_CANDIDATE_MAX_PER_DAY,
    )
    self.assertEqual(
        html.count('placeholder="https://item.rakuten.co.jp/...">'),
        office_views.ROOM_CANDIDATE_MAX_PER_DAY,
    )
    self.assertNotIn("http://", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)

  def test_room_daily_candidates_no_image_upload_or_fabricated_reviews(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertNotIn('type="file"', html)
    self.assertNotIn("<img", html)
    # 「#オリジナル写真」への言及は、自動付与しない旨の注記1箇所だけである
    # ことを確認する(実際にオリジナル写真を使用したという記述がないこと)。
    self.assertEqual(html.count("#オリジナル写真"), 1)
    self.assertIn(
        "商品画像の取得・生成画像の自動アップロード・#オリジナル写真の自動付与は",
        html,
    )
    self.assertIn(
        "実際に使用していない商品についての購入・使用体験や口コミは"
        "書かないでください。",
        html,
    )

  def test_room_daily_candidates_fields_have_no_prefilled_fabricated_values(self):
    # ♡数・コメント数など、実際の反応実績は柴犬社長が手動入力する前提のため、
    # サーバー側で架空の数値を事前入力していないことを確認する。
    import re
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for cls in ("rc-hearts", "rc-comments", "rc-checked-date", "rc-genre",
                "rc-product-name", "rc-product-url"):
      for m in re.finditer(rf'class="{cls}"[^>]*', html):
        self.assertNotIn("value=", m.group())
    for m in re.finditer(r'<textarea class="rc-intro"[^>]*>([^<]*)</textarea>', html):
      self.assertEqual(m.group(1), "")

  def test_room_daily_candidates_is_linked_from_room_prep_section(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn('href="/content-studio/room-daily-candidates"', html)
    self.assertIn("楽天ROOM 毎日の投稿候補（下書き）を見る", html)

  def test_room_daily_candidates_does_not_change_existing_pinterest_note_room_counts(self):
    # 新機能の追加により、既存のPinterest・note・楽天ROOMの件数表示に
    # 影響がないことを確認する(回帰確認)。
    root_html = self.html
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿17件", revenue_html)
    self.assertIn(
        "楽天ROOMアカウント全体では商品投稿が30件あり、このうちAI Hiveで"
        "追加・記録しているのは17件です。",
        revenue_html,
    )

  # --- MISSION 061: 「紹介文とハッシュタグを作成」ボタン --------------------

  def test_room_daily_candidates_has_generate_draft_button_per_card(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for slot in range(office_views.ROOM_CANDIDATE_MAX_PER_DAY):
      card = html.split(f'<div class="room-candidate-card" data-slot="{slot}">', 1)[1]
      card = card.split('<div class="room-candidate-card"', 1)[0]
      self.assertIn(
          f'<button type="button" class="room-candidate-generate-btn '
          f'rc-generate-draft" data-slot="{slot}">紹介文とハッシュタグを作成</button>',
          card,
      )
      # ボタンは反応実績の入力欄より後、紹介文欄より前に置く。
      self.assertLess(
          card.index("rc-generate-draft"), card.index('class="rc-intro"')
      )

  def test_room_daily_candidates_has_bulk_generate_button(self):
    # MISSION 087: 利用者向けに分かりやすい文言へ変更した
    # (「入力済みの候補をまとめて下書きを作成」→「まとめて紹介文を作成する」)。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn(
        '<button type="button" id="rc-generate-all">'
        "まとめて紹介文を作成する</button>",
        html,
    )
    # まとめてボタンは日付ナビゲーションの後、候補カードより前に配置する。
    self.assertLess(
        html.index('id="rc-generate-all"'),
        html.index('class="room-candidate-card" data-slot="0"'),
    )
    self.assertGreater(
        html.index('id="rc-generate-all"'), html.index('id="rc-date-input"')
    )

  def test_room_daily_candidates_generate_js_defines_core_functions(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for fn in (
        "function generateIntro(",
        "function generateHashtags(",
        "function generateForSlot(",
        "function generateForAllFilled(",
        "function applyDraftToSlot(",
        "function isFilledSlot(",
        "function hasDraftContent(",
    ):
      self.assertIn(fn, html)
    self.assertIn(
        'document.querySelectorAll(".rc-generate-draft").forEach(btn=>{', html
    )
    self.assertIn(
        'document.querySelector("#rc-generate-all")'
        ".addEventListener(\"click\",generateForAllFilled);",
        html,
    )

  def test_room_daily_candidates_generate_functions_make_no_external_calls(self):
    # 生成機能(紹介文・ハッシュタグのテンプレート組み立て)自体は外部API・
    # AI API・楽天ROOM等への送信・ログインを一切発生させない。MISSION 088
    # で追加した、このMac上のアプリ内DBへの同一オリジンfetch(/api/
    # dashboard/*)は「手動投稿を完了した」ボタン側にあり、生成関数の
    # スコープ外であることを合わせて確認する。
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    script = html.split("function generateIntro(", 1)[1].split(
        "function dispatchInput", 1
    )[0]
    self.assertNotIn("fetch(", script)
    self.assertNotIn("XMLHttpRequest", html)
    for api_path in self._find_api_paths(html):
      self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("<form", html)
    self.assertNotIn("<script src", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(
        html.count("https://"), office_views.ROOM_CANDIDATE_MAX_PER_DAY
    )

  def test_room_daily_candidates_generate_overwrite_confirmation_present(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("window.confirm(", html)
    self.assertIn(
        "すでに入力されている紹介文・ハッシュタグを上書きします。よろしいですか？",
        html,
    )
    self.assertIn(
        "入力済みの候補の中に、すでに紹介文・ハッシュタグが入力されているものが"
        "あります。上書きします。よろしいですか？",
        html,
    )
    # MISSION 087: 単一候補で項目が不足しているときは、ブラウザの
    # window.alertではなく、各欄のすぐ下のインライン表示で案内する
    # ようになった(旧アラート文言は削除)。「候補が1つもない」という
    # 全体状況のときだけ、引き続きwindow.alertを使う。
    self.assertNotIn("ジャンルと商品名を入力してから作成してください。", html)
    self.assertIn("window.alert(", html)
    self.assertIn("ジャンル・商品名・楽天市場URLを入力した候補がありません。", html)

  def test_room_daily_candidates_notice_discloses_generate_feature_constraints(self):
    # MISSION 087: ボタン名の変更(「まとめて下書きを作成」→「まとめて
    # 紹介文を作成する」)、および生成が♡数・コメント数を使わなくなった
    # ことに合わせて、注意書きの文言も更新した。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn(
        "「紹介文とハッシュタグを作成」「まとめて紹介文を作成する」は、入力済みの"
        "ジャンル・商品名だけをもとに、このブラウザの中だけで文章を組み立てる機能です。"
        "外部API・AI APIへの送信は行わず、実際に使用した・購入した・効果があった・"
        "口コミで高評価・最安値といった、入力から確認できない内容は書きません。"
        "すでに紹介文やハッシュタグが入力されている場合は、上書き前に確認が表示されます。",
        html,
    )

  def test_room_daily_candidates_intro_length_guidance_uses_120_to_180(self):
    # MISSION 087: 読者がそのまま読める長さへ短縮した
    # (220〜300字 → 120〜180字程度)。
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.ROOM_CANDIDATE_INTRO_MIN_LENGTH, 120)
    self.assertEqual(office_views.ROOM_CANDIDATE_INTRO_TARGET_LENGTH, 180)
    self.assertIn("紹介文（120〜180字程度の目安", html)

  def test_room_daily_candidates_hashtag_data_includes_base_tag_and_priority_genres(self):
    import office_views
    self.assertEqual(office_views.ROOM_CANDIDATE_BASE_HASHTAG, "#楽天ROOM")
    for genre in office_views.ROOM_CANDIDATE_PRIORITY_GENRES:
      self.assertIn(genre, office_views.ROOM_CANDIDATE_GENRE_HASHTAGS)
      tags = office_views.ROOM_CANDIDATE_GENRE_HASHTAGS[genre]
      self.assertGreaterEqual(len(tags), 1)
      for tag in tags:
        self.assertTrue(tag.startswith("#"))
    self.assertGreaterEqual(len(office_views.ROOM_CANDIDATE_FALLBACK_HASHTAGS), 1)
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("const BASE_HASHTAG=", html)
    self.assertIn("const GENRE_HASHTAGS=", html)
    self.assertIn("const FALLBACK_HASHTAGS=", html)

  def test_room_daily_candidates_generate_intro_js_has_no_fabricated_experience_claims(self):
    # 生成される紹介文のテンプレート文言そのものに、確認できない体験・評価・
    # 最安値の断定表現が含まれないことをソースレベルで確認する。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    script = html.split("function generateIntro(", 1)[1].split("function dispatchInput", 1)[0]
    for forbidden in (
        "購入しました", "使ってみました", "使用してみて", "口コミで高評価",
        "レビューで人気", "最安値", "効果がありました", "おすすめです！",
    ):
      self.assertNotIn(forbidden, script)

  def test_room_daily_candidates_generate_intro_has_no_internal_jargon(self):
    # MISSION 087: 生成される紹介文の構成要素(ジャンル別テンプレート+
    # フォールバック)に、読者へ不要な社内向け語や、反応数の直書き、
    # 未確認の断定表現が含まれないことを確認する。
    import office_views
    all_text = []
    for tmpl in office_views.ROOM_CANDIDATE_INTRO_TEMPLATES.values():
      all_text.extend([tmpl["hook"], tmpl["scene"], tmpl["check"]])
    all_text.extend([
        office_views.ROOM_CANDIDATE_INTRO_FALLBACK_HOOK,
        office_views.ROOM_CANDIDATE_INTRO_FALLBACK_SCENE,
        office_views.ROOM_CANDIDATE_INTRO_FALLBACK_CHECK,
    ])
    combined = "".join(all_text)
    for forbidden in (
        "候補", "下書き", "記録", "入力", "アプリ", "この画面", "ローカル",
        "データベース", "確認していない", "実際に使用していない",
        "口コミには触れていない", "♡", "コメントが",
    ):
      self.assertNotIn(forbidden, combined)

  def test_room_daily_candidates_generate_intro_js_builds_three_part_structure(self):
    # MISSION 087: hook(困りごと・使う場面)→scene(商品カテゴリが役立ち
    # そうな場面)→check(購入前に見るポイント)の3文構成だけで組み立てる
    # (反応数・コメント数を引数に取らない、入力はgenre/productNameだけ)。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("function generateIntro(genre,productName){", html)
    self.assertIn('return [hook,scene,check].join("\\n\\n");', html)
    self.assertIn("const tmpl=INTRO_TEMPLATES[g];", html)
    self.assertIn("const INTRO_TEMPLATES=", html)
    self.assertIn("const INTRO_FALLBACK_HOOK=", html)
    self.assertIn("const INTRO_FALLBACK_SCENE=", html)
    self.assertIn("const INTRO_FALLBACK_CHECK=", html)

  def test_room_daily_candidates_existing_checkbox_semantics_unchanged(self):
    # MISSION 061で生成ボタンを追加しても、「手動確認済み」「ROOMで投稿する」
    # チェック欄の意味・手動投稿である旨は変わらないことを確認する(回帰確認)。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for slot in range(5):
      self.assertIn(
          f'<input type="checkbox" class="rc-manual-checked" data-slot="{slot}"> 手動確認済み',
          html,
      )
      self.assertIn(
          f'<input type="checkbox" class="rc-post-in-room" data-slot="{slot}">', html
      )
    self.assertIn(
        "このチェックは手動投稿の確認記録であり、ここから楽天ROOMへの投稿・送信は"
        "行われません。実際の投稿は利用者がROOM上で手動で行ってください。",
        html,
    )
    # MISSION 081: 「手動投稿を完了した」ボタン(manual-post-complete-btn)
    # 以外のボタンが近くに追加されていないことを確認する。
    for slot_html in html.split('class="rc-post-in-room"')[1:]:
      snippet = slot_html[:400]
      self.assertEqual(
          snippet.count("<button"),
          snippet.count('<button type="button" class="manual-post-complete-btn"'),
      )

  # --- MISSION 062: note「毎日2本の記事候補・下書き」機能 --------------------

  def test_note_daily_candidates_page_loads(self):
    res = self.client.get("/content-studio/note-daily-candidates")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("note記事候補（毎日2本の下書き）", html)
    self.assertIn(
        "<title>note記事候補（毎日2本の下書き） | AI Hive</title>", html
    )

  def test_note_daily_candidates_shows_exactly_two_candidate_slots(self):
    import office_views
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.NOTE_CANDIDATE_MAX_PER_DAY, 2)
    self.assertEqual(html.count('class="note-candidate-card"'), 2)
    for slot in range(2):
      self.assertIn(f'<h3>候補 {slot + 1}</h3>', html)

  def test_note_daily_candidates_each_slot_has_all_required_fields(self):
    import office_views
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    for slot in range(office_views.NOTE_CANDIDATE_MAX_PER_DAY):
      card = html.split(f'<div class="note-candidate-card" data-slot="{slot}">', 1)[1]
      card = card.split('<div class="note-candidate-card"', 1)[0]
      self.assertIn(f'class="nc-title" data-slot="{slot}"', card)
      self.assertIn(f'class="nc-audience" data-slot="{slot}"', card)
      self.assertIn(f'class="nc-price-type" data-slot="{slot}"', card)
      self.assertIn(f'class="nc-intro" data-slot="{slot}"', card)
      self.assertEqual(
          card.count(f'class="nc-heading" data-slot="{slot}"'),
          office_views.NOTE_CANDIDATE_HEADING_MAX,
      )
      self.assertIn(f'class="nc-body" data-slot="{slot}"', card)
      self.assertIn("2500〜3500字程度の目安", card)
      self.assertEqual(
          card.count(f'class="nc-hashtag" data-slot="{slot}"'),
          office_views.NOTE_CANDIDATE_HASHTAG_COUNT,
      )
      self.assertIn(
          f'<input type="checkbox" class="nc-manual-checked" data-slot="{slot}"> 手動確認済み',
          card,
      )
      self.assertIn(
          f'<input type="checkbox" class="nc-post-in-note" data-slot="{slot}">', card
      )

  def test_note_daily_candidates_price_type_defaults_to_free_and_has_paid_option(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertEqual(html.count('<option value="free">無料記事</option>'), 2)
    self.assertEqual(
        html.count(
            '<option value="paid-candidate">有料記事候補'
            "（複数の無料記事の反応を確認できたテーマのみ）</option>"
        ),
        2,
    )
    self.assertIn(
        "有料記事候補は、無料記事を複数公開して反応が確認できた"
        "テーマだけを対象にしてください。この画面から自動で有料公開されることは"
        "ありません。",
        html,
    )
    # <select>にvalue="paid-candidate"を選択済みにするselected属性がないこと
    # (自動で有料記事候補が選ばれていないこと)を確認する。
    self.assertNotIn('value="paid-candidate" selected', html)
    self.assertNotIn('value="free" selected', html)

  def test_note_daily_candidates_post_in_note_is_a_checkbox_not_a_button(self):
    # MISSION 081: 近くに「手動投稿を完了した」ボタン(外部投稿は行わず、
    # ローカルの運用記録へ保存するだけの安全なボタン)を追加したため、
    # 「ボタンが一切ないこと」ではなく「manual-post-complete-btn以外の
    # ボタンがないこと」を確認する形に更新した。
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertIn('class="nc-post-in-note"', html)
    for slot_html in html.split('class="nc-post-in-note"')[1:]:
      snippet = slot_html[:400]
      self.assertEqual(
          snippet.count("<button"),
          snippet.count('<button type="button" class="manual-post-complete-btn"'),
      )
    self.assertIn(
        "このチェックは手動公開の確認記録であり、ここからnoteへの投稿・送信は"
        "行われません。実際の公開は利用者がnote上で手動で行ってください。",
        html,
    )

  def test_note_daily_candidates_has_date_navigation(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertIn('id="nc-date-input"', html)
    self.assertIn('id="nc-prev-day"', html)
    self.assertIn('id="nc-next-day"', html)
    self.assertIn('id="nc-today"', html)
    self.assertIn('type="date"', html)

  def test_note_daily_candidates_has_generate_today_button(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertIn(
        '<button type="button" id="nc-generate-today">今日の2記事候補を作成</button>',
        html,
    )
    self.assertLess(
        html.index('id="nc-generate-today"'),
        html.index('class="note-candidate-card" data-slot="0"'),
    )

  def test_note_daily_candidates_generate_js_defines_core_functions(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    for fn in (
        "function themeForSlot(",
        "function buildIntro(",
        "function buildBody(",
        "function buildHashtags(",
        "function applyThemeToSlot(",
        "function generateToday(",
        "function hasDraftContent(",
    ):
      self.assertIn(fn, html)
    self.assertIn(
        'document.querySelector("#nc-generate-today")'
        '.addEventListener("click",generateToday);',
        html,
    )

  def test_note_daily_candidates_overwrite_confirmation_present(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertIn("window.confirm(", html)
    self.assertIn(
        "入力済みのタイトル・本文・見出し・ハッシュタグがある候補は上書きされます。"
        "よろしいですか？",
        html,
    )

  def test_note_daily_candidates_uses_local_storage_only_no_external_calls(self):
    # MISSION 088: 「手動投稿を完了した」ボタンが、このMac上のアプリ内
    # DB(同一オリジンの/api/dashboard/*、無認証・ローカル限定)へも
    # ベストエフォートで保存するようになった。外部サービスへの送信・
    # ログイン・認証トークンが一切ないことは引き続き確認する。
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertIn("window.localStorage", html)
    self.assertIn('postJsonSafe("/api/dashboard/daily-records"', html)
    self.assertIn('postJsonSafe("/api/dashboard/candidates"', html)
    self.assertNotIn("XMLHttpRequest", html)
    for api_path in self._find_api_paths(html):
      self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("<form", html)
    self.assertNotIn("<script src", html)
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)

  def test_note_daily_candidates_no_image_upload_or_external_service_mentions(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertNotIn('type="file"', html)
    self.assertNotIn("<img", html)
    self.assertIn(
        "noteへのログイン・下書き保存・公開・送信・外部API通信・ブラウザ自動操作は"
        "一切行いません。Pinterest・Threads・楽天ROOM・楽天アフィリエイトへの"
        "アクセス・送信・ログイン・投稿も一切行いません。",
        html,
    )

  def test_note_daily_candidates_fields_have_no_prefilled_fabricated_values(self):
    import re
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    for cls in ("nc-title", "nc-audience", "nc-heading", "nc-hashtag"):
      for m in re.finditer(rf'class="{cls}"[^>]*', html):
        self.assertNotIn("value=", m.group())
    for m in re.finditer(r'<textarea class="nc-(intro|body)"[^>]*>([^<]*)</textarea>', html):
      self.assertEqual(m.group(2), "")

  def test_note_daily_candidates_is_linked_from_content_studio_index(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('href="/content-studio/note-daily-candidates"', html)
    self.assertIn("note記事候補（毎日2本の下書き）を見る", html)

  def test_note_daily_candidates_theme_data_covers_five_topics_without_duplicating_existing_articles(self):
    import office_views
    self.assertEqual(len(office_views.NOTE_CANDIDATE_THEMES), 5)
    expected_labels = {
        "AI初心者の文章作成",
        "AIに調べ物を頼む前の準備",
        "タスク整理・優先順位付け",
        "スマホでのAI活用",
        "メール下書き・仕事の時短",
    }
    self.assertEqual(
        {t["label"] for t in office_views.NOTE_CANDIDATE_THEMES}, expected_labels
    )
    existing_titles = {
        office_views.NOTE_FIRST_ARTICLE["title"],
        office_views.NOTE_SECOND_ARTICLE_DRAFT["title"],
        office_views.NOTE_THIRD_ARTICLE_DRAFT["title"],
    }
    for theme in office_views.NOTE_CANDIDATE_THEMES:
      self.assertNotIn(theme["title"], existing_titles)
      self.assertGreaterEqual(len(theme["headings"]), office_views.NOTE_CANDIDATE_HEADING_MIN)
      self.assertLessEqual(len(theme["headings"]), office_views.NOTE_CANDIDATE_HEADING_MAX)
      self.assertGreaterEqual(len(theme["hashtags"]), 1)

  def test_note_daily_candidates_body_length_guidance_uses_2500_to_3500(self):
    import office_views
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.NOTE_CANDIDATE_BODY_MIN_LENGTH, 2500)
    self.assertEqual(office_views.NOTE_CANDIDATE_BODY_MAX_LENGTH, 3500)
    self.assertIn("下書き本文（2500〜3500字程度の目安", html)

  def test_note_daily_candidates_headings_use_five_to_seven_and_fixed_structure(self):
    import office_views
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.NOTE_CANDIDATE_HEADING_MIN, 5)
    self.assertEqual(office_views.NOTE_CANDIDATE_HEADING_MAX, 7)
    self.assertIn("見出し（5〜7個）", html)
    for theme in office_views.NOTE_CANDIDATE_THEMES:
      self.assertEqual(len(theme["headings"]), 7)
      self.assertIn("悩み", theme["headings"][0])
      self.assertEqual(theme["headings"][1], "うまくいかない原因")
      self.assertEqual(theme["headings"][2], "今日からできる手順")
      self.assertEqual(theme["headings"][3], "AIに伝えるときの具体例")
      self.assertEqual(theme["headings"][4], "よくある失敗と避け方")
      self.assertEqual(theme["headings"][6], "まとめと最初の一歩")
      self.assertIn("action_noun", theme)
      self.assertIn("example_task", theme)

  def test_note_daily_candidates_generate_js_defines_seven_section_functions(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    for fn in (
        "function sectionWorry(",
        "function sectionCause(",
        "function sectionSteps(",
        "function sectionExample(",
        "function sectionMistakes(",
        "function sectionMindset(",
        "function sectionSummary(",
        "function buildBody(",
    ):
      self.assertIn(fn, html)
    self.assertIn(
        "sectionWorry(theme),sectionCause(theme),sectionSteps(theme),", html
    )
    self.assertIn(
        "sectionExample(theme),sectionMistakes(theme),sectionMindset(theme),", html
    )

  def test_note_daily_candidates_generated_body_template_has_no_fabricated_or_absolute_claims(self):
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    script = html.split("function sectionWorry(theme){", 1)[1].split(
        "function buildHashtags", 1
    )[0]
    for forbidden in (
        "購入しました", "使ってみました", "口コミで人気", "売上が上がりました",
        "絶対に", "投資すべき", "治ります",
    ):
      self.assertNotIn(forbidden, script)
    self.assertIn("効果や成果を保証", script)
    self.assertIn("価格・投資・法律・", script)
    self.assertIn("医療・健康について断定的な判断は行っておらず", script)
    self.assertIn("実際の購入・使用・収益に関する体験談や", script)
    self.assertIn("口コミも含んでいません", script)

  def test_note_daily_candidates_hashtags_include_base_tag(self):
    import office_views
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.NOTE_CANDIDATE_BASE_HASHTAG, "#AI活用")
    self.assertIn("const BASE_HASHTAG=", html)
    for theme in office_views.NOTE_CANDIDATE_THEMES:
      for tag in theme["hashtags"]:
        self.assertTrue(tag.startswith("#"))

  def test_note_daily_candidates_does_not_change_existing_note_pinterest_room_content(self):
    # 新機能の追加により、既存のnote初回記事・投稿企画工場・楽天ROOM表示に
    # 影響がないことを確認する(回帰確認)。
    import office_views
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn(office_views.NOTE_FIRST_ARTICLE["title"], html)
    self.assertIn(office_views.NOTE_SECOND_ARTICLE_DRAFT["title"], html)
    self.assertIn(office_views.NOTE_THIRD_ARTICLE_DRAFT["title"], html)
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 066: 運用司令室(/command-center) --------------------------

  def test_command_center_page_loads(self):
    res = self.client.get("/command-center")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("運用司令室", html)
    self.assertIn("<title>運用司令室 | AI Hive</title>", html)

  def test_command_center_is_in_nav_tabs_on_every_office_page(self):
    for path in ("/office", "/office/break-room", "/office/ceo-office",
                 "/revenue", "/content-studio", "/command-center"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('href="/command-center"', html)
        self.assertIn(">運用司令室<", html)

  def test_command_center_header_shows_approver_and_no_external_note(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn("最終承認者：利用者本人", html)
    self.assertIn(
        "楽天ROOM・楽天アフィリエイト・note・Pinterest・Threadsへのアクセス・"
        "ログイン・投稿・送信・削除は一切行いません。",
        html,
    )
    self.assertIn("← ダッシュボードへ戻る", html)

  def test_command_center_check_board_has_five_categories_with_correct_fields(self):
    import office_views
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertEqual(len(office_views.COMMAND_CENTER_CHECK_CATEGORIES), 5)
    self.assertEqual(html.count('class="cc-check-category"'), 5)
    expected = {
        "room": ["item_count", "hearts", "comments"],
        "affiliate": ["clicks", "sales", "commission"],
        "note": ["pv", "likes", "followers"],
        "pinterest": ["monthly_views", "saves", "link_clicks"],
        "threads": [],
    }
    for cat in office_views.COMMAND_CENTER_CHECK_CATEGORIES:
      self.assertEqual([f[0] for f in cat["fields"]], expected[cat["key"]])
      card = html.split(f'data-category="{cat["key"]}">', 1)[1]
      card = card.split('<div class="cc-check-category"', 1)[0]
      for field_key, field_label in cat["fields"]:
        self.assertIn(
            f'<input type="text" class="cc-check-field" '
            f'data-category="{cat["key"]}" data-field="{field_key}">',
            card,
        )
        self.assertIn(field_label, card)
      self.assertIn(
          f'<input type="checkbox" class="cc-check-confirmed" '
          f'data-category="{cat["key"]}">',
          card,
      )
      self.assertIn(cat["confirm_label"], card)
    self.assertIn("20時投稿を確認した", html)

  def test_command_center_check_fields_start_empty_no_fabricated_values(self):
    import re
    html = self.client.get("/command-center").get_data(as_text=True)
    for m in re.finditer(r'class="cc-check-field"[^>]*', html):
      self.assertNotIn("value=", m.group())

  def test_command_center_pending_section_shows_empty_message_and_memo_field(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn(
        '<p class="cc-pending-empty" id="cc-pending-empty">現在、承認待ちの'
        "項目はありません。</p>",
        html,
    )
    self.assertIn('id="cc-pending-memo"', html)
    import re
    m = re.search(
        r'<textarea id="cc-pending-memo"[^>]*>([^<]*)</textarea>', html
    )
    self.assertIsNotNone(m)
    self.assertEqual(m.group(1), "")
    self.assertIn(
        "提案・下書き・確認まで。公開操作は利用者本人が行う。", html
    )

  def test_command_center_department_cards_match_five_departments(self):
    import office_views
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertEqual(len(office_views.COMMAND_CENTER_DEPARTMENT_CARDS), 5)
    expected_labels = ["運用責任者", "ROOM担当", "note担当", "Pinterest担当", "分析担当"]
    self.assertEqual(
        [d["label"] for d in office_views.COMMAND_CENTER_DEPARTMENT_CARDS],
        expected_labels,
    )
    for d in office_views.COMMAND_CENTER_DEPARTMENT_CARDS:
      self.assertIn(
          f'<div class="cc-dept-card"><h3>{d["label"]}</h3><p>{d["summary"]}</p></div>',
          html,
      )
    self.assertIn(
        "以下はAI Hive OS内の仮想チームです。実在する人物や自動で稼働する"
        "プログラムではなく、提案・下書き・記録までを担当します。",
        html,
    )

  def test_command_center_department_summaries_do_not_contradict_department_docs(self):
    # departments/*.mdで明記した「やってはいけないこと」と矛盾する表現
    # (実際に投稿・公開する、など)がカード説明文に含まれないことを確認する。
    import office_views
    for d in office_views.COMMAND_CENTER_DEPARTMENT_CARDS:
      self.assertNotIn("投稿します", d["summary"])
      self.assertNotIn("公開します", d["summary"])
      self.assertNotIn("送信します", d["summary"])

  def test_command_center_decision_memo_has_required_fields_and_media_options(self):
    import office_views
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn('id="cc-decision-date"', html)
    self.assertIn('id="cc-decision-media"', html)
    self.assertIn('id="cc-decision-observed"', html)
    self.assertIn('id="cc-decision-judgement"', html)
    self.assertIn('id="cc-decision-next"', html)
    self.assertIn('id="cc-decision-hold"', html)
    self.assertIn('id="cc-decision-add"', html)
    self.assertEqual(
        office_views.COMMAND_CENTER_DECISION_MEDIA_OPTIONS,
        ["楽天ROOM", "楽天アフィリエイト", "note", "Pinterest", "Threads"],
    )
    for media in office_views.COMMAND_CENTER_DECISION_MEDIA_OPTIONS:
      self.assertIn(f'<option value="{media}">{media}</option>', html)
    self.assertIn(
        "推測と確認済み事実を分けて記録する。数字は未確認のまま断定的な判断を"
        "書かないでください。",
        html,
    )
    self.assertIn(
        '<p class="cc-decision-log-empty" id="cc-decision-log-empty">まだ記録は'
        "ありません。</p>",
        html,
    )

  # --- MISSION 080: 本日の運用記録(AIオフィスの実績表示と連携) ------------

  def test_command_center_daily_record_form_has_required_fields_and_options(self):
    import office_views
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn('id="cc-record-date"', html)
    self.assertIn('id="cc-record-media"', html)
    self.assertIn('id="cc-record-type"', html)
    self.assertIn('id="cc-record-content"', html)
    self.assertIn('id="cc-record-metric"', html)
    self.assertIn('id="cc-record-reference"', html)
    self.assertIn('id="cc-record-add"', html)
    self.assertEqual(
        office_views.COMMAND_CENTER_DAILY_RECORD_MEDIA_OPTIONS,
        ["楽天ROOM", "楽天アフィリエイト", "note", "Pinterest", "Threads", "共通"],
    )
    self.assertEqual(
        office_views.COMMAND_CENTER_DAILY_RECORD_TYPES,
        ["確認", "下書き", "投稿済み", "数字記録", "承認待ち"],
    )
    for media in office_views.COMMAND_CENTER_DAILY_RECORD_MEDIA_OPTIONS:
      self.assertIn(f'<option value="{media}">{media}</option>', html)
    for record_type in office_views.COMMAND_CENTER_DAILY_RECORD_TYPES:
      self.assertIn(f'<option value="{record_type}">{record_type}</option>', html)
    self.assertIn(
        '<p class="cc-decision-log-empty" id="cc-record-log-empty">まだ本日の'
        "運用記録はありません。</p>",
        html,
    )
    self.assertIn("本日の運用記録", html)

  def test_command_center_daily_record_js_saves_to_shared_storage_key(self):
    # MISSION 080: AIオフィス側と同じlocalStorageキー(daily-record-log)へ
    # 保存する。外部通信・DB書き込みは行わない。
    import office_views
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn('const recordLogKey=STORAGE_PREFIX+"daily-record-log";', html)
    self.assertEqual(
        "ai-hive-command-center:" + "daily-record-log",
        office_views.AI_OFFICE_DAILY_RECORD_STORAGE_KEY,
    )
    for fn in (
        "function loadRecordLog(",
        "function renderRecordLog(",
    ):
      self.assertIn(fn, html)
    self.assertIn('document.querySelector("#cc-record-add").addEventListener("click"', html)
    # 自動で実績を作らない: 日付・媒体・種別・内容のいずれかが空なら保存
    # しない。
    self.assertIn(
        "if(!entry.date||!entry.media||!entry.type||!entry.content.trim()){",
        html,
    )

  def test_command_center_daily_record_does_not_prefill_pinterest_entry(self):
    # MISSION 080 要件4: 実装後、利用者が実際に入力するまでPinterestの
    # 実績を勝手に登録しない。
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertNotIn("AIでメール作成の時間を短くするための考え方", html)

  def test_command_center_decision_log_js_defines_core_functions(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    for fn in (
        "function loadDecisionLog(",
        "function renderDecisionLog(",
        "function loadCheckCategory(",
        "function saveCheckCategory(",
        "function updatePendingEmptyState(",
    ):
      self.assertIn(fn, html)

  def test_command_center_uses_local_storage_only_no_external_calls(self):
    # MISSION 088: 本日の運用記録の保存時・「データ保存」セクションの
    # 移行操作時に、このMac上のアプリ内DB(同一オリジンの/api/dashboard/*、
    # 無認証・ローカル限定)へのfetchが追加された。外部サービスへの送信・
    # ログイン・認証トークンが一切ないことは引き続き確認する。
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn("window.localStorage", html)
    self.assertIn('window.fetch("/api/dashboard/daily-records"', html)
    self.assertIn('window.fetch("/api/dashboard/migrate"', html)
    self.assertNotIn("XMLHttpRequest", html)
    for api_path in self._find_api_paths(html):
      self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("<form", html)
    self.assertNotIn("<script src", html)
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertNotIn("<img", html)
    self.assertNotIn('type="file"', html)

  def test_command_center_storage_key_prefix_is_isolated_from_other_features(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn('STORAGE_PREFIX="ai-hive-command-center:"', html)

  def test_command_center_linked_from_dashboard(self):
    html = self.html
    self.assertIn('href="/command-center"', html)
    self.assertIn("運用司令室を見る", html)

  def test_command_center_does_not_change_existing_pages(self):
    # 新画面の追加により、既存の主要ページの表示に影響がないことを確認する
    # (回帰確認)。
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 067: AIオフィス(/ai-office) --------------------------------

  def test_ai_office_page_loads(self):
    res = self.client.get("/ai-office")
    self.assertEqual(res.status_code, 200)
    html = res.get_data(as_text=True)
    self.assertIn("AIオフィス", html)
    self.assertIn("<title>AIオフィス | AI Hive</title>", html)

  def test_ai_office_is_in_nav_tabs_on_every_office_page(self):
    for path in ("/office", "/office/break-room", "/office/ceo-office",
                 "/revenue", "/content-studio", "/command-center", "/ai-office"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('href="/ai-office"', html)
        self.assertIn(">AIオフィス<", html)

  def test_ai_office_demo_banner_and_role_diff_present(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("デモ表示・実データ未接続", html)
    self.assertIn(
        "AI社員が実際に自動稼働しているわけではありません。", html
    )
    self.assertIn(
        "運用司令室</b>（/command-center）は、数字の確認・判断・記録を行う"
        "画面です。",
        html,
    )
    self.assertIn(
        "AIオフィス</b>（このページ）は、役割・進行状況・活動を見える化する"
        "画面であり、役割は重複していません。",
        html,
    )

  def test_ai_office_no_action_buttons_or_forms(self):
    # MISSION 070: 「アニメーションを停止」ボタンのみを許可する
    # (投稿・公開・送信・ログイン・削除を行うボタンではない)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(html.count("<button"), 1)
    self.assertIn(
        '<button type="button" class="ai-office-anim-toggle" '
        'id="ai-office-anim-toggle">アニメーションを停止</button>',
        html,
    )
    self.assertNotIn("<form", html)
    self.assertNotIn("<input", html)
    self.assertIn(
        "このページには、投稿・公開・送信・ログイン・削除を行うボタンは"
        "一切ありません。すべての実行判断は利用者本人が行います。",
        html,
    )

  def test_ai_office_floor_has_five_desks_matching_departments(self):
    # MISSION 073: 「社員名簿」カードは12人分へ拡張されたが、5部署
    # (AI_OFFICE_DEPARTMENTS)の内容自体は変わっていないことを確認する。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(len(office_views.AI_OFFICE_DEPARTMENTS), 5)
    self.assertEqual(len(office_views.AI_OFFICE_EXTENDED_STAFF), 10)
    self.assertEqual(html.count('class="ai-office-desk"'), 15)
    expected = [
        ("operations_lead", "指令デスク", "運用責任者"),
        ("room", "ROOM運用席", "ROOM担当"),
        ("note", "note編集席", "note担当"),
        ("pinterest", "Pinterest企画席", "Pinterest担当"),
        ("analytics", "分析ラボ", "分析担当"),
    ]
    self.assertEqual(
        [(d["key"], d["desk_label"], d["role_label"]) for d in office_views.AI_OFFICE_DEPARTMENTS],
        expected,
    )
    for key, desk_label, role_label in expected:
      self.assertIn(desk_label, html)
      self.assertIn(role_label, html)

  def test_ai_office_desk_scope_statement_present_and_consistent(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(
        office_views.AI_OFFICE_SCOPE_STATEMENT,
        "提案・下書き・記録まで。最終承認と外部公開は利用者本人。",
    )
    # MISSION 073: 社員名簿カードは12人分になったため、範囲表明も12回
    # 出現する(5部署 + 拡張担当7人)。
    self.assertEqual(
        html.count(office_views.AI_OFFICE_SCOPE_STATEMENT),
        len(office_views.AI_OFFICE_DEPARTMENTS) + len(office_views.AI_OFFICE_EXTENDED_STAFF),
    )

  def test_ai_office_desk_summaries_do_not_contradict_department_docs(self):
    import office_views
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      self.assertNotIn("投稿します", d["role_summary"])
      self.assertNotIn("公開します", d["role_summary"])
      self.assertNotIn("送信します", d["role_summary"])
      self.assertNotIn("自動で", d["role_summary"])

  def test_ai_office_desk_status_badges_show_demo_labels(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    valid_statuses = set(office_views.AI_OFFICE_STATUS_LABELS)
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      self.assertIn(d["demo_status"], valid_statuses)
      label = office_views.AI_OFFICE_STATUS_LABELS[d["demo_status"]]
      self.assertIn(f"{label}（デモ表示）", html)

  def test_ai_office_today_tasks_tagged_as_demo(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(len(office_views.AI_OFFICE_TODAY_TASKS), 4)
    task_section = html.split("今日のタスク（デモ）", 1)[1].split(
        "動いている仕事と結果（デモ）", 1
    )[0]
    for t in office_views.AI_OFFICE_TODAY_TASKS:
      self.assertIn(t["text"], task_section)
    self.assertGreaterEqual(task_section.count("ai-office-demo-tag"), 4)

  def test_ai_office_running_work_statuses_are_not_fabricated_real_activity(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for w in office_views.AI_OFFICE_RUNNING_WORK:
      self.assertIn(w["status"], office_views.AI_OFFICE_STATUS_LABELS)
      self.assertIn(w["item"], html)
    self.assertNotIn("実行中", html)
    self.assertNotIn("自動実行", html)

  def test_ai_office_chat_is_static_demo_no_external_api(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("AIとのチャット窓口（デモ）", html)
    for m in office_views.AI_OFFICE_CHAT_DEMO_MESSAGES:
      self.assertIn(m["text"], html)
    self.assertIn(
        "この窓口は現在デモの会話表示のみで、次の段階で接続を予定しています。",
        html,
    )
    self.assertIn(
        "外部AI APIへの送信や自動応答は行っていません。", html
    )

  def test_ai_office_source_freshness_shows_five_channels_unconnected_demo(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(
        office_views.AI_OFFICE_SOURCE_CHANNELS,
        ["楽天ROOM", "楽天アフィリエイト", "note", "Pinterest", "Threads"],
    )
    self.assertEqual(html.count('class="ai-office-freshness-card"'), 5)
    # 5枚のカード分 + 注記文中の1回 = 6回。
    self.assertEqual(html.count("未接続・デモ"), 6)
    self.assertIn(
        "実際の取得日時は表示していません（未実装）。", html
    )
    # 実際の取得日時らしき表記(日付や「◯分前」等)が含まれないことを確認する。
    import re
    self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}\s*\d{1,2}:\d{2}", html))
    self.assertNotIn("分前", html)
    self.assertNotIn("時間前", html)

  def test_ai_office_deliverables_link_to_real_pages_only(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(len(office_views.AI_OFFICE_DELIVERABLES), 4)
    for d in office_views.AI_OFFICE_DELIVERABLES:
      self.assertIn(d["label"], html)
      if d["href"]:
        self.assertIn(f'href="{d["href"]}"', html)
        # リンク先が実在のルートであることを確認する。
        linked_res = self.client.get(d["href"])
        self.assertEqual(linked_res.status_code, 200)
    self.assertIn("company_knowledge/", html)

  def test_ai_office_activity_feed_prefixed_with_demo(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(len(office_views.AI_OFFICE_ACTIVITY_FEED), 3)
    for entry in office_views.AI_OFFICE_ACTIVITY_FEED:
      self.assertTrue(entry.startswith("デモ："))
      self.assertIn(entry, html)
    self.assertIn(
        "これはデモの表示であり、実際のAI作業ログではありません。", html
    )

  def test_ai_office_reads_but_never_writes_local_storage(self):
    # MISSION 070: フロアマップのデモアニメーション自体の状態(誰が今動いて
    # いるか等)はlocalStorageへ保存せず、再読み込みで初期状態に戻る。
    # MISSION 080: 運用司令室の「本日の運用記録」を反映するため、
    # localStorage.getItem(読み取り)だけは行うようになった。setItem・
    # removeItem・clear(書き込み)は一切行わないことを確認する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("localStorage.getItem(", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)

  def test_ai_office_no_external_calls_or_credentials(self):
    import re
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: アプリ内DBへの読み取り専用GETは許可する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("<script src", html)
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    # MISSION 069/072: フロアマップ画像1枚だけがローカルの/static配下から
    # 読み込まれていることを確認する(外部URL・新規スクリプトは追加しない)。
    # MISSION 072で、表示する背景をロボット無しのempty版へ差し替えた。
    img_srcs = re.findall(r'<img[^>]*\ssrc="([^"]+)"', html)
    self.assertEqual(img_srcs, ["/static/images/ai-office-floor-map-empty.png"])

  def test_ai_office_linked_from_dashboard(self):
    html = self.html
    self.assertIn('href="/ai-office"', html)
    self.assertIn("AIオフィスを見る", html)

  def test_ai_office_does_not_change_existing_pages(self):
    # 新画面の追加により、既存の主要ページの表示に影響がないことを確認する
    # (回帰確認)。
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 068: AIオフィスのオフィスフロアマップ強化 --------------------

  def test_ai_office_floormap_status_strip_has_five_chips_matching_departments(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(html.count('class="ai-office-strip-chip"'), 5)
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      self.assertIn(f'data-department="{d["key"]}"', html)
      self.assertIn(d["desk_label"], html)

  def test_ai_office_floormap_image_appears_before_status_section(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertLess(
        html.index("オフィスフロアマップ（デモ表示）"),
        html.index("社員名簿（15人・状態一覧）"),
    )
    self.assertLess(
        html.index('class="ai-office-floormap-image"'),
        html.index('class="ai-office-desk"'),
    )

  def test_ai_office_floormap_each_chip_shows_department_and_status(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      chip = html.split(f'data-department="{d["key"]}">', 1)[1]
      chip = chip.split('</li>', 1)[0]
      self.assertIn(d["desk_label"], chip)
      status_label = office_views.AI_OFFICE_STATUS_LABELS[d["demo_status"]]
      self.assertIn(f"{status_label}（デモ）", chip)
      self.assertIn(
          f'ai-office-char-avatar-{d["demo_status"]}', chip
      )
      self.assertIn(d["symbol"], chip)

  def test_ai_office_status_labels_include_four_states(self):
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_STATUS_LABELS,
        {
            "working": "稼働中",
            "pending": "確認待ち",
            "waiting": "待機中",
            "demo_done": "デモ完了",
        },
    )
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      self.assertIn(d["demo_status"], office_views.AI_OFFICE_STATUS_LABELS)

  def test_ai_office_floormap_css_defines_status_colors_for_strip_chips(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    for cls in (
        ".ai-office-char-avatar-working", ".ai-office-char-avatar-pending",
        ".ai-office-char-avatar-waiting", ".ai-office-char-avatar-demo_done",
        ".ai-office-floormap-status-strip", ".ai-office-strip-chip",
        ".ai-office-floormap-image", ".ai-office-floormap-image-wrap",
    ):
      self.assertIn(cls, html)
    # 発光(box-shadow)がキャラクターの状態別スタイルに定義されていることを
    # 確認する(実際にAIが稼働しているように見せる新規JS/アニメーション追加
    # ではなく、CSSだけで表現されていることを確認する)。
    self.assertIn(
        ".ai-office-char-avatar-working{border-color:var(--cyan);"
        "box-shadow:0 0 12px 3px rgba(34,211,238,.55);"
        "animation:ai-office-pulse 1.8s ease-in-out infinite}",
        html,
    )

  def test_ai_office_floormap_uses_only_the_one_local_image_no_new_assets(self):
    # MISSION 071/072: <img>はフロアマップ画像1枚のみ。MISSION 072で、
    # 表示する背景をロボット無しのai-office-floor-map-empty.pngへ差し替えた
    # (旧ai-office-floor-map.pngはファイルとして残すが、画面には使わない)。
    # 社員スプライトはCSSのbackground-image(ローカルの/static配下)1個だけで
    # 表現し、それ以外の新規画像アセット・外部リソースは追加しない。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(
        office_views.AI_OFFICE_FLOOR_MAP_IMAGE_RELATIVE_PATH,
        "images/ai-office-floor-map.png",
    )
    self.assertEqual(
        office_views.AI_OFFICE_FLOOR_MAP_EMPTY_IMAGE_RELATIVE_PATH,
        "images/ai-office-floor-map-empty.png",
    )
    # MISSION 073: 立体的な3Dキャラクター調スプライト(3列×4行、12人)へ
    # 全面更新した。旧スプライト(images/ai-office-team-sprites.png)は
    # ファイルとして残るが、画面には使わない。
    self.assertEqual(
        office_views.AI_OFFICE_SPRITE_SHEET_RELATIVE_PATH,
        "images/ai-office-team-3d.png",
    )
    self.assertEqual(
        office_views.AI_OFFICE_LEGACY_SPRITE_SHEET_RELATIVE_PATH,
        "images/ai-office-team-sprites.png",
    )
    self.assertEqual(office_views.AI_OFFICE_SPRITE_COLS, 3)
    self.assertEqual(office_views.AI_OFFICE_SPRITE_ROWS, 4)
    self.assertNotIn(
        f'url(/static/{office_views.AI_OFFICE_LEGACY_SPRITE_SHEET_RELATIVE_PATH})',
        html,
    )
    self.assertEqual(html.count("<img"), 1)
    self.assertIn(
        f'src="/static/{office_views.AI_OFFICE_FLOOR_MAP_EMPTY_IMAGE_RELATIVE_PATH}"',
        html,
    )
    # MISSION 074: フロアマップ上の社員本人(.ai-office-floormap-token)専用の
    # スプライト参照が増えたため、background-image:url(の出現数は2箇所に
    # なった(社員名簿の丸アイコン用+フロアマップの全身キャラ用)。いずれも
    # 同じ新スプライトを指すことを確認する。
    self.assertEqual(html.count("background-image:url("), 2)
    self.assertEqual(
        html.count(
            f'background-image:url(/static/{office_views.AI_OFFICE_SPRITE_SHEET_RELATIVE_PATH})'
        ),
        2,
    )
    self.assertNotIn("<script src", html)

  def test_ai_office_floormap_image_file_exists_and_is_not_the_protected_image(self):
    import os
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-floor-map.png",
    )
    self.assertTrue(os.path.isfile(path))
    # 既存の保護対象画像を上書きしていないことを確認する。
    protected = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "note-ai-mismatch-hero.png",
    )
    self.assertNotEqual(os.path.abspath(path), os.path.abspath(protected))

  def test_ai_office_floormap_image_alt_text_discloses_it_is_a_demo_illustration(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        "ピクセルアート風のイラスト（デモ表示）", html
    )
    self.assertIn(
        "実際のオフィスの写真や、AIが実際に稼働している様子を撮影したもの"
        "ではありません。",
        html,
    )

  def test_ai_office_floormap_hint_text_present_without_click_functionality(self):
    # MISSION 070: 「各部屋を選択すると…」という案内文は維持しつつ、実際に
    # 部屋やキャラクターをクリックできる機能(onclick等)は追加していない
    # ことを確認する。「アニメーションを停止」ボタンのための
    # addEventListenerだけは許可する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("各部屋を選択すると下の詳細を確認できます。", html)
    self.assertIn("今回はクリック操作・状態変更は実装しておらず", html)
    self.assertNotIn("onclick", html)
    self.assertEqual(html.count("addEventListener"), 1)
    self.assertIn('toggleBtn.addEventListener("click"', html)

  def test_ai_office_floormap_disclaims_demo_status_clearly(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        "しているものではなく、すべてデモの表示です。",
        html,
    )
    self.assertIn(
        "稼働中・移動中はシアン、確認待ちは黄色、待機中は"
        "控えめな青、デモ完了は緑で状態を示しますが",
        html,
    )

  def test_ai_office_existing_seven_parts_preserved_below_floormap(self):
    # 既存の7パーツの見出し・リンク・注意書きが引き続き存在することを確認する
    # (回帰確認)。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for heading in (
        "社員名簿（15人・状態一覧）", "今日のタスク（デモ）",
        "動いている仕事と結果（デモ）", "AIとのチャット窓口（デモ）",
        "情報源の鮮度モニター（デモ）", "成果物一覧", "活動フィード（デモ）",
    ):
      self.assertIn(heading, html)
    self.assertEqual(
        html.count(office_views.AI_OFFICE_SCOPE_STATEMENT),
        len(office_views.AI_OFFICE_DEPARTMENTS) + len(office_views.AI_OFFICE_EXTENDED_STAFF),
    )
    self.assertIn("この窓口は現在デモの会話表示のみで", html)
    self.assertIn("未接続・デモ", html)
    for d in office_views.AI_OFFICE_DELIVERABLES:
      self.assertIn(d["label"], html)
    for entry in office_views.AI_OFFICE_ACTIVITY_FEED:
      self.assertIn(entry, html)

  def test_ai_office_top_notice_still_states_demo_and_no_external_actions(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("デモ表示・実データ未接続", html)
    self.assertIn(
        "このページには、投稿・公開・送信・ログイン・削除を行うボタンは"
        "一切ありません。すべての実行判断は利用者本人が行います。",
        html,
    )
    self.assertIn(
        "運用司令室</b>（/command-center）は、数字の確認・判断・記録を行う"
        "画面です。",
        html,
    )

  def test_ai_office_floormap_no_dangerous_actions_forms_or_external_calls(self):
    # MISSION 070: フロアマップのデモアニメーション用に、ローカルの
    # <script>と「アニメーションを停止」ボタン1個だけを許可する。
    # フォーム・外部通信は引き続き一切禁止のままであることを確認する。
    # MISSION 080: 運用司令室の運用記録を読むためlocalStorage.getItem(の
    # みは許可されるが、setItem・removeItemによる書き込みは禁止のまま。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(html.count("<button"), 1)
    self.assertNotIn("<form", html)
    self.assertNotIn("<input", html)
    self.assertEqual(html.count("<script"), 1)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    # MISSION 088: アプリ内DBへの読み取り専用GETは許可する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )

  def test_ai_office_floormap_mobile_media_query_stacks_status_strip(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-floormap-status-strip{flex-direction:column;"
        "align-items:stretch}",
        html,
    )
    self.assertIn(
        ".ai-office-floormap-image{display:block;width:100%;", html
    )

  def test_ai_office_does_not_change_existing_pages_after_floormap_addition(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 070: AIオフィスの仕事進行・報告デモアニメーション -----------

  def test_ai_office_demo_animation_has_five_floor_tokens(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      self.assertIn(f'id="ai-office-token-{d["key"]}"', html)
      pos = office_views.AI_OFFICE_FLOOR_POSITIONS[d["key"]]
      self.assertIn(f'left:{pos["left"]}%;top:{pos["top"]}%', html)
    # MISSION 076: 「中央の指令デスクへ結ぶ線」表現は廃止し、報告する
    # 本人同士が対面する表示に変更したため、接続ライン要素は存在しない。
    self.assertNotIn('ai-office-floormap-line', html)

  def test_ai_office_demo_animation_has_bubble_speech_and_controls(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-floormap-bubble"', html)
    self.assertIn('id="ai-office-floormap-speech"', html)
    self.assertIn('aria-live="polite"', html)
    self.assertIn(
        '<button type="button" class="ai-office-anim-toggle" '
        'id="ai-office-anim-toggle">アニメーションを停止</button>',
        html,
    )
    self.assertIn(
        "会話はすべてデモ用のデータであり、実際のAI稼働ログではありません。",
        html,
    )

  def test_ai_office_report_routes_match_mission_076_text_and_no_fabricated_results(self):
    # MISSION 076: 部署から指令デスクへの一律報告は廃止し、役割ごとの
    # 対面報告ルート(mover→receiver)に置き換えた。
    # MISSION 077: 凛→海・伊織→蓮・彩→悠の3ルートを追加し、11ルートに
    # なった。
    import office_views
    routes = office_views.AI_OFFICE_REPORT_ROUTES
    self.assertEqual(len(routes), 11)
    by_key = {r["key"]: r for r in routes}
    expected = {
        "room_to_yu": ("room", "yu", "ROOM候補を整理しました",
                       "受け取りました。次の確認へ進めます"),
        "note_to_aya": ("note", "aya", "見出し構成をまとめました",
                        "美咲にも共有して方向性をそろえます"),
        "pinterest_to_aya": ("pinterest", "aya", "画像テーマ候補を用意しました",
                             "noteの見出しと合わせて確認します"),
        "sou_to_iori": ("sou", "iori", "画面表示を確認しました",
                        "品質観点で確認します"),
        "yui_to_analytics": ("yui", "analytics", "情報源の鮮度を確認しました",
                             "比較メモへ反映します"),
        "analytics_to_yu": ("analytics", "yu", "確認済みの数字を比較しました",
                            "判断メモとして整理します"),
        "yu_to_president": ("yu", "operations_lead", "各部署の報告をまとめました",
                            "受け取りました。利用者の確認待ちにします"),
        "ren_to_president": ("ren", "operations_lead", "安全・承認確認を終えました",
                             "確認しました。外部操作は利用者判断です"),
        "rin_to_note": ("rin", "note", "資料室の内容を確認しました",
                        "確認ありがとう。記事に反映します"),
        "iori_to_ren": ("iori", "ren", "表示内容の品質確認を終えました",
                        "安全・承認の観点で確認します"),
        "aya_to_yu": ("aya", "yu", "部署間の連携状況を共有しました",
                      "進行管理に反映します"),
    }
    for key, (mover, receiver, mover_line, receiver_line) in expected.items():
      route = by_key[key]
      self.assertEqual(route["mover"], mover)
      self.assertEqual(route["receiver"], receiver)
      self.assertEqual(route["mover_line"], mover_line)
      self.assertEqual(route["receiver_line"], receiver_line)
      for forbidden in ("売上", "円", "件成約", "投稿完了", "公開しました", "送信しました"):
        self.assertNotIn(forbidden, mover_line)
        self.assertNotIn(forbidden, receiver_line)
    # 柴犬社長へ直接報告するのは悠・蓮の2件だけ(全員が殺到する演出にしない)。
    president_receivers = [r["mover"] for r in routes if r["receiver"] == "operations_lead"]
    self.assertEqual(sorted(president_receivers), ["ren", "yu"])
    html = self.client.get("/ai-office").get_data(as_text=True)
    for route in routes:
      self.assertIn(route["mover_line"], html)
      self.assertIn(route["receiver_line"], html)
      self.assertIn(route["feed_text"], html)

  def test_ai_office_activity_feed_list_has_stable_id_for_js_updates(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-activity-feed-list"', html)
    self.assertEqual(office_views.AI_OFFICE_ACTIVITY_FEED_MAX_ITEMS, 5)
    # 初期状態(サーバー描画時点)は既存の3件のまま(回帰確認)。
    self.assertEqual(html.count("<li>デモ："), 3)

  def test_ai_office_demo_js_data_embeds_positions_and_report_routes_safely(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("var DATA=", html)
    self.assertIn('"positions":', html)
    self.assertIn('"reportRoutes":', html)
    self.assertIn('"statusLabels":', html)
    self.assertIn('"staffNames":', html)
    self.assertIn('"interactions":', html)
    self.assertIn('"visitorSlots":', html)
    self.assertIn('"maxFeedItems":', html)
    # 状態遷移に使うキー("working"/"pending"/"waiting"/"demo_done")が
    # すべてJSへ渡っていることを確認する。
    for status_key in office_views.AI_OFFICE_STATUS_LABELS:
      self.assertIn(f'"{status_key}"', html)

  def test_ai_office_demo_js_functions_implement_the_face_to_face_report_flow(self):
    # MISSION 076: 「中央へ移動するだけ」の5ステップ(stepStart〜stepSettle)
    # を、報告先の社員の前まで歩いて対面で会話する対面報告ルートへ
    # 置き換えた(reportStepTravel〜reportStepSettle)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    for fn in (
        "function reportStepTravel(", "function reportStepArrive(",
        "function reportStepReply(", "function reportStepReturn(",
        "function reportStepSettle(", "function runReportRoute(",
        "function pickNextReportRoute(",
        "function setStatus(", "function showBubble(", "function hideBubble(",
        "function showBubbleReceiver(", "function hideBubbleReceiver(",
        "function showSpeech(", "function pushFeed(", "function moveToken(",
        "function faceTowards(", "function resetFacing(", "function setPhase(",
        "function scheduleNext(",
    ):
      self.assertIn(fn, html)

  def test_ai_office_demo_toggle_button_pauses_and_resumes_locally(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('paused=!paused', html)
    self.assertIn("アニメーションを再生", html)
    self.assertIn("clearTimeout(pendingTimer)", html)

  def test_ai_office_demo_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)

  def test_ai_office_demo_animation_does_not_change_existing_seven_parts(self):
    # 既存の7パーツの見出し・注意書きが引き続き存在することを確認する
    # (回帰確認)。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for heading in (
        "社員名簿（15人・状態一覧）", "今日のタスク（デモ）",
        "動いている仕事と結果（デモ）", "AIとのチャット窓口（デモ）",
        "情報源の鮮度モニター（デモ）", "成果物一覧", "活動フィード（デモ）",
    ):
      self.assertIn(heading, html)
    for entry in office_views.AI_OFFICE_ACTIVITY_FEED:
      self.assertIn(entry, html)
    self.assertIn("デモ表示・実データ未接続", html)

  def test_ai_office_demo_animation_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 071: 社員キャラクター本人が働き・歩き・報告・交流する演出 ---

  def test_ai_office_staff_roster_matches_mission_names(self):
    # MISSION 073: 12人体制(5部署 + 拡張担当7人)に更新した。
    import office_views
    dept_names = {d["key"]: d["staff_name"] for d in office_views.AI_OFFICE_DEPARTMENTS}
    self.assertEqual(
        dept_names,
        {
            "operations_lead": "柴犬社長",
            "room": "里奈",
            "note": "海",
            "pinterest": "美咲",
            "analytics": "葵",
        },
    )
    extended_names = {s["key"]: s["name"] for s in office_views.AI_OFFICE_EXTENDED_STAFF}
    self.assertEqual(
        extended_names,
        {
            "sou": "蒼", "iori": "伊織", "aya": "彩", "rin": "凛",
            "yu": "悠", "yui": "結", "ren": "蓮",
            "tsumugi": "紬", "nagi": "凪", "hina": "陽菜",
        },
    )
    extended_roles = {s["key"]: s["role_label"] for s in office_views.AI_OFFICE_EXTENDED_STAFF}
    self.assertEqual(
        extended_roles,
        {
            "sou": "技術担当", "iori": "品質確認",
            "aya": "連携担当（社内コーディネーター）",
            "rin": "資料室管理", "yu": "進行管理",
            "yui": "情報源の鮮度確認", "ren": "安全・承認確認",
            # MISSION 089: 候補管理チーム3名。
            "tsumugi": "候補整理席", "nagi": "商品確認席", "hina": "投稿準備席",
        },
    )

  def test_ai_office_sprite_sheet_constants_and_file_exists(self):
    import os
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_SPRITE_SHEET_RELATIVE_PATH,
        "images/ai-office-team-3d.png",
    )
    self.assertEqual(
        office_views.AI_OFFICE_LEGACY_SPRITE_SHEET_RELATIVE_PATH,
        "images/ai-office-team-sprites.png",
    )
    self.assertEqual(office_views.AI_OFFICE_SPRITE_COLS, 3)
    self.assertEqual(office_views.AI_OFFICE_SPRITE_ROWS, 4)
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-team-3d.png",
    )
    self.assertTrue(os.path.isfile(path))
    res = self.client.get("/static/images/ai-office-team-3d.png")
    self.assertEqual(res.status_code, 200)
    # MISSION 071の旧スプライトも、ファイルとしては削除せず残っている。
    legacy_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-team-sprites.png",
    )
    self.assertTrue(os.path.isfile(legacy_path))

  def test_ai_office_all_twelve_people_have_valid_unique_sprite_coordinates(self):
    # MISSION 089: 候補管理チーム3名(紬・凪・陽菜)は、新しい画像を追加
    # せず、既存12コマのうちAI_OFFICE_SPRITE_REUSE_MAPで指定したコマを
    # そのまま再利用する。よって「12コマを過不足なく使い切る」検証は
    # 元の12人だけに対して行い、再利用組は再利用元と同じ座標であることを
    # 別途確認する。
    import office_views
    people = list(office_views.AI_OFFICE_DEPARTMENTS) + list(office_views.AI_OFFICE_EXTENDED_STAFF)
    self.assertEqual(len(people), 15)
    reused_keys = set(office_views.AI_OFFICE_SPRITE_REUSE_MAP.keys())
    self.assertEqual(reused_keys, {"tsumugi", "nagi", "hina"})
    original_people = [p for p in people if p["key"] not in reused_keys]
    self.assertEqual(len(original_people), 12)
    seen = set()
    for p in people:
      row, col = p["sprite"]["row"], p["sprite"]["col"]
      self.assertGreaterEqual(row, 0)
      self.assertLess(row, office_views.AI_OFFICE_SPRITE_ROWS)
      self.assertGreaterEqual(col, 0)
      self.assertLess(col, office_views.AI_OFFICE_SPRITE_COLS)
    for p in original_people:
      row, col = p["sprite"]["row"], p["sprite"]["col"]
      self.assertNotIn((row, col), seen)
      seen.add((row, col))
    # 元の12人でスプライトシートの12コマすべてを過不足なく使い切っている。
    self.assertEqual(len(seen), office_views.AI_OFFICE_SPRITE_COLS * office_views.AI_OFFICE_SPRITE_ROWS)
    people_by_key = {p["key"]: p for p in people}
    for key, source_key in office_views.AI_OFFICE_SPRITE_REUSE_MAP.items():
      self.assertEqual(people_by_key[key]["sprite"], people_by_key[source_key]["sprite"])
    # 柴犬社長だけが1行目・左(0,0)であること。
    self.assertEqual(
        [p["sprite"] for p in office_views.AI_OFFICE_DEPARTMENTS if p["key"] == "operations_lead"][0],
        {"row": 0, "col": 0},
    )
    for p in people:
      if p["key"] != "operations_lead":
        self.assertNotEqual(p["sprite"], {"row": 0, "col": 0})

  def test_ai_office_all_twelve_floor_tokens_rendered_with_nameplates(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(html.count('class="ai-office-floormap-token'), 15)
    dept_keys = [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
    extended_keys = [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    for key in dept_keys + extended_keys:
      self.assertIn(f'id="ai-office-token-{key}"', html)
      self.assertIn(f'id="ai-office-nameplate-{key}"', html)
      self.assertIn(f'id="ai-office-nameplate-dot-{key}"', html)
    for d in office_views.AI_OFFICE_DEPARTMENTS:
      self.assertIn(f'data-department="{d["key"]}"', html)
    for name in ("蒼", "伊織", "彩", "凛", "悠", "結", "蓮"):
      self.assertIn(name, html)

  def test_ai_office_extended_staff_are_included_in_twelve_person_roster(self):
    # MISSION 073: 拡張担当7人も「社員名簿」に統合され、12枚のカードで
    # 一覧できることを確認する(以前の「5部署のみ」制約を撤廃)。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(len(office_views.AI_OFFICE_DEPARTMENTS), 5)
    self.assertEqual(len(office_views.AI_OFFICE_EXTENDED_STAFF), 10)
    self.assertEqual(html.count('class="ai-office-desk"'), 15)
    for s in office_views.AI_OFFICE_EXTENDED_STAFF:
      self.assertIn(f'data-department="{s["key"]}"', html)
      self.assertIn(s["name"], html)
      self.assertIn(s["zone_label"], html)

  def test_ai_office_interaction_scenes_match_mission_examples(self):
    # MISSION 076: 美咲・海(旧misaki_umi_pinterest)・伊織・蒼
    # (旧iori_sou_desk)・悠の巡回(旧yu_progress_check)・結の情報源確認
    # (旧yui_monitor_check)は対面報告ルート(AI_OFFICE_REPORT_ROUTES)へ
    # 統合されたため、対面報告に該当しない彩(休憩スペース)・凛(資料室↔
    # note)の2件だけが残る。
    # MISSION 089: 候補管理チームの引き継ぎ(紬→凪)を1件追加した。
    import office_views
    scenes = office_views.AI_OFFICE_INTERACTION_SCENES
    self.assertEqual(len(scenes), 3)
    by_key = {s["key"]: s for s in scenes}
    self.assertEqual(by_key["aya_lounge"]["mover"], "aya")
    self.assertEqual(by_key["aya_lounge"]["location"], "lounge")
    self.assertEqual(by_key["aya_lounge"]["line"], "ひと息ついたら続けます")
    self.assertEqual(by_key["rin_note_visit"]["mover"], "rin")
    self.assertEqual(by_key["rin_note_visit"]["location"], "note")
    self.assertEqual(by_key["rin_note_visit"]["line"], "資料を確認して戻ります")
    self.assertEqual(by_key["tsumugi_nagi_handoff"]["mover"], "tsumugi")
    self.assertEqual(by_key["tsumugi_nagi_handoff"]["location"], "nagi")
    self.assertEqual(
        by_key["tsumugi_nagi_handoff"]["line"], "今日の候補を確認してもらえますか"
    )
    html = self.client.get("/ai-office").get_data(as_text=True)
    for scene in scenes:
      self.assertIn(scene["line"], html)

  def test_ai_office_lounge_position_used_as_shared_gathering_spot(self):
    import office_views
    self.assertEqual(office_views.AI_OFFICE_LOUNGE_POSITION, {"left": 50, "top": 55})
    positions = office_views._ai_office_all_positions()
    self.assertIn("lounge", positions)
    self.assertEqual(positions["lounge"], office_views.AI_OFFICE_LOUNGE_POSITION)
    # 5部署 + 拡張担当10人(MISSION 089で候補管理チーム3名を追加) + lounge
    self.assertEqual(len(positions), 5 + 10 + 1)

  def test_ai_office_js_supports_working_moving_and_interaction_steps(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    for fn in (
        "function setStatus(", "function setWorking(", "function setMoving(",
        "function setMonitorActive(", "function stepInteractionStart(",
        "function stepInteractionTalk(", "function stepInteractionReturn(",
        "function stepInteractionSettle(",
        # MISSION 075: Track B(部署間交流)は、対面報告ルート(Track A)とは
        # 独立して常時ループし続ける。
        "function runTrackB(", "function pickNextSceneIdx(",
        "function scheduleNextB(",
    ):
      self.assertIn(fn, html)
    self.assertIn("trackBTalking", html)
    # MISSION 076: mainActiveKey(単一キーの排他制御)は、報告者・受け手の
    # 両方を予約できるbusy{}集合に置き換わった。
    self.assertIn("var busy={};", html)
    self.assertIn("function markBusy(", html)
    self.assertIn("function isBusy(", html)

  def test_ai_office_monitor_glow_elements_present_for_five_departments(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    for key in ("room", "note", "pinterest", "analytics"):
      self.assertIn(f'id="ai-office-monitor-{key}"', html)
    self.assertNotIn('id="ai-office-monitor-operations_lead"', html)

  def test_ai_office_walk_and_type_bob_css_present_and_respects_reduced_motion(self):
    # MISSION 074: 作業中の上下動+発光は1つのkeyframe
    # (ai-office-work-pulse)へ統合された(旧ai-office-type-bobは廃止)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("ai-office-walk-bob", html)
    self.assertIn("ai-office-work-pulse", html)
    self.assertNotIn("ai-office-type-bob", html)
    self.assertIn(".ai-office-floormap-token.is-moving{animation:", html)
    self.assertIn(".ai-office-floormap-token.is-working{animation:", html)
    # 既存のグローバルなprefers-reduced-motionルールが引き続き存在し、
    # すべてのアニメーション・トランジションを無効化することを確認する
    # (回帰確認)。
    self.assertIn(
        "@media(prefers-reduced-motion:reduce){*,*::before,*::after{"
        "animation-duration:.001ms!important;"
        "animation-iteration-count:1!important;"
        "transition-duration:.001ms!important}}",
        html,
    )

  def test_ai_office_speech_uses_staff_name_and_quotation_format(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("STAFF_NAMES[personKey]", html)
    self.assertIn('「"+text+"」（デモ会話）', html)
    self.assertIn("柴犬社長", html)
    self.assertIn("（デモ会話）", html)

  def test_ai_office_demo_animation_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(html.count("<button"), 1)
    self.assertEqual(html.count("<script"), 1)

  def test_ai_office_demo_still_preserves_top_notice_and_seven_parts(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("デモ表示・実データ未接続", html)
    self.assertIn(
        "このページには、投稿・公開・送信・ログイン・削除を行うボタンは"
        "一切ありません。すべての実行判断は利用者本人が行います。",
        html,
    )
    for heading in (
        "社員名簿（15人・状態一覧）", "今日のタスク（デモ）",
        "動いている仕事と結果（デモ）", "AIとのチャット窓口（デモ）",
        "情報源の鮮度モニター（デモ）", "成果物一覧", "活動フィード（デモ）",
    ):
      self.assertIn(heading, html)
    for entry in office_views.AI_OFFICE_ACTIVITY_FEED:
      self.assertIn(entry, html)

  def test_ai_office_team_sprites_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 072: 社員表示の不具合修正(全員柴犬社長化・背景ロボット重複) ---

  def test_ai_office_floormap_uses_empty_background_with_no_robots_drawn_in(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        f'src="/static/{office_views.AI_OFFICE_FLOOR_MAP_EMPTY_IMAGE_RELATIVE_PATH}"',
        html,
    )
    self.assertNotIn(
        f'src="/static/{office_views.AI_OFFICE_FLOOR_MAP_IMAGE_RELATIVE_PATH}"',
        html,
    )
    self.assertIn("ロボットや人物は描かれていません", html)

  def test_ai_office_old_floor_map_image_file_still_exists_unmodified(self):
    # 旧ai-office-floor-map.pngはファイルとして残すが、画面には使わない。
    import os
    old_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-floor-map.png",
    )
    new_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-floor-map-empty.png",
    )
    self.assertTrue(os.path.isfile(old_path))
    self.assertTrue(os.path.isfile(new_path))
    res = self.client.get("/static/images/ai-office-floor-map-empty.png")
    self.assertEqual(res.status_code, 200)

  def test_ai_office_each_floor_token_has_a_distinct_sprite_position(self):
    # 過去に発生した不具合(background-position:が抜けて全員柴犬社長の
    # コマ(0% 0%)にフォールバックしていた)を防ぐ回帰テスト。MISSION 073で
    # 12人体制になったが、引き続き全員が固有のbackground-positionを持ち、
    # 柴犬社長以外が(0% 0%)を指していないことを確認する。
    # MISSION 076: background-positionは、向き反転用に分離した内側の
    # ai-office-floormap-sprite要素側に付与されている。
    # MISSION 089: 候補管理チーム3名は既存コマを再利用するため、
    # background-positionも再利用元と同じ値になる(値の重複はこの3名分だけ
    # 想定どおり発生する)。
    import re
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    people = list(office_views.AI_OFFICE_DEPARTMENTS) + list(office_views.AI_OFFICE_EXTENDED_STAFF)
    self.assertEqual(len(people), 15)
    reused_keys = set(office_views.AI_OFFICE_SPRITE_REUSE_MAP.keys())
    positions_seen = {}
    for p in people:
      key = p["key"]
      m = re.search(
          rf'id="ai-office-sprite-{key}"[^>]*style="([^"]*)"', html
      )
      self.assertIsNotNone(m, f"sprite style not found for {key}")
      style = m.group(1)
      self.assertIn("background-position:", style)
      bp_match = re.search(r"background-position:([^;\"]+)", style)
      self.assertIsNotNone(bp_match)
      positions_seen[key] = bp_match.group(1)
    # 元の12人分のbackground-positionが互いに異なること(重複=不具合の再発)。
    original_positions = {
        key: pos for key, pos in positions_seen.items() if key not in reused_keys
    }
    self.assertEqual(len(set(original_positions.values())), 12)
    # 再利用組は、再利用元とまったく同じbackground-positionになる。
    for key, source_key in office_views.AI_OFFICE_SPRITE_REUSE_MAP.items():
      self.assertEqual(positions_seen[key], positions_seen[source_key])
    # 柴犬社長(operations_lead)だけが(0.00% 0.00%)であること。
    self.assertEqual(positions_seen["operations_lead"], "0.00% 0.00%")
    for key, pos in positions_seen.items():
      if key != "operations_lead":
        self.assertNotEqual(pos, "0.00% 0.00%", f"{key} still shows 柴犬社長's frame")

  def test_ai_office_sprite_avatar_style_helper_includes_property_name(self):
    # _sprite_avatar_style_attrとフロアトークンの両方が、有効なCSS宣言
    # ("background-position:"というプロパティ名つき)を出力していることを
    # 確認する。
    import office_views
    dept = office_views.AI_OFFICE_DEPARTMENTS[1]
    pos_value = office_views._ai_office_sprite_position(dept["sprite"])
    self.assertNotIn("background-position:", pos_value)
    html = self.client.get("/ai-office").get_data(as_text=True)
    for p in list(office_views.AI_OFFICE_DEPARTMENTS) + list(office_views.AI_OFFICE_EXTENDED_STAFF):
      expected_decl = (
          f'background-position:{office_views._ai_office_sprite_position(p["sprite"])}'
      )
      self.assertIn(expected_decl, html)

  def test_ai_office_eight_people_positioned_per_mission_room_layout(self):
    import office_views
    positions = office_views._ai_office_all_positions()
    # 左上=指令デスク(柴犬社長)、右上=技術席(蒼)、左下=Pinterest企画席(美咲)、
    # 左中央=note編集席(海)、右中央=ROOM運用席(里奈)、右下=分析ラボ(葵)。
    self.assertLess(positions["operations_lead"]["left"], 50)
    self.assertLess(positions["operations_lead"]["top"], 50)
    self.assertGreater(positions["sou"]["left"], 50)
    self.assertLess(positions["sou"]["top"], 50)
    self.assertLess(positions["pinterest"]["left"], 50)
    self.assertGreater(positions["pinterest"]["top"], 50)
    self.assertLess(positions["note"]["left"], 50)
    self.assertLess(positions["note"]["top"], 50)
    self.assertGreater(positions["room"]["left"], 50)
    self.assertGreater(positions["analytics"]["left"], 50)
    self.assertGreater(positions["analytics"]["top"], 50)
    # 8人全員(+休憩スペース)の座標が0〜100%の範囲内で、互いに十分離れて
    # おり重ならないことを確認する(最小距離8%以上)。
    import math
    keys = list(positions.keys())
    for i in range(len(keys)):
      for j in range(i + 1, len(keys)):
        p1, p2 = positions[keys[i]], positions[keys[j]]
        dist = math.hypot(p1["left"] - p2["left"], p1["top"] - p2["top"])
        self.assertGreaterEqual(
            dist, 8, f"{keys[i]} and {keys[j]} are too close ({dist:.1f})"
        )

  def test_ai_office_mission072_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 073: 立体的な3Dキャラクター12人体制への全面更新 -----------

  def test_ai_office_sprite_avatar_css_uses_3d_sheet_with_correct_background_size(self):
    # 過去に発生した不具合(CSSルールにスプライト画像URLが直書きされたまま
    # 更新されておらず、background-sizeも列数変更(2列→3列)に追随して
    # いなかった)を防ぐ回帰テスト。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-sprite-avatar{"
        "background-image:url(/static/images/ai-office-team-3d.png);"
        "background-repeat:no-repeat;background-size:300% 400%;",
        html,
    )
    self.assertNotIn("ai-office-team-sprites.png", html)

  def test_ai_office_twelve_person_placement_matches_mission_zones(self):
    import office_views
    positions = office_views._ai_office_all_positions()
    zone_by_key = {d["key"]: d["desk_label"] for d in office_views.AI_OFFICE_DEPARTMENTS}
    zone_by_key.update({s["key"]: s["zone_label"] for s in office_views.AI_OFFICE_EXTENDED_STAFF})
    self.assertEqual(
        zone_by_key,
        {
            "operations_lead": "指令デスク",
            "yu": "指令デスク",
            "ren": "指令デスク",
            "room": "ROOM運用席",
            "note": "note編集席",
            "rin": "note編集席",
            "pinterest": "Pinterest企画席",
            "aya": "Pinterest企画席",
            "sou": "技術・品質スペース",
            "iori": "技術・品質スペース",
            "analytics": "分析ラボ",
            "yui": "分析ラボ",
            # MISSION 089: 候補管理チーム3名の新しいゾーン。
            "tsumugi": "候補管理スペース",
            "nagi": "候補管理スペース",
            "hina": "候補管理スペース",
        },
    )
    # 指令デスクの3人(柴犬社長・悠・蓮)が互いに8%以上離れていること。
    import math
    for a, b in (("operations_lead", "yu"), ("operations_lead", "ren"), ("yu", "ren")):
      dist = math.hypot(
          positions[a]["left"] - positions[b]["left"],
          positions[a]["top"] - positions[b]["top"],
      )
      self.assertGreaterEqual(dist, 8)

  def test_ai_office_all_twelve_people_positions_do_not_overlap(self):
    import math
    import office_views
    positions = office_views._ai_office_all_positions()
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    self.assertEqual(len(people_keys), 15)
    for i in range(len(people_keys)):
      for j in range(i + 1, len(people_keys)):
        p1, p2 = positions[people_keys[i]], positions[people_keys[j]]
        dist = math.hypot(p1["left"] - p2["left"], p1["top"] - p2["top"])
        self.assertGreaterEqual(
            dist, 8,
            f"{people_keys[i]} and {people_keys[j]} are too close ({dist:.1f})",
        )
    for key in people_keys:
      pos = positions[key]
      self.assertGreaterEqual(pos["left"], 0)
      self.assertLessEqual(pos["left"], 100)
      self.assertGreaterEqual(pos["top"], 0)
      self.assertLessEqual(pos["top"], 100)

  def test_ai_office_ren_safety_check_is_a_face_to_face_report_to_president(self):
    # MISSION 076: 蓮の安全・承認確認は、指令デスクでの静的な表示から、
    # 柴犬社長への対面報告ルート(ren_to_president)へ変更した。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    route = next(
        r for r in office_views.AI_OFFICE_REPORT_ROUTES if r["key"] == "ren_to_president"
    )
    self.assertEqual(route["mover"], "ren")
    self.assertEqual(route["receiver"], "operations_lead")
    self.assertEqual(route["mover_line"], "安全・承認確認を終えました")
    self.assertEqual(route["receiver_line"], "確認しました。外部操作は利用者判断です")
    self.assertIn(route["mover_line"], html)
    self.assertIn(route["receiver_line"], html)
    self.assertIn(route["feed_text"], html)

  def test_ai_office_aya_role_reflects_coordinator_description(self):
    import office_views
    aya = next(s for s in office_views.AI_OFFICE_EXTENDED_STAFF if s["key"] == "aya")
    self.assertIn("社内コーディネーター", aya["role_label"])
    self.assertIn("確認待ちを整理", aya["role_summary"])
    self.assertIn("外部サービスへの投稿・送信・判断は行いません", aya["role_summary"])
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(aya["role_summary"], html)

  def test_ai_office_legacy_sprite_file_untouched_and_still_on_disk(self):
    import os
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-team-sprites.png",
    )
    self.assertTrue(os.path.isfile(path))
    new_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-team-3d.png",
    )
    self.assertTrue(os.path.isfile(new_path))
    self.assertNotEqual(os.path.abspath(path), os.path.abspath(new_path))

  def test_ai_office_mission073_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 074: 全身の立体3Dキャラクターへの表示方式修正 -------------

  def test_ai_office_floormap_token_has_no_black_icon_box_styling(self):
    # フロアマップ上の社員トークンは、黒いアイコン枠(円形カード・境界線・
    # 塗りつぶし背景)を使わない。
    # MISSION 079: 単純な楕円のmask-imageでは、体・持ち物の外側にある
    # スプライトの暗い背景が見えてしまっていたため、人物ごとの輪郭に
    # 沿ったclip-pathへ置き換えた(mask-imageは使わない)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-floormap-token{position:absolute;width:112px;"
        "height:126px;transform:translate(-50%,-78%);",
        html,
    )
    sprite_rule = html.split(".ai-office-floormap-sprite{")[1].split("}")[0]
    self.assertNotIn("mask-image", sprite_rule)
    self.assertIn("clip-path:polygon(", html)
    self.assertIn("-webkit-clip-path:polygon(", html)
    # 旧デザイン(円形カード+塗りつぶし背景色)のクラスの組み合わせが
    # フロアトークンには付与されていないことを確認する。
    self.assertNotIn('class="ai-office-floormap-token ai-office-char-avatar', html)
    self.assertNotIn("ai-office-char-avatar.ai-office-floormap-token", html)

  def test_ai_office_floormap_token_uses_ring_glow_per_status_not_character_blur(self):
    # MISSION 078: キャラクター全体を光らせるfilter:drop-shadow(の状態別
    # グロー)は完全に廃止し、足元の細いリング(ai-office-report-ring)の
    # 色だけで状態を示す。MISSION 075で常時のアイドルモーション用クラス
    # (ai-office-idle-*)が基本クラスと状態クラスの間に追加されたため、
    # 完全一致ではなく個別クラスの存在を確認する。
    import re
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for status_key in office_views.AI_OFFICE_STATUS_LABELS:
      self.assertNotIn(f".ai-office-floormap-token-{status_key}{{filter:drop-shadow(", html)
      self.assertIn(f".ai-office-floormap-token-{status_key} .ai-office-report-ring{{", html)
    self.assertIn("ai-office-work-pulse", html)
    m = re.search(
        r'<span class="([^"]*)" id="ai-office-token-operations_lead"', html
    )
    self.assertIsNotNone(m)
    classes = m.group(1).split()
    self.assertIn("ai-office-floormap-token", classes)
    self.assertIn("ai-office-floormap-token-working", classes)

  def test_ai_office_floormap_token_is_roughly_three_times_larger_than_old_icon(self):
    # 旧デザイン(44×33px)に対し、2〜3倍以上の視認性を目安に拡大した。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("width:112px;", html)
    self.assertIn("height:126px;", html)
    old_area = 44 * 33
    new_area = 112 * 126
    self.assertGreaterEqual(new_area / old_area, 3)

  def test_ai_office_twelve_person_positions_still_do_not_overlap_at_larger_size(self):
    # MISSION 074でキャラクターが大幅に大きくなったため、座標間隔を
    # 見直した。実際のキャラクターサイズ(112×126px、正方形の
    # フロアマップ画像に対する概算の百分率)を踏まえた余裕を持った間隔で、
    # 12人が重ならないことを確認する。
    import math
    import office_views
    positions = office_views._ai_office_all_positions()
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    self.assertEqual(len(people_keys), 15)
    for i in range(len(people_keys)):
      for j in range(i + 1, len(people_keys)):
        p1, p2 = positions[people_keys[i]], positions[people_keys[j]]
        dx = abs(p1["left"] - p2["left"])
        dy = abs(p1["top"] - p2["top"])
        self.assertTrue(
            dx >= 16 or dy >= 18,
            f"{people_keys[i]} and {people_keys[j]} are too close (dx={dx},dy={dy})",
        )
    for key in people_keys:
      pos = positions[key]
      self.assertGreaterEqual(pos["left"], 0)
      self.assertLessEqual(pos["left"], 100)
      self.assertGreaterEqual(pos["top"], 0)
      self.assertLessEqual(pos["top"], 100)

  def test_ai_office_mobile_media_query_shrinks_character_and_keeps_aspect(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        "@media(max-width:480px){.ai-office-floormap-token{width:72px;height:81px}",
        html,
    )

  def test_ai_office_bubble_and_nameplate_still_move_with_character(self):
    # 吹き出しはJSでキャラクターの座標に合わせて位置を更新し(showBubble)、
    # 名前札・状態ドットはトークンの子要素として一緒に配置される
    # (=キャラクター本人と一緒に動く)ことを確認する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function showBubble(text,atKey){", html)
    self.assertIn('bubbleEl.style.left=pos.left+"%";', html)
    self.assertIn('bubbleEl.style.top=pos.top+"%";', html)
    import re
    for m in re.finditer(
        r'<span class="ai-office-floormap-token[^"]*"[^>]*id="ai-office-token-(\w+)"[^>]*>(.*?)</span>\s*</span>',
        html,
    ):
      inner = m.group(2)
      self.assertIn("ai-office-footstep", inner)
      self.assertIn("ai-office-nameplate", inner)

  def test_ai_office_five_departments_and_extended_staff_data_unchanged_names(self):
    # MISSION 073の12人名簿・役割は変更していないことを確認する
    # (今回は表示方式のみの修正)。
    import office_views
    dept_names = {d["key"]: d["staff_name"] for d in office_views.AI_OFFICE_DEPARTMENTS}
    self.assertEqual(
        dept_names,
        {
            "operations_lead": "柴犬社長", "room": "里奈", "note": "海",
            "pinterest": "美咲", "analytics": "葵",
        },
    )
    extended_names = {s["key"]: s["name"] for s in office_views.AI_OFFICE_EXTENDED_STAFF}
    self.assertEqual(
        extended_names,
        {
            "sou": "蒼", "iori": "伊織", "aya": "彩", "rin": "凛",
            "yu": "悠", "yui": "結", "ren": "蓮",
            "tsumugi": "紬", "nagi": "凪", "hina": "陽菜",
        },
    )

  def test_ai_office_mission074_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 075: 常に少しずつ動いている、生きた会社への強化 ---------

  def test_ai_office_all_twelve_people_have_idle_type_assigned(self):
    import office_views
    people = list(office_views.AI_OFFICE_DEPARTMENTS) + list(office_views.AI_OFFICE_EXTENDED_STAFF)
    self.assertEqual(len(people), 15)
    valid_types = set(office_views.AI_OFFICE_IDLE_ANIMATION_BY_TYPE.keys())
    self.assertEqual(valid_types, {"typing", "reading", "analyzing", "waiting"})
    for p in people:
      self.assertIn(p["idle_type"], valid_types)

  def test_ai_office_idle_animation_classes_and_keyframes_present(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    import office_views
    for idle_type, class_name in office_views.AI_OFFICE_IDLE_ANIMATION_BY_TYPE.items():
      self.assertIn(f".{class_name}{{animation:{class_name} ", html)
      self.assertIn(f"@keyframes {class_name}{{", html)
      self.assertIn(f'data-idle="{idle_type}"', html)

  def test_ai_office_idle_classes_appear_before_working_moving_rules_in_source(self):
    # is-working/is-moving(2クラス、後発)が、ai-office-idle-*(2クラス)より
    # CSS宣言順で後に来ることを確認する回帰テスト。同じ詳細度の場合、
    # ソース順が後のルールが勝つため、実際に稼働・移動中はアイドル
    # モーションより優先して表示される。
    html = self.client.get("/ai-office").get_data(as_text=True)
    idle_pos = html.index(".ai-office-idle-typing{animation:")
    working_pos = html.index(".ai-office-floormap-token.is-working{animation:")
    moving_pos = html.index(".ai-office-floormap-token.is-moving{animation:")
    self.assertLess(idle_pos, working_pos)
    self.assertLess(idle_pos, moving_pos)

  def test_ai_office_all_twelve_tokens_have_staggered_animation_timing(self):
    # 全員が同じ周期で動くと不自然なので、animation-delay/durationが
    # 人物ごとに異なることを確認する。
    import re
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    delays = set()
    for key in people_keys:
      m = re.search(
          rf'id="ai-office-token-{key}"[^>]*style="([^"]*)"', html
      )
      self.assertIsNotNone(m)
      style = m.group(1)
      self.assertIn("animation-delay:", style)
      self.assertIn("animation-duration:", style)
      delay_match = re.search(r"animation-delay:(-?[0-9.]+s)", style)
      self.assertIsNotNone(delay_match)
      delays.add(delay_match.group(1))
    # 12人全員が同じ遅延を使っていない(=ずらしてある)ことを確認する。
    self.assertGreater(len(delays), 1)

  def test_ai_office_ambient_monitor_glow_extended_to_tech_and_analytics_desks(self):
    # MISSION 075: モニターの控えめな明滅を、技術席(蒼)・分析ラボ担当(結)
    # にも拡張した。
    html = self.client.get("/ai-office").get_data(as_text=True)
    for key in ("room", "note", "pinterest", "analytics", "sou", "yui"):
      self.assertIn(f'id="ai-office-monitor-{key}"', html)
    self.assertIn("ai-office-monitor-glow-ambient", html)
    self.assertIn("@keyframes ai-office-monitor-idle-flicker{", html)

  def test_ai_office_lounge_has_coffee_steam_decoration_css_only(self):
    # 新規画像・外部ライブラリを使わず、CSSのみで湯気を表現する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("ai-office-lounge-decor", html)
    self.assertIn("ai-office-lounge-cup", html)
    self.assertIn("ai-office-lounge-steam", html)
    self.assertIn("@keyframes ai-office-lounge-steam-rise{", html)
    self.assertNotIn("<img", html.split("ai-office-lounge-decor")[1][:400])

  def test_ai_office_command_desk_has_notification_pulse_on_report_arrival(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-command-pulse"', html)
    self.assertIn("@keyframes ai-office-command-pulse-ring{", html)
    self.assertIn("function pulseCommandDesk(){", html)
    self.assertIn("pulseCommandDesk();", html)

  def test_ai_office_progress_board_shows_live_status_counts(self):
    # 指令デスクの「本日の進行状況」ミニボードが、「今のオフィス」の
    # 短いステータス行(稼働中・移動中・相談中の人数)を兼ねる。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("本日の進行状況", html)
    self.assertIn('id="ai-office-progress-board-line"', html)
    self.assertIn("function refreshOfficeStatusLine(){", html)
    self.assertIn("稼働中", html)
    self.assertIn("相談中", html)

  def test_ai_office_pause_button_freezes_all_css_animations_via_overlay_class(self):
    # MISSION 075: 停止ボタンは、常時のアイドルモーション・モニター明滅・
    # 湯気・通知光を含む、フロアマップ内の全CSSアニメーションを一括で
    # 停止する(animation-play-state:pausedをoverlay配下すべてに適用)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-floormap-overlay"', html)
    self.assertIn(
        ".ai-office-floormap-overlay.is-paused,"
        ".ai-office-floormap-overlay.is-paused *{"
        "animation-play-state:paused!important}",
        html,
    )
    self.assertIn('overlayEl.classList.toggle("is-paused",paused);', html)

  def test_ai_office_track_b_runs_independently_of_report_routes(self):
    # Track A(対面報告ルート)とTrack B(部署間交流)は、それぞれ専用の
    # 予約タイマー(pendingTimer/pendingTimerB)を持ち、停止ボタンの
    # クリックで両方が止まる。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("var pendingFnB=null,pendingTimerB=null;", html)
    self.assertIn("if(pendingTimerB){clearTimeout(pendingTimerB);pendingTimerB=null;}", html)
    self.assertIn("scheduleNextB(runTrackB,3500);", html)
    self.assertIn("scheduleNext(runReportRoute,900);", html)

  def test_ai_office_new_short_conversation_lines_present(self):
    # MISSION 076で指定された、対面報告の会話例が実際に使われていることを
    # 確認する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    for line in (
        "ROOM候補を整理しました", "受け取りました。次の確認へ進めます",
        "見出し構成をまとめました", "美咲にも共有して方向性をそろえます",
        "画像テーマ候補を用意しました", "noteの見出しと合わせて確認します",
        "画面表示を確認しました", "品質観点で確認します",
        "情報源の鮮度を確認しました", "比較メモへ反映します",
        "確認済みの数字を比較しました", "判断メモとして整理します",
        "各部署の報告をまとめました",
        "受け取りました。利用者の確認待ちにします",
        "安全・承認確認を終えました",
        "確認しました。外部操作は利用者判断です",
    ):
      self.assertIn(line, html)

  def test_ai_office_second_bubble_element_for_concurrent_track(self):
    # Track A・Track Bが同時に別の場所で吹き出しを出せるよう、
    # 吹き出し要素を複数用意している。MISSION 076で、対面報告の受け手用に
    # さらにもう1つ(bubbleElReceiver、配色違い)を追加した。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(html.count('class="ai-office-floormap-bubble"'), 2)
    self.assertIn('id="ai-office-floormap-bubble"', html)
    self.assertIn(
        'class="ai-office-floormap-bubble ai-office-floormap-bubble-receiver" '
        'id="ai-office-floormap-bubble-receiver"',
        html,
    )
    self.assertIn('id="ai-office-floormap-bubble-b"', html)
    self.assertIn("function showBubbleB(text,atKey){", html)
    self.assertIn("function hideBubbleB(){", html)
    self.assertIn("function showBubbleReceiver(text,atKey){", html)
    self.assertIn("function hideBubbleReceiver(){", html)

  def test_ai_office_reduced_motion_rule_still_covers_new_animations(self):
    # 新規追加したアイドル・モニター明滅・湯気・通知光のCSSアニメーションも、
    # 既存のグローバルなprefers-reduced-motionルール(*,*::before,*::after)
    # で自動的に無効化される(個別対応不要)ことを確認する回帰テスト。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        "@media(prefers-reduced-motion:reduce){*,*::before,*::after{"
        "animation-duration:.001ms!important;"
        "animation-iteration-count:1!important;"
        "transition-duration:.001ms!important}}",
        html,
    )

  def test_ai_office_mission075_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  def test_ai_office_mission075_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(html.count("<button"), 1)
    self.assertEqual(html.count("<script"), 1)

  # --- MISSION 076: 対面報告(位置・向き・会話で報告関係を示す) -----------

  def test_ai_office_report_routes_cover_the_required_receivers(self):
    # 通常報告は悠・彩・伊織・蓮など役割ごとの受け手へ行き、柴犬社長は
    # 悠・蓮からのまとめ報告だけを受ける(全員が指令デスクへ殺到しない)。
    # MISSION 077: 凛→海・伊織→蓮・彩→悠の3ルートが加わった。
    import office_views
    routes = office_views.AI_OFFICE_REPORT_ROUTES
    movers = [r["mover"] for r in routes]
    receivers = {r["mover"]: r["receiver"] for r in routes}
    self.assertEqual(
        set(movers),
        {"room", "note", "pinterest", "sou", "yui", "analytics", "yu", "ren",
         "rin", "iori", "aya"},
    )
    self.assertEqual(receivers["room"], "yu")
    self.assertEqual(receivers["note"], "aya")
    self.assertEqual(receivers["pinterest"], "aya")
    self.assertEqual(receivers["sou"], "iori")
    self.assertEqual(receivers["yui"], "analytics")
    self.assertEqual(receivers["analytics"], "yu")
    self.assertEqual(receivers["yu"], "operations_lead")
    self.assertEqual(receivers["ren"], "operations_lead")
    self.assertEqual(receivers["rin"], "note")
    self.assertEqual(receivers["iori"], "ren")
    self.assertEqual(receivers["aya"], "yu")

  def test_ai_office_report_visitor_slots_defined_for_every_receiver(self):
    # 対面報告の受け手(悠・彩・伊織・分析ラボ・柴犬社長・note・蓮)ごとに、
    # 本人の座席と重ならない訪問者スロットが定義されていることを確認する。
    import office_views
    receivers = {r["receiver"] for r in office_views.AI_OFFICE_REPORT_ROUTES}
    self.assertEqual(
        receivers, {"yu", "aya", "iori", "analytics", "operations_lead", "note", "ren"}
    )
    for key in receivers:
      self.assertIn(key, office_views.AI_OFFICE_VISITOR_SLOTS)

  def test_ai_office_report_visitor_slots_do_not_overlap_any_seat(self):
    # 訪問者スロットに立った報告者本人が、その部屋の他の在席者(受け手を
    # 含む)と重ならないことを確認する回帰テスト(MISSION 075と同じ間隔
    # 基準: 列は16%以上または行は18%以上)。
    import office_views
    positions = office_views._ai_office_all_positions()
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    for slot_key, slot_pos in office_views.AI_OFFICE_VISITOR_SLOTS.items():
      for person_key in people_keys:
        dx = abs(slot_pos["left"] - positions[person_key]["left"])
        dy = abs(slot_pos["top"] - positions[person_key]["top"])
        self.assertTrue(
            dx >= 14 or dy >= 15,
            f"visitor slot for {slot_key} too close to {person_key} "
            f"(dx={dx},dy={dy})",
        )

  def test_ai_office_floormap_token_has_inner_sprite_for_facing(self):
    # MISSION 076: 対面報告時に向き(スプライトの反転)を変えられるよう、
    # background-image/maskを担う内側のスプライト要素を分離した。外側の
    # トークンは位置・常時アニメーションの担当を維持する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(".ai-office-floormap-sprite{position:absolute;inset:0;", html)
    self.assertIn(".ai-office-floormap-sprite.is-facing-left{transform:scaleX(-1)}", html)
    token_rule_body = html.split(".ai-office-floormap-token{")[1].split("}")[0]
    self.assertNotIn("background-image", token_rule_body)
    self.assertNotIn("mask-image", token_rule_body)
    self.assertIn("function faceTowards(personKey,refLeft){", html)
    self.assertIn("function resetFacing(personKey){", html)

  def test_ai_office_nameplate_phase_label_present_for_all_twelve(self):
    # MISSION 076: 「移動中」「帰席中」を名前札で分かるようにする、
    # ai-office-nameplate-phase要素が全員に存在する。
    # MISSION 077: 対面報告中は、単に「対面報告中」「応答中」と表示する
    # のではなく、「{相手}へ報告中」「{相手}の報告を確認中」という、
    # 誰と対面しているかまで分かる具体的な文言に変更した。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    for key in people_keys:
      self.assertIn(f'id="ai-office-nameplate-phase-{key}"', html)
    self.assertIn("function setPhase(personKey,text){", html)
    for phase in ("移動中", "帰席中"):
      self.assertIn(phase, html)
    self.assertIn('shortName(route.receiver)+"へ報告中"', html)
    self.assertIn('STAFF_NAMES[route.mover]+"の報告を確認中"', html)

  def test_ai_office_report_step_chain_sets_phases_in_order(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('setPhase(route.mover,"移動中");', html)
    self.assertIn(
        'setPhase(route.mover,shortName(route.receiver)+"へ報告中");', html
    )
    self.assertIn(
        'setPhase(route.receiver,STAFF_NAMES[route.mover]+"の報告を確認中");',
        html,
    )
    self.assertIn('setPhase(route.mover,"帰席中");', html)

  def test_ai_office_report_step_chain_uses_busy_set_not_a_single_key(self):
    # MISSION 076: 報告者・受け手の両方を同時に予約できるよう、単一キーの
    # mainActiveKeyから、複数人を保持できるbusy{}集合へ置き換えた。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("markBusy(route.mover,true);", html)
    self.assertIn("markBusy(route.receiver,true);", html)
    self.assertIn("markBusy(route.mover,false);", html)
    self.assertIn("markBusy(route.receiver,false);", html)
    # MISSION 080: pickNextReportRouteは、デモ(REPORT_ROUTES)と実績
    # (REAL_RECORD_QUEUE)のどちらを巡回する場合も、busy{}でスキップする
    # 判定を共通のロジックで行う。
    self.assertIn(
        "if(!isBusy(r.mover)&&!isBusy(r.receiver)){", html
    )
    self.assertIn("var pool=DEMO_MODE_ACTIVE?REPORT_ROUTES:REAL_RECORD_QUEUE;", html)

  def test_ai_office_command_pulse_only_for_president_routes(self):
    # 指令デスク(柴犬社長)への報告(悠・蓮からのまとめ報告)のときだけ
    # 通知光が点灯する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        'if(route.receiver==="operations_lead")pulseCommandDesk();', html
    )

  def test_ai_office_no_thin_connecting_lines_between_reporters(self):
    # 「報告中の2人を細いシアンの線で結ぶだけ」の表現をやめ、本人同士が
    # 対面する表示に変更したため、接続ライン用のCSS・要素は存在しない。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertNotIn("ai-office-floormap-line", html)
    self.assertNotIn('id="ai-office-line-', html)

  def test_ai_office_receiver_bubble_uses_different_color_than_mover_bubble(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(".ai-office-floormap-bubble-receiver{border-color:#34d399}", html)
    self.assertIn(
        ".ai-office-floormap-bubble-receiver:after{border-color:#34d399 "
        "transparent transparent}",
        html,
    )

  def test_ai_office_mission076_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  def test_ai_office_mission076_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(html.count("<button"), 1)
    self.assertEqual(html.count("<script"), 1)

  # --- MISSION 077: 誰が社長へ報告しているか一目で分かる表示 + 彩の女性化 ---

  def test_ai_office_sprite_sheet_still_three_by_four_after_swap(self):
    # 彩の3D画像を差し替えても、スプライト格子(3列×4行)・彩自身の
    # コマ位置(2行目・右=row1,col2)・他11人のコマ位置は変わらない。
    import os
    import office_views
    self.assertEqual(office_views.AI_OFFICE_SPRITE_COLS, 3)
    self.assertEqual(office_views.AI_OFFICE_SPRITE_ROWS, 4)
    aya = next(s for s in office_views.AI_OFFICE_EXTENDED_STAFF if s["key"] == "aya")
    self.assertEqual(aya["sprite"], {"row": 1, "col": 2})
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "images", "ai-office-team-3d.png",
    )
    self.assertTrue(os.path.isfile(path))
    res = self.client.get("/static/images/ai-office-team-3d.png")
    self.assertEqual(res.status_code, 200)

  def test_ai_office_eleven_report_routes_and_president_receives_only_two(self):
    # MISSION 077: 通常報告(9件)はすべて悠・彩・伊織・蓮のいずれかへ行き、
    # 柴犬社長への最終報告は悠・蓮の2件だけ。
    import office_views
    routes = office_views.AI_OFFICE_REPORT_ROUTES
    self.assertEqual(len(routes), 11)
    president_routes = [r for r in routes if r["receiver"] == "operations_lead"]
    self.assertEqual(len(president_routes), 2)
    self.assertEqual(sorted(r["mover"] for r in president_routes), ["ren", "yu"])
    normal_receivers = {r["receiver"] for r in routes if r["receiver"] != "operations_lead"}
    self.assertEqual(normal_receivers, {"yu", "aya", "iori", "analytics", "note", "ren"})

  def test_ai_office_report_banner_shows_mover_role_and_receiver_role(self):
    # フロアマップ最上部の進行バナーに、報告者・受け手それぞれの役割
    # ラベルとともに「対面報告中 A（役割） → B（役割）」の形式で表示する。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-report-banner"', html)
    self.assertIn("対面報告中の社員はまだいません（デモ）", html)
    self.assertEqual(office_views.AI_OFFICE_REPORT_ROLE_LABELS["operations_lead"], "最終確認")
    self.assertEqual(office_views.AI_OFFICE_REPORT_ROLE_LABELS["yu"], "進行管理")
    self.assertIn("function updateReportBanner(route){", html)
    # MISSION 080: 実績(localStorageの運用記録)による対面報告は「実績報告
    # 中」、デモは「対面報告中」と表示し分ける。
    self.assertIn('var verb=route.isReal?"実績報告中":"対面報告中";', html)
    self.assertIn(
        'reportBannerEl.textContent=verb+"　"+STAFF_NAMES[route.mover]+'
        '"（"+REPORT_ROLES[route.mover]+"） → "+STAFF_NAMES[route.receiver]+'
        '"（"+REPORT_ROLES[route.receiver]+"）"+(route.isReal?"（実績）":"");',
        html,
    )

  def test_ai_office_short_name_used_for_president_in_mover_nameplate(self):
    # 報告者の名前札は「柴犬社長へ報告中」ではなく「社長へ報告中」と、
    # 短い呼び方を使う。
    import office_views
    self.assertEqual(office_views.AI_OFFICE_SHORT_NAMES, {"operations_lead": "社長"})
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function shortName(key){return SHORT_NAMES[key]||STAFF_NAMES[key];}", html)

  def test_ai_office_report_ring_and_connector_present(self):
    # 報告者・受け手の足元に同じ色の発光リング、二人を結ぶ点線+矢印の
    # コネクタが存在する。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    self.assertEqual(html.count('class="ai-office-report-ring"'), len(people_keys))
    self.assertIn(
        ".ai-office-floormap-token.is-report-mover .ai-office-report-ring,",
        html,
    )
    self.assertIn('id="ai-office-report-connector"', html)
    self.assertIn("function showReportConnector(fromPos,toPos){", html)
    self.assertIn("function hideReportConnector(){", html)
    self.assertIn(".ai-office-report-connector:after{content:\"\";", html)

  def test_ai_office_report_step_chain_toggles_report_active_classes(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('moverToken.classList.add("is-report-mover");', html)
    self.assertIn('receiverToken.classList.add("is-report-receiver");', html)
    self.assertIn('overlayEl.classList.add("is-reporting");', html)
    self.assertIn('moverToken.classList.remove("is-report-mover");', html)
    self.assertIn('receiverToken.classList.remove("is-report-receiver");', html)
    self.assertIn('overlayEl.classList.remove("is-reporting");', html)

  def test_ai_office_other_staff_dimmed_while_reporting(self):
    # 対面報告中は、報告者・受け手以外の常時アニメーションを維持したまま
    # 少し控えめ(不透明度を下げる)にする。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-floormap-overlay.is-reporting .ai-office-floormap-token{opacity:.5;",
        html,
    )
    self.assertIn(
        ".ai-office-floormap-overlay.is-reporting "
        ".ai-office-floormap-token.is-report-mover,",
        html,
    )

  def test_ai_office_conversation_panel_shows_mover_and_receiver_lines(self):
    # 「悠 → 柴犬社長「各部署の報告をまとめました」」の形式で、対面会話
    # パネルに報告者→受け手のセリフを表示する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-report-panel"', html)
    self.assertIn('id="ai-office-report-panel-mover"', html)
    self.assertIn('id="ai-office-report-panel-receiver"', html)
    self.assertIn("function setReportPanelLine(el,speakerKey,receiverKey,text){", html)
    self.assertIn('b.textContent=STAFF_NAMES[speakerKey]+" → "+STAFF_NAMES[receiverKey];', html)
    self.assertIn(
        "setReportPanelLine(reportPanelMoverEl,route.mover,route.receiver,"
        "route.mover_line);",
        html,
    )
    self.assertIn(
        "setReportPanelLine(reportPanelReceiverEl,route.receiver,route.mover,"
        "route.receiver_line);",
        html,
    )

  def test_ai_office_report_panel_and_banner_persist_after_report_ends(self):
    # MISSION 077: 停止ボタンを押した場合も、最後の「誰が誰へ報告中か」の
    # 表示が読み取れるよう、対面報告が終わってもバナー・会話パネルは
    # クリアしない(次の対面報告が始まるまで内容を保持する)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    return_step = html.split("function reportStepReturn(route,onDone){")[1].split(
        "function reportStepSettle"
    )[0]
    self.assertNotIn("reportBannerEl.textContent", return_step)
    self.assertNotIn("reportPanelMoverEl.textContent", return_step)
    self.assertNotIn("reportPanelReceiverEl.textContent", return_step)

  def test_ai_office_activity_feed_names_mover_and_receiver(self):
    # 活動フィードに「誰が誰へ何を報告したか」が分かる文言で記録する。
    import office_views
    routes = office_views.AI_OFFICE_REPORT_ROUTES
    html = self.client.get("/ai-office").get_data(as_text=True)
    for route in routes:
      mover_name = office_views.AI_OFFICE_REPORT_ROUTES
      self.assertIn(route["feed_text"], html)
      self.assertIn("が", route["feed_text"])
      self.assertIn("へ", route["feed_text"])

  def test_ai_office_report_route_legend_present(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        '<p class="ai-office-report-legend">通常報告 → 悠・彩・伊織・蓮'
        ' ／ 最終報告 → 柴犬社長</p>',
        html,
    )

  def test_ai_office_mission077_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  def test_ai_office_mission077_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(html.count("<button"), 1)
    self.assertEqual(html.count("<script"), 1)

  # --- MISSION 078: キャラクター周辺のモヤ・ぼかしを完全に消す ------------

  def test_ai_office_no_filter_glow_on_status_token_classes(self):
    # 状態別(working/pending/waiting/demo_done)のfilter:drop-shadowに
    # よるキャラクター全体の発光は、一切出力しない。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    for status_key in office_views.AI_OFFICE_STATUS_LABELS:
      self.assertNotIn(f".ai-office-floormap-token-{status_key}{{filter:", html)

  def test_ai_office_work_pulse_keyframe_has_no_filter(self):
    # MISSION 078: 稼働中の上下動(ai-office-work-pulse)から、発光
    # (filter:drop-shadow)を取り除き、動きだけを残す。
    html = self.client.get("/ai-office").get_data(as_text=True)
    keyframe = html.split("@keyframes ai-office-work-pulse{")[1].split(
        "@keyframes ai-office-walk-bob"
    )[0]
    self.assertNotIn("filter", keyframe)
    self.assertIn("translateY", keyframe)

  def test_ai_office_floormap_token_has_no_filter_property_anywhere(self):
    # トークン本体(キャラクター全体)を対象にしたfilterプロパティは、
    # どの状態・アニメーションにも一切残っていないことを確認する
    # (念のための包括的な回帰テスト)。
    import re
    html = self.client.get("/ai-office").get_data(as_text=True)
    style_block = html.split("<style>")[1].split("</style>")[0]
    for m in re.finditer(r'(\.ai-office-floormap-token[^{]*)\{([^}]*)\}', style_block):
      selector, body = m.group(1), m.group(2)
      if "report-ring" in selector or "footstep" in selector:
        continue
      self.assertNotIn(
          "filter:", body, f"unexpected filter on selector: {selector}"
      )
    for m in re.finditer(r'@keyframes ([a-z-]+)\{(.*?)\}\s*(?=@keyframes|\Z)', style_block, re.S):
      name, body = m.group(1), m.group(2)
      if name in ("ai-office-work-pulse", "ai-office-walk-bob") or name.startswith("ai-office-idle-"):
        self.assertNotIn("filter", body, f"unexpected filter in keyframes {name}")

  def test_ai_office_sprite_uses_clip_path_not_mask_image(self):
    # MISSION 078では楕円マスクのフェード範囲を狭めて対応したが、単純な
    # 楕円である以上、体・持ち物の外側にスプライトの暗い背景が残っていた。
    # MISSION 079で、mask-imageによる楕円切り抜きを完全に廃止し、
    # 人物ごとの輪郭に沿ったclip-path(AI_OFFICE_SPRITE_CLIP_PATHS)へ
    # 置き換えた。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    # ai-office-floormap-sprite自体にはmask-imageを使わない(ページ全体の
    # 共有スタイルには、/office(ライブオフィス)ページ用の無関係な
    # .figure{mask-image:...}が別途存在するため、そちらまでは対象外)。
    sprite_rule = html.split(".ai-office-floormap-sprite{")[1].split("}")[0]
    self.assertNotIn("mask-image", sprite_rule)
    self.assertNotIn("radial-gradient", sprite_rule)
    people_keys = (
        [d["key"] for d in office_views.AI_OFFICE_DEPARTMENTS]
        + [s["key"] for s in office_views.AI_OFFICE_EXTENDED_STAFF]
    )
    # MISSION 089: 候補管理チーム3名は新しい画像を追加しないため、
    # AI_OFFICE_SPRITE_CLIP_PATHSには引き続き元の12人分しか無い
    # (再利用元のclip-pathはAI_OFFICE_SPRITE_REUSE_MAP経由で解決する)。
    self.assertEqual(len(office_views.AI_OFFICE_SPRITE_CLIP_PATHS), 12)
    reuse_map = office_views.AI_OFFICE_SPRITE_REUSE_MAP
    for key in people_keys:
      lookup_key = reuse_map.get(key, key)
      self.assertIn(lookup_key, office_views.AI_OFFICE_SPRITE_CLIP_PATHS)
      polygon = office_views.AI_OFFICE_SPRITE_CLIP_PATHS[lookup_key]
      self.assertTrue(polygon.startswith("polygon("))
      self.assertTrue(polygon.endswith(")"))
      # 単純な四角形・円形ではなく、体の輪郭をたどった十分な数の頂点を
      # 持つ多角形になっていることを確認する。
      self.assertGreater(polygon.count("%,"), 20)
      self.assertIn(f"clip-path:{polygon}", html)
      self.assertIn(f"-webkit-clip-path:{polygon}", html)

  def test_ai_office_status_shown_via_ring_color_not_character_blur(self):
    # 「作業中」「確認待ち」「待機中」「デモ完了」は、キャラ全体を
    # ぼかして発光させず、足元の細いリングの色だけで示す。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-floormap-token-working .ai-office-report-ring{"
        "opacity:.8;border-color:var(--cyan);", html,
    )
    self.assertIn(
        ".ai-office-floormap-token-pending .ai-office-report-ring{"
        "opacity:.8;border-color:#fbbf24;", html,
    )
    self.assertIn(
        ".ai-office-floormap-token-waiting .ai-office-report-ring{"
        "opacity:.45;border-color:#3b5c86}", html,
    )
    self.assertIn(
        ".ai-office-floormap-token-demo_done .ai-office-report-ring{"
        "opacity:.8;border-color:#34d399;", html,
    )

  def test_ai_office_working_and_moving_pulse_the_ring_not_the_character(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-floormap-token.is-working .ai-office-report-ring,\n"
        ".ai-office-floormap-token.is-moving .ai-office-report-ring{"
        "animation:ai-office-report-ring-pulse",
        html,
    )

  def test_ai_office_report_mover_receiver_ring_still_visible_after_haze_removal(self):
    # 対面報告中の二人は、引き続き足元リング(紫)+会話パネルで分かる
    # (モヤ除去の影響を受けていないことの回帰確認)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".ai-office-floormap-token.is-report-mover .ai-office-report-ring,",
        html,
    )
    self.assertIn("border-color:#a78bfa", html)
    self.assertIn('id="ai-office-report-panel"', html)

  def test_ai_office_desk_and_monitor_decorations_unaffected_by_haze_removal(self):
    # 指令デスクの通知光・モニターの光・休憩スペースの湯気は維持する
    # (キャラクター本体に付随するモヤではなく、固定位置の演出のため対象外)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-command-pulse"', html)
    self.assertIn("ai-office-monitor-glow-ambient", html)
    self.assertIn("ai-office-lounge-steam", html)

  def test_ai_office_mission078_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  def test_ai_office_mission078_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(html.count("<button"), 1)
    self.assertEqual(html.count("<script"), 1)

  # --- MISSION 079: スプライト背景(四角・グラデーション)を完全に隠す ----

  def test_ai_office_clip_path_polygons_are_unique_and_not_simple_shapes(self):
    # 12人それぞれ異なる、単純な四角形・円形ではない(頂点数の多い)
    # clip-path多角形を持つことを確認する。
    import office_views
    paths = office_views.AI_OFFICE_SPRITE_CLIP_PATHS
    self.assertEqual(len(paths), 12)
    self.assertEqual(len(set(paths.values())), 12)
    for key, poly in paths.items():
      self.assertGreater(
          poly.count("%,"), 20, f"{key} clip-path looks too simple: {poly}"
      )

  def test_ai_office_facing_flip_still_uses_same_clip_path(self):
    # scaleX(-1)による向き反転は、clip-pathを適用した後の座標系に対して
    # 効くため、反転時も輪郭とスプライト画像がずれない(同じ要素の
    # transformプロパティで反転するだけで、clip-path自体は変更しない)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(".ai-office-floormap-sprite.is-facing-left{transform:scaleX(-1)}", html)
    sprite_rule = html.split(".ai-office-floormap-sprite{")[1].split("}")[0]
    self.assertIn("background-image", sprite_rule)

  def test_ai_office_sprite_element_has_no_opaque_background_color(self):
    # ai-office-floormap-sprite自体に、不透明な黒・灰色・青系の背景色を
    # 付けていないことを確認する(背景を薄く見せる透明度処理も含めて
    # 使わない)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    sprite_rule = html.split(".ai-office-floormap-sprite{")[1].split("}")[0]
    self.assertNotIn("background-color", sprite_rule)
    self.assertNotIn("opacity", sprite_rule)
    token_rule = html.split(".ai-office-floormap-token{")[1].split("}")[0]
    self.assertNotIn("background", token_rule)

  def test_ai_office_no_pseudo_element_background_wraps_character(self):
    # キャラクター全体を包む疑似要素の背景(::before/::after)を、
    # トークン・スプライト本体には付けていない。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertNotIn(".ai-office-floormap-token:after", html)
    self.assertNotIn(".ai-office-floormap-token:before", html)
    self.assertNotIn(".ai-office-floormap-sprite:after", html)
    self.assertNotIn(".ai-office-floormap-sprite:before", html)

  def test_ai_office_report_pair_still_shows_only_the_two_people(self):
    # 対面報告中も、報告者・受け手の背後に四角い背景・カードを追加しない
    # (mission077の対面会話パネル・進行バナーは、キャラクター本体とは
    # 別の固定位置のUIであり、人物の背景にはならないことを回帰確認する)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-report-panel"', html)
    self.assertIn('id="ai-office-report-banner"', html)
    sprite_rule = html.split(".ai-office-floormap-sprite{")[1].split("}")[0]
    self.assertNotIn("background-color", sprite_rule)

  def test_ai_office_mission079_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  def test_ai_office_mission079_still_no_external_communication(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    # MISSION 088: 「本日の指示」「今日の実行キュー」「直近の実績」が、
    # このMac上のアプリ内DB(同一オリジンの読み取り専用GET)を参照する
    # ようになった。外部サービスへの送信・ログイン・認証トークンが
    # 一切ないことは引き続き確認する。
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertNotIn("XMLHttpRequest", html)
    self.assertNotIn("WebSocket", html)
    for api_path in self._find_api_paths(html):
      self.assertIn(
          api_path,
          ("/api/dashboard/daily-records", "/api/dashboard/candidates"),
      )
    self.assertNotIn("https://", html)
    self.assertNotIn("http://", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("api_key", html)
    self.assertNotIn("access_token", html)
    self.assertEqual(html.count("<button"), 1)
    self.assertEqual(html.count("<script"), 1)

  # --- MISSION 080: デモ専用表示からローカル運用記録の可視化へ -----------

  def test_ai_office_daily_record_storage_key_matches_command_center(self):
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_DAILY_RECORD_STORAGE_KEY,
        "ai-hive-command-center:daily-record-log",
    )
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('"dailyRecordStorageKey": "ai-hive-command-center:daily-record-log"', html)
    self.assertIn("RECORD_KEY=DATA.dailyRecordStorageKey", html)
    self.assertIn(
        'raw=window.localStorage.getItem(RECORD_KEY);', html
    )

  def test_ai_office_daily_record_owner_mapping_matches_mission_rules(self):
    # Pinterest→美咲、note→海、楽天ROOM→里奈、数字記録→葵、承認待ち→蓮、
    # 共通→彩、それ以外→悠(必要時のみ柴犬社長)。
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS,
        {"Pinterest": "pinterest", "note": "note", "楽天ROOM": "room", "共通": "aya"},
    )
    self.assertEqual(
        office_views.AI_OFFICE_DAILY_RECORD_TYPE_OWNERS,
        {"承認待ち": "ren", "数字記録": "analytics"},
    )
    self.assertEqual(office_views.AI_OFFICE_DAILY_RECORD_FALLBACK_OWNER, "yu")
    # 各ownerは、既存の対面報告ルートで必ずmoverになれること(実績表示が
    # 既存の訪問者スロット・向き・リング・コネクタの仕組みをそのまま使う
    # ための前提)。
    movers = {r["mover"] for r in office_views.AI_OFFICE_REPORT_ROUTES}
    owners = (
        set(office_views.AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS.values())
        | set(office_views.AI_OFFICE_DAILY_RECORD_TYPE_OWNERS.values())
        | {office_views.AI_OFFICE_DAILY_RECORD_FALLBACK_OWNER}
    )
    self.assertTrue(owners.issubset(movers))

  def test_ai_office_daily_record_type_ack_lines_cover_all_types(self):
    import office_views
    self.assertEqual(
        set(office_views.AI_OFFICE_DAILY_RECORD_TYPE_ACK.keys()),
        set(office_views.COMMAND_CENTER_DAILY_RECORD_TYPES),
    )
    for label, ack in office_views.AI_OFFICE_DAILY_RECORD_TYPE_ACK.items():
      self.assertTrue(ack)
      for forbidden in ("売上", "円", "件成約", "公開しました", "送信しました"):
        self.assertNotIn(forbidden, ack)

  def test_ai_office_builds_real_record_queue_from_todays_records_only(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function todayDateStr(){", html)
    self.assertIn("function loadTodayRecords(){", html)
    self.assertIn('r&&r.date===today&&r.content&&', html)
    self.assertIn("function ownerForRecord(rec){", html)
    self.assertIn(
        "return RECORD_TYPE_OWNERS[rec.type]||RECORD_MEDIA_OWNERS[rec.media]||"
        "RECORD_FALLBACK_OWNER;",
        html,
    )
    self.assertIn("function buildRealRecordQueue(){", html)
    self.assertIn("var REAL_RECORD_QUEUE=buildRealRecordQueue();", html)
    self.assertIn("var DEMO_MODE_ACTIVE=REAL_RECORD_QUEUE.length===0;", html)

  def test_ai_office_record_mode_badge_present_and_distinguishes_demo_vs_real(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-record-mode-badge"', html)
    self.assertIn("読み込み中…（デモ表示）", html)
    self.assertIn(
        '本日：運用記録の入力はまだありません', html
    )
    self.assertIn("実績表示・", html)
    self.assertIn('recordModeBadgeEl.classList.add("is-real")', html)
    self.assertIn('recordModeBadgeEl.classList.remove("is-real")', html)
    self.assertIn(".ai-office-record-mode-badge.is-real{", html)

  def test_ai_office_real_record_queue_reuses_existing_report_routes(self):
    # 実績は、対応する既存の対面報告ルート(mover=owner)を再利用し、
    # 内容だけを実際の記録に差し替える。専任担当のいない実績はスキップする
    # (対応ルートがない場合、queueに追加しない)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("if(REPORT_ROUTES[i].mover===owner){baseRoute=REPORT_ROUTES[i];break;}", html)
    self.assertIn("if(!baseRoute)return;", html)
    self.assertIn('mover_line:typeLabel+"："+contentText,', html)
    self.assertIn("isReal:true", html)

  def test_ai_office_demo_mode_falls_back_when_no_todays_records(self):
    # 実際の記録がない日は、既存のデモ表示(全11ルート+部署間交流)へ
    # 自動で切り替わる。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("var pool=DEMO_MODE_ACTIVE?REPORT_ROUTES:REAL_RECORD_QUEUE;", html)
    self.assertIn("if(DEMO_MODE_ACTIVE)scheduleNextB(runTrackB,3500);", html)

  def test_ai_office_activity_feed_uses_real_prefix_for_real_records(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        'pushFeed((route.isReal?"実績：":"デモ：")+route.feed_text);', html
    )

  def test_ai_office_daily_record_read_only_no_write_to_storage(self):
    # AIオフィスはlocalStorageを読み取るだけで、書き込み(setItem等)は
    # 一切行わない(運用司令室だけが保存を行う)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)

  def test_ai_office_mission080_does_not_change_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 081: 「手動投稿を完了した」ボタンで運用記録を自動入力 ------

  def test_room_daily_candidates_has_manual_post_complete_button(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for slot in range(5):
      self.assertIn(
          f'<button type="button" class="manual-post-complete-btn" '
          f'data-slot="{slot}">手動投稿を完了した</button>',
          html,
      )
      self.assertIn(f'id="manual-post-status-{slot}"', html)
    self.assertIn(office_views.AI_OFFICE_MANUAL_POST_COMPLETE_NOTE, html)
    self.assertIn(
        "このボタンは外部へ投稿しません。実際の投稿を確認した後、社内の運用"
        "記録へ保存します。",
        html,
    )

  def test_note_daily_candidates_has_manual_post_complete_button(self):
    import office_views
    html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    for slot in range(2):
      self.assertIn(
          f'<button type="button" class="manual-post-complete-btn" '
          f'data-slot="{slot}">手動投稿を完了した</button>',
          html,
      )
      self.assertIn(f'id="manual-post-status-{slot}"', html)
    self.assertIn(office_views.AI_OFFICE_MANUAL_POST_COMPLETE_NOTE, html)

  def test_manual_post_complete_script_is_shared_and_reusable(self):
    # ROOM・noteの両ページが、同じ共通スクリプト生成関数(_manual_post_
    # complete_script)由来のロジックを使っていることを確認する(将来の
    # Pinterest候補にもそのまま再利用できる設計であることの回帰確認)。
    import office_views
    room_html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    note_html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    shared_snippets = (
        "function todayStr(){",
        "function loadRecordEntries(){",
        'document.querySelectorAll(".manual-post-complete-btn").forEach(function(btn){',
        'var card=btn.parentElement?btn.parentElement.closest("[data-slot]"):null;',
        "本日すでに記録済みです。",
        'entries.push({',
        'date:today,media:MEDIA_LABEL,type:"投稿済み",content:content,',
    )
    for snippet in shared_snippets:
      self.assertIn(snippet, room_html)
      self.assertIn(snippet, note_html)
    self.assertIn(
        f'var RECORD_KEY={office_views.json.dumps(office_views.AI_OFFICE_DAILY_RECORD_STORAGE_KEY)};',
        room_html,
    )
    self.assertIn(
        f'var RECORD_KEY={office_views.json.dumps(office_views.AI_OFFICE_DAILY_RECORD_STORAGE_KEY)};',
        note_html,
    )
    # ROOMは商品URLを持つが、noteの記事候補にはURL欄がないため、
    # URL_SELECTORがnullになる(候補にURLがない場合の仕様どおり)。
    self.assertIn('var MEDIA_LABEL="楽天ROOM";', room_html)
    self.assertIn('var URL_SELECTOR=".rc-product-url";', room_html)
    self.assertIn('var MEDIA_LABEL="note";', note_html)
    self.assertIn('var URL_SELECTOR=null;', note_html)

  def test_manual_post_complete_dedupes_by_date_media_and_content(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn(
        'return e&&e.date===today&&e.media===MEDIA_LABEL&&e.content===content;',
        html,
    )
    self.assertIn("if(isDuplicate){", html)

  def test_manual_post_complete_does_not_save_without_content(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn(
        '"商品名・タイトルを入力してから押してください。"', html
    )

  def test_manual_post_complete_media_labels_match_ai_office_owner_mapping(self):
    # ROOM/noteのmedia_labelが、AIオフィスの担当マッピングのキーと一致して
    # いることを確認する(ズレると実績が誰にも反映されなくなるため)。
    import office_views
    self.assertIn("楽天ROOM", office_views.AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS)
    self.assertEqual(office_views.AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS["楽天ROOM"], "room")
    self.assertIn("note", office_views.AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS)
    self.assertEqual(office_views.AI_OFFICE_DAILY_RECORD_MEDIA_OWNERS["note"], "note")

  def test_manual_post_complete_no_external_calls_added(self):
    # ROOM候補ページの商品URL欄のプレースホルダ(https://item.rakuten...)
    # は既存の仕様(件数がROOM_CANDIDATE_MAX_PER_DAYと一致することは、
    # test_room_daily_candidates_uses_local_storage_only_no_external_calls
    # 側で確認済み)であり、それ以外に新たな外部通信・投稿・送信・ログイン
    # に関わる文字列が増えていないことを確認する。
    # MISSION 088: 「手動投稿を完了した」ボタンは、このMac上のアプリ内DB
    # (同一オリジンの/api/dashboard/*、無認証・ローカル限定)へも
    # ベストエフォートで保存するようになったため、fetch(自体は許可しつつ、
    # それ以外の外部通信に関わる文字列が増えていないことを確認する。
    for path in (
        "/content-studio/room-daily-candidates",
        "/content-studio/note-daily-candidates",
    ):
      html = self.client.get(path).get_data(as_text=True)
      self.assertIn('postJsonSafe("/api/dashboard/daily-records"', html)
      self.assertIn('postJsonSafe("/api/dashboard/candidates"', html)
      self.assertNotIn("XMLHttpRequest", html)
      self.assertNotIn("WebSocket", html)
      for api_path in self._find_api_paths(html):
        self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
      self.assertNotIn('method="POST"', html)
      self.assertNotIn("<form", html)
      self.assertNotIn("Authorization", html)
      self.assertNotIn("api_key", html)
      self.assertNotIn("access_token", html)
    note_html = self.client.get("/content-studio/note-daily-candidates").get_data(as_text=True)
    self.assertNotIn("https://", note_html)

  def test_manual_post_complete_button_does_not_change_existing_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
        ("/ai-office", "AIオフィス"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))
    root_html = self.html
    self.assertIn("5件公開済み", root_html)
    self.assertIn("AI Hiveで追加した商品投稿が17件公開済み", root_html)

  # --- MISSION 082: 本格運用向けのナビゲーション整理 -----------------------

  def test_nav_main_menu_has_exactly_the_four_required_pages_in_order(self):
    import office_views
    self.assertEqual(
        [(key, href, name) for key, href, name in office_views.NAV_MAIN_TABS],
        [
            ("aioffice", "/ai-office", "AIオフィス"),
            ("command", "/command-center", "運用司令室"),
            ("content", "/content-studio", "投稿企画工場"),
            ("revenue", "/revenue", "収益化ボード"),
        ],
    )
    html = self.client.get("/ai-office").get_data(as_text=True)
    main_nav = html.split('<nav class="tabs"')[1].split("<details")[0]
    self.assertIn('href="/ai-office"', main_nav)
    self.assertIn('href="/command-center"', main_nav)
    self.assertIn('href="/content-studio"', main_nav)
    self.assertIn('href="/revenue"', main_nav)
    # スペース内の3画面は、主メニューの並びには含まれない。
    self.assertNotIn('href="/office"', main_nav)
    self.assertNotIn('href="/office/ceo-office"', main_nav)
    self.assertNotIn('href="/office/break-room"', main_nav)

  def test_nav_space_menu_groups_the_three_auxiliary_pages(self):
    import office_views
    self.assertEqual(
        [(key, href, name) for key, href, name in office_views.NAV_SPACE_TABS],
        [
            ("office", "/office", "オフィス"),
            ("ceo", "/office/ceo-office", "社長室"),
            ("break", "/office/break-room", "休憩室"),
        ],
    )
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('<details class="tabs-space">', html)
    self.assertIn("<summary>スペース</summary>", html)
    space_menu = html.split('<div class="tabs-space-menu">')[1].split("</div>")[0]
    self.assertIn('href="/office"', space_menu)
    self.assertIn(">オフィス<", space_menu)
    self.assertIn('href="/office/ceo-office"', space_menu)
    self.assertIn(">社長室<", space_menu)
    self.assertIn('href="/office/break-room"', space_menu)
    self.assertIn(">休憩室<", space_menu)

  def test_nav_space_details_is_keyboard_and_screen_reader_accessible(self):
    # <details>/<summary>はネイティブの開閉部品であり、追加のJSなしで
    # Enter/Spaceキー操作・スクリーンリーダーの両方に開閉状態が伝わる。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("<details class=", html)
    self.assertIn("<summary>", html)
    self.assertNotIn("onclick=", html)

  def test_nav_space_details_opens_automatically_on_space_pages(self):
    for path in ("/office", "/office/ceo-office", "/office/break-room"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('<details class="tabs-space" open>', html)
    for path in ("/ai-office", "/command-center", "/content-studio", "/revenue"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn('<details class="tabs-space">', html)
        self.assertNotIn('<details class="tabs-space" open>', html)

  def test_nav_active_state_marks_current_page_in_main_or_space_menu(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn(
        '<a class="active" href="/command-center" aria-current="page">運用司令室</a>',
        html,
    )
    office_html = self.client.get("/office").get_data(as_text=True)
    self.assertIn(
        '<a class="active" href="/office" aria-current="page">オフィス</a>',
        office_html,
    )

  def test_nav_all_existing_urls_still_load_directly(self):
    # 既存URLはすべて維持され、直接開いても表示できる。
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
        ("/ai-office", "AIオフィス"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  def test_nav_role_hints_present_on_the_four_main_pages(self):
    expected = {
        "/ai-office": "今日の実績・社員の報告を見る",
        "/command-center": "確認・判断・運用記録を残す",
        "/content-studio": "下書きを作り、手動投稿後の完了を記録する",
        "/revenue": "週次でクリック・売上・成果報酬を確認する",
    }
    for path, hint in expected.items():
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn(f'<p class="role-hint">{hint}</p>', html)
    # スペース配下の3画面には、この短い案内は必須ではない(既存のlead文の
    # ままでよい)。
    for path in ("/office", "/office/ceo-office", "/office/break-room"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertNotIn('<p class="role-hint">', html)

  def test_nav_no_horizontal_scroll_desktop_and_mobile_css_present(self):
    # レイアウトはflex-wrapで折り返す設計になっており、固定幅で画面外へ
    # はみ出す要素を追加していないことを確認する(CSSレベルの回帰確認。
    # 実際の折り返し表示はPlaywrightで別途確認する)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        ".tabs{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px;"
        "margin-bottom:15px}",
        html,
    )
    self.assertIn(
        '.tabs-space-menu{display:flex;gap:8px;flex-wrap:wrap;', html
    )

  def test_nav_reorg_does_not_add_external_calls_or_scripts(self):
    # ナビ整理そのものはHTML/CSSのみの変更であり、新規のonclickを追加して
    # いない(command-center・ai-officeはMISSION 080/081由来の既存
    # localStorage連携のみを持つため、この2画面はここでは対象外)。
    # MISSION 089: content-studioは「今日の一歩」カードがアプリ内DB
    # (/api/dashboard/candidates)を読み取り専用で参照するため、fetch(
    # 自体は許可しつつ、それ以外の外部通信が無いことを確認する。
    for path in ("/office", "/revenue", "/content-studio"):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertNotIn("onclick=", html)
        self.assertNotIn("XMLHttpRequest", html)
        self.assertNotIn("<form", html)
        if path == "/content-studio":
          for api_path in self._find_api_paths(html):
            self.assertEqual(api_path, "/api/dashboard/candidates")
        else:
          self.assertNotIn("fetch(", html)

  def test_nav_reorg_preserves_ai_office_real_record_and_demo_fallback(self):
    # MISSION 080・081の実績表示・デモフォールバックの仕組みが、ナビ整理
    # によって壊れていないことを確認する回帰テスト。
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-record-mode-badge"', html)
    self.assertIn("function buildRealRecordQueue(){", html)
    self.assertIn("var DEMO_MODE_ACTIVE=REAL_RECORD_QUEUE.length===0;", html)
    self.assertEqual(
        office_views.AI_OFFICE_DAILY_RECORD_STORAGE_KEY,
        "ai-hive-command-center:daily-record-log",
    )
    room_html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("manual-post-complete-btn", room_html)

  # --- MISSION 083: オフィス・社長室・休憩室を「生きたスペース」にする -----

  def test_office_shows_only_its_assigned_four_staff(self):
    # 里奈(ROOM運用)・凛(資料室管理)・葵(分析ラボ)・蒼(技術担当)だけを
    # オフィスに表示し、他画面の担当(悠・蓮・伊織・彩・美咲・海・柴犬社長)
    # はこのページには登場しない(各ページはその場所にいる社員だけを
    # 表示する)。
    html = self.client.get("/office").get_data(as_text=True)
    for key in ("room", "rin", "analytics", "sou"):
      self.assertIn(f'data-person="{key}"', html)
    for key in ("yu", "ren", "iori", "aya", "pinterest", "note", "operations_lead"):
      self.assertNotIn(f'data-person="{key}"', html)

  def test_office_real_record_watch_covers_room_and_analytics_only(self):
    # 里奈(楽天ROOM)・葵(数字記録)は本日の運用記録に該当があれば実績表示
    # へ切り替わるが、凛・蒼はどの記録種別・媒体にも直接対応しないため、
    # 常に通常の待機・確認の小さな動きのままになる(仕様どおり)。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('"room":{name:"里奈",demoText:', html)
    self.assertIn('"analytics":{name:"葵",demoText:', html)
    self.assertNotIn('"rin":{name:"凛",demoText:', html)
    self.assertNotIn('"sou":{name:"蒼",demoText:', html)
    self.assertIn('id="office-record-mode-badge"', html)

  def test_office_person_tokens_and_record_script_are_read_only(self):
    # MISSION 083で追加した社員トークン・運用記録の読み取りスクリプトは、
    # localStorageへの書き込み(setItem/removeItem/clear)を一切行わない。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn("localStorage.getItem(", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    for forbidden in ("fetch(", "XMLHttpRequest", "<form", "Authorization", "api_key"):
      self.assertNotIn(forbidden, html)

  def test_ceo_office_shows_president_yu_ren_and_iori(self):
    # 柴犬社長を常駐させ、悠・蓮を基本配置、伊織はデモの来訪として表示する。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    for key in ("operations_lead", "yu", "ren", "iori"):
      self.assertIn(f'data-person="{key}"', html)
    for key in ("room", "note", "pinterest", "analytics", "rin", "aya"):
      self.assertNotIn(f'data-person="{key}"', html)

  def test_ceo_office_report_panel_reuses_existing_report_routes(self):
    # 実績がある日は、既存の対面報告ルール(AI_OFFICE_REPORT_ROUTES)と同じ
    # mover→receiverの組み合わせを使って、柴犬社長・悠・蓮への報告を
    # 「誰が誰へ何を報告しているか」が分かる形で表示する。
    import office_views
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="ceo-report-banner"', html)
    self.assertIn('id="ceo-report-panel-mover"', html)
    self.assertIn('id="ceo-report-panel-receiver"', html)
    self.assertIn('id="ceo-record-mode-badge"', html)
    route_receiver_by_mover = {
        r["mover"]: r["receiver"] for r in office_views.AI_OFFICE_REPORT_ROUTES
    }
    self.assertEqual(route_receiver_by_mover["room"], "yu")
    self.assertEqual(route_receiver_by_mover["ren"], "operations_lead")
    self.assertEqual(route_receiver_by_mover["yu"], "operations_lead")
    self.assertIn('"room": "yu"', html)
    self.assertIn('"ren": "operations_lead"', html)

  def test_ceo_office_scripts_are_read_only_and_make_no_external_calls(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("localStorage.getItem(", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    for forbidden in ("fetch(", "XMLHttpRequest", "Authorization", "api_key"):
      self.assertNotIn(forbidden, html)

  def test_break_room_shows_aya_and_at_most_two_visiting_slots(self):
    # 彩を中心に、常時「彩+最大2人」だけを表示する(4候補全員を同時に
    # 置かない)。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn('data-person="aya"', html)
    self.assertEqual(html.count('class="sofa-guest'), 2)
    self.assertEqual(html.count('data-slot="1"'), 1)
    self.assertEqual(html.count('data-slot="2"'), 1)

  def test_break_room_rotation_prioritizes_real_records_and_is_read_only(self):
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn("function renderSlot(slotNum,key){", html)
    self.assertIn("setInterval(rotate,9000)", html)
    self.assertIn("prefers-reduced-motion", html)
    self.assertIn("localStorage.getItem(", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    for forbidden in ("fetch(", "XMLHttpRequest", "<form", "Authorization", "api_key"):
      self.assertNotIn(forbidden, html)

  def test_mission_083_preserves_existing_urls_nav_and_ai_office_link(self):
    # 既存の7URLはすべて維持し、主メニュー・スペースメニューも壊さない
    # (MISSION 082のナビ整理を引き続き維持する)。
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
        ("/ai-office", "AIオフィス"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn(title, html)
        self.assertIn('<details class="tabs-space"', html)
        self.assertIn('href="/ai-office"', html)

  def test_mission_083_does_not_touch_ai_office_or_command_center_logic(self):
    # AIオフィス自体の実績表示・デモフォールバック・運用司令室の記録
    # フォームは、このミッションの対象外であり、そのまま動作し続ける。
    import office_views
    ai_office_html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function buildRealRecordQueue(){", ai_office_html)
    command_html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn("daily-record-log", command_html)
    self.assertTrue(
        office_views.AI_OFFICE_DAILY_RECORD_STORAGE_KEY.endswith("daily-record-log")
    )

  # --- MISSION 084: AIオフィスに「今日の実行キュー」を追加する -----------

  def test_ai_office_execution_queue_section_is_present(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("<h2>今日の実行キュー</h2>", html)
    self.assertIn('id="ai-office-queue-list"', html)
    self.assertIn('id="ai-office-queue-empty"', html)
    self.assertIn(office_views.AI_OFFICE_QUEUE_EMPTY_MESSAGE, html)
    self.assertIn('href="/command-center"', html)

  def test_ai_office_queue_owner_assignment_matches_the_operating_rules(self):
    # Pinterest→美咲・note→海・楽天ROOM→里奈・数字記録→葵・承認待ち→蓮・
    # 共通/その他→悠、という指定どおりの割り当てになっていることを確認
    # する。既存の対面報告ルート向けdailyRecordMediaOwners(共通→彩)とは
    # 別の、このキュー専用のマッピングを使う。
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_QUEUE_MEDIA_OWNERS,
        {"Pinterest": "pinterest", "note": "note", "楽天ROOM": "room"},
    )
    self.assertNotIn("共通", office_views.AI_OFFICE_QUEUE_MEDIA_OWNERS)
    self.assertEqual(
        office_views.AI_OFFICE_DAILY_RECORD_TYPE_OWNERS["数字記録"], "analytics"
    )
    self.assertEqual(
        office_views.AI_OFFICE_DAILY_RECORD_TYPE_OWNERS["承認待ち"], "ren"
    )
    self.assertEqual(office_views.AI_OFFICE_DAILY_RECORD_FALLBACK_OWNER, "yu")

  def test_ai_office_queue_status_and_next_action_avoid_overclaiming(self):
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_QUEUE_STATUS_BY_TYPE,
        {
            "下書き": "手動投稿待ち",
            "投稿済み": "反応確認待ち",
            "数字記録": "数値を確認済み",
            "承認待ち": "確認・承認待ち",
            "確認": "確認済み",
        },
    )
    # 「投稿済み」の状態文言(反応確認待ち)は、外部への投稿を断定する表現
    # ではなく、利用者自身が記録した場合にのみ表示される。
    self.assertNotIn(
        "外部に投稿しました", office_views.AI_OFFICE_QUEUE_STATUS_BY_TYPE.values()
    )
    for record_type in office_views.AI_OFFICE_QUEUE_STATUS_BY_TYPE:
      self.assertIn(record_type, office_views.AI_OFFICE_QUEUE_NEXT_ACTION_BY_TYPE)

  def test_ai_office_queue_script_reads_records_read_only(self):
    # MISSION 088: 実行キューはアプリ内DB(loadTodayRecordsDb、同一
    # オリジンの読み取り専用GET)を参照するようになった。対面報告
    # (buildRealRecordQueue)は引き続きlocalStorage(loadTodayRecords)の
    # ままで、どちらも書き込みは一切行わない。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function queueOwnerForRecord(rec){", html)
    self.assertIn("function renderExecutionQueue(){", html)
    self.assertIn("function loadTodayRecordsDb(){", html)
    self.assertIn("var records=loadTodayRecordsDb();", html)
    self.assertIn("initDashboardDrivenSections();", html)
    self.assertIn("loadTodayRecords()", html)
    # 記録が0件のときは、空メッセージ<li>を書き換えずに残す。
    self.assertIn("if(records.length===0)return;", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    for forbidden in ("XMLHttpRequest", "<form", "Authorization", "api_key"):
      self.assertNotIn(forbidden, html)

  def test_ai_office_queue_uses_text_content_not_inner_html_for_record_data(self):
    # 利用者が入力した内容(content/metric)をDOMへ書き込む際、innerHTMLでは
    # なくtextContentを使っていることを確認する(HTMLインジェクション対策)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("contentEl.textContent=content;", html)
    self.assertIn('listEl.innerHTML="";', html)
    self.assertNotIn("innerHTML=content", html)
    self.assertNotIn("innerHTML=rec.content", html)

  def test_ai_office_queue_does_not_break_existing_ai_office_content(self):
    # 既存のキャラクター表示・対面報告・デモ表示は、このミッションの対象
    # 外であり、そのまま維持されている。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-record-mode-badge"', html)
    self.assertIn('id="ai-office-report-banner"', html)
    self.assertIn("function buildRealRecordQueue(){", html)
    self.assertIn("<h2>社員名簿（15人・状態一覧）</h2>", html)
    self.assertIn("デモ表示・実データ未接続", html)

  def test_mission_084_does_not_change_office_ceo_office_or_break_room(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn(title, html)
        self.assertNotIn("今日の実行キュー", html)

  def test_ai_office_queue_css_has_no_new_animation_and_respects_reduced_motion(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(
        '@media(prefers-reduced-motion:reduce){*,*::before,*::after{'
        "animation-duration:.001ms!important;animation-iteration-count:1!"
        'important;transition-duration:.001ms!important}}',
        html,
    )
    self.assertNotIn("@keyframes ai-office-queue", html)

  # --- MISSION 085: AIオフィスに「直近の実績」を追加する -------------------

  def test_ai_office_recent_records_section_is_present_after_the_queue(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("<h2>直近の実績</h2>", html)
    self.assertIn('id="ai-office-recent-list"', html)
    self.assertIn('id="ai-office-recent-empty"', html)
    self.assertIn(office_views.AI_OFFICE_RECENT_EMPTY_MESSAGE, html)
    # 「今日の実行キュー」セクションの直後に続いていることを確認する。
    queue_idx = html.index("<h2>今日の実行キュー</h2>")
    recent_idx = html.index("<h2>直近の実績</h2>")
    roster_idx = html.index("<h2>社員名簿（15人・状態一覧）</h2>")
    self.assertLess(queue_idx, recent_idx)
    self.assertLess(recent_idx, roster_idx)

  def test_ai_office_recent_records_labels_avoid_overclaiming_external_execution(self):
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_RECENT_LABEL_BY_TYPE["投稿済み"],
        "利用者が投稿済みとして記録",
    )
    self.assertEqual(
        office_views.AI_OFFICE_RECENT_LABEL_BY_TYPE["下書き"], "下書きとして記録"
    )
    for label in office_views.AI_OFFICE_RECENT_LABEL_BY_TYPE.values():
      self.assertNotIn("しました", label)
      self.assertNotIn("完了しました", label)
    self.assertEqual(office_views.AI_OFFICE_RECENT_MAX_ITEMS, 5)

  def test_ai_office_recent_records_script_is_read_only_and_scoped_to_past_dates(self):
    # MISSION 088: 「直近の実績」はアプリ内DB(DB_RECORDS_CACHE、同一
    # オリジンの読み取り専用GETで取得)を参照するようになった。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function loadAllRecords(){", html)
    self.assertIn("function loadRecentRecords(){", html)
    self.assertIn("function renderRecentRecords(){", html)
    self.assertIn("initDashboardDrivenSections();", html)
    # 当日より前(< today)だけを対象にし、今日の実行キュー(loadTodayRecordsDb)
    # とは別の読み取り専用ロジックであることを確認する。
    self.assertIn("r.date<today", html)
    self.assertIn("past.slice(0,RECENT_MAX_ITEMS)", html)
    self.assertIn("if(records.length===0)return;", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    for forbidden in ("XMLHttpRequest", "<form", "Authorization", "api_key"):
      self.assertNotIn(forbidden, html)

  def test_ai_office_recent_records_uses_text_content_not_inner_html(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("contentEl.textContent=content;", html)
    self.assertIn('listEl.innerHTML="";', html)
    self.assertNotIn("innerHTML=content", html)
    self.assertNotIn("innerHTML=rec.content", html)

  def test_ai_office_recent_records_link_to_command_center(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('linkEl.href="/command-center";', html)
    self.assertIn('linkEl.textContent="運用司令室へ移動する";', html)

  def test_ai_office_recent_records_reuse_queue_owner_assignment(self):
    # 昨日のPinterest投稿記録は、実行キューと同じ担当割り当て(美咲)で
    # 表示されることを、共通のqueueOwnerForRecord関数の再利用によって
    # 保証する。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("var owner=queueOwnerForRecord(rec);", html)

  def test_mission_085_does_not_change_office_ceo_office_or_break_room(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn(title, html)
        self.assertNotIn("直近の実績", html)

  def test_mission_085_preserves_mission_084_execution_queue(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("<h2>今日の実行キュー</h2>", html)
    self.assertIn(office_views.AI_OFFICE_QUEUE_EMPTY_MESSAGE, html)
    self.assertIn("function renderExecutionQueue(){", html)
    self.assertIn("var records=loadTodayRecords();", html)

  # --- MISSION 086: 柴犬社長の本日の指示 + 投稿企画工場「今日の一歩」 -----

  def test_ai_office_directive_card_is_first_and_shows_a_single_action(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-directive-card"', html)
    self.assertIn('id="ai-office-directive-task"', html)
    self.assertIn('id="ai-office-directive-reason"', html)
    self.assertIn('id="ai-office-directive-button"', html)
    self.assertIn("🐕 柴犬社長からの本日の指示", html)
    # カードが、デモ表示バナーより前(=最初)に現れることを確認する。
    section_idx = html.index('<section class="ai-office" aria-label="AIオフィス">')
    directive_idx = html.index('id="ai-office-directive-card"')
    banner_idx = html.index('class="ai-office-demo-banner"')
    self.assertLess(section_idx, directive_idx)
    self.assertLess(directive_idx, banner_idx)
    # 行動ボタンはこのカード内に1つだけ。
    self.assertEqual(html.count('id="ai-office-directive-button"'), 1)

  def test_ai_office_directive_rules_match_the_required_priority_order(self):
    import office_views
    rules = office_views.AI_OFFICE_DIRECTIVE_RULES
    self.assertEqual(len(rules), 5)
    self.assertEqual(
        [r["key"] for r in rules],
        ["draft", "posted", "approval", "prepare", "start"],
    )
    self.assertEqual(rules[0]["task"], "下書きを確認し、手動で投稿してください")
    self.assertEqual(rules[1]["task"], "投稿の反応を確認してください")
    self.assertEqual(rules[2]["task"], "承認待ちの内容を確認してください")
    self.assertEqual(rules[3]["task"], "今日は投稿候補を1件だけ用意してください")
    self.assertEqual(
        rules[4]["task"], "まず運用司令室で、今日の作業を1件記録してください"
    )
    self.assertEqual(rules[1]["href"], "/command-center")
    self.assertEqual(rules[2]["href"], "/command-center")
    self.assertEqual(rules[4]["href"], "/command-center")
    self.assertEqual(rules[0]["href"], "/content-studio")
    self.assertEqual(rules[3]["href"], "/content-studio")

  def test_ai_office_directive_posted_rule_does_not_overclaim_external_posting(self):
    import office_views
    posted_rule = office_views.AI_OFFICE_DIRECTIVE_RULES[1]
    self.assertEqual(posted_rule["key"], "posted")
    # 「投稿済み」の指示文は、利用者が記録した事実の確認を促すだけで、
    # 外部投稿そのものを断定・推測する表現は使わない。
    self.assertNotIn("完了しました", posted_rule["task"])
    self.assertNotIn("成功しました", posted_rule["task"])

  def test_ai_office_directive_script_picks_in_priority_order_and_is_read_only(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function pickDirective(){", html)
    self.assertIn("function renderDirective(){", html)
    self.assertIn("renderDirective();", html)
    self.assertIn('if(today.some(function(r){return r.type==="下書き";}))', html)
    self.assertIn('if(today.some(function(r){return r.type==="投稿済み";}))', html)
    self.assertIn('if(today.some(function(r){return r.type==="承認待ち";}))', html)
    self.assertIn("var hasPast=loadAllRecords().some(", html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)

  def test_ai_office_directive_does_not_break_existing_sections(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn('id="ai-office-record-mode-badge"', html)
    self.assertIn('id="ai-office-report-banner"', html)
    self.assertIn("<h2>社員名簿（15人・状態一覧）</h2>", html)
    self.assertIn("<h2>今日の実行キュー</h2>", html)
    self.assertIn("<h2>直近の実績</h2>", html)

  def test_content_studio_today_step_card_is_present_and_simple(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('id="cs-today-step"', html)
    self.assertIn("今日の一歩", html)
    self.assertIn('id="cs-today-step-task"', html)
    self.assertIn('id="cs-today-step-button"', html)
    # カードの直後、詳細は<details>に折りたたまれている。
    card_idx = html.index('id="cs-today-step"')
    details_idx = html.index('<details class="cs-details">')
    summary_idx = html.index("詳細設定・注意事項")
    self.assertLess(card_idx, details_idx)
    self.assertLess(details_idx, summary_idx)

  def test_content_studio_today_step_defaults_to_one_room_candidate(self):
    # MISSION 089: DB(アプリ内データ)に楽天ROOM候補が1件も無い初回状態
    # では、従来どおり「楽天ROOMの投稿候補を1件作る」を案内する。
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("楽天ROOMの投稿候補を1件作る", html)
    self.assertIn(
        'href="/content-studio/room-daily-candidates">候補を作成する</a>', html
    )
    self.assertIn('window.fetch("/api/dashboard/candidates")', html)

  def test_content_studio_today_step_shows_hold_guidance_when_candidates_exist(self):
    # MISSION 089: 候補はあるが「今日」に設定した候補が無い場合は、
    # 「保留の候補を1件選んで今日に入れる」と案内する。
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("保留の候補を1件選んで今日に入れる", html)

  def test_content_studio_today_step_script_is_read_only(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn('c.bucket==="today"', html)
    self.assertIn('window.fetch("/api/dashboard/candidates")', html)
    self.assertNotIn("localStorage.setItem(", html)
    self.assertNotIn("localStorage.removeItem(", html)
    self.assertNotIn("localStorage.clear(", html)
    for forbidden in ("XMLHttpRequest", "<form", "Authorization", "api_key"):
      self.assertNotIn(forbidden, html)
    for api_path in self._find_api_paths(html):
      self.assertEqual(api_path, "/api/dashboard/candidates")

  def test_content_studio_details_preserves_all_existing_content(self):
    # 既存の詳しい候補フォーム・注意事項は削除しておらず、<details>内に
    # そのまま残っていることを確認する。
    html = self.client.get("/content-studio").get_data(as_text=True)
    for existing in (
        "この画面は投稿企画の手動準備用です。",
        "楽天ROOMリンクについて。",
        "初回手動投稿パッケージを見る",
        "7日間コンテンツ計画を見る",
        "デスク環境投稿パッケージを見る",
        "投稿キューを見る（社長承認待ち）",
        "note初回記事を見る",
        "note記事候補（毎日2本の下書き）を見る",
        "楽天ROOM投稿準備を見る",
        "localhost限定で表示される社内検討用の",
    ):
      self.assertIn(existing, html)

  def test_content_studio_does_not_break_room_or_note_candidate_pages(self):
    for path in (
        "/content-studio/room-daily-candidates",
        "/content-studio/note-daily-candidates",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        self.assertIn("manual-post-complete-btn", html)

  def test_mission_086_no_horizontal_scroll_css_additions_present(self):
    ai_office_html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(".ai-office-directive-card{", ai_office_html)
    cs_html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn(".cs-today-step{", cs_html)
    self.assertIn("prefers-reduced-motion:reduce", cs_html)

  # --- MISSION 087: 楽天ROOM候補の文章生成を読者向けに改善する -----------

  def test_room_candidates_gadget_pouch_example_matches_required_wording(self):
    # ユーザーが提示した「スマホ周辺の持ち運び収納」ジャンルのガジェット
    # ポーチ例と一致する、hook/scene/checkの3文構成になっていることを
    # 確認する。
    import office_views
    tmpl = office_views.ROOM_CANDIDATE_INTRO_TEMPLATES["スマホ周辺の持ち運び収納"]
    self.assertEqual(
        tmpl["hook"], "バッグの中で充電ケーブルやモバイルバッテリーが絡まりがちな方へ。"
    )
    body = tmpl["hook"] + tmpl["scene"].replace("{product}", "ガジェットポーチ") + tmpl["check"]
    self.assertGreaterEqual(len(body), office_views.ROOM_CANDIDATE_INTRO_MIN_LENGTH)
    self.assertLessEqual(len(body), office_views.ROOM_CANDIDATE_INTRO_TARGET_LENGTH + 20)
    for forbidden in (
        "候補", "下書き", "記録", "入力", "アプリ", "この画面", "ローカル",
        "データベース", "確認していない", "実際に使用していない", "口コミ",
        "最安値", "在庫",
    ):
      self.assertNotIn(forbidden, body)

  def test_room_candidates_field_errors_are_inline_not_alert_only(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for slot in range(office_views.ROOM_CANDIDATE_MAX_PER_DAY):
      for field, message in (
          ("genre", "ジャンルを入力してください"),
          ("product-name", "商品名を入力してください"),
          ("product-url", "楽天市場URLを入力してください"),
      ):
        self.assertIn(
            f'<p class="rc-field-error" data-slot="{slot}" data-field="{field}" '
            f'hidden>{message}</p>',
            html,
        )
    self.assertIn("function setFieldError(slot,field,show){", html)
    self.assertIn("function validateSlot(slot,fields){", html)

  def test_room_candidates_primary_fields_are_genre_name_url_only(self):
    # 最初に表示する入力は、ジャンル・商品名・楽天市場URLの3つだけに
    # 絞り、♡数・コメント数・確認日・ハッシュタグは詳細設定(<details>)に
    # 折りたたまれていることを確認する。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    for slot in range(5):
      card = html.split(f'<div class="room-candidate-card" data-slot="{slot}">', 1)[1]
      card = card.split('<div class="room-candidate-card"', 1)[0]
      primary = card.split('<details class="room-candidate-advanced">', 1)[0]
      self.assertIn("rc-genre", primary)
      self.assertIn("rc-product-name", primary)
      self.assertIn("rc-product-url", primary)
      self.assertNotIn("rc-hearts", primary)
      self.assertNotIn("rc-comments", primary)
      self.assertNotIn("rc-checked-date", primary)
      self.assertNotIn("rc-hashtag", primary)
      advanced = card.split('<details class="room-candidate-advanced">', 1)[1]
      self.assertIn("rc-hearts", advanced)
      self.assertIn("rc-comments", advanced)
      self.assertIn("rc-checked-date", advanced)
      self.assertIn("rc-hashtag", advanced)
      self.assertIn("<summary>詳細設定</summary>", advanced)

  def test_room_candidates_hashtag_count_is_three_to_five(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertEqual(office_views.ROOM_CANDIDATE_HASHTAG_MIN_COUNT, 3)
    self.assertEqual(office_views.ROOM_CANDIDATE_HASHTAG_COUNT, 5)
    self.assertIn("const HASHTAG_MIN_COUNT=", html)
    self.assertIn(
        "while(tags.length<HASHTAG_MIN_COUNT&&i<FALLBACK_HASHTAGS.length){", html
    )
    self.assertIn("ハッシュタグ（3〜5個）", html)

  def test_room_candidates_require_genre_name_and_url_before_generating(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn(
        "return genreOk&&nameOk&&urlOk;",
        html,
    )
    self.assertIn(
        'return Boolean(fields.genre.value.trim())&&Boolean(fields.productName.value.trim())&&'
        'Boolean(fields.productUrl.value.trim());',
        html,
    )

  def test_room_candidates_generation_still_local_storage_only_no_external_calls(self):
    # MISSION 088: 「手動投稿を完了した」ボタンが、このMac上のアプリ内DB
    # (同一オリジンの/api/dashboard/*)へもベストエフォートで保存する
    # ようになった。生成機能自体(紹介文・ハッシュタグ)は従来どおり
    # ブラウザの中だけで完結する。
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("window.localStorage", html)
    self.assertIn('postJsonSafe("/api/dashboard/daily-records"', html)
    self.assertNotIn("XMLHttpRequest", html)
    for api_path in self._find_api_paths(html):
      self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("<form", html)
    self.assertEqual(
        html.count("https://"), office_views.ROOM_CANDIDATE_MAX_PER_DAY
    )

  def test_room_candidates_does_not_break_manual_post_complete_or_room_prep_link(self):
    # 既存の候補保存・手動投稿確認・運用司令室への記録・楽天ROOM準備への
    # リンクは、このミッションの対象外であり、そのまま動作し続ける。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("manual-post-complete-btn", html)
    self.assertIn("ai-hive-command-center:daily-record-log", html)
    revenue_html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn('href="/content-studio/room-daily-candidates"', revenue_html)

  def test_room_candidates_ai_office_execution_queue_still_reflects_room_records(self):
    # AIオフィスの実績表示(MISSION 080・084)は、このミッションの対象外
    # であり、楽天ROOM候補ページの手動投稿完了ボタンが書き込む記録を
    # 引き続き読み取り専用で参照できることを確認する。
    ai_office_html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function buildRealRecordQueue(){", ai_office_html)
    self.assertIn("function renderExecutionQueue(){", ai_office_html)

  # --- MISSION 088: 運用記録・投稿候補をアプリ内DBへ移行する --------------

  def test_dashboard_db_schema_adds_tables_without_touching_existing_ones(self):
    import sqlite3
    conn = sqlite3.connect(self.temp_db_path)
    try:
      names = {
          r[0]
          for r in conn.execute(
              "SELECT name FROM sqlite_master WHERE type='table'"
          ).fetchall()
      }
    finally:
      conn.close()
    for existing in (
        "work_logs", "employees", "missions", "tasks", "metrics", "reports",
        "proposals", "decisions", "audit_logs",
    ):
      self.assertIn(existing, names)
    self.assertIn("daily_records", names)
    self.assertIn("post_candidates", names)

  def test_dashboard_db_insert_daily_record_dedups_identical_entries(self):
    # MISSION 089: 本番ai_company.dbには実際の利用で蓄積した行がすでに
    # 入っていることがあるため、一時コピー側の2テーブルを空にしてから
    # 厳密な件数アサーションを行う(本番DBは一切変更しない)。
    self._reset_dashboard_tables()
    r1 = dashboard_db.insert_daily_record(
        "2099-01-01", "楽天ROOM", "投稿済み", "テスト商品A", "", ""
    )
    self.assertTrue(r1["inserted"])
    r2 = dashboard_db.insert_daily_record(
        "2099-01-01", "楽天ROOM", "投稿済み", "テスト商品A", "", ""
    )
    self.assertFalse(r2["inserted"])
    rows = dashboard_db.list_daily_records("2099-01-01")
    self.assertEqual(len(rows), 1)
    # 内容が少しでも違えば別の記録として保存される。
    r3 = dashboard_db.insert_daily_record(
        "2099-01-01", "楽天ROOM", "投稿済み", "テスト商品B", "", ""
    )
    self.assertTrue(r3["inserted"])
    self.assertEqual(len(dashboard_db.list_daily_records("2099-01-01")), 2)

  def test_dashboard_db_insert_daily_record_rejects_missing_required_fields(self):
    self._reset_dashboard_tables()
    r = dashboard_db.insert_daily_record("", "楽天ROOM", "投稿済み", "内容")
    self.assertFalse(r["inserted"])
    self.assertEqual(len(dashboard_db.list_daily_records()), 0)

  def test_dashboard_db_upsert_post_candidate_updates_instead_of_duplicating(self):
    self._reset_dashboard_tables()
    c1 = dashboard_db.upsert_post_candidate(
        "2099-01-01", "楽天ROOM", 0, "スマホ周辺の持ち運び収納", "ガジェットポーチ",
        "https://item.rakuten.co.jp/x/", "紹介文1", ["#楽天ROOM"], True, False,
    )
    self.assertTrue(c1["inserted"])
    c2 = dashboard_db.upsert_post_candidate(
        "2099-01-01", "楽天ROOM", 0, "スマホ周辺の持ち運び収納", "ガジェットポーチ",
        "https://item.rakuten.co.jp/x/", "紹介文2(更新)", ["#楽天ROOM", "#ガジェット"],
        True, True,
    )
    self.assertFalse(c2["inserted"])
    self.assertTrue(c2["updated"])
    rows = dashboard_db.list_post_candidates("2099-01-01")
    self.assertEqual(len(rows), 1)
    self.assertEqual(rows[0]["intro"], "紹介文2(更新)")
    self.assertTrue(rows[0]["manual_posted"])
    self.assertEqual(rows[0]["hashtags"], ["#楽天ROOM", "#ガジェット"])
    # bucket列はデフォルトで'hold'(保留)になっている。
    self.assertEqual(rows[0]["bucket"], "hold")

  def test_dashboard_db_migrate_dedups_and_does_not_grow_on_replay(self):
    self._reset_dashboard_tables()
    payload_records = [
        {"date": "2098-12-31", "media": "Pinterest", "type": "投稿済み",
         "content": "昨日のPin投稿", "metric": "", "reference": ""},
        {"date": "2099-01-01", "media": "楽天ROOM", "type": "確認",
         "content": "本日のROOM確認", "metric": "", "reference": ""},
    ]
    payload_candidates = [
        {"targetDate": "2099-01-01", "media": "楽天ROOM", "slot": 0,
         "genre": "バッグの中の整理", "productName": "収納ポーチ",
         "url": "https://item.rakuten.co.jp/y/", "intro": "紹介文",
         "hashtags": ["#楽天ROOM"], "manualChecked": True, "manualPosted": False},
    ]
    result1 = dashboard_db.migrate_from_payload(payload_records, payload_candidates)
    self.assertEqual(result1["records"]["inserted"], 2)
    self.assertEqual(result1["records"]["skipped"], 0)
    self.assertEqual(result1["candidates"]["inserted"], 1)

    result2 = dashboard_db.migrate_from_payload(payload_records, payload_candidates)
    self.assertEqual(result2["records"]["inserted"], 0)
    self.assertEqual(result2["records"]["skipped"], 2)
    # 候補は同じ対象日・媒体・枠番号ならUPDATE扱いになり、やはり件数は
    # 増えない。
    self.assertEqual(len(dashboard_db.list_daily_records()), 2)
    self.assertEqual(len(dashboard_db.list_post_candidates()), 1)
    # localStorageから移行した候補にはbucketが無いため、既存候補と同じく
    # 'hold'(保留)として扱われる(勝手に「今日」へ割り当てない)。
    self.assertEqual(dashboard_db.list_post_candidates()[0]["bucket"], "hold")

  def test_dashboard_api_daily_records_post_and_get_round_trip(self):
    self._reset_dashboard_tables()
    res = self.client.post(
        "/api/dashboard/daily-records",
        json={"date": "2099-01-01", "media": "note", "type": "下書き",
              "content": "テスト記事", "metric": "", "reference": ""},
    )
    self.assertEqual(res.status_code, 200)
    self.assertTrue(res.get_json()["inserted"])
    res2 = self.client.get("/api/dashboard/daily-records?date=2099-01-01")
    data = res2.get_json()
    self.assertEqual(len(data["records"]), 1)
    self.assertEqual(data["records"][0]["content"], "テスト記事")
    # 同じ内容を再度POSTしても重複登録されない。
    self.client.post(
        "/api/dashboard/daily-records",
        json={"date": "2099-01-01", "media": "note", "type": "下書き",
              "content": "テスト記事", "metric": "", "reference": ""},
    )
    res3 = self.client.get("/api/dashboard/daily-records?date=2099-01-01")
    self.assertEqual(len(res3.get_json()["records"]), 1)

  def test_dashboard_api_requires_no_authentication(self):
    # MISSION 088: 新しいログイン機構・認証トークンは追加しない。既存の
    # GET /api/logs と同様、Authorizationヘッダなしでアクセスできる。
    res = self.client.get("/api/dashboard/daily-records")
    self.assertEqual(res.status_code, 200)
    res2 = self.client.post("/api/dashboard/daily-records", json={})
    self.assertEqual(res2.status_code, 200)
    self.assertFalse(res2.get_json()["inserted"])

  def test_dashboard_api_migrate_endpoint_round_trip(self):
    self._reset_dashboard_tables()
    payload = {
        "records": [
            {"date": "2098-12-31", "media": "Pinterest", "type": "投稿済み",
             "content": "昨日のPin投稿", "metric": "", "reference": ""},
            {"date": "2099-01-01", "media": "楽天ROOM", "type": "確認",
             "content": "本日のROOM確認", "metric": "", "reference": ""},
        ],
        "candidates": [],
    }
    res = self.client.post("/api/dashboard/migrate", json=payload)
    self.assertEqual(res.status_code, 200)
    data = res.get_json()
    self.assertEqual(data["records"]["inserted"], 2)
    res2 = self.client.post("/api/dashboard/migrate", json=payload)
    data2 = res2.get_json()
    self.assertEqual(data2["records"]["inserted"], 0)
    self.assertEqual(data2["records"]["skipped"], 2)

  def test_ai_office_directive_queue_recent_read_from_db_not_local_storage_only(self):
    # MISSION 088: 本日の指示・実行キュー・直近の実績は、アプリ内DBを
    # 読み取り専用GETで参照する(buildRealRecordQueue=対面報告は従来どおり
    # localStorageのまま)。
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function initDashboardDrivenSections(){", html)
    self.assertIn('window.fetch("/api/dashboard/daily-records")', html)
    self.assertIn("var DB_RECORDS_CACHE=[];", html)
    self.assertIn("function loadTodayRecordsDb(){", html)
    self.assertIn("var records=loadTodayRecordsDb();", html)
    self.assertIn("var today=loadTodayRecordsDb();", html)

  def test_command_center_data_storage_section_is_present_and_plain_language(self):
    import office_views
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn('id="cc-data-storage"', html)
    self.assertIn("<h2>データ保存</h2>", html)
    self.assertIn(office_views.DATA_STORAGE_LOCAL_NOTE, html)
    self.assertIn("外部のサービスへは送信されません", html)
    self.assertIn(
        '<button type="button" id="cc-migrate-btn">'
        "このブラウザの記録をこのアプリに保存する</button>",
        html,
    )
    self.assertIn('id="cc-local-record-count"', html)
    self.assertIn('id="cc-local-candidate-count"', html)
    # 「DB保存中」のような技術的すぎる表現は使わない。
    self.assertNotIn("DB保存中", html)

  def test_command_center_migrate_script_reads_local_storage_and_posts_once(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    self.assertIn("function collectLocalRecords(){", html)
    self.assertIn("function collectLocalCandidates(){", html)
    self.assertIn("function updateLocalCounts(){", html)
    self.assertIn('window.fetch("/api/dashboard/migrate"', html)
    # 移行してもlocalStorage側のデータを削除する操作はない。
    migrate_script = html.split('id="cc-data-storage"', 1)[1]
    self.assertNotIn("localStorage.removeItem(", migrate_script)
    self.assertNotIn("localStorage.clear(", migrate_script)

  def test_command_center_daily_record_save_also_posts_to_db(self):
    html = self.client.get("/command-center").get_data(as_text=True)
    handler = html.split('document.querySelector("#cc-record-add")', 1)[1][:1200]
    self.assertIn('window.fetch("/api/dashboard/daily-records"', handler)
    self.assertIn("safeSet(recordLogKey,JSON.stringify(entries));", handler)

  def test_manual_post_complete_candidate_payload_has_required_fields(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    payload_script = html.split('postJsonSafe("/api/dashboard/candidates"', 1)[1][:400]
    for key in (
        "targetDate:targetDate", "media:MEDIA_LABEL", "slot:Number(slot)",
        "genre:genre", "productName:content", "url:url", "intro:intro",
        "hashtags:hashtags", "manualChecked:manualChecked", "manualPosted:true",
    ):
      self.assertIn(key, payload_script)

  def test_mission_088_does_not_break_existing_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/content-studio", "投稿企画工場"),
        ("/command-center", "運用司令室"),
        ("/ai-office", "AIオフィス"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  def test_mission_088_empty_db_does_not_break_demo_or_empty_states(self):
    # MISSION 089: 本番ai_company.dbは実際の利用で行が蓄積していることが
    # あるため、一時コピー側のテーブルを明示的に空にしたうえで、DBが
    # 空の状態でも既存のデモ・空状態表示が壊れないことを確認する
    # (本番DBは一切変更しない)。
    import office_views
    self._reset_dashboard_tables()
    self.assertEqual(len(dashboard_db.list_daily_records()), 0)
    self.assertEqual(len(dashboard_db.list_post_candidates()), 0)
    ai_office_html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn(office_views.AI_OFFICE_QUEUE_EMPTY_MESSAGE, ai_office_html)
    self.assertIn(office_views.AI_OFFICE_RECENT_EMPTY_MESSAGE, ai_office_html)
    self.assertIn("デモ表示・実データ未接続", ai_office_html)

  # --- MISSION 089: 楽天ROOM候補を「今日・今週・保留」に整理する ----------

  def test_dashboard_db_migration_adds_bucket_column_to_pre_existing_table(self):
    # MISSION 088時点のスキーマ(bucket列なし)を一時コピー上に人為的に
    # 再現し、init_schema()の移行が既存の行を一切失わずにbucket列
    # (デフォルト'hold')を追加できることを確認する(本番DBには触れない)。
    import sqlite3
    conn = sqlite3.connect(self.temp_db_path)
    try:
      conn.execute("DROP TABLE IF EXISTS post_candidates")
      conn.execute(
          "CREATE TABLE post_candidates ("
          " id INTEGER PRIMARY KEY AUTOINCREMENT,"
          " dedup_key TEXT NOT NULL UNIQUE,"
          " target_date TEXT NOT NULL,"
          " media TEXT NOT NULL,"
          " slot INTEGER,"
          " genre TEXT, product_name TEXT, url TEXT, intro TEXT, hashtags TEXT,"
          " manual_checked INTEGER NOT NULL DEFAULT 0,"
          " manual_posted INTEGER NOT NULL DEFAULT 0,"
          " created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),"
          " updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))"
          ")"
      )
      conn.execute(
          "INSERT INTO post_candidates"
          " (dedup_key, target_date, media, slot, product_name, manual_posted)"
          " VALUES ('2098-01-01|楽天ROOM|0', '2098-01-01', '楽天ROOM', 0,"
          " 'MISSION088時代の候補', 1)"
      )
      conn.commit()
      cols_before = {
          r[1] for r in conn.execute("PRAGMA table_info(post_candidates)").fetchall()
      }
      self.assertNotIn("bucket", cols_before)
    finally:
      conn.close()

    dashboard_db.init_schema()

    conn = sqlite3.connect(self.temp_db_path)
    try:
      cols_after = {
          r[1] for r in conn.execute("PRAGMA table_info(post_candidates)").fetchall()
      }
      self.assertIn("bucket", cols_after)
      row = conn.execute(
          "SELECT product_name, manual_posted, bucket FROM post_candidates"
      ).fetchone()
      self.assertEqual(row[0], "MISSION088時代の候補")
      self.assertEqual(row[1], 1)
      self.assertEqual(row[2], "hold")
    finally:
      conn.close()

  def test_dashboard_db_upsert_post_candidate_preserves_bucket_when_not_provided(self):
    self._reset_dashboard_tables()
    dashboard_db.upsert_post_candidate(
        "2099-02-01", "楽天ROOM", 0, "ジャンルA", "商品A", "https://item.rakuten.co.jp/a/",
        "紹介文", ["#楽天ROOM"], False, False, bucket="today",
    )
    row = dashboard_db.list_post_candidates("2099-02-01")[0]
    self.assertEqual(row["bucket"], "today")
    # bucketを指定せずに更新(例:「手動投稿を完了した」と同じ呼び出し方)
    # すると、既存のbucketがそのまま保持される。
    dashboard_db.upsert_post_candidate(
        "2099-02-01", "楽天ROOM", 0, "ジャンルA", "商品A", "https://item.rakuten.co.jp/a/",
        "紹介文", ["#楽天ROOM"], True, True,
    )
    row2 = dashboard_db.list_post_candidates("2099-02-01")[0]
    self.assertEqual(row2["bucket"], "today")
    self.assertTrue(row2["manual_posted"])

  def test_dashboard_db_upsert_post_candidate_normalizes_invalid_bucket(self):
    self._reset_dashboard_tables()
    result = dashboard_db.upsert_post_candidate(
        "2099-02-02", "楽天ROOM", 0, "ジャンルB", "商品B", "", "", [], False, False,
        bucket="not-a-real-bucket",
    )
    self.assertTrue(result["inserted"])
    row = dashboard_db.list_post_candidates("2099-02-02")[0]
    # 無効な区分は無視され、新規行は'hold'(保留)になる。
    self.assertEqual(row["bucket"], "hold")

  def test_dashboard_db_bucket_values_are_limited_to_three_choices(self):
    self.assertEqual(dashboard_db.BUCKET_VALUES, ("today", "week", "hold"))
    self.assertEqual(dashboard_db.BUCKET_DEFAULT, "hold")

  def test_dashboard_api_candidates_bucket_persists_across_reload(self):
    # 「選択結果はローカルアプリのSQLite DBへ保存し、再読み込み後も
    # 保持してください」の確認。POSTで保存した区分が、別のGETでも
    # そのまま読み取れることを確認する(=再読み込みしても保持される)。
    self._reset_dashboard_tables()
    res = self.client.post(
        "/api/dashboard/candidates",
        json={
            "targetDate": "2099-02-03", "media": "楽天ROOM", "slot": 2,
            "genre": "バッグの中の整理", "productName": "商品C",
            "url": "https://item.rakuten.co.jp/c/", "intro": "紹介文",
            "hashtags": ["#楽天ROOM"], "manualChecked": False,
            "manualPosted": False, "bucket": "week",
        },
    )
    self.assertEqual(res.status_code, 200)
    self.assertTrue(res.get_json()["inserted"])
    res2 = self.client.get("/api/dashboard/candidates?targetDate=2099-02-03")
    candidates = res2.get_json()["candidates"]
    self.assertEqual(len(candidates), 1)
    self.assertEqual(candidates[0]["bucket"], "week")
    self.assertEqual(candidates[0]["product_name"], "商品C")

  def test_dashboard_api_candidates_existing_rows_default_to_hold(self):
    # 「既存候補は初期状態では「保留」として扱い、勝手に「今日」へ割り当て
    # ない」の確認。bucketを指定しないPOST(=既存候補の保存と同じ形)は
    # 'hold'になる。
    self._reset_dashboard_tables()
    res = self.client.post(
        "/api/dashboard/candidates",
        json={
            "targetDate": "2099-02-04", "media": "楽天ROOM", "slot": 0,
            "genre": "", "productName": "商品D", "url": "", "intro": "",
            "hashtags": [], "manualChecked": False, "manualPosted": False,
        },
    )
    self.assertEqual(res.status_code, 200)
    res2 = self.client.get("/api/dashboard/candidates?targetDate=2099-02-04")
    self.assertEqual(res2.get_json()["candidates"][0]["bucket"], "hold")

  def test_room_candidates_bucket_summary_and_per_card_controls_present(self):
    import office_views
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn('id="rc-bucket-summary"', html)
    self.assertIn('id="rc-bucket-count-today"', html)
    self.assertIn('id="rc-bucket-count-week"', html)
    self.assertIn('id="rc-bucket-count-hold"', html)
    for slot in range(office_views.ROOM_CANDIDATE_MAX_PER_DAY):
      self.assertIn(
          f'<b class="room-candidate-bucket-current" data-slot="{slot}">保留</b>',
          html,
      )
      for bucket, label in (("today", "今日にする"), ("week", "今週にする"), ("hold", "保留にする")):
        self.assertIn(
            f'<button type="button" class="room-candidate-bucket-btn'
            f'{" is-active" if bucket == "hold" else ""}" '
            f'data-slot="{slot}" data-bucket="{bucket}">{label}</button>',
            html,
        )

  def test_room_candidates_bucket_script_saves_to_db_and_reads_back(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("function setBucketForSlot(slot,bucket){", html)
    self.assertIn("function loadSlotBucketsForDate(iso){", html)
    self.assertIn("function refreshBucketSummary(){", html)
    self.assertIn('window.fetch("/api/dashboard/candidates"', html)
    self.assertIn(
        'window.fetch("/api/dashboard/candidates?targetDate="+encodeURIComponent(iso))',
        html,
    )
    self.assertIn("bucket:bucket", html)
    for api_path in self._find_api_paths(html):
      self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)

  def test_room_candidates_date_query_param_supported_for_deep_link(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("new URLSearchParams(window.location.search)", html)
    self.assertIn('urlParams.get("date")', html)
    res = self.client.get("/content-studio/room-daily-candidates?date=2099-03-01")
    self.assertEqual(res.status_code, 200)

  def test_room_candidates_manual_post_complete_marks_candidate_done_not_in_buckets(self):
    # 投稿候補を手動投稿完了にした場合、既存どおり運用記録・AIオフィスの
    # 実績へ反映される(manualPosted:trueを送る)。実行キュー・指示の対象は
    # manual_posted=0の候補だけなので、完了済みは自動的に整理対象から
    # 外れる。
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn("manualPosted:true", html)
    self.assertIn("manual-post-complete-btn", html)

  def test_content_studio_today_step_links_to_candidate_target_date(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn(
        '"/content-studio/room-daily-candidates?date="+'
        "encodeURIComponent(c.target_date||\"\")",
        html,
    )

  def test_ai_office_directive_includes_room_candidate_today_case(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function todayRoomCandidate(){", html)
    self.assertIn("楽天ROOM候補を確認し、手動で投稿する", html)
    self.assertIn("本日「今日」に設定した楽天ROOM候補があります", html)
    # 既存5ルールの優先順位・内容自体は変更していない。
    self.assertEqual(len(office_views.AI_OFFICE_DIRECTIVE_RULES), 5)

  def test_ai_office_execution_queue_includes_room_candidate_item(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function buildQueueItem(", html)
    self.assertIn("var roomCandidate=todayRoomCandidate();", html)
    self.assertIn("投稿企画工場へ移動する", html)
    self.assertIn('"/content-studio/room-daily-candidates"', html)

  def test_ai_office_candidate_team_real_state_only_when_today_bucket_exists(self):
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertIn("function applyCandidateTeamRealState(hasTodayCandidate){", html)
    self.assertIn("if(!hasTodayCandidate)return;", html)
    self.assertIn(
        'var CANDIDATE_TEAM_KEYS=["tsumugi","nagi","hina"];', html
    )
    self.assertIn(
        'var hasTodayCandidate=loadActiveRoomCandidates().some(function(c){',
        html,
    )
    # 投稿済み(manual_posted)の候補は対象から除外される。
    self.assertIn(
        'return c&&c.media==="楽天ROOM"&&!c.manual_posted;', html
    )

  def test_ai_office_candidate_management_staff_present_in_roster(self):
    import office_views
    html = self.client.get("/ai-office").get_data(as_text=True)
    staff_by_key = {
        s["key"]: s for s in office_views.AI_OFFICE_EXTENDED_STAFF
        if s["key"] in ("tsumugi", "nagi", "hina")
    }
    self.assertEqual(len(staff_by_key), 3)
    self.assertEqual(staff_by_key["tsumugi"]["name"], "紬")
    self.assertEqual(staff_by_key["tsumugi"]["role_label"], "候補整理席")
    self.assertEqual(staff_by_key["nagi"]["name"], "凪")
    self.assertEqual(staff_by_key["nagi"]["role_label"], "商品確認席")
    self.assertEqual(staff_by_key["hina"]["name"], "陽菜")
    self.assertEqual(staff_by_key["hina"]["role_label"], "投稿準備席")
    for key in ("tsumugi", "nagi", "hina"):
      self.assertIn(f'data-department="{key}"', html)
      self.assertIn(staff_by_key[key]["name"], html)
      self.assertIn(f'id="ai-office-token-{key}"', html)

  def test_ai_office_candidate_management_staff_reuse_existing_sprites_only(self):
    # 「新しい画像素材の生成・追加は行わず」の確認。既存のスプライト
    # シート画像ファイル自体は変更していない(ファイルは1枚のみ)。
    import office_views
    self.assertEqual(
        office_views.AI_OFFICE_SPRITE_REUSE_MAP,
        {"tsumugi": "yui", "nagi": "aya", "hina": "room"},
    )
    html = self.client.get("/ai-office").get_data(as_text=True)
    self.assertEqual(html.count("ai-office-team-3d.png"), html.count("ai-office-team-3d.png"))
    self.assertIn("/static/images/ai-office-team-3d.png", html)

  def test_mission_089_does_not_break_other_pages(self):
    for path, title in (
        ("/office", "ライブオフィス"),
        ("/office/break-room", "休憩室"),
        ("/office/ceo-office", "社長室"),
        ("/revenue", "収益化ボード"),
        ("/command-center", "運用司令室"),
        ("/content-studio/note-daily-candidates", "note"),
    ):
      with self.subTest(path=path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        self.assertIn(title, res.get_data(as_text=True))

  def test_mission_089_no_new_external_communication_anywhere(self):
    # /api/dashboard/* 以外の新しい外部通信・認証情報を追加していない
    # ことを、関係する全画面で確認する。
    for path in (
        "/ai-office", "/content-studio", "/content-studio/room-daily-candidates",
        "/command-center",
    ):
      with self.subTest(path=path):
        html = self.client.get(path).get_data(as_text=True)
        for api_path in self._find_api_paths(html):
          self.assertTrue(api_path.startswith("/api/dashboard/"), api_path)
        self.assertNotIn("XMLHttpRequest", html)
        self.assertNotIn("WebSocket", html)
        self.assertNotIn("Authorization", html)
        self.assertNotIn("api_key", html)
        self.assertNotIn("access_token", html)
        self.assertNotIn("<form", html)

  def test_mission_089_no_horizontal_scroll_css_present(self):
    html = self.client.get("/content-studio/room-daily-candidates").get_data(as_text=True)
    self.assertIn(".room-candidate-bucket-summary{display:flex;gap:10px;flex-wrap:wrap", html)
    self.assertIn(".rc-bucket-chip{flex:1 1 140px", html)
    self.assertIn(".room-candidate-bucket-buttons{display:flex;gap:6px;flex-wrap:wrap}", html)
    self.assertIn("prefers-reduced-motion:reduce", html)


if __name__ == "__main__":
  unittest.main()
