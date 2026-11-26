# `--dump-mixed`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（推論エンジンの標準 generate parser） |
| オプション | `--dump-mixed` |
| 別名 | なし |
| 値 | 出力先ファイルパス（文字列） |

## 役割

生成処理で使われた `mixed` ベクトルを、ホストメモリへ読み戻してバイナリ保存する診断用オプションです。コードコメントでは `bb.mixed` を head 入力とし、head 側の一部処理を外部で再計算する用途を説明しています（`engine/src/program/generate.cpp:828-830`）。usage は出力を post-attention residual と記しています（`engine/src/program/generate.cpp:1388`）。

## 使い方

`--pack` と `--tokens` は標準 parser の基本入力です。既存ファイルを避けるため、一時ファイルを出力先にする例です。

```sh
out="$(mktemp)"
strata generate --pack ./pack --tokens "1,2,3" --dump-mixed "$out"
```

## 値と既定値

- 値は次の argv 要素をそのままパスとして受け取ります。省略時は空文字列で、出力処理を行いません（`engine/src/program/generate.cpp:827-830, 3842-3847, 3894-3897`）。
- 値の形式・存在・拡張子に対する個別 validation はありません。オプションの直後に値がない場合は `--dump-mixed needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- 同じオプションを複数回指定すると `dump_mixed` 文字列への代入が繰り返され、最後に指定したパスが使われます（`engine/src/program/generate.cpp:3894-3897`）。空文字列を値として指定した場合は空のままなので、出力分岐に入りません（`engine/src/program/generate.cpp:25416`）。

## 実行時の動作

parser が値を `Options::dump_mixed` に格納します。通常の generate 経路では、生成・集計処理の後にこの値が空でなければ `ss.block.mixed` から `g.n_embd` 個の float をホスト側 vector にコピーし、指定先を `fopen(..., "wb")` で開いて書き込みます（`engine/src/program/generate.cpp:25416-25429`）。SYCL 実装も同じ数の float を queue の memcpy で読み戻して同様に書き込みます（`engine/sycl/src/program/generate.cpp:14395-14410`）。

出力はヘッダーなしの float 配列です。指定した値を「1回の vector 出力先」として扱い、レイヤーごと・トークンごとのファイル分割はしません。`fopen` の `wb` は同名ファイルがあれば内容を切り詰めます。ファイルサイズは `g.n_embd * sizeof(float)` バイトです（CUDA 系: `engine/src/program/generate.cpp:25416-25429`、SYCL 系: `engine/sycl/src/program/generate.cpp:14395-14410`）。

## 適用条件と副作用

- 標準 generate parser のオプションです。CUDA 系ソースと SYCL 系ソースの双方に parser と出力経路があります（`engine/src/program/generate.cpp:3894-3897, 25416-25434`; `engine/sycl/src/program/generate.cpp:1933-1936, 14395-14415`）。
- `strata-engine` 索引は Qwen3.6 専用 parser を別スコープ `qwen36/` に分けています。今回の調査では同 parser に `--dump-mixed` の定義は確認できず、対象オプションの適用範囲には含めません（`docs/cli/README.md:1036-1043, 1240-1244`; `docs/cli/000_cli_tools.md:7-11`）。
- 出力先を `wb` で開くため、既存ファイルを指定すると上書きされます。ディレクトリの自動作成は行いません（`engine/src/program/generate.cpp:25423-25429`）。
- 出力分岐は生成処理後にあるため、データ転送とディスク書き込みが追加されます。環境変数や別オプションによるパスの優先順位はありません。

## 出力とエラー

- 正常に書き込み処理へ進むと、stdout に `mixed dumped`、ファイルパス、`n_embd`、RMS、平均絶対値を表示します（`engine/src/program/generate.cpp:25430-25433`; SYCL: `engine/sycl/src/program/generate.cpp:14411-14414`）。
- デバイスからの読み戻しに失敗すると `strata generate: reading mixed back failed` を stderr に出し、終了コード 1 を返します。ファイルを開けない場合は `strata generate: cannot write <path>` を出して終了コード 1 です（CUDA 系: `engine/src/program/generate.cpp:25418-25426`; SYCL 系: `engine/sycl/src/program/generate.cpp:14397-14407`）。
- `fwrite` と `fclose` の戻り値は確認していないため、書き込み途中の I/O エラーをこの分岐が検出する保証はありません（`engine/src/program/generate.cpp:25423-25433`; SYCL: `engine/sycl/src/program/generate.cpp:14404-14414`）。

## 根拠

- parser の既定値・引数取得・代入: `engine/src/program/generate.cpp:827-830, 3842-3847, 3894-3897`、SYCL: `engine/sycl/src/program/generate.cpp:511-514, 1882-1887, 1933-1936`
- CLI usage と vector の説明: `engine/src/program/generate.cpp:1208-1214, 1388`、SYCL: `engine/sycl/src/program/generate.cpp:945`
- CUDA 系での読み戻し・ファイル生成・表示: `engine/src/program/generate.cpp:25416-25434`
- SYCL 系での読み戻し・ファイル生成・表示: `engine/sycl/src/program/generate.cpp:14395-14415`
- エンジンと parser scope: `docs/cli/000_cli_tools.md:7-11`、索引: `docs/cli/README.md:1036-1043, 1240-1244`
