# `STRATA_RSS_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`rss_probe()` が呼ばれた時点で `/proc/self/status` の `RssFile` 行を読み、`strata rss:` の診断行を stderr に出すためのスイッチです。CUDA/HIP 系と SYCL 系の `engine/.../program/generate.cpp` に同じ実装があります。値は設定有無だけに使われ、モデル処理、arena の release、prefetch の条件や内容はこの変数では変わりません（`engine/src/program/generate.cpp:659-672,11022-11045`、`engine/sycl/src/program/generate.cpp:303-316,6505-6528`）。

## 値と判定

両 backend とも `std::getenv("STRATA_RSS_TRACE") != nullptr` だけで判定します。未設定なら無効、環境に存在すれば値の文字列を調べず有効です。したがって空文字、`0`、`1`、`true`、`false`、`0anything` のいずれも有効です。数値変換、文字列比較、大文字小文字変換、空白除去、値域検査、無効値警告はありません（`engine/src/program/generate.cpp:660-662`、`engine/sycl/src/program/generate.cpp:304-306`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP 系 | 無効 | 空文字を含む任意の値 | なし（設定済みなら有効） |
| SYCL 系 | 無効 | 空文字を含む任意の値 | なし（設定済みなら有効） |

CPU-only build にはこの `rss_probe()` 実装がありません。

## 有効になる条件

- CUDA/HIP 系または SYCL 系の `generate.cpp` を含むエンジンであること。SYCL は別 backend のビルド経路です（`engine/CMakeLists.txt:20-32`）。
- `rss_probe()` の呼び出し地点まで実行が到達すること。arena release 前後と prefetch hints 後の3回は `graph_hits && !o.no_capture && !o.no_token_graph && layer_dump == nullptr && half_dump == nullptr` の経路内です（CUDA/HIP: `engine/src/program/generate.cpp:10997-11000,11022-11045`; SYCL: `engine/sycl/src/program/generate.cpp:6483-6485,6505-6528`）。prompt path の初期化後にも呼ばれます（CUDA/HIP: `engine/src/program/generate.cpp:12995`; SYCL: `engine/sycl/src/program/generate.cpp:7478`）。
- `serving` の記録は、起動後の VRAM 空き量が `free_mib >= 256` の分岐でのみ呼ばれます。低い場合の警告・案内分岐では呼ばれません（CUDA/HIP: `engine/src/program/generate.cpp:16089-16120`; SYCL: `engine/sycl/src/program/generate.cpp:9480-9494`）。
- 実装は `/proc/self/status` を開こうとします。ファイルを開けない環境（たとえば `/proc` を提供しない OS や実行環境）では、設定値があっても `rss_probe()` はログなしで戻ります（CUDA/HIP: `engine/src/program/generate.cpp:663-664`; SYCL: `engine/sycl/src/program/generate.cpp:307-308`）。
- CLI 引数、モデル形式、サーバー設定、別の環境変数による値の上書きはありません。呼び出し条件を満たさない実行ではこの変数は観測可能な効果を持ちません。

## 実行時の詳細

設定有無は `rss_probe()` 内の関数ローカル `static const bool` に保存され、プロセス内で最初にこの関数が呼ばれた時に一度だけ評価されます。その後の環境変更は反映されません。初回呼び出しより前に環境が変更されていた場合は、その時点の状態で評価されます。各呼び出しでは有効時に `/proc/self/status` を開き、先頭から `RssFile:` で始まる行を探し、続く数値を `std::atoll` で kB として読みます。arena の release 前後や prompt path 設定後など、呼び出し地点ごとに同じ読み取りを行います（CUDA/HIP: `engine/src/program/generate.cpp:660-670`; SYCL: `engine/sycl/src/program/generate.cpp:304-314`）。

ファイルを開けなければその呼び出しは何も出力せず終了します。ファイルは開けたが `RssFile:` 行がなければ初期値 `-1` のまま GiB 換算され、通常の出力処理へ進みます。arena 操作の成否や後続処理をこの probe の読み取り結果で分岐させるコードはありません（CUDA/HIP: `engine/src/program/generate.cpp:663-672`; SYCL: `engine/sycl/src/program/generate.cpp:307-316`）。

## ログと測定値

`/proc/self/status` を開けた場合、stderr に次の形式で出力し、直後に flush します（CUDA/HIP: `engine/src/program/generate.cpp:670-671`; SYCL: `engine/sycl/src/program/generate.cpp:314-315`）。

```text
strata rss: <呼び出し地点>: RssFile <GiBを小数点以下2桁で表示> GiB
```

呼び出し地点の文字列は `before the release`、`after the release`、`after the prefetch hints`、`the prompt path set up`、`serving` です。Strata の測定条件付き性能値はこの変数の実装箇所にありません。このログは `RssFile` の観測値であり、変数を設定したこと自体によるメモリ量や性能の変化を示すものではありません。

## 根拠

- 値の読み取り、static cache、`/proc/self/status` の走査と出力: `engine/src/program/generate.cpp:659-672`、`engine/sycl/src/program/generate.cpp:303-316`。
- arena release/prefetch 経路: `engine/src/program/generate.cpp:10997-11045`、`engine/sycl/src/program/generate.cpp:6483-6528`。
- prompt path と serving の呼び出し: `engine/src/program/generate.cpp:12995,16089-16120`、`engine/sycl/src/program/generate.cpp:7478,9480-9494`。
- SYCL が別 backend として選択される build 経路: `engine/CMakeLists.txt:20-32`。
