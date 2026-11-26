# `STRATA_Q6P_SELFTEST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Q6_K head を packed 形式に登録した直後、GGUF 配置カーネルと packed カーネルを合成入力で比較し、実行時間を測る開発・診断用スイッチです。`1` 相当では 1～4 列の出力一致確認と 1/2/4 列の paired timing を行い、`2` 相当ではそれに加えて packed カーネルの grid sweep を行います。通常の生成結果を設定する変数ではなく、この確認・測定処理を head のロード時に追加します（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3182-3187,3203-3235`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3251-3260,3282-3324`）。

## 値と判定

CUDA 実装と SYCL 実装はどちらも `std::getenv` の戻り値が非 null で、先頭 byte が文字 `'1'` または `'2'` なら有効とします。文字列全体の比較や数値変換はしません。したがって空文字は無効、`1anything` と `2anything` は有効、`10` も `'1'` で始まるため有効です。`0`、`0anything`、`true`、` 1`、`A` は無効です。大小文字の変換や空白除去もありません（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3184-3185`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3253-3254`）。

| 実装 | 未設定 | 自己診断を実行する値 | 実行しない値 |
|---|---|---|---|
| CUDA / SYCL | 無効 | 先頭文字が `1` または `2`（例: `1`, `2`, `10`, `2debug`） | 空文字、`0`, `0anything`, `true`, ` 1` など |

## 有効になる条件

- 対象コードが CUDA 実装 (`engine/src/kernels/cuda/native_mmvq.cu`) または SYCL 実装 (`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp`) としてビルドされ、その実装の native head 経路が使われること。別 backend の実装はこの変数を読んでいません。
- 別変数 `STRATA_Q6_PACKED` が実装側で有効であり、Q6_K 型 (`type_ == 14`) の出力 head または MTP draft head の packed 化が呼び出されること。`STRATA_Q6_PACKED` は値全体が文字列 `1` の場合だけ有効です（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3145-3150`、`engine/src/core/native_head.cpp:261-264,988-995`。SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`、`engine/sycl/src/core/native_head.cpp:92-96`、`engine/sycl/src/core/mtp.cpp:857,866-868`）。
- packed 化対象が形状条件を満たすこと: 重みポインターが非 null、`n_in > 0`、`n_in` が 256 の倍数、`n_in / 256 >= WARPS * WARP / 32`、`n_out >= 2048`。条件外では pack 関数が自己診断より前に `false` を返します（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3153-3155`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3191-3193`）。
- 設定値は CLI 引数や設定ファイルから選ばれるものではなく、コード上でそれらとの優先順位はありません。`STRATA_Q6_PACKED` が無効、Q6_K head がない、または pack が成功しなければ、この変数の分岐には到達しません。

## 実行時の詳細

自己診断用 `getenv` は `native_q6_k_pack` が packed 領域を registry に登録し、その成功ログを出した後に評価されます。関数を呼ぶたびに値を読み、`static` cache はありません。通常はモデルの出力 head または MTP draft head を準備して packed 登録するロード経路で実行されます。よってプロセス開始時に固定されるとは限らず、後続の pack 呼び出しより前に環境値が変われば、その呼び出しでの判定に反映されます（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3177-3185`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3242-3254`）。

自己診断は seed `12345` の線形更新で Q8_1 入力を作り、各列数 1～4 について GGUF 配置と packed 配置の結果を `memcmp` で比較します。続けて列数 1、2、4 ごとに各方式を 5 回ずつ実行する測定を 11 組行い、中央値と範囲を出します（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3187-3235`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3255-3324`）。

値の先頭が `2` の場合はさらに grid 数 `160, 320, 640, 1280, 2560, 5120, 20480` をそれぞれ指定し、列数 1、2、4 ごとに 5 回実行を 7 標本測ります。測定中だけ `g_q6p_grid_override` を設定し、終了後 `0` に戻します（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3236-3255`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3325-3349`）。grid sweep を指定しない場合の packed kernel grid は別変数 `STRATA_Q6P_GRID` を `q6p_grid()` 初回呼出し時に読み、正値ならその数、未設定または `atoi` 後に正値でなければ 640 です。したがって通常の paired timing はこの別変数の影響を受けますが、`2` の sweep は固定 grid を override します（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:2845-2852,2933-2941`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2709-2716,2830-2873`）。

出力一致しない場合は `DIFFER` を記録して packed registry を解除し、pack 関数は `false` を返します。呼び出し元は戻り値を無視しているため、この分岐自体はモデルロードを失敗扱いにしません（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3259-3261`、`engine/src/core/native_head.cpp:262-264`。SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3356-3358`、`engine/sycl/src/core/native_head.cpp:93-96`）。SYCL 実装で `sycl::exception` が投げられた場合は catch 節が例外文と位置を stderr に出し `exit(1)` します（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3360-3364`）。CUDA 実装の自己診断内の CUDA API 呼び出しには個々の戻り値を検査する処理がなく、失敗時の専用ログや復旧分岐は確認できません。

## ログと測定値

有効条件を満たして packed 登録に成功すると、両実装とも stderr に `strata: STRATA_Q6_PACKED=1 packed the ...` を出した後、診断結果を出します。測定ログの文言は `strata: Q6_K packed self-test %s ncols %d: GGUF ...`、比較ログは `strata: Q6_K packed self-test %s: outputs BITWISE EQUAL (1-4 columns)` または `... DIFFER ...` です。値 `2` の場合は `strata: Q6_K packed grid sweep %s grid %d ncols %d: ...` も出力します（CUDA: `engine/src/kernels/cuda/native_mmvq.cu:3182,3231-3235,3250-3251`、SYCL: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3251,3320-3324,3345-3346`）。

ソースにはこの自己診断の実行結果を示す固定性能値はありません。上記ログ値は実行環境で生成される測定結果であり、ここでは新たな性能・正確性の実測はしていません。

## 根拠

- 環境変数の全参照と判定: `engine/src/kernels/cuda/native_mmvq.cu:3184-3185`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3253-3254`。他の出現はコメントと設定レジストリ (`engine/include/strata/kernels/native_mmvq.hpp:134`、`engine/sycl/include/strata/kernels/native_mmvq.hpp:113`、`terminal/data/settings-register.json:39594`) で、追加の読み取り箇所ではありません。
- pack の前提と診断の登録位置: `engine/src/kernels/cuda/native_mmvq.cu:3153-3185`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3191-3254`。
- head / MTP 呼び出し条件: `engine/src/core/native_head.cpp:261-264,988-995`、`engine/src/core/mtp.cpp:988-995`、`engine/sycl/src/core/native_head.cpp:92-96`、`engine/sycl/src/core/mtp.cpp:857,866-868`。
- 比較、測定、追加 sweep、結果の扱い: `engine/src/kernels/cuda/native_mmvq.cu:3187-3261`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3255-3364`。
