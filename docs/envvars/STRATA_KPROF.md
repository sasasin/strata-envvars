# `STRATA_KPROF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

SYCL port の Strata kernel profiler を有効にします。有効時、`strata::kprof::kp(...)` 経由で投入された kernel の event を保持し、phase/window/chunk の区切りまたはプロセス終了時に event の開始・終了時刻を集計して stderr に出します。同時に `dpct::device` が作る queue に profiling property を付けます。全ての Strata backend 共通の設定ではなく、実装箇所は `sycl/` 以下です（`sycl/include/strata/kprof.hpp:1-14,223-257`; `sycl/include/dpct/device.hpp:679-701`）。

## 値と判定

2箇所の判定はいずれも `getenv()` が null でないこと、および値の先頭文字が `'0'` でないことです。文字列全体や真偽値として parse しません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効（値は存在し、先頭文字 `\0` は `'0'` ではない） |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、`2`、その他先頭が `0` 以外の値 | 有効 |

空白、大文字小文字、数値としての妥当性は確認しません。queue 作成側と profiler 側では、それぞれ最初の判定結果を `static const bool` に保持します。従って、それぞれの初回評価後にプロセス内で環境値を変更してもその箇所の判定には反映されません（`sycl/include/dpct/device.hpp:685-687`; `sycl/include/strata/kprof.hpp:31-34`）。

## 有効になる条件

- **SYCL backend**: 直接の読み取り・利用は `sycl/include/` と `sycl/src/` にあります。CUDA/HIP の実行経路にこの Strata 側 profiler が有効になる根拠は確認できません。
- **queue 作成**: `dpct::device::create_queue_impl()` が呼ばれた時点で有効判定が真なら、作成 queue に `enable_profiling()` を加えます。偽なら、その translation unit が `DPCT_PROFILING_ENABLED` を定義している場合に限って同 property を付けます。したがって、この変数はマクロによる queue 設定を有効値で上書きし、queue 作成後に設定しても既存 queue の設定は変えません（`sycl/include/dpct/device.hpp:679-701`）。
- **kernel event 記録**: profiler header を使う箇所でも、記録対象は `kp()` の `parallel_for` / `submit` / `single_task` wrapper を通る投入です。`record()` は queue が `executing` 状態でない場合（graph recording 中）には event を保存しません（`sycl/include/strata/kprof.hpp:81-86,223-257`）。SYCL decode は graph replay だと event を記録できないため、decode kernel の per-kernel 計測には別環境変数 `STRATA_VERIFY_EAGER` を設定した eager 経路が必要とコメントに明記されています。prompt は eager launch 経路です（`sycl/include/strata/kprof.hpp:3-8`; `sycl/src/core/verify.cpp:1833-1837,2522`）。
- **CLI・モデル状態**: CLI 引数やモデル状態で `STRATA_KPROF` の判定を変える処理は確認できません。サーバーモード固有の分岐もこの profiler 実装にはありません。

## 実行時の詳細

`STRATA_KPROF` の読み取りは起動時の一箇所に集約されているわけではありません。queue 側は最初の `create_queue_impl()` で、profiler 側は最初の `enabled()` 呼び出しで各々キャッシュします。profiler が有効なら、wrapper が返した event を記録し、graph recording 中の event は除外します。decode の `Verifier::run()` は `phase("decode")` で phase を切り替え、成功した verify window の終わりに `window_end("decode")` を呼びます。prompt の prefill path も終端で `window_end("prompt")` を呼び、蓄積 event を flush します（`sycl/include/strata/kprof.hpp:31-34,81-86,197-213`; `sycl/src/core/verify.cpp:2107-2120,2515-2526`; `sycl/src/prefill/prefill.cpp:5006-5010`）。

flush 時は event を待ち、kernel ごとの開始・終了時刻、queue span、合計を phase ごとに集計します。既定では途中の周期出力はなく、プロセス終了時に残りを flush して、データがあれば集計表を stderr に出します。出力行は `kprof <phase>: ...`、続く行は launch site と時間等です。`STRATA_KPROF_EVERY` が正数に変換される場合はその回数ごとの flush でも stderr に出し、`STRATA_KPROF_TOP` は各 phase 表に出す site 数を制御します（既定値45）。これら2変数は別の環境変数で、本書の対象ではありません（`sycl/include/strata/kprof.hpp:118-139,142-188,215-220`）。

event の wait / profiling timestamp 取得で例外が発生した場合、その event の例外は `catch (...)` で握りつぶされ、その event の集計は加算されません。Strata 独自の警告やエラー出力はこの経路にはありません。SYCL runtime/driver が出すメッセージや挙動はここでは扱いません（`sycl/include/strata/kprof.hpp:147-177`）。

## 根拠

- 候補一覧上の記載: `000_envvers.md:963`。
- 候補名の全参照を検索し、値を読む本番実装として確認した箇所: `sycl/include/dpct/device.hpp:685-687`、`sycl/include/strata/kprof.hpp:31-34`。他の候補名参照は helper のコメント、呼び出し箇所、関連変数 `STRATA_KPROF_EVERY` / `STRATA_KPROF_TOP` で、`STRATA_KPROF` の追加読み取りではありません。
- `docs/DETAILS.md` に `STRATA_KPROF` の説明は見つかりませんでした。挙動の根拠は上記の実装です。
