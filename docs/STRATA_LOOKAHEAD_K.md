# `STRATA_LOOKAHEAD_K`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

ルーティング先読みで、各 token について次層（または CUDA 系のより深い先読み設定で対象になる層）の上位何 expert までを予測し、先読み対象にするかを指定します。予測器は現在層の MoE 入力に対象層の router 重みを適用して上位 expert を選び、GPU または RAM 側に既にある expert を除いて `ExpertSource::warm()` に渡します。これはデータの先読みだけで、実際に計算する expert や router の結果は変更しません。

## 値と判定

`generate.cpp` は `std::getenv("STRATA_LOOKAHEAD_K")` の値を `std::atoi` に渡します。未設定なら既定値は `10` です。設定値は文字列全体の検証ではなく、`atoi` が先頭から読める整数部分を使います。したがって、先頭空白と符号は受け付け、整数の後ろの文字は無視します（例: `" 5tail"` は 5）。空文字や整数で始まらない文字列は 0 になります。

`RouterLookahead::start()` は値を expert 数の範囲に制限します。

| `atoi` の結果 | 実際の予測数 |
|---|---:|
| 1 未満（0、負数を含む） | 1 |
| 1 以上、層あたりの expert 数以下 | その値 |
| 層あたりの expert 数より大きい | 層あたりの expert 数 |

そのため `STRATA_LOOKAHEAD_K=0` や不正文字列は先読みを無効にせず、1 expert に丸められます。未設定時の 10 も expert 数が 10 未満ならその数に丸められます。

根拠: `src/program/generate.cpp:5510-5511`, `sycl/src/program/generate.cpp:5081-5082`, `src/core/expert_source.cpp:2183-2193`。

## 有効になる条件

この変数だけでは先読みを開始しません。値の読み取りと予測器の起動は生成経路の条件を満たしたときだけです。

- CUDA 系 (`src/program/generate.cpp`) では `srcp` が存在し、ファイル source が通常 warm 可能であるか、Foresight swap の先読みまたは統計計測が有効である必要があります。また `STRATA_LOOKAHEAD` が未設定か、`atoi` の結果が 0 以外である必要があります。統計計測は `STRATA_LOOKAHEAD_STATS`、Foresight 側は `STRATA_FS_SLOTS` と `STRATA_FS_AHEAD` による条件です。
- SYCL 系 (`sycl/src/program/generate.cpp`) では `src` が warm 可能で、`STRATA_LOOKAHEAD` が未設定か `atoi` の結果が 0 以外の場合に起動します。
- 両経路で router 重みが arena 内の BF16 で、形状が `n_expert * n_embd` と一致し、重みの host copy に成功する必要があります。CUDA/SYCL の各実装は全層分を確認してから `RouterLookahead::start()` を呼びます。
- 先読み worker は層あたり最大 8 token 分の入力を受け取り、既に GPU または RAM にある expert を予測対象から除外します。対象層に到達しない最終層では予測要求を出しません。

CUDA 系では `STRATA_IO_PREFETCH_DEPTH` が正数なら予測する層数を 1〜4 に丸めて設定します。そうでなく、通常の file source が `io_prefetch()` を使う場合は深さ 2、その他はクラス既定の深さ 1 です。SYCL 系はこの深さ設定をここでは行わず、既定の 1 層です。いずれの場合も `STRATA_LOOKAHEAD_K` は対象層ごとの上位 expert 数を決めます。

根拠: `src/program/generate.cpp:5491-5517`, `sycl/src/program/generate.cpp:5066-5083`, `include/strata/core/expert_source.hpp:240-265`。

## 実行時の詳細

環境変数は生成経路の先読み初期化時に一度読み取られ、その値を `RouterLookahead::start()` が `k_` に保存します。各 token/window ごとに環境を読み直す処理はありません。worker は各 token の router score を降順に並べ、上位 `k_` expert を集約します。resident 判定で除かれた残りを source に warm 要求します。CUDA 系で Foresight swap がある場合は、次層についてその候補を Foresight にも渡します。

`STRATA_LOOKAHEAD_K` は予測の幅を変えますが、実際の routing ID、計算経路、出力値を選択・上書きする処理には使われません。初期化で予測器を開始できなかった場合、CUDA/SYCL のコードは `routing-aware prefetch off (...)` を stderr に出します。開始した場合は、それぞれ `routing-aware prefetch on ...` のログを出します。

根拠: `src/core/expert_source.cpp:2202-2210,2333-2383,2409-2412`; 呼び出し元 `src/core/expert_source.cpp:3634-3639`。

## 文書との照合

`docs/DETAILS.md:225-229` は Linux file-tier I/O prefetch の文脈で `STRATA_LOOKAHEAD_K` を次層 router 予測の expert 数として記載し、先読み深さの既定値が I/O prefetch 有効時に 2 であると説明しています。`docs/UNSLOTH_Q4.md:228-235` は既定値 10 を記載しています。コードでは K が未設定なら 10、I/O prefetch 有効時の CUDA 系の深さは 2 ですが、K は expert 数を上限に clamp されます。また、SYCL 系は同じ K を読むものの、ここでのコードでは深さ 2 の特別設定を行いません。
