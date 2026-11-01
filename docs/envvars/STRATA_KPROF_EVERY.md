# `STRATA_KPROF_EVERY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main`（`origin/main` と表示）、未コミット変更なし。

## 役割

SYCL エンジン内蔵のカーネルプロファイラが phase の計測値を flush する際、集計レポートを stderr に追加出力する間隔を指定します。この変数だけでは計測もプロファイラの有効化も行いません。別変数 `STRATA_KPROF` が有効で、プロファイラが記録したイベントを flush するときにのみ効果があります。対象実装は `sycl/` 以下の SYCL エンジンです。

## 値と判定

実装は `std::getenv` の結果を `std::atoll` に渡し、変換後の値が正数かどうかを判定します。文字列全体の検証やエラー報告はありません。

| 値 | 判定と挙動 |
|---|---|
| 未設定 | `0` として扱い、flush ごとのレポートは出さない |
| 空文字 | `atoll` の変換結果は `0`。flush ごとのレポートは出さない |
| 正数に変換される文字列 | 現在の phase の flush 回数がその数の倍数になるたびに、集計レポートを stderr に出す |
| `0`、負数、先頭から数値に変換できない文字列 | `every > 0` を満たさず、flush ごとのレポートは出さない |

`atoll` は整数として読める先頭部分を変換し、後続文字列を検証しません。したがって、例えば `3x` は `3`、`1.5` は `1` として扱われます。先頭の空白や符号も整数変換の規則に従います。値の範囲を別途検査したり clamp したりする処理、無効値に対する警告・エラーはありません。

## 有効になる条件

- SYCL 実装の `sycl/include/strata/kprof.hpp` が使われるビルドであること。CUDA/HIP/Metal 実装で同名変数を読む箇所は見つかりません。
- `STRATA_KPROF` が設定され、値の先頭文字が `0` ではないこと。未設定または先頭文字が `0` なら計測処理が無効で、この変数による定期レポートもありません。`STRATA_KPROF` の有効判定も関数内 `static` に cache されます。
- SYCL のプロファイラが kernel/event を記録し、空でない記録を flush すること。flush 対象が空なら `STRATA_KPROF_EVERY` の読み取り自体が行われません。

デコードの通常の graph replay はカーネルイベントを記録しません。`STRATA_VERIFY_EAGER` が設定されると verifier は eager 経路を使い、デコード window のイベント計測が可能になります。prompt は prompt chunk/window の処理から phase flush に進みます。これらの条件は `STRATA_KPROF_EVERY` 自身の値判定とは別です。

## 実行時の詳細

`flush_locked()` は記録済みイベントを現在の phase（例: `prompt`、`decode`）に集計し、その phase の `flushes` を増やします。`STRATA_KPROF_EVERY` は `flush_locked()` 内の関数ローカル `static const long long` として初回の非空 flush 時に一度だけ読み込まれます。以降、プロセス実行中に環境値を変えても再評価されません。正数 `N` の場合、flush した phase の `flushes % N == 0` のタイミングで、flush 数がある全 phase の集計表を stderr に書き込み、stderr を flush します。間隔のカウントは全体通算ではなく phase ごとです。

プロセス終了時、`State` の destructor は残りイベントを flush し、集計レポートを stderr に出します。この終了時レポートは `STRATA_KPROF_EVERY` が未設定、0、負数でも出力され得るため、この変数は終了時レポートの ON/OFF スイッチではありません。表の行数上限は別変数 `STRATA_KPROF_TOP`（未設定時 45）が決めます。

この変数の無効値を理由にしたログ、終了、失敗経路はありません。SYCL event の待機・profiling info 取得は `flush_locked()` で行われますが、その取得中の例外は catch されて無視されます。定期レポートの `fprintf` 自体について専用のエラー処理はありません。

## 根拠

- `sycl/include/strata/kprof.hpp:142-188` — 空 flush の早期 return、イベント集計、phase ごとの flush 回数、`atoll` による cache 済み判定、正数間隔での stderr 出力。
- `sycl/include/strata/kprof.hpp:190-220` — profiler 有効時のみ flush する経路と、終了時に間隔条件なしで集計を出す処理。
- `sycl/include/strata/kprof.hpp:31-34,223-253` — `STRATA_KPROF` の判定 cache と kernel launch/event 記録の gate。
- `sycl/include/dpct/device.hpp:685-701` — `STRATA_KPROF` 有効時に SYCL queue profiling property を付ける処理。
- `sycl/src/core/verify.cpp:1830-1838,2107-2112,2516-2522` — graph replay / `STRATA_VERIFY_EAGER` 分岐、decode phase 開始と window 終了時の profiler flush。
- `sycl/src/prefill/prefill.cpp:2388-2393,5009-5011` — prompt phase 開始と処理終了時の profiler flush。
