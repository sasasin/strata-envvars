# `DF2B_CHUNKS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版の DFlash2 ベンチマーク `dflash2_bench ctx` が、プロンプトの context update を何個の 8-row chunk に分けて計測するかを指定します。通常の Strata generate / serve 実行の設定ではなく、独立した診断・ベンチマーク実行ファイル内だけで使われます。

## 値と判定

`envi("DF2B_CHUNKS", 256)` は共通 helper で `std::getenv` し、値が未設定または空文字なら既定値 `256` を返します。それ以外は `std::atoi` で整数に変換します。文字列全体の検証や範囲制限はありません。

| 環境値 | `NCH` の結果 |
|---|---:|
| 未設定、空文字 | 256 |
| 整数文字列（例: `12`, `+12`, `-2`） | `atoi` の変換結果 |
| 数字で始まらない非空文字列（例: `abc`） | 0 |
| 数字の後ろに文字が続く文字列（例: `12x`） | 数字部分の 12 |

先頭の空白も `atoi` の規則で読み飛ばされます。`NCH` が 0 以下でも拒否・clamp されません。範囲外の整数文字列に対する `atoi` の結果は C/C++ の変換契約上保証されないため、ここでは有効値として扱えません。

## 有効になる条件

この値を読むのは `run_ctx()` だけです。`main()` は引数が `ctx` のときに同関数を呼びます。引数省略時は `bench`、未知の引数も最後の分岐により通常ベンチマークへ進むため、その場合 `DF2B_CHUNKS` は読まれません。実行ファイルは SYCL の GPU queue を作成してからモードを選ぶので、`ctx` を指定しても GPU が必要です。

`sycl/CMakeLists.txt` は `dflash2_bench` を追加する独立ターゲットとして定義しています。この変数は通常のエンジンやサーバーモード、CUDA/HIP backend、モデル設定には接続されていません。

## 実行時の詳細

値は `run_ctx()` の呼び出しごとに一度読み取られ、関数内の `NCH` としてその実行中に使われます。static cache はありません。`NCH` は次の計測規模と表示値に使われます。

- GPU context update の形状・固定値は Q4_0 pack の形状を使ったベンチマーク用 Drafter であり、実モデルの prompt を処理するものではありません（`dflash2_bench.cpp:825-827`）。
- 最初に `NCH` 個の metadata staging buffer を作ります（同:830-831）。その後、4 回の warm-up は `NCH` に関係なく実行します（同:832-833）。
- 計測 (a)〜(d) はそれぞれ `NCH` 回の loop で 8-row update の staging、kernel、コピーや wait の組合せを測ります。(a) は chunk ごとに wait し、(c) は kernels を連続投入して最後に wait、(d) は chunk ごとの metadata を事前確保して最後に wait します（同:836-862）。
- 各計測の表示は `NCH` あたりの時間と `NCH * 8` rows を出します。(e) の kernel marker 計測は `NCH` ではなく常に 1 chunk を測り、(f) は `NCH` を使って規模を表示します（同:834-835,864-888）。

値が 0 または負の場合、`k < NCH` の loop は実行されず、metadata staging vector も空になります。(a)〜(d) の `per` は 0 で割るため、時間表示は `inf` / `nan` などの非有限値になり得ます。負値では行数表示も負になります。その後の固定 1-chunk 計測 (e) は引き続き実行されます。正の大きな値には上限がなく、metadata staging の確保や反復量が増えます。

この変数について Strata 独自の警告や無効値 fallback はありません。メモリ確保や SYCL 処理が失敗した場合の診断は、その処理経路・ランタイムによります。値の読み取り自体は startup `main()` ではなく `ctx` モードの `run_ctx()` 内で行われます。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56-57` — `envi` は未設定・空文字に既定値を返し、それ以外を `std::atoi` に渡す。
- `sycl/src/kernels/dflash2_bench.cpp:824-835` — `NCH` の読み取り、8-row 単位、staging 確保、warm-up、表示計算。
- `sycl/src/kernels/dflash2_bench.cpp:836-888` — `NCH` を使う計測 loop と固定 1-chunk の marker 計測。
- `sycl/src/kernels/dflash2_bench.cpp:894-902` — SYCL queue 作成後、引数 `ctx` の場合だけ `run_ctx()` を呼ぶ。
- `sycl/CMakeLists.txt:437-438` — `dflash2_bench` 独立ターゲットの定義。
