# AI Hive OS ローカル運用 最終運用手順書（MISSION 020）

対象ファイル: `test_integration.py`（本MISSIONで追加した唯一の実装ファイル。
既存の `hive_status.py`・`hive_backup.py`・`hive_ops.py`・`hive_admin.py`の
実装には一切手を加えていない）

作成時点のブランチ: `claude/company-dashboard-sqlite-mjoexa`
作成時点のHEAD: `9be6cedac66ff9cc91b4702f6ae3192607229831`（MISSION 019完了時点）

本書は、MISSION 009〜019で整備してきたローカル運用ツール群（状態確認・
バックアップ検証・隔離復旧訓練・運用CLI・監査ログ確認CLI）を、日常運用で
迷わず使えるように1つにまとめた**最終版の運用リファレンス**である。個々の
ツールの詳細は各MISSIONの手順書（末尾「関連文書」参照）にあり、本書は
それらを跨いだ「どの順番で・何を確認するか」に焦点を当てる。

---

## 1. ツール一覧（すべてlocalhost限定・人が明示的に実行）

| ツール | 役割 | 副作用 |
|---|---|---|
| `app.py` | AI Hive OS本体（`host=127.0.0.1`固定） | - |
| `hive_status.py` | 状態確認（`GET /`・`GET /api/logs`・DB読み取り専用チェック・トークン環境変数の設定有無） | なし |
| `hive_backup.py create` | `ai_company.db`の安全なバックアップ作成 | `backups/`へ新規ディレクトリ作成のみ |
| `hive_backup.py verify` | 既存バックアップの検証(ハッシュ・整合性・外部キー) | なし(読み取り専用) |
| `hive_backup.py restore-test` | 検証済みバックアップの一時領域への隔離復旧訓練 | なし(一時領域は訓練後に自動削除。実DBは変更しない) |
| `hive_ops.py` | 状態確認+(任意で)バックアップ検証を一貫した表示でまとめて実行 | なし |
| `hive_admin.py` | admin権限で監査ログ(`audit_logs`)を参照 | **あり**(呼び出しごとに`audit_logs`へ1件記録される。MISSION 013以来の仕様) |

いずれも常駐・cron・launchd・バックグラウンド自動実行ではない。人が
ターミナルで明示的にコマンドを打ったときだけ動作する。

---

## 2. 通常確認の順序（日常のヘルスチェック）

サーバーを起動した後や、作業を再開するときは、以下の順で確認する。

```bash
# 1. まとめて確認する(最も手軽)
python hive_ops.py
```

`hive_ops.py`は内部で`hive_status.py`の4項目をそのまま実行する
（`root_page`・`logs_api`・`database`・`token_env_presence`）。「総合判定: OK」
であれば、サーバー・DBともに正常に稼働している。

直近のバックアップの健全性も一緒に確認したい場合は、`--verify-backup`を
付ける（新規作成・復元は行わない。既存バックアップの検証のみ）。

```bash
# 2. 直近のバックアップも一緒に検証する
python hive_ops.py --verify-backup backups/backup_<日時>_<suffix>
```

`token_env_presence`が`NG`でも、それだけでは異常ではない（3章参照）。

---

## 3. 異常時の切り分け

`hive_ops.py`（または`hive_status.py`単体）の結果に応じて、以下の順で
切り分ける。

### 3.1 `root_page`・`logs_api` がNG

- `http://127.0.0.1:5050 へ接続できませんでした` と表示される場合:
  `app.py`のプロセスが起動しているか、ポート5050を他プロセスが使って
  いないかを確認する（`lsof -i :5050`等）
- HTTPステータスが200以外・レスポンス内容が想定外の場合:
  `app.py`が別バージョンのコードで起動していないか、起動時のログに
  エラーが出ていないかを確認する

### 3.2 `database` がNG

- `DBファイルが見つかりません`: `ai_company.db`の配置場所・作業ディレクトリを
  確認する
- `整合性チェックに失敗しました`・`integrity_check`が`ok`以外: DBファイルの
  破損の可能性がある。5章の復旧前チェックリストへ進む
- `不足テーブル=[...]`: 想定テーブル（`work_logs`・AI Hive 7テーブル・
  `audit_logs`）のいずれかが欠落している。誤って別のDBファイルを参照して
  いないか、`hive_db.init_hive_schema()`が実行されているかを確認する

### 3.3 `token_env_presence` がNG

- これは**異常ではない**。このCLIを実行しているターミナル自身に
  `AI_HIVE_READ_TOKEN`等が設定されていないだけであり、`app.py`を起動して
  いる別ターミナルの設定状態とは無関係（総合判定にも含まれない参考情報）
