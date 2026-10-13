# `STRATA_STAGER_SLEEP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象は Strata 所有ソース。外部ランタイム内部の待機実装は対象外。

## 役割

プロンプト prefill の Stager worker が、ステージング用バッファの再利用前に行う DMA 完了待ちを、sleep 系にするか yield しながら待つか選びます。値は Stager 初期化時に DMA 完了イベントの作成方法を選び、標準ライブラリが `std::atomic::wait` に対応するビルドでは、DMA 発行数を待つ worker 側の待機方法にも使われます。Stager を使わない処理全般の CPU 待機方式を切り替える変数ではありません。

## 値と判定

`stager_sleep()` は `std::getenv()` で値を取得し、関数内の `static const bool` に初回の結果を保存します。空文字は unset と同じ既定値です。空でない値は先頭1文字だけを検査し、`'0'` なら false、それ以外なら true です。文字列全体の数値 parse、大文字小文字変換、空白除去はしません。

| 設定値 | Linux など `_WIN32` 以外 | Windows |
|---|---:|---:|
| unset または空文字 | true | false |
| 空でない値の先頭文字が `0` | false | false |
| 空でない値の先頭文字が `0` 以外 | true | true |

たとえば `0`, `0anything` は false、`1`, `2`, `true`, `false`, ` ` は true です。Windows では最後の例を含め、unset/空文字以外は同じ先頭文字規則になります（先頭が `0` なら false）。

## 有効になる条件

- `src/prefill/prefill.cpp` の Stager が初期化される実行経路で参照されます。`Prefill::init` は Stager を必要に応じて作成し、`Stager::init` が ring buffer ごとの `dma_done` イベントを作ります。
- Stager は、プロンプトの expert をステージングする際に、入力 blob が pinned でない場合などにホストコピー用 worker として利用されます。全 expert が pinned なら Stager worker によるコピー待ちは発生しませんが、Stager の初期化時にイベント作成の設定値は参照されます。
- Windows の既定は yield 側、Windows 以外の既定は sleep 側です。明示的な非空値でこの既定を上書きできます。
- worker の `issued` カウンタに対する `std::atomic::wait` は、`__cpp_lib_atomic_wait` が定義される標準ライブラリでだけコンパイルされます。未対応のビルドでは `STRATA_STAGER_SLEEP` が true でも、このカウンタ待ちは `std::this_thread::yield()` のループです。一方、イベントは引き続き `cudaEventBlockingSync` 付きで作成されます。

## 実行時の詳細

`Stager::init` は各 ring slot の `dma_done` を作成します。sleep 側なら `cudaEventDisableTiming | cudaEventBlockingSync`、yield 側なら `cudaEventDisableTiming` を渡します。worker は各 slot の再利用前に `cudaEventSynchronize(dma_done[...])` を呼びます。また、ring の先行 DMA が発行されるのを待つ箇所では、atomic wait 対応ビルドかつ sleep 側なら `issued.wait()` を使い、そうでなければ `issued` を読みながら `yield()` します。launch 側は DMA を copy stream に積んで対応 event を記録し、`issued` を更新して worker に通知します。

値は `stager_sleep()` の初回呼び出しで評価され、その後の呼び出しではキャッシュ値を返します。通常は Stager 初期化時のイベント作成で初回評価されるため、その後プロセス内で環境を変更しても判定は変わりません。

この設定の対象外である待機もあります。worker の新しい世代を待つ `condition_variable`、job のコピー完了を待つ `ready` のループ、Stager の `finish()` における active worker の完了待ちは、いずれも `STRATA_STAGER_SLEEP` で分岐しません。

## 文書との照合

`docs/DETAILS.md` は Linux では sleep、Windows では spin を既定とし、`STRATA_STAGER_SLEEP=1` で Windows も sleep、`=0` で Linux も spin と記載しています。ソースの既定分岐と先頭文字判定に一致します。同資料は Linux の DGX Spark のプロンプト読み込み例、Windows RTX 5070 の Q2_0 8K prompt の差、Windows の Ryzen 9 7940HS + RTX 4070 で CPU 使用率が下がる代わりに読み込みが遅くなった例も記載しています。これらは記載された機材・条件での資料上の測定値で、一般的な性能保証ではありません。

## 根拠

- `src/prefill/prefill.cpp:125-140` — 既定値、先頭文字判定、static cache。
- `src/prefill/prefill.cpp:434-450` — Stager ring ごとの DMA event 作成と flag 選択。
- `src/prefill/prefill.cpp:472-505` — worker の発行数待ち、event 同期、buffer copy。
- `src/prefill/prefill.cpp:536-572` — job 発行、event 記録、ready/finish 待ち。
- `src/prefill/prefill.cpp:1091-1128` — `Prefill::init` における Stager 初期化。
- `src/prefill/prefill.cpp:2334-2366, 3642-3684` — unpinned/transient expert のステージング利用経路。
- `src/prefill/prefill.cpp:3-6` — atomic wait 対応の compile-time 判定。
- `docs/DETAILS.md:1537` — OS ごとの既定と資料記載の測定例。
