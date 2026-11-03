# `STRATA_LAUNCH_PROBE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

verify window の graph capture / launch に関する診断ログを出します。HIP では capture した graph の node 数と kernel node 数を stderr に出し、`STRATA_VERIFY_HGL` が定義されるビルドでは通常 launch の最初の最大12 windowについて、launch 呼び出しの所要時間と GPU/host の進行状況を stderr に記録します。計算や launch の選択を切り替える設定ではありません。

この変数は verifier の `capture()` または `run()` が実行される経路でのみ参照されます。実行時に verifier を使わない場合、診断ログは出ません。候補一覧に名前がありますが、Strata 内の実装読み取りは `src/core/verify.cpp` の2箇所です（同ファイル中のコメントを除く）。

## 値と判定

両方の読み取り箇所が使う `env_on()` は、値を文字列全体として parse せず、未設定でないこと、空文字でないこと、先頭文字が `0` でないことを判定します。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外（例: `1`, `true`, `false`, `2`, ` 1`） | 有効 |

数値変換、範囲制限、大文字小文字の変換はありません。したがって `false` も有効です。

## 有効になる条件

- **HIP**: `Verifier::capture()` が新しい window graph を capture するとき、`STRATA_USE_HIP` のビルドで graph node 数を出します。既に同じ graph が作成済みなら `capture()` は冒頭で戻るため、毎 window ではなく、新たな graph capture ごとのログです。1回の capture につき `hipGraphGetNodes()` で総 node 数を取得し、その node 群から kernel node 数を数えます。
- **`STRATA_VERIFY_HGL` が定義されるビルド**: `Verifier::run()` が通常の window launch を行うとき、最初に評価した環境値を関数内 static に保存し、値が有効なら通常 launch の最初の最大12 windowを計測します。`pre` として既に prelaunch 済みの window は対象外です。定義条件は `src/core/verify.cpp:1-5` のプリプロセッサ条件です。
- **その他のビルド**: HIP の node 数ログを除き、この変数による処理はありません。特に SYCL の `sycl/src/core/verify.cpp` にはこの名前の読み取りがありません。

`STRATA_VERIFY_ASYNC_LAUNCH` は別設定です。`STRATA_LAUNCH_PROBE` が有効でも自動的に helper thread launch にはなりません。helper thread の使用は `STRATA_VERIFY_HGL` 経路で別途 `STRATA_VERIFY_ASYNC_LAUNCH` の先頭文字が `1` かにより決まり、その状態を probe のログに表示します。

## 実行時の詳細

HIP の node 数診断は `capture()` が graph capture に成功した後に行われます。stderr の形式は `strata tdr-probe: the %d-token window graph has %zu nodes, %zu of them kernels` です。`STRATA_USE_HIP` 条件内で `env_on("STRATA_LAUNCH_PROBE")` を capture ごとに評価し、この読み取り結果は cache しません。

launch timing 診断は `run()` 内で `probe_on` を初回評価時に cache します。設定の変更は、その static 初期化後には反映されません。probe が対象にする window はプロセス内の static counter で数え、対象ごとに launch 前に process 起動からの経過時間、空き VRAM、window 情報を記録します。launch 呼び出しが戻らない間は別 thread が 50、250、500、1000、2000、3000、5000、10000、30000 ms の各時点で、GPU の rung 数と host が処理した flag 数を stderr に出します。launch 呼び出しが戻ると監視 thread を join し、呼び出しが `returned` したか helper に `handed to the helper` されたか、所要時間と返却時点の進行状況を記録します。

probe 自体は launch 結果を書き換えません。launch が失敗した場合は通常の処理として `verify: launch: <CUDA/HIP error string>` を `err` に設定して `run()` が失敗します。probe のログ追加だけを理由に終了する経路はありません。launch 前の空き VRAM 問い合わせの戻り値は無視されています。

## 根拠

- `src/core/verify.cpp:305-315` — `env_on()` の値判定と HIP 用 compile guard。
- `src/core/verify.cpp:2748-2751,2768-2780,2884-2896` — graph capture 時の読み取り条件、既存 graph の早期 return、HIP node 数診断。
- `src/core/verify.cpp:3220-3221,3264-3270,3310-3365` — `run()` の経路、static cache、最大12件の選別、launch 前・待機中・返却時のログ。
- `src/core/verify.cpp:3326-3331,3357-3377` — `STRATA_VERIFY_HGL` の launch 経路、別変数による helper thread 選択、launch 失敗時の通常エラー処理。
- `sycl/src/core/verify.cpp` — 同名の読み取りなし（対象名のリポジトリ全体検索結果）。
