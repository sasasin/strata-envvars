# `MIGRATE_ONLY`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`sycl/tools/migrate.sh` が SYCLomatic (`dpct`) 用の compilation database を作る際、変換対象の翻訳単位一覧を明示指定します。Strata の通常実行時に読む設定ではなく、CUDA ソースから SYCL port を再生成する開発・移植用スクリプト専用の環境変数です。`docs/INTEL.md` は同スクリプトが CUDA を使う翻訳単位の compilation database を作り `dpct` を実行すると説明していますが、この環境変数による一覧上書きには触れていません。

## 値と判定

Python の `os.environ.get("MIGRATE_ONLY")` を真偽値として判定し、真なら同じ環境変数の値に対して `.split()` を呼びます。数値や `1` など特定の値として parse する処理はありません。

| 値 | 動作 |
|---|---|
| 未設定 | `find` と `grep` で得た既定の一覧を使用する。既定一覧は `src` 以下の `.cu` と CUDA header を含む `.cpp`。 |
| 空文字 | Python では偽となるため、未設定時と同じ既定一覧を使う。 |
| 空白のみ | 空でない文字列なので上書き分岐に入るが、`.split()` の結果は空リストとなり、明示一覧は空になる。 |
| その他の非空文字列 | Python の空白区切りで分割した各要素を、既定一覧の代わりに使用する。 |

文字列全体の形式検証、各パスの存在確認、拡張子の事前制限はこの分岐では行いません。複数語は引用符でグループ化されず、空白で分割されます。

## 有効になる条件

この変数を参照するのは `sycl/tools/migrate.sh` 内で起動される Python プログラムです。通常のエンジン、サーバー、セットアップの実行経路で参照されるコードは確認できません。非空値を設定すると自動検出した一覧は全面的に置き換わります。その後 `src/prefill/moe_mmq.cu`、`src/prefill/ggml_cuda_host.cu`、`src/kernels/native_expert_parity.cpp` は、明示一覧に含まれていても除外されます。

## 実行時の詳細

`migrate.sh` は `setvars.sh` を読み込み、`PATH` を更新してからリポジトリへ移動し、その後に Python の一覧生成処理を実行します。Python は `MIGRATE_ONLY` が真なら値を空白分割し、重複を `set` で除いてソートした上で、上記3パスを除外します。各 `.cu` は `nvcc`、それ以外は `g++` を使う compilation database 項目になります。項目には include path や `-DSTRATA_VERSION="port"` 等が設定され、JSON compilation database を一時ディレクトリへ書き出した後、`dpct` がそのデータベースを用いて変換します。

したがって、空白のみの値や除外対象しか含まない値では、生成される compilation database の翻訳単位数は 0 になります。コード上はその場合も一覧生成後に `dpct` コマンドへ進みます。パスは `cd "$repo"` 後の相対パスとして扱われ、`.cu` 以外は `g++` 用の項目になります。スクリプトは `set -euo pipefail` を有効にしています。

## 根拠

- `sycl/tools/migrate.sh:1-13` — スクリプトの用途、引数・環境準備、Python 実行前に repo へ移動する処理。
- `sycl/tools/migrate.sh:17-36` — 既定一覧の生成、`MIGRATE_ONLY` の真偽判定と `.split()`、除外・重複除去、コンパイラ選択、compilation database の出力。
- `sycl/tools/migrate.sh:38-49` — 生成データベースを用いた `dpct` 実行と結果表示。
- `docs/INTEL.md:330-340` — SYCL port の生成工程の説明。`MIGRATE_ONLY` の値の意味は記載されていない。

