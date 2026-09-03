# AI Hive OS ローカル認証運用手順書（MISSION 011 / MISSION 012更新版）

本書は、MISSION 012で実装したread/write/admin 3階層のBearerトークン認証
を用いて、AI Hive API（新規Hive API：employees / missions / tasks /
metrics / reports / proposals / decisions）をlocalhost環境で安全に起動・
利用するための手順書である。**外部公開・外部AI接続は対象外。** それらを
行う場合は別途承認が必要（MISSION 009設計文書
`docs/MISSION009_auth_design.md` 3.6節参照）。

**旧方式（MISSION 010で導入した単一の `AI_HIVE_API_TOKEN`）は
MISSION 012で廃止されており、現在は使用しない。** 現在は
`AI_HIVE_READ_TOKEN` / `AI_HIVE_WRITE_TOKEN` / `AI_HIVE_ADMIN_TOKEN` の
3つの環境変数による権限分離方式のみを使用する。

---

## 0. 権限モデル（read / write / admin）

| 権限 | 環境変数 | 許可される操作 |
|---|---|---|
| read | `AI_HIVE_READ_TOKEN` | Hive APIの読み取り（GET）操作のみ |
| write | `AI_HIVE_WRITE_TOKEN` | 読み取り操作 ＋ 通常の登録・更新（POST/PATCH、`PATCH /api/proposals/<id>`を除く） |
| admin | `AI_HIVE_ADMIN_TOKEN` | write権限の操作 ＋ 管理操作（`PATCH /api/proposals/<id>`、意思決定の承認・却下に相当） |

上位権限は下位権限の操作も満たす（admin ⊇ write ⊇ read）。**利用目的に
対して必要最小限の権限のトークンだけを使うこと**（例：読み取りだけで
よい用途にadminトークンを使わない）。

### 重要な安全条件

- **3つのトークンには必ず異なる値を設定すること。** 2つ以上の権限に
  同じトークン値を設定すると、そのトークンがどの権限を表すか安全に
  一意判定できなくなる
- 上記のように安全に判定できない設定（重複値）が検出された場合、
  Hive API全体が**fail-closedで拒否**される（どのトークンを使っても
  401になる）
- `AI_HIVE_READ_TOKEN` / `AI_HIVE_WRITE_TOKEN` / `AI_HIVE_ADMIN_TOKEN` の
  **いずれか1つでも未設定**の場合も、Hive API全体が**fail-closedで
  拒否**される（部分的な設定では動作しない）
- 既存の `GET /` と `GET /api/logs` は引き続き認証・権限の対象外であり、
  上記の設定状況に関わらず常に従来どおり動作する

## 1. トークンを環境変数として一時的に設定する方法

3つのトークンは**その場限りのシェル環境変数としてのみ**設定し、ファイル
には一切書き出さない。3つには必ず異なる値を使うこと。

```bash
# シェルの現在のセッションにのみ設定される。ファイルには保存されない。
read -s -p "AI_HIVE_READ_TOKENを入力: " AI_HIVE_READ_TOKEN; echo
read -s -p "AI_HIVE_WRITE_TOKENを入力: " AI_HIVE_WRITE_TOKEN; echo
read -s -p "AI_HIVE_ADMIN_TOKENを入力: " AI_HIVE_ADMIN_TOKEN; echo
export AI_HIVE_READ_TOKEN AI_HIVE_WRITE_TOKEN AI_HIVE_ADMIN_TOKEN
```

- `read -s` は入力内容を画面に表示しない（シークレット入力向け）
- `export` したこれらの変数は、このシェルセッションとその子プロセス
  （後述の `python app.py`）にのみ有効。ターミナルを閉じれば自動的に
  消える
- 1回限りの起動であれば、`export`せず起動コマンドの先頭に付ける方法も
  安全（後述4節）。この方法は環境変数がその1コマンドのプロセスにしか
  渡らず、シェルの環境には残らない

## 2. トークンを残してはいけない場所（厳守）

以下のいずれにもトークンの実際の値を書き込まない・出力しない。

