# `STRATA_ADAPT_FETCH_VERIFY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の適応 fetch が有効な実行で、PCIe share から VRAM expert cache に admission した slot を記録し、後続の生成窓で slot の内容を host 側の expert blob と照合する診断スイッチ。fetch の選択・admission 自体を有効化する変数ではなく、生成 token や routing を変える処理も行わない。admission を有効にするのは `STRATA_ADAPT_FETCH` である（`engine/src/program/generate.cpp:24580-24603`、`engine/src/core/expert_source.cpp:5663-5676`）。

## 値と判定

`strata generate` の初期化時に `std::getenv("STRATA_ADAPT_FETCH_VERIFY") != nullptr` を一度評価し、その真偽を `drive.d.fetch_log_on` に保存する。値の文字列は parse しない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| fetch が利用可能な `strata generate` 経路 | ログ記録なし | 空文字、`0`、`false`、`1`、`0anything`、空白を含む値など、環境変数が存在する値すべて | なし（設定有無だけを見る） |
| fetch が無効または利用不能な経路 | フラグは初期値 `false` のまま | 該当なし | 該当なし |

大文字小文字、空白、数値としての妥当性は判定しない。`STRATA_ADAPT_FETCH_VERIFY=0` も設定済みなので診断を有効にする。未設定だけが無効である。`ExpertDispatch` の初期値は `false`（`engine/include/strata/core/expert_source.hpp:691-692`）、設定有無の読み取りは `engine/src/program/generate.cpp:24598`。

## 有効になる条件

- `strata generate` の経路で `STRATA_ADAPT_FETCH` の値が 0 より大きいこと。`adapt_fetch()` はこの別変数を `atoi` で読み、0〜2 に clamp する。未設定時は 0 だが、CUDA 起動時に GPU 条件に応じて `STRATA_ADAPT_FETCH` の既定値が環境へ設定される場合がある（`engine/src/program/generate.cpp:2345-2347,4438-4449`; `engine/src/core/nv_defaults.cpp:21-26,228-238`）。
- 適応 tier の使用量カウンターが有効であること（`--adapt-every` と `--adapt-swaps` がともに正数。`engine/src/program/generate.cpp:24570,24580-24592`）。
- residency table と VRAM expert cache slot があり、`--spec-split`、layer split、peer tier、helper GPU の経路でないこと。さらに PCIe mode は `dma` / `direct` ではなく、GPU plan と PCIe share があり、resident RAM mode ではないこと（`engine/src/program/generate.cpp:24571-24585`）。実際の dispatch でも PCIe mode 2、`dst2`、peer/helper/file tier なし、正の PCIe share、および対象 layer の PCIe source を要求する（`engine/src/core/expert_source.cpp:5271-5275`）。
- これらを満たしても、窓で PCIe miss が発生し admission 条件を通らなければ記録対象はない。候補 expert の routing count、in-flight 状態、resident victim との比較は `engine/src/core/expert_source.cpp:5640-5676` による。
- `strata serve` にはこの変数の読み取りがない。serve 側は `fetch_admit` を設定する箇所があるが（`engine/src/program/generate.cpp:15067-15089`）、`fetch_log_on` を設定しないため、この変数による read-back 診断は有効にならない。

## 実行時の詳細

変数は初期化時に一度読み、結果を `ExpertDispatch::fetch_log_on` に保持する。リクエストごと・生成窓ごとの再読込や static cache はない。値が設定されていても、適応 fetch の初期化条件を満たさない場合は読み取り箇所に到達せず、ログ記録は初期値のままである（`engine/src/program/generate.cpp:24580-24598`）。

実際の admission が成立すると、dispatch は `(layer * n_expert + expert, slot)` を `fetch_log` に追加する（`engine/src/core/expert_source.cpp:5663-5676`）。次の生成窓の開始時に GPU を同期し、まだ同じ expert がその slot に resident なら `ExpertCache::verify_slot` で slot の blob を host 側の blob と比較する。既に別 slot へ追い出されていれば照合をスキップする（`engine/src/program/generate.cpp:25102-25120`; `engine/src/core/expert_cache.cpp:968-995`）。

比較は device から host への copy 後、`memcmp` で行う。読み取り・比較に失敗した場合もこの経路は `drive.d.failed` を立てず、生成ループを終了させない。したがってこの変数は観測用であり、expert cache の修復や fallback を行わない（`engine/src/program/generate.cpp:25104-25124`; `engine/src/core/expert_cache.cpp:968-995`）。

## ログと測定値

差異または `verify_slot` のエラーがあれば stderr に `strata: FETCH VERIFY layer %lld expert %lld slot %d: %s` を出す。検査件数の累積値が `(checked & 1023) < 64` のときは `strata: fetch verify: %lld admitted slots read back, %lld differ` も出す（`engine/src/program/generate.cpp:25104-25123`）。`checked` は記録された admission ごとに増えるため、追い出し済みで実際の照合を省いた slot も件数に含まれる。`cudaDeviceSynchronize()` の戻り値はこの箇所では検査されず、個別の D2H copy / byte 比較の失敗は `verify_slot` のエラー文字列として報告される（`engine/src/program/generate.cpp:25106-25117`; `engine/src/core/expert_cache.cpp:968-994`）。

`docs/DETAILS.md:1262` は `STRATA_ADAPT_FETCH_VERIFY=1` を `strata generate` で各 admission slot を read-back する例として記載する。実装上は `=1` に限らず、環境変数が存在すれば有効である。同資料の性能値は `STRATA_ADAPT_FETCH` の動作評価であり、この診断変数単独の測定値ではないため、ここでは転記しない。

## 根拠

- `engine/src/program/generate.cpp:24580-24603` — 適応 fetch の利用条件と診断フラグの読み取り。
- `engine/src/program/generate.cpp:25102-25124` — 記録 slot の read-back、ログ、検査件数。
- `engine/src/core/expert_source.cpp:5271-5275,5663-5676` — dispatch が fetch 可能な条件と admission 記録。
- `engine/include/strata/core/expert_source.hpp:691-692` — 診断フラグと記録 vector の初期値。
- `engine/src/core/expert_cache.cpp:968-995` — slot のコピーと host blob の比較、失敗理由。
- `engine/src/program/generate.cpp:15067-15089` — serve 側の fetch 初期化。ここでは read-back フラグを設定しない。
- `engine/src/program/generate.cpp:2345-2347,4438-4449`; `engine/src/core/nv_defaults.cpp:21-26,228-238` — `STRATA_ADAPT_FETCH` の値と CUDA 起動時の既定値設定。
- `docs/DETAILS.md:1262` — `strata generate` における診断の記載との照合。
