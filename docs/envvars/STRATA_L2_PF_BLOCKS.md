# `STRATA_L2_PF_BLOCKS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の L2 prefetch kernel `l2_prefetch_kernel` を起動するときの grid block 数を指定する。値は 1〜64 に clamp されるため、この変数単独では prefetch の有効・無効を切り替えない。prefetch 自体は `STRATA_L2_PF` が有効で、partial-residency の verify 経路などの条件が揃ったときだけ呼び出される。kernel は cache prefetch hint を出し、通常の読み書き計算はしない（`engine/src/kernels/cuda/verify_kernels.cu:1932-1948`, `1962-1965`; 呼び出し条件は `engine/src/core/verify.cpp:1558-1565`, `2838-2845`, `2897-2906`）。

## 値と判定

`std::getenv` で設定の有無を調べ、設定値は `std::atoi` で `int` に変換する。文字列全体の妥当性検査はなく、`atoi` が返した値を `std::max(1, std::min(value, 64))` で 1〜64 に制限する（`engine/src/kernels/cuda/verify_kernels.cu:1962-1964`）。

| ビルド・条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・変換例 |
|---|---|---|---|
| prefetch kernel が呼ばれる CUDA 経路 | `atoi` を通さず既定値 8（clamp 後も 8） | 1〜64。例: `1`→1、`8`→8、`64`→64 | 0 以下は 1（`0`、`0anything`、`abc`、`-2`→1）。65 以上は 64（`65`→64）。空文字も `atoi("") == 0` となり 1 |
| HIP 経路 | ブロック数を読まない | 該当なし | `verify.cpp` 側で prefetch を無効にするため、この kernel 呼び出しに至らない |

`atoi` は先頭の空白と符号を許し、先頭の整数部分だけを読むため、`  +3tail` は 3 として扱われます。先頭に数値がない文字列は 0 となり clamp で 1 になります。大文字小文字の比較はありません。整数型で表せない数値文字列については `atoi` の範囲外動作を Strata が検査・定義していません。未設定と空文字は異なり、未設定は 8、空文字は 1 です。

## 有効になる条件

- ビルド・実行経路に CUDA の `verify_kernels.cu` が使われ、`l2_prefetch_ranges` が呼び出されること。HIP では `l2pf_cuda` が `false` です（`engine/src/core/verify.cpp:1560-1565`）。
- 呼び出し側で `STRATA_L2_PF` が unset なら 0、設定時は `atoi` で解釈した値が 0 以外であること。したがって `STRATA_L2_PF=abc` や空文字は機能を有効にしません（同 `verify.cpp:1558-1565`）。ソース中の NVIDIA defaults にも L2 prefetch は opt-in と記されています（`engine/src/core/nv_defaults.cpp:76-82`, `104-113`）。
- `G == 1`、batch recording ではない、stage profiler が無効、all-resident 計画ではないこと（`engine/src/core/verify.cpp:1565`）。
- 対象レイヤーの prefetch set が空でなく、次レイヤーが現在の layer range 内にあり、共有 side stream と fork/join event が利用できること（`engine/src/core/verify.cpp:2838-2845`, `2897-2906`）。prefetch 対象は `blk.*` の範囲内レイヤーに属し、データを持つ重みから組み立てられます（同 `verify.cpp:1569-1601`）。
- 直接の CLI 引数によるブロック数上書きはありません。CLI やモデル状態が上記の verify / batch / residency 条件を変えた場合は、prefetch 呼び出し自体がなくなり、この値も参照されません（同 `verify.cpp:1565`, `2838-2845`, `2897-2906`）。

## 実行時の詳細

ブロック数は `l2_prefetch_ranges` 内の関数ローカル `static const` 初期化子で読み込まれます。これはプロセス起動時ではなく、この関数が最初に実行された時点で一度だけ評価され、以後の環境変更は反映されません。prefetch API は、現在の layer `l` の重みではなく次の layer `l + 1` の範囲を共有 side stream に投入します。呼び出し箇所は device-hits 経路と、通常の partial-residency で device plan を使わない経路です（`engine/src/core/verify.cpp:2833-2845`, `2893-2906`; kernel の static cache と launch は `engine/src/kernels/cuda/verify_kernels.cu:1952-1965`）。

この変数は grid の block 数だけを変えます。起動後は `check("l2_prefetch_ranges")` が `cudaGetLastError()` を確認し、CUDA エラーなら stderr に `l2_prefetch_ranges: <CUDA error text>` を出して `exit(1)` します（`engine/src/kernels/cuda/verify_kernels.cu:37-40`, `1964-1965`）。

## ログと測定値

`STRATA_L2_PF_BLOCKS` の値や clamp 結果を表示するログはありません。親機能の有効条件を通って prefetch set を構築したときは、初回に限り stderr に `strata: STRATA_L2_PF=%d: next-layer dense-weight L2 prefetch while the window waits for CPU experts (largest layer %.1f MiB%s)` が出ます。ここに表示されるのは `STRATA_L2_PF` と対象サイズで、blocks 値ではありません（`engine/src/core/verify.cpp:1603-1608`）。本調査では blocks 値に関する Strata 資料の測定値は確認できませんでした。

## 根拠

- 読み取り・既定値・clamp・kernel 起動: `engine/src/kernels/cuda/verify_kernels.cu:1952-1965`
- prefetch の呼び出し条件・対象 weight set・親変数・有効ログ: `engine/src/core/verify.cpp:1553-1608`, `2833-2845`, `2893-2906`
- HIP で無効になる条件: `engine/src/core/verify.cpp:1560-1565`
- kernel のエラー出力と終了: `engine/src/kernels/cuda/verify_kernels.cu:37-40`
