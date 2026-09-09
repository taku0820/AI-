"""ダッシュボード画面(GET /)のデザイン刷新（MISSION 024）の表示内容テスト。

Flaskのテストクライアントで `GET /` のレスポンスHTMLを取得し、実際の
ブラウザ描画・CSSアニメーションの見た目そのものは検証しない（それは
別途ヘッドレスブラウザでの目視確認で行った）。ここで機械的に確認するのは、
- 既存ツール(hive_status.py等)が参照しているマーカー文字列が保たれているか
- 外部リソース(外部画像・外部フォント・CDN・外部JS・外部URL)が
  一切含まれていないか
- prefers-reduced-motion に対応したCSSが含まれているか
- プロジェクト内のミニフィギュア画像が8名分描画されているか
- 既存の /api/logs 連携用の要素・スクリプトが維持されているか
- レスポンシブ対応のメディアクエリが含まれているか
といった、安全要件・アクセシビリティ要件・既存機能の維持に関わる点のみ。

本番の `ai_company.db` を汚さないよう、一時コピーに対してテストを実行する
(test_hive_api.pyと同じ方針)。

実行方法: venv/bin/python test_dashboard_design.py
"""

import os
import re
import shutil
import tempfile
import unittest

import app as app_module

PROJECT_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_company.db")


