# `FNX_BDECODE_SEED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`split_fnx_run` の `bdecode` モードで、各 lane の乱数生成器 `std::mt19937_64` に渡す seed を指定します。基準 seed を `seed0` とし、lane 番号 `r` には `seed0 + r` を割り当てます。値は lane ごとの生成過程に使われる乱数列を変えます。通常の `strata` CLI や sFNX サーバーの環境設定ではなく、Strata split engine の lab/test driver にある `bdecode` 専用設定です。

## 値と判定

変数は `fnx::env_int("FNX_BDECODE_SEED", 1000)` で読みます。未設定なら `1000` です。設定値は符号付き十進整数として文字列全体を検査し、成功した値を `long long` から `int` にキャストします。

| 値 | 処理 |
|---|---|
| 未設定 | 既定値 `1000` を使用 |
| `0`、正負の整数（例 `+7`, `-7`） | 受理し、読み取った数を seed の基準値にする |
| 空文字、空白始まり、整数でない文字、末尾に余分な文字がある値（例 `7x`）、`long long` の範囲外 | `std::runtime_error`。`fnx_run` は stderr に `fnx_run: FNX_BDECODE_SEED: '<値>' is not a whole number` を出し、終了コード 1 |

`parse_whole` は先頭が符号または数字であることを確認したうえで `strtoll(..., 10)` を使い、文字列末尾まで消費したことと `ERANGE` でないことを要求します。小数、基数接頭辞、空白、部分的に読める値は受理しません。`long long` から `int` への変換に範囲チェックや clamp はありません。`int` の範囲外の値の変換結果は処理系依存で、その後の `seed0 + r` にも別途範囲制限はありません。

## 有効になる条件

- `bdecode` は `fnx_run MODEL.gguf bdecode [LANES] [N] [PROMPTS]` の lab モードです。lane 数は既定 2、許容 1〜6、生成 token 数は既定 512、1 以上です。seed 用の CLI 引数はありません。
- `bdecode` に入るには `FNX_BATCH_DRAFTS` が off でない必要があります。未設定または `1` は draft layer、`lookup` は lookup draft、`0` は off です。off の場合は `bdecode: set FNX_BATCH_DRAFTS (lookup or 1)` を stderr に出して終了コード 2 となり、`FNX_BDECODE_SEED` は読みません。不正な `FNX_BATCH_DRAFTS` は別の例外経路です。
- 対象コードは Strata split engine の CUDA/HIP 向け opt-in build 節にある test driver です。split engine 自体も build option であり、通常の Strata 実行経路にこの seed 読み取りはありません。

## 実行時の詳細

`bdecode` はモデルの読込後、batch drafts の有効確認、MTP と Engine の準備、lane と prompt の用意、`BatchDecoder` の構築を経て `FNX_BDECODE_SEED` を一度読みます。その後の2回の run それぞれで、lane `r` に `std::mt19937_64(seed0 + r)` を渡します。最初の run は warm-up として計測結果を表示せず、2回目の run の集計を表示します。したがって同じ環境値のままなら、両 run と lane 順で seed 割り当ては同じです。値は次の `bdecode` 呼び出しでも再評価されます（この読み取り自体に static cache はありません）。

各 lane の `BatchLane` は渡された generator を保持し、sampling が有効なとき、draft token の抽選や draft の受理判定・棄却時の抽選に使います。`bdecode` は sampling temperature `0.6`、top-p `0.95` を設定します。環境変数の値を表示する専用ログはありません。正常時には処理後に `bdecode ...` の速度・window・draft 集計行を stdout に出します。無効な seed は例外となり、その集計出力より前に終了します。

## 根拠

- `src/split/tools/fnx_run.cpp:646-680` — `bdecode` の引数境界、`FNX_BATCH_DRAFTS` の gate、sampling 設定、既定値 `1000`、lane 番号ごとの seed の生成と `BatchLane::start` への引渡し。
- `src/split/tools/fnx_run.cpp:714-728,1364-1373` — warm-up と2回目の集計、例外時の stderr 文言と終了コード。
- `src/split/src/env.hpp:15-22,33-40` — 符号付き十進整数全体の parse、`long long` 範囲確認、未設定時の既定値、無効値の例外。
- `src/split/src/batch.hpp:15-34` と `src/split/src/batch.cpp:40-56,104-117,184-215` — lane が generator を保持し、sampling の draft 抽選と acceptance sampling に使用する処理。
- `src/split/src/engine_common.cu:1020-1028` — `FNX_BATCH_DRAFTS` の許容値と未設定時の既定動作。
- `src/split/CMakeLists.txt:1-5,64-80,92-123,153-165` — split engine の opt-in build と `split_fnx_run` test driver の build 定義。
