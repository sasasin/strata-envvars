# `STRATA_PIPED_CONCURRENT_PRIO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の `Verifier::init` が作る window 用ストリームを、デバイスから問い合わせた最高優先度で作成するかを制御する補助スイッチです。既定では `STRATA_PIPED_CONCURRENT` が有効なとき高優先度作成を試み、`STRATA_PIPED_CONCURRENT_PRIO` を `0` 相当の値にすると通常の既定優先度に戻します。この変数単独では prompt 読み込みと slot window の同時実行を有効にしません。読み取り・ストリーム作成は `engine/src/core/verify.cpp:1310-1333`、同時読み込み本体の有効条件は `engine/src/program/generate.cpp:21024-21054` にあります。

対象の `make_stream` は `copy_`、独自の `cs_`、`sh_cs_` に使われます。外部共有ストリーム `ext_stream_` が設定されると独自 `cs_` の作成は省かれますが、`copy_` と `sh_cs_` は引き続き対象です（`engine/src/core/verify.cpp:1348-1355`）。`STRATA_GRAPH_PRIO` が別途有効なら、同時実行優先度を使わない場合に `gp` 優先度でストリーム作成を試みます（`engine/src/core/verify.cpp:1300-1309,1326-1333`）。

## 値と判定

CUDA ビルド（`STRATA_USE_HIP` と `STRATA_HIP_GFX906` が未定義）では、`make_stream` 内の関数ローカル `static const bool hi` の初回評価時に、`STRATA_PIPED_CONCURRENT` と本変数を `std::getenv` で取得します。本変数が未設定なら既定で許可し、設定されていれば `std::atoi(p) != 0` のときだけ許可します。ただし親条件として `STRATA_PIPED_CONCURRENT` も設定済みかつ `std::atoi(v) != 0` である必要があります（`engine/src/core/verify.cpp:1312-1318`）。

| ビルド | `STRATA_PIPED_CONCURRENT_PRIO` | 結果（`STRATA_PIPED_CONCURRENT` も非ゼロの場合） |
|---|---|---|
| CUDA（HIP/GFX906 以外） | 未設定 | 高優先度ストリーム作成を試す |
| CUDA（HIP/GFX906 以外） | `0`、空文字、`true`、`0anything` | `atoi` が 0 を返すため高優先度を使わない |
| CUDA（HIP/GFX906 以外） | `1`、`-1`、` 1`、`1tail` | `atoi` が非ゼロを返すため高優先度ストリーム作成を試す |
| HIP または `STRATA_HIP_GFX906` | 任意 | この変数を読む分岐がコンパイルされず、通常の non-blocking ストリームを作成する |
| Metal | 任意 | `Verifier::init` が Metal 初期化後に戻るため、この読み取り位置に到達しない |

文字列全体・大文字小文字・空白の妥当性検査はありません。`atoi` は先頭の空白と符号を扱い、数値として読める接頭辞の後ろは判定に使いません。数値接頭辞のない文字列は 0 になります。範囲外の整数文字列に対する `atoi` の結果はここで保証されていません。`STRATA_PIPED_CONCURRENT` が未設定、空文字、`0`、`true` など `atoi` が 0 を返す値なら、本変数が未設定または非ゼロでも高優先度経路には入りません。優先度を選ぶ CLI 引数はなく、`--batch` / `--batch-groups` 等は同時読み込み経路に入るかを間接的に決めます（`engine/src/core/verify.cpp:1314-1318`; `engine/src/program/generate.cpp:17531-17532,21054`）。

## 有効になる条件

- CUDA で、`STRATA_USE_HIP` と `STRATA_HIP_GFX906` が定義されていないこと。この条件以外では本変数による優先度選択を行いません（`engine/src/core/verify.cpp:1312-1333`）。
- `STRATA_PIPED_CONCURRENT` が、初回評価時に設定済みかつ `atoi` で非ゼロになること。これがなければ高優先度要求は偽です（`engine/src/core/verify.cpp:1314-1318`）。
- 同時 prompt 読み込みを実際に行うには、さらに `piped`、画像なし、プロンプト長が `STRATA_PIPED_CONCURRENT_MIN` 以上という条件が必要です。`piped` は `o.batch > 0`、`o.batch_groups > 1`、`n_pipe > 1` の場合です（`engine/src/program/generate.cpp:17531-17532,21047-21054`）。
- 同時 prompt 読み込みは `STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS`、`--pcie-mode dma`、helper cache、GGUF staged source、その他の expert source がある構成では無効化されます。最初に該当した理由を `strata batch: STRATA_PIPED_CONCURRENT is off beside %s` と stderr に出します（`engine/src/program/generate.cpp:21027-21043`; 判定順と条件: `engine/include/strata/program/batch_read.hpp:30-53`）。
- `STRATA_GRAPH_PRIO` も有効な場合、本変数が無効なら `gp` を使った優先度作成を試せます。本変数の高優先度作成が成功した場合は先に返るため、そのストリームでは `gp` 経路より優先されます（`engine/src/core/verify.cpp:1300-1309,1320-1329`）。

## 実行時の詳細

判定値は `make_stream` 内の関数ローカル `static const bool` に保存されます。したがってプロセス内で最初にこの関数が呼ばれた時点の両環境変数を使い、その後の環境変更は反映されません。高優先度が選ばれると、Strata はデバイスの優先度範囲を問い合わせ、その `top` 値で `cudaStreamCreateWithPriority(..., cudaStreamNonBlocking, top)` を試します。範囲問い合わせまたは優先度付き作成に失敗した場合は `cudaGetLastError()` でエラー状態を消費し、`STRATA_GRAPH_PRIO` が有効なら `gp` の優先度付き作成を試した後、通常の `cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)` に進みます（`engine/src/core/verify.cpp:1319-1333`）。

通常の作成も失敗した場合、`copy_` 用なら初期化は `verify: copy stream create failed`、compute/shared-expert stream 用なら `verify: stream create failed` を `err` に設定して失敗します（`engine/src/core/verify.cpp:1348-1356`）。優先度範囲問い合わせや優先度付き作成だけの失敗では専用の警告ログはありません。

## ログと測定値

本変数専用の有効ログや測定値はありません。高優先度問い合わせ・作成が失敗しても、その場で `cudaGetLastError()` を呼び、通常のストリーム作成へ fallback します（`engine/src/core/verify.cpp:1320-1329`）。`STRATA_GRAPH_PRIO` が有効な場合に限り、別機能のログ `strata verify: STRATA_GRAPH_PRIO: stream priorities side %d, cs / side2 %d, shared expert %d` が出ます（`engine/src/core/verify.cpp:1308-1309`）。

## 根拠

- `engine/src/core/verify.cpp:1310-1333` — 環境変数の読み取り、値判定、優先度付き作成と fallback。
- `engine/src/core/verify.cpp:1348-1356` — 各ストリームへの適用と初期化失敗経路。
- `engine/src/core/verify.cpp:978-993` — Metal 初期化がストリーム設定より前に戻る経路。
- `engine/src/program/generate.cpp:17531-17532,21024-21054` — 同時 prompt 読み込みの判定・適用条件。
- `engine/include/strata/program/batch_read.hpp:30-53` — 同時読み込みを無効にする構成と判定順。
