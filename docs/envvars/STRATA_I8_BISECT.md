# `STRATA_I8_BISECT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA/HIP の native int8 expert kernel に、調査用の早期 return を入れる変数。通常の gate/up・SwiGLU・activation 量子化・down 計算を途中で止め、fault hunt で失敗箇所を切り分けるためのフックである。通常の CLI 設定ではなく、値が 1〜7 のとき出力計算を意図的に不完全にする。読み取りは `native_expert_i8`、停止点は `i8_kernel`（`src/kernels/cuda/iq_kernels.cu:6372-6373`、`src/kernels/cuda/i8_expert.cuh:543-544`）。

この kernel の呼び出し経路は Qwen3.6 engine の prompt expert route の一つである。decode や他 backend 全体を切り替える設定ではない（`src/qwen35/q36_engine.cu:2131-2138,2173-2183`）。

## 値と判定

`i8_env_int` は `std::getenv(name)` を呼び、未設定または空文字なら既定値 `0`、それ以外なら `std::atoi` の結果を使う。`native_expert_i8` ごとに値を読み、`I8Args` に格納して kernel launch へ渡す。`atoi` の変換結果を 1〜7 と完全一致で比較するため、文字列全体の妥当性検査、範囲検査、clamp はない。先頭に数値変換できる部分があれば後続文字は無視される。数値変換できない文字列は `atoi` の結果 0 となり通常計算へ進む。数値として大きすぎる文字列の扱いはコードで検査されない（`src/kernels/cuda/i8_expert.cuh:1208-1211`, `src/kernels/cuda/iq_kernels.cu:6372-6373`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| tile code 2〜4 の `i8_kernel` | `0`（通常計算） | `1`〜`7`。例: `1`, `7`, `2tail`（`atoi` が 2） | 空文字、`0`, `0anything`, `true`, `-1`, `8`。いずれも指定停止点に一致せず通常計算 |
| tile code 8 の `i8b_kernel` | `0` 相当 | なし。この kernel は受け取った `bisect` を参照しない | どの値でも bisect 停止は発生しない |

空白や符号の先頭部分は `atoi` の変換規則に従い、たとえば `  +3tail` は 3 になる。`true` のように数値変換が始まらない文字列は 0 になる。文字列全体の一致や大文字小文字の判定はしない。CLI 引数による上書きはない。

## 有効になる条件

- CUDA/HIP の `native_expert_i8` が呼ばれること。Qwen3.6 engine では prompt chunk の `T > kGemmT` かつ `use_pf` の経路に入り、その layer が int8 route である必要がある（`src/qwen35/q36_engine.cu:2131-2138,2173-2183`）。
- route 選択では fused route が優先される。`STRATA_EXPERT_I8=1` は対応する layer を MMQ より先に int8 にし、MMQ がない build では同変数 unset も有効値 1 として扱われる。MMQ が使える場合は通常 MMQ が先で、対応する layer が MMQ に取られないとき int8 が候補になる。`STRATA_EXPERT_I8=0` は int8 route を止める（`src/qwen35/q36_engine.cu:1396-1427`, `include/strata/kernels/q36_prompt_route.hpp:21-29`）。
- layer の形式・寸法・shared memory が `native_expert_i8_supported` を満たすこと（`src/kernels/cuda/iq_kernels.cu:6330-6334`）。全 layer の route が prompt path の条件を満たさないと engine は int8 を含む prompt route を無効にする（`src/qwen35/q36_engine.cu:1433-1440`）。
- chunk の routed entries が少なく `STRATA_I8_FEWROWS` による few-rows route に入る場合は `native_expert_grouped` が呼ばれ、対象変数は読まれない（`src/qwen35/q36_engine.cu:2177-2183`; route 判定は `include/strata/kernels/q36_prompt_route.hpp:36-38`）。
- tile code 8 が選ばれた場合、値 1〜7 でも早期 return は行われない。tile 8 は entry 数・寸法・型で自動選択される場合があり、`STRATA_I8_TM` でも要求できるが、shared memory 制約で tile 4 以下へ落ちることがある（`src/kernels/cuda/iq_kernels.cu:6363-6370`）。

## 実行時の詳細

`native_expert_i8` は scratch と tile table を準備した後、`STRATA_I8_BISECT` を読み `I8Args.bisect` に格納する。値は gate/up と down の両 launch に渡される。関数内 `static` cache や起動時 cache はなく、関数呼び出しごとに読み直すため、プロセス内で環境を変更した場合は次の呼び出しから反映される。ひとつの呼び出しでは値を両方の launch に渡す（`src/kernels/cuda/iq_kernels.cu:6344-6346,6372-6396`; `src/kernels/cuda/i8_expert.cuh:1097-1106,1132-1157`）。

tile code 2〜4 の `i8_kernel` では値ごとに次の位置で block 全体が return する。停止した kernel は通常の出力を最後まで計算せず、後続 gate/up または down 側も同じ値で早期 return する。値 4 と 5 は該当条件のとき `out[0] = 0.0f` を書いてから return する（`src/kernels/cuda/i8_expert.cuh:577-578,604-607,670-678`）。

| 値 | return 位置 |
| --- | --- |
| 1 | group/tile の位置決め後、型・寸法に応じた処理の前 |
| 2 | 共有メモリ用の定数テーブル準備後 |
| 3 | tile の source entry を共有メモリへ置き、同期した後 |
| 4 | 最初の weight block 読み込み後。`wraw[0] == 0x12345678u` なら `out[0]` を 0 にする |
| 5 | 最初の weight block と activation block の読み込み後。`wraw[0] + ar[0] == 0x12345678u` なら `out[0]` を 0 にする |
| 6 | 最初の weight block を変換して共有メモリへ置いた後 |
| 7 | 最初の activation block も共有メモリへ置き、同期した後 |

0 および 1〜7 以外は `i8_kernel` の停止条件に一致せず通常計算へ進む。tile code 8 の `i8b_kernel` には停止条件がない（`src/kernels/cuda/i8_expert.cuh:894-896,926-1094`）。

## ログと測定値

この変数自体の値や bisect 停止を知らせるログはない。`native_expert_i8` は gate/up と down の launch 後に通常の CUDA/HIP error check を行い、error があれば stderr に `native_expert_i8/gu: <error string>` または `native_expert_i8/down: <error string>` の形で出して終了コード 1 で終了する。早期 return 自体はエラーを報告しない（`src/kernels/cuda/iq_kernels.cu:42-45,6388-6396`）。意図的に未計算の出力が後段へ渡るため、生成結果の誤りや後続処理の失敗はあり得るが、専用の結果判定・終了処理はこの変数の実装にはない。

## 根拠

- `src/kernels/cuda/i8_expert.cuh:543-578,604-678` — tile 2〜4 kernel の bisect checkpoints。
- `src/kernels/cuda/i8_expert.cuh:894-896,926-1094` — tile 8 kernel に checkpoint がないこと。
- `src/kernels/cuda/i8_expert.cuh:1097-1106,1123-1157,1208-1211` — 値の引き渡し、kernel launch、共通 parser。
- `src/kernels/cuda/iq_kernels.cu:6330-6334,6344-6396` — 対応条件、読み取り、両 kernel の呼び出し。
- `src/qwen35/q36_engine.cu:1396-1442,2131-2183` — Qwen3.6 の route と prompt chunk からの呼び出し条件。
- `include/strata/kernels/q36_prompt_route.hpp:21-38` — route 優先順位と few-rows 判定。
