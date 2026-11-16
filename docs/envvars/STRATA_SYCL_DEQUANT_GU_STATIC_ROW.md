# `STRATA_SYCL_DEQUANT_GU_STATIC_ROW`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

SYCL の IQ gate/up FP16 dequantization が tiled 経路を使うとき、`n_embd == 2560` かつ型 ID が 16、22、29 なら、1 行を 10 個の 256 値ブロックとしてコンパイル時に固定した kernel specialization を選ぶためのフラグです。値の展開式や出力レイアウトを変える設定ではなく、行幅・型の dispatch を特殊化します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6591-6609`、`sycl/include/strata/kernels/iq_dequant.hpp:11-19`）。

これは SYCL port 専用コードで読み取られます。通常の CUDA 実装ではこの名前の読み取りは確認できません。SYCL の prefill から `iq_dequant_gu_f16` が呼ばれる経路に適用されます（`sycl/CMakeLists.txt:1-7,240-253`、`sycl/src/prefill/prefill.cpp:4592-4600,4686-4717`）。

## 値と判定

`env_on` は `std::getenv` の結果が未設定でなく、かつ先頭文字が NUL と `'0'` のどちらでもない場合に true を返します。文字列全体の parse や真偽語の比較はしません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL tiled dequant 経路で本変数を評価 | false | `1`、`true`、` 0`（先頭が空白） | 空文字、`0`、`01`、`0anything` |

大文字小文字、後続文字、数値としての妥当性は検査しません。したがって `false` も先頭が `'f'` のため true です。明示的な空文字は設定済みですが false になります。変数が true でも、固定 dispatch の条件を満たさなければこのフラグによる specialization は選ばれません。

## 有効になる条件

- SYCL build の `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の実装を通ること。CUDA 側の同名動作は確認できません（`sycl/CMakeLists.txt:1-7,240-253`）。
- 呼び出しが IQ gate/up FP16 dequantization であること。入口は `n_embd % 256 == 0`、IQ 型、`tail == nullptr` を要求し、満たさない場合は stderr に `iq_dequant_gu_f16: type %d / %lld` を出して `exit(1)` します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6644`）。
- `STRATA_SYCL_DEQUANT_GU_BOUNDED` が有効で、bounded 実装がその入力を処理した場合はそちらから戻るため、本変数には到達しません。bounded 経路が false を返す場合は後続判定に進みます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558,6643-6645`）。
- `STRATA_SYCL_DEQUANT_GU_SG` の判定結果が 2、4、8 のいずれかで tiled 経路に入ること。未設定時は 1。設定時は `atoi` で変換し、結果が 2/4/8 以外なら 1 に戻すため、1・空文字・変換不能値では本変数を読みません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617,6645-6649`）。
- tiled 経路で `n_embd == 2560`、かつ型 ID が 16、22、29 のいずれかであること。この条件で `launch_dequant_gu_tiled<Subgroups, Type, 10>` を使います。幅が異なる場合または他の型では `static_row` では特殊化されず、`STRATA_SYCL_DEQUANT_GU_STATIC_TYPE` が有効なら型のみ固定した経路、それも該当しなければ一般 dispatch へ進みます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6591-6609`）。

## 実行時の詳細

本変数の値は `iq_dequant_gu_f16` 内の関数ローカル `static const bool` です。関数呼び出しのたびに無条件で読むのではなく、bounded 経路から戻らず、かつ subgroup 数が 1 以外で tiled 経路に進んだ最初の呼び出しで初期化されます。その後はプロセス内でキャッシュされ、環境変数を実行中に変更しても反映されません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6643-6649`）。

値が有効でも、固定行 dispatch が成立しない幅・型では挙動を変えません。成立すると、1 行あたりのブロック数をテンプレート引数 10 として kernel を起動します。通常の変数値・既定値の選択に CLI 引数や設定ファイルが関わる処理は、この読み取り経路では確認できません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6562-6609`）。

## ログと測定値

このフラグの読み取りや有効化だけを知らせるログはありません。入口の入力条件不正時には上記の stderr と `exit(1)` があり、tiled 関数は shape/type 不正時に `iq_dequant_gu_f16_tiled: invalid type or shape` を出して終了し、完了時に `check("iq_dequant_gu_f16_tiled")` を呼びます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6621-6635,6638-6649`）。この変数について条件付き測定値は確認できません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692` — env 判定規則。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558,6591-6617,6621-6675` — bounded/tiled dispatch、値の読み取り、cache、エラー経路。
- `sycl/include/strata/kernels/iq_dequant.hpp:11-19` — SYCL 専用 API と static row の説明。
- `sycl/src/prefill/prefill.cpp:4592-4600,4686-4717` — prefill からの呼び出し経路。
- `sycl/CMakeLists.txt:1-7,240-253` — SYCL build と kernel source の登録。
