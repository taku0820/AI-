# localhost限定 監査ログ確認CLI 運用手順書（MISSION 015）

対象ファイル: `hive_admin.py`（本MISSIONで追加した唯一の実装ファイル）

作成時点のブランチ: `claude/company-dashboard-sqlite-mjoexa`
作成時点のHEAD: `35d5df9ce4a95b3aaf9a5f2d1e6dad84b69f8fd1`（MISSION 014完了時点）

本CLIは、`docs/MISSION014_local_audit_view_design.md` で「画面実装前に
必要」と整理した判断事項のうち、ブラウザUIを一切使わない代替手段として、
`GET /api/audit-logs`（admin専用・読み取り専用API）をターミナルから安全に
呼び出すためのものである。ブラウザUI・ダッシュボード・Cookie・セッション・
`localStorage` は本MISSIONでは一切実装していない。

---

## 1. localhost限定であること

- `hive_admin.py` の接続先は `http://127.0.0.1:5050` にコード上で固定
  されている。CLI引数・環境変数で接続先を変更するオプションは存在
  しない
- サーバー（`app.py`）自体も `host="127.0.0.1"` 固定・`0.0.0.0`
  バインドなしのまま運用する（MISSION 008以降の方針を継続）
- 本CLIは同一Mac上でサーバーが起動していることを前提とし、LAN・
  インターネット越しの利用は想定しない

---

## 2. サーバー側で必要な環境変数（3本すべて）

サーバー（`app.py`）を起動するには、`hive_db.require_permission` の
fail-closed方針により、以下の3つの環境変数が**すべて**設定されている
必要がある（いずれか1つでも未設定・空だと、Hive API全体が401を返す）。

| 環境変数 | 用途 |
|---|---|
| `AI_HIVE_READ_TOKEN` | 読み取り専用トークン |
| `AI_HIVE_WRITE_TOKEN` | 読み書きトークン |
| `AI_HIVE_ADMIN_TOKEN` | 管理者トークン（本CLIが利用するのはこれ） |

この3本はサーバープロセスを起動する端末・シェルで設定する（CLI側とは
別）。詳細は `docs/MISSION011_local_auth_runbook.md` を参照。

---

## 3. CLI側では `AI_HIVE_ADMIN_TOKEN` を一時環境変数として使う

- `hive_admin.py` はコマンドライン引数でトークンを受け取らない。必ず
  環境変数 `AI_HIVE_ADMIN_TOKEN` から読み取る
- CLIを実行する端末（サーバーを起動した端末と同じでも別のターミナル
  タブでもよい）で、**その場限りの一時環境変数として**設定することを
  推奨する（`.bashrc`/`.zshrc`等の恒久設定ファイルには書かない）

```bash
# その場限りの一時環境変数として設定する（シェルの現在のセッションのみ）
export AI_HIVE_ADMIN_TOKEN="<admin token>"
```

---

## 4. 実トークンをシェル履歴・スクリーンショット・Git・ファイルへ残さない

- トークンの値そのものをコマンドライン引数として打たない（`export`の
  代入文自体もシェル履歴に残る点に注意し、可能であれば下記4.1のように
  履歴に残さない方法を使う）
- `hive_admin.py` はトークンをコマンドライン引数・標準出力・標準
  エラー出力・例外メッセージ・ファイルのいずれにも出力しない設計に
  なっている（出力されるのはエンドポイント名・HTTPステータス・
  `audit_logs` の内容のみ）
- ターミナルの画面をスクリーンショット・画面共有する際は、`export`
  実行直後の行（トークン文字列を含む行）が画面に映らないよう、
  実行前にターミナルをクリアする、または該当行をスクロールで隠す
- `.env`や設定ファイルにトークンを書き出さない。本MISSIONでも実
  トークン・`.env`ファイルは一切作成・保存していない
- `git status`・`git diff --cached` で、トークンを含む一時ファイルが
  ステージされていないことをコミット前に必ず確認する

### 4.1 シェル履歴に残さずに設定する例（任意・推奨）

