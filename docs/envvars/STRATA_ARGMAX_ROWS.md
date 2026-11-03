# `STRATA_ARGMAX_ROWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

verify head と draft の greedy argmax で、通常の `sample_tokens()` ではなく、1 行を複数 CUDA block に分割して最大値を選ぶ `argmax_rows()` を使うか指定します。この切り替えは `Verifier` の verify head と、coupled draft sampling を使わない MTP draft head の内部経路に適用されます。`STRATA_ARGMAX_ROWS` を直接読むのは `src/kernels/cuda/verify_kernels.cu` だけです。

## 値と判定

環境変数の文字列を `std::atoi()` に渡し、その戻り値が 0 かどうかで判定します。文字列全体の妥当性検査や範囲検査はありません。

| 値 | 判定 |
| --- | --- |
| 未設定 | GPU/backend ごとの自動判定へ進む |
| 空文字、数値変換できない文字列（例 `true`） | `atoi` が 0 を返すため無効 |
| 先頭の空白や符号の後に非ゼロの整数（例 ` 1`, `+1`, `-1`, `1tail`） | `atoi` が非 0 を返すため有効。ただし後続文字は検査しない |
| 0、`0tail` | 無効（`atoi` が 0） |

`atoi` の表現範囲外入力について、実装はエラー検出や fallback を行いません。値の parse 結果は関数内の `static const int` に初回評価時に保存されます。したがって初回評価後にプロセス環境を変更しても再評価されません。

## 有効になる条件

この値が非 0 でも、GPU/backend と `STRATA_MULTI_BLOCK_ARGMAX` の判定を通らなければ `argmax_rows()` は選ばれません。

| 経路 | `STRATA_ARGMAX_ROWS` 未設定時 | 設定値が非 0 の場合 |
| --- | --- | --- |
| CUDA | Compute Capability major 8 で有効。major 7 は `STRATA_ARGMAX_ROWS_SM70` が `atoi != 0` のとき有効。その他は無効 | major による自動選択を飛ばして要求するため、major 7/9 などでも選択可能。ただし `STRATA_MULTI_BLOCK_ARGMAX` が無効なら不成立 |
| HIP wave32（`__HIPCC__`, gfx906 互換ビルド以外） | gfx12 で有効。それ以外は無効 | 要求しても gfx12 以外では無効。`STRATA_MULTI_BLOCK_ARGMAX` が無効なら不成立 |
| gfx906 互換ビルド（`STRATA_HIP_GFX906`） | 無効 | 無効。関数が環境変数を読む前に `false` を返す |
| SYCL | この変数を読まない | この変数による変更なし。SYCL 側は major 8 と `STRATA_MULTI_BLOCK_ARGMAX` で独立に判定 |

CUDA/HIP の `STRATA_MULTI_BLOCK_ARGMAX` は未設定なら既定で有効、設定時は `atoi != 0` です。CUDA で `STRATA_ARGMAX_ROWS` を明示すると major の自動判定を飛ばします。HIP では `multi_block_head_ops()` が gfx12 以外を拒否するため、明示値だけでは他世代を有効にできません。未設定時の CUDA major 7 判定に使う `STRATA_ARGMAX_ROWS_SM70` も `atoi != 0` です。

## 実行時の詳細

CUDA 経路では `argmax_rows_wanted()` が選択を行い、verify の greedy head は true の場合に `argmax_rows()`、それ以外は greedy 設定の `sample_tokens()` を呼びます。MTP draft head も同じ選択をしますが、coupled draft sampling の経路は先に別処理を行って戻るため、この選択を通りません。`argmax_rows()` は行ごとに最大 128 block で logits を走査し、block ごとの候補を統合して出力します。Strata のカーネル API コメントは tie 時に低い index を選ぶこと、通常の greedy pick と bitwise 同一であることを記しています。

環境変数の選択自体に専用ログや警告はありません。カーネル起動後の CUDA エラーは `argmax_rows: <CUDA error text>` を stderr に出し、終了コード 1 で終了します。これは環境変数の parse エラーではなく、選択されたカーネルの起動失敗経路です。

SYCL の `argmax_rows_wanted()` は `STRATA_ARGMAX_ROWS` を参照せず、SYCL デバイスの major 8 と `STRATA_MULTI_BLOCK_ARGMAX` に基づいて判定します。したがって同じ名前を設定しても SYCL 経路の選択は変わりません。

## 根拠

- `src/kernels/cuda/verify_kernels.cu:1009-1031` — `STRATA_MULTI_BLOCK_ARGMAX` の parse、既定値、HIP gfx12 制限。
- `src/kernels/cuda/verify_kernels.cu:1033-1066` — `STRATA_ARGMAX_ROWS` の全読み取り、gfx906 guard、CUDA/HIP の自動判定と `STRATA_ARGMAX_ROWS_SM70`。
- `src/kernels/cuda/verify_kernels.cu:880-915,953-962` — 行ごとの複数 block argmax、scratch と kernel launch。
- `src/core/verify.cpp:2624-2634` — verify head での `argmax_rows()` / greedy `sample_tokens()` 選択。
- `src/core/mtp.cpp:1358-1379` — coupled draft 経路の早期 return と、通常 MTP draft head での選択。
- `include/strata/kernels/verify_kernels.hpp:178-199` — API の tie 規則、bitwise 同一性の説明、選択 API。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:1595-1621` — SYCL 側の独立した判定。`STRATA_ARGMAX_ROWS` の読み取りはない。
- `src/kernels/cuda/verify_kernels.cu:37-40,955-962` — 起動エラーを stderr に出して終了する経路。
- `docs/NVIDIA_V100.md:63,109` — V100 の `STRATA_ARGMAX_ROWS_SM70` に関する資料。対象の `STRATA_ARGMAX_ROWS` の既定値・効果を説明する記述ではありません。
