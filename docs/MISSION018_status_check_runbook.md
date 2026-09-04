# localhost限定 読み取り専用ヘルスチェックCLI 利用手順書（MISSION 018）

対象ファイル: `hive_status.py`（本MISSIONで追加した唯一の実装ファイル）

作成時点のブランチ: `claude/company-dashboard-sqlite-mjoexa`
作成時点のHEAD: `ce36cad7e1b93a306667deb46de3555bf2f24548`（MISSION 017完了時点）

---

## 1. 目的

`app.py`（AI Hive OS）と `ai_company.db` の稼働状態を、**一切の副作用なしに**
その場で確認するための最小限のCLI。サーバーを再起動したとき、作業を
再開するときなど、「今この環境は正常に動いているか」をすぐに確認できる
ようにする。

---

## 2. 実行方法

前提: 別ターミナルで `app.py` が起動済み（ポート5050、`host=127.0.0.1`）で
あること。サーバーが起動していなくても実行は可能（その場合は接続失敗が
安全に表示される）。

```bash
python hive_status.py
```

引数は受け付けない（接続先・対象DBともにコード上固定のため）。想定外の
引数を渡した場合はargparseが安全にエラー終了する。

出力例（正常時）:

```
[OK] root_page (GET /): OK (HTTP 200)
[OK] logs_api (GET /api/logs): OK (3件, HTTP 200)
[OK] database (ai_company.db): integrity_check=ok, foreign_key_violations=0
      audit_logs: 3件
      decisions: 0件
      employees: 0件
      metrics: 0件
      missions: 0件
      proposals: 0件
      reports: 0件
      tasks: 0件
      work_logs: 3件
[NG] token_env_presence (このCLIプロセス自身の環境変数): AI_HIVE_READ_TOKEN=未設定, AI_HIVE_WRITE_TOKEN=未設定, AI_HIVE_ADMIN_TOKEN=未設定
      ※ 値そのものは表示していません。サーバー側の設定確認ではなく、参考情報のため総合判定には含めません。
総合判定: OK
```

終了コードは、総合判定が `OK` のとき `0`、`NG` のとき `1`。

---

## 3. 確認している項目

| チェック名 | 内容 | 認証 | 副作用 |
|---|---|---|---|
| `root_page (GET /)` | `http://127.0.0.1:5050/` にGETし、200かつダッシュボードHTMLが返るか | 不要 | なし |
| `logs_api (GET /api/logs)` | 同URLの `/api/logs` にGETし、200かつJSON配列が返るか | 不要 | なし |
| `database (ai_company.db)` | `ai_company.db` を読み取り専用接続で開き、`PRAGMA integrity_check`・`PRAGMA foreign_key_check`・想定9テーブルの存在とテーブル別件数を確認 | 不要(HTTPを使わずファイルへ直接読み取り専用アクセス) | なし |
| `token_env_presence` | `AI_HIVE_READ_TOKEN`/`AI_HIVE_WRITE_TOKEN`/`AI_HIVE_ADMIN_TOKEN` が、**このCLIを実行しているプロセス自身の環境**に設定されているか(値は見ない) | - | なし。総合判定には含めない参考情報 |

### なぜ `/api/employees` 等の新規Hive APIを直接チェックしないのか

`hive_db.require_permission` で保護された新規Hive API（`/api/employees`
等、MISSION 015の `hive_admin.py` が使う `GET /api/audit-logs` も含む）は、
**成功する読み取り専用のGETリクエストであっても、呼び出しのたびに
`audit_logs` テーブルへ1行記録するという副作用を伴う**（MISSION 013で
導入した監査ログの仕様どおりであり、不具合ではない）。

本CLIは「既存サーバーへ副作用のない確認だけを行う」という要件を厳密に
満たすため、これらの保護されたエンドポイントを一切呼び出さない設計と
した。Hive APIの認証そのものが正しく機能しているかを能動的に確認したい
場合は、副作用（`audit_logs`への1件記録）を許容したうえで、別途
`hive_admin.py`（MISSION 015、`docs/MISSION015_admin_cli_runbook.md`）を
使うこと。

