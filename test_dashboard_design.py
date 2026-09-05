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
