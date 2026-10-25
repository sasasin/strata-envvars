# `--model-path`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--model-path` |
| 別名 | なし |
| 値 | モデルファイルのパス。文字列として受け取る |

## 役割

測定対象モデルのファイル identity をチューニング計画に含めます。identity は内容 digest とファイルサイズを使った履歴比較用で、引数値はエンジン起動引数や測定 workload には渡されません。したがって、この指定だけで測定に使うモデルを選択・読み込みするわけではありません。モデル識別子 `--model` と、API モードの worker が使う設定 `--config` は別に指定します。

## 使い方

```sh
strata tune run --engine ./strata --backend cuda --model example --model-path ./models/example.gguf
```

`--engine`、`--backend`、`--model` は `run` の必須引数です。`--model-path` は省略可能で、ファイルを指定する場合は現在の作業ディレクトリからの相対パスまたは絶対パスを使えます。

## 値と既定値

- parser は `default=None` の文字列引数として定義し、`choices`、型変換、独自 validation は行いません。短縮 alias もありません（`strata_cli/cli.py:447-450`）。
- 指定した空文字列は parser では受理されますが、CLI は truthiness で判定するため未指定と同じ扱いになり、モデル identity は作られません（`strata_cli/cli.py:1763-1768`）。
- パスが存在しないと `file_identity()` はエラーにせず、digest とサイズが `None` の identity を返します。そのため sweep 自体は続きますが、モデル内容による比較はできません（`strata_control/tune_history.py:48-58`; `strata_control/tuning.py:753-761`）。
- 存在する通常ファイルは、既定で sampled SHA-256 により識別します。サイズは必ず含め、12 MiB 以下なら全内容、それより大きければ先頭・中央・末尾の各 4 MiB を読みます。`--full-digests` を同時に指定した場合はファイル全体を SHA-256 で読みます（`strata_control/tune_history.py:39-45,48-81`）。
- `--model-path` に値を複数回指定した場合の専用処理はありません。argparse の通常の単一値引数として最後の値が残ります（parser 定義: `strata_cli/cli.py:447-450`）。

## 実行時の動作

CLI は engine の存在を確認した後、`Path(a.model_path)` を `plan_tuning()` に渡します。`plan_tuning()` はこのファイルから model digest を作り、比較 identity に digest、サイズ、digest method を含めます。比較 identity には engine identity、backend、workload、context、machine identity も含まれ、値が異なる記録は同じ条件の測定として比較されません（`strata_cli/cli.py:1759-1768`; `strata_control/tuning.py:723-761`; `strata_control/tune_history.py:99-118`）。

このパスは測定プロセスには渡されません。標準の protocol 測定で起動する engine の argv は `--serve` と候補設定の engine flags から組み立てられます（`strata_control/tune_engine.py:415-420,596-609`）。API モードで worker が使うモデル設定は `--config` 由来です（`strata_cli/cli.py:1771-1786`）。

モデル path を省略した sweep は `model_digest: null` を記録します。後で `strata tune apply` する際、このような sweep はモデル digest がないため適用を拒否され、エラーは終了コード 2 です。apply 側にも別スコープの `--model-path` がありますが、この文書の対象は `strata tune run` の引数です（`strata_cli/cli.py:461-470,1868-1894`）。

## 適用条件と副作用

- このオプションがあるのは `strata tune run` parser です。同じ文字列の `strata tune apply --model-path` は別の引数・目的を持ちます（`strata_cli/cli.py:414-459,461-470`）。
- パスは `Path()` にそのまま渡され、`expanduser()` は呼ばれません。シェル展開されない引用済みの `~` はホームディレクトリとして補完されません。ディレクトリや読み取り不能なファイルを事前に拒否する専用 validation もありません（`strata_cli/cli.py:1763-1768`; `strata_control/tune_history.py:48-81`）。
- 通常の digest 計算は対象ファイルの一部または全体を読み取ります。`--full-digests` 併用時は、モデルファイル全体の読み取り時間が追加されます。ディレクトリなど `open("rb")` できないパスでは `OSError` が CLI 共通処理に渡り、ファイル操作エラーとして終了コード 6 になります（`strata_control/tune_history.py:60-80`; `strata_cli/cli.py:2176-2183`）。
- `strata tune run` 自体は sweep を実行し、job 状態と report を state directory に保存します。identity 用の読み取り以外に、このオプションによるモデルファイルの変更は確認できません。設定への推薦適用は別の `strata tune apply` です（`strata_cli/cli.py:1643-1650,1708-1709,1802-1806`; `strata_control/tuning.py:317-362,682-714`）。

## 出力とエラー

- `--model-path` がない、または指定先が存在しない場合に、このオプション単独の警告・エラーはありません。digest がない記録は履歴で他の実在モデル identity と比較されません（`strata_control/tune_history.py:56-58,99-118`; `strata_control/tuning.py:753-761`）。
- `--engine` が存在しない場合は sweep 前にエラーを出し、終了コード 2 で戻ります（`strata_cli/cli.py:1759-1762`）。
- identity 対象を開けないなどの `OSError` は CLI 共通エラーとして出力され、終了コード 6 になります（`strata_control/tune_history.py:60-80`; `strata_cli/cli.py:2176-2183`）。
- 通常の human 出力は job ID、計測結果、状態確認コマンドを表示します。JSON 出力では job を返します。どちらも sweep が対象で、モデル path を指定しただけで設定を変更することはありません（`strata_cli/cli.py:1802-1806,1808-1846`）。

## 根拠

- `strata_cli/cli.py:414-459` — `strata tune run` parser と `--model-path` の default・値規則。
- `strata_cli/cli.py:1708-1709,1742-1768` — run の dispatch、engine 存在確認、model path と full-digest 指定を計画へ渡す処理。
- `strata_control/tuning.py:723-768` — plan の identity 生成。path がなければ digest なし、指定時はモデルファイル identity を作成。
- `strata_control/tune_history.py:39-81,99-118` — sampled/full digest の計算と比較 identity の構成。
- `strata_control/tune_engine.py:388-420,596-609` — 測定 subprocess の argv に model path が含まれないこと。
- `strata_cli/cli.py:1771-1786,1840-1846` — API モードの worker 設定と測定結果の説明。
- `strata_cli/cli.py:461-470,1868-1894` — `tune apply` 側の別スコープの同名引数と model digest の適用要件。
- `strata_cli/cli.py:2176-2183`; `strata_control/tuning.py:317-362,682-714` — OSError の CLI 処理、job 状態と履歴の保存。

調査日: `2026-10-25`。Strata の作業状態は `main...origin/main` で変更表示なしでした。CLI `--help`、build、GPU 実行、性能測定、テストは行わず、parser と同一 revision のソースを確認しました。
