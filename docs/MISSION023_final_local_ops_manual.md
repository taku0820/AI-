# AI Hive OS 最終ローカル運用マニュアル（MISSION 023）

本書は、MISSION 005〜022で実装してきたAI Hive OS本体・認証/監査基盤・
localhost限定の運用CLI群を、**「起動してから止めるまで」の一連の流れで
安全に再現・運用できるようにする**ための最終マニュアルである。個々の
ツールの詳細な仕様は各MISSIONの手順書に譲り、本書はそれらを跨いだ
「まず何をするか」の唯一の入口として使う。

作成時点のブランチ: `claude/company-dashboard-sqlite-mjoexa`
作成時点のHEAD: `e7e807d26cce09f2ac5c66bc3e972df888279ad2`（MISSION 022完了時点）

本MISSIONで行ったのは本書（ドキュメント）の追加と、既存文書1箇所の
事実誤り修正（10章参照）のみである。アプリ・CLIのコード変更、DBの変更、
実バックアップ・監査ログの変更は一切行っていない。

---

## 0. 全体像（このマニュアルの歩き方）

```
0. 前提: すべてlocalhost(127.0.0.1)限定・人が明示的に実行するツールのみ
1. ローカル起動・停止 ......... app.py を127.0.0.1:5050で動かす/止める
2. 日常のヘルスチェック ....... hive_help.py / hive_status.py / hive_ops.py
3. 監査ログ確認(必要な時だけ) . hive_admin.py (副作用あり、明示実行のみ)
4. バックアップ運用 ........... hive_backup.py create/list/verify/restore-test
5. 異常時の切り分け ........... 2〜4の結果を使った判断フロー
6. 実復元 ...................... 本書だけでは実行不可。別途個別承認が必要
7. 変更・コミット・push ....... git操作時の安全確認手順
```

---

## 1. ローカル起動・停止

### 1.1 起動

```bash
cd /path/to/AI-
source venv/bin/activate

# Hive API(read/write/admin)を使う場合は事前に3本の環境変数を設定する
# (Hiveの新規APIのみに影響し、既存 GET / ・GET /api/logs には不要)
export AI_HIVE_READ_TOKEN="<read token>"
export AI_HIVE_WRITE_TOKEN="<write token>"
export AI_HIVE_ADMIN_TOKEN="<admin token>"

# ポートは既定5050(未設定・不正値の場合も安全に5050へフォールバック)
python app.py
```

- 常に `host="127.0.0.1"` 固定で起動する（`app.py`側にハードコードされて
  おり、CLI引数・環境変数での変更はできない）。`0.0.0.0`へのバインドは
  一切行わない
- Hive API用の3トークンを設定しない場合、既存の `GET /`・`GET /api/logs`
  は従来どおり利用できるが、新規Hive API（`/api/employees`等、
  `GET /api/audit-logs`含む）はfail-closedの方針により全て401となる
  （`docs/MISSION011_local_auth_runbook.md`参照）
- 起動確認: ブラウザまたは `curl http://127.0.0.1:5050/` で200が返ること

### 1.2 停止

- フォアグラウンドで起動した場合は、そのターミナルで `Ctrl+C` を押す
- バックグラウンドで起動した場合は、該当プロセスを通常の方法で終了する
  （例: 起動時のPIDを控えておき `kill <PID>`）
- 停止後は、サーバー起動用に設定した3つの環境変数を
  `unset AI_HIVE_READ_TOKEN AI_HIVE_WRITE_TOKEN AI_HIVE_ADMIN_TOKEN`で
  破棄することを推奨する（`docs/MISSION015_admin_cli_runbook.md` 6章と
  同様の方針）

---

## 2. 日常運用確認（ヘルスチェック・統合ヘルプ）

日常的には、以下のいずれか1つを覚えておけば十分。

```bash
# 最も迷わない入口(引数なしでは何も実行しない。メニューを表示するだけ)
python hive_help.py

# 状態確認だけを行う(副作用なし)
python hive_help.py status
# ↑ 実体は hive_status.py そのもの。直接実行しても同じ:
python hive_status.py

# 状態確認 + 必要ならバックアップ検証も一緒に(副作用なし)
python hive_help.py ops --verify-backup backups/backup_<日時>_<suffix>
# ↑ 実体は hive_ops.py そのもの:
python hive_ops.py --verify-backup backups/backup_<日時>_<suffix>
```

`hive_help.py`は`hive_status.py`・`hive_ops.py`・`hive_backup.py`
（`list`/`verify`）をそのまま呼び出す薄いディスパッチャであり、
引数なし実行・`--help`表示だけではネットワーク通信・DB操作・
バックアップ操作を一切行わない
（`docs/MISSION022_help_cli_runbook.md`参照）。

状態確認で見る4項目（副作用ゼロ）:

