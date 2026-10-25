# `--full-digests`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--full-digests` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると有効、未指定時は `False` |

## 役割

チューニング記録のエンジン・モデルの identity を、既定の一部領域サンプリングではなくファイル全体の SHA-256 で計算します。比較の識別精度を上げる代わりに、対象ファイル全体を読み込む時間がかかります。

## 使い方

```sh
strata tune run --engine ./strata --backend cuda --model example --model-path ./model.gguf --full-digests
```

`--engine`、`--backend`、`--model` は `run` で必須です。モデルファイルの identity も full digest にするには `--model-path` を指定してください。これは `strata tune run` 固有のオプションで、`strata tune plan` や `strata tune apply` にはありません（`strata_cli/cli.py:414-459,461-470`）。

## 値と既定値

- `argparse` の `store_true` として宣言され、指定時は真、未指定時は偽です。引数値の型変換や独自 validation はありません（`strata_cli/cli.py:453-455`）。
- 未指定時のファイル identity は sampled SHA-256 です。既定方式はファイルサイズも hash に含め、12 MiB 以下なら全内容、より大きい場合は先頭・中央・末尾から各 4 MiB を読みます（`strata_control/tune_history.py:44-45,67-80`）。
- 指定時はファイルを 1 MiB 単位で EOF まで読み、通常の SHA-256 を計算します。identity には digest と別にファイルサイズも記録されます（`strata_control/tune_history.py:60-65,80-81`）。
- `--model-path` が省略された場合、モデル identity は digest なしで作られます。そのため `--full-digests` を付けてもモデルの内容は hash されず、エンジンだけが全体 hash の対象になります（`strata_control/tuning.py:753-761`）。存在しないモデルパスも `file_identity` はエラーにせず、digest なしの identity を返します（`strata_control/tune_history.py:56-58`）。

## 実行時の動作

`strata tune run` は engine 引数の解決と存在確認の後、測定 plan を作る段階で `a.full_digests` を `plan_tuning(full_digests=...)` に渡します。plan 作成時にエンジンと（指定があれば）モデルの identity が計算され、比較 key には digest、サイズ、digest method、backend、workload、context、machine identity が含まれます（`strata_cli/cli.py:1757-1768`; `strata_control/tuning.py:723-761`; `strata_control/tune_history.py:99-118`）。

この値は identity 計算にだけ使われ、測定モード（`protocol` / `api`）、候補探索、試行回数には渡されません。full digest の読み込みは plan 作成中、測定開始前に行われます（`strata_cli/cli.py:1763-1786`）。

## 適用条件と副作用

- フラグを付けても実際にチューニング sweep を実行し、job 状態・レポートを state directory に保存します。通常の `tune run` と同じ副作用で、digest 計算自体は対象ファイルを読み取るだけです（`strata_cli/cli.py:1802-1806`; `strata_control/tuning.py:335,359-362`）。
- モデルとエンジンが大きいほど全量読み取りに時間がかかります。エンジンは既存確認後に必ず identity 計算されます。モデルは `--model-path` を渡した場合に限り計算されます（`strata_cli/cli.py:1759-1768`; `strata_control/tuning.py:757-761`）。
- `strata tune apply` には full digest 指定がなく、apply 時の identity 再計算は sampled 方式です。したがって full digest で作成した sweep は、apply 側で digest/method が一致せず拒否され得ます。適用の可否に影響する範囲は、`--model-path` でモデル digest を記録した sweep を含みます（`strata_cli/cli.py:461-470,1868-1879`; `strata_control/tune_history.py:121-143`）。なお、モデル path を省いた sweep はモデル digest がなく、apply で明示的に拒否されます（`strata_cli/cli.py:1883-1892`）。

## 出力とエラー

- 通常出力・JSON 出力では、フラグの有無自体を示す専用メッセージは確認できません。レポートの `identity` に算出された digest が含まれます（`strata_cli/cli.py:1805-1838`; `strata_control/tuning.py:640-669`）。
- エンジンパスが存在しない場合はエラーを出して終了コード 2 で戻ります（`strata_cli/cli.py:1759-1761`）。
- digest 対象ファイルを開けないなどの `OSError` は CLI の共通処理に渡り、ファイルエラーとして終了コード 6 になります（`strata_control/tune_history.py:63-65`; `strata_cli/cli.py:2176-2183`）。
- `--full-digests` に値を付けると余分な引数として parser が拒否し、usage とともに終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser 定義と scope: `strata_cli/cli.py:414-459`
- `run` の engine 解決、plan への引き渡しと測定開始: `strata_cli/cli.py:1742-1803`
- full / sampled SHA-256 の実装: `strata_control/tune_history.py:39-81`
- identity 作成と digest method を含む比較キー: `strata_control/tuning.py:723-761`; `strata_control/tune_history.py:99-143`
- apply 時の sampled identity 再計算と model digest 要件: `strata_cli/cli.py:1850-1898`

調査では parser とソースコードの呼び出し経路を確認しました。CLI `--help` の実行、build、GPU 実行、性能測定、テストは行っていません。
