# `STRATA_TEST_PAGEABLE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリや driver 自身が読む環境変数の動作は対象外。

## 役割

ページロック（pinned）ホストメモリを使う一部のアップロード／prefill 用バッファを意図的に避け、コードに用意された pageable メモリの経路を通す診断用フックです。CUDA/HIP 共通側の `PinnedRing`、CUDA/HIP 側と SYCL 側それぞれの `Prefill` に読み取り箇所があります。一般的な設定というより、pinned allocation が失敗した場合の fallback 経路を試す用途です。

## 値と判定

3か所の読み取りはいずれも `getenv()` の戻り値が非 null で、かつ先頭文字が `'1'` のときだけ有効とします。文字列全体の parse、数値変換、大文字小文字の処理はありません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（値は設定済みだが先頭文字は `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, その他先頭文字が `1` でない文字列 | 無効 |

各読み取り関数は結果を `static const bool` に保存します。判定はその関数が初めて呼ばれた時点で行われ、以後の環境変更では再評価されません。CUDA/HIP側には `PinnedRing::pageable_forced()` と `Prefill` 内の `force_pageable()` の別々のキャッシュがあり、SYCL側にも独立した `force_pageable()` があります。

根拠: `include/strata/core/pinned_ring.hpp:137-140`、`src/prefill/prefill.cpp:120-125`、`sycl/src/prefill/prefill.cpp:108-113`。

## 有効になる条件

該当する実行ファイルに各実装が組み込まれ、その関数が呼ばれることが条件です。値が有効でも、該当する `PinnedRing` の転送や `Prefill::init` の対象バッファ確保がなければ影響しません。コマンドライン引数や設定ファイルによる上書きはこの変数の読み取り箇所にはありません。

この変数が抑止するのは、コードが明示的に `force_pageable()`／`pageable_forced()` を確認する pinned allocation です。ホストメモリ割り当て全体を pageable にするものではありません。たとえば SYCL の `Stager::init` は `done_seq` と `src_seq` を環境変数判定なしで `sycl::malloc_host` から確保します（`sycl/src/prefill/prefill.cpp:388-393`）。

## 実行時の詳細

- `PinnedRing` は強制時に `acquire()` から pinned slot を返さず、`h2d()` は `direct()` に進みます。これは caller のメモリから `cudaMemcpyAsync` を行った後に stream を同期し、呼び出し元の source が戻り時に再利用できるようにします。`d2h_sync()` も pinned staging slot を使わず、caller の宛先へ転送して stream を同期します。`PinnedRing` は prefill の pageable upload と MTP の prompt records 転送で使われます。根拠: `include/strata/core/pinned_ring.hpp:36-43,48-50,95-113`、`src/prefill/prefill.cpp:661,862`、`include/strata/core/mtp.hpp:231`、`src/core/mtp.cpp:1216`。
- CUDA/HIP の `Prefill` では、Stager の各 blob 用 pinned allocation を省略し、代わりに `std::vector` の pageable buffer を使います。mapped group-copy buffer を確保しない場合は従来のコピー経路へ進み、PLE embedding buffer も pageable vector に切り替わります。`PinnedUpload` は pinned buffer を確保せず、upload 時に `cudaMemcpyAsync` の通常分岐へ進みます。根拠: `src/prefill/prefill.cpp:435-447,704-730,1138-1164`。
- SYCL の `Prefill` では Stager blob 用 `sycl::malloc_host` を省略して pageable vector を使います。mapped group-copy buffer は作らず、PLE embedding buffer は pageable vector を使います。根拠: `sycl/src/prefill/prefill.cpp:382-415,1021-1053,1056-1073`。

この変数自体によるログ出力は、確認した読み取り・分岐箇所にはありません。割り当て失敗時と同じ fallback を選ぶコードであり、変数の設定だけでエラーや終了を起こす処理は見当たりません。`PinnedRing` の転送では同期が明示されますが、`PinnedUpload::upload()` の pinned buffer がない分岐は `cudaMemcpyAsync` を呼び出して戻るため、両経路の同期挙動を一律には扱えません。

## 根拠

- 読み取りと `PinnedRing` の分岐: `include/strata/core/pinned_ring.hpp:36-43,48-50,95-113,137-140`。
- CUDA/HIP prefill の読み取り、Stager、PinnedUpload、group-copy、PLE fallback: `src/prefill/prefill.cpp:120-125,435-447,704-730,1138-1164`。
- SYCL prefill の読み取りと fallback: `sycl/src/prefill/prefill.cpp:108-113,382-415,1021-1073`。
- `docs/DETAILS.md` などの文書には pageable fallback に関する説明はありますが、`STRATA_TEST_PAGEABLE` の記載は見つかりませんでした。性能値はこの変数について資料で条件付き測定が確認できないため記載していません。
