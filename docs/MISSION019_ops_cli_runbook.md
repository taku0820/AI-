# localhost限定 日常運用保守CLI 手順書（MISSION 019）

対象ファイル: `hive_ops.py`（本MISSIONで追加した唯一の実装ファイル。
既存の `hive_status.py`・`hive_backup.py` をそのまま呼び出す薄い
ラッパーであり、両者の実装には一切手を加えていない）

作成時点のブランチ: `claude/company-dashboard-sqlite-mjoexa`
作成時点のHEAD: `2515759d39654c2d4cd6f7d4cd3e980e9694ac76`（MISSION 018完了時点）

---

## 1. 位置づけ

`hive_ops.py` は新しい機能を持つツールではなく、既存の

- `hive_status.py`（MISSION 018: 副作用のない状態確認）
- `hive_backup.py verify`（MISSION 016: 既存バックアップの読み取り専用検証）

を、人が明示的にコマンドを打ったときだけ、**同じ表示形式でまとめて**
確認できるようにする薄いラッパーである。

- **人が明示的に起動したときだけ動く。** 常駐プロセス・cron・
  launchd・バックグラウンド自動実行・外部通知は一切実装していない
- 状態確認のロジック（接続先固定・副作用ゼロ等）は `hive_status.py`
  側にそのまま従う。`hive_ops.py` は独自のネットワーク通信を追加しない
- バックアップに関して行うのは「指定した既存バックアップの検証」だけ。
  新規バックアップの作成・実DBへの復元・バックアップの削除は
  `hive_ops.py` からは一切実行できない（コード上、`hive_backup.create_backup`・
  `hive_backup.restore_test` を呼び出す経路が存在しない）

---

## 2. 通常確認（日常的なヘルスチェック）

```bash
python hive_ops.py
```

`hive_status.py` の4項目（`root_page`・`logs_api`・`database`・
`token_env_presence`）をそのまま実行し、一貫した書式で表示する。詳細は
`docs/MISSION018_status_check_runbook.md` を参照。

出力例:

```
[OK] root_page (GET /): OK (HTTP 200)
[OK] logs_api (GET /api/logs): OK (3件, HTTP 200)
[OK] database (ai_company.db): integrity_check=ok, foreign_key_violations=0
      audit_logs: 3件
      ...
      work_logs: 3件
[NG] token_env_presence (このCLIプロセス自身の環境変数): AI_HIVE_READ_TOKEN=未設定, ...
      ※ 値そのものは表示していません。サーバー側の設定確認ではなく、参考情報のため総合判定には含めません。
総合判定: OK
```

終了コードは総合判定が `OK` のとき `0`、`NG` のとき `1`。

---

## 3. バックアップ検証（既存バックアップの健全性確認）

```bash
python hive_ops.py --verify-backup backups/backup_20260904_213645_374d29
```

状態確認の4項目に加え、指定したバックアップの検証結果
（`hive_backup.verify_backup()` と同じ内容: ハッシュ一致・整合性・外部キー
整合性）を、同じ書式の1行として追加表示する。バックアップの新規作成・
復元は行わない（このコマンドは既存バックアップを検証するだけ）。

出力例（末尾の1行が追加される）:

```
[OK] root_page (GET /): OK (HTTP 200)
[OK] logs_api (GET /api/logs): OK (3件, HTTP 200)
[OK] database (ai_company.db): integrity_check=ok, foreign_key_violations=0
      ...
[NG] token_env_presence (...): ...
[OK] backup_verify (backups/backup_20260904_213645_374d29): hash_matches=True, integrity_check=ok, foreign_key_check_ok=True
総合判定: OK
```

検証対象として渡せるのは `backups/` 配下の既存バックアップディレクトリ、
またはそのDBファイルのみ。それ以外のパス・存在しないバックアップは、
`hive_backup.verify_backup()` の既存の安全策により例外を出さず
`[NG] backup_verify (...): <安全な理由>` として表示され、総合判定は
`NG`（終了コード1）となる。

まだバックアップを作成していない場合は、先に `hive_backup.py create`
（`docs/MISSION016_backup_recovery_runbook.md` 参照）でバックアップを
作成してから、そのディレクトリを `--verify-backup` に渡すこと。

---

## 4. 異常時に確認する順序

サーバー・DBの様子がおかしいと感じたときは、以下の順で確認する。