| 項目 | 内容 |
|---|---|
| `root_page` | `GET /` が200かダッシュボードHTMLか |
| `logs_api` | `GET /api/logs` が200かJSON配列か |
| `database` | `ai_company.db`の読み取り専用整合性チェック・想定テーブルの有無・件数 |
| `token_env_presence` | このCLIプロセス自身にHiveトークン3種が設定されているか（値は見ない。参考情報で総合判定には含めない） |

詳細: `docs/MISSION018_status_check_runbook.md`（状態確認）・
`docs/MISSION019_ops_cli_runbook.md`（運用CLI）。

---

## 3. 監査ログ確認CLI（`hive_admin.py`）

**`hive_admin.py`は、上記の状態確認・バックアップ検証とは性質が異なる。
成功する読み取り専用の呼び出しであっても、呼び出しのたびに
`audit_logs`テーブルへ1件記録するという副作用を持つ**
（MISSION 013以来の仕様。不具合ではない）。

```bash
export AI_HIVE_ADMIN_TOKEN="<admin token>"
python hive_admin.py --limit 20
unset AI_HIVE_ADMIN_TOKEN
```

- `hive_help.py`・`hive_ops.py`からは自動実行・初期実行・一括実行の
  いずれも行われない（`hive_help.py admin-info`は案内文を表示するだけで
  `hive_admin.py`自体は一切呼び出さない）
- `audit_logs`への記録が増えることを許容できるとき（実際に「直近の
  認証失敗・権限不足・レート制限・admin操作」を確認したいとき）だけ、
  利用者が明示的にこのコマンドを実行すること
- admin権限のトークンのみで参照可能。read/writeトークン・トークンなし・
  不正トークンは拒否される
- 詳細: `docs/MISSION015_admin_cli_runbook.md`

---

## 4. バックアップ運用

### 4.1 作成（副作用: `backups/`へ新規ディレクトリ作成のみ）

```bash
python hive_backup.py create
```

`ai_company.db`を読み取り専用で開き、SQLite公式のOnline Backup APIで
`backups/backup_<日時>_<乱数6桁>/`へコピーする。既存バックアップの
上書き・自動削除は行わない。

### 4.2 一覧（副作用なし。DBファイルすら開かない）

```bash
python hive_backup.py list
```

各バックアップの`metadata.json`に記録済みの情報（作成日時・SHA-256・
整合性チェック結果・テーブル件数）を新しい順に表示するだけで、
検証処理は自動実行しない。`metadata.json`を持たない旧形式のバックアップ
（`pre_missionNNN_*`等、MISSION 016以前に手動で作成したもの）は、
「無視/エラーとなったエントリ」として区別して表示される。

### 4.3 検証（副作用なし。読み取り専用）

```bash
python hive_backup.py verify backups/backup_<日時>_<suffix>
```

ハッシュ一致・`PRAGMA integrity_check`・外部キー整合性を確認する。

### 4.4 隔離復旧訓練（副作用なし。一時領域は訓練後に自動削除）

```bash
python hive_backup.py restore-test backups/backup_<日時>_<suffix>
```

検証済みのバックアップだけを、プロジェクト外の完全な一時領域
（`tempfile`が生成。`backups/`・`ai_company.db`とは絶対に重ならない）へ
実際に複製し、整合性・外部キー整合性・テーブル件数の一致を確認する。
**実DB(`ai_company.db`)へは一切書き込まない。**

詳細: `docs/MISSION016_backup_recovery_runbook.md`（create/list/verify）・
`docs/MISSION017_isolated_restore_drill_runbook.md`（restore-test）。

---

## 5. 異常時の切り分け

サーバー・DBの様子がおかしいと感じたら、以下の順で確認する
（`docs/MISSION020_final_ops_runbook.md` 3章・
`docs/MISSION022_help_cli_runbook.md` 4章と同一の方針）。

1. **`python hive_help.py ops` を実行する。**
   - `root_page`・`logs_api`がNG → `app.py`のプロセス・ポート5050を確認
   - `database`がNG → `ai_company.db`の配置・破損・想定テーブルの欠落を
     確認（`docs/MISSION018_status_check_runbook.md` 6章）
   - `token_env_presence`のNGは異常ではない（このCLI自身の端末の環境
     変数設定を示すだけの参考情報）
2. **`python hive_backup.py list` で候補バックアップを確認し、
   `python hive_help.py ops --verify-backup <対象>` で健全性を確認する。**
   - 「総合判定: NG」の場合、そのバックアップは信頼せず、別世代の
     バックアップで再確認するか、新たに`create`する
3. **必要であれば `python hive_backup.py restore-test <対象>` で、
   実際に複製して中身まで正しく展開できるかを確認する（一時領域のみ）。**
