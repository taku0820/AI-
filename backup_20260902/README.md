# バックアップ (2026-09-02作成, AI Hive OS基盤追加前)

AI Hive OS基盤追加(MISSION 005)の実装前に取得したバックアップです。

## 内容

- `app.py.bak` : 変更前の app.py
- `init_db.py.bak` : 変更前の init_db.py (今回は無変更)
- `requirements.txt.bak` : 変更前の requirements.txt (今回は無変更)

## 復元方法

```bash
cp backup_20260902/app.py.bak app.py
cp backup_20260902/init_db.py.bak init_db.py
cp backup_20260902/requirements.txt.bak requirements.txt
rm -f hive_db.py hive_api.py
```

または git 上で本コミットの直前のコミットに戻すことでも復元できます。

```bash
git log --oneline
git checkout <このMISSION実装コミットの直前のハッシュ> -- app.py init_db.py requirements.txt
```

## 注意

`ai_company.db` はこのリポジトリには含まれていません(.gitignore対象、
実行環境のローカルファイル)。Mac mini実機での適用時は、本MISSIONの変更を
適用する前に、実機の `ai_company.db` を別途手動でコピーしてバックアップ
してください(例: `cp ai_company.db ai_company.db.bak_20260902`)。
新規テーブルは `CREATE TABLE IF NOT EXISTS` で追加されるため、
既存の `work_logs` テーブルとデータは変更されません。
