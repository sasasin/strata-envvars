# `DF2B_ITERS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この変数は DFlash2 のベンチマークが計測サンプルを何回取るかを指定します。通常の Strata CLI やサーバーの生成設定ではなく、Metal の `df2_bench` と SYCL の `dflash2_bench` にある開発・診断用ベンチマークの設定です。Metal では各段階・round の計測反復数、SYCL では直接 launch と有効な graph replay の計測反復数になります。モデルの生成動作やカーネルの計算内容を切り替える値ではありません。

## 値と判定

どちらの実装も `atoi` で整数へ変換し、変換後の値を下限・上限に clamp せず、正の値かどうかも検査しません。数値の後ろの文字は検査されないため、たとえば `12tail` は 12、`tail` は 0 になります。`atoi` の通常の変換規則により、先頭空白と符号も許されます。

| 実行経路 | 未設定 | 空文字 | 設定値 |
| --- | --- | --- | --- |
| Metal `df2_bench` | 200 | 0（設定済みポインターに対して `atoi("")`） | `atoi` の結果。例: `12` → 12、`-2` → -2、数値で始まらない文字列 → 0 |
| SYCL `dflash2_bench bench` | 100 | 100（helper が空文字を既定値扱い） | 空でない場合は `atoi` の結果。例: `12` → 12、`-2` → -2、数値で始まらない文字列 → 0 |

正の値 `n` のとき Metal は各 `time_it` 計測で n 回、SYCL は直接 launch と graph replay ごとに n 回の標本を集めます（graph が有効な場合）。0 または負値を防ぐ検証はありません。その場合は標本ベクターが空になり、中央値・パーセンタイルを求める処理が空配列を添字参照します。正常な計測結果や安全な終了は保証されず、未定義動作になります。Metal の集計は `metal/tests/df2_bench.cpp:37-38,426-439`、SYCL は `sycl/src/kernels/dflash2_bench.cpp:54-55,526-539` にあります。

## 有効になる条件

- Metal では `metal/tests/df2_bench.cpp` のベンチマーク実行が対象です。`DF2B_ONLY=ctx|block|head` を指定すると該当段階だけを測りますが、反復数は同じように適用されます。`DF2B_ONLY=soak` は反復回数ではなく `DF2B_SECS` による時間計測へ進むため、`DF2B_ITERS` は測定反復に使われません（`metal/tests/df2_bench.cpp:419-454`）。
- SYCL では既定の `bench` モード（または未知のモード名からの fallback）が `run_bench()` を呼ぶ場合に適用されます。`test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` は別の関数に進み、この変数を読みません（`sycl/src/kernels/dflash2_bench.cpp:894-901`）。
- SYCL で `DF2B_GRAPH` が 0 になると graph replay の計測は省略されますが、直接 launch の計測には引き続き適用されます。`DF2B_PROFILE` による per-kernel profile は固定 20 回の別計測です（`sycl/src/kernels/dflash2_bench.cpp:525-600`）。
- 同じ名前でも Metal と SYCL で未設定・空文字の既定値が異なります。CLI 引数や他の環境変数が `DF2B_ITERS` の値を上書きする経路はありません。

## 実行時の詳細

両ベンチマークとも実行中に一度読み、ローカル定数 `ITERS` に保持します。Metal は `main()` で `getenv` を調べ、値が未設定の場合だけ 200 を使います。設定値は `atoi` で整数化され、`time_it()` の `for (i = 0; i < ITERS; ++i)` の反復回数になります。各測定群は同じ回数を使い、標本から GPU 時間と host wall time の中央値・p10・p90を表示します（`metal/tests/df2_bench.cpp:62-79,426-441`）。`DF2B_ITERS` はベンチの実行中に再読込されません。

SYCL は `run_bench()` の冒頭で共通 helper `envi("DF2B_ITERS", 100)` を呼びます。helper は未設定または空文字なら既定値を返し、それ以外は `atoi` します。直接 launch と graph replay はそれぞれ `ITERS + 10` 回ループし、先頭 10 回を warm-up として捨ててから測定ベクターに追加します。結果として正の ITERS なら指定した数の標本になります。標準出力の `config` 行に ITERS が表示され、集計結果は `DIRECT wall ms/round` と、graph 有効時の `GRAPH wall ms/round` として出ます。graph が例外で利用できない場合は `GRAPH unavailable: ...` を出します（`sycl/src/kernels/dflash2_bench.cpp:56-57,486-508,525-572`）。

SYCL の host submit 時間は固定 30 回、profile は固定 20 回であり、`DF2B_ITERS` の対象外です（`sycl/src/kernels/dflash2_bench.cpp:540-600`）。また、この変数が変えるのはベンチマークの標本数だけで、標本の内容や実際の Strata 推論時の反復数ではありません。

## 根拠

- `metal/tests/df2_bench.cpp:1-9` — `df2_bench` の目的と `DF2B_ITERS` の既定値 200。
- `metal/tests/df2_bench.cpp:62-79` — Metal 側の環境読み取りと未設定判定。
- `metal/tests/df2_bench.cpp:37-38,426-441` — 標本ループと集計、出力。
- `metal/tests/df2_bench.cpp:442-454` — soak / ctx / block / head の分岐。
- `sycl/src/kernels/dflash2_bench.cpp:1-9` — SYCL ベンチの説明と既定値 100。
- `sycl/src/kernels/dflash2_bench.cpp:54-57,486-508` — 空文字を既定値扱いする共通 helper と読み取り、設定表示。
- `sycl/src/kernels/dflash2_bench.cpp:525-600` — warm-up 後の直接 launch / graph 標本、graph 条件、固定回数の submit / profile。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — CLI モードと `run_bench()` への経路。

`docs/DETAILS.md` に `DF2B_ITERS` の追加説明は見つかりませんでした。`docs/envvars/000_envvers.md` には候補名がありますが、実際の読み取りは上記2つのベンチマーク実装に限られます。