4. **Hive API（`/api/employees`等）の認証で問題が起きている場合は、
   サーバーを起動しているターミナルの環境変数（3本のトークン）を
   直接確認する。**`hive_status.py`/`hive_ops.py`の`token_env_presence`は
   このCLI自身の端末しか見ていない点に注意（`docs/MISSION011_local_auth_runbook.md`）
5. **必要なら `hive_admin.py` で直近の認証失敗・権限不足・レート制限・
   admin操作を確認する（3章の副作用に留意した上で実行する）。**

---

## 6. 実復元は別途承認が必要であること

**本書、およびMISSION 016〜022を通じて、実DB(`ai_company.db`)への
復元・上書き・削除の機能は一切実装していない。**

`hive_backup.py`が持つのは `create`・`list`・`verify`・`restore-test`の
4つのみであり、いずれも実DBを書き換えることはできない。`restore-test`が
一時領域で「総合判定: OK」を示したことは、あくまで「バックアップの中身が
壊れていない・正しく複製できる」ことの確認に過ぎず、実復元の実施可否
そのものを承認するものではない。

実際に本番DBを復旧する必要が生じた場合は、以下を満たした上で、
**利用者の明示的な個別承認を得てから、別MISSIONとして計画・実施する**こと。

- [ ] 復元対象のバックアップが`verify`（または`restore-test`）で
      「総合判定: OK」であることを確認済み
- [ ] 復元対象ファイル・バックアップ日時・復元先（本番を直接上書きするか、
      別名で並行稼働させて比較するか）を明確にした
- [ ] サーバー停止手順（1.2節）を確認した
- [ ] 復元後の動作確認手順（本書2章の状態確認＋全テストの再実行）を
      用意した
- [ ] 復元によって失われるデータ（バックアップ以降に追加された
      `work_logs`・Hiveデータ・`audit_logs`）とその許容可否を整理した

詳細: `docs/MISSION020_final_ops_runbook.md` 5〜6章（復旧前チェック
リストの原本）。

---

## 7. 変更・コミット・push時の安全確認

これまでのMISSIONを通じて一貫して用いてきた手順を、ここに整理する。

### 7.1 コミット前

```bash
# 1. 意図したファイルだけをステージする(git add -A は使わない)
git add <file1> <file2> ...

# 2. ステージ済み差分が意図したファイルだけであることを確認する
git diff --cached --name-only

# 3. git status で ai_company.db・backups/・.DS_Store 等が
#    含まれていないことを確認する(.gitignoreで既に除外されている)
git status
```

- `ai_company.db`・`backups/`は`.gitignore`に登録済みであり、通常操作では
  `git status`にすら現れない。誤って`git add -f`等で追跡対象に加えない
  こと
- 実トークン・`.env`ファイル・秘密情報を含むファイルをステージしない
- コミットメッセージは新規コミットとして作成し、既存コミットの
  `--amend`は明示的に指示された場合のみ行う

### 7.2 push前後

```bash
git branch --show-current
git rev-parse HEAD
git push origin <branch>
git rev-parse HEAD
git rev-parse origin/<branch>
```

- 通常の`git push`のみを使う。`pull`・`merge`・`rebase`・`reset`・
  `force push`は、明示的に指示された場合を除き行わない
- push後は、ローカルHEADとリモートHEADのコミットIDが一致することを
  必ず確認する

---

## 8. 参照一覧（詳細はこちら）

| 分野 | 文書 |
|---|---|
| 認証・脅威モデルの設計 | `docs/MISSION009_auth_design.md` |
| ローカル認証運用手順(3トークンの扱い) | `docs/MISSION011_local_auth_runbook.md` |
| 監査ログ運用画面の設計(未実装・設計のみ) | `docs/MISSION014_local_audit_view_design.md` |
| 監査ログ確認CLI(`hive_admin.py`) | `docs/MISSION015_admin_cli_runbook.md` |
| バックアップ作成・一覧・検証(`hive_backup.py create/list/verify`) | `docs/MISSION016_backup_recovery_runbook.md` |
| 隔離復旧訓練(`hive_backup.py restore-test`) | `docs/MISSION017_isolated_restore_drill_runbook.md` |
| 状態確認(`hive_status.py`) | `docs/MISSION018_status_check_runbook.md` |
| 運用CLI(`hive_ops.py`) | `docs/MISSION019_ops_cli_runbook.md` |
| 横断リファレンス・統合テストの範囲 | `docs/MISSION020_final_ops_runbook.md` |
| バックアップ一覧の詳細仕様(`hive_backup.py list`) | 本書4.2節、実装は`hive_backup.py`本体のdocstring参照(MISSION 021) |
| 統合ヘルプ／ナビゲーションCLI(`hive_help.py`) | `docs/MISSION022_help_cli_runbook.md` |
| 本書(最終ローカル運用マニュアル) | `docs/MISSION023_final_local_ops_manual.md`（本書） |