```bash
# 行頭にスペースを入れると、HISTCONTROL=ignorespace設定時は履歴に残らない
# (bash/zshの設定に依存するため、確実に消したい場合は5章の破棄手順を使う)
 export AI_HIVE_ADMIN_TOKEN="<admin token>"
```

---

## 5. CLIの安全な実行例

前提: 別ターミナルで `app.py` が3本の環境変数付きで起動済み（ポート
5050、`host=127.0.0.1`）であること。

```bash
# 1. このターミナルにのみadminトークンを設定する
export AI_HIVE_ADMIN_TOKEN="<admin token>"

# 2. 既定件数(50件)で監査ログを新しい順に確認する
python hive_admin.py

# 3. 件数を指定する(1〜100の範囲。100件を超える指定は自動的に100件に
#    丸められ、0以下・非整数はエラーになる)
python hive_admin.py --limit 20

# 4. 確認が終わったら、必ずこのターミナルの環境変数を破棄する(6章)
unset AI_HIVE_ADMIN_TOKEN
```

失敗時の表示例（いずれもトークン・Authorizationヘッダーの値は含まない）:

```
エラー: 環境変数 AI_HIVE_ADMIN_TOKEN が設定されていません。admin権限のトークンを設定してから再実行してください。
エラー: --limit には正の整数を指定してください。
エラー: 権限が不足しています。
エラー: 認証に失敗しました。
エラー: リクエストが多すぎます。しばらく待ってから再試行してください。
エラー: http://127.0.0.1:5050 へ接続できませんでした。サーバー(hive_admin.pyが利用するlocalhost:5050のAPI)が起動しているか確認してください。
```

---

## 6. サーバー停止後・利用後の環境変数破棄方法

CLIの利用が終わったら、admin権限のトークンをターミナルのプロセス環境に
残さないよう、以下のいずれかを実施する。

```bash
# そのターミナルタブ内でCLIの利用を終える場合
unset AI_HIVE_ADMIN_TOKEN

# サーバー自体を止める場合(別ターミナルでCtrl+C、または該当プロセスをkill)
# サーバー停止後は、サーバー側で使っていた3本の環境変数
# (AI_HIVE_READ_TOKEN / AI_HIVE_WRITE_TOKEN / AI_HIVE_ADMIN_TOKEN)も
# 同様にunsetすることを推奨する
unset AI_HIVE_READ_TOKEN AI_HIVE_WRITE_TOKEN AI_HIVE_ADMIN_TOKEN
```

- 作業を完全に終える場合は、該当のターミナルタブ・セッション自体を
  閉じることで、そのプロセス環境に残った変数も確実に消える
- `env` / `printenv` コマンドで、意図せずトークンが残っていないかを
  作業終了時に確認する習慣を推奨する

---

## 7. 外部公開・外部AI接続・ブラウザUIには別途承認が必要

- 本CLIはlocalhost限定運用を前提とする。`docs/MISSION009_auth_design.md`
  3.6節・`docs/MISSION014_local_audit_view_design.md` 7章の方針をそのまま
  引き継ぐ
- 本CLI・本APIをLAN・インターネットへ公開すること、GPT・Geminiなどの
  外部AIから直接（またはこのCLI経由で間接的に）アクセスさせることは、
  本MISSIONでは一切想定・許可しない
- ブラウザ向けの運用画面（ダッシュボードUI）の実装も本MISSIONの範囲外
  であり、`docs/MISSION014_local_audit_view_design.md` 3章で整理した
  認証方式の判断（候補A/B/C）についてユーザーの承認を得た上で、
  別途MISSIONとして着手する
- 上記のいずれかを行う場合も、必ず利用者の明示的な承認を得てから
  着手する

---

## 8. まとめ（本MISSIONでの成果）

- `hive_admin.py`（localhost:5050固定・admin専用・読み取り専用・
  `GET /api/audit-logs`のみを呼び出すCLI）を追加した
- 本手順書に、必要な環境変数・トークンの安全な取り扱い・実行例・
  破棄手順・外部公開時の承認要件を整理した
- ダッシュボードUI・Cookie・セッション・`localStorage`は実装していない
