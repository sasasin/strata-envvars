# `STRATA_GDN_NOY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AMD の GDN（gated-delta-net）再帰 `variant == 1` で、出力正規化後の FP32 バッファ `y` への書き戻しを省くかを指定する。`STRATA_GDN_NOY` が有効なら `gdn_out_norm_loop_kernel<false>` を選び、`y16` への FP16 出力は引き続き書く。無効なら `<true>` を使い、FP32 の `y` と FP16 の `y16` の両方を書く（`engine/src/prefill/kernels.cu:1835-1870, 3122-3137`、SYCL 側 `engine/sycl/src/prefill/kernels.dp.cpp:1715-1746, 2841-2856`）。

通常の prefill 呼び出しは正規化結果 `m.y_h` を出力射影へ渡し、`y16` がその入力であるため、NOY 分岐は FP32 保存を省く（`engine/src/prefill/prefill.cpp:5209-5213, 9342-9344`）。カーネルコメントはこの FP32 結果を後続処理が読まないと説明している（`engine/src/prefill/kernels.cu:1860-1862`）。Strata の資料・ソースコメントに記載された 403 MB は 16K chunk あたりの FP32 結果サイズの説明であり、性能測定値ではない。

名前の他の参照には、gfx1103/gfx1150 用の値 `"1"` を含む `terminal/setup.py` の設定表と、そのキーを setup 管理対象にする一覧がある（`terminal/setup.py:4472-4485, 7544-7547`）。同ファイルにこの名前の環境読み取りはなく、エンジン実行時の読み取り箇所ではない。設定登録 JSON、資料、テストにも名前が現れるが、それらは実行時の読み取り根拠にはしていない。

## 値と判定

HIP 対応実装の `variant == 1` かつ `T > 0` に到達したとき、`std::getenv` の結果を `std::atoi` に渡し、変換値が 0 以外なら有効とする（`engine/src/prefill/kernels.cu:3122-3137`、SYCL 側 `engine/sycl/src/prefill/kernels.dp.cpp:2841-2856`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `variant == 1`, `T > 0`, NOY の分岐まで実行 | `false` | `1`, `-1`, `2`, ` 1`, `1abc`（`atoi` が 0 以外を返す） | 空文字、`0`, `0anything`, `true`, `abc`（変換値が 0） |

文字列全体の妥当性や後続文字は検査しない。先頭の空白と符号は `atoi` の変換規則に従う。整数として変換できない文字列は 0 になる。`atoi` の整数範囲外入力の結果は C/C++ の仕様上保証されないため、受け付ける境界値として断定できない。読み取り箇所に clamp やエラー処理はない（同上）。

## 有効になる条件

- 再帰 dispatch が `variant == 1` であること。通常入口では `STRATA_GDN_HEAD` が非 0 で、かつ `STRATA_GDN_REC_HEADS` が未設定の場合にこの variant が選ばれる（`engine/src/prefill/kernels.cu:3286-3293`、SYCL 側 `engine/sycl/src/prefill/kernels.dp.cpp:2972-2980`）。
- HIP コンパイル時の AMD 向け quad 分岐であること。`variant == 1` の NOY 読み取りは `#if defined(__HIPCC__)` の内側にある。通常の CUDA 分岐ではこの NOY 読み取りを通らない（`engine/src/prefill/kernels.cu:3088-3144`、SYCL 側 `engine/sycl/src/prefill/kernels.dp.cpp:2821-2862`）。
- `T > 0` であること。0 以下なら variant の分岐内で NOY を評価しない（同上）。
- chunked GDN が先に成功して return した場合は NOY 分岐に到達しない。HIP 側では `STRATA_GDN_CHUNKED` と適用可能な chunked kernel の条件により先行経路が成立しうる（`engine/src/prefill/kernels.cu:3088-3100`）。
- `STRATA_GDN_REC_HEADS` が設定されていると通常入口は `variant == 0` にし、この NOY 分岐は使わない。CUDA の state-only KVA 経路では variant 1 のとき読み取り自体は行うが、`with_out == false` のため正規化 kernel を起動せず、NOY による保存有無の差は生じない（`engine/src/prefill/kernels.cu:3122-3137, 3286-3314`）。

Strata は AMD の一部アーキテクチャで起動時に `"1"` を既定設定する。`STRATA_GDN_NOY` がすでに設定されていれば、値が `0` や空文字でもユーザー設定を保持する。既定値を加える対象は gfx12（ただし `STRATA_GFX12_DEFAULTS` が先頭 `'0'` なら無効）、gfx1151（同様に `STRATA_GFX1151_DEFAULTS`）、および非統合の discrete RDNA3 gfx1100/1101/1102（`STRATA_GFX11_DEFAULTS` が先頭 `'0'` なら無効）である（`engine/src/core/arch_defaults.cpp:28-50, 64-75, 302-324`、`engine/include/strata/core/gfx11_extra.hpp:27-52`）。他のアーキテクチャにはこの既定値テーブルからは設定されない。設定値は Windows で `_putenv_s`、それ以外で上書き禁止の `setenv(..., 0)` によりプロセス環境へ設定される（`engine/src/core/arch_defaults.cpp:218-224`）。

## 実行時の詳細

NOY は関数内 `static const bool` の初期化ラムダで最初に該当分岐へ来たとき一度読み取られ、その値がプロセス内でキャッシュされる。したがって初回評価後の環境変更は反映されない。初期化は `T > 0` の `variant == 1` 分岐内にあるので、その分岐に到達しなければ読み取りません（`engine/src/prefill/kernels.cu:3122-3137`、SYCL 側 `engine/sycl/src/prefill/kernels.dp.cpp:2841-2856`）。

NOY が有効な kernel は各要素について `oc` から正規化値 `bp` を求め、gate `sg` と乗算して FP16 の `y16` に書くが、FP32 の `y[at]` には書かない。無効時は同じ出力正規化ループ内で `y[at] = v` と `y16[o16] = hf(v)` を実行する（`engine/src/prefill/kernels.cu:1841-1869`）。再帰状態の更新 kernel 自体の選択は NOY 判定より前に行われる（`engine/src/prefill/kernels.cu:3124-3131`）。

## ログと測定値

NOY を直接示す有効・無効ログ、警告、入力値エラーはない。起動時のアーキテクチャ既定値適用では他のスイッチとまとめたログが出る場合がある。gfx11 discrete の一覧には `GDN_NOY` が含まれ、gfx12 の extra switches 一覧にも設定名が列挙される（`engine/src/core/arch_defaults.cpp:312-332, 360-370`）。gfx1151 の通常テーブルについて、この調査で NOY 専用のログ文言は確認できなかった。

16K chunk あたり 403 MB というコメント上の FP32 バッファ量の記述はあるが、NOY 単独の速度・メモリ測定値は確認できなかった（`engine/src/prefill/kernels.cu:1860-1862`）。

## 根拠

- 値の読み取りと kernel 選択: `engine/src/prefill/kernels.cu:3122-3137`、`engine/sycl/src/prefill/kernels.dp.cpp:2841-2856`
- 出力バッファの書き分け: `engine/src/prefill/kernels.cu:1835-1870`、`engine/sycl/src/prefill/kernels.dp.cpp:1715-1746`
- 通常入口の variant 選択と出力射影: `engine/src/prefill/kernels.cu:3286-3293`、`engine/src/prefill/prefill.cpp:5209-5213`
- アーキテクチャ既定値の適用: `engine/src/core/arch_defaults.cpp:28-50, 64-75, 302-324`、`engine/include/strata/core/gfx11_extra.hpp:27-52`
