# `strata connect --show-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--show-key` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は `False` |

## 役割

接続先アプリ向けに表示する設定から API key のマスキングを外します。key だけを単独表示する機能ではありません。通常は出力内の key を伏せ、明示的にこのフラグを指定した場合に、人が読む設定表示で実際の key を出します。

## 使い方

```sh
strata connect opencode --show-key
```

この例は OpenCode 用の設定を標準出力に表示し、含まれる key も表示します。実際の key が設定済みなら、表示結果をログや共有端末に残さないよう取り扱ってください。

## 値と既定値

- `argparse` の `store_true` フラグで、値は不要です。省略時は `False` です。
- 引数なしの `strata connect --show-key` はアプリ一覧を表示するだけで、key は取得・表示しません。アプリ名（例: `opencode`）を指定したときだけ設定表示経路に入ります。
- `--output json` ではこの指定は表示内容に反映されません。JSON 経路は `--show-key` の有無にかかわらず key をマスクします。

## 実行時の動作

アプリ名を指定すると、key は `--key`、`--key-env` で指定した環境変数、実行中 launch または `--preset` から得た key、空文字列の順で選択されます。選ばれた key を含むアプリ設定を組み立て、`--show-key` が有効な人向け表示では設定ファイル本文と環境変数値をマスクせずに出力します。通常表示では `harness.mask` が key を伏せます。key が得られない場合、テンプレートには `strata-local` というプレースホルダーが使われ、実 key を表示する状態にはなりません。

`--show-key` は `--write` の保存内容を切り替えません。設定はこのフラグなしでも選択された key を使って生成され、`--write` でファイルに書かれます。既存ファイルを置き換える場合は通常バックアップを作り、JSON merge 対象は既存キーを保ったうえで Strata の値を優先し、書き込み後は可能なら mode `0600` にします。

## 適用条件と副作用

- 適用されるのは `strata connect <アプリ名>` の人向け設定表示です。指定したアプリ設定に含まれる key が標準出力に露出します。
- `--output json` は独立した JSON 出力経路で、各文字列・生成ファイル本文をマスクするため、このフラグは key 開示を解除しません。
- `--check` はサーバーへ prompt と tool call を送りますが、`--show-key` はその検査方法を変えません。人向け出力では検査前に設定が表示されます。
- `--write` は設定ファイルを書き込み、既存ファイルをバックアップすることがあります。この保存処理は `--show-key` の有無とは独立しています。
- `--show-key` 単独ではファイル、ネットワーク、サーバーを変更しません。`--check` や `--write` を併用した場合の副作用はそれぞれの処理によります。

## 出力とエラー

- アプリ名を省略するとアプリ一覧を出力して終了コード `0` です。`--show-key` を付けても一覧に key は含まれません。
- 未知のアプリ名は stderr に `strata: There is no app called ...` を出し、終了コード `2` です。
- `--show-key` 自体に追加 validation はありません。`--check` の接続・動作検査に失敗すると終了コード `1` になります。
- `--output json` は `--show-key` を無視してマスク済み JSON を stdout に出します。`--check` 併用時の検査失敗は JSON の `ok: false` と `error` に記録され、終了コード `1` です。
- 未知オプションは CLI の parser が stderr に案内を出して終了コード `2` にします。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` parser と `--show-key`（値なし、`store_true`）の定義。
- `strata_cli/launch/cmd.py:842-871` — アプリ名の必須条件、アプリ解決、key の優先順、接続情報の生成、フラグの反映。
- `strata_cli/launch/cmd.py:872-896` — JSON 出力では key を常にマスクし、`--check` の結果と終了コードを返す処理。
- `strata_cli/launch/cmd.py:897-948` — 人向け出力での表示マスク解除、check/write の実行と失敗経路。
- `strata_cli/launch/cmd.py:605-627` — 実行中 launch または preset から URL/key/model/context を得る処理。
- `strata_cli/launch/harness.py:22,253-267,310-311` — key がない場合のプレースホルダー、設定生成、通常表示のマスク規則。
- `strata_cli/launch/harness.py:275-298` — `--write` によるファイル作成・バックアップ・merge・権限設定。
- `strata_cli/cli.py:2153-2155,2223-2235` — `strata connect` の dispatch と未知オプション処理。
