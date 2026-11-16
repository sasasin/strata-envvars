# `STRATA_I8_TM`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`native_expert_i8()` が gate/up と down の CUDA/HIP int8 expert kernel に渡す tile code を選ぶ研究用変数。int8 expert 経路そのものを有効化する設定ではなく、その関数まで処理が来た場合に tile の行数を指定する。tile 2/3/4 はそれぞれ 32/48/64 entries、tile 8 は variant B の 128 entries を扱う。実装は `src/kernels/cuda/iq_kernels.cu` と `src/kernels/cuda/i8_expert.cuh` にある（`src/kernels/cuda/iq_kernels.cu:6344-6373`, `src/kernels/cuda/i8_expert.cuh:1123-1205`）。

## 値と判定

関数内 helper `i8_env_int()` が `std::getenv()` で読み、未設定または空文字なら既定引数 `0`、それ以外は `std::atoi()` の結果を返す。数値全体の妥当性検査やエラー報告はない。したがって先頭の空白・符号と数値部分は `atoi` の変換規則に従い、変換できない先頭（例 `true`）は 0、数値の後ろの文字は無視される（例 `3junk` は 3）。大文字小文字の区別はなく、文字列真偽値としては解釈しない。整数範囲を超える入力の扱いは `atoi` に委ねられ、Strata 側で制限していない（`src/kernels/cuda/i8_expert.cuh:1208-1211`）。

| 条件 | unset / 空文字 | 有効になる値の例 | 無効または別値になる例 |
|---|---|---|---|
| `native_expert_i8()` が実行された場合 | 0 と同じ自動選択 | `2` → tile 2、`3` → tile 3、`4` → tile 4。`8` 以上は条件を満たせば tile 8 | `0`、負数、`true`（いずれも自動選択）；`1` → tile 2；`5`〜`7` → tile 4；`8` 以上でも条件不成立なら tile 4 |

自動選択（読み取り値が 0 以下、または tile 2 への写像後も 0 相当の場合）は、平均 entries 数 `cap_entries / cap_groups` が 96 以上かつ `n_embd % 128 == 0`・`n_ff % 64 == 0` なら tile 8。それ以外は `(avg + 8) / 16` を 2〜4 に clamp した tile を使う。明示値は `<=2` が tile 2、`3` が tile 3、`4`〜`7` が tile 4、`>=8` が tile 8 候補となる。tile 8 には上記寸法条件に加えて gate/up と down の型が `i8_tile8_type()` 対象である条件が必要（`src/kernels/cuda/iq_kernels.cu:6363-6367`）。

選ばれた tile が型ごとの共有メモリ使用量上限を超えると、tile 8 は 4 に、以降は 1 ずつ小さくして、上限内の tile 2〜4 に落とす。tile 2 でも上限を超えるレイアウトは `native_expert_i8_supported()` の判定対象外となる（`src/kernels/cuda/iq_kernels.cu:6330-6334,6368-6370`）。

## 有効になる条件

- `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` の GPU ビルドで `src/kernels/cuda/iq_kernels.cu` が組み込まれていること。CPU / SYCL / Metal 経路にはこの読み取り実装がない（`cmake/strata_gpu_engine.cmake:8-10,98`; `CMakeLists.txt:91-104`）。
- 呼び出し側が `native_expert_i8()` に到達すること。通常の prefill 経路では `STRATA_EXPERT_I8` の選択、fused/staged 経路の優先、対応する重み形式・寸法・共有メモリ、group entries 数（最低 256）が int8 経路の条件となる。これらを満たさなければ `STRATA_I8_TM` は読まれず、他の経路が処理する（`include/strata/kernels/i8_expert_rule.hpp:28-56`; `src/prefill/prefill.cpp:5966-6010`; `src/kernels/cuda/iq_kernels.cu:6285-6289,6330-6334`）。
- Qwen3.6 standalone engine でも fused / int8 / MMQ / grouped の経路選択を通り、int8 に割り当てられた layer/chunk でのみこの関数を呼ぶ（`src/qwen35/q36_engine.cu:1412-1428,2173-2183`）。
- `STRATA_EXPERT_I8` は int8 経路の選択に関与する別変数であり、`STRATA_I8_TM` がその設定を上書きすることはない。明示した tile も共有メモリ上限で縮小され得る。

## 実行時の詳細

`native_expert_i8()` は `cap_groups <= 0` または `cap_entries <= 0` の場合、または対応外 layout の場合に先に戻る／終了するため、その経路では tile 変数を読まない。その他は関数呼び出しごとに `i8_env_int("STRATA_I8_TM", 0)` を呼ぶ。helper に static cache はないので、プロセス環境が変われば次回呼び出しで再読込される。Strata 内にこの変数を設定・変更する処理や CLI 引数による上書きは見つからなかった（`src/kernels/cuda/iq_kernels.cu:6344-6369`; `src/kernels/cuda/i8_expert.cuh:1208-1211`）。

決まった tile は同じ呼び出し内で tile table の `bm` と gate/up・down の両方の kernel launch に使われる。共有メモリ調整後の tile は `i8_launch()` が tile 2/3/4/8 のテンプレート kernel に振り分ける。別の `STRATA_I8_N8` は tile 2〜4 の 8-entry slice の選択に使われるが、tile code 自体は変更しない（`src/kernels/cuda/iq_kernels.cu:6370-6396`; `src/kernels/cuda/i8_expert.cuh:1123-1157,1199-1205`）。

## ログと測定値

tile 値や自動選択結果を通常実行時に表示するログはない。CUDA expert-paths bench は各異なる要求について stdout に `I8-LAUNCH gu_type=%d d_type=%d tokens=%d tile=%d gu_dyn_smem_bytes=%zu down_dyn_smem_bytes=%zu gu_launch=%s down_launch=%s` を出し、選択 tile と launch 状態を確認できる（`tests/cuda/prefill_expert_paths_bench.cpp:429-445`）。非対応 layout で関数が直接呼ばれた場合は stderr に `native_expert_i8: gate/up type %d, down type %d at %lld x %lld is not covered` を出して終了コード 1 で終了する。activation rows が 4 GiB 以上になる場合も stderr に `native_expert_i8: %lld entries at %lld x %lld exceed 4 GiB of activation rows` を出して終了する。kernel launch エラー時は `native_expert_i8/gu: <CUDA error>` または `native_expert_i8/down: <CUDA error>` を stderr に出して終了コード 1 となる（`src/kernels/cuda/iq_kernels.cu:42-45,6347-6356,6388-6396`）。この変数の tile ごとの性能測定値は Strata の説明資料で確認できなかった。

## 根拠

- 候補名の製品コードでの読み取り、値変換と tile 選択: `src/kernels/cuda/iq_kernels.cu:6344-6373`; helper: `src/kernels/cuda/i8_expert.cuh:1208-1211`。
- tile から kernel launch への反映: `src/kernels/cuda/i8_expert.cuh:1123-1157,1199-1205`。
- 対応 layout と経路選択条件: `src/kernels/cuda/iq_kernels.cu:6285-6289,6330-6334`; `include/strata/kernels/i8_expert_rule.hpp:28-56`; `src/prefill/prefill.cpp:5966-6010`。
- Qwen3.6 engine の int8 呼び出し経路: `src/qwen35/q36_engine.cu:1412-1428,2173-2183`。
- CUDA/HIP ビルドへの実装組み込み: `cmake/strata_gpu_engine.cmake:8-10,98`; backend 設定: `CMakeLists.txt:91-104`。
