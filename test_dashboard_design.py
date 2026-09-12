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
    # 既存の演出用デスクキャラクター(琴衣・蒼・美咲・海・湊・伊藤)は
    # そのまま残っていることを確認する(トップページからの削除が、他画面を
    # 壊していないことの回帰確認)。
    office_html = self.client.get("/office").get_data(as_text=True)
    for name in ("琴衣", "蒼", "美咲", "海", "湊", "伊藤"):
      self.assertIn(name, office_html)

  # --- MISSION 038.1: 4カードの現状表示を実際の運用状況へ合わせる更新 -----------

  def test_root_dashboard_cards_reflect_current_actual_status(self):
    # MISSION 050: Pinterestは4件公開済み+次の投稿案1件、noteは2本公開済み
    # +次の記事下書き準備済み、という実際の運用状況に合わせて更新した。
    # Threadsカード(Dify別管理の自動投稿)も新たに追加した。
    for role, next_action in (
        (
            "現在の役割：4件公開済み。反応を手動で確認しつつ、"
            "次の投稿案（1件）を準備済み。",
            "次の行動：<b>投稿キューの準備済み案を確認し、社長が手動で"
            "Pinterestへ投稿・分析確認を行う。</b>",
        ),
        (
            "現在の役割：公開済みの商品投稿を確認し、次に紹介する候補を整理する。",
            "次の行動：<b>投稿間隔を空けながら、社長が手動で商品を整理・投稿する。</b>",
        ),
        (
            "現在の役割：2本公開済み。次の記事の下書き・見出し画像・"
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
    self.assertIn("Pinterest：4件公開済み", html)
    self.assertIn("note：2本公開済み", html)
    self.assertIn("Threads：Difyで別管理の自動投稿を運用中", html)
    self.assertNotIn('fetch("/api/logs")', html)
    self.assertNotIn('fetch("/api/employees")', html)
    self.assertNotIn('method="POST"', html)
    self.assertNotIn("A8.net", html)
    self.assertNotIn("ラッシュアディクト", html)
    self.assertNotIn("美容サロン", html)

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
    # をやめ、柴犬社長が確認したPinterest・noteの公開件数・次の投稿案の
    # 準備状況を静的に表示する。書き込みは一切行わない。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("<b>4件</b><span>Pinterest公開済み</span>", html)
    self.assertIn("<b>2本</b><span>note公開済み</span>", html)
    self.assertIn("<b>1件</b><span>Pinterest次の投稿案</span>", html)
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
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("最新の仕事", html)
    self.assertIn(
        "Pinterest：「AIが「なんか違う」ときに見直す3つ」を準備（社長承認待ち）", html
    )
    self.assertIn(
        "note：「AIに聞いても「なんか違う」と感じる人へ」の下書きを準備", html
    )
    self.assertIn("前回Pinterest投稿の反応を確認中（48時間ほど様子を見る段階）", html)
    self.assertNotIn("logs.slice(0,3)", html)

  def test_ceo_office_shows_fixed_priority_text(self):
    # 優先事項は「Pinterestの反応確認と、次の手動投稿タイミングの判断」の
    # 固定文言で表示する(社長からの明示的な指定内容)。
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("いま優先すること", html)
    self.assertIn("<p>Pinterestの反応確認と、次の手動投稿タイミングの判断</p>", html)
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
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn("qaAppendBoss", html)
    self.assertIn('document.querySelector("#log")', html)
    self.assertIn(
        "🐕 柴犬社長：Pinterestは4件、noteは2本、公開済みだよ。", html
    )
    self.assertIn(
        "🐕 柴犬社長：いま優先するのは、Pinterestの反応確認と、"
        "次の手動投稿タイミングの判断だよ。",
        html,
    )
    self.assertIn(
        "🐕 柴犬社長：Pinterestは4件、noteは2本、公開まで完了しているよ。", html
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
    # 不要になったため削除したが、オフィス側の6デスクの構成・並び順自体は
    # 変更していないことを確認する。
    office_html = self.client.get("/office").get_data(as_text=True)
    for key in ("misaki", "umi", "minato", "ito", "kotoe", "aoi"):
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
    html = self.client.get("/office").get_data(as_text=True)
    for role in ("WEBディレクター", "UIデザイナー", "フロントエンド", "QA・SEO", "運用チーム"):
      self.assertIn(role, html)

  def test_break_room_reflects_actual_posting_wait_and_review_state(self):
    # MISSION 051: 架空スタッフの氏名・休憩理由・移動予定を一旦削除し、
    # 「投稿の反応を待ち、次の作業を整理する時間」という実際の待機・
    # 振り返りの状態を表示するように更新した。
    # MISSION 053: 「気軽に相談している空気感」を出すため、琴衣・蒼・彩の
    # 3人をソファ・休憩室に再登場させたが、話している内容はPinterest反応
    # 待ち・note次の記事準備済みという実際の状態のみであり、休憩理由・
    # 移動予定などの新しい実データは増やしていない。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn("Pinterest投稿の反応を待つ時間", html)
    self.assertIn("次の投稿・記事の準備状況を整理中", html)
    self.assertIn("48時間ほど反応を見ている段階です", html)
    self.assertIn("勤怠・休憩予定・作業ログの実データは表示・記録していません", html)
    for name in ("琴衣", "蒼", "彩"):
      self.assertIn(name, html)
    for name in ("海", "伊藤"):
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
    # MISSION 052: Pinterest 4件公開・note 2本公開・楽天ROOM折りたたみ
    # キーボード1件公開という現在の実際の運用状況に合わせて更新済み。
    html = self.client.get("/revenue").get_data(as_text=True)
    self.assertIn("事業の目的", html)
    self.assertIn("投稿企画工場のテーマを軸に発信し", html)
    self.assertIn("想定するお客さま像", html)
    self.assertIn("AI初心者、仕事の効率化に関心がある人", html)
    self.assertIn("収益化の柱（案）", html)
    self.assertIn("投稿企画工場のテーマに沿った発信", html)
    self.assertIn("公開済みPinterest投稿（4件）・note記事（2本）からの流入育成", html)
    self.assertIn("楽天ROOMでの手動カテゴリ紹介（折りたたみキーボードを1件公開済み）", html)
    self.assertIn("ROOM登録までの段階", html)
    for stage in ("テーマ選定", "投稿確認", "ROOM準備", "手動登録"):
      self.assertIn(stage, html)
    self.assertIn("今週の優先行動", html)
    self.assertIn("Pinterest・noteの反応確認", html)
    self.assertIn("次の手動投稿タイミングの判断", html)
    self.assertIn("既存ROOM投稿（折りたたみキーボード）の内容・反応を確認", html)

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
    self.assertEqual(html.count('class="cs-plan-card"'), 5)

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
    self.assertEqual(queue_html.count('class="pq-status-badge"'), 5)
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
    self.assertEqual(queue_html.count('class="pq-status-badge"'), 5)
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
    html = self.client.get("/content-studio").get_data(as_text=True)
    self.assertIn("次のnote記事・Pinterest投稿の候補（AI初心者向け・企画メモ）", html)
    self.assertIn(
        "公開済みのPinterest投稿4本・note記事2本の内容を踏まえ、次に作る候補を3つ整理した"
        "企画メモです。",
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

  def test_content_studio_shows_three_candidates_with_all_required_fields(self):
    import office_views
    candidates = office_views.CONTENT_STUDIO_NEXT_ARTICLE_CANDIDATES
    self.assertEqual(len(candidates), 3)
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
    # 既存4本(メール下書き・デスク配線・周辺機器選び・スマホでのAI下書き)や、
    # note記事2本(一般的なAIの使い方・スマホでのAI下書き)と同じテーマ文言を
    # 候補のタイトル案に使っていないことを確認する。
    import office_views
    existing_titles = (
        "AIにメールの下書きを頼む前に決める3つ",
        "デスクが狭いときに配線を見直す3つのポイント",
        "スマホ・PC作業をラクにする周辺機器の選び方",
        "スマホでAIに下書きを頼む前に確認する3つ",
        "AI初心者が仕事で最初に試す3つの使い方──メール・要約・壁打ちを失敗しない形で始める",
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
    self.assertEqual(queue_html.count('class="pq-status-badge"'), 5)
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
    self.assertEqual(rendered.count('class="cs-plan-card"'), 5)

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

  def test_room_prep_shows_published_folding_keyboard_post_as_plain_fact(self):
    # MISSION 052: 既に手動投稿済みの折りたたみキーボード投稿を、金額・
    # 在庫・ランキング・未確認レビューなしの事実のみで表示することを確認する。
    html = self.client.get("/revenue").get_data(as_text=True)
    published_block = html.split('class="room-prep-published"', 1)[1].split(
        "</div>", 1
    )[0]
    self.assertIn("公開済みの楽天ROOM投稿", published_block)
    self.assertIn("折りたたみキーボード", published_block)
    self.assertIn("楽天ROOMへ手動投稿済み（1件）", published_block)
    self.assertIn(
        "商品候補を増やす前に、この投稿の内容と反応を手動で確認する段階です。",
        published_block,
    )
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
    import office_views
    self.assertEqual(len(office_views.ROOM_PREP_CATEGORIES), 2)
    for category in office_views.ROOM_PREP_CATEGORIES:
      self.assertIn(category["status"], office_views.ROOM_PREP_STATUS_LABELS)
    self.assertEqual(len(office_views.ROOM_PUBLISHED_POSTS), 1)
    for post in office_views.ROOM_PUBLISHED_POSTS:
      self.assertIn("item_label", post)
      self.assertIn("status_text", post)
      self.assertIn("next_step", post)
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

  def test_publish_queue_shows_five_posts_as_awaiting_approval(self):
    import office_views
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    # MISSION 042で4件目(スマホでのAI下書き)、MISSION 049で5件目(AIが
    # 「なんか違う」ときに見直す3つ)を追加した。
    self.assertEqual(len(office_views.PUBLISH_QUEUE_POSTS), 5)
    for post in office_views.PUBLISH_QUEUE_POSTS:
      self.assertIn(post["pin"]["title"], html)
      self.assertEqual(post["status"], "社長承認待ち")
    self.assertEqual(html.count('class="pq-status-badge"'), 5)
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
    # 新規追加分も空欄のままだが、汎用文言ではなく専用の注記(折りたたみ
    # キーボード投稿URLを手動で貼る旨)を表示するため、「楽天ROOMリンク：
    # （空欄）」自体の出現数は3件(共通の書き出し部分)になる。MISSION 049の
    # 新規追加分(ai-mismatch-3points)は汎用文言のまま空欄にしているため、
    # 出現数はさらに1件増えて4件になる。
    html = self.client.get("/content-studio/publish-queue").get_data(as_text=True)
    self.assertEqual(html.count("楽天ROOMリンク：（空欄）"), 4)
    self.assertEqual(
        html.count(
            "社長がPinterestへ投稿する際に手動で貼り付けてください。"
            "URLの取得・保存・外部連携は、この画面では一切行いません。"
        ),
        3,
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
    # コピー用ボタンは、デスク配線・周辺機器選び・スマホAI下書き・AIとの
    # 会話見直しの4件がタイトル・説明文・altテキストの3フィールド×4件=12個、
    # メール下書きがタイトル・説明文・altテキスト・リンク先の4フィールド=
    # 4個で、合計16個(MISSION 049でAIとの会話見直しカードの3フィールドが
    # 追加された)。
    self.assertEqual(html.count('class="fp-copy-btn"'), 16)

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
    self.assertEqual(post["status"], "社長承認待ち")
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
    self.assertEqual(html.count('class="pq-status-badge"'), 5)

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
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    self.assertIn("さらに次のnote記事下書き", html)
    self.assertIn(
        "AIに聞いても「なんか違う」と感じる人へ。話がかみ合わないときの3つの見直し", html
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

  def test_note_third_article_draft_states_draft_only_not_posted_to_note(self):
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    third_section_html = html.split(
        'aria-label="AIとの会話の見直しテーマのnote記事下書き"', 1
    )[1]
    self.assertIn("この記事はまだ下書きであり、noteへは投稿していません", third_section_html)
    self.assertIn(
        "note・SNSへの自動投稿・予約投稿・ログイン操作・API連携・外部通信は一切行いません",
        third_section_html,
    )

  def test_note_third_article_draft_shows_hero_image_without_html_title_overlay(self):
    import office_views
    article = office_views.NOTE_THIRD_ARTICLE_DRAFT
    html = self.client.get("/content-studio/note-first-article").get_data(as_text=True)
    third_section_html = html.split(
        'aria-label="AIとの会話の見直しテーマのnote記事下書き"', 1
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
    self.assertEqual(post["status"], "社長承認待ち")
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
    self.assertNotIn('id="pq-link-ai-mismatch-3points"', html)

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
    # であり、人物アバターや各部屋の画像・キャラクターは変更しないことを
    # 確認する(既存の演出用デスクキャラクターがそのまま残っていること)。
    office_html = self.client.get("/office").get_data(as_text=True)
    for name in ("琴衣", "蒼", "美咲", "海", "湊", "伊藤"):
      self.assertIn(name, office_html)

  def test_weekly_plan_published_days_have_no_fabricated_reaction_numbers(self):
    # MISSION 050で新たに公開済みへ変わった2・6・7日目も、1日目と同様に
    # 表示回数・保存数・クリック数などの反応・成果を、数値付きで記載して
    # いないことを確認する。
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    for day_start, day_end in (("2日目：", "3日目："), ("6日目：", "7日目："), ("7日目：", "</section>")):
      with self.subTest(day_start=day_start):
        card = html.split(day_start, 1)[1].split(day_end, 1)[0]
        self.assertIn("公開済み", card)
        self.assertIn("反応・成果は", card)
        for word in ("表示回数", "保存数", "クリック数", "閲覧数", "スキ数"):
          self.assertNotIn(f"{word}：", card)
          self.assertNotIn(f"{word}が", card)

  def test_weekly_plan_status_labels_reflect_only_statuses_in_use(self):
    import office_views
    used_statuses = {entry["status"] for entry in office_views.WEEKLY_PLAN}
    self.assertEqual(used_statuses, {"published", "manual_candidate"})
    html = self.client.get("/content-studio/weekly-plan").get_data(as_text=True)
    self.assertEqual(html.count('class="wp-day-status status-published"'), 4)
    self.assertEqual(html.count('class="wp-day-status status-manual_candidate"'), 3)

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
    # MISSION 051は表示テキストの更新のみで、人物アバター・部屋の背景画像・
    # 画像ファイルは変更しないことを確認する。
    html = self.client.get("/office").get_data(as_text=True)
    self.assertIn("/static/images/office-avatars-v1.png", html)
    for key in ("misaki", "umi", "minato", "ito", "kotoe", "aoi"):
      self.assertIn(f'avatar-{key}', html)
    for role in ("WEBディレクター", "UIデザイナー", "フロントエンド", "QA・SEO", "運用チーム"):
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

  def test_office_walker_figure_is_visible_with_correct_avatar(self):
    # 上記回帰の直接確認: 「彩・休憩へ」の人物アバターが実際に描画される
    # (avatar-ayakaのクラスが立っている)ことを確認する。
    html = self.client.get("/office").get_data(as_text=True)
    walker_section = html.split('<div class="walker">', 1)[1].split("</div>", 1)[0]
    self.assertIn("avatar-ayaka", walker_section)

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
    # 手前の列(desk-front)に分ける。手前列はCSS変数--sで人物をやや
    # 拡大し、奥列は明度・彩度を落とす(filter)ことで奥行きを表現する
    # (人物を縮小すると、モニター表示の裏に顔が隠れてしまうため、奥列の
    # 拡大縮小は行わない)。デスクの実データ(役割・作業内容)は変更しない。
    html = self.client.get("/office").get_data(as_text=True)
    for key in ("misaki", "umi", "minato", "ito"):
      self.assertIn(f'id="desk-{key}" data-key="{key}"', html)
    for key in ("kotoe", "aoi"):
      self.assertIn(f'id="desk-{key}" data-key="{key}"', html)
    for i, key in enumerate(("misaki", "umi", "minato", "ito"), start=1):
      self.assertIn(f'class="desk d{i} desk-back" id="desk-{key}"', html)
    for i, key in enumerate(("kotoe", "aoi"), start=5):
      self.assertIn(f'class="desk d{i} desk-front" id="desk-{key}"', html)
    self.assertIn(".desk.desk-back{filter:", html)
    self.assertIn(".desk.desk-front{--s:", html)

  def test_office_desks_show_visible_role_labels_without_a_click(self):
    # MISSION 053: 役割(顔・表情・役割が分かる)を、デスク詳細を開かなくても
    # その場で見えるようにする。
    html = self.client.get("/office").get_data(as_text=True)
    for role in ("WEBディレクター", "UIデザイナー", "フロントエンド", "QA・SEO"):
      self.assertIn(f'<i class="desk-role">{role}</i>', html)
    self.assertEqual(html.count('<i class="desk-role">運用チーム</i>'), 2)

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
    html = self.client.get("/office/ceo-office").get_data(as_text=True)
    self.assertIn('class="ceo-spotlight" aria-hidden="true"', html)
    self.assertIn('class="ceo-monitor" aria-hidden="true"', html)
    self.assertIn("いま確認している状況", html)
    self.assertIn("<span>Pinterest</span><span>4件公開</span>", html)
    self.assertIn("<span>note</span><span>2本公開</span>", html)
    self.assertIn("<span>Threads</span><span>Dify運用</span>", html)
    self.assertIn(".ceo-desk{--s:", html)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)

  def test_break_room_shows_two_characters_chatting_about_real_status_only(self):
    # MISSION 053: 「投稿後の反応確認や次の企画を気軽に相談している
    # 空気感」を出すため、琴衣・蒼をソファに座らせる。会話の内容は
    # Pinterest反応待ち・note次の記事準備済みという既存の事実のみで
    # あり、新しい休憩理由・移動予定・個人の勤務実績は追加しない。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn('class="sofa-guest sofa-guest-1"', html)
    self.assertIn('class="sofa-guest sofa-guest-2"', html)
    self.assertIn("avatar-kotoe", html)
    self.assertIn("avatar-aoi", html)
    self.assertIn('<span class="sofa-chat"><b>琴衣</b>', html)
    self.assertIn('<span class="sofa-chat"><b>蒼</b>', html)
    self.assertNotIn("休憩理由", html)
    self.assertNotIn("円", html)
    self.assertNotIn("¥", html)

  def test_break_room_walker_is_a_character_figure_not_a_bare_emoji(self):
    # MISSION 053: 「📝」の絵文字だけだった移動中の人物を、既存のアバター
    # 仕組み(彩)を使ったキャラクター表示に差し替える。読みやすさの回帰
    # 修正(.break-walker smallの明るい文字色)は維持する。
    html = self.client.get("/office/break-room").get_data(as_text=True)
    self.assertIn("avatar-ayaka", html)
    walker_section = html.split('class="break-walker"', 1)[1].split("</div>", 1)[0]
    self.assertNotIn("📝", walker_section)
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


if __name__ == "__main__":
  unittest.main()
