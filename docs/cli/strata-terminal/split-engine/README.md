# `strata split-engine`（Strata Terminal CLI）

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。調査時の checkout は `main`（`origin/main` と一致）、working tree clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine apply` |
| 主な実装 | `strata_cli/split_cmd.py`、`strata_control/split_engine.py` |
| CLI 登録・実行 | `strata_cli/cli.py` |

## 役割

`strata split-engine apply` は、デスクトップアプリが作成した run config を all-cards split engine の選択規則に照合し、適用可能なら split engine 用の別 run config を出力します。Terminal の `strata launch` も同じ規則を内部で使います。このサブコマンドは判定と設定変換を行うもので、engine の起動やモデル・engine ファイルのダウンロードはしません（`strata_cli/split_cmd.py:1-5,41-58`）。

親の `strata split-engine` には必須のサブコマンド `apply` があり、親コマンド単独では処理しません（`strata_cli/split_cmd.py:16-22`）。この操作は、アプリの start 処理が作った run config を Control に渡す用途を想定しています。手動で使う場合も、`--config` には実際の Strata run config を指定してください。

## 基本的な使い方

```sh
# 判定し、適用された場合だけ変換後 config を /tmp に書く
strata split-engine apply --config /path/to/run-config.json --out /tmp/split-run-config.json

# 結果を機械処理する（human 出力が既定）
strata split-engine apply --config /path/to/run-config.json --out /tmp/split-run-config.json --output json
```

`--config` は必須です。`--out` を省略すると変換後 config はファイルに書かず、判定結果だけを表示します。`--output` は `human` または `json` を選び、既定値は `human` です。各 option の値と出力形式は索引内の [`apply` option 文書](apply/--config.md) などを参照してください（parser: `strata_cli/split_cmd.py:18-22`）。

## 実行モード

| モード | 動作 |
| --- | --- |
| human（既定） | 適用時は判定メッセージ、非適用でメッセージが空なら `Using the normal layer split.` を標準出力に表示します。 |
| JSON | 標準出力に `schema_version`, `ok`, `split`, `line`, `warn`, `reasons`, `cards`, `written` を含む JSON を1行出力します。適用なしも `ok: true`, `split: false` で表し、`written` は通常 `null` です。 |
| 適用対象外 | 判定規則に合わない場合は通常終了（コード 0）し、元の run config はそのままです。理由は human/JSON の結果に含まれます。 |
| 入力エラー | config を読み取れない、JSON として不正、または JSON object でない場合は失敗を出し、終了コード 5 を返します。 |

実行時に `strata_control.split_engine.apply_run_config()` を呼び出します。同関数は設定を変換するかどうかを判定し、適用なしの通常条件（Auto の拒否を含む）は例外にせず結果として返します（`strata_cli/split_cmd.py:25-43,54-59`; `strata_control/split_engine.py:631-656`）。

## 主な動作

1. `--config` の UTF-8（BOM 付きも可）JSON を読み、トップレベルが object であることを確認します。
2. 読み込んだ object を複製してから判定関数に渡します。したがって入力ファイルは書き換えません。
3. split engine が選ばれ、かつ `--out` が指定されているときだけ、変換後 config を `<出力名>.tmp` に書いてから `os.replace()` で出力先へ置き換えます。temporary file は mode `0600` で作成されます。
4. 選択されなければ出力ファイルを作らず、通常の layer split を使う旨と判定理由を返します。コマンド自身は split engine も通常 engine も起動しません。

このため、`--out` に既存ファイルのパスを指定して適用条件を満たすと、そのファイルは置き換えられます。出力先は意図した新規ファイルを指定してください（`strata_cli/split_cmd.py:35-58`）。

## 適用条件と関連動作

実行規則は `strata_control/split_engine.py` に集約されています。主な条件として Linux、同一メーカー・同一モデル・同一 VRAM 容量の 2〜4 枚の GPU、対応するモデル構造・tensor 型とメモリ条件、engine package 内のカード構成対応 `strata-split-N`、選択した drafting 方式に応じた draft layer または DFlash2 pack と draft vocabulary などを確認します。run config の engine 固有引数や replicas、非対応の `--kv` 指定なども適用を止める条件です（`strata_control/split_engine.py:190-249,492-565`）。詳細な対応条件は同ファイルの判定処理を参照してください。

モードは run config の `split_engine`（既定相当は `auto`）と環境変数 `STRATA_SPLIT_ENGINE` から決まります。環境変数が空でなければ run config より優先されます。`on/1/true/yes` は有効、`off/0/false/no` は無効として扱い、未知の値は `auto` です（`strata_control/split_engine.py:395-408`）。また `STRATA_SPLIT_ALLOW_UNTESTED=1` は未検証構成を許可する判定引数として渡されます（`strata_cli/split_cmd.py:41-43`）。

デスクトップアプリの起動は、このコマンドに run config を渡して split 用設定を受け取り、server 起動側へ進みます。split engine が起動できない場合に通常の layer split へ戻る処理は server 側の別経路です。この CLI 自体の責務には含まれません（Strata `docs/SPLIT_ENGINE.md`、`serve/server.py:9107-9145`）。

## 出力と失敗

- 人間向けの config 読込エラーは `strata: The run config could not be read (<例外型>).` を標準エラーへ出します。
- JSON モードの同エラーは `ok: false`、`error.code: "split_engine_failed"`、`message` を含む JSON を標準出力へ出します。
- 上記の config 読込エラーは終了コード 5 です。通常の「条件不適合」はエラーではなく、終了コード 0 の判定結果です。
- 出力先のディレクトリ作成は行いません。出力ファイルを作成・置換できない場合の OSError はこの関数内で読み込みエラーと同じ `fail()` には変換されず、CLI 共通のエラー処理へ進みます。CLI 共通処理は OSError を標準エラー（JSON 指定時は JSON）へ整形し、終了コード 6 を返します。

根拠: `strata_cli/split_cmd.py:25-59`、CLI の dispatch は `strata_cli/cli.py:174-175,2156-2158`。出力操作の OSError は `strata_cli/cli.py:2188-2195` で共通エラー（終了コード 6）になります。

## 関連文書

- [`docs/cli/README.md` の strata-terminal 索引](../../README.md) — `split-engine` と `split-engine apply` の階層および option 文書。
- [`strata-split` engine の概要](../../strata-split/root/README.md) — split engine 本体の独立 CLI。
- [`STRATA_SPLIT_ENGINE`](../../../envvars/STRATA_SPLIT_ENGINE.md)、[`STRATA_SPLIT_ALLOW_UNTESTED`](../../../envvars/STRATA_SPLIT_ALLOW_UNTESTED.md) — 判定モードと未検証条件の環境変数。
- Strata checkout の `docs/SPLIT_ENGINE.md` — split engine の適用条件、Terminal・Desktop の利用経路。
