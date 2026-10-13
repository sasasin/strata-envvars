# `STRATA_COMMIT_SYNC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

単一 GPU の speculative verification で、採用 token の状態を確定する commit graph の非同期実行を抑止します。設定すると、commit の stream/queue 完了をその場で待つ同期経路になります。commit の内容や採用 token 数を変える環境変数ではありません。

CUDA と SYCL の `Verifier::set_commit_async()` に同じ判定があります。通常の `generate` 経路は GPU 数から `set_commit_async(!multi_gpu)` を呼び、単一 GPU のときだけ非同期を候補にします（`src/program/generate.cpp:3345`, `sycl/src/program/generate.cpp:3197`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| unset | `on` が true のとき非同期を許可。通常の単一 GPU 経路では非同期 commit が有効 |
| 空文字を含む任意の設定値 | 設定値の内容は parse せず、環境変数が存在するため非同期を無効化 |
| 複数 GPU | `on` が false で渡されるため、変数が unset でも同期 |

したがって `STRATA_COMMIT_SYNC=0` も非同期を無効にします。`1` だけを有効・無効の値として比較したり、数値変換したりする処理はありません。判定式は `on && std::getenv("STRATA_COMMIT_SYNC") == nullptr` です。

根拠: `src/core/verify.cpp:2494-2495`, `sycl/src/core/verify.cpp:2614-2615`。

## 有効になる条件

環境変数 unset で非同期 commit が選ばれるのは、呼び出し元が `on=true` にした場合だけです。通常の `generate` ではこれは `!multi_gpu` に対応します。複数 GPU / layer split では `on=false` のため、変数の有無にかかわらず同期です。

さらに verifier が `next_` verifier を持つ場合、非同期フラグが true でも各 commit は同期されます。commit graph の後続処理と stream/queue の所有関係を保つための条件です。環境変数はこの条件を上書きしません。

## 実行時の詳細

`set_commit_async()` が呼ばれた時点で環境変数の存在を調べ、結果をプロセス内の `g_commit_async` に保存します。候補一覧にある他の環境変数 helper のような `static` 初回読み取りではなく、この関数の呼び出しごとに評価します。ただし通常の generate ソースでの呼び出し箇所は上記の初期化箇所です。設定後にプロセス環境を書き換えても、既に設定された `g_commit_async` は変わりません（再度 `set_commit_async()` が呼ばれれば再評価されます）。

非同期経路では commit graph を CUDA stream / SYCL queue に投入し、完了 event/barrier を記録して `commit_pending_` を立てて戻ります。次の window は同じ stream/queue 上で続けられ、drafter は別 stream で処理できます。host や別 stream から状態を読む前には `wait_commit()` が pending commit の完了を待ちます。同期経路では commit graph の直後に stream/queue を待ちます。CUDA では commit の起動・待機エラーを `err` に設定して呼び出し元へ返します。SYCL では同様のエラー値を `err` に設定する経路に加え、捕捉された `sycl::exception` は stderr に出力してプロセスを終了する処理があります。

根拠: CUDA `src/core/verify.cpp:2497-2520,2532-2539`; SYCL `sycl/src/core/verify.cpp:2617-2697,2713-2736`; 待機前に session を読む例 `src/program/generate.cpp:10207-10212`。

## 文書との照合・制限

`docs/DETAILS.md` にはこの環境変数の説明や commit 非同期化の測定値は見当たりません。`docs/INTEL.md:556-557` は upstream の `set_commit_async` / `wait_commit` に対応する SYCL 移植上の deferred commit について述べていますが、`STRATA_COMMIT_SYNC` の値判定や性能は説明していません。したがって、この文書では性能向上を主張しません。
