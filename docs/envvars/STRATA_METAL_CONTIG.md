# `STRATA_METAL_CONTIG`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine の SSD streaming が使う、GGUF 隣の連続配置 expert ファイル `<model>.experts` を利用するか選びます。利用すると各 expert の gate/up/down のデータを連続配置ファイルから読みます。無効にすると、元の GGUF から3つの tensor slice を読む経路になります。

## 値と判定

`metal/src/engine/stream.cpp` 内の `env_int()` は、変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で整数に変換します。`STRATA_METAL_CONTIG` の既定値は `1` で、変換結果が 0 以外なら連続配置ファイルを検査します。

| 値 | 判定と動作 |
|---|---|
| 未設定、空文字 | 既定値 `1`。連続配置ファイルを検査する |
| `1`、`2`、`-1` など、`atoi` 結果が 0 以外 | 連続配置ファイルを検査する |
| `0`、`00`、`abc`、`0tail` など、`atoi` 結果が 0 | 連続配置ファイルを使わず、GGUF本体から読む |

文字列全体との比較ではありません。`atoi` が先頭の空白や符号付き数値を変換し、数字以降を読み取らないため、たとえば `1tail` は有効、`tail1` は 0 になります。大小文字の比較はありません。

## 有効になる条件

- `STRATA_METAL_STREAM` により expert streaming が選択され、`Window::init()` が `ExpertStream::open()` を呼ぶ場合にだけ評価されます。stream が使われない場合は、設定値にかかわらずこの変数は参照されません。
- stream を使っていても、連続配置ファイルが開けない、形式・サイズ・GGUFとの対応が一致しない、または先頭・末尾のサンプルbytesが異なる場合は採用されません。その場合は元のGGUFから読みます。`STRATA_METAL_CONTIG` が 0 の場合は連続配置ファイルの検査自体を飛ばします。
- この設定は Metal engine のコードにあります。CUDA/HIP/SYCL engine での動作は確認されません。

## 実行時の詳細

`ExpertStream::open()` は先に元GGUFを開き、layerごとの expert tensor offset とサイズを記録します。`STRATA_METAL_CONTIG` の変換結果が 0 以外なら `<GGUF path>.experts` を開きます。ファイルのヘッダーが `STRX`、version が 1、layer数が48、expert数が512、記録された元ファイルサイズとtensorサイズが一致することを確認し、layer 0 の最初と layer 47 の最後の expertについて各sliceのbytesをGGUFと照合します。

検査に通ると `.experts` のファイル記述子と各layerのoffsetを保持し、stderr に `strata metal stream: experts read from <path> (one request per expert)` を出します。読み込み時はexpert全体を `split_` 個に分けて `.experts` から取得します。変数を 0 にするか、検査に失敗した場合は `.experts` を使わず、GGUFのgate/up/down各sliceを読みます。不一致のファイルが開けていた場合、stderr に `strata metal stream: <path> is not this GGUF's (sizes or bytes differ): the GGUF is read` を出します。sidecarを開けない場合、この不一致ログは出ずGGUF経路に進みます。

値は環境変数の実行時変更ごとには再評価されず、stream初期化時の `open()` 呼び出しで読みます。stream準備後に値を変更しても、すでに選ばれた読み込み元は変わりません。

## 根拠

- `metal/src/engine/stream.cpp:27-30,74-120`: 整数変換、既定値、sidecar検査・採用・fallback・ログ。
- `metal/src/engine/stream.cpp:272-305,335-346`: 採用された読み込み元に応じたexpert読み込み経路と分割数。
- `metal/src/engine/stream.h:94-98`: `cfd_` がある場合は連続配置ファイル、`STRATA_METAL_CONTIG=0` の場合は常にGGUFを使う旨。
- `metal/src/engine/window.cpp:451-458`: stream判定後にのみ `ExpertStream::open()` を呼ぶ。
- `docs/MAC.md:274-276`: ユーザー向け資料では `STRATA_METAL_CONTIG=0` を「Streaming: read the model file even when the experts' copy is there」と説明。ソースの分岐と一致する。
