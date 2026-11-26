# `STRATA_ADAPT_ASYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA 版 `strata generate` で `--adapt-async` が省略されたとき、セッション内の測定に基づいて非同期 adaptive tier を試す自動選択を許可するかを決める。値が 1 だから直ちに非同期 tier を ON にする設定ではない。環境値が 0 なら自動選択を止め、blocking tier を使う。明示的な `--adapt-async 0|1` がある場合は環境値より CLI が優先され、`--adapt-async 1` は従来どおり非同期 tier を要求する（`engine/src/program/generate.cpp:4061,11777-11794`、`engine/include/strata/core/adapt_async_default.hpp:42-60`）。

自動選択が候補になるのは CUDA build の `--serve` 経路だけである。HIP build では自動選択ゲートが false、SYCL 実装にはこの環境変数の読み取りも自動選択処理もない。明示的な `--adapt-async` の挙動は別経路であり、この環境変数では変更しない（`engine/src/program/generate.cpp:11777-11794`、`engine/sycl/src/program/generate.cpp:1-52,2054,7063-7082`）。

## 値と判定

`adapt_async_env()` が `std::getenv` で読み、未設定または空文字列なら `-1`（未設定扱い）、それ以外は `std::atoi` の戻り値を使う。文字列全体の検証やエラー報告はない。`atoi` が先頭の空白・符号・数字列を変換し、数字列の後ろは無視するため、たとえば `"1tail"` は 1、`"0tail"` は 0、数字で始まらない `"true"` や空白だけの値は 0 になる。大文字小文字の比較はしない。自動選択 helper が特別扱いするのは変換結果がちょうど 0 の場合だけで、正負を問わず 0 以外は自動選択を妨げない（`engine/include/strata/core/adapt_async_default.hpp:35-60`）。

| build / 条件 | unset（未設定または空文字） | 設定時に自動選択を許す値 | 自動選択を止める値 |
|---|---|---|---|
| CUDA、`--adapt-async` 省略 | 測定による選択の候補 | `atoi` 結果が 0 以外（例: `1`, `-1`, `1tail`） | `atoi` 結果が 0（例: `0`, `00`, `0tail`, `true`, 空白のみ） |
| HIP または SYCL、あるいは CLI を指定 | 環境変数による自動選択なし | 該当なし | 該当なし |

CLI の値は `std::atoi(...) != 0` で 0/1 に正規化される。CLI が指定されると `adapt_async_self_decides()` は環境値を見る前に自動選択を拒否するため、環境値が 0 でも `--adapt-async 1` を打ち消さない（`engine/src/program/generate.cpp:4061,11777-11794`、`engine/include/strata/core/adapt_async_default.hpp:42-45`）。

## 有効になる条件

自動選択が進むには、環境値が 0 以外または未設定で、かつ CLI が未指定であり、次の条件をすべて満たす必要がある。

- CUDA build で `--serve` を使用する。HIP build は `aa.cuda` が false になる。
- adaptive tier が有効（`--adapt-every` と `--adapt-swaps` がともに 0 より大きい）。
- expert arena を使い、全 expert が RAM arena から供給される。
- 単一 GPU で、layer split、`--pipeline-windows`、`--batch` slots、`--peer-device`、`--remote-expert-opt` を使わない。
- `STRATA_ADAPT_OVERLAP` の tier と同時に使わず、`STRATA_ADAPT_FETCH` が 1 または 2 の設定でない。

これらは `adapt_async_self_decides()` の判定である（`engine/include/strata/core/adapt_async_default.hpp:19-32,42-60`）。条件を満たさない場合、自動選択フラグは立たず blocking tier のまま進む。明示的な `--adapt-async 1` はこの自動選択とは別に判定され、たとえば `--serve`、有効な adaptive tier、resident RAM mode / `--resident-experts` / expert arena などが不足すると blocking tier に戻る（`engine/src/program/generate.cpp:11796-11812`）。

## 実行時の詳細

環境値は `generate.cpp` の serve 処理で、自動選択候補の条件を組み立てる時に一度読み取られる。`adapt_async_env()` 自体に static cache はないが、その結果はこのセッションの `o.adapt_async_self` に保存され、その後のリクエストで環境を読み直さない。通常のプロセス内環境変更がこの判定後に反映される経路はない（`engine/include/strata/core/adapt_async_default.hpp:35-39`、`engine/src/program/generate.cpp:11777-11794`）。

自動選択候補では blocking tier から始める。最初の 64 decode windows をウォームアップとして除外し、続く 64 windows の所要時間に対する adaptive tier の待ち時間比率を測る。待ち時間が 5% 以上なら非同期 tier を試し、試行開始後 4 windows を除外して 64 windows を測定する。非同期時の ms/token が blocking 時より約 2%を超えて悪化しなければそのセッションでは維持し、悪化が大きければ quiesce 後に blocking tier へ戻る。待ち時間比率が 5% 未満なら試行しない（`engine/include/strata/core/adapt_async_default.hpp:63-107`）。

arena 経路では非同期 round が expert cache への copy-in のみとなり、必要時に job thread を開始する。tier は decode windows の間に swap を進め、生成 token 自体をこの環境値で直接選ぶ処理はない（`engine/src/program/generate.cpp:15517-15531,15555-15567,15598-15616`）。

## ログと測定値

自動選択候補の arena 経路では起動時に blocking 状態を示す次の行を stderr に出す。環境値が 0 のときもこの行は同じで、自動選択を試さない専用の警告や終了はない。

```text
strata serve: adaptive tier: blocking, and the asynchronous tier is tried once the session shows the swaps hold the windows up (--adapt-async 0 or STRATA_ADAPT_ASYNC=0: never)
```

実際に試行する場合、切替時に「swaps held the windows up」、試行結果に応じて「asynchronous tier stays on」または「was slower ... back to the blocking tier for this session」を stderr に出す。明示的 CLI の適用条件不足では `strata generate: --adapt-async 1 is off (<理由>): the blocking adaptive tier` を出して blocking に戻す（`engine/src/program/generate.cpp:11770-11773,15601-15613,23165-23183`）。

## 根拠

- `engine/include/strata/core/adapt_async_default.hpp:35-60` — 環境値の取得・変換と自動選択ゲート。
- `engine/include/strata/core/adapt_async_default.hpp:63-107` — 測定・試行・維持または blocking へ戻す判定。
- `engine/src/program/generate.cpp:4061,11777-11794` — CLI 優先順位、CUDA build 判定、適用条件の入力。
- `engine/src/program/generate.cpp:15598-15616,23165-23183` — arena での自動 tier 初期化と切替ログ。
- `engine/sycl/src/program/generate.cpp:2054,7063-7082` — SYCL の CLI 経路と explicit async の条件。`STRATA_ADAPT_ASYNC` の読み取りはない。
