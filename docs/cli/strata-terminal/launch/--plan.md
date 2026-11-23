# `strata launch --plan`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は `false`。 |

## 役割

起動設定を組み立て、選んだモデル・設定・ダウンロード見込み・警告などを表示して終了します。通常起動の TUI、モデルやエンジンの取得、チューニング、サーバー起動には進みません。計画のためにローカルの設定・モデル状態・ハードウェア情報を読み、条件によっては署名付き更新フィードにも問い合わせます。

## 使い方

```sh
# 推奨設定で q2_0 の起動計画を人向けに表示
strata launch --plan --model q2_0

# JSON で計画を取得（JSON 出力は --plan と併用）
strata launch --plan --model q2_0 --output json

# 保存済みプリセットを基に、今回の変更を含めた計画を表示
strata launch --plan --preset "Office" --context 64k
```

## 値と既定値

`--plan` は `argparse` の `store_true` で、引数値を取りません。省略時は通常の起動経路になり、指定すると計画表示後に終了します。`--output` は別オプションで `human`（既定）または `json` を選びます。人向け表示では計画内容と `Nothing was changed.` を出し、JSON では `schema_version`、`ok`、`plan` を含むオブジェクトを標準出力へ出します（`terminal/strata_cli/launch/cmd.py:141-154,897-925`）。

`--plan` 自体に値の範囲や独自 validation はありません。モデル、ポート、コンテキストなど他の指定値はそれぞれの parser と設定処理で検証されます。例としてポートは 1〜65535 に制限され、`--gpu` と `--gpu-roles` の併用は拒否されます（`terminal/strata_cli/launch/cmd.py:46-60,262-273`）。

## 実行時の動作

1. 指定したプリセットを読み込み、コマンドライン指定を重ねて `LaunchSettings` を作ります。モデル名の解決や `--api-key-env` の読み取りもこの段階で行います（`terminal/strata_cli/launch/cmd.py:215-313`）。
2. `--plan` のときは TUI を選ばず、未指定の設定にコンピューターに応じた既定値を適用します。モデルも指定されず、TUI にも入らない場合は推奨モデルの選択を試みます（`terminal/strata_cli/launch/cmd.py:344-415,849-875`）。
3. 指定された `--model-path` の存在・内容を確認し、runner が計画情報をまとめます。計画には設定（API key を含めない形式）、警告、起動手順、モデル情報、ダウンロード見込み、drafting の説明が含まれます（`terminal/strata_cli/launch/cmd.py:876-900`, `terminal/strata_cli/launch/runner.py:1885-1918,2968-2990`）。
4. 計画を表示して終了コード 0 で戻ります。通常実行の `runner.run()`、preset 保存・最終使用時刻更新、ブラウザー起動の経路には進みません（`terminal/strata_cli/launch/cmd.py:897-925,949-1008`）。

`--output json` を付けると計画のオブジェクトを JSON として出力します。エラー時も JSON 形式を選んでいれば `ok: false` とエラーコード・メッセージを出し、エラーコードを終了コードとして返します。たとえばモデルファイルの問題は `LaunchError` として返され、設定 validation の `ValueError` はコード 2 になります（`terminal/strata_cli/launch/cmd.py:753-764,879-881,1009-1014`）。

## 適用条件と副作用

- `--plan` は対話可能な端末でも計画だけを表示します。明示した `--move-data` は選択値として受け取られますが、このモードではデータ移動を実行しません。移動判定は計画時に既定で移動しない扱いです（`terminal/strata_cli/launch/cmd.py:600-608,897-925`）。
- `--backend` の明示値は現在の Python プロセスの環境変数に反映されますが、`--plan` では backend の選択を保存しません（`terminal/strata_cli/launch/cmd.py:817-837`）。
- 外部共有用の API key が必要で既存キーがない場合、既定値処理でキーを生成することがあります。ただし plan 経路は書き込み後に出す通知を保留し、runner はキーなし形式の設定を返すため、計画出力にキーを含めず保存もしません（`terminal/strata_cli/launch/cmd.py:402-411,884-886,917`, `terminal/strata_cli/launch/runner.py:2988-2990`）。
- 計画表示は通常、ローカル状態の読み取りです。ただし DFlash2 の tuned drafter のサイズを判定する必要がある場合、署名付き feed を一度取得して照会します。この照会は何も書き込まず、オフライン・接続失敗・署名検証失敗などで回答できない場合は「不明」として計画を続けます（`terminal/strata_cli/launch/cmd.py:897-899`, `terminal/strata_cli/launch/runner.py:2812-2821`, `terminal/strata_control/drafting_fetch.py:260-271`）。
- ダウンロード量を計算できない場合も、runner は計画全体を中断せず、計算不能の説明を含めます（`terminal/strata_cli/launch/runner.py:2976-2984`）。計画は実行時のハードウェア状態や feed 応答を反映するため、その後の起動結果を保証するものではありません。

## 出力とエラー

成功時は標準出力に人向け計画、または JSON 計画を出し、コード 0 で終了します。対象モデルの一覧が利用できない場合はコード 5、指定モデルファイルの問題は原因に応じたコードで失敗します。設定エラーは通常コード 2 です。人向けエラーは `strata: ...` として標準エラーへ、`--output json` のエラーは JSON オブジェクトとして標準出力へ出ます（`terminal/strata_cli/launch/cmd.py:759-764,838-844,879-881,1009-1014`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:141-154` — launch parser 上の `--plan` 定義、値を取らないこと、`--output` の選択肢と既定値。
- `terminal/strata_cli/launch/cmd.py:215-313,344-415` — プリセットと引数からの設定構築、入力処理、マシンに応じた既定値。
- `terminal/strata_cli/launch/cmd.py:817-837,849-925` — backend の一時的な反映、TUI を避ける条件、plan の計算・出力・終了。
- `terminal/strata_cli/launch/cmd.py:949-1014` — 通常起動との差、失敗の標準出力・標準エラー・終了コード。
- `terminal/strata_cli/launch/runner.py:1885-1918,2968-2990` — モデルファイル確認と plan の項目構成。
- `terminal/strata_cli/launch/runner.py:2812-2821`、`terminal/strata_control/drafting_fetch.py:260-271` — tuned drafter の feed 照会と、書き込みを伴わない応答取得。
