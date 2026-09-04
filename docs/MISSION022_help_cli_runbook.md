# localhost限定 統合ヘルプ／ナビゲーションCLI 利用手順書（MISSION 022）

対象ファイル: `hive_help.py`（本MISSIONで追加した唯一の実装ファイル。
既存の `hive_status.py`・`hive_ops.py`・`hive_backup.py`・`hive_admin.py`の
実装には一切手を加えていない）

作成時点のブランチ: `claude/company-dashboard-sqlite-mjoexa`
作成時点のHEAD: `45bb12d324af8d7991261a7d944839213bfe9fbf`（MISSION 021完了時点）

---

## 1. 位置づけ

`hive_help.py` は新しい機能を持たない。既存の運用ツール群
（`hive_status.py`・`hive_ops.py`・`hive_backup.py`の`list`/`verify`）を
「どれをどう使えばよいか迷わない」よう1つの入口からまとめて案内・
呼び出しするだけの薄いディスパッチャである。実体はすべて各モジュールの
既存の`main()`関数をそのまま呼び出しており、本ファイル独自のネットワーク
通信・DB操作・ファイル書き込みは一切ない。

```bash
python hive_help.py
```

引数なしで実行すると、利用可能な操作の一覧（メニュー）を表示するだけで
終了する。**この時点では何も実行されない**（ネットワーク通信・DB操作・
バックアップの作成/復元/削除/検証のいずれも発生しない）。`--help`/`-h`も
同様に、argparseの使い方表示のみで何も実行しない。

---

## 2. 操作一覧

| サブコマンド | 実体 | 副作用 |
|---|---|---|
| `python hive_help.py status` | `hive_status.py`の状態確認をそのまま実行 | なし |
| `python hive_help.py ops` | `hive_ops.py`の状態確認をそのまま実行 | なし |
| `python hive_help.py ops --verify-backup <path>` | `hive_ops.py`の状態確認+指定バックアップの検証をそのまま実行 | なし(読み取り専用) |
| `python hive_help.py backup-list` | `hive_backup.py list`をそのまま実行 | なし(DBファイルすら開かない) |
| `python hive_help.py backup-verify <path>` | `hive_backup.py verify <path>`をそのまま実行 | なし(読み取り専用) |
| `python hive_help.py admin-info` | `hive_admin.py`についての案内文を表示するだけ | なし(`hive_admin.py`は一切呼び出さない) |

上記いずれのサブコマンドも、**利用者が明示的にサブコマンドを指定した
場合にのみ**実行される。引数なし実行やhelp表示だけでは一切実行されない。

### 2.1 なぜ`hive_admin.py`を直接実行しないのか

`hive_admin.py`（監査ログ確認CLI、`docs/MISSION015_admin_cli_runbook.md`）
は、成功する読み取り専用の呼び出しであっても、**呼び出しのたびに
`audit_logs`テーブルへ1件記録するという副作用を持つ**（MISSION 013以来の
仕様）。この副作用は、状態確認やバックアップ検証（いずれも本質的に
副作用ゼロ）とは性質が異なるため、`hive_help.py`からは自動実行・初期
実行・一括実行のいずれも行わない。`admin-info`サブコマンドは、この違いを
説明した上で、必要な場合に利用者が別途手動で`hive_admin.py`を実行する
方法を案内するだけであり、`hive_admin.py`のコード自体を一切呼び出さない
（`import hive_admin`すら行っていない）。

---

## 3. 各操作の副作用の有無（まとめ）

- **副作用ゼロ**: `status`・`ops`（`--verify-backup`の有無を問わず）・
  `backup-list`・`backup-verify`・`admin-info`・引数なし実行・`--help`
  — このCLIから実行できる操作は、すべて読み取り専用または案内表示のみ
- **副作用あり（このCLIからは呼び出せない）**: `hive_admin.py`の実行
  （`audit_logs`へ1件記録）、`hive_backup.py create`（新規バックアップ
  作成）、`hive_backup.py restore-test`（一時領域への隔離復旧訓練）。
  これらが必要な場合は、利用者が各ツールを直接実行すること
  （`docs/MISSION015_admin_cli_runbook.md`・
  `docs/MISSION016_backup_recovery_runbook.md`・
  `docs/MISSION017_isolated_restore_drill_runbook.md`参照）

---

## 4. 異常時の確認順序

`hive_help.py status` または `hive_help.py ops` の結果に応じて、以下の
順で切り分ける（詳細は`docs/MISSION020_final_ops_runbook.md` 3章と同一）。

1. `root_page`・`logs_api`がNG → `app.py`のプロセスが起動しているか、
   ポート5050を確認する
2. `database`がNG → `ai_company.db`の配置・破損・想定テーブルの欠落を
   確認する（`docs/MISSION018_status_check_runbook.md` 6章参照）
3. `token_env_presence`がNG → これは異常ではない（このCLIを実行して
   いるターミナル自身の環境変数設定を示すだけの参考情報）
4. バックアップの健全性を確認したい場合は
   `hive_help.py backup-list` で候補を確認し、
   `hive_help.py backup-verify <path>` または
   `hive_help.py ops --verify-backup <path>` で検証する

---

## 5. 実復元には別途の個別承認が必要であること

- `hive_help.py`からは、実DB(`ai_company.db`)への復元・上書き・削除を
  行う経路は一切存在しない（そもそも呼び出せるサブコマンドが4つの
  読み取り専用操作＋案内表示のみに限定されている）
- `hive_backup.py restore-test`（隔離復旧訓練、一時領域のみ）や、実際の
  本番DB復旧についても、`hive_help.py`からは実行できない。これらが
  必要な場合は、利用者が直接各ツールを実行し、実復元については
  `docs/MISSION020_final_ops_runbook.md` 5〜6章の復旧前チェックリストを
  満たした上で、**別途の明示的な個別承認**を得てから行うこと

---

## 6. 常駐・外部公開との無関係性

- `hive_help.py`は、人が実行するたびに1回だけ動作して終了する。常駐・
  cron・launchd・バックグラウンド自動実行の仕組みは一切持たない
- 対象は`http://127.0.0.1:5050`のローカルサーバーと、プロジェクト内の
  `ai_company.db`・`backups/`に限定されており、それ以外への通信・外部
  公開・外部通知は一切行わない（内部で呼び出す`hive_status.py`・
  `hive_ops.py`・`hive_backup.py`自体がこの制約を持つため）
- これまでのMISSION（009・014〜021）で維持してきた
  「localhost限定運用・外部公開なし・外部AI接続なし」の方針に一切
  影響しない

---

## 7. まとめ（本MISSIONでの成果）

- `hive_help.py`（既存の安全な運用CLI群を案内・呼び出しする薄い
  ディスパッチャ。新しい操作は追加していない）を追加した
- 引数なし実行・`--help`表示・`admin-info`のいずれも、ネットワーク通信・
  DB操作・バックアップの作成/復元/削除/検証を一切行わない
- 本書に、操作一覧・各操作の副作用の有無・異常時の確認順序・実復元に
  必要な個別承認・常駐や外部公開との無関係性を整理した
