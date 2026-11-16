# `STRATA_PRIVATE_GU_GRID_S4`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。調査開始時の Strata 作業ツリーは `main` で `origin/main` と一致し、`git status --short --branch` に未コミット変更はありませんでした。

## 役割

SYCL エンジンの grouped expert の gate/up（GU）計算で、条件が一致する特定形状に対し、通常の型別 `launch_gu` 経路の代わりに `launch_grid_s4` の ESIMD kernel を選ぶための opt-in 環境変数です。`grid_s4_packet` は重みコードと符号を grid から展開し、DP4A の積和と scale を適用して gate/up 出力バッファへ値を書きます。環境変数は選択フラグであり、モデル設定や出力先を直接設定するものではありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4913`, `4981-5023`, `5063-5085`, `7403-7417`）。

この読み取りと kernel は SYCL ポートの `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にあります。トップレベルでは `STRATA_ENABLE_SYCL` が有効なときに独立した SYCL project を構成し、それ以外の CUDA/HIP エンジンからはこの実装を使いません（`CMakeLists.txt:23-32`, `sycl/CMakeLists.txt:1-11,240-253`）。

## 値と判定

`grid_s4_enabled()` は `std::getenv` で値を取得し、値が存在して先頭文字が文字 `'1'` のときだけ `true` を返します。文字列全体の比較や数値 parse はしません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4913`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL grouped expert dispatch がこの判定箇所まで到達 | `false` | 先頭が `1` の値。例: `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, `True`, ` 1` |

先頭 1 文字以降は判定されないため、`1` の後ろの文字列・数値妥当性は検査されません。大文字小文字は文字列比較の対象ではなく、先頭文字が ASCII の `1` かどうかだけで決まります。空文字は設定済みでも無効です。別の CLI 引数によるこの値の上書きや、無効文字列時の fallback 値はありません（同上）。

## 有効になる条件

値が有効でも、次をすべて満たす grouped expert 呼び出しでなければこの kernel は選択されません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469,7403-7406`）。

- SYCL 版がビルドされていること。CUDA/HIP や CPU 専用の別エンジンではこのコードは実行されません（`CMakeLists.txt:23-32`）。
- GU の型 ID `22`、`L.n_embd == 2560`、`L.n_ff == 640` であること。
- `v1` grouped 経路、`STRATA_OLD_IQ_MMVQ` による旧 kernel、`STRATA_EXPERT_SPLIT` による split multi 経路のいずれでもないこと（`!v1 && !g_old_kernels && !g_split_multi`）。
- `STRATA_GU_LANES` から決まる `gu_lanes()` が `8` であること。値が省略・不正なら既定 lane 数 `kExpertLanes` に戻り、4/8/16/32 以外も既定値に戻ります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4243-4248`）。
- `grid_groups == 0` かつ `cap_groups == cap_entries` であること。
- `cap_entries == 10`、または `cap_entries` が 20 か 40 で、単一 actor モードではなく device 0 を使っていること。
- `ps_enabled(device)` が真であること。これは `STRATA_PRIVATE_PACKED_REGISTER` の先頭文字が `1` で、B60 main actor であり、weights が packed 済みで、実行 device の世代が Battlemage の場合に限り真です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`）。

dispatch は順序付き `if` / `else if` です。先行する GU-XXS-S4、S4-basis9、S4-WG16 の条件が成立した場合はそちらが先に起動され、この変数の経路には到達しません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7406`）。それらの条件が成立しない場合でも、本変数が無効、または上記条件のいずれかを満たさなければ、後続の grid64 条件または `L.gu_type` による通常の型別 `launch_gu` に進みます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7408-7417`）。

## 実行時の詳細

環境変数の判定は `grid_s4_enabled()` の関数内 `static const bool` にキャッシュされます。読み取りは grouped expert dispatch が固定形状などの先行条件を満たし、この判定式まで到達した最初のときに行われます。その後の呼び出しでは同じ結果を使い、プロセス実行中に環境を変更しても再評価されません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4913,7403-7406`）。

選択された場合、`launch_grid_s4` は SYCL queue に `GuGridS4Kernel` を投入します。kernel は各 expert entry について gate/up 側の行を処理し、`grid_s4_packet` が計算結果を `first_output` / `second_output`（呼び出し側の `gate` / `up`）に格納します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4981-5023,5063-5085,7405-7406`）。

この変数を読み取り、子プロセスへ転送する Strata 所有箇所は見つかりませんでした。読み取りはプロセス内の SYCL kernel dispatch に限られます。

## ログと測定値

この変数の有効・無効や選択理由を表示する専用ログはありません。該当する dispatch は `launch_grid_s4` を呼び分けるだけです（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7403-7417`）。この変数に結び付く測定値も、確認した Strata の資料には記載されていません。

## 根拠

- 直接読み取りと先頭文字判定、static cache: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4913`
- packed-register・デバイス条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`
- GU lane 数の取得・許容値: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4243-4248`
- S4 packet の演算と出力: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4981-5023`
- kernel launch: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5063-5085`
- grouped expert の優先順位と fallback: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7417`
- SYCL backend の分離: `CMakeLists.txt:23-32`, `sycl/CMakeLists.txt:1-11,240-253`
