# `STRATA_ATTN_MERGE_V2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP 共通の QSA decode attention で、チャンクごとに計算した partials を統合する merge kernel を選ぶ。値が有効なら `attn_merge_v2_kernel`（1）、無効なら `attn_merge_kernel`（0）を起動する。対象は merge 段だけで、チャンク計算側の選択をこの変数は変えない。実装は `engine/src/kernels/cuda/qsa_decode_attn.cu` の `attn_merge_v2()` と `launch_merge()`。実装コメントは両 kernel の出力が bitwise 同じとしている（同ファイル 1003-1020）。

## 値と判定

`attn_merge_v2()` の初回呼び出し時に `std::getenv` で値を読み、関数内 `static const int` に保存する（`engine/src/kernels/cuda/qsa_decode_attn.cu:1005-1010`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 設定値が非空 | `STRATA_ATTN_DAILY` の判定にフォールバック | `atoi(v) != 0`。例: `1`, `-1`, `+1`, `1abc`, ` 1` | `atoi(v) == 0`。例: `0`, `0anything`, `true`, `false`, `abc`, `  ` |
| 設定値が空文字 | `STRATA_ATTN_DAILY` の判定にフォールバック（空文字は未設定相当） | ― | ― |

非空文字列は `atoi` で整数変換し、文字列全体の妥当性検査はしない。したがって先頭の空白や符号を許容し、数値の後ろに文字があっても整数部分で判定する。`atoi` が 0 以外なら v2、0 なら従来版を選ぶ。`STRATA_ATTN_DAILY` はこの変数が未設定または空の場合だけ関係する。`daily_attn()` は CUDA では値がちょうど文字列 `1` の場合に有効、別の設定値なら無効、未設定ならデバイス判定に進む。HIP では常に false を返す（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923`）。

## 有効になる条件

- QSA decode attention の merge 処理が呼ばれること。対象関数では、`qsa_decode_attn_batch`、`qsa_decode_attn_slots`、`qsa_decode_attn_batch_rows`、`qsa_decode_attn_step` がこの選択を merge launch に渡す（`engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1147, 1217-1223, 1295-1301, 1349-1354`）。
- 環境変数の非空値があると、その `atoi` 結果が `STRATA_ATTN_DAILY` より優先される。未設定・空文字の場合、CUDA は `STRATA_ATTN_DAILY=1` または同変数未設定時のデバイス既定値で v2 を選ぶ。未設定時のデバイス既定値は compute capability を初回デバイスごとに調べ、`sm12x_default(..., kGb10AttnDaily)` の結果をキャッシュする。設定された `STRATA_ATTN_DAILY` は文字列全体が `1` でなければ無効（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923`、`engine/include/strata/core/sm120_series.hpp:78-81, 87-95`）。
- AMD gfx12 では、エンジンがアーキテクチャ既定値を適用し、`STRATA_GFX12_DEFAULTS` が先頭文字 `0` でなく、`STRATA_DEFAULTS=026` の既定値セットでもない場合、この変数を `1` に設定する。適用前から値が設定済みなら空文字を含めその値が維持され、利用者の値が優先される（`engine/src/core/arch_defaults.cpp:28-55, 302-310`）。この既定値表は `apply_arch_defaults()` を通じて適用される（`engine/src/program/generate.cpp:4320`）。
- CLI 引数による別の上書き経路は、この値の読み取り・選択箇所には見当たらない。アーキテクチャ既定値は未設定時のみプロセス環境へ設定される（`engine/src/core/arch_defaults.cpp:302-310`）。

## 実行時の詳細

初回 merge 選択時に環境を読み取り、以後は `static` に保持した判定を使う。プロセス実行中に環境を変更しても再評価されない。`STRATA_ATTN_MERGE_V2` が空または未設定なら、`daily_attn()` の既定値に従う。CUDA では `STRATA_ATTN_DAILY` が未設定のときデバイスごとの判定結果も `per_dev[64]` にキャッシュする。HIP の `daily_attn()` は常に false だが、`STRATA_ATTN_MERGE_V2` に非空値があればその明示値は merge kernel 選択に使われる（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923, 1005-1020`）。

`launch_merge()` は v2 が真なら `attn_merge_v2_kernel`、偽なら `attn_merge_kernel` を起動する。両方とも同じ partials、steps、出力領域を受け取る。各 QSA decode 経路は merge 後に CUDA/HIP の起動エラーを検査し、エラー時は経路名とエラー文字列を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/qsa_decode_attn.cu:1013-1020, 1143-1147, 1219-1223, 1297-1301, 1350-1354`）。

## ログと測定値

この変数の値を直接表示するログや、無効値の警告は見当たらない。gfx12 の既定値適用がこの変数を自動設定した場合は、他の gfx12 既定スイッチとともに `strata: gfx12 (RDNA4): exact extra switches on by default ...` の行にスイッチ名が表示される。利用者が値を設定済みならその変数は既定値適用の表示対象に含まれない（`engine/src/core/arch_defaults.cpp:360-370`）。

ソースコメントは二つの merge kernel の出力を bitwise 同一としているが、本調査では再測定していない（`engine/src/kernels/cuda/qsa_decode_attn.cu:1013-1020`）。

## 根拠

- `engine/src/kernels/cuda/qsa_decode_attn.cu:902-923` — `STRATA_ATTN_DAILY` の値判定と CUDA/HIP の既定値。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1003-1020` — 本変数の読み取り、空文字・数値判定、merge kernel の分岐。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1147, 1217-1223, 1295-1301, 1349-1354` — decode 経路からの選択利用と起動エラー処理。
- `engine/src/core/arch_defaults.cpp:28-55, 302-310, 360-370` — AMD gfx12 の既定値と既設定値の優先、観測ログ。
- `engine/src/program/generate.cpp:4320` — アーキテクチャ既定値適用の呼び出し。
- `engine/include/strata/core/sm120_series.hpp:78-81, 87-95` — CUDA compute capability の既定判定に使う helper と GB10 設定。