---

## 9. 現在の全テスト最終確認結果（本MISSIONで再実行）

作成時点のブランチ・HEADにおいて、以下の全テストファイルを実行し、
**合計166件、全PASS**を確認した（実行方法: `venv/bin/python <ファイル名>`、
いずれも一時ディレクトリ・モック通信のみを使用し、本番`ai_company.db`・
実`backups/`には書き込みなし）。

| テストファイル | 件数 | 結果 | 対象 |
|---|---|---|---|
| `test_hive_api.py` | 45 | PASS | 既存Hive API・認証・監査ログ・レート制限 |
| `test_hive_admin.py` | 10 | PASS | `hive_admin.py`(監査ログ確認CLI) |
| `test_hive_backup.py` | 43 | PASS | `hive_backup.py`(create/list/verify/restore-test) |
| `test_hive_status.py` | 26 | PASS | `hive_status.py`(状態確認) |
| `test_hive_ops.py` | 12 | PASS | `hive_ops.py`(運用CLI) |
| `test_integration.py` | 13 | PASS | 全ツール横断の統合結合テスト |
| `test_hive_help.py` | 17 | PASS | `hive_help.py`(統合ヘルプCLI) |
| **合計** | **166** | **全PASS** | |

さらに、稼働中の実サーバー（本番`ai_company.db`使用、`http://127.0.0.1:5050`）
に対し、副作用のない範囲（`hive_status.py`・`hive_ops.py`・
`hive_backup.py list/verify`・`hive_help.py`の各サブコマンド）で実際に
コマンドを実行し、いずれも正常に応答すること、実行前後で本番DBの
SHA-256ハッシュ・`work_logs`/`audit_logs`の件数・実`backups/`の内容が
完全に不変であることを確認した。

---

## 10. 既存ドキュメントの修正について

本MISSIONで、`docs/MISSION020_final_ops_runbook.md` 6章の以下の記述を、
MISSION 021（`hive_backup.py list`の追加）以降の実態に合わせて修正した
（内容の矛盾修正のみであり、それ以外の追記・言い回しの変更は行っていない）。

- 修正前: 「`hive_backup.py`が持つのは `create`（新規作成）・`verify`
  （検証）・`restore-test`（一時領域への隔離復旧訓練）のみであり」
- 修正後: 「`hive_backup.py`が持つのは `create`（新規作成）・`list`
  （一覧表示、MISSION 021で追加）・`verify`（検証）・`restore-test`
  （一時領域への隔離復旧訓練）のみであり」

`list`はDBファイルを一切開かず実DBへ書き込みを行わない読み取り専用
コマンドであるため、修正後も「いずれも実DBを書き換えることはできない」
という同章の結論には影響しない。

他のドキュメント間で、内容が矛盾する記述は確認されなかった（各文書の
「作成時点のHEAD」・「まとめ（本MISSIONでの成果）」節は、いずれも
その時点の状態を記録した文書として妥当であり、後続MISSIONでの機能追加が
それらを「誤り」にするものではないと判断した）。

---

## 11. 禁止事項の遵守確認（本MISSIONでの実施内容）

- アプリ・CLIのコード（`app.py`・`hive_db.py`・`hive_status.py`・
  `hive_backup.py`・`hive_admin.py`・`hive_ops.py`・`hive_help.py`）は
  一切変更していない
- `ai_company.db`・`backups/`・`work_logs`・既存テーブル・既存APIは
  変更・削除・追加していない
- 実バックアップ・監査ログ（`audit_logs`の既存レコード）は変更・削除
  していない
- 外部通信・外部公開・常駐・cron・launchd・外部通知は追加していない
- 実トークン・秘密情報は出力・保存・ログ・例外・本書・コミットのいずれ
  にも含めていない
- `ai_company.db`・`backups/`・`work_logs`・`.DS_Store`はGitへ追加して
  いない（`.gitignore`により`ai_company.db`・`backups/`は元から対象外）

---

## 12. まとめ（本MISSIONでの成果）

- `docs/MISSION023_final_local_ops_manual.md`（本書）を追加し、
  「ローカル起動・停止」「日常運用確認・統合ヘルプ」「監査ログ確認CLI
  （副作用の明記）」「バックアップ運用（作成・一覧・検証・隔離復旧
  訓練）」「異常時の切り分け」「実復元には別途承認が必要」「変更・
  コミット・push時の安全確認」を1つの導線として整理した
- `docs/MISSION020_final_ops_runbook.md`の1箇所（`hive_backup.py`の
  サブコマンド一覧）を、MISSION 021以降の実態に合わせて修正した
- 現在の全166テストを再実行し、全PASSであることを確認・記録した
- アプリ・CLIの挙動変更、リファクタリング、既存コードの削除は行って
  いない