class DashboardDesignTestCase(unittest.TestCase):

  def setUp(self):
    fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy(PROJECT_DB_PATH, self.temp_db_path)

    self._orig_db_name = app_module.DB_NAME
    app_module.DB_NAME = self.temp_db_path

    app_module.app.testing = True
    self.client = app_module.app.test_client()

    res = self.client.get("/")
    self.assertEqual(res.status_code, 200)
    self.html = res.get_data(as_text=True)

  def tearDown(self):
    app_module.DB_NAME = self._orig_db_name
    os.remove(self.temp_db_path)

  # --- 既存機能・既存ツールとの互換性 ------------------------------------------

  def test_required_marker_text_is_preserved(self):
    # hive_status.check_root_page() および test_hive_api.py が参照する
    # マーカー文字列。これが失われると既存のヘルスチェックCLIが誤検知する。
    self.assertIn("会社の全体像ダッシュボード", self.html)

  def test_logs_api_endpoint_still_exists_though_root_page_no_longer_uses_it(self):
    # MISSION 038でトップページの「現在の作業」カード(/api/logsから最新の
    # 作業ログを表示していた箇所)を削除したため、トップページ自体は
    # /api/logsを呼び出さなくなった。エンドポイント自体は/officeなど他の
    # 画面が読み取り専用で使い続けているため、削除していない。
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

  def test_root_dashboard_shows_only_the_four_required_channels(self):
    for channel in ("Pinterest", "楽天ROOM", "note", "コンテンツスタジオ"):
      self.assertIn(channel, self.html)
    self.assertEqual(self.html.count('class="badge-manual"'), 4)
    self.assertEqual(self.html.count("現在の役割："), 4)
    self.assertEqual(self.html.count("次の行動："), 4)

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
    self.assertIn("柴犬社長", self.html)
    self.assertIn(
        "Pinterest・楽天ROOM・note・投稿づくりは、すべて社長が手動で担当しています。",
        self.html,
    )
    self.assertIn("自動投稿・自動集計・外部サービスとの自動連携は行っていません。", self.html)

  def test_root_dashboard_office_page_still_has_its_own_fictional_desk_characters(self):
    # /officeの「ライブオフィス」表示は、このミッションの対象外であり、
    # 既存の演出用デスクキャラクター(琴衣・蒼・美咲・海・湊・伊藤)は
    # そのまま残っていることを確認する(トップページからの削除が、他画面を
    # 壊していないことの回帰確認)。
    office_html = self.client.get("/office").get_data(as_text=True)
    for name in ("琴衣", "蒼", "美咲", "海", "湊", "伊藤"):
      self.assertIn(name, office_html)

  # --- MISSION 038.1: 4カードの現状表示を実際の運用状況へ合わせる更新 -----------

  def test_root_dashboard_cards_reflect_current_actual_status(self):
    for role, next_action in (
        (
            "現在の役割：公開済みピンの反応を手動で確認し、次の投稿を準備する。",
            "次の行動：<b>投稿キューの内容を確認し、社長が手動でPinterestへ"
            "投稿・分析確認を行う。</b>",
        ),
        (
            "現在の役割：公開済みの商品投稿を確認し、次に紹介する候補を整理する。",
            "次の行動：<b>投稿間隔を空けながら、社長が手動で商品を整理・投稿する。</b>",
        ),
        (
            "現在の役割：初回記事を公開済み。表示と反応を手動で確認する。",
            "次の行動：<b>公開済み記事の表示と反応を確認し、次の記事を準備する。</b>",
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

  def test_work_floor_reads_existing_logs_only(self):
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="office-live-status"', html)
    self.assertIn('fetch("/api/logs")', html)
    self.assertNotIn('fetch("/api/employees")', html)
    self.assertNotIn('method="POST"', html)

  # --- MISSION 025: 役割別ライブオフィス連携(実データ表示) --------------------

  def test_fixed_desk_avatars_have_status_elements_for_real_data(self):
    # 固定アバター(琴衣・蒼・美咲・海・湊・伊藤)それぞれのデスクに、
    # 実データで更新される担当状況テキストと状態チップが用意されている。
    html = self.client.get("/office").get_data(as_text=True)
    for key in ("misaki", "umi", "minato", "ito", "kotoe", "aoi"):
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

  def test_desk_status_reflects_completed_vs_in_progress_logs(self):
    # 実データ(work_logs)の"完了"ステータスはstatus-done、それ以外(進行中等)
    # はstatus-progressへ安全に切り替わるロジックが含まれていることを、
    # レスポンスHTML中のスクリプト文字列で確認する(実際のDOM挙動そのものは
    # ヘッドレスブラウザでの目視確認で別途行った)。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('log[4]==="完了"', html)
    self.assertIn('done?"status-done":"status-progress"', html)

  def test_ceo_office_shows_today_and_total_task_counts_from_real_logs(self):
    # 社長室に「今日の最新タスク数・完了数」を実データ(work_logs)から
    # 表示する。書き込みは一切行わない。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="ceo-today-count"', html)
    self.assertIn('id="ceo-today-done"', html)
    self.assertIn('id="ceo-total-note"', html)
    self.assertIn('fetch("/api/logs")', html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/tasks", html)

  def test_ceo_office_and_desk_scripts_have_graceful_fallback_on_fetch_failure(self):
    # 作業ログの取得に失敗しても、例外を投げずに安全な表示へ切り替わる
    # (catch節が存在する)ことを確認する。
    office_html = self.client.get("/office").get_data(as_text=True)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn(".catch(()=>{", office_html)
    self.assertIn(".catch(()=>{", ceo_html)

  # --- MISSION 026: 社長室(業務司令室)への拡張 --------------------------------

  def test_ceo_office_shows_today_progress_count_in_addition_to_done(self):
    # 「今日の作業件数・完了件数・進行中件数」の3つがすべて表示される。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="ceo-today-count"', html)
    self.assertIn('id="ceo-today-done"', html)
    self.assertIn('id="ceo-today-progress"', html)
    self.assertIn("今日の作業", html)
    self.assertIn("完了", html)
    self.assertIn("進行中", html)

  def test_ceo_office_shows_up_to_three_recent_items(self):
    # 最新の仕事を最大3件表示する一覧が存在し、slice(0,3)で件数を
    # 制限していることをスクリプト内容で確認する。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="ceo-recent-list"', html)
    self.assertIn("最新の仕事", html)
    self.assertIn("logs.slice(0,3)", html)

  def test_ceo_office_shows_priority_derived_from_real_data(self):
    # 「いま優先すること」は、実データのうち未完了(進行中)の最新項目から
    # 導出される(該当が無ければ安全なフォールバック文言になる)。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="ceo-priority"', html)
    self.assertIn("いま優先すること", html)
    self.assertIn("logs.find(l=>!isDone(l))", html)
    self.assertIn("すべて完了しています", html)

  def test_ceo_office_and_office_desks_use_identical_completion_rule(self):
    # 社長室とライブオフィスの各デスクが、"完了"以外はすべて"進行中"として
    # 扱うという同一の判定基準を使っていることを確認する(表示の整合性)。
    office_html = self.client.get("/office").get_data(as_text=True)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('log[4]==="完了"', office_html)
    self.assertIn('l[4]==="完了"', ceo_html)

  def test_ceo_office_command_center_reads_only_logs_and_never_writes(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_ceo_office_command_center_has_fallback_text_for_all_new_fields(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn(
        'document.querySelector("#ceo-today-progress").textContent="―"', html
    )
    self.assertIn(
        '"<li>作業ログを取得できませんでした。</li>"', html
    )
    self.assertIn(
        'document.querySelector("#ceo-priority").textContent='
        '"作業ログを取得できませんでした。"',
        html,
    )

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

  def test_quick_action_buttons_use_only_existing_logs_api(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('fetch("/api/logs")', html)
    self.assertIn("qaWithLogs", html)
    self.assertNotIn("/api/employees", html)
    self.assertNotIn("/api/missions", html)
    self.assertNotIn("/api/tasks", html)
    self.assertNotIn("/api/audit-logs", html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("Authorization", html)
    self.assertNotIn("AI_HIVE_", html)

  def test_quick_action_handlers_append_to_chat_log_with_fallback(self):
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("qaAppendBoss", html)
    self.assertIn('document.querySelector("#log")', html)
    self.assertIn(
        '"🐕 柴犬社長：作業ログを取得できませんでした。"', html
    )

  # --- MISSION 028: デスク詳細と案内(クリック・キーボード操作対応) --------------

  def test_desks_are_keyboard_and_click_operable_buttons(self):
    # <button>はEnter/Space/クリックのいずれでも標準で活性化するため、
    # 各デスクを<button>にしていることでキーボード操作対応も満たす。
    html = self.client.get("/office").get_data(as_text=True)
    for key in ("misaki", "umi", "minato", "ito", "kotoe", "aoi"):
      self.assertIn(f'id="desk-{key}"', html)
      self.assertIn(f'data-key="{key}"', html)
    self.assertEqual(html.count('<button type="button" class="desk d'), 6)
    self.assertIn('aria-haspopup="true"', html)
    self.assertIn('aria-expanded="false"', html)
    self.assertIn('aria-controls="desk-detail-panel"', html)

  def test_desk_detail_panel_has_required_fields_and_is_hidden_initially(self):
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="desk-detail-panel"', html)
    self.assertIn('id="desk-detail-panel" role="region"', html)
    self.assertIn("hidden>", html)  # 初期状態は非表示
    self.assertIn('id="desk-detail-title"', html)  # AI名
    self.assertIn('id="desk-detail-role"', html)  # 役割
    self.assertIn('id="desk-detail-status"', html)  # 現在の状態
    self.assertIn('id="desk-detail-task"', html)  # 最新の作業内容
    self.assertIn('id="desk-detail-time"', html)  # 更新時刻

  def test_desk_detail_disclaimer_is_honest_about_no_individual_assignment(self):
    # 実データにAI個別の担当情報が存在しないことを、断定せず誠実に示す。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="desk-detail-disclaimer"', html)
    self.assertIn("個別の担当データは存在しない", html)
    self.assertIn("既存の作業ログを順番に表示している演出", html)
    self.assertIn("実際にこのAIが個人で担当した", html)

  def test_desk_detail_close_and_escape_are_supported(self):
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('id="desk-detail-close"', html)
    self.assertIn("closeDeskDetail", html)
    self.assertIn('e.key==="Escape"', html)
    # 閉じた後、直前にフォーカスしていたデスクへフォーカスを戻す。
    self.assertIn("lastFocusedDesk.focus()", html)

  def test_desk_click_and_detail_scripts_use_only_existing_logs_api(self):
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn('fetch("/api/logs")', html)
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

  def test_ceo_office_link_points_to_desk_hash_dynamically(self):
    # 既定はプレーンな/officeへのリンクだが(JS未実行/フェッチ失敗時の
    # フォールバック)、実データが取得できれば「いま優先すること」に
    # 対応するデスクの#desk-<key>へ、通常のhref書き換えのみで更新される。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('id="qa-office" href="/office"', html)
    self.assertIn('setAttribute("href","/office#desk-"+targetKey)', html)
    self.assertIn(
        'const deskKeys=["misaki","umi","minato","ito","kotoe","aoi"];', html
    )
    self.assertNotIn("location.href", html)

  def test_desk_order_is_identical_between_office_and_ceo_office(self):
    # 社長室のdeskKeysとオフィスのdesksタプルの並び順が一致していることを
    # 確認する(ログのローテーション割り当てが両画面で食い違わないため)。
    office_html = self.client.get("/office").get_data(as_text=True)
    ceo_html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn(
        'const keys=["misaki","umi","minato","ito","kotoe","aoi"];', office_html
    )
    self.assertIn(
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
    html = self.client.get("/office").get_data(as_text=True)
    for role in ("WEBディレクター", "UIデザイナー", "フロントエンド", "QA・SEO", "運用チーム"):
      self.assertIn(role, html)

  def test_break_room_reason_and_return_plan_marked_as_not_real_data(self):
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn("休憩理由・戻る予定はすべて画面演出であり", html)
    self.assertIn("実データに基づくものではありません", html)

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
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("事業の目的", html)
    self.assertIn("投稿企画工場のテーマを軸に発信し", html)
    self.assertIn("想定するお客さま像", html)
    self.assertIn("AI初心者、仕事の効率化に関心がある人", html)
    self.assertIn("収益化の柱（案）", html)
    self.assertIn("投稿企画工場のテーマに沿った発信", html)
    self.assertIn("初回Pinterest投稿からの流入育成", html)
    self.assertIn("楽天ROOMでの手動カテゴリ紹介", html)
    self.assertIn("ROOM登録までの段階", html)
    for stage in ("テーマ選定", "投稿確認", "ROOM準備", "手動登録"):
      self.assertIn(stage, html)
    self.assertIn("今週の優先行動", html)
    self.assertIn("投稿企画工場のテーマ整理", html)
    self.assertIn("初回Pinterest投稿の実績確認", html)
    self.assertIn("ROOM投稿準備の下ごしらえ", html)

  def test_revenue_board_price_is_an_explicit_draft_not_final(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("収益の入り口候補（すべて未定・検討中）", html)
    self.assertIn("未確定", html)
    self.assertIn("確定した収益・契約内容ではありません", html)
    self.assertIn("検討中", html)
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
    self.assertEqual(html.count('class="cs-plan-card"'), 2)

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
    html = self.client.get("/content-studio").get_data(as_text=True)
    for removed in (
        "投稿改善ワークフロー", "投稿候補", "要確認", "見送り",
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
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertNotIn("http://", html)
    self.assertNotIn("https://", html)
    self.assertNotIn("<script", html)
    self.assertNotIn("fetch(", html)
    self.assertIn("prefers-reduced-motion:reduce", html)

  def test_content_studio_is_fully_read_only_no_api_or_write_methods(self):
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertNotIn("/api/", html)
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
    )
    self.assertIn(office_views.CONTENT_STUDIO_THEME, rendered)

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

  def test_first_post_shows_threads_draft(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("Threads投稿案（同テーマ）", html)
    self.assertIn('id="fp-threads"', html)
    self.assertIn("AIって結局なにに使えばいいの？", html)

  def test_first_post_states_manual_posting_and_next_automation_step(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertIn("柴犬社長がPinterestで手動投稿してください", html)
    self.assertIn("実際のURLや", html)
    self.assertIn("反応（保存数・クリック数など）を確認したうえで", html)
    self.assertIn("次にどこまで自動化するかを", html)
    self.assertIn("自動投稿・自動連携は行いません", html)

  def test_first_post_copy_buttons_fail_safely_without_breaking_page(self):
    html = self.client.get("/content-studio/first-post").get_data(as_text=True)
    self.assertEqual(html.count('class="fp-copy-btn"'), 4)  # title/description/alt/threads
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
    self.assertIn("Threads投稿案（同テーマ）", html)
    self.assertIn('id="fp-threads"', html)

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
    # 既存の投稿企画(初回投稿テーマ + 過去に検討したテーマ4件)だけを使って
    # おり、新しいテーマ名を発明していないことを確認する。WEEKLY_PLANは
    # office_views.py内で独立して定義されたデータであり、MISSION 040で
    # /content-studioの表示テーマを2件に絞った後も、このデータ自体は
    # 変更していない(過去に検討されたテーマの記録として、この画面には
    # 引き続き表示され続ける)。
    import office_views
    self.assertIn(
        office_views.FIRST_POST_PACKAGE["theme"], html
    )
    for title in (
        "AI初心者が最初に試す便利な使い方",
        "仕事の文章作成・要約をラクにするAI活用",
        "デスク周りを整える便利ガジェット",
        "スマホ・PC作業を快適にする周辺機器",
    ):
      self.assertIn(title, html)
    # 「見送り」扱いだったテーマは計画に含めない。
    self.assertNotIn("買う前に確認したいAI対応ガジェットの選び方", html)

  def test_weekly_plan_shows_medium_purpose_and_status_for_each_day(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    for medium in ("Pinterest", "Threads", "Instagram", "note"):
      self.assertIn(f"<b>{medium}</b>", html)
    for status_label in ("公開済み", "下書き", "確認待ち", "手動投稿候補"):
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

  def test_weekly_plan_explains_review_then_decide_flow(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn("初回投稿の実績", html)
    self.assertIn("確認したうえで", html)
    self.assertIn("自動化するかを判断します", html)

  def test_weekly_plan_states_internal_draft_not_published_or_sent(self):
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertIn("社内向けの確認用計画です", html)
    self.assertIn("予約投稿・", html)
    self.assertIn("自動投稿は一切行われません", html)
    self.assertIn("localhost限定", html)
    self.assertIn(
        "SNS投稿・予約投稿・広告出稿・営業送信は行われません", html
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
    html = self.client.get("/revenue").get_data(as_text=True)
    section = html.split('id="room-prep"', 1)[1]
    for genre in (
        "AIアシスタント対応スマートスピーカー",
        "音声入力対応キーボード",
        "音声文字起こしデバイス",
        "ノートPC用外付けマイク",
        "モニターアーム",
        "デスクライト",
        "ケーブル収納グッズ",
        "USB-Cハブ",
        "ワイヤレス充電スタンド",
        "ノートPCスタンド",
    ):
      self.assertIn(genre, section)
    self.assertIn("実在の商品名・価格・ランキング・在庫・成果予測は表示しません", section)
    # 実在の商品名・価格・ランキング・在庫数量・成果予測を捏造していないこと。
    self.assertNotIn("円", section)
    self.assertNotIn("¥", section)
    self.assertNotIn("位獲得", section)
    self.assertNotIn("http://", section)
    self.assertNotIn("https://", section)

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
    import office_views
    self.assertEqual(len(office_views.ROOM_PREP_CATEGORIES), 4)
    for category in office_views.ROOM_PREP_CATEGORIES:
      self.assertIn(category["status"], office_views.ROOM_PREP_STATUS_LABELS)
    rendered = office_views._render_room_prep_section(
        office_views.ROOM_PREP_CATEGORIES, office_views.ROOM_PREP_STATUS_LABELS
    )
    self.assertIn("room-prep-section", rendered)

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
    # v3画像)になった。MISSION 037.1のnoteヒーロー画像は文字を画像に
    # 焼き込まないためImageFontを使わず、ImageDraw+ImageFilterのみの
    # 遅延importになっている(別テストで検証)。
    self.assertEqual(
        module_source.count("from PIL import Image, ImageDraw, ImageFont"), 4
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

  def test_publish_queue_shows_three_posts_as_awaiting_approval(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 3)
    for post in office_views.PUBLISH_QUEUE_POSTS:
      self.assertIn(post["pin"]["title"], html)
      self.assertEqual(post["status"], "社長承認待ち")
    self.assertEqual(html.count('class="pq-status-badge"'), 3)
    for title in (
        # MISSION 039でメール下書き用の投稿タイトルを更新した。
        "AIにメールの下書きを頼む前に決める3つ",
        "デスクが狭いときに配線を見直す3つのポイント",
        "スマホ・PC作業をラクにする周辺機器の選び方",
    ):
      self.assertIn(title, html)

  def test_publish_queue_each_post_has_svg_title_description_alt_topics_and_checklist(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 039で「AIにメールの下書きを頼む前に決める3つ」だけ、SVG生成
    # ではなく高精細画像(<img>)を使うようになったため、SVG件数は3→2件になった
    # (デスク配線・周辺機器選びの2件は引き続きSVG生成のまま)。
    self.assertEqual(html.count('<svg viewBox="0 0 1000 1500"'), 2)
    self.assertEqual(html.count("Pinterestのトピック候補"), 3)
    self.assertEqual(html.count("投稿前チェックリスト"), 3)
    for post_id in ("email-draft-3points", "desk-wiring-3points", "peripheral-choice-3points"):
      self.assertIn(f'id="pq-title-{post_id}"', html)
      self.assertIn(f'id="pq-description-{post_id}"', html)
      self.assertIn(f'id="pq-alt-{post_id}"', html)
    for topic in (
        "AI活用術", "仕事効率化", "ビジネスメール",
        "デスク環境", "配線収納", "在宅ワーク",
        "周辺機器", "ガジェット選び",
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
    self.assertEqual(html.count("<img"), 1)
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
    # 残る2件(デスク配線・周辺機器選び)は引き続き空欄のまま。
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(html.count("楽天ROOMリンク：（空欄）"), 2)
    self.assertEqual(
        html.count(
            "社長がPinterestへ投稿する際に手動で貼り付けてください。"
            "URLの取得・保存・外部連携は、この画面では一切行いません。"
        ),
        2,
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
    self.assertEqual(html.count("公開について"), 3)
    # ページ冒頭のリード文でも同じ文言を明記しているため、カード3件+リード文1件
    # の合計4件が期待値。
    self.assertEqual(
        html.count("公開は社長がPinterestで手動実行します"), 4
    )
    self.assertIn(
        "Pinterest・楽天ROOM・Threads・Instagram・noteへの自動投稿・予約投稿・外部通信は"
        "一切行いません", html
    )

  def test_publish_queue_links_to_desk_setup_post_and_weekly_plan(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn('href="/content-studio/desk-setup-post"', html)
    self.assertIn('href="/content-studio/weekly-plan"', html)

  def test_publish_queue_copy_buttons_fail_safely_without_breaking_page(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertIn("fp-copy-btn", html)
    self.assertIn("showResult(false)", html)
    self.assertIn("catch(e)", html)
    # コピー用ボタンは、デスク配線・周辺機器選びが3フィールド×2件=6個、
    # メール下書きがタイトル・説明文・altテキスト・リンク先の4フィールド=
    # 4個で、合計10個(MISSION 039でリンク先フィールドが1件追加された)。
    self.assertEqual(html.count('class="fp-copy-btn"'), 10)

  def test_publish_queue_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 039で「AIにメールの下書きを頼む前に決める3つ」のPinterest
    # リンク先として、公開済みnote記事への実URLを1箇所だけ追加した(href属性
    # とリンクテキストの2箇所に同じURLが現れるため、https://の出現回数は2)。
    # それ以外の外部通信・スクリプト・API呼び出しは一切追加していないことを
    # 確認する。
    self.assertEqual(html.count("https://"), 2)
    self.assertEqual(
        html.count("https://note.com/legal_crow9879/n/nf7af35ac8c28"), 2
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
    self.assertEqual(html.count("Pinterest用PNGを保存"), 3)
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
    self.assertEqual(html.count('type="checkbox"'), 7)
    self.assertIn("本文が4,500〜5,500字の目安に収まっているか確認した", html)

  def test_note_first_article_has_no_external_resources_or_network_calls(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertNotIn("https://", html)
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


if __name__ == "__main__":
  unittest.main()
