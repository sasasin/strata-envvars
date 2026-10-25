# `STRATA_REFILL_BLOCKING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

prefill 用に一時的に借りた expert cache slot を、prefill 後に元の expert データで埋め戻すときのコピー方法を切り替えます。設定時は slot ごとに blocking の `fill_slot_blocking()`、未設定時は queued の `fill_slot_queued()` を呼びます。対象は `src/program/generate.cpp` と `sycl/src/program/generate.cpp` の batched prefill の refill 経路です。通常の expert load や remote expert の初期ロードにはこの環境変数の分岐はありません。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` だけで判定します。空文字、`0`、`false` を含め、環境変数が存在すれば有効です。未設定なら無効です。

| 状態 | 判定 | 選ばれる処理 |
|---|---|---|
| 未設定 | false | `fill_slot_queued()` |
| 任意の設定値（空文字を含む） | true | `fill_slot_blocking()` |

判定結果は `refill_blocking()` 内の function-local `static const bool` に初回呼び出し時に保存されます。その後プロセス内で環境を書き換えても再評価されません。子プロセスの起動や環境継承をこのコードが行う箇所はありません。

根拠: `src/program/generate.cpp:244-247`, `sycl/src/program/generate.cpp:286-289`。

## 有効になる条件

この変数が影響するのは、batched prefill の実行後に返却すべき lent slot がある場合だけです。借用 slot が空なら refill loop 自体がなく、設定しても作用しません。複数 stage の layer split でも同じ分岐を使い、未設定かつ `STRATA_REFILL_SERIAL` が未設定の場合は各 stage のコピーを発行してから待ちます。設定時は `refill_issue()` の各 slot コピーで待つため、stage ごとの発行を他 stage と重ねる効果も失われます。`STRATA_REFILL_SERIAL` は refill stage の順序に関係する別変数です。

根拠: `src/program/generate.cpp:10838-10886`, `sycl/src/program/generate.cpp:10082-10132`。

## 実行時の詳細

CUDA/HIP 実装では blocking 側は `cudaMemcpy` を使い、slot ごとにコピー完了を待ってから次の slot に進みます。未設定側は default stream への `cudaMemcpyAsync` を順に発行し、loop 後の `sync_queued()` で待ちます。したがって変数が主に変えるのは複数 slot 間のコピー発行と完了待ちの配置です。HIP の blocking 実装では staging buffer へ host copy してから device へコピーし、buffer のサイズ不足やコピー失敗は refill 失敗になります。

SYCL 実装では `fill_slot_queued()` も queue の `memcpy(...).wait()` を呼びます。よって、SYCL では名前に反して未設定側も各 slot ごとに wait し、両分岐とも loop 後に queue 全体の `sync_queued()` を実行します。この実装では変数による slot ごとの同期タイミングの差はありません。

refill が失敗すると呼び出し元はエラーを stderr に出して処理を失敗させます。通常の batched path では成功時に `strata generate: %zu lent slots refilled in %.1f ms` を stderr に出します。trace が有効な multi-stage path では `strata trace: refilled ...` も出ます。処理時間を短縮・保証する測定値は本調査では確認していません。

根拠: `src/core/expert_cache.cpp:692-746`, `sycl/src/core/expert_cache.cpp:866-985`, `src/program/generate.cpp:10838-10866,12639-12665`, `sycl/src/program/generate.cpp:10082-10112,11762-11795`。

## 文書との照合

`docs/DETAILS.md` および他の `docs` 内 Markdown に `STRATA_REFILL_BLOCKING` の説明は見つかりませんでした。このため、上記は実装箇所と `ExpertCache` のコピー関数から確認できる範囲に限ります。
