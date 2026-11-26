# `STRATA_RDNA2_SGEMM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP 版の dense prefill GEMM の一部を、16-bit 入力を FP32 バッファへ拡張して `hipblasSgemm` で計算する opt-in 切り替え。対象経路では FP16/BF16 入力の `Gemm::f16` / `Gemm::bf16` がこの実装を呼び、適用された積は FP32 出力 `Y` に加算係数 `beta` で書く。GPU 全体や decode の設定ではない。CUDA/SYCL にはこの読み取り・実装はない。`engine/src/prefill/gemm.cu:1052-1066, 1120-1140, 1191-1194, 1303-1306, 1358-1360`

## 値と判定

`rdna2_sgemm_on()` の関数内 `static const int mode` 初期化で `std::getenv` を一度読み、結果をプロセス内で保持する。未設定または空文字列なら mode 0。文字列が厳密に小文字の `all` と一致すると mode 2。それ以外は `std::atoi(v) > 0` なら mode 1、そうでなければ mode 0。整数全体の妥当性検査はないため、`atoi` が先頭から読める正の10進数を含む値（例 `1x`, `1.5`, ` 1`, `+1`）も mode 1 になる。数値に変換できない文字列、`0`、`-1`、`0x10` は mode 0。`all `、`ALL`、` true` は mode 2 にならない。`atoi` の範囲外入力の結果は本コードで検査・規定していない。`engine/src/prefill/gemm.cu:1082-1089`

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP build、mode 判定 | mode 0（native GEMM） | `all` は全 AMD device、`atoi` 結果が正なら gfx103x のみ | `0`, `-1`, `true`, `ALL`, 空文字 |
| CUDA / SYCL build | この変数を読むコードなし | 該当なし | 該当なし |

`mode=1` では device 名 `gcnArchName` の先頭6文字が `gfx103` かを確認する。device が選べない、device index が 0–63 の範囲外、または device properties の取得に失敗した場合は無効として呼び出し元が native 経路を続ける。`all` は architecture 判定を通らず全 AMD device で有効になる。どちらの mode も出力行数 `N < 64` では無効。`K <= 0` でも SGEMM 関数は失敗扱いで戻る。`engine/src/prefill/gemm.cu:1090-1102, 1120-1123`

## 有効になる条件

- HIP (`__HIPCC__`) でビルドされた engine であること。環境変数の読み取りと本体は `__HIPCC__` の条件付きコードにある。engine で CLI 引数や設定ファイルとこの値を合成する処理はなく、環境値の mode 判定が直接使われる。`engine/src/prefill/gemm.cu:1052, 1141`
- mode が 1 なら実行中 device が `gfx103x`、mode が `all` なら AMD device であること。さらに `N >= 64`、`K > 0` が必要。`engine/src/prefill/gemm.cu:1090-1102, 1122`
- BF16 `Gemm::bf16` では、`ldx == 0`（連続行）であり、前段の `f16_io_` 経路が処理を終えておらず、ビルド済み hipBLASLt がある場合は `try_hipblaslt` も処理を終えていないこと。前者なら SGEMM 呼び出し自体を飛ばし、hipBLASLt が成功すればそこから return する。 `f16_io_` 経路で `beta != 0` の場合は SGEMM へ進まず stderr に `prefill gemm: an accumulating BF16 GEMM on the FP16 prompt path` を出して `exit(1)` する。`engine/src/prefill/gemm.cu:1169-1194`
- FP16 `Gemm::f16` では、HIP の `f16_io_ && beta == 0` 経路が先に `f16_inplace` を実行して return する。ビルド済み hipBLASLt が積を処理した場合も SGEMM へ進まない。`engine/src/prefill/gemm.cu:1318-1327, 1358-1360`
- 必要な FP32 変換バッファを確保できること。確保に失敗した場合は SGEMM を行わず、呼び出し元が native GEMM に進む。`engine/src/prefill/gemm.cu:1104-1114, 1125-1126, 1191-1194, 1358-1360`
- `STRATA_HIP_PROMPT_F16` 自体はこの関数で読まないが、prefill 初期化で選ばれた `m.f16_io` が `Gemm` に渡され、上記の先行 FP16 経路を制御する。`engine/src/prefill/prefill.cpp:2724-2729`, `engine/src/prefill/gemm.cu:1169-1179, 1318-1320`

