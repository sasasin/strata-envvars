# `STRATA_SYCL_IQ4_Q8_SPLIT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の IQ4_XS 行列ベクトル積で、条件に合う形状について Q8 activation の読み出しを分割する `IQ4Q8Split` カーネルを使うか選びます。分割経路が選ばれない場合は `launch_iq4_pair_reuse` に進みます。この変数は `native_iq4_xs_mmvq` 内でのみ直接読み取られます。GGML type 23 は `native_mmvq` から同関数に振り分けられます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3694, 3750-3756, 4203-4217`）。

## 値と判定

関数内の `static const bool` 初期化で `std::getenv` の戻り値を調べ、未設定なら `true`、設定されていれば先頭文字が `'1'` の場合だけ `true` にします。文字列全体の比較や数値変換はしません。したがって空文字は無効、`1`・`1anything` は有効、`0`・`0anything`・`true`・`01`・先頭空白付きの ` 1` は無効です（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3740-3743`）。

| 条件 | unset | split を許可する値 | split を許可しない値 |
|---|---|---|---|
| この SYCL 関数で split 判定まで到達 | `true`（既定） | 先頭文字が `1`（例: `1`, `1anything`） | 空文字、`0`, `0anything`, `true`, `01`, ` 1` |

## 有効になる条件

- SYCL backend の `native_iq4_xs_mmvq` が呼ばれること。GGML type 23 が `native_mmvq` からこの関数に渡されます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217`）。
- 関数冒頭の Battlemage packed/cache 経路などで早期 return せず、split 判定まで到達すること（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3735`）。
- `STRATA_SYCL_IQ4_PAIR_REUSE` が未設定か先頭文字 `'1'` であること。この別変数が false なら split 判定にかかわらず pair reuse 分岐に入らず、後続の通常経路へ進みます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3736-3739, 3750`）。
- GPU 世代が Battlemage、`ncols` が 1〜4、`n_in` が 2560 または 6144 であり、重みと Q8 activation の両ポインタが 64-byte aligned であること（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3748-3752`）。
- 形状が次のいずれかであること: `(n_in, n_out, ncols) = (2560, 10240, 4)`, `(6144, 2560, 4)`, `(2560, 106299, 1)`。この `selected` 条件に一致しない形状では pair reuse を選びます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3753-3756`）。

## 実行時の詳細

値は `native_iq4_xs_mmvq` が初めて split 判定箇所に到達したとき、関数ローカル `static` として一度読み取られます。その後の呼び出しではキャッシュ値が使われるため、同一プロセスで環境を変更しても判定には反映されません。前段の早期 return 経路では初期化・読み取り自体が起きない場合があります（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3743`）。

条件が揃い `split` が true なら `launch_iq4_q8_split(1, ...)` を呼び、false なら `launch_iq4_pair_reuse(1, ...)` を呼びます。split launcher は mode、ポインタ、出力数、token 数、入力幅を検証し、不正な引数なら `std::invalid_argument("IQ4 split normal route")` を投げます。正常な経路では入力幅 2560/6144 に応じて各々の dispatch を起動し、`launch_check()` を呼びます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3754-3756, 4635-4640`）。この環境変数による CLI・サーバー引数との優先順位、子プロセスへの転送、リクエスト単位の設定処理は見つかりません。

## ログと測定値

この分岐には環境変数の値や選択経路を出すログはありません。split launcher は不正引数で上記例外を投げ、正常な起動後は `launch_check()` を通します。Strata の資料でこの変数に紐づく条件付き測定値は確認できなかったため、速度・正確性の差は記載しません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3754-3756, 4635-4640`）。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3756` — 関数、先行経路、値の読み取りと分岐条件。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217` — native MMVQ の GGML type 23 dispatch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4431-4445, 4635-4640` — split kernel の起動と引数検証。