---

## 4. 接続先・対象DBの固定について

- HTTP接続先は `http://127.0.0.1:5050` にコード上で固定されている。CLI
  引数・環境変数で変更するオプションは存在しない
- HTTPリダイレクトは一切追跡しない（`hive_admin.py` と同じ方針）
- DBチェックの対象は `ai_company.db`（プロジェクト直下）に固定
- いずれのチェックも `Authorization` ヘッダーを一切送信しない
  （対象が認証不要の既存2エンドポイントのみのため）

---

## 5. トークンの取り扱い

- 本CLIはネットワーク越しにトークンを一切送信しない（対象が認証不要の
  エンドポイントのみのため）
- `token_env_presence` チェックは、環境変数が「設定されているか否か」の
  真偽値のみを表示し、**値そのものを取得・表示・ログ・ファイルへ出力
  することは一切ない**
- この確認はあくまで「このCLIを実行しているプロセス自身」の環境変数を
  見ているだけであり、`app.py` を起動している別プロセス・別ターミナルの
  設定状態を保証するものではない（両者が同じ環境変数を共有している
  保証はない）。サーバー側の認証設定を確認したい場合は、サーバーを
  起動したターミナルで直接確認すること

---

## 6. エラー時の見え方

| 状況 | 表示 |
|---|---|
| サーバー未起動・接続不可 | `http://127.0.0.1:5050 へ接続できませんでした。サーバー(app.py)が起動しているか確認してください。` |
| タイムアウト(5秒) | `http://127.0.0.1:5050 への接続がタイムアウトしました。` |
| リダイレクトが返された | `サーバーがリダイレクトを返しました(HTTP xxx)。安全のため追跡しません。` |
| 想定外のHTTPステータス | `想定外のHTTPステータスでした: xxx` |
| `/api/logs` のレスポンスが不正なJSON | `レスポンスが不正なJSON形式でした。` |
| `ai_company.db` が存在しない | `DBファイルが見つかりません: ...` |
| DBが破損している | `整合性チェックに失敗しました: ...` （例外を外に漏らさず安全に表示） |
| 想定テーブルが不足 | `database` の詳細に `不足テーブル=[...]` として表示 |

いずれの場合も、Pythonの例外トレースバックをそのまま表示することはなく、
チェック単位で `[NG] <チェック名>: <理由>` の形式にまとめて表示される。

---

## 7. 動作確認の記録（本MISSIONでの実施内容）

一時DBコピー上で起動したサーバーに対し、以下を確認した（本番
`ai_company.db` には一切接続していない）。

- 正常時: 4チェックすべて実行され、`root_page`・`logs_api`・`database` が
  OK、総合判定OK（終了コード0）。実行前後で `audit_logs` の件数が3件の
  まま変化しないこと＝副作用なしを実証済み
- トークン環境変数を設定した状態での実行: `token_env_presence` が
  「設定済み」と表示され、出力全体にトークンの値そのものが一切含まれ
  ないことを確認済み
- サーバー停止後の実行: `root_page`・`logs_api` がいずれも安全な接続
  失敗メッセージとなり、`database` チェックのみ引き続きOK、総合判定NG
  （終了コード1）となることを確認済み

---

## 8. 外部公開・外部AI接続とは無関係であること

- 本CLIは `http://127.0.0.1:5050` 以外へは一切接続しない
- 本機能の追加は、`docs/MISSION009_auth_design.md` 3.6節・
  `docs/MISSION014_local_audit_view_design.md` 7章・
  `docs/MISSION015_admin_cli_runbook.md` 7章・
  `docs/MISSION016_backup_recovery_runbook.md` 7章・
  `docs/MISSION017_isolated_restore_drill_runbook.md` 7章で維持してきた
  「localhost限定運用・外部公開なし・外部AI接続なし」の方針に一切影響
  しない
