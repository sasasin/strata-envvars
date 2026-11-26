# `strata launch --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

`strata launch` の主な結果や失敗を、人向け表示または機械処理向け JSON で出力します。`--list-presets`、`--status`、`--plan`、通常起動の結果を JSON で受け取りたい自動化で使えます。`strata connect` にも同名の別スコープの parser 定義がありますが、この文書は `strata launch` のみを対象にします（`terminal/strata_cli/launch/cmd.py:73-80, 154-155, 163-183`）。

## 使い方

```sh
strata launch --list-presets --output json
strata launch --plan --model q2_0 --output json
```

実際に `--model` などの選択肢を指定して `--plan` なしで実行すると、JSON モードでは対話画面を開かず、起動確認も自動的に承認扱いになります。エンジンやモデルの取得を含む実行をスクリプトから行う場合は、その副作用を前提にしてください（`terminal/strata_cli/launch/cmd.py:849-877`）。

## 値と既定値

- 値は必須で、選択肢は `human` と `json`、省略時は `human` です（`terminal/strata_cli/launch/cmd.py:154`）。
- `choices` にない値（空文字列を含む）は引数解析で拒否されます。値を複数回指定した場合は `argparse` の通常の `store` 動作となり、最後に指定した値が使われます。専用の変換関数や重複指定時の追加処理はありません（`terminal/strata_cli/launch/cmd.py:154`）。

## 実行時の動作

- `human` 以外、すなわち `json` のとき `run_launch` は機械出力モードと判定します（`terminal/strata_cli/launch/cmd.py:753-764`）。このモードでは TUI を起動せず、モデル等の選択がない非 plan 実行はエラーになります（同 `:849-873`）。
- Runner の進捗出力 callback は抑止され、`assume_yes` が真になります。したがって通常の対話確認を行わずに Runner の実行へ進みます。`--output json` 自体がファイルを変更するわけではありませんが、組み合わせた起動オプションに応じて Runner がエンジン／モデル取得やサーバー起動などを進める条件を変えます（同 `:876-877`、`terminal/strata_cli/launch/runner.py:980-993`）。
- `--plan` と併用した場合は plan オブジェクトを `schema_version: 1`、`ok: true` とともに JSON 出力し、plan 分岐から終了します（`terminal/strata_cli/launch/cmd.py:897-903`）。
- `--list-presets` は preset を `to_dict(with_key=False)` で JSON 化します。`--status` は稼働中 launch の一覧を JSON 化します（同 `:767-797`）。
- 通常起動では、非 serving の結果に `serving: false`、`engine_problem`、`message` などを含め、serving 中の結果に profile、URL、再利用状態、API key の有無を示す `api_key`、tune 情報、通知を含めます。API key の値そのものは通常起動の結果 JSON には載せず、`set` または `null` です（同 `:967-979`）。
- JSON モードの失敗経路では、`schema_version`、`ok: false`、エラーコードとメッセージを JSON 出力し、同じコードを終了コードとして返します（同 `:759-764, 1009-1014`）。

## 適用条件と副作用

- `--output` は `strata launch` に作用します。同じ `add_parsers` 関数内にある `strata connect --output` は別 parser・別コマンドであり、本オプション文書の対象外です（`terminal/strata_cli/launch/cmd.py:73-80, 154-183`）。
- JSON モードで `--show-key` を使うと、成功時に key は JSON オブジェクトではなく `_say` 経由の標準出力へそのまま書かれます。したがって JSON 一個だけが出ることを期待するパイプラインでは混在に注意してください（同 `:798-815`）。
- 管理操作すべてが JSON 化されるわけではありません。特に `--delete-preset` は人向けの完了文を出し、`--stop` は専用処理へ委譲します（同 `:783-788`）。`--output json` だけで、それらの出力形式が JSON になるとはソース上確認できません。
- JSON モードで起動選択を指定しない場合、非 plan 実行は「選択を指定する」旨のエラーになります（同 `:859-862`）。

## 出力とエラー

選択肢外の値は parser の `choices` により拒否されます。未知の追加引数については CLI の `main` が launch/connect 用のエラー文を標準エラーへ出し、終了コード `2` を返します（`terminal/strata_cli/launch/cmd.py:154, 186-200`、`terminal/strata_cli/cli.py:2325-2334`）。通常処理内で捕捉される preset error と `ValueError` は既定コード `2`、割り込みは `130` を返し、JSON モードでは前述のエラー形式を標準出力へ出します（`terminal/strata_cli/launch/cmd.py:759-764, 1009-1014`）。

## 根拠

- parser 定義と同スコープの connect parser: `terminal/strata_cli/launch/cmd.py:73-80, 141-183`
- JSON モード判定と失敗形式: `terminal/strata_cli/launch/cmd.py:753-764`
- preset 一覧・削除・停止・status・key 表示: `terminal/strata_cli/launch/cmd.py:767-815`
- TUI 判定、JSON 時の確認抑止、Runner への出力 callback 転送: `terminal/strata_cli/launch/cmd.py:849-877`
- plan／起動結果の JSON 形式: `terminal/strata_cli/launch/cmd.py:897-903, 967-979`
- Runner の callback・確認フラグ保持: `terminal/strata_cli/launch/runner.py:980-993`
- CLI での parser 登録と未知引数の終了経路: `terminal/strata_cli/cli.py:516-518, 2325-2334`
