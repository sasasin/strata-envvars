# `--vision`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `off`、`on`、`gpu`、`cpu` のいずれか |

## 役割

モデルに画像を読ませるか、画像 reader を使う場合に CPU と GPU のどちらを選ぶか指定します。`strata launch` は値を launch 設定へ反映し、モデル準備時に `setup.py` の `--vision` へ変換して渡します。reader の導入や設定はモデル・エンジン・backend ごとの setup 経路が行います。

## 使い方

```sh
# 画像を使わず、テキスト専用で起動する
strata launch --model iq3_xxs --vision off --no-tui

# 画像 reader を自動選択して起動する
strata launch --model iq3_xxs --vision on --no-tui

# 画像を読む処理を CPU に指定する
strata launch --model iq3_xxs --vision cpu --no-tui
```

## 値と既定値

- 値は必須です。parser の変換関数は前後の空白を除き小文字化してから `off`、`on`、`gpu`、`cpu` と照合するため、大文字・小文字は区別されません。空値やそれ以外の文字列は拒否されます（`terminal/strata_cli/launch/cmd.py:35-43,93-96`、選択肢は `terminal/strata_cli/launch/settings.py:30`）。
- 省略時は launch 設定の `None` をモデルとエンジンに応じた値で補います。モデルが画像非対応、既存エンジンに reader がない、または Intel Linux でその経路が画像を使えない場合は `off`。それ以外は画像対応モデルを `on` にします。通常の reader は VRAM 量・OS に基づき選択され、Mac は共有メモリ向けの Metal reader、利用可能な GPU がない場合は CPU reader になります（`terminal/strata_cli/launch/settings.py:135`、`terminal/strata_cli/launch/cmd.py:393-400`、`terminal/strata_cli/launch/catalog.py:662-692`）。
- `on` は画像を有効にし、対応モデルでは reader の選択を setup に任せます。`gpu` と `cpu` は画像を有効にして reader を指定します。`off` は画像を無効にします（`terminal/strata_cli/launch/runner.py:1322-1331,1351-1363`）。

## 実行時の動作

コマンドライン値は preset を読み込んだ後に設定へ代入されるため、同じ `strata launch --preset NAME` に併記すると preset の画像設定より今回の指定が優先されます（`terminal/strata_cli/launch/cmd.py:215-220,248-251`）。通常のモデルでは `on` が setup の `yes` となり、`gpu` / `cpu` はそのまま転送されます。Setup は `yes` をカードの条件に応じて具体的な reader に解決し、`gpu` の指定を小容量 VRAM を理由に勝手に CPU へ変更せず、警告を出して選択を保ちます（`terminal/strata_cli/launch/runner.py:1322-1331,1358-1363`、`terminal/setup.py:4130-4147`）。Mac では画像対応モデルの既定が Metal reader で、`cpu` 指定は維持されますが CPU reader に関する注意が出ます（`terminal/setup.py:11009-11025`）。

Hy4-Flash と Inkling-2-Mini はネイティブ `.strata` 系です。launch はこれらを setup に渡すとき `on`、`gpu`、`cpu` をいずれも `yes` に変換します。そのためこの2モデルでは `gpu` / `cpu` による reader の個別選択は setup へ伝わらず、`off` だけが無効化指定として働きます（`terminal/strata_cli/launch/runner.py:1204-1216,1322-1331,1362`）。一方、別の既存 run config を起動する際は、launch が通常モデルの engine 引数へ `--vision` を加除して設定を反映します（`terminal/strata_cli/launch/runner.py:305-354`）。

画像対応モデルで setup が必要な場合、画像を有効にすると画像 reader ファイルも準備対象になります。画像非対応モデルに `on`、`gpu`、`cpu` を指定すると警告を追加して `off` に補正します。省略時に既存 reader がない場合も警告して `off` にします（`terminal/strata_cli/launch/cmd.py:393-400`、reader が存在しない実行構成を伝える処理は `terminal/strata_cli/launch/runner.py:1333-1349`）。`--save-preset` を併用した場合、解決後の設定は保存されます（`terminal/strata_cli/launch/cmd.py:962-966`）。

## 適用条件と副作用

- `--vision` は `strata launch` の parser に登録されています。`strata connect` のオプションではありません（`terminal/strata_cli/launch/cmd.py:73-96`）。
- 明示的な reader 指定は、画像対応モデルと reader を扱う setup 経路で意味を持ちます。`on` の具体的な選択則は OS、backend、モデルにより異なるため、全組み合わせの選択規則はここでは列挙していません。たとえば AMD は `yes` を AMD 用 reader 選択関数へ渡し、Qwen3.6 の own-path 経路は VRAM 量で CPU/GPU を決めます（`terminal/setup.py:9718-9747`）。
- 画像を有効にしてモデル準備が必要な場合、setup が画像 reader 等のファイルをダウンロードし、起動用設定を準備します。既存設定が同じ選択で再利用できる場合はモデル準備を省くことがあります（`terminal/strata_cli/launch/runner.py:299-302,1682-1690,1719-1730`）。`--plan` は実行計画だけを表示し、何も変更しない経路です（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 出力とエラー

- 不正な値は parser の引数変換時に拒否され、`argparse` の usage/error 経路になります。妥当な語に近い場合は候補を示す文言を組み立てます（`terminal/strata_cli/launch/cmd.py:35-43,93-96`）。
- モデルが画像に対応しない場合は警告して画像を `off` に補正します。reader が不足する場合の案内文も launch の通知として追加されます（`terminal/strata_cli/launch/cmd.py:393-400`、`terminal/strata_cli/launch/runner.py:1333-1349`）。
- launch の通常エラーは `strata: ...` を stderr に出し、該当コード（既定 2）で終了します。JSON 出力では標準出力にエラー JSON を返します（`terminal/strata_cli/launch/cmd.py:753-764,1009-1014`）。reader の起動やモデル取得自体が失敗した場合の詳細は、それぞれの setup / engine 経路に依存します。

## 根拠

- `terminal/strata_cli/launch/cmd.py:35-43,73-96` — 値変換・選択肢・parser 定義。
- `terminal/strata_cli/launch/settings.py:25-30,126-139` — UI 表示語と値の内部表現、未指定値。
- `terminal/strata_cli/launch/cmd.py:215-220,248-251,344-400` — preset と CLI の優先関係、既定値、非対応モデル時の補正。
- `terminal/strata_cli/launch/catalog.py:662-692` — reader の有無と既定 reader の判定。
- `terminal/strata_cli/launch/runner.py:1204-1216,1313-1349,1351-1363,1682-1690,1719-1730` — ネイティブモデルの適用条件、setup への値転送、reader 通知、モデル準備と setup 起動。
- `terminal/setup.py:4130-4147,9718-9747,11009-11025` — reader の選択・保持、VRAM 条件、Qwen3.6 および Mac の例。
- `terminal/strata_cli/launch/cmd.py:897-925,753-764,1009-1014` — plan の非変更経路と launch の出力・エラー処理。
