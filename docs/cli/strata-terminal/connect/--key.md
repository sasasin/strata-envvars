# `--key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <harness>` |
| オプション | `--key KEY` |
| 別名 | なし |
| 値 | API key を表す文字列。parser 上の形式・長さ検証なし |

## 役割

接続先アプリ用に表示・生成する設定へ渡す API key を指定します。これは `strata connect` のオプションであり、サーバーの key 自体を設定・変更するものではありません。

## 使い方

```sh
strata connect opencode --key "$STRATA_API_KEY"
```

例では key をシェルの環境変数から渡しています。実際の key をコマンド履歴に直接書かない方法を選んでください。

## 値と既定値

- `argparse` の通常の文字列引数で、必須ではありません。省略時の値は `None` です。空文字列、形式、長さに対する `--key` 固有の validation はありません（`strata_cli/launch/cmd.py:148-165`）。
- 有効値は `--key`、`--key-env NAME` が指定されていればその環境変数、選択された実行中 launch または preset から得た key、空文字列の順で選ばれます（`strata_cli/launch/cmd.py:864-868`）。この選択は truthy 判定なので、`--key ""` や空の環境変数値は値として採用されず、次の候補へ進みます。
- 同じ `--key` を複数回指定した場合は `argparse` の通常の `store` 動作で最後の値が使われます（宣言は `strata_cli/launch/cmd.py:155`）。
- 選択後も key が空なら、接続先設定の生成時に placeholder `strata-local` が使われます（`strata_cli/launch/harness.py:22,259-260`）。

## 実行時の動作

`strata connect` は、指定されたアプリ名に対応する harness を探し、URL・key・model・context から設定ファイルや環境変数の内容を組み立てます。`--key` の値はこの `Target` に渡され、各 harness の設定生成関数が app 固有の key 欄または credential 環境変数へ埋め込みます（`strata_cli/launch/cmd.py:857-870`; `strata_cli/launch/harness.py:259-267,209-234`）。

通常の人向け出力では、key は既定でマスクされます。`--show-key` を加えると表示中の設定・環境値に実値を表示します。`--output json` では key を含む文字列をマスクして出力し、`--show-key` でも JSON 出力のマスクは解除されません（`strata_cli/launch/cmd.py:871-910`）。

`--check` を併用すると、選ばれた key を Bearer と `x-api-key` の両 HTTP header に設定し、対象 server へ prompt と tool-call の要求を送ります（`strata_cli/launch/cmd.py:880-896,921-929`; `strata_cli/launch/check.py:36-43,111-143`）。成功時は終了コード 0、いずれかの確認失敗時は 1 です。認証拒否、URL 不在、接続不能などは確認結果の説明へ変換されます（`strata_cli/launch/check.py:146-155`）。

## 適用条件と副作用

- `--key` は `<harness>` を指定した接続設定の生成経路で参照されます。`strata connect` の harness 省略時はアプリ一覧を出力して終了するため、key は使用されません（`strata_cli/launch/cmd.py:842-856`）。
- `--preset NAME` があると `launch_info(NAME)` が候補を解決します。key の選択では、明示した `--key`、`--key-env`、launch/preset の key の順になります（`strata_cli/launch/cmd.py:864-868`; launch/preset 情報の読み出しは `strata_cli/launch/cmd.py:605-627`）。
- `--write` を付けると生成設定をユーザーの app 設定パスへ書き込み、既存ファイルはまず時刻付き backup にコピーします。生成設定に実 key が含まれることがあり、書き込み後は mode `0600` の設定を試みます。端末での確認を省くには `--yes` が必要です（`strata_cli/launch/cmd.py:930-947`; `strata_cli/launch/harness.py:275-298`）。
- key 自体に対する拒否・サニタイズ・ネットワーク検証は `--key` の選択時にはありません。実サーバーとの疎通・認証確認は `--check` を指定した場合にのみ行われます（`strata_cli/launch/cmd.py:864-896`）。

## 出力とエラー

このオプション値について独自の parser validation エラーはありません。未知の harness は stderr に候補付きのエラーを出し、終了コード 2 で終了します（`strata_cli/launch/cmd.py:857-863`）。通常の接続設定表示は key をマスクし、`--show-key` は人向け表示に実値を出します（`strata_cli/launch/cmd.py:871-910`）。`--write` の確認・キャンセル・書き込み処理は `strata_cli/launch/cmd.py:930-947` にあります。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` parser と `--key` / `--key-env` / `--preset` / `--show-key` の宣言。
- `strata_cli/launch/cmd.py:605-627,842-910` — launch/preset 情報、値の優先順位、harness への受け渡し、出力・mask 処理。
- `strata_cli/launch/cmd.py:921-947` — `--check` と `--write` の分岐。
- `strata_cli/launch/harness.py:22,259-267,275-298,310-311` — key placeholder、Target、設定の描画、ファイル保存・backup・permission 試行、mask。
- `strata_cli/launch/check.py:36-43,111-155` — key 付き要求と check の結果・失敗説明。
