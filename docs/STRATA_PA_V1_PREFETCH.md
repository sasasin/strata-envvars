# `STRATA_PA_V1_PREFETCH`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

CUDA の QSA プロンプト attention にある v1 int8-KV カーネルで、次のセルチャンクの K/V データをレジスタへ先読みする実装を選ぶ。prefetch 版では K と V が共有メモリ上の同じ領域を共有し、K のスコア計算後に V をその領域へ上書きする。ソースコメントは通常版と同じバイト配置・演算で同じ結果になる設計と説明しているが、この調査では性能や数値一致を実測していない。

## 値と判定

変数は `qsa_prompt_attn_batch` 内で初めて該当経路に入った時に `static` 値として一度読み取られる。

| 環境変数の状態・値 | 判定 |
| --- | --- |
| 未設定 | `pf_env = -1`。Turing 相当 (`t75`) かつ `STRATA_SM75_PERF` が有効なら prefetch 版、それ以外は通常の v1 版。 |
| 設定あり | `std::atoi` の結果が 0 なら無効、それ以外なら有効。空文字や数値に変換できない文字列は 0 として扱われる。`1x` や `-1` など、`atoi` が非ゼロを返す値は有効。文字列全体の検証はしない。 |

明示値は Turing 以外でも選択を強制できる。ただし、v1 経路に入ることが前提であり、カーネルの適用条件を越えて単独で有効化するものではない。

## 有効になる条件

- 実行時に `qsa_prompt_attn_batch` が使われること。通常の prefill 呼び出し元は、`STRATA_PROMPT_ATTN_OLD` が設定されていない場合にこの関数を呼び、関数が `false` を返すと decode attention にフォールバックする。
- `qsa_prompt_attn_batch` が CUDA の経路を進み、形状・入力条件を満たすこと。HIP ビルドでは HIP 専用の処理後に戻るため、この環境変数の分岐へは進まない。
- プールが int8 K/V (`pools.k_q != nullptr`) で、Q4 K/V の分岐や hybrid K8V4 の分岐に該当しないこと。K/V のスケール等が欠けているとこのカーネル経路を使わない。
- v1 が選択されていること: `STRATA_PROMPT_ATTN_V1` が設定されている、またはデバイスが Turing 相当 (`turing`) で `STRATA_PA_V2T` の先頭文字が `1` ではないこと。sm_80 以降では v1 を別途選ばない限り v2 系の経路になる。

明示値が非ゼロなら、上記の v1 経路内で `launch<1, true>` を選ぶ。未設定時の既定選択は `t75` と `strata::sm75_series()` の両方が真の場合だけである。`t75` は実デバイスの compute capability 7.5、または `STRATA_EMULATE_CC` による同等の仮想化を反映する。`STRATA_SM75_PERF` は共通 helper で `std::atoi(e) != 0` として一度読み取られる。

## 実行時の詳細

prefetch 版のカーネルでは、各チャンクについて K/V の 16-byte 部分と scale をレジスタへ読み込み、K のスコア計算後に V を共有メモリへ書き込む。その間に次チャンクのデータを読み始め、現在チャンクの計算完了後に次の反復で使う。通常版はチャンクごとに行番号を共有メモリへ置き、K/V を共有メモリへ gather する。prefetch 版は `KV_MODE == 1 && PF` のときだけコンパイル時にこの処理を使う。

`launch<1, true>` が共有メモリ属性の設定に失敗すると `false` を返し、prefill 呼び出し元は decode attention にフォールバックする。カーネル起動後の CUDA エラーは stderr に `qsa_prompt_attn_batch: <CUDA error>` を出してプロセスを終了する。環境変数自体による専用ログはない。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:89-111, 155-185, 187-199, 359-366`: カーネルの `PF` テンプレート、レジスタへの先読み、K/V 共有領域、チャンク間の処理。
- `src/kernels/cuda/qsa_prompt_attn.cu:2254-2284, 2317-2340`: device capability 判定、int8-KV 分岐、v1/v2 選択、`STRATA_PA_V1_PREFETCH` の parse と launch 選択。変数の直接参照はこの箇所のみ。
- `src/kernels/cuda/qsa_prompt_attn.cu:1427-1455`: prefetch テンプレート版の起動、共有メモリ属性設定失敗時の `false` と CUDA 起動エラー処理。
- `include/strata/core/sm75_series.hpp:24-37`: `STRATA_SM75_PERF` の parse と Turing 限定の既定判定。
- `src/prefill/prefill.cpp:3257-3271`: prefill 呼び出し元と、QSA prompt attention が使えない場合の decode attention フォールバック。
- `docs/DETAILS.md:2244-2257`: Turing kernel series と本変数を bitwise Turing kernel の一つとして説明している。測定値は PR 等に帰属させた資料上の記述であり、本調査で再測定していない。
