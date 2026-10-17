# `STRATA_TOPK_SPLIT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA decode top-k 選択で、1 query あたりの処理を複数 CTA に分割する実装を選びます。選択した cell ID は既存の wide kernel と同じになる設計です。対象は CUDA の decode 選択で、prompt 選択には使われません。

## 値と判定

`topk_split_device()` 内の `static const int` に判定を保存します。`std::getenv` が返す値を `std::atoi` で整数に変換し、未設定は `-1` とします。文字列全体の妥当性検査はありません。

| 設定 | 判定 | 結果 |
|---|---|---|
| unset | `-1` | 対象 GPU が Turing (compute capability 7.5) で、かつ `STRATA_SM75_PERF` が真なら候補になる。それ以外は無効 |
| `0`、空文字、数値変換結果が 0 の値（例: `false`, `abc`） | `0` | GPU にかかわらず無効 |
| `1` など `atoi` の結果が非 0 の値（例: `2`, `-1`, `1tail`） | `1` | GPU にかかわらず有効候補 |

`atoi` は先頭空白と符号を許し、数値の後ろにある文字列を判定に使いません。たとえば `  +1tail` は有効、`0tail` は無効です。環境変数はプロセス内の初回判定時に読み取られ、その後の変更は反映されません。unset 時の既定経路では `STRATA_SM75_PERF` も共通 helper 内で一度だけ読み取られます。

## 有効になる条件

この分割カーネルを実際に呼ぶには、すべての条件が必要です。

- CUDA ビルドである（分割実装と呼び出し箇所は `!__HIPCC__` で囲まれている）。
- `qsa_block_topk()` が decode 経路で呼ばれている（`active_blocks <= 0`）。
- `STRATA_TOPK_OLD` が未設定である。
- `max_blocks >= 16384`、block 幅が `R` と一致し、`cap` が最大選択幅以上である。
- 環境変数による判定が有効である。
- さらに `qsa_block_topk_split()` が `nq` を 1〜16、chunk 数を最大 512 以下とし、GPU 上の histogram symbol を取得でき、初期化の `cudaMemsetAsync` が成功する。

先行する cluster dispatch が成功すれば関数から先に戻るため、`STRATA_TOPK_SPLIT` が有効でも split は実行されません。split の条件を満たさない場合は既存の選択経路に続き、通常の wide / register / reference カーネルが選ばれます。HIP ではこの環境変数を読む dispatch 自体がコンパイル対象外です。

## 実行時の詳細

split 経路では query ごとの block 群を 2048 block 単位の chunk に分け、4 回の radix histogram、threshold 上下の cell 数集計、ID 出力の計 6 kernel launch を行います。通常の decode 選択が wide kernel に集約される場合に比べ、処理を複数 CTA に分配します。ソースコメントは既存の `block_topk_kernel` と同一の threshold、tie の扱い、ID を出力すると説明しています。

この変数専用のログ出力はありません。split launch 後の `cudaGetLastError()` が失敗した場合は stderr に `qsa_block_topk (split): <CUDA error>` を出し、プロセスを終了します。

## 根拠

- `src/kernels/cuda/qsa_select.cu:2030-2038` — CUDA 限定の split 実装、処理方式、ID 同一性に関する実装コメント。
- `src/kernels/cuda/qsa_select.cu:2246-2258` — `STRATA_TOPK_SPLIT` の `getenv` / `atoi` 判定、初回値の保存、device ごとの既定適用。
- `src/kernels/cuda/qsa_select.cu:2261-2281` — query/chunk 上限、histogram 初期化、6 kernel の起動と失敗時 fallback 用の戻り値。
- `src/kernels/cuda/qsa_select.cu:2501-2519` — 先行 cluster 分岐と split を呼ぶ decode 条件。
- `src/kernels/cuda/qsa_select.cu:2516-2518` — split launch 後のエラー表示と終了。
- `include/strata/core/sm75_series.hpp:24-37` — unset 時に参照する `STRATA_SM75_PERF` と compute capability 7.5 の既定条件。
- `docs/DETAILS.md:2244-2257` — `STRATA_TOPK_SPLIT` を含む Turing kernel series の説明。記載の RTX 2080 Ti の測定値はシリーズ全体の説明であり、この変数単独の効果としては扱わない。
