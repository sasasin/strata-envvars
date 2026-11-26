# `strata launch --api-key`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | 必須の文字列 `KEY`。値の形式・長さの parser validation はない |

## 役割

起動する Strata server のクライアント認証キーを指定する。launch の保存済み preset を使う場合は、その preset のキーを今回の起動だけ変更できる。キーは実行設定に入り、起動結果の表示ではマスクされる。

## 使い方

```sh
# ローカル server に指定したキーを設定する
strata launch --model q2_0 --api-key 'my-local-key' --no-tui

# LAN 共有と preset 保存を行う。実運用では例示値を秘密のキーに置き換える
strata launch --model q2_0 --access lan --api-key 'replace-with-a-secret' --save-preset Office --no-tui
```

## 値と既定値

- `--api-key` は値を1つ取る。`argparse` の `metavar="KEY"` で登録され、型変換・選択肢・長さ検査は設定されていない（`terminal/strata_cli/launch/cmd.py:137`）。
- オプションを省略した場合、このフラグ自体は保存 preset のキーを変更しない。preset がなければ初期値は `None`（`terminal/strata_cli/launch/cmd.py:219`, `terminal/strata_cli/launch/settings.py:146`）。共有先が local 以外でキーがなく、`--no-api-key` もない場合は、後続処理が以前のキーを再利用するか新しいキーを生成する（`terminal/strata_cli/launch/cmd.py:402-411`）。
- 値は launch の設定反映時には trim されない。空文字 `--api-key ""` は parser では受理されるが、設定反映時の truthy 判定で無視される。空白だけの値は設定へ渡るものの、server 側の `api_key_of` が空キーとして `ValueError` にし、起動前検査で終了コード `2` になる（`terminal/strata_cli/launch/cmd.py:288-290`; `terminal/serve/server_parts/http_api.py:238-252`; `terminal/serve/server.py:9331-9339`）。
- 同じオプションを複数回指定した場合の選択は標準 `argparse` の単一値引数の動作に委ねられ、独自の重複検査はない。

## 実行時の動作

`settings_from_args` は `--preset` があれば保存設定を読み込んだ後、非空の `--api-key` をその設定に反映する（`terminal/strata_cli/launch/cmd.py:215-220,288-290`）。続けて `--api-key-env NAME` も指定されていれば、指定環境変数の値が `--api-key` より後に適用され、キーを上書きする。環境変数が未設定または空ならエラーになる（`terminal/strata_cli/launch/cmd.py:290-294`）。launch parser 自体は `STRATA_API_KEY` を既定値として読み込まない。一方、server の parser は `STRATA_API_KEY` を `--api-key` の既定値にし、server 起動時にはその値を設定ファイルのキーより優先する実装になっている（`terminal/serve/server.py:9202-9204,9331-9336`）。この調査では runtime 起動時の環境変数伝播までは追っていないため、launch での同変数の影響範囲は断定しない。

実行設定の `api_key` にキーを入れ、server 用設定ファイルを作成する。`--save-preset NAME` を指定した場合は同じ設定を preset にも保存する。`--preset NAME` だけで起動時に `--api-key` を添えた場合、その変更は今回の起動用であり、preset 本体は保存し直さない（`terminal/strata_cli/launch/runner.py:724-739,2234-2238`; `terminal/strata_cli/launch/cmd.py:962-966`）。

`--api-key-env` と併用した場合は環境変数指定が優先される。`--no-api-key` と非空の `--api-key` を併用すると、キーを保持し「キーも指定されたためキーを保持する」という警告を出す。`--new-key` も指定した場合は、後段で新しいキーを生成して指定キーを置き換える（`terminal/strata_cli/launch/cmd.py:295-301,890-892`）。

## 適用条件と副作用

- `--access local` でもキーは実行設定へ書かれる。キー設定時、server は `/v1/*` に Bearer または `x-api-key` header の認証を要求する（`terminal/strata_cli/launch/runner.py:732-739`; `terminal/serve/server.py:4201,7283-7294`）。ネットワーク共有時には、キー未設定かつ `--no-api-key` なしなら既存キーの再利用または新規生成が行われる（`terminal/strata_cli/launch/cmd.py:402-411`）。
- launch の実行設定は state 領域の `launch/<name>.json` に書かれ、POSIX では一時ファイルを `0600` にして置換する。Windows では現ユーザーに限定する処理を試みる。キーは平文 JSON の値として含まれる（`terminal/strata_cli/launch/runner.py:819-838,841-845,2234-2238`）。`--save-preset` も指定すると preset ファイルにもキーを含む設定を保存し、同じく POSIX `0600` と Windows のユーザー制限処理を行う（`terminal/strata_cli/launch/store.py:1-6,40-60,76-86`）。
- 成功時の通常表示はキーをマスクし、機械可読出力は値そのものではなく `"api_key": "set"` とする。`--plan` の表示もキーの有無だけを示す（`terminal/strata_cli/launch/cmd.py:916-924,975-978,988-992`; `terminal/strata_cli/launch/access.py:418-421`）。
- この値の形式に関する追加の制限、server 内部でのキー文字列解釈、OS のプロセス引数表示・shell 履歴への記録は、この launch option の処理からは確定できない。機密値をコマンドラインへ直接書いた場合の外部環境での露出範囲は本調査対象外。

## 出力とエラー

- `--api-key-env NAME` が未設定または空の場合、`ValueError` を「The environment variable NAME is empty or not set.」として失敗扱いにし、launch は終了コード `2` を返す（`terminal/strata_cli/launch/cmd.py:290-294,1009-1012`）。
- `--api-key` に値を付けなければ `argparse` の引数エラーとなる。CLI は parser を呼び出し、引数解析エラーは終了コード `2` となる（`terminal/strata_cli/cli.py:2325-2334`; `terminal/strata_cli/launch/cmd.py:137`）。
- `--api-key` と `--no-api-key` の併用は拒否されず、キー保持の警告が記録される（`terminal/strata_cli/launch/cmd.py:295-299`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-80,130-140` — launch parser と API key option の定義。
- `terminal/strata_cli/launch/cmd.py:215-220,288-301,402-411` — preset への適用順、空値・環境変数・`--no-api-key` の相互作用、共有時のキー再利用・生成。
- `terminal/strata_cli/launch/cmd.py:890-892,916-924,962-978,988-992` — 新規キーの優先、plan/実行結果の表示、preset 保存。
- `terminal/strata_cli/launch/runner.py:724-739,819-838,2234-2238` — run config への格納と private write。
- `terminal/strata_cli/launch/store.py:1-6,40-60,76-86` — preset にキーを含めて保存する形式とファイル保護。
- `terminal/strata_cli/launch/settings.py:143-147`; `terminal/strata_cli/launch/access.py:418-421` — キーの初期値とマスク表示。
- `terminal/serve/server.py:4201,7283-7294,9202-9204,9331-9339`; `terminal/serve/server_parts/http_api.py:238-252` — `/v1/*` の認証、server 側環境変数既定値、空白だけのキーの拒否。
- `terminal/strata_cli/cli.py:2325-2334` — CLI 引数解析と未知引数エラー。