- Hive API（`/api/employees`等）やhive_admin.py・hive_backup.pyの認証で
  問題が起きている場合は、**サーバーを起動しているターミナル**の環境変数を
  直接確認すること（`docs/MISSION011_local_auth_runbook.md`参照）

### 3.4 `backup_verify` がNG（`--verify-backup`指定時）

- `記録済みハッシュ一致: いいえ`: バックアップファイルが作成後に変更されて
  いる可能性がある。そのバックアップは信頼せず、より古い別のバックアップで
  再検証するか、新たに`hive_backup.py create`でバックアップを取り直す
- `backups/ 配下以外のパスは扱えません` / `指定されたバックアップが
  見つかりません`: 指定したパスを再確認する（誤入力の可能性が高い）
- 整合性・外部キーチェックが異常: そのバックアップ自体が壊れている。同様に
  そのバックアップは使わず、別世代のバックアップで確認する

---

## 4. バックアップ検証（詳細）

```bash
# 単体で検証する場合
python hive_backup.py verify backups/backup_<日時>_<suffix>

# 状態確認と合わせて一貫した表示で確認する場合(推奨)
python hive_ops.py --verify-backup backups/backup_<日時>_<suffix>
```

- 検証は完全に読み取り専用。バックアップ元・実DBのいずれも変更しない
- 確認するのは「ハッシュ一致」「`PRAGMA integrity_check`が`ok`」「外部キー
  整合性に違反なし」の3点（詳細は`docs/MISSION016_backup_recovery_runbook.md`
  3章）
- さらに一歩進んで「実際に複製して中身まで正しく展開できるか」を確認したい
  場合は、隔離復旧訓練を使う（一時領域のみ、実DBには一切触れない）:

```bash
python hive_backup.py restore-test backups/backup_<日時>_<suffix>
```

詳細は`docs/MISSION017_isolated_restore_drill_runbook.md`を参照。

---

## 5. 復旧前チェックリスト

障害が疑われ、実際に復旧を検討する段階になったら、実行前に必ず以下を
確認する。**このチェックリストを満たすことは「復旧してよい」ことを
意味しない。5章はあくまで判断材料を揃える手順であり、実復元の可否は
6章の承認プロセスに従うこと。**

- [ ] `python hive_ops.py` で現在のサーバー・DBの状態を記録した
      （`root_page`・`logs_api`・`database`それぞれの結果）
- [ ] 候補となるバックアップすべてに対し `python hive_ops.py --verify-backup
      <対象>`（または`hive_backup.py verify`）を実行し、「総合判定: OK」の
      ものを洗い出した
- [ ] 洗い出したバックアップのうち、最も新しく「総合判定: OK」なものに
      対して `python hive_backup.py restore-test <対象>` を実行し、実際に
      中身まで正しく複製・展開できることを確認した（一時領域のみ、実DBは
      変更しない）
- [ ] 各バックアップの`metadata.json`の`created_at`・`table_row_counts`を
      比較し、どの時点まで遡ると何件のデータが失われるかを把握した
      （`work_logs`・AI Hiveの7テーブル・`audit_logs`それぞれ）
- [ ] 復元対象ファイル・バックアップ日時・復元先（本番を直接上書きするか、
      別名で並行稼働させて比較するか）・サーバー停止手順・復元後の動作
      確認手順（既存135テストの再実行を含む）を文書化した
- [ ] 復元によって失われるデータの内容と、それを許容できるかを整理した

---

## 6. 復元には別途の個別承認が必要であること

- **本MISSION以降のMISSION（021以降）を含め、実DB(`ai_company.db`)への
  復元・上書き・削除の機能は一切実装していない。**
  `hive_backup.py`が持つのは `create`（新規作成）・`list`（一覧表示、
  MISSION 021で追加）・`verify`（検証）・`restore-test`（一時領域への
  隔離復旧訓練）のみであり、いずれも実DBを書き換えることはできない
- 実際に本番DBを復旧する場合は、5章のチェックリストをすべて満たした上で、
  利用者の明示的な個別承認を得てから、別MISSIONとして計画・実施すること
- 5章のチェックリストや`restore-test`で「総合判定: OK」を確認できたことは、
  あくまで「バックアップの中身が壊れていない・正しく複製できる」ことの
  確認に過ぎず、実復元の実施可否そのものを承認するものではない

---

## 7. 監査ログ確認CLI（`hive_admin.py`）について

