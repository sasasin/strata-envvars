# `STRATA_UPDATE_TRUSTED_KEYS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の更新フィードとエンジンコンポーネント署名を検証するとき、同梱の `strata_control/update_keys.json` に追加して信頼する公開鍵ファイルを指定します。主にローカル・テスト用フィードを検証する用途です。同梱鍵を置き換える設定ではなく、両方の鍵集合を使います。秘密鍵や署名方法はこの変数では指定しません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 追加鍵ファイルを読み込まず、同梱鍵だけを使う |
| 空文字 | `environ.get()` が空文字を返し、`if not path` でスキップされる。同梱鍵だけを使う。追加鍵が有効という注記も出ない |
| 空でない文字列 | その文字列を `pathlib.Path` に渡し、指す JSON ファイルを追加鍵として読む。文字列の真偽以外の値解釈や trim、環境変数内の `~` 展開はしない |
| 読めないファイル、不正な JSON、キー形式の不正 | `SignatureError`。黙ってキーを無視せず、呼び出し元の更新または検証を失敗させる |

JSON のトップレベルはキー配列、または `{"keys": [...]}` の形式です。各要素には `alg: "ed25519"`、32 byte 公開鍵の base64 文字列 `public`、およびその公開鍵の SHA-256 先頭 8 byte の小文字 hex と一致する `key_id` が必要です。追加鍵ファイルの文字コードは UTF-8（BOM も許容）です。重複 `key_id` は辞書に格納され、後から読んだ値が同じ ID の値を置きます。同じ ID は公開鍵から算出されるため、通常は同一公開鍵です。

## 有効になる条件

環境変数が空でないだけでは、その鍵が使用されるとは限りません。ファイルが有効な形式で、検証対象の署名の `key_id` が同梱鍵または追加鍵に含まれる必要があります。フィード検証では署名・期限・channel などの別の検査も続き、鍵が一致してもそれらを通過しなければ更新できません。

`strata update` / `strata components update` は更新処理の開始時に鍵を読みます。`strata update --check` も同じ信頼鍵を使ってフィードを検証します。エンジン起動時のコンポーネント署名検証では、署名付きコンポーネントを初めて検証するときに鍵を遅延読込し、プロセス内の verifier に登録します。一度登録された後にプロセス環境を変えても、その verifier は再読込されません。`docker/fetch-engines.py` も起動時に同じ helper から鍵を読み、取得したエンジンを検証します。

`packaging/install.sh` と `packaging/install.ps1` は `STRATA_INSTALL_TEST_TRUST=1` の場合に限り、作業ディレクトリへ取得した `test-trust.json` のパスを子の `strata update --check` に `STRATA_UPDATE_TRUSTED_KEYS` として設定します。これはインストーラー内のテスト用フィード検証です。

## 実行時の詳細

`load_trusted_keys()` はまず同梱鍵ファイルを読み、次に引数 `extra` が真ならそのファイル、そうでなければ環境変数の値を読みます。相対パスはプロセスの現在ディレクトリ基準です。追加鍵ファイルの読み込みや形式検査に失敗すると `SignatureError` となります。CLI の `strata update` 経路では stderr に `strata: ...` を出して終了コード 5 を返します。追加鍵が有効な通常出力モードでは、検証前に stderr に `note: trusting the extra keys in <path> (a test setup)` と表示します。`--output json` / `jsonl` ではこの注記を出しません。

鍵ファイルが有効でも、同梱鍵と追加鍵のどちらも読み込めず信頼鍵が空なら、フィード検証は `this build trusts no update key ...` で失敗し、何もダウンロードしません。署名が未知の鍵によるもの、または署名内容と一致しない場合も拒否します。

## 根拠

- `strata_control/signing.py:30-32,194-221`: 変数名、同梱鍵と追加鍵の読込順、空値の扱い、JSON 形式と鍵検証、追加鍵有効判定。
- `strata_control/signing.py:262-272` と `strata_control/engine_component.py:348-375`: コンポーネント verifier の初回遅延登録とプロセス内 verifier の再利用。
- `strata_cli/update_cmd.py:189-205,217-224`: 更新コマンドでの読み込み、注記、失敗時の出力と終了コード。
- `strata_control/feed.py:294-319,322-340`: 空の信頼鍵や署名不一致の拒否、署名後のフィード検査。
- `docker/fetch-engines.py:99-124`: 同梱 fetch ツールによる鍵読込とフィード検証。
- `packaging/install.sh:104-110`, `packaging/install.ps1:87-96`: インストーラーのテスト鍵設定と `strata update --check` 呼び出し。
- `packaging/UPDATES.md:53-62,107-111`: 信頼鍵の用途とテスト鍵をリリース鍵から分ける設計説明。
