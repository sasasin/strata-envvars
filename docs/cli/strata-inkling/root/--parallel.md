# `strata-inkling` `--parallel`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--parallel` |
| 別名 | `--batch`、`--slots` |
| 値 | 整数。受理後に 1〜64 へ補正 |

## 役割

同時に扱うリクエスト slot の数を指定する。serve では同時に実行できるリクエスト数、bench と batch-check では処理する slot 数を決める。既定値は 1。

## 使い方

```sh
strata-inkling --serve --native ./model.strata --parallel 8
strata-inkling --bench --native ./model.strata --parallel 8
```

`--batch` と `--slots` も同じ値を設定する別名である。

## 値と既定値

値は `atoi` で整数へ変換され、その後 `max(1, min(64, 値))` が設定される。したがって 0 や負数は 1、64 を超える値は 64 になる。整数として変換できない文字列も `atoi` の結果 0 となるため 1 に補正され、厳密な数値検証エラーにはならない。値が省略された場合は `missing value after --parallel`（別名の場合は指定した表記）を標準エラーに出して終了コード 2 で終了する。複数回指定した場合は引数走査中に後の値で上書きされる。既定値 1 は `BackendOpts::parallel` の初期値である（`engine/src/inkling2/ink_main.cpp:845-849,877-878`; `engine/src/inkling2/ink_backend.h:17-20`）。

## 実行時の動作

- `--serve` では、補正済みの値を最大 slot 数 `P` として使い、backend に `0..P-1` の slot を割り当てる。空き slot がなければ `GENERATE` 要求に `ERR busy: all ... parallel slots active` を返し、指定 slot が範囲外なら範囲エラーを返す（`engine/src/inkling2/ink_serve.h:494-498,541-548,799-810`）。
- `--bench` では `P` 個の slot を割り当て、合成 prompt を各 slot に流して同時処理を計測する。結果には `parallel=P` が表示される（`engine/src/inkling2/ink_main.cpp:131-165,167-184,227-250`）。
- `--batch-check N` では比較対象の slot 数 `K` として使う。K 個の slot を割り当て、同一リクエストの単独実行と K slot バッチ実行の logits を比較する（`engine/src/inkling2/ink_main.cpp:450-463,496-538`）。
- 自動 KV dtype が有効なまま値が 16 以上の場合、KV dtype の既定選択を FP8_E4M3 にする。`--kv` / `--kv-dtype` で明示形式を指定すると自動選択は無効になる（`engine/src/inkling2/ink_main.cpp:882-889,1021-1024`; 初期状態は `engine/src/inkling2/ink_backend.h:33-35`）。

値は `BackendOpts` に保持され、slot pool の上限 64 として backend に渡る（`engine/src/inkling2/ink_batch.h:11-14`; `engine/src/inkling2/ink_backend.h:17-20,82-86`）。slot の KV 領域はページ単位で確保される設計だが、slot 数を増やすと同時に保持できるリクエストが増え、使用時のメモリ需要も増える（`engine/src/inkling2/ink_batch.h:13-14`; `engine/src/inkling2/ink_serve.h:541-548`）。

## 適用条件と副作用

この parser は mode ごとにオプションの適用を制限せず、値を共通設定へ格納する。ただし通常の単発生成は slot 0 だけを割り当てるため、`--parallel` による複数リクエスト処理はしない（`engine/src/inkling2/ink_main.cpp:1097-1101`）。`--spec-check` は内部で `parallel=1` に固定する（`engine/src/inkling2/ink_main.cpp:599-611`）。これらの mode でも 16 以上なら、前述の自動 KV dtype 選択には影響する（`engine/src/inkling2/ink_main.cpp:1021-1024`）。

serve / bench / batch-check は複数 slot を backend に割り当てるため、初期化または slot 割り当てに失敗することがある。各経路は失敗内容を標準エラーまたは serve のプロトコル出力に出し、終了コード 1 を返す（`engine/src/inkling2/ink_main.cpp:143-165,454-463,1086-1094`; `engine/src/inkling2/ink_serve.h:541-548`）。GPU ごとの実際のメモリ消費量や、全 backend での割り当て上限はこのオプションの parser だけからは確定できない。

## 出力とエラー

`--parallel` 自体は値の受理・補正について警告を出さない。serve は `INFO` の `batch_slots` に設定 slot 数を出し、bench は計測行に `parallel` を出す（`engine/src/inkling2/ink_serve.h:562-568`; `engine/src/inkling2/ink_main.cpp:248-250`）。値の欠落は標準エラーと終了コード 2、未知のオプションは `unknown option` と終了コード 2 になる（`engine/src/inkling2/ink_main.cpp:845-849,985-988`）。backend 初期化・slot 割り当て・forward の失敗は各経路のエラー出力と終了コード 1 になる（`engine/src/inkling2/ink_main.cpp:161-165,183-185,232-234`; `engine/src/inkling2/ink_serve.h:541-548`）。

## 根拠

- parser、別名、値の補正、欠落値の処理: `engine/src/inkling2/ink_main.cpp:845-849,877-878`
- 値の既定値と backend option: `engine/src/inkling2/ink_backend.h:17-20`
- 1〜64 の slot 上限: `engine/src/inkling2/ink_batch.h:11-14`
- serve の slot 割当と空き slot 判定: `engine/src/inkling2/ink_serve.h:494-498,541-548,799-810`
- bench と batch-check の slot 利用: `engine/src/inkling2/ink_main.cpp:131-165,450-463,496-538`
- KV dtype の自動選択: `engine/src/inkling2/ink_main.cpp:882-889,1021-1024`; `engine/src/inkling2/ink_backend.h:33-35`
- 単発生成と spec-check の扱い: `engine/src/inkling2/ink_main.cpp:599-611,1097-1101`
