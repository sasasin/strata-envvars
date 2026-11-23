# `STRATA_HIPBLASLT_MIN_M`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling2 HIP backend の BF16 行列積で、hipBLASLt 経路を試す最小の `M`（行数）を設定する。初期値は `8`。値を上げると小さい `M` の演算では hipBLASLt を使わず、下げると既定より小さい `M` でも他の条件を満たせば hipBLASLt を試す。これは選択しきい値であり、結果の `M` や演算内容自体を書き換えるものではない。読み取りは `HipBackend::init`、適用は `launch_bf16_opt` にある（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-565,703-711,2582-2609`）。

## 値と判定

`HipBackend::init` が `std::getenv` で値の有無を調べ、設定されていれば `std::atoi` で整数変換する。変換値が `1` 以上の場合だけしきい値に採用し、それ以外は初期値 `8` のままにする。文字列全体の妥当性検査はなく、`atoi` が読む先頭の整数部分が使われる。したがって先頭の空白や符号は受け付けられ、`8junk` は `8`、`0anything` は `0` として扱われる。空文字、`true`、`false`、数値で始まらない文字列は `0` となり、既定値に戻る。大文字小文字は数値変換に関与しない。整数型の範囲外の入力に対する安全な検査はない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:707-711`）。

| 条件 | unset | 有効になる値（例） | 採用されず既定値になる値（例） |
|---|---|---|---|
| HIP backend の初期化 | `8` | `1`, `8`, `16`, `+4`, ` 9`, `8junk` | 空文字, `0`, `-1`, `true`, `false`, `0anything` |

## 有効になる条件

- HIP backend がビルドされ、その `HipBackend::init` が実行される必要がある。既定 backend の選択では、`force_cpu` が false で、ビルド時に CUDA / EP-CUDA が先に選択されない場合に HIP が選ばれる（`engine/src/inkling2/ink_backend.h:131-167`）。
- hipBLASLt runner が `ready()` である必要がある。runner は RDNA2 と世代不明の場合に初期化を拒否し、`STRATA_HIPBLASLT` が設定されると `atoi` の非ゼロ判定で有効・無効を上書きする。既定では RDNA4 が有効、その他の世代は無効で、ライブラリや必要シンボルなどの初期化が成立しない場合も利用できない（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-105`）。これは `STRATA_HIPBLASLT_MIN_M` 自体の判定とは別の条件である。
- 各 `launch_bf16_opt` 呼び出しで `M >= 設定値`、`N >= 64`、`K >= 64` が必要。さらに BF16 変換用 scratch buffer の容量が必要量以上で、`gemm_bf16_f32` が成功した場合に hipBLASLt の結果を採用する（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2582-2593`）。
- `M` しきい値未達、`N` / `K` 不足、scratch 不足、または GEMM が成功しない場合はこの hipBLASLt 経路を抜け、条件が合えば HIP BF16 WMMA、それ以外は `launch_bf16_linear` に進む（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2594-2609`）。
- この変数を CLI 引数や設定ファイルで上書きする読み取り箇所は見つからない。`STRATA_HIPBLASLT` は runner 自体の有効・無効を制御するため、このしきい値を設定しても runner が無効なら hipBLASLt は使われない（上記 runner と dispatch の根拠を参照）。

## 実行時の詳細

値はバックエンド初期化中、hipBLASLt runner の `init` と `warmup` の後に読み取られ、メンバー `blaslt_min_m_` に保存される。各 BF16 GEMM のたびに環境変数を再読込するのではなく、この保存値を `launch_bf16_opt` が参照する。プロセス実行中に環境を変更しても現在の backend の値には反映されず、次の backend 初期化で再評価される（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:703-711,2582-2589`）。

しきい値を通過した呼び出しでは入力 `X` を BF16 scratch に変換し、`blaslt_.gemm_bf16_f32` の成功時は必要なら出力へ bias を加えて戻る。失敗または事前条件不成立時の処理は前節の WMMA / `launch_bf16_linear` 経路である（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2582-2609`）。

## ログと測定値

この変数の値の採用・不採用や `M` しきい値による分岐を報告するログは、この読み取り箇所と dispatch にない。調査対象のソース・資料で、この変数に結び付いた測定値は確認できなかった。

## 根拠

- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-565,703-711` — HIP backend の初期化と値の読み取り、既定値 `8`、`atoi` と `v >= 1` の採用条件。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2582-2609` — hipBLASLt dispatch の `M/N/K` 条件、scratch 条件、成功時の処理と後続 fallback。
- `engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-105` — runner の世代条件、`STRATA_HIPBLASLT` による有効・無効、実行時初期化失敗時の未準備状態。
- `engine/src/inkling2/ink_backend.h:131-167` — backend factory のビルド条件と既定選択順。