1. **`python hive_ops.py` を実行する。**
   - `root_page`・`logs_api` がNGの場合: `app.py` プロセスが起動して
     いるか、ポート5050を使っているかを確認する
   - `database` がNGの場合: `ai_company.db` の破損・想定テーブルの
     欠落の可能性がある。詳細は表示された `detail` を確認する
   - `token_env_presence` のNGは参考情報であり、単独ではサーバーの
     異常を意味しない（このCLI自身の端末に環境変数が未設定なだけの
     ことが多い）
2. **直近の正常なバックアップを `python hive_ops.py --verify-backup <対象>`
   で検証する。**
   - 「総合判定: OK」であれば、そのバックアップの中身は健全であり、
     いざというときの復旧候補になり得ることが確認できる
   - 「総合判定: NG」（`backup_verify` がNG）の場合、そのバックアップは
     信頼できない。より古い別のバックアップで再度検証するか、新たに
     `hive_backup.py create` でバックアップを取り直す
3. **上記の結果を踏まえて、原因調査・対応方針を検討する。**
   `docs/MISSION016_backup_recovery_runbook.md` 5章（障害発生時にまず
   行うこと）・`docs/MISSION017_isolated_restore_drill_runbook.md`
   5章（訓練成功・失敗時の確認項目）も合わせて参照する

---

## 5. 復元を実施しないこと

- `hive_ops.py` は、状態確認とバックアップ検証（いずれも読み取り専用）
  しか行わない。**実DB(`ai_company.db`)への復元・上書き・削除の機能は
  一切実装していない。**
- `--verify-backup` で「総合判定: OK」を確認できたとしても、それは
  「そのバックアップの中身が壊れていないこと」の確認に過ぎず、実際に
  本番DBを復旧して良いという判断・承認を意味しない

---

## 6. 実復元には別途の個別承認が必要であること

実際に本番DBを復旧する場合は、`docs/MISSION016_backup_recovery_runbook.md`
6章の確認項目（復元対象ファイル・バックアップ日時・復元先・サーバー
停止手順・復元後の動作確認手順・失われるデータの許容可否）をすべて
満たした上で、利用者の明示的な個別承認を得てから、別MISSIONとして
計画・実施すること。`docs/MISSION017_isolated_restore_drill_runbook.md`
の隔離復旧訓練（`hive_backup.py restore-test`、一時領域のみを使用）は
実復元そのものではなく、あくまで訓練であることも改めて確認しておく。

---

## 7. 安全上の制約（まとめ）

| 項目 | 内容 |
|---|---|
| 接続先 | `http://127.0.0.1:5050` 固定（`hive_status.py`側の実装に準拠）。CLI引数・環境変数での変更不可 |
| リダイレクト | 一切追跡しない |
| Authorizationヘッダー | 送信しない（対象が認証不要の既存2エンドポイントのみのため） |
| 常駐・自動実行 | cron・launchd・バックグラウンド実行・外部通知は一切実装していない。人が明示的にコマンドを実行したときだけ動く |
| バックアップ作成・復元・削除 | 一切実行できない（呼び出し経路がコード上存在しない）。行うのは指定バックアップの読み取り専用検証のみ |
| 実DB(`ai_company.db`) | `hive_status.py`のDBチェックと同様、読み取り専用接続でのみアクセスする |
| トークン | 状態確認・バックアップ検証のいずれもトークンを必要とせず、送信・表示・保存しない |
| 失敗時の挙動 | 例外トレースバックを外へ漏らさず、`[NG] <項目名>: <安全な理由>` の形式で表示し、終了コード1を返す |

---

## 8. 外部公開・外部AI接続とは無関係であること

- `hive_ops.py` はローカルのHTTPチェック(`127.0.0.1:5050`固定)と
  ローカルファイルの読み取り専用アクセスのみを行い、それ以外の外部
  通信は一切行わない
- 本機能の追加は、これまでのMISSION（009・014〜018）で維持してきた
  「localhost限定運用・外部公開なし・外部AI接続なし」の方針に一切
  影響しない

---

## 9. まとめ（本MISSIONでの成果）

- `hive_ops.py`（`hive_status.py`の状態確認と`hive_backup.py`の
  バックアップ検証を、一貫した表示形式でまとめて実行する薄いCLI）を
  追加した
- 常駐・cron・launchd・バックグラウンド自動実行・外部通知は実装して
  いない。バックアップの新規作成・復元・削除も実装していない
- 本手順書に、通常確認・バックアップ検証・異常時の確認順序・復元を
  実施しないこと・実復元に必要な個別承認・安全上の制約を整理した
