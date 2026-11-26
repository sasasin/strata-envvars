# `STRATA_STATE_HASH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--serve` のリクエスト処理後に、セッション状態の診断用 fingerprint を計算してログへ出すスイッチ。CUDA/HIP 実装と SYCL 実装にそれぞれ同じ設定有無判定がある。状態を書き換える処理ではなく、デバイス処理の同期と状態メモリの読み取りを行い、`STATE_HASH` を stderr に出力する（`engine/src/program/generate.cpp:23432-23438,23529-23538`、`engine/sycl/src/program/generate.cpp:12983-12991,13096-13105`）。

設計資料 `docs/SPLIT_SERVE.md:123-126` もこれを状態 fingerprint として説明し、prefill と restore 後の decode の照合結果を記載している。資料の「whole session」という説明に対し、実装は下記の項目別 hash を出力する診断処理であり、ここでは資料記載の照合試験を再実行していない。

## 値と判定

値の文字列や数値は parse せず、`std::getenv(...) != nullptr` で設定されているかだけを判定する。したがって未設定なら無効、設定されていれば空文字・`0`・`false`・`1` など値に関係なく有効。大文字小文字、空白、数値としての妥当性、範囲、境界値の検査はない（`engine/src/program/generate.cpp:23432`、`engine/sycl/src/program/generate.cpp:12983`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP および SYCL の `--serve` リクエスト処理 | `state_hash == false` | 空文字、`0`、`false`、`1` を含む、環境変数が存在する状態 | 変数が存在しない状態のみ |

## 有効になる条件

- 該当 backend のエンジンを使い、サーバーのリクエスト処理まで到達すること。読み取り箇所は CUDA/HIP と SYCL の `generate.cpp` にある（上記各行）。
- リクエストがキャンセルされておらず、`o.prompt_cache > 0` であること。この条件を満たさない場合は fingerprint 処理を通らない（`engine/src/program/generate.cpp:23433`、`engine/sycl/src/program/generate.cpp:12984`）。
- GDN のレイヤー別短縮 hash を追加出力するには、別変数 `STRATA_STATE_HASH_GDN` も設定され、かつ `ss.gdn_alloc > 0` であること。これは本変数による全体 fingerprint 処理の内側にある（`engine/src/program/generate.cpp:23470-23478`、`engine/sycl/src/program/generate.cpp:13037-13045`）。

## 実行時の詳細

関数内 `static const bool` として、リクエスト処理箇所へ初めて到達したときに設定有無を一度だけ読み取る。以降のリクエストでは同じ値を使うため、プロセス稼働中に環境を変更しても再評価されない（`engine/src/program/generate.cpp:23432-23433`、`engine/sycl/src/program/generate.cpp:12983-12984`）。

有効なリクエストではまずデバイス処理の完了を待ち、その後 64 KiB の作業バッファを使って状態データを読み、FNV-1a で hash する。出力はセッション長 `L`、GDN state、PLE 履歴、QSA の index tail / pooled 行 / KV、KV の有効範囲外の stale cells、dead 行、pooled 全行、MTP を使用する場合の draft K/V、`ple_prev` を項目別に示す。CUDA/HIP 側では QSA の各 session-owned state を走査し、SYCL 側も同じ構成を出力する（`engine/src/program/generate.cpp:23440-23468,23480-23527`、`engine/sycl/src/program/generate.cpp:12993-13035,13047-13094`）。

処理は状態をコピーして hash する診断経路であり、生成やセッション状態を更新するコードはこの分岐内にない。キャンセルされたリクエストと prompt cache 無効時には hash しない。読み取り範囲や項目は実装上の状態構成に依存するため、この出力だけから全ての内部状態を検査したとは断定できない。

## ログと測定値

成功時は stderr に次の形式で出力する（`engine/src/program/generate.cpp:23533-23538`、`engine/sycl/src/program/generate.cpp:13100-13105`）。

```text
strata serve: STATE_HASH L=... gdn=... ple=... tail=... pooled=... kv=... mtp=... stale=... dead=... pooled_full=... ple_prev=...,...
```

デバイス同期に失敗すると stdout に `ERR synchronizing state fingerprint` を出し、`return 1` で処理を抜ける。状態読み取り中に失敗した場合は `ERR reading state fingerprint` を stdout に出し、同じく `return 1` する（`engine/src/program/generate.cpp:23436-23438,23529-23531`、`engine/sycl/src/program/generate.cpp:12987-12991,13096-13098`）。SYCL のコピー時に `sycl::exception` が投げられた場合は `what()` と `Exception caught at file:` / `line:` を stderr に出して `exit(1)` する（`engine/sycl/src/program/generate.cpp:12997-13022`）。測定値は該当なし。

## 根拠

- `engine/src/program/generate.cpp:23432-23538` — CUDA/HIP 側の設定有無判定、条件、計算、出力、失敗経路。
- `engine/sycl/src/program/generate.cpp:12983-13105` — SYCL 側の対応実装。
- `engine/include/strata/core/mtp.hpp:110`、`engine/sycl/include/strata/core/mtp.hpp:76` — `--serve` の `STRATA_STATE_HASH` が draft layer の K/V を hash 対象とする旨の注記。
