# `STRATA_VERIFY_DEBUG`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

verifier の実行経過や内部状態を標準エラーへ出す診断用スイッチです。CUDA/HIP 共通実装では verify window の capture・入力 staging・launch、各 layer の GPU 到達と CPU expert 処理、window 完了のログを追加します。SYCL 実装では同様の進行ログに加え、各 window の時間内訳を表示します。また `STRATA_VERIFY_NO_HOST` が有効な SYCL 経路では、window 後に device 側の状態や layer ごとの残差統計を出すための追加コピーと集計を行います。

通常の verifier の計算値や経路を選ぶ設定ではなく、診断ログおよび SYCL の診断用バッファ・読み戻しを有効にします。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値を設定 | 有効 |

値の文字列や数値は parse せず、`std::getenv("STRATA_VERIFY_DEBUG") != nullptr` で設定の有無だけを判定します。したがって `0`、`false`、空文字も有効です。

CUDA/HIP 共通実装と SYCL 実装にある `g_dbg` は翻訳単位の初期化時に一度評価され、その後 `VDBG` が同じ値を使います。SYCL ではこれとは別に verifier 初期化時の debug buffer 確保、各 window 終了時の時間表示と all-resident 状態ダンプで `getenv` を直接再確認します。環境変数をプロセス実行中に変更すると、各処理で有効状態が一致しない場合があります。

## 有効になる条件

- CUDA/HIP 共通実装では `src/core/verify.cpp` の verifier 経路で有効です。`VDBG` の各ログは値が設定済みの場合に限り stderr へ出ます。
- SYCL では `sycl/src/core/verify.cpp` の verifier 経路で有効です。通常の `VDBG` ログに加えて window の時間内訳を出します。
- SYCL の layer ごとの `R` / `mixed` 診断バッファは verifier 初期化時にこの変数が設定されている場合に確保され、window graph が token 0（`Rt(0)`）の値を layer ごとに記録します。詳細な読み戻しと集計ログはさらに `STRATA_VERIFY_NO_HOST` が有効な場合に限られます。
- SYCL の all-resident 状態ダンプは `no_host` と `STRATA_VERIFY_DEBUG` の両方が有効な window に限られます。`STRATA_VERIFY_NO_HOST` は未設定・空文字・文字列全体が `0` の場合は無効で、それ以外の設定値で有効です。`no_host` が無効ならこの大きな状態ダンプは行いません。
- layer 到達・CPU expert 処理の進行ログは、host が layer ごとに処理する ring loop を通る場合に限られます。CUDA/HIP の all-resident 経路や SYCL の `no_host` 経路はこの loop を飛ばすため、そのログは出ません。

## 実行時の詳細

CUDA/HIP 共通実装では、`VDBG` が `fprintf(stderr, "verify dbg: ...")` の形式でログを出し、各行の後に `fflush(stderr)` します。対象は capture 後、staging 後、launch 後、GPU が layer に到達した時、CPU expert pool の処理後、window 完了時です。値を読むだけのため、verify の計算や token 選択を変更する分岐はありません。

SYCL 実装も同じ進行ログを出します。追加で各 window の `T`、前の window からの間隔、staging 時間、GPU 時間を stderr に出します。SYCL で `no_host` とデバッグ設定が両方有効なら、window 完了後に host sequence、skip 値、layer-0 の weights / expert ids、`d_res` と出力 token の先頭値を出し、いくつかの device 配列について平均絶対値・最大絶対値・非有限値数・先頭4値を集計します。layer ごとには token 0 の `R` と mixed 値を device から読み戻し、平均絶対値と非有限値数を表示します。この経路はデバッグ値を device から host にコピーして集計するため、診断時の追加処理です。

## 根拠

- `src/core/verify.cpp:69,157` — 環境変数の存在判定と `VDBG` マクロ。
- `src/core/verify.cpp:2148,2167,2176,2234,2247,2360` — capture / staging / launch / layer 到達・処理 / window 完了の stderr ログ。
- `sycl/src/core/verify.cpp:70,77` — SYCL 版の存在判定と `VDBG` マクロ。
- `sycl/src/core/verify.cpp:773-776,1537-1539` — debug buffer の確保と、各 layer の token 0 残差・mixed 値の記録。
- `sycl/src/core/verify.cpp:2008,2027,2175,2254,2271,2446` — SYCL 版の進行ログ。
- `sycl/src/core/verify.cpp:2311-2316` — window ごとの時間内訳。
- `sycl/src/core/verify.cpp:2333-2390` — `no_host` 時の状態読み戻し、統計と layer ごとの残差ログ。
- `docs/INTEL.md:262-264` — SYCL の不具合調査で `STRATA_VERIFY_DEBUG=1` の per-layer residual ladder を使ったとの説明。表示内容と適用条件の詳細はソース実装を根拠とした。
