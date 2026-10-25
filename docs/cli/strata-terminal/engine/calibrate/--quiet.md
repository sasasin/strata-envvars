# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効 |

## 役割

human 出力の情報メッセージを抑えます。対象は `strata engine calibrate` の stdout です。診断やエラーなど stderr に出る内容は抑制しません。

## 使い方

```sh
strata engine calibrate --profile PROFILE --plan --quiet
```

`--profile` と必須の操作（ここでは読み取り専用の `--plan`）を指定します。`--quiet` は `--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のいずれとも併用できます。

## 値と既定値

値は不要です。parser は `store_true` で登録し、指定しない場合の実効値は false です。引数を取る `--quiet VALUE` 形式ではありません。繰り返し指定しても true のままです。

このコマンドで `--quiet` を有効にするのは、`calibrate` parser が one-shot parser 群に含まれ、その群に `--quiet` が追加されるためです。オプションの追加時は `default=argparse.SUPPRESS` で、未指定なら Namespace に属性を作らず、実行時は `getattr(..., False)` で未指定を扱います。

## 実行時の動作

`--quiet` がなく、または `--output json` が有効なときは通常の実行経路です。human 出力で `--quiet` がある場合は `_run()` の stdout を一時捕捉します。終了コードが 0 なら捕捉した stdout を表示せず、非 0 なら捕捉した内容を stderr に出して終了コードを保ちます。捕捉量が上限を超えて切り詰められた場合は、その前に省略を知らせるメッセージを stderr に出します。

`--json` は one-shot コマンドで `--output json` の alias として処理されるため、`--quiet --json` では JSON が stdout に出ます。`calibrate` の `--output` は `human` または `json` を受け付け、既定値は `human` です。`jsonl` はこの parser の選択肢にありません。

計測・適用・ロールバック処理は、処理関数が stdout に書く内容を明示的に stderr へ転送します。この転送先は quiet 捕捉の対象外なので、`--quiet` でもそれらの進捗や診断は stderr に表示され得ます。quiet は校正処理、プロファイル解決、レポート生成・適用などの動作を変更しません。

## 適用条件と副作用

`--quiet` は `calibrate` parser のみに追加されるフラグです。stdout の捕捉と再出力だけを行い、ファイルや設定を変更しません。各校正アクション固有の副作用はこのフラグでは変わりません。

## 出力とエラー

- human 出力、終了コード 0: 捕捉対象の stdout を表示しません。
- human 出力、終了コードが非 0: 捕捉済み stdout を stderr に出します。切り詰めがあれば `strata: earlier human output omitted in quiet mode` も stderr に出ます。
- stderr に直接書かれた内容: quiet でもそのまま表示されます。
- JSON 出力: quiet の捕捉分岐を通らず、機械可読 JSON が stdout に出ます。
- 引数不備など parser が処理するエラー: argparse の usage/error 表示と終了コード 2 で、quiet はこの事前解析を抑制しません。

## 根拠

- `strata_cli/cli.py:174-189` — `engine calibrate` parser と操作群、`--output` の選択肢・既定値を定義。
- `strata_cli/cli.py:508-515` — `calibrate` を含む one-shot parser 群へ `--json` と `--quiet` を追加。`--quiet` は `store_true`。
- `strata_cli/cli.py:1059-1126` — 校正の各操作を実行し、human/JSON 出力と成功・失敗コードを選択。計測・適用・ロールバック処理では処理中 stdout を stderr へ転送。
- `strata_cli/cli.py:527-542` — human エラーは stderr、JSON エラーおよび成功結果は stdout に出力。
- `strata_cli/cli.py:2119-2144` — `engine` コマンドを `_calibration()` へ振り分け。
- `strata_cli/cli.py:2232-2248` — `--json` を `output=json` に反映し、JSON は quiet 捕捉を迂回。human quiet では stdout を捕捉し、失敗時に stderr へ転送。
