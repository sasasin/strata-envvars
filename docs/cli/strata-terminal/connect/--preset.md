# `strata connect --preset`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--preset` |
| 別名 | なし |
| 値 | 保存済み launch preset の名前（`NAME`） |

## 役割

アプリ向け接続設定を表示・書き込みする際、指定した launch preset に結び付く server の接続先情報を選びます。`strata connect` 自体が server を起動したり、preset を適用して起動し直したりする機能ではありません。

## 使い方

```sh
strata connect opencode --preset "Office"
```

この例は `Office` preset を参照して OpenCode 向けの設定内容を表示します。ファイルを書き込むには別途 `--write` が必要です。

## 値と既定値

- `--preset` は `NAME` を1つ取ります。parser では値を文字列として受け取り、名前の存在確認や空文字の検証は行いません。値の省略は argparse の引数エラーになります（`strata_cli/launch/cmd.py:148-165`）。
- 保存ファイル名を求める際、名前は小文字化され、英小文字・数字・`-`・`_` 以外を `-` に置換し、先頭末尾の `-` / `_` を取り除き、先頭が英字でなければ `l` を付け、48文字に切り詰めます。そのため異なる入力名が同じ slug になることがあります（`strata_cli/launch/settings.py:310-315`、`strata_cli/launch/store.py:35-36`）。
- 省略時は `launch_info(None)` が最初の稼働中 launch を選びます。稼働中 launch がなければ、URL は `http://127.0.0.1:8080`、model は `strata`、context は `32768` にフォールバックします。key がない場合は harness 内部の非秘密 placeholder `strata-local` が使われます（`strata_cli/launch/cmd.py:605-627,864-869`、`strata_cli/launch/harness.py:22,259-260`）。

## 実行時の動作

`strata connect` にアプリ名がある場合、`run_connect` は `launch_info(a.preset)` から接続情報を取得します。名前を指定すると slug が一致する稼働中 launch を探し、同名の保存 preset も読み込みます。稼働中 launch があれば、その URL と server 設定ファイルの API key が優先されます。保存 preset は URL が得られない場合の port と、稼働中設定から key を得られない場合の API key に使われます（`strata_cli/launch/cmd.py:567-627`）。

ただし、保存 preset の `model` と `context` は `launch_info` の戻り値に使われていません。model は稼働中設定の `model_name`、または `strata`、context は稼働中設定の `--max-context`、または後段の `32768` になります。したがって、preset に保存された model/context を接続設定へ反映するオプションとしては動作しません（`strata_cli/launch/cmd.py:595-602,621-627,864-869`）。

同時指定時は `--url` が preset / 稼働中 launch の URL より優先し、`--key`、`--key-env` が preset 由来 key より優先します。`--model` と `--context` も、稼働中 launch 情報より優先します。値の選択式は `--url`、`--key`、`--key-env`、`--model`、`--context` の順で実装されています（`strata_cli/launch/cmd.py:154-160,864-869`）。

アプリ名を省略した `strata connect --preset NAME` はアプリ一覧を表示して終了し、preset は参照しません。名前が保存されておらず対応する稼働中 launch もない場合、`launch_info` は空情報を返すため、既定の URL/model/context で続行します。人向け出力では稼働中 server が見つからなかった旨も表示します（JSON 出力ではこの注意文は出ません）（`strata_cli/launch/cmd.py:842-869,897-900`）。

## 適用条件と副作用

- `--preset` の情報が利用されるのはアプリ名を指定した `strata connect <app>` の経路です。preset の読み込みは `store.load(..., missing_ok=True)` による読み取りで、`--preset` 単体では保存設定を変更しません（`strata_cli/launch/cmd.py:621-627,842-869`、`strata_cli/launch/store.py:88-103`）。
- アプリ設定のファイル書き込みは別オプション `--write` が必要です。既存ファイルは backup を作ってから置換し、JSON merge 対象では既存キーを保って新しい値を優先します（`strata_cli/launch/cmd.py:930-947`、`strata_cli/launch/harness.py:275-290`）。
- `--check` を重ねると、選択された接続情報で server に prompt と tool call を送信します。preset だけではネットワーク接続確認を行いません（`strata_cli/launch/cmd.py:880-896,921-929`）。
- 接続出力に含まれる API key は通常マスクされます。人向け出力で実値を出すには `--show-key` が必要です。JSON 出力は `--show-key` にかかわらず key をマスクします（`strata_cli/launch/cmd.py:871-876,900-910`、`strata_cli/launch/harness.py:310-311`）。

## 出力とエラー

- preset 名が存在しない場合、`missing_ok=True` により preset の読み込み自体は失敗扱いにならず、稼働中 launch が名前一致しなければ既定値にフォールバックします。従って、無効な名前を必ず拒否する validation はありません（`strata_cli/launch/cmd.py:611-627`、`strata_cli/launch/store.py:88-95`）。
- 保存ファイルが壊れている、読み取れないなど `store.load` が `PresetError`（`ValueError` の派生）を送出すると、通常出力では `strata: ...` を stderr に出し、終了コード 2 になります。`--output json` では同じエラーを JSON に出します（`strata_cli/launch/store.py:23,88-103`、`strata_cli/cli.py:2166-2173,527-532`）。
- `--output json` の正常時は、app 設定の説明を JSON にして stdout に出します。preset の値を使っても server が実際に応答するかは確認しません。確認には `--check` が必要です（`strata_cli/launch/cmd.py:872-896`）。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` parser と `--preset` 定義。
- `strata_cli/launch/cmd.py:567-627` — 稼働中 launch の検索、preset 読み込み、URL/key/model/context の組み立て。
- `strata_cli/launch/cmd.py:842-929` — 接続先の優先順位、表示、JSON、`--check` の分岐。
- `strata_cli/launch/store.py:27-36,88-103` — preset の場所、slug 化、読み込みと missing / damaged の扱い。
- `strata_cli/launch/settings.py:78-103,310-315` — 保存される launch 設定と preset 名の正規化。
- `strata_cli/launch/harness.py:22,253-267,275-311` — URL/key/context の既定、app 設定の生成、書き込み、key マスク。
- `strata_cli/cli.py:2166-2188,2223-2231` — ValueError のエラー変換と未知引数の処理。
