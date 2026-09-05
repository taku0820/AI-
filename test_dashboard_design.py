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

  def test_api_logs_integration_script_is_preserved(self):
    self.assertIn("fetch('/api/logs')", self.html)
    self.assertIn('id="latest-theme"', self.html)
    self.assertIn('id="latest-content"', self.html)

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

  # --- ミニフィギュア(ローカル画像スプライト)が8名分描画されていること -------

  def test_eight_member_mini_figures_are_rendered(self):
    self.assertEqual(self.html.count('class="avatar-sprite '), 8)
    for name in ("柴犬社長", "彩・経理担当", "琴衣", "蒼", "美咲", "海", "湊", "伊藤"):
      self.assertIn(name, self.html)

  def test_each_role_status_prop_badge_is_rendered(self):
    for prop in ("stamp", "doc", "check", "phone", "list", "pen", "code", "search"):
      self.assertIn(f'avatar-badge prop-{prop}', self.html)

  # --- レスポンシブ対応 --------------------------------------------------------

  def test_viewport_meta_present(self):
    self.assertIn('name="viewport"', self.html)

  def test_responsive_media_queries_present(self):
    self.assertIn("@media (max-width: 860px)", self.html)
    self.assertIn("@media (max-width: 480px)", self.html)

  # --- アニメーションは既存ステータス文言に紐づく装飾のみであること ----------------

  def test_status_text_labels_are_unchanged_example_data(self):
    # 各ステータス文言は元のダッシュボードから引き継いだ表示用の例示
    # データであり、新規に「リアルタイムの実処理」を主張する文言を
    # 追加していないことを確認する。
    for status in (
        "A8.net提携確認", "Pinterest投稿準備", "制約進行を整理中",
        "デザインを調整中", "コードを実装中", "テストを実施中",
    ):
      self.assertIn(status, self.html)

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
    self.assertIn("美容サロン向けWeb制作", html)

  def test_revenue_board_shows_all_required_content_cards(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("事業の目的", html)
    self.assertIn("美容サロンの集客・予約導線を整えるWeb制作支援", html)
    self.assertIn("想定するお客さま像", html)
    self.assertIn("地域の美容サロン、小規模店、Web集客を改善したい事業者", html)
    self.assertIn("サービス案", html)
    self.assertIn("LP制作", html)
    self.assertIn("既存サイト改善", html)
    self.assertIn("予約導線・SNS導線の整理", html)
    self.assertIn("受注までの段階", html)
    for stage in ("準備", "提案", "商談", "受注"):
      self.assertIn(stage, html)
    self.assertIn("今週の優先行動", html)
    self.assertIn("ポートフォリオ整理", html)
    self.assertIn("提案テンプレート作成", html)
    self.assertIn("見込みサロンの条件整理", html)

  def test_revenue_board_price_is_an_explicit_draft_not_final(self):
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("価格帯", html)
    self.assertIn("未確定", html)
    self.assertIn("確定した金額・契約内容ではありません", html)
    self.assertIn("未定", html)
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


if __name__ == "__main__":
  unittest.main()
