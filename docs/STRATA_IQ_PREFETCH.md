# `STRATA_IQ_PREFETCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

CPU native expert の一部 multi-token row kernel で、重みデータの software prefetch 先を現在の block から何 byte 先にするか指定します。値は prefetch 距離であり、単純な on/off ではありません。AVX1・AVX2・AVX-512 の実装があり、どれが実行されるかは CPU ISA、format、token 数、他の `STRATA_NO_IQ*` / `STRATA_IQ_MT_MIN` 条件によります。

## 値と判定

各実装は `std::atoi` で整数に変換し、文字列全体の検証や上限・下限の clamp はしません。後続文字列は無視されます。unset は `2048` byte です。

| 値 | 判定・動作 |
|---|---|
| unset | `2048` byte 先を指定 |
| 正の整数（例: `512`, `2048tail`） | 変換された整数 byte 先を指定。数値後方は無視 |
| `0`、空文字、数値で始まらない文字列 | `0` となり prefetch を行わない |
| 負数 | 負のまま保持され、`pf > 0` 判定を満たさないため prefetch を行わない |

空白や符号を含む文字列も `atoi` の変換規則に従います。大文字小文字の比較はありません。数値範囲外の文字列の結果はコードで別途扱われません。

## 有効になる条件

対象は Strata の CPU native expert row kernels です。native experts が build に含まれ、CPU pool が native expert を処理し、multi-token kernel が選択される必要があります。gate/up は通常 `nt >= STRATA_IQ_MT_MIN` が必要です。ただし `STRATA_IQ_MT_MIN` が unset で `STRATA_IQ3S_MT1` が有効な場合、AVX2-only CPU の IQ3_S gate/up は別の分岐で1 tokenから候補になります。AVX-512、AVX2、AVX1 の利用可否、format 対応、`STRATA_NO_IQ512` / `STRATA_NO_IQ256` / `STRATA_NO_IQ128` によって実装が選ばれます。該当しなければ ggml-cpu の dot 経路となり、この prefetch は使われません。

- AVX-512 の gate/up kernel では IQ2_XXS、IQ2_XS、IQ3_XXS、IQ3_S、IQ2_S が対象です。
- AVX2 の gate/up kernel では上記に IQ4_XS を加えた形式が対象です。IQ4_NL の down rows にも AVX2 kernel があり、`nt >= STRATA_IQ_MT_MIN` かつ `STRATA_NO_IQ4NL` unset の場合に選択されます。
- AVX1 の gate/up kernel は IQ3_XXS、IQ3_S、IQ2_S、down kernel は IQ4_NL と Q2_0 が対象です。gate/up には同じ token 閾値がありますが、down kernel の選択にはありません。

AVX-512/AVX2/AVX1 kernel の利用条件や fallback の詳細は [STRATA_IQ_MT_MIN.md](STRATA_IQ_MT_MIN.md) を参照してください。この変数自身は kernel の format/ISA 選択を変えず、選択された kernel 内の prefetch 距離だけを変えます。

## 実行時の詳細

AVX1 と AVX2 は `prefetch_distance()` の function-local `static` で初回呼び出し時に値を読み、以降その値を再利用します。AVX-512 は translation unit の namespace-scope `const int` 初期化で読み取ります。いずれも読み取り後のプロセス環境の変更は反映されません。

各処理 block `blk` に対し、距離が正なら `blk + 距離` とそこからさらに 64 byte 先に `_MM_HINT_T0` prefetch を発行します。AVX1/AVX2 は helper の `pf <= 0` 判定で無効化され、AVX-512 も `prefetch_ahead > 0` の場合だけ発行します。変数による専用ログ、警告、エラー出力はありません。

`src/kernels/cpu/iq_avx2_parity.cpp` は値を診断表示しますが、それは parity 実行ファイルの表示であり engine の動作ログではありません。`docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。kernel ソースのコメントには特定 CPU の測定メモがありますが、DETAILS に測定条件一式が記載されていないため、ここでは性能値を一般化しません。

## 根拠

- `src/kernels/cpu/iq_avx1.cpp:135-148,239-248,315-328,351-364` — default、`atoi`、無効化判定、AVX1 row kernels の prefetch。
- `src/kernels/cpu/iq_avx2.cpp:177-195,239-248,369-374` — default、`atoi`、AVX2 row loop と prefetch helper。
- `src/kernels/cpu/iq_avx2.cpp:503-518` — IQ4_NL down kernel の入口。
- `src/kernels/cpu/iq_avx512.cpp:31-39,155-168,245-259` — namespace-scope での読み取り、block ごとの prefetch、kernel 入口。
- `src/kernels/cpu/native_expert.cpp:134-185,199-223` — gate/up と down kernel の選択条件および fallback。
- `src/kernels/cpu/pool.cpp:635-663` — CPU pool から native gate/up/down row kernel を呼ぶ箇所。
- `src/kernels/cpu/iq_avx1.cpp:396-430`, `src/kernels/cpu/native_expert.cpp:37-43`, `src/kernels/cpu/iq_avx2.cpp:465-518`, `src/kernels/cpu/iq_avx512.cpp:245-259` — format 対応と各 backend の kernel 入口。
- `src/kernels/cpu/iq_avx2_parity.cpp:528-534` — parity ツールによる値の表示。
- `CMakeLists.txt:1265-1296` — native CPU kernel sources の登録と ISA 別 compile options。
- `docs/DETAILS.md` — `STRATA_IQ_PREFETCH` の説明はなし（同ファイル内検索）。
