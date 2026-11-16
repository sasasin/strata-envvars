# `STRATA_SYCL_IQ4_T4_XMX`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL backend の IQ4_XS 行列ベクトル積で、条件に合う Battlemage 上の 4 列処理を XMX joint-matrix カーネルへ切り替える opt-in 変数。対象呼び出しが通常の IQ4_XS 計算から別経路になるが、モデルや重みの選択は変更しない。読み取りと分岐は `strata::kernels::native_iq4_xs_mmvq` にあり、GGML type 23（IQ4_XS）の `native_mmvq` dispatch から呼ばれる（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3693,3764-3770,4203-4217`）。

このコードは `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあり、SYCL build の `strata_kernels` ソースとして組み込まれる。CUDA 実装 `src/kernels/cuda/native_mmvq.cu` にはこの環境変数の参照がない（`sycl/CMakeLists.txt:245-253`）。

## 値と判定

関数内 `static const bool` の初期化で `std::getenv` を呼び、値が存在し、かつ先頭文字 `e[0]` が文字 `'1'` なら有効とする。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3764`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL の IQ4_XS 経路がこの判定まで到達 | 無効（`false`） | 先頭文字が `1`：`1`、`10`、`1anything` | 空文字、`0`、`true`、` 1`、`01`、`2` |

## 有効になる条件

- SYCL build の IQ4_XS（GGML type 23）行列ベクトル積であること。CUDA backend の同名演算にはこの読み取りはない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217`; CUDA 側 `src/kernels/cuda/native_mmvq.cu:3321-3343`）。
- Battlemage と判定されるデバイス、`ncols == 4`、かつ次の形状であること：`n_in == 2560` かつ `n_out` が `6144`、`10240`、`12288`、`248320` のいずれか、または `n_in == 6144 && n_out == 2560`（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3748-3749,3765-3769`）。
- 重みと activation のアドレス 64-byte alignment は、この XMX 分岐自身では検査しない。ただし先行する pair reuse / ESIMD 分岐は alignment 条件を持つため、該当時はそちらで先に処理される（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3750-3762,3766-3770`）。
- 先行経路が戻らず、この分岐まで到達する必要がある。B60 packed/cache 条件を満たす経路は先に処理される（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3735`）。また、Battlemage・対象の入力サイズ・4列で alignment が合う `STRATA_SYCL_IQ4_PAIR_REUSE` 経路が有効なら、その分岐が先に戻る。`STRATA_SYCL_IQ4_T4_ESIMD` が先頭 `1` で、同じく Battlemage・4列・入力サイズ・alignment 条件を満たす場合も先に戻る（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3736-3763`）。pair reuse は `STRATA_SYCL_IQ4_PAIR_REUSE` 未設定なら有効で、設定時は先頭文字が `1` のときだけ有効（同ファイル `3736-3739`）。
- この XMX 分岐は明示的な aspect / joint-matrix capability 検査をせず、前述の世代・形状条件で起動する。対応デバイス機能がない場合の挙動を Strata のコードだけからは確定できない（同ファイル `3765-3770,2012-2024`）。

## 実行時の詳細

`native_mmvq` は GGML type 23 を `native_iq4_xs_mmvq` に渡す。環境値はその関数の先行する B60・pair reuse・ESIMD の早期 return を通過した後に評価される。関数内 `static` なので、初めてこの宣言まで到達した時の値をプロセス内で保持し、以後の呼び出しでは環境の変更を読み直さない。先行経路しか通らない実行では、初期化も行われない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3770,4203-4217`）。

環境判定より前に形状・ポインター・stream を検証する。`n_in` は正で 256 の倍数、`ncols` は 1〜8、`n_out` は正、各ポインターは非 null かつ 4-byte aligned、stream は非 null でなければ `std::invalid_argument` になる（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2297-2309,3692-3700`）。

分岐に入ると `n_in == 2560` では `iq4_xmx_virtual_T<10>`、`n_in == 6144` では `<24>` を呼ぶ。カーネルは 16 行単位で処理し、`ncols` を T とするテンプレート版を起動する。ここでは `ncols == 4` に限定される。計算結果は `y` に書き込まれ、分岐後に `launch_check()` を呼んで通常の経路へ戻る（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2006-2059,2061-2065,3766-3770`）。

CLI 引数や設定ファイルによる上書きは、この読み取り箇所にはない。環境値が無効、または条件に合わない場合はこの XMX 分岐を通らず、後続の wide lookup / wide IQ4_XS / multi または標準 IQ4_XS kernel の候補へ進む（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3772-3784`）。

## ログと測定値

この変数を読み取る分岐に、選択結果を示す Strata のログ出力はない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3764-3770`）。前述の入力検証に失敗すると記載された `std::invalid_argument` が投げられる。選択経路の後では `launch_check()` が呼ばれるが、現実装は CUDA 由来の error code を `0` に置き換えており、独自のエラーメッセージを出す条件分岐は到達しない（同ファイル `2311-2334`）。SYCL の起動・実行時例外が発生するかどうかや、その外部実装側の表示内容はここでは断定しない。確認した Strata docs にこの変数の測定値は見当たらず、性能差は記載しない。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3770,4203-4217` — IQ4_XS 関数、値判定、条件・優先分岐、GGML type dispatch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2006-2059,2061-2065` — XMX kernel と T 別 launch。
- `sycl/CMakeLists.txt:245-253` — SYCL kernel library の構成。
- `src/kernels/cuda/native_mmvq.cu:3321-3343` — CUDA の同等関数に当該環境変数の読み取りがないこと。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2311-2330` — `launch_check()` の実装。
