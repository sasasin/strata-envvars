# `--family`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--family` |
| 別名 | なし |
| 値 | family ID を表す文字列（`NAME`）。parser では候補を制限しない |

## 役割

同じモデルサイズを複数のモデル family が提供するとき、`--model` が指すサイズをどの family のものとして扱うか指定します。省略時はカタログが選び、複数候補に `qwen` が含まれる場合は `qwen`、それ以外は最初の候補が選ばれます。

## 使い方

```sh
strata launch --model iq3_xxs --family qwen --plan
```

ここでは `iq3_xxs` と `qwen` が現在のカタログで組み合わせ可能な例として、起動計画を表示します。実際に使える family とモデルの組み合わせは、実行する Strata のカタログに従います。

## 値と既定値

- 値は必須です。`argparse` の `metavar` は `NAME` で、別名は定義されていません（`strata_cli/launch/cmd.py:83-90`）。省略時は `None` です。
- `--model` と併用すると、モデル名は大文字・小文字を区別せず解決しますが、family ID はカタログのキーと大文字・小文字を区別して照合されます（`strata_cli/launch/catalog.py:350-374`）。family 名は固定の CLI 列挙値ではなく、同リビジョンのモデルカタログから取得されます。
- family が存在しない場合は候補 family の一覧を含むエラーになります。family が存在しても指定モデルを提供していない場合は、その family が提供するサイズ一覧を含むエラーになります（`strata_cli/launch/catalog.py:362-370`）。
- オプション単独では、モデルサイズの適合性検査は行われません。プリセットにモデルがあるときはその family を上書きします。プリセットなしで `--model` もない場合は、family は設定に反映されず、通常のモデル選択経路に進みます（`strata_cli/launch/cmd.py:201-218,688-706`）。

## 実行時の動作

- `--model` と併用した場合、カタログは指定サイズを提供する family を調べ、指定 family とモデルの組を起動設定 `s.family` / `s.model` に格納します。family を省いたときは、候補のうち `qwen` を優先し、なければ先頭を選択します（`strata_cli/launch/cmd.py:210-217`、`strata_cli/launch/catalog.py:350-374`）。
- その family はモデル一覧の行、インストール済み設定の識別タグ、モデルファイルの準備などに使われます。起動処理は選択した family と model を `setup.py` に `--family` / `--model` として渡します（`strata_cli/launch/catalog.py:376-378`、`strata_cli/launch/runner.py:729-762,841-861`）。したがって、同じサイズ名でも family の選択で参照・準備するモデルが変わります。
- `--preset NAME` を指定すると preset が先に読み込まれます。`--model` を指定すれば、そのモデルと family の組で preset のモデル選択を置き換えます。`--model` を省いて `--family` だけ指定した場合は preset の `s.model` を残して `s.family` を直接置き換えます。この経路では `Catalog.resolve()` による family の存在・サイズ適合検証を通りません（`strata_cli/launch/cmd.py:197-218`）。無効な組み合わせの後続挙動は実行時の利用箇所に依存するため、ここでは受理される値として推奨しません。
- `--model-path` と `--model` を併用した場合も family/model の組を解決します。ファイルのヘッダーから別のモデルと判定されても、明示した family/model の選択はここでは拒否されず、警告を出して指定モデルのファイルを探す処理へ進みます（`strata_cli/launch/cmd.py:206-216`、`strata_cli/launch/runner.py:1156-1188`）。`--model-path` だけなら既存ファイルから family と model を判定するため、`--family` は使われません（`strata_cli/launch/cmd.py:206-210`、`strata_cli/launch/runner.py:1189-1198`）。
- `--plan` と併用すれば family を反映した起動計画を表示して終了します。通常起動では選択した family に基づくファイル確認・準備とサーバー起動へ続きます（`strata_cli/launch/cmd.py:733-760,784-787`）。

## 適用条件と副作用

- 通常の `--model` 解決には Terminal にモデルカタログが必要です。カタログを持たない配布形態でモデルまたはモデルパスを指定すると、実行処理より前にエラーになります（`strata_cli/launch/cmd.py:679-685`）。
- family 選択自体は設定値を決めるもので、単独でファイルを変更しません。計画表示では「変更なし」で終了します。通常起動では選ばれた family/model に応じて不足モデルの準備などが行われ得ます（`strata_cli/launch/cmd.py:733-760`、`strata_cli/launch/runner.py:729-762,912-917`）。
- 一部 family は専用の実行制約を持ちます。たとえば `multi_family` と判定される family では、同時リクエスト数や画像機能の設定が通常と異なる扱いになります（`strata_cli/launch/cmd.py:315-340`）。この条件は `--family` 自体の一般的な制約ではなく、選択後の family に対する起動処理です。

## 出力とエラー

- `--model` と指定 family の不整合、未知の family、未知のモデルは `ValueError` となり、通常出力では `strata: ...` を標準エラーへ出して終了コード 2 になります。JSON 出力モードでは同じ失敗を JSON の `ok: false` / `error` として出します（`strata_cli/launch/catalog.py:357-374`、`strata_cli/launch/cmd.py:636-641,834-835`）。
- `--model-path` 併用時にファイル内容から別 family/model が推定されると、起動処理はその不一致を通知に記録します。指定モデル用ファイルが見つからないなどの失敗は後続の準備処理で発生し得ます（`strata_cli/launch/runner.py:1167-1188`）。

## 根拠

- `strata_cli/launch/cmd.py:83-90` — `strata launch` parser の `--family NAME` 宣言。
- `strata_cli/launch/cmd.py:197-218` — preset 読み込み、`--model` に伴う catalog 解決、family 単独上書きの分岐。
- `strata_cli/launch/catalog.py:350-378` — モデル・family の検証、既定 family の選択、family/model から識別タグへの変換。
- `strata_cli/launch/runner.py:729-762,841-861` — family と model を setup に渡し、インストール済み設定・モデル状態を参照する処理。
- `strata_cli/launch/runner.py:1116-1147,1156-1198` — `--model-path` と family/model の相互作用、ファイル判定と不一致通知。
- `strata_cli/launch/cmd.py:636-641,679-685,733-760,784-835` — カタログ未搭載時、計画表示、通常起動とエラー出力。
