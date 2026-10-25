# `STRATA_HC_CHECK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend で hyper-connection read の split / staged 実装を plain read と比較する自己検査を許可します。実装は値を parse せず、環境変数が存在するかだけを見ます。通常の CUDA 実装にはこの変数の読み取りがなく、CUDA 側の `fused_gr_check()` は別の `STRATA_HC_SPLIT` 設定に基づいて検査します。

SYCL の `Verifier::init()` は GPU ごとの初期化時に `fused_gr_check()` を呼びます。`STRATA_HC_CHECK` が未設定ならそのカードの自己検査をスキップして plain variant を記録します。設定されていれば、ランダムな重みと入力を使って plain / split / staged read を複数 token 数および pending write の有無で比較します。比較後に選んだ variant をカードごとの状態へ保存し、結果を stderr に出します。

ただし、現行 SYCL ソース内では `fused_gr_variant()` の呼び出し箇所が見つかりません。自己検査関数は選択結果を記録し、公開関数はその値を返せますが、検査後の通常経路でその値を参照して variant を切り替える接続は、この commit の SYCL ソースからは確認できません。従って、この変数が通常の SYCL 計算経路を split / staged に切り替えるとは断定できません。

## 値と判定

| 値 | SYCL `fused_gr_check()` の動作 |
|---|---|
| 未設定 | 検査を実行せず、そのカードを plain read として記録 |
| 空文字 | 設定済みとして検査を実行 |
| `0`、`false`、`1`、その他の文字列 | すべて設定済みとして検査を実行 |

判定は `std::getenv("STRATA_HC_CHECK") == nullptr` のみです。値の内容、先頭文字、大文字小文字、数値としての妥当性は見ません。`STRATA_HC_CHECK=0` も検査を有効にします。

検査する上限 variant は別変数 `STRATA_HC_SPLIT` で決まります。`STRATA_HC_SPLIT` が未設定または空なら staged、先頭文字が `0` なら plain、`1` なら split、それ以外なら staged です。検査結果が許可した範囲で最も新しい variant を選びます。これは `STRATA_HC_CHECK` 自身の値判定ではありません。

## 有効になる条件

- SYCL backend の `sycl/src/kernels/cuda/fused_gr.dp.cpp` が使われ、`Verifier::init()` が対象カードで `fused_gr_check()` を呼ぶこと。
- そのカードの検査状態がまだ設定されていないこと。状態はデバイス ID ごとの `g_variant[64]` に保持され、正の値が記録済みなら後続呼び出しは早期 return します。そのため、最初の verifier 初期化後に環境を変更しても同じプロセス・カードでは再検査されません。
- カード ID が `0..63` の範囲にあること。範囲外では `fused_gr_check()` は何もせず戻ります。

SYCL port は upstream の variant を通常の read 経路で使わず、split norm / sliced down 実装を持つというコード注記があり、B70 では自己検査がクラッシュした履歴が `docs/INTEL.md` に記録されています。自己検査が実行可能か、また結果を通常 dispatch が消費するかは GPU 実行なしには確認していません。

## 実行時の詳細

`fused_gr_check()` は verifier 初期化から呼ばれます。未設定時は `g_variant[dev]` に plain を保存して終了します。設定時は決定的 seed `20260930` の乱数から検査データを生成し、1〜最大 8 token、pending write の有無で各 read を実行します。比較は float のビット列単位です。割当・実行・read-back などの失敗時や出力差がある場合、split / staged は不合格扱いとなり plain に fallback します。

検査時には `strata hc: CUDA%d: ...` 形式の stderr ログが出ます。設定値が plain を要求する `STRATA_HC_SPLIT=0` の場合は検査を行わず、plain で動く旨を記録してログを出します。未設定で検査をスキップする経路はログを出しません。SYCL 実装内の例外 catch は例外内容とファイル・行を stderr に出して `exit(1)` します。

`docs/INTEL.md` は「`STRATA_HC_CHECK=1` のときだけ」と説明しますが、実装は設定値を比較していません。コード上は任意の設定値で検査が有効です。また、通常 CUDA の `fused_gr_check()` にはこの opt-in 判定がありません。

## 根拠

- `sycl/src/core/verify.cpp:466-480` — `Verifier::init()` からカードごとの検査関数を呼ぶ。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1580-1587` — `STRATA_HC_SPLIT` の先頭文字による variant 上限判定。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1954-1964,2110-2149` — 自己検査の範囲、seed、variant 実行、ビット単位の比較。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2176-2224` — カード状態の確認、`STRATA_HC_CHECK` の存在判定、fallback と stderr ログ。
- `include/strata/kernels/fused_gr.hpp:64-75` — 公開 API と意図の説明。
- `src/kernels/cuda/fused_gr.cu:2127-2169` — 通常 CUDA 実装。`STRATA_HC_CHECK` を読み取らず、`STRATA_HC_SPLIT` に基づいて検査する。
- `docs/INTEL.md:558-561` — SYCL では `STRATA_HC_CHECK=1` で opt-in と説明している。値判定については上記実装との差がある。
