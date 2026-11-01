# `STRATA_TEST_COPY_FAIL_AT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の会話 snapshot / checkpoint 共通コピー経路で、指定した順番のコピーを一度だけ `cudaErrorMemoryAllocation` として失敗させる診断用フックです。ヘッダーコメントは tests only としていますが、値を読むコードにテスト専用のビルド条件はなく、`copy_nonblocking()` が組み込まれた実行ファイルでは通常の実行時環境変数として評価されます。

## 値と判定

値は `std::atol()` で `long` に変換されます。文字列全体の妥当性は検査しません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | `0`。失敗注入なし |
| 空文字 | `atol("")` は `0`。失敗注入なし |
| 数値変換結果が 0 以下 | 注入なし |
| 正の数 `N` | プロセス内の `copy_nonblocking()` 呼び出しを数え、N 回目だけ失敗させる |
| 数値として読めない文字列 | `atol()` の変換結果は `0`。注入なし |

`atol()` のため、先頭空白や符号を含む数値は変換対象となり、数値の後ろにある文字は検査されません（例: `3junk` は `3`）。範囲外の数値に対する値はこの実装で検査・制限されません。失敗番号を超えた後のコピーは通常処理へ進みます。

## 有効になる条件

値の判定と失敗カウンターは CUDA の `conversation_detail::copy_nonblocking()` に実装されています。実際に失敗するには、そのプロセスで同関数を少なくとも N 回呼ぶ必要があります。snapshot の保存や会話 checkpoint の実行経路が主な利用箇所です。対象コードには OS・モデル・CLI 引数による追加条件や、テスト専用ビルド macro によるガードはありません。

## 実行時の詳細

`test_copy_fail_at()` の値は関数内 `static const long` に初回評価時の値が保存されます。したがって、最初の `copy_nonblocking()` 呼び出し後にプロセス環境を変更しても反映されません。値が正の場合、呼び出し側の `static std::atomic<long>` カウンターを増やし、現在値が N と一致した回だけ、stream 取得や `cudaMemcpyAsync()` の前に `cudaErrorMemoryAllocation` を返します。カウンターはこの処理中にリセットされず、注入は一回限りです。

この共通関数は checkpoint の running-state copy と snapshot の通常 / queued / stage / VRAM slot / direct K/V copy に使われます。そのため N は特定の1種類のデータだけを数える値ではなく、同一プロセスでこれらの経路が呼び出す共通関数の順番です。checkpoint copy は error に `conversation snapshot running-state copy: ...` を設定し、K/V copy は経路に応じて `conversation snapshot copy: ...`、`... slot copy: ...`、`... stage copy: ...`、`... direct copy: ...` を設定して失敗を返します。

失敗の外部観測は呼び出し元によって異なります。serve の会話 cache park では snapshot 保存が false を返し、park 処理はその snapshot を保存できません。checkpoint 保存では stderr に `strata serve: checkpoint save: ...` が出て、上位処理がコピー失敗として checkpoint を省略できる場合があります。session file 用 snapshot capture は失敗理由を session 保存拒否経路へ渡します。環境変数自体による専用ログはありません。

## 根拠

- `src/core/conversation_copy.hpp:117-122` — tests only というコメント、`std::atol()`、unset の既定値、および読み取り値の static cache。
- `src/core/conversation_copy.hpp:140-152` — 正の N に対する atomic カウント、N 回目の `cudaErrorMemoryAllocation`、および通常コピー処理との順序。
- `src/core/conversation_state.cpp:39-45` — checkpoint running-state copy が共通関数を呼び、失敗理由を返す処理。
- `src/core/conversation_snapshot.cpp:258-265,332-345,363-370,435-452` — K/V の通常、VRAM slot、stage、direct copy 経路とエラー伝播。
- `src/core/conversation_state.cpp:517-568,622-642` — snapshot save と session 用 snapshot sources が checkpoint の複製・保存を行う箇所。
- `src/program/generate.cpp:1915-1920,10717-10722,13749-13755` — checkpoint save の stderr ログ、会話 park の snapshot 失敗伝播、session capture の拒否経路。
- `docs/envvars/000_envvers.md:1553` — 候補一覧での掲載。`docs/DETAILS.md` にはこの変数の説明・測定値は見当たらず、上記の挙動は調査対象 commit の実装から確認したものです。