`hive_admin.py`（`docs/MISSION015_admin_cli_runbook.md`）はadmin権限で
`audit_logs`を参照するツールであり、**呼び出しのたびに`audit_logs`へ1件
記録するという副作用を持つ**（MISSION 013以来の仕様どおり）。日常の
ヘルスチェック（2章）やバックアップ検証（4章）では使わず、「直近の
認証失敗・権限不足・レート制限・admin操作を実際に確認したいとき」だけ
individually使うこと。トークンの安全な取り扱いは同手順書を参照。

---

## 8. 統合検証で確認したこと（本MISSIONでの実施内容）

`test_integration.py`（一時DB・一時`backups_root`・モックHTTPのみを使用。
本番`ai_company.db`・実`backups/`・`work_logs`・`audit_logs`には一切
書き込まない）で、以下を確認した。

- 正常系: 状態確認→バックアップ作成→検証→隔離復旧訓練→`hive_ops.py`の
  一貫した確認、までの一連の流れがすべて成功すること
- `hive_admin.py`の正常系（モック通信のみ）が、トークンを一切出力に
  含めずに動作すること
- 改ざんされたバックアップが、`verify`・`restore-test`・`hive_ops.py`の
  いずれからも一貫して安全に拒否されること
- 破損したDBが、`hive_status.py`・`hive_ops.py`のいずれからも一貫して
  NGとして検出されること
- `backups/`配下から外れたパス・パストラバーサル・存在しないバックアップ
  指定が、`verify`・`restore-test`・`hive_ops.py`のいずれからも一貫して
  安全に拒否されること
- サーバー接続失敗が、`hive_status.py`・`hive_ops.py`で一貫してNGとなる
  こと
- `hive_admin.py`のトークン未設定・不正な件数指定が、ネットワーク通信を
  一切発生させずに安全に失敗すること、および401/403応答が安全に表示
  されること
- 一連の操作を通じて、一時コピーのハッシュが変化しないこと、いかなる
  出力にもテスト用トークンの値が含まれないこと
- 各テストの前後で、本番`ai_company.db`のハッシュと実`backups/`の
  ディレクトリ一覧が完全に一致すること（統合テスト自体が本番環境へ
  影響しないことの自己検証）

さらに、実際に稼働中の`app.py`（本番`ai_company.db`使用、ポート5050）に
対して、副作用のない範囲（`hive_status.py`・`hive_ops.py`・
`hive_backup.py verify`。いずれもHTTP面は`GET /`・`GET /api/logs`のみで
認証不要、DB面は読み取り専用）で実際にコマンドを実行し、「総合判定: OK」
となること、実行前後で本番DBのハッシュ・`audit_logs`件数が完全に一致する
ことを確認した。

---

## 9. 外部公開・外部AI接続とは無関係であること

- 本書・本MISSIONで追加した統合テストは、いずれもローカルのHTTPモック・
  一時ファイルへのアクセスのみで完結しており、実ネットワーク通信・外部
  公開は一切行っていない
- これまでのMISSION（009・014〜019）で維持してきた「localhost限定運用・
  外部公開なし・外部AI接続なし」の方針に一切影響しない

---

## 10. 関連文書

| MISSION | 文書 | 内容 |
|---|---|---|
| 009 | `docs/MISSION009_auth_design.md` | 認証・脅威モデルの設計 |
| 011 | `docs/MISSION011_local_auth_runbook.md` | ローカル認証運用手順 |
| 014 | `docs/MISSION014_local_audit_view_design.md` | 監査ログ運用画面の設計(未実装・設計のみ) |
| 015 | `docs/MISSION015_admin_cli_runbook.md` | `hive_admin.py`利用手順 |
| 016 | `docs/MISSION016_backup_recovery_runbook.md` | `hive_backup.py create/verify`手順 |
| 017 | `docs/MISSION017_isolated_restore_drill_runbook.md` | `hive_backup.py restore-test`手順 |
| 018 | `docs/MISSION018_status_check_runbook.md` | `hive_status.py`利用手順 |
| 019 | `docs/MISSION019_ops_cli_runbook.md` | `hive_ops.py`利用手順 |
| 020(本書) | `docs/MISSION020_final_ops_runbook.md` | 上記を横断した最終運用リファレンス |

---

## 11. まとめ（本MISSIONでの成果）

- `test_integration.py`（既存ローカル運用ツール群の統合結合テスト。
  一時DB・一時`backups_root`・モックHTTPのみを使用し、本番環境には一切
  影響しない）を追加した
- 新たな外部連携・画面・自動実行は一切追加していない
- 本書に、通常確認の順序・異常時の切り分け・バックアップ検証・復旧前
  チェックリスト・復元には別途の個別承認が必要であること・監査ログCLIの
  副作用に関する注意・統合検証の範囲と結果を整理した
