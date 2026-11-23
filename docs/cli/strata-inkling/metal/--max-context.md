# `strata-inkling-metal --max-context`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--max-context` |
| 別名 | `--ctx` |
| 値 | 整数。parser に明示的な値域検査はない。runner が最低値 256 を適用する。 |

## 役割

Metal runner の最大 context 長（token 数）を指定する。これは Metal の KV cache 容量に使われ、生成ループの上限にもなる。Apple の推奨 working set と並列 slot 数を使った初期化時の調整があるため、指定値がそのまま実効値になるとは限らない。parser は両表記を同じ `max_ctx` に読み込む（`engine/src/inkling2/metal/ink_metal_main.cpp:420-424,448`）。

## 使い方

```sh
# Metal runner のベンチマークを context 長 8192 で実行する
strata-inkling-metal --model ./Inkling-2-Mini.strata --max-context 8192 --bench

# 短縮別名でも同じ値を指定できる
strata-inkling-metal --model ./Inkling-2-Mini.strata --ctx 4096 --bench
```

## 値と既定値

- 省略時は `4096`（`engine/src/inkling2/metal/ink_metal_main.cpp:420`）。
- `--max-context` と `--ctx` は同じ `atoi` 変換の分岐で扱われる（同 `:448`）。繰り返し指定時は引数走査のたびに代入されるため、後の値が残る（同 `:432-468`）。
- CLI 側には数値の範囲検査や形式エラー処理がなく、`atoi` の結果が runner に渡る。runner は `max_ctx = std::max(256, ctx_len)` として 256 未満を 256 に引き上げる（`engine/src/inkling2/metal/ink_metal_runner.h:230-239`）。したがって 0 や負値も parser では拒否されず、少なくとも初期値の下限は 256 になる。非整数文字列の詳しい変換規則はこの CLI ソースでは独自に定義していない。

## 実行時の動作

- main は値を `runner.init(..., max_ctx, ...)` に渡す（`engine/src/inkling2/metal/ink_metal_main.cpp:489-493`）。runner は初期値を設定した後、モデル構成と `max_slots` を使い、Global KV の 1 token あたりの必要量を算出する（`engine/src/inkling2/metal/ink_metal_runner.h:230-239,383-395`）。
- 推奨 working set が 4 GiB を超え、固定分を差し引いた領域から算出した収容可能長 `fit_ctx` が指定値より小さい場合、値を 64 token 単位に切り下げた見積もりに合わせて調整する。ただし調整値には最低 1024 が適用されるため、指定値が 1024 未満の場合にこの分岐へ入ると、実効値が指定値より大きくなる場合もある（同 `:388-403`）。
- 固定分が working set を超える分岐では、`max_batch` を 256 に抑え、context が 4096 より大きい場合は 4096 に下げる（同 `:404-410`）。推奨 working set が 4 GiB 以下の場合、この自動調整ブロック自体を通らない（同 `:388`）。
- 実効値は非 sliding-window visits の KV stride とバッファサイズに反映される（同 `:428-435`）。DSpark が有効なモデルでは、その context KV の stride にも使われる（同 `:239,521-527`）。standalone CLI では `--draft off` でなければ DSpark を要求するが、モデル manifest に DSpark がなければ runner では無効になる（`engine/src/inkling2/metal/ink_metal_main.cpp:489-492`、`engine/src/inkling2/metal/ink_metal_runner.h:239`）。このため DSpark の有無も working-set 見積もりに影響する（同 `:395`）。
- 通常生成では `cur_pos + 1 < max_ctx` が decode 継続条件であり、DSpark の speculative 経路も上限近くでは通常の 1 token forward に切り替わる（`engine/src/inkling2/metal/ink_metal_main.cpp:174-185`）。

## 適用条件と副作用

- オプションは `strata-inkling-metal` の standalone CLI に実装されている。Terminal の `strata` サブコマンドに対するものではない（parser: `engine/src/inkling2/metal/ink_metal_main.cpp:417-468`）。
- context 長と slot 数に応じて KV cache 用メモリが確保される。Global KV は各 token の stride を `max_ctx` とし、割当サイズに `max_slots` と stride が乗算される（`engine/src/inkling2/metal/ink_metal_runner.h:160-165,428-435`）。大きな値は必要メモリを増やすが、Metal の working-set 見積もりにより前述の調整を受ける。
- 通常生成関数では prompt の prefill を先に行い、その後に decode 上限を判定する。確認した呼び出し箇所には prefill 長と `max_ctx` を比較する明示的な検査がない（`engine/src/inkling2/metal/ink_metal_main.cpp:145-159,174-185`）。そのため、指定 context を超える prompt が必ず CLI エラーになるとはソースから確認できない。

## 出力とエラー

- 自動調整が発生した場合、working-set 分岐に応じて stderr に `[ink_metal] WorkingSet-aware auto-ctx: ...` または `[ink_metal] Tight Unified WorkingSet ... clamping ctx ...` を出す（`engine/src/inkling2/metal/ink_metal_runner.h:398-410`）。runner 初期化完了時にも stderr の `[ink_metal] runner ready: ... ctx=%d ...` に実効値を出す（同 `:758-764`）。
- 値を付け忘れると `missing value for --max-context`（または `--ctx`）を stderr に出し、終了コード 2 で終了する（`engine/src/inkling2/metal/ink_metal_main.cpp:434-437`）。値を整数として検証して拒否する専用エラー経路は parser にない。
- runner 初期化が失敗すると main は `[ERROR] runner init: ...` を stderr に出して終了コード 1 を返す（同 `engine/src/inkling2/metal/ink_metal_main.cpp:491-493`）。context 値に起因する個別の失敗条件や、Metal allocation failure 時のこの CLI に固有のメッセージは、確認した範囲では特定できなかった。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-468` — 既定値、parser、別名、値欠落・不明引数の処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:489-493` — 値を runner に渡す箇所と初期化失敗時の出力・終了コード。
- `engine/src/inkling2/metal/ink_metal_main.cpp:145-185` — prefill と生成上限・speculative fallback。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-239,383-435,521-527` — 下限、working-set 調整、KV 容量への反映。
- `engine/src/inkling2/metal/ink_metal_runner.h:758-764` — 初期化後の実効 context 出力。
