# `STRATA_VERIFY_STEPPED`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

SYCL verifier の検証窓を、CPU 側の expert 処理を挟む区間に分けて実行します。区間の GPU 処理が完了してからホストが doorbell の内容を読み、CPU expert pool を実行し、次区間が待つ flag を立てます。これにより、実行中の kernel とホストが互いの mapped-memory store を読む必要がない構成になります。実装コメントは Arc A-series / DG2 向けの opt-in と説明しています。

この名前を読む箇所は `sycl/src/core/verify.cpp` です。CUDA/HIP側でこの名前を読む Strata 所有コードは見つかりませんでした。

## 値と判定

共通 helper `env_on()` は `getenv()` の値が存在し、空文字でなく、先頭文字が `0` でない場合に真を返します。文字列全体の比較や数値変換はしません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効 |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、`2`、`anything` | 有効（先頭が `0` 以外で空でないため） |

判定結果は翻訳単位の `const bool g_stepped` に初期化時に保存されます。起動後に環境を書き換えても再判定されません。

## 有効になる条件

- 機能の読み取りと実装は `sycl/` の verifier にあります。CUDA/HIPの verifier に同じ名前の読み取りはありません。
- expert が全て VRAM に常駐していない通常経路では、`STRATA_VERIFY_EAGER` が未設定で、窓サイズ `T` の区間 graph (`seg_[T]`) が作られている場合に segmented run になります。`STRATA_VERIFY_EAGER` が設定されると、通常経路では区間化されず、eager replay の経路になります。
- expert が全て VRAM に常駐している経路では、eager の設定にかかわらず `g_stepped` が真なら stepped all-resident 経路を使います。ただしテスト用 stall hook が対象窓で作動する場合は除外されます。
- segmented run は `--remote-expert-opt` をサポートせず、その組み合わせでは `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` をエラーとして返します。この拒否は通常の segmented run にあるため、all-resident 経路には同じチェックがありません。
- `STRATA_VERIFY_SPLIT` は区間分割方法を調整します。未設定なら split point 用 hook を有効にし、値の先頭が `0` のとき無効にします。`STRATA_VERIFY_PIPE` は split point で CPU pool と次区間を重ねる helper thread を制御し、先頭が `0` のとき無効、その他（未設定を含む）は有効です。

## 実行時の詳細

通常の segmented run では、`capture_segments()` が窓を command graph の複数区間として記録します。doorbell publish 後に区間を閉じ、各serve境界を記録します。既定では `STRATA_VERIFY_SPLIT` が有効なので、VRAM expert group の後にも split point が設けられます。`STRATA_VERIFY_NODES` が設定されている場合は、stderr に `strata verify: the %d-token window as %zu graph segments` を出します。

実行時は各区間を投入し、serve point で queue を待機します。期待した doorbell sequence に届いていなければ `verify (stepped): layer ... did not ring after its queue drained ...` で失敗します。届いていればCPU expert poolを実行し、DMAコピーを待ってflag Bと次のflagを立ててから次の区間へ進みます。`STRATA_VERIFY_PIPE` が有効で次区間が split point なら、poolをhelper threadで実行し、flag Aが立った段階で次区間を先に投入します。実行中のSYCL例外などは `verify (stepped): ...` 等のエラーに変換されます。

全expert常駐時は通常の区間serveがありません。必要な PLE 行を用意した後、graph起動前にhost flagを立て、windowのgraphを実行します。この経路では窓内のレイヤごとのCPU serveを行いません。

このモードでは、window用のhost allocationは通常の `sycl::malloc_host` になります。`STRATA_VERIFY_HOST_UNCACHED` を有効値にした場合はuncached host allocationを維持します。stepped無効時は従来どおりuncached allocationを使います。これはwindowのmapped bufferとdoorbell payload storeの扱いにも関係します。

## 根拠

- `sycl/src/core/verify.cpp:92-103` — `env_on()` の値判定、`g_stepped` の初期化。
- `sycl/src/core/verify.cpp:218-239` — stepped 時のhost allocation選択と `STRATA_VERIFY_HOST_UNCACHED` の例外。
- `sycl/src/core/verify.cpp:1679-1719,1726-1734` — windowの区間記録、`STRATA_VERIFY_SPLIT`、EAGERとの関係、任意のsegment数ログ。
- `sycl/src/core/verify.cpp:2039-2057,2064-2135,2137-2154` — 通常/全expert常駐の経路選択、CPU pool・flag処理、remote expert optのエラー、eager fallback。
- `sycl/src/core/verify.cpp:2186-2200` — stepped経路で通常のhost per-layer serveを省略する箇所。
- `sycl/include/strata/core/verify.hpp:358-369` — モードの設計説明、step hook、segment graphのメンバー。

`docs/DETAILS.md` には `STRATA_VERIFY_STEPPED` の説明は見つかりませんでした。速度・正確性の測定値はこの文書では主張しません。
