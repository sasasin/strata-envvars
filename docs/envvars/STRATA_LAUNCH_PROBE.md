# `STRATA_LAUNCH_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

検証 window graph の診断用 probe を有効にする。HIP では graph capture 時に node 数と kernel node 数を stderr に出す。CUDA と Windows の HIP では、通常実行の最初の 12 window について graph launch の所要時間と、launch 呼び出しが戻るまでに GPU が layer を通知した数・ホストが処理した flag 数を stderr に出す。モデル計算、生成結果、graph の選択を切り替える環境変数ではなく、ソース上で確認できる作用は観測用ログとそのための監視 thread である（`engine/src/core/verify.cpp:3395-3407,3879-3934`）。

## 値と判定

`Verifier::run` と HIP の `Verifier::capture` から `env_on` に名前を渡して読む。helper は `std::getenv` が null でなく、かつ空文字でなく、先頭文字が `'0'` でなければ true を返す。文字列全体の parse、数値変換、大文字小文字の比較はしない（`engine/src/core/verify.cpp:336-339,3395-3396,3879-3882`）。

| ビルド／読み取り箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `Verifier::run` の launch timing probe | 無効 | `1`, `true`, `false`, `2`, ` 0` など、空でなく先頭が `0` 以外の値 | 空文字、`0`, `0anything` など先頭が `0` の値 |
| HIP の `Verifier::capture` の graph node 数 | 無効 | 上と同じ | 上と同じ |

空白は trim されないため、先頭が空白なら後続が `0` でも有効になる。大文字小文字は区別しない比較自体がなく、先頭文字だけで判定する。設定値に CLI 引数や別の環境変数を使った上書き・優先規則はない（`engine/src/core/verify.cpp:336-339`）。

## 有効になる条件

- graph capture／launch を使う GPU `Verifier` 経路を通る必要がある。HIP の node 数ログは `STRATA_USE_HIP` 時だけコンパイルされる（`engine/src/core/verify.cpp:3395-3407`）。
- launch timing の採取・出力は `STRATA_VERIFY_HGL` の compile 条件が成立する場合だけ実行される。この条件は gfx906 互換を除く CUDA 系、または gfx906 互換を除く Windows HIP である。Linux HIP ではこの timing block ではなく通常の `cudaGraphLaunch` が使われるが、HIP の graph node 数ログは別途対象になる（`engine/src/core/verify.cpp:4-5,3895-3939`）。
- Metal の `Verifier::run` は Metal 用処理を行って返るため、この launch timing probe には到達しない（`engine/src/core/verify.cpp:3792-3819`）。SYCL 等について、このファイル以外に同名の読み取り箇所は見つからなかった。
- Timing log は `pre` launch では採番されず、`Verifier::run` 内の共有 atomic counter による最初の 12 件だけが対象。HIP node 数ログはこの 12 件制限とは別で、環境変数が有効な状態で capture した graph ごとに出る（`engine/src/core/verify.cpp:3395-3407,3879-3882`）。
- `STRATA_VERIFY_ASYNC_LAUNCH` は probe の有効・無効を決めない。HGL 経路で launch を helper thread に渡すかを決め、その実行形態が probe のログ文言に反映される。gfx1151 の Windows defaults はこの別変数を既定設定し得る（`engine/src/core/verify.cpp:3895-3911,3926-3934`; `engine/src/core/arch_defaults.cpp:444-452`）。

## 実行時の詳細

Launch timing 用の値は `Verifier::run` 内の `static const bool probe_on` で初回評価時に cache され、実行中に環境を変えても反映されない。初回の `run` 呼び出しから、`pre` でない window ごとに atomic counter を進め、index 0〜11 だけ probe thread を起動する。launch 前に空き VRAM と process start からの時間を記録し、launch 呼び出しがまだ戻らない場合は 50、250、500、1000、2000、3000、5000、10000、30000 ms の各時点で GPU/host の flag 値を出力する。launch が戻ると probe thread を止めて join し、戻り時間と通知数を出力する（`engine/src/core/verify.cpp:345-347,3879-3883,3906-3934`）。

HIP graph node 数用の読み取りは `capture(T)` ごとに helper を呼ぶ。capture 済み graph が存在すれば `capture` は先に返るため、その graph の再利用時には読み直さない。未 capture の window graph を作る時点で環境が有効なら `hipGraphGetNodes` と node type の走査を行い、node 総数・kernel node 数を記録する（`engine/src/core/verify.cpp:3254-3258,3395-3407`）。

probe は launch の結果を変更しない。HGL 経路では実際の launch error を通常どおり `verify: launch: <error>` として返し、layer が通知されない timeout も通常の `verify: timed out at layer ...` 経路で失敗する。probe 固有の終了コードや警告はない（`engine/src/core/verify.cpp:3926-3942,4023-4061,4156-4166`）。

## ログと測定値

すべて stderr に出力される。HIP graph capture 時の書式は次のとおり（`engine/src/core/verify.cpp:3395-3405`）。

```text
strata tdr-probe: the %d-token window graph has %zu nodes, %zu of them kernels
```

HGL launch timing のログは以下の3形式で、途中経過は launch が戻らない場合に到達した各 mark で出る（`engine/src/core/verify.cpp:3906-3934`）。

```text
strata tdr-probe: window %d T=%d pos=%lld: t=%.0f ms since start, %.0f MiB free, launching%s
strata tdr-probe: window %d T=%d: the launch call has not returned after %.0f ms; GPU rang %u, flags served %u A %u B %u
strata tdr-probe: window %d T=%d: launch call %s in %.2f ms; the GPU had rung %u layer(s) and the host served %u at the return
```

この probe の測定結果を記録した資料は調査対象ソースから確認できなかったため、性能値は記載しない。

## 根拠

- `engine/src/core/verify.cpp:336-339` — 共通の値判定。
- `engine/src/core/verify.cpp:3254-3258,3395-3407` — HIP の graph capture、cache 条件、node 数ログ。
- `engine/src/core/verify.cpp:345-347,3776-3819,3879-3948` — process 起点時刻、Metal 経路、run 時の cache・採番・launch 計測。
- `engine/src/core/verify.cpp:4-5,3895-3939` — HGL compile 条件と通常 launch との差。
- `engine/src/core/verify.cpp:4023-4061,4156-4166` — launch 不通知・timeout・launch error の通常失敗経路。
- `engine/src/core/arch_defaults.cpp:444-452` — gfx1151 の別 launch 環境変数の既定設定とログ。
- `engine/cmake/strata_gpu_engine.cmake:305-316` — GPU engine に `verify.cpp` を含める build 定義。
