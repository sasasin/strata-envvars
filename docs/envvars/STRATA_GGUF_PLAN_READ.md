# `STRATA_GGUF_PLAN_READ`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

SYCL の prompt prefill で、GGUF から読む expert を stager の worker thread に遅延して読ませるか、通常の source 経由で先に取得するかを切り替える開発・調整用のフックです。設定すると `GgufExpertSource` 専用の stager job を作らなくなります。CUDA/HIP 共通の設定ではありません。

## 値と判定

| 環境変数 | 判定 |
|---|---|
| 未設定 | 無効。`GgufExpertSource` を dynamic_cast し、成功すれば GGUF 読み込みを stager job にする |
| 空文字 | 無効（設定ポインターは非 null だが `v[0]` は `\0`） |
| 先頭文字が `1` | 有効。例: `1`, `10`, `1anything` |
| その他 | 無効。例: `0`, `true`, ` 1` |

文字列全体、整数値、大文字小文字、後続文字は検査しません。値は関数内の `static const bool` に保存され、該当コードで最初に評価された後はプロセス内で再評価されません。実行中の環境変更は反映されません。

## 有効になる条件

実装は `sycl/src/prefill/prefill.cpp` にのみあります。`Prefill` の prompt chunk 処理に入り、この判定箇所が実行されることが必要です。値による読み込み経路の差が現れるのは、さらに `stream_all` が真で、expert source が `GgufExpertSource` の場合です。`stream_all` は source があり、ring が `STAGE`（8）より大きく、chunk が `stream_all_min()` 以上の場合に真になります。GGUF source は SYCL engine の `--stream-experts` 経路で設定され、native pack と `--native SHARD1` が必要です。

## 実行時の詳細

無効時は `m.src` を `GgufExpertSource` に dynamic_cast します。成功した場合、stream-all の expert 列挙時には各 expert の layer/expert 番号を含む `Stager::Job` を作り、worker thread が順番を claim した時点で `read_into()` を呼びます。読み込み先は stager の pinned host buffer（確保できない場合は pageable fallback）です。読み込み後、issuer がその buffer から device staging ring へコピーします。

有効時は cast を行わず `gsrc` が null になります。stream-all の列挙処理は `m.src->transient()` 等の通常分岐へ進み、該当する GGUF expert は `m.src->blob()` から得た pointer を使います。`GgufExpertSource::blob()` は GGUF の gate/up/down 部分を `pread()` で組み立てて ring buffer から返します。この場合、GGUF 専用 `read_into()` job は作られません。device へのコピーや ring の利用条件は同じ prefill の後続処理に従います。

無効時の stager `read_into()` が失敗すると stderr に `prefill: reading expert %d of layer %d from the GGUF failed` を出し、その buffer をゼロ埋めします。通常 `blob()` の読み込み失敗は null を返し、prefill 側が `prefill: expert source has no blob` として chunk を失敗させます。これらは各読み込み経路の実装上の違いであり、設定時に性能や出力がどう変わるかを示す測定資料は確認できませんでした。

## 根拠

- `sycl/src/prefill/prefill.cpp:2464` — stream-all の成立条件。
- `sycl/src/prefill/prefill.cpp:2517-2519` — 先頭文字判定と GGUF source の cast。
- `sycl/src/prefill/prefill.cpp:2528-2567` — stream-all の列挙と job 構築。
- `sycl/src/prefill/prefill.cpp:433-473` — worker thread が GGUF job を読み、失敗時にログ出力・ゼロ埋めする処理。
- `sycl/src/prefill/prefill.cpp:2573-2605` — stager buffer から device staging ring へコピーする処理。
- `sycl/src/core/gguf_expert_source.cpp:79-115,218-236` — `blob()` と `read_into()` の GGUF expert 読み込み。
- `sycl/include/strata/core/gguf_expert_source.hpp:34-43` — GGUF source の前提と `read_into()` の用途。
- `sycl/src/program/generate.cpp:4150-4167` — `--stream-experts` における `GgufExpertSource` の設定と前提。
- `docs/DETAILS.md:215-223,1539` — GGUF 直読みと stager の説明。`STRATA_GGUF_PLAN_READ` 自体の説明や比較測定はありません。