| 場所 | 注意点 |
|---|---|
| ソースコード（`app.py`、`hive_db.py`等） | ハードコード禁止。`os.environ.get(...)`で読むのみ |
| `.env`ファイル等の設定ファイル | 本プロジェクトでは`.env`運用自体を導入していない（MISSION 009設計文書4.1節「要承認事項」参照）。作成しない |
| SQLite DB（`ai_company.db`） | トークンをテーブルの値として保存しない |
| Git（コミット・コミットメッセージ・PR説明） | `git diff`/`git status`をcommit前に必ず確認し、トークン文字列が含まれていないことを確認する |
| README・設計文書・本手順書 | サンプル・実行例には実トークンではなくシェル変数展開（`$AI_HIVE_READ_TOKEN`等）や説明文のみを記載する |
| ログ（Flask/Werkzeugの標準出力、リダイレクトしたログファイル） | Werkzeugの標準アクセスログはメソッド・パス・ステータスのみを出力し、ヘッダー値は出力しない（MISSION010/012で実機確認済み）。独自にログを追加する場合はAuthorizationヘッダーの値を出力しないよう実装すること |
| スクリーンショット・画面共有・チャット報告 | ターミナル操作の様子を画面共有・スクリーンショットする際は、`read -s`で非表示入力にする、または実行後の履歴（`history`）にトークンが残らないよう配慮する |
| シェルのコマンド履歴 | `AI_HIVE_READ_TOKEN=xxxx python app.py` のようにコマンドラインへ直接値を書くと、シェル履歴（`.bash_history`/`.zsh_history`）に残る場合がある。1節の`read -s`方式、または対話的に`export`する方式を推奨する |

## 3. localhost・既定ポート5050での起動方法

AI Hiveはホストを`127.0.0.1`に固定しており、`0.0.0.0`へバインドすることは
ない（`app.py`側でハードコード済み、MISSION 008で導入）。

```bash
cd /Users/shirahamatakuya/Desktop/AI-
source venv/bin/activate

# 1節でAI_HIVE_READ_TOKEN / AI_HIVE_WRITE_TOKEN / AI_HIVE_ADMIN_TOKEN を
# export済みの場合（3つとも異なる値で設定されていること）
python app.py
```

既定ポートは`5050`。`http://127.0.0.1:5050` で待受する。ポート5000は
macOSのAirPlay Receiverが使用しているため使用しない方針（MISSION007/008
で確認・決定済み）。別ポートで起動したい場合のみ `PORT` 環境変数を使う
（例：`PORT=5077 python app.py`）。

## 4. `Authorization: Bearer` を使った安全なAPI呼び出し例

トークンをコマンドライン上にリテラルで書かず、環境変数展開を使う。
用途に応じて必要最小限の権限のトークンを選ぶこと（read操作にadmin
トークンを使わない等）。

```bash
# 読み取り例（employees一覧取得） — readトークンで十分
curl -s -H "Authorization: Bearer $AI_HIVE_READ_TOKEN" \
  http://127.0.0.1:5050/api/employees

# 通常の書き込み例（missions登録） — writeトークンを使う
curl -s -X POST \
  -H "Authorization: Bearer $AI_HIVE_WRITE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"サンプルMISSION"}' \
  http://127.0.0.1:5050/api/missions

# 管理操作の例（提案の承認/却下） — admin専用
curl -s -X PATCH \
  -H "Authorization: Bearer $AI_HIVE_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}' \
  http://127.0.0.1:5050/api/proposals/1
```

トークンなし、誤ったトークン、権限不足（例：readトークンで書き込み
APIを呼ぶ）、環境変数の未設定・重複設定のいずれの場合も、新規Hive API
は`401`または`403`の統一JSON形式のみを返す
（`{"status":"error","message":"認証に失敗しました。"}` または
`{"status":"error","message":"権限が不足しています。"}`。詳細な失敗理由
は返さない設計。MISSION 009/010/012参照）。

既存の `GET /` と `GET /api/logs` は認証対象外であり、Authorization
ヘッダーなしで従来通り利用できる。

```bash
curl -s http://127.0.0.1:5050/api/logs
```

## 5. 利用後の停止と環境変数の破棄

```bash
# サーバー停止（フォアグラウンドで起動していればCtrl+C）
# バックグラウンド起動していた場合はプロセスを確実に停止する
pkill -f "python app.py"

# このシェルセッションから3つの一時トークンを破棄する
unset AI_HIVE_READ_TOKEN AI_HIVE_WRITE_TOKEN AI_HIVE_ADMIN_TOKEN
```

シェルセッション自体を閉じれば`export`した環境変数も自動的に破棄される
が、同一セッションを使い続ける場合は明示的に`unset`することを推奨する。

## 6. 外部公開・外部AI接続について

本手順書はlocalhost限定運用のみを対象とする。GPT・Gemini等の外部AIへの
接続、インターネットへの公開、ポート開放、リバースプロキシの導入は、
**本手順書の範囲外であり、実施する場合は事前の明示的な承認が必要**
（MISSION 009設計文書 `docs/MISSION009_auth_design.md` 3.6節・4.1節、
MISSION 010の禁止事項を参照）。
