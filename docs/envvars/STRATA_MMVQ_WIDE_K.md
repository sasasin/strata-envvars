# `STRATA_MMVQ_WIDE_K`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の native MMVQ で、Q4_K・Q5_K・IQ4_XS の wide kernel を試すかどうかを制御する。未設定なら wide kernel を有効にし、値を `atoi` で整数化した結果が 0 なら無効にする。wide kernel が使われるときは `ncols` ごとの `launch_wide` を起動し、無効または入力条件外なら後続の wave / multi-column / 1-column 実装へ進む。対象は Strata の `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` であり、CUDA/HIP の実装にはこの環境変数の読取箇所はない（同名の全参照検索結果は当該 SYCL ファイルだけ）。`native_mmvq` は GGML type 12、13、23 をそれぞれ Q4_K、Q5_K、IQ4_XS の実装へ振り分ける。

この変数は演算結果を直接変更する値ではなく、実装経路の選択値である。異なる kernel の計算順序や結果の同一性について、この環境変数に関する測定資料は確認できなかった。

## 値と判定

`wide_k()` 内の関数ローカル `static const bool` を初期化するとき、`std::getenv` の結果が null（未設定）なら `true`、設定済みなら `std::atoi` の結果が 0 以外の場合だけ `true` になる。文字列全体の検証やエラー処理はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL native MMVQ の wide 判定 | 有効 | `1`、`2`、`-1`、`1tail`（`atoi` が非 0） | 空文字、`0`、`0tail`、`true`、`false`、先頭が数値でない文字列（`atoi` が 0） |

`atoi` は先頭の空白と符号付き十進整数を読み、整数の後ろに続く文字列を検証しない。そのため `  +2tail` は有効、`0anything` は無効になる。`true` / `false` は真偽値として解釈されず、どちらも 0 になる。数値変換範囲を超えた文字列について、実装に定義された判定はない。根拠: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2068`。

## 有効になる条件

- この読取コードを含む SYCL backend の実行であること。SYCL CMake は `native_mmvq` を kernel 群に含め、`strata_resolve` の結果を `strata_kernels` に加える（`engine/sycl/CMakeLists.txt:273-286`）。候補名の完全一致検索では、CUDA/HIP ソースや CLI / Python サーバーの読取は見つからなかった。
- 呼び出しが GGML type 12（Q4_K）、13（Q5_K）、23（IQ4_XS）の native MMVQ に到達すること（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4222`）。
- `wide_k()` が true であり、`ncols` が 1〜8、`n_in` が 256 の倍数であること（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2071-2083`）。各形式の公開関数は先に形状・ポインター・stream を検証し、範囲外なら例外にする（同ファイル `3457-3465`, `3692-3700`, `3859-3867`）。
- IQ4_XS は関数冒頭で B60 の cache / packed-weight 経路や条件付き専用 kernel を試す。該当条件で早期 return すれば `try_wide` の判定自体に到達しない（同ファイル `3701-3734`）。その後も IQ4 の pair-reuse、ESIMD、XMX 経路が条件を満たして早期 return する場合は wide 判定より優先される（同ファイル `3736-3776`）。`STRATA_SYCL_IQ4_LOOKUP` は unset または `atoi` の結果が非 0 のとき有効で、Battlemage かつ `n_in` が 2560 または 6144 の場合に lookup 版 wide kernel を先に試す。それが不成立なら IQ4_XS wide kernel を試す（同ファイル `3744-3747`, `3772-3779`）。
- wide kernel 内の実装選択には別条件がある。`STRATA_MMVQ_WIDE_K_RPW` は行数パラメーターを渡し、未設定かつ shape / Battlemage 条件を満たす場合は `STRATA_MMVQ_SHAPE_RPW` の既定 ON 判定が一部 Q4_K/Q5_K 形状で RPW=2 を選ぶ。2 列以上では `mmvq_large_grf` の判定により GRF 256 variant になる場合もある（同ファイル `1961-2004`）。これらは `STRATA_MMVQ_WIDE_K` の有効・無効判定そのものを上書きしない。

## 実行時の詳細

値はプロセス起動時に必ず読むのではなく、対象関数 `wide_k()` が初めて呼ばれたときに静的初期化され、以後そのプロセス内で cache される。実行中に環境変数を変更しても判定は更新されない。対象の最初の呼出しが IQ4_XS の専用経路で早期 return した場合は読み取りは遅れ、いずれかの Q4_K/Q5_K/IQ4_XS 呼出しが `try_wide` に到達した時点で初期化される（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2072`, `3701-3779`, `3867`）。

判定が true で `try_wide` が入力条件を満たすと、列数 1〜8 に対応する `launch_wide` を呼び出し、成功扱いで呼出元が `launch_check()` 後に return する。wide 判定が false のとき `try_wide` は false を返し、Q4_K/Q5_K は必要に応じて wave MMVQ、複数列なら multi kernel、1 列なら形式別 kernel へ進む。IQ4_XS も専用経路を通らなければ同様に wave / multi / 1 列 kernel へ進む（同ファイル `2071-2083`, `3465-3508`, `3772-3838`, `3867-3916`）。`STRATA_HIP_GFX906` が定義された build では、wide 判定後の wave 分岐が有効になり得る（同ファイル `2337-2405`）。

無効値によるログや専用の終了・例外経路はない。無効値は通常の fallback 選択として扱われる。入力形状などの例外と kernel 起動後の SYCL 例外は別の経路であり、この環境変数の値検証がそれらを追加することはない（同ファイル `2297-2334`, `3460-3470`, `3861-3872`）。

## 根拠

- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2083` — 値の読取、cache、wide kernel の適用条件と列数別 dispatch。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3457-3476` — Q5_K の検証、wide 判定、fallback。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3779` — IQ4_XS の先行経路と wide 判定。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3859-3878` — Q4_K の検証、wide 判定、fallback。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4222` — GGML type と形式別関数の対応。
- `engine/sycl/CMakeLists.txt:273-286` — SYCL engine の kernel 群と `strata_kernels` への登録。
