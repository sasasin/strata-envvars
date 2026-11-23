# `strata-hy4 --save-logits`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--save-logits` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

オフライン推論の prompt prefill で得た logits を、NumPy の `.npy` 形式で `logits.npy` に保存します。生成中の各 token の logits を保存する指定ではありません。CUDA/HIP 実装で受理されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:492,777`）。

## 使い方

```sh
# 事前に空の出力ディレクトリを用意し、入力 token ID の prefill logits を保存する
strata-hy4 --model MODEL.strata --tokens prompt.ids --save-logits --out ./logits-out
```

`--out` は保存先ディレクトリを指定します。実装はこの指定先を自動作成しないため、ディレクトリが存在する状態で実行してください。また同名の `logits.npy` があれば上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:347,485,777`; `engine/src/hy4flash/run/hy4_graph.hip.h:85-96`）。

## 値と既定値

値を取りません。parser は指定時に `save_logits = true` とし、既定値は `false` です。数値・パスなどの値検証はありません。同じフラグを複数回指定しても同じ真偽値を設定するだけです（`engine/src/hy4flash/run/hy4_main.hip.cpp:351,492`）。

## 実行時の動作

通常のオフライン経路では、prompt を chunk 単位で prefill し、最後の chunk の処理後に logits を GPU から host にコピーします。その時点で `--save-logits` または `--dump` が指定されていれば、`<out-dir>/logits.npy` に保存します。配列形状は `(n, V)` で、`V` は語彙数です。dtype は float32 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:758-777`; `engine/src/hy4flash/run/hy4_graph.hip.h:77-96`）。

`--all-logits` を付けない場合、最後の prefill chunk の最終位置に対応する1行だけを head で計算・保存します。`--all-logits` を付け、かつ speculative `spec_mode` でない場合は最後の prefill chunk 全位置の行を保存します。prefill が複数 chunk に分かれても、それ以前の chunk の logits はこの保存処理に含まれません（`engine/src/hy4flash/run/hy4_main.hip.cpp:701,758-777`）。

保存先は `--out` の値で決まり、省略時はカレントディレクトリ `.` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:347,485`）。`--dump` も同じ条件で `logits.npy` を保存するため、両方を付けてもこのファイルについて効果は重複します（同:490-492,777）。

## 適用条件と副作用

- `--serve` の場合、parser 後に serve 用処理へ戻るため、`save_logits` は serve 処理へ渡されず、この offline logits 保存箇所には到達しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611`）。
- `--load-only` はモデル読み込み後に終了するため、prefill と保存は行いません（同:658-665）。
- `--dump-dfly-batch` は通常の prefill 経路より前に専用処理へ分岐して戻るため、この `logits.npy` 保存処理は通りません（同:707-709）。
- 保存処理はファイルを `wb` で開くので既存ファイルを切り詰めて上書きします。指定ディレクトリがない、または開けない場合、helper は何も出力せず戻ります。`fwrite` の戻り値も確認しないため、書き込み失敗は CLI のエラーとして報告されません（`engine/src/hy4flash/run/hy4_graph.hip.h:85-96`）。

## 出力とエラー

成功時、指定ディレクトリに `logits.npy` を生成します。保存関数は `fopen` に失敗しても診断を出さず戻り、呼び出し元も失敗を検査しません。そのため、保存に失敗してもこの箇所からは警告や非ゼロ終了になりません（`engine/src/hy4flash/run/hy4_graph.hip.h:85-96`; `engine/src/hy4flash/run/hy4_main.hip.cpp:777`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351,492` — `save_logits` の初期値と parser 登録。引数なしのフラグとして受理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,658-665,701,707-709` — serve、load-only、dump-dfly-batch の分岐と適用範囲。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:758-777` — 最終 prefill chunk の logits 計算・host copy・保存条件。`--all-logits` との関係。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-96` — NumPy header、float32 payload、`wb` による出力、open/write エラーの扱い。
