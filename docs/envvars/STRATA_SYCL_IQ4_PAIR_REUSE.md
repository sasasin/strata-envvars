# `STRATA_SYCL_IQ4_PAIR_REUSE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の IQ4_XS MMVQ で、条件を満たした Battlemage 向け呼び出しを `IQ4PairAllT` カーネルへ振り分けるかを制御する。このカーネルは IQ4_XS 重みと Q8_1 活性値を読み、複数 token 列の積を計算して出力 `y` に書く。対象変数はカーネル選択だけを制御し、値を読むだけの診断スイッチではない。実装は `native_iq4_xs_mmvq` 内にある（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3699,3736-3756,4332-4405`）。

この設定だけでは全 IQ4_XS 呼び出しに適用されない。Battlemage、形状、ポインター整列などの条件を満たす呼び出しに限られ、先行する B60 専用経路が選ばれた場合も到達しない（同 `3701-3735,3748-3756`）。

## 値と判定

`std::getenv` の戻り値を関数内 `static const bool` の初期化 lambda で一度読み、未設定なら `true`、設定済みなら文字列の先頭 byte が `'1'` の場合だけ `true` にする。空文字は設定済みで先頭 byte が終端文字なので `false`。文字列全体の比較、数値変換、空白除去、大文字小文字変換はしない。したがって `1`、`10`、`1anything` は有効、`0`、`true`、`TRUE`、空白で始まる値、空文字は無効（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3736-3739`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `native_iq4_xs_mmvq` がこの判定箇所まで到達 | 有効（`true`） | 先頭文字が `1`。例: `1`, `10`, `1anything` | 先頭文字が `1` 以外。例: `0`, `true`, `TRUE`, ` 1`, 空文字 |
| 先行分岐で関数が戻る | 判定されない | 判定されない | 判定されない |

## 有効になる条件

値が有効でも、次の条件がすべて必要。

- SYCL 実装の IQ4_XS MMVQ 経路を実行すること。汎用 `native_mmvq` は GGML type `23` を `native_iq4_xs_mmvq` に渡す（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217`）。
- GPU 世代が `IntelGpuGen::Battlemage` であること。`ncols` は 1〜4、`n_in` は 2560 または 6144（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3748-3752`）。
- 形状 `ncols==1 && n_in==2560 && n_out==640` ではないこと（同 `3750-3752`）。
- `weights` と `x_q8_1` のアドレスがどちらも 64 byte 境界に整列していること（同 `3750-3752`）。
- 先に評価される B60 分岐が return していないこと。IQ4 SSM/head のキャッシュ分岐、`STRATA_PRIVATE_IQ4_INT4_DPAS` と packed weights による分岐、および main actor の packed dense 分岐は pair-reuse 判定より前にある（同 `3701-3735`）。これらの分岐で使われる状態・変数には `STRATA_PRIVATE_IQ4_SSM_SOA`、`STRATA_PRIVATE_IQ4_HEAD_SOA`、`STRATA_PRIVATE_IQ4_INT4_DPAS`、`STRATA_PRIVATE_B60_NEXT_POOL`、`STRATA_PRIVATE_BMG_SINGLE_ACTOR` がある（同 `3683,3701-3735`）。

さらに `STRATA_SYCL_IQ4_Q8_SPLIT` もこの位置で一度読み、同じ先頭文字規則（未設定または先頭が `1` なら true）で判定する。対象環境変数と Q8 split の両方が有効で、形状が `(n_in,n_out,ncols)=(2560,10240,4)`, `(6144,2560,4)`, `(2560,106299,1)` のいずれかなら、pair-reuse カーネルでなく `launch_iq4_q8_split` に進む。それ以外の条件を満たす形状では `launch_iq4_pair_reuse` に進む（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3740-3756,4635-4639`）。対象環境変数を無効にすると、この分岐を通らず、後続の ESIMD、XMX、wide lookup、汎用 MMVQ などの判定へ進む。したがって「無効」は後続の別カーネルも含め IQ4 最適化全体を無効化する意味ではない（同 `3758-3780`）。

## 実行時の詳細

読み取りは `native_iq4_xs_mmvq` が B60 専用の先行分岐を通過して `pair_reuse` 宣言まで初めて到達した時に行われる。`static const` のため初期値はプロセス内で保持され、後から環境を変更しても再評価されない。先行分岐だけが呼ばれていた場合は、そこではまだこの変数を読み取らない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3739`）。

pair-reuse 分岐では `n_in==2560` の場合 `KB=10`、`n_in==6144` の場合 `KB=24` のテンプレートを選び、`ncols` に応じた `IQ4PairAllT<NT,KB>` を投入する。カーネルは各出力行の有効範囲を扱い、2 系列の積和を蓄積して加算・縮約し、`y` に scatter する。起動後は `launch_check()` を呼ぶ。分岐に入る前の `native_iq4_xs_mmvq` では形状・`n_out`・ポインター・stream を検証し、`n_out<=0` は `native MMVQ requires n_out > 0` の `std::invalid_argument` になる（同 `3692-3700,4332-4405,4419-4426`）。

## ログと測定値

この環境変数の値や選択結果を表示するログは、該当する読み取り・分岐・カーネル起動コードにはない。無効値に対する警告や fallback ログもない。呼び出し結果は `y` への計算結果であり、起動後に `launch_check()` が実行される（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3736-3756,4419-4426`）。

`docs/DETAILS.md` にはこの環境変数に関する性能測定値や説明は見当たらない。`docs/SETTINGS.md:369` は値の型を `on / off` と分類するが、受理値の詳細は示していない。実装上は `on` という文字列では無効で、先頭が `1` の値だけが有効である。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3700,3736-3756` — IQ4_XS 関数、環境変数の読み取り、Battlemage・形状・整列判定、Q8 split との分岐。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4332-4405,4419-4426` — `IQ4PairAllT` カーネルと起動時の引数検査・launch check。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217` — native MMVQ から IQ4_XS 実装へのディスパッチ。
- `docs/SETTINGS.md:369` — 候補一覧の分類。挙動の根拠には使用していない。
