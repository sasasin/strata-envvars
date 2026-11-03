# `STRATA_Q6_SHAPE_GRF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の native Q6_K wide matvec で、限定された射影形状に 256-register large-GRF kernel を選ぶ opt-in フラグです。通常の Q6_K wide 経路に対して対象形状だけ `grf_size<256>` を要求します。Battlemage のみが対象で、他 GPU ではこの変数を有効にしても bounded dispatch は起動しません。

## 値と判定

変数名は呼び出し側から共通 helper に文字列で渡され、helper が `std::getenv(name)` で読みます。値を数値として parse せず、設定されていて空でなければ先頭文字だけを判定します。空文字と未設定はいずれも helper の既定値 `false` になります。

| 値 | helper の結果 | 対象 dispatch |
|---|---:|---|
| 未設定 | `false` | 無効 |
| 空文字 | `false` | 無効 |
| `0` または `0` で始まる文字列 | `false` | 無効 |
| `1`、`true`、`false`、空白で始まる文字列など、空でなく先頭が `0` 以外 | `true` | 条件を満たす場合に有効 |

文字列全体の比較、大文字小文字の変換、数値変換、範囲検査はありません。したがって文字列 `false` も helper 上は true です。設定値は `launch_q6k_wide<NCOLS>` の関数テンプレート特殊化ごとに `static const bool` として最初の評価時に保持され、そのプロセス内では後から環境を変えても再評価されません。

## 有効になる条件

この経路が選ばれるには、native Q6_K の呼び出しで packed / planar 専用経路が先に処理を終えず、wide 経路のゲート（`STRATA_MMVQ_WIDE`、column 数、`n_in`、`n_out`）を通る必要があります。さらに `STRATA_MMVQ_A2` が有効、wide kernel の rows-per-warp が 1、column 数が 1 より大きいことが必要です。

対象形状は以下のいずれかです。

- `n_in == 6144`、`n_out == 2560`（column 数は 2 以上）
- `n_in == 2560`、`n_out == 512` または `640`（column 数は 2 以上）
- column 数 3 以上、`n_in == 2560`、`n_out == 6144`
- column 数 4 以上、`n_in == 2560`、`n_out == 10240` または `12288`

上記に加え、対象デバイスが Battlemage で、`STRATA_MMVQ_LARGE_GRF` が未設定でなければなりません。`STRATA_MMVQ_LARGE_GRF` が設定済みなら、その値が `0` であっても bounded dispatch は抑止され、large-GRF の選択は同変数自身の別ロジックに委ねられます。したがってこの変数は通常の large-GRF 強制指定の代替ではありません。

## 実行時の詳細

`native_mmvq()` は GGML type 14 を Q6_K handler に渡します。Q6_K handler は packed / planar 経路を試した後、wide が有効で column 数等の条件を満たす場合に `launch_q6k_wide<NCOLS>()` を呼びます。wide launcher は A2 と `NCOLS > 1` の場合にこの変数を読み、形状・環境・デバイス条件を組み合わせます。

条件が成立すると stderr に一度 `strata: shape-guarded Q6_K large-GRF dispatch enabled` を出し、`grf_size<256>` property 付きで `native_mmvq_q6k_wide_kernel` を起動します。bounded 条件が成立しない場合は別途 `STRATA_MMVQ_LARGE_GRF` の判定に進み、そちらも false なら通常の A2 Q6_K wide kernel を使います。対象変数に起因する警告、エラー、終了経路はありません。

この変数は CLI 引数や設定ファイルから上書きされません。Q6_K wide 自体が無効、または packed / planar 経路など別経路が先に成立する場合は、この変数は実質的に評価・適用されません。

## 根拠

- `sycl/include/strata/sycl_queue.hpp:159-166` — `bm_default_on()` は環境変数を動的な名前で取得し、空でない値の先頭文字が `0` かどうかを判定します。既定値 false ではデバイス世代に関係なく未設定時 off です。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1550-1553` — `STRATA_MMVQ_A2` の既定値と判定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1725-1731` — `STRATA_MMVQ_LARGE_GRF` の別の判定・デバイス既定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1734-1787` — wide launcher、対象形状、Battlemage / 明示 large-GRF との条件、通知ログ、256-GRF と通常 kernel の選択。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3853-3875` — Q6_K packed / planar 経路の先行判定と wide dispatch 条件。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4113-4130` — native matvec の type 14 が Q6_K handler に渡ること。
- `docs/INTEL.md:544-549` — 文書側もこの変数を既定 off の bounded Q6_K large-GRF 制御として掲載し、測定上の理由で opt-in とする旨を記載しています。ここでは測定値を独自に確認していません。
