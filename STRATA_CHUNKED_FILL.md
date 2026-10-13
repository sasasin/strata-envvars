# `STRATA_CHUNKED_FILL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL エンジンで大きな device memory 領域をゼロ初期化するとき、最大 256 MiB ずつ分割して計算カーネルでゼロにする経路を選びます。`STRATA_CHUNKED_FILL` を無効にすると、領域全体を一度の `queue.memset` でゼロにします。実装コメントによれば、Arc Pro B70（xe driver）で数 GiB の `queue.memset` が blitter engine 上で timeout する事象を避けるための経路です。コードには GPU や driver による有効・無効の自動切り替えはありません。

## 値と判定

値全体や数値としての parse はせず、`getenv()` の結果の先頭文字が `0` かだけを調べます。

| 値 | 選ばれる処理 |
|---|---|
| 未設定 | 分割ゼロ初期化（既定） |
| 空文字 | 分割ゼロ初期化 |
| 先頭文字が `0`（例: `0`, `0abc`） | 一度の `queue.memset` |
| その他（例: `1`, `true`, `false`, `abc`） | 分割ゼロ初期化 |

大文字小文字、空白、残りの文字列、数値の妥当性は判定しません。`plain` は関数内の `static const bool` なので、プロセス内で `big_fill_zero()` が最初に呼ばれた時に一度だけ評価されます。その後に環境変数を書き換えても選択は変わりません。

## 有効になる条件

この読み取りは `sycl/include/strata/sycl_queue.hpp` の `strata::big_fill_zero()` にあります。したがって Strata の SYCL エンジンでこの関数が呼ばれる場合にだけ影響します。CUDA/HIP の同名環境変数の読み取りは調査対象 HEAD では見つかりません。

SYCL エンジンでは、KV state のゼロ化、expert cache arena、verification arena、MTP の作業領域、expert-cache slot の初期化などが呼び出し箇所です。対象データや初期化の発生条件は各呼び出し元に従います。この変数は初期化方式を選び、初期化自体を要求するスイッチではありません。

## 実行時の詳細

`STRATA_CHUNKED_FILL` が未設定、空、または先頭文字が `0` 以外の場合、入力サイズを既定 256 MiB の chunk に分け、各 chunk を順番に処理して `q.wait()` します。chunk が 1 MiB 以上で、現在の書き込み先アドレスが 8-byte aligned なら、`uint64_t` 要素をゼロにする `parallel_for` を起動します。chunk の末尾に 1〜7 byte が残る場合はその部分を `q.memset` します。chunk が 1 MiB 未満、またはアドレスが 8-byte aligned でない場合は chunk 全体を `q.memset` します。

値の先頭文字が `0` の場合は、chunk 分割やカーネル起動を行わず `q.memset(p, 0, bytes)` を一度呼び、`q.wait()` します。helper 自体はログを出しません。呼び出し元では、たとえば expert cache 初期化が `big_fill_zero()` の失敗を検査し、失敗時にエラーを返します。

## 根拠

- 読み取り、値判定、既定 chunk、カーネル／memset の分岐と wait: `sycl/include/strata/sycl_queue.hpp:17-38`
- KV state の各 format に応じたゼロ化: `sycl/src/core/layer.cpp:983-1013`
- expert cache arena の初期化と失敗処理: `sycl/src/core/expert_cache.cpp:672-680`
- verification arena と MTP 作業領域の初期化: `sycl/src/core/verify.cpp:612-620`, `sycl/src/core/mtp.cpp:466-476`
- 自動 cache 調整時の slot 再初期化: `sycl/src/program/generate.cpp:4544-4546`
- SYCL エンジンの位置付け: `docs/INTEL.md:3-5,154-163`

`docs/DETAILS.md` と `docs/INTEL.md` を確認しました。`docs/DETAILS.md` にはこの変数の説明は見つからず、`docs/INTEL.md` は SYCL port の構成を説明しています。Arc Pro B70 の timeout の理由は実装コメントに記載されていますが、この調査では性能測定やハードウェア上での再現確認はしていません。
