# `--setup`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` 経由を含む） |
| オプション | `--setup` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False` |

## 役割

既にモデル設定がある環境で通常のモデル起動へ進まず、モデルの追加または設定変更を行う setup 経路を選びます。`setup.py` の help は「install another model or change settings」と説明しています。

## 使い方

```sh
# Linux: セットアップ画面・質問に従ってモデルを追加または設定変更
./setup.sh --setup

# Windows: 同じ setup.py オプションを渡す
START-HERE.bat --setup

# 設定を行い、最後にモデルを起動しない
./setup.sh --setup --no-start
```

モデルなどの値を明示する場合は、たとえば `./setup.sh --setup --model IQ3_XXS` のように他の `setup.py` オプションと組み合わせます。

## 値と既定値

`argparse` の `store_true` action で、引数なしで指定します。省略時は `False`、指定時は `True` です。同じフラグを複数回指定しても真偽値のままです。値を付ける形式は定義されていません。

## 実行時の動作

既存の設定がある場合、`--setup` は「既存モデルをそのまま起動する」条件を外し、PC の確認から setup の処理へ進ませます。モデル・family を指定しなければ、その後の選択は対話式です。`--yes` を加えると推奨回答を受け入れ、質問を省く動作になります。

通常はセットアップ完了後に作成・更新した run config のモデルを起動します。`--no-start` も指定した場合は設定完了後に終了し、モデルを起動しません。複数の既存モデルがある場合でも、通常起動時の「どのモデルを起動するか」選択分岐は `--setup` により迂回され、setup 処理へ進みます。

各 wrapper は引数を `setup.py` に渡します。`SETUP.bat` は `START-HERE.bat --setup` の別名です。更新 wrapper は別の動作で、`update.sh` は `setup.sh --update` を実行し、`UPDATE.bat` も `--update` を付加します。`setup.py` は `--update` を通常 setup 分岐より先に処理するため、更新 wrapper に追加引数として `--setup` を渡しても更新処理が優先されます。

## 適用条件と副作用

- 未指定時の通常起動は、既存モデルがあれば保存済み設定から直接起動します。`--setup` を付けるとセットアップ用のデータフォルダー解決を使い、PC 確認、モデル・設定の選択、必要なファイル取得や設定生成へ進みます。
- 成功したセットアップは run config を書き込み、run script を作成します。既存 config が更新され内容が変わる場合、旧 config を `.bak` として保存しようとします。バックアップ作成に失敗した場合は警告を出して続行します。
- `--setup` 自体はダウンロードや設定値を決めません。実際の取得・変更内容は選んだモデル、ほかのオプション、既存ファイルや環境に依存します。
- macOS の通常 setup では parser 作成前に `metal/setup_mac.py` へ引数全体を委譲し、Intel SYCL backend 指定時も `sycl/setup_intel.py` へ委譲します。このフラグの個別効果は委譲先実装を含めて確認していません。

## 出力とエラー

`--setup` 単独に固有のエラー経路はありません。ほかの引数の形式エラーは `argparse` が usage とエラーを表示して終了し、モデル選択・ファイル取得・設定書き込みなど後続 setup の失敗は各処理のエラー経路に従います。成功時は setup の進捗・完了メッセージを表示し、`--no-start` がなければサーバーを起動します。

## 根拠

- `setup.py:8420-8427,8493-8505` — parser の生成、`--setup` の boolean 定義、および `--yes`、`--no-start`、`--update` との定義上の関係。
- `setup.py:8602-8620` — 既存設定の検出、通常起動判定、`--update` の先行処理、setup 経路を選ぶ条件。
- `setup.py:8677-8696` — 既存モデルの通常起動・選択分岐と、setup に進む場合のデータフォルダー再解決。
- `setup.py:6234-6265,6312-6346` — 明示された引数の保持、既存 config の引継ぎ、変更時の `.bak` 作成と失敗時警告。
- `setup.py:9729-9760` — config・run script の作成、完了表示、`--no-start` 時の終了と通常時の起動。
- `setup.sh:6-12,68-76`、`START-HERE.bat:8-12,44-55` — POSIX/Windows wrapper の Python 選択と引数委譲。
- `SETUP.bat:1-3` — `START-HERE.bat --setup` への委譲。
- `update.sh:1-7,62`、`UPDATE.bat:1-6,79` — update wrapper が `--update` を追加すること。

調査対象は指定 revision のソース checkout です。実機での CLI 実行、Release 配布物、各 OS/backend の setup 実行結果は確認していません。