## 実行時の詳細

環境変数値は `rdna2_sgemm_on()` が最初に呼ばれた時に一度だけ評価され、後からの環境変更は反映されない。gfx 判定も device ごとの固定長 atomic 配列に cache される。`mode=1` で architecture 判定が失敗したときはその呼び出しでは native 経路に戻る。`mode=all` は device 判定をしない。`engine/src/prefill/gemm.cu:1083-1102`

SGEMM は重みを FP32 に広げ、入力行を最大 `32 Mi` FP32 要素（128 MiB）の slice に分けて同じ stream で処理する。BF16 の拡張は 16-bit 値の上位ビットを FP32 に写し、FP16 は half-to-float 変換を使う。slice ごとの出力領域は別々なので各々に呼び出し元の `beta` を渡す。必要サイズに応じて `tc_w_` / `tc_x_` を再利用または確保し、再確保前には過去 GEMM が stream 上で読むバッファを解放しないよう同期する。`engine/src/prefill/gemm.cu:1068-1080, 1104-1116, 1120-1139`

変換バッファの `cudaMalloc` が失敗すると Strata は CUDA/HIP の last error を消費して `false` を返し、呼び出し元の native GEMM に進む。この fallback に専用ログはない。SGEMM の `hipblasSgemm` が失敗した場合、共通 `ck()` が stderr に `prefill gemm: hipblasSgemm (RDNA2): cuBLAS status %d` を出して `exit(1)` する。成功を示す専用ログはない。`engine/src/prefill/gemm.cu:1105-1113, 1135-1138, 160-165`

## ログと測定値

有効化・architecture 判定・バッファ確保失敗を知らせるログはコードにない。SGEMM 呼び出し失敗時だけ上記 `ck()` の status ログと終了がある。ソースコメントには RX 6800 / ROCm 10.2.0a20260930 の個別測定（Coder の prompt shapes、12K token prompt で GEMM 合計 14.1 秒から 4.7 秒、BF16 hyper-connection GEMM 10.9 ms から 7.5 ms）が記載されているが、特定条件での開発者測定であり、一般性能の保証ではない。`engine/src/prefill/gemm.cu:1056-1063, 160-165`

`docs/AMD_HIP.md:517` の説明は「`STRATA_HIP_PROMPT_F16=1` と併用すると FP16 route が先に実行され、SGEMM が残った積を処理する」としている。一方、現行 `Gemm::bf16` は `f16_io_` なら `f16_inplace` 後に無条件 return し、`Gemm::f16` も `f16_io_ && beta == 0` なら先に return するため、これらの呼び出しでは当該 GEMM は SGEMM に到達しない。適用結果は説明ではなく上記の現行分岐に従う。`engine/src/prefill/gemm.cu:1169-1179, 1191-1194, 1318-1320, 1358-1360`

## 根拠

- `engine/src/prefill/gemm.cu:1052-1066` — HIP 限定の機能と設計コメント。
- `engine/src/prefill/gemm.cu:1082-1102` — 値の読み取り、static cache、device 判定。
- `engine/src/prefill/gemm.cu:1104-1140` — バッファ確保、FP32 変換、slice SGEMM と失敗処理。
- `engine/src/prefill/gemm.cu:1169-1194, 1303-1360` — BF16/FP16 の先行経路と native fallback。
- `engine/src/prefill/prefill.cpp:2724-2729`; `engine/include/strata/prefill/gemm.hpp:63-66` — `f16_io_` の設定元と用途。
- `docs/AMD_HIP.md:510-518`; `docs/SETTINGS.md:294` — 補助資料との照合。
