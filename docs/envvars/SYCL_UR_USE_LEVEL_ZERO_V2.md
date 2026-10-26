# `SYCL_UR_USE_LEVEL_ZERO_V2`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ランタイムがこの変数自体をどう解釈するかは対象外とし、Strata ソースが行う判定だけを記す。

## 役割

SYCL の Level Zero backend で、Strata が専用 copy-engine queue を作るかどうかに影響します。Strata はこの環境変数を使って専用 queue の作成を見送り、呼び出し元に通常の in-order queue を使わせます。SYCL ランタイムの adapter 選択や動作そのものを Strata が設定する処理ではありません。

## 値と判定

Strata は値を数値や真偽値として parse せず、`getenv()` の返す文字列の先頭文字だけを調べます。

| 環境変数の値 | Strata の処理 |
|---|---|
| 未設定 | 専用 queue 作成をこの変数では止めない |
| 空文字 | 先頭文字は `\0` のため、専用 queue 作成を止めない |
| 先頭文字が `0`（例: `0`, `0anything`） | 専用 queue 作成を見送り、`nullptr` を返す |
| その他（例: `1`, `false`, `true`, `2`） | 専用 queue 作成をこの変数では止めない |

空白、大文字小文字、文字列全体、数値としての妥当性は検査しません。値が未設定または先頭文字が `0` 以外でも、他の条件により専用 queue が作られない場合があります。

## 有効になる条件

この変数が専用 queue 作成を許しても、`make_copy_engine_queue()` が呼び出され、Level Zero API のヘッダーが利用可能なビルドであり、選択デバイスの SYCL backend が Level Zero であることが必要です。さらに、`STRATA_COPY_ENGINE` が先頭文字 `1` でなければ Battlemage 以外の GPU では専用 queue を作りません。Level Zero loader/API の関数が使えない、copy 専用 command queue group がない、または queue 作成に失敗した場合も作成されません。

`STRATA_COPY_ENGINE` の先頭文字が `0` なら、関数冒頭で専用 queue 作成を止めます。この判定は関数内の `static const bool` に一度だけ保存され、後から環境を書き換えても変わりません。

## 実行時の詳細

変数の読み取り箇所は `make_copy_engine_queue()` 内の1箇所です。デバイスごとの queue 初回要求時に読みます。同じ device は `dev_queues` に記録され、2回目以降の要求では保存済みの queue（作成失敗時は `nullptr`）を返すため、初回判定後の環境変更はその device には反映されません。別 device の初回要求では、その時点の値を判定します。

専用 queue が作られない場合、SYCL prefill の呼び出し元は通常の in-order queue を作成して `m.copy` に設定します。専用 queue 作成に成功した場合は、初回成功時に stderr へ `strata: copy engine: ...` のログを出します。例外が発生した場合は `strata: copy engine queue not available (%s): ordinary queue` を出して `nullptr` を返します。その他の早期 return は同箇所でログを出しません。

## 根拠

- `sycl/src/core/copy_queue.cpp:73-99`: `STRATA_COPY_ENGINE` と `SYCL_UR_USE_LEVEL_ZERO_V2` の判定。後者は先頭文字 `0` のときだけ専用 queue を無効化。
- `sycl/src/core/copy_queue.cpp:60-63,80-84`: mutex 保護されたデバイスごとの queue 記録と既存記録の再利用。
- `sycl/src/core/copy_queue.cpp:100-137`: loader/API、copy-only group、queue 作成、stderr のログと例外時 fallback。
- `sycl/src/prefill/prefill.cpp:1257-1263`: prefill が専用 queue を要求し、`nullptr` の場合に通常 queue を用意。
- `sycl/CMakeLists.txt:252-260`: `copy_queue.cpp` が SYCL engine library に含まれること。
- `sycl/include/strata/copy_queue.hpp:10-15`: 専用 queue の目的と通常 queue への fallback の説明。測定値は設計資料の記載として扱い、本調査では独自に再測定していない。
