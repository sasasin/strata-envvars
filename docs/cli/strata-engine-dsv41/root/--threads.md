# `--threads`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 専用 engine） |
| オプション | `--threads` |
| 別名 | なし |
| 値 | `on` または `off`（実装上は `off` との完全一致だけを無効扱い） |

## 役割

GPU ごとに host thread を用意し、その GPU に割り当てた層の処理を並列に enqueue するモードを有効にします。GPU 間の層の受け渡しには host-mapped memory を使います。主に decode の window 処理を並列化し、条件によって prompt の chunk 処理にも GPU ごとの host thread を使います。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --tp 1 --threads on --ids 1,2,3
```

`--ids` は推論入力の例です。複数 GPU の tensor parallelism を使う場合は `--tp` と組み合わせます。`--threads off` で明示的に無効にできますが、`--tp` により並列経路が選ばれる場合があります。

## 値と既定値

- `--threads` は値を1つ取ります。ヘルプは `on|off` と案内しています（`src/dsv41/ds4_main.cpp:85-93`）。
- 既定値は off です。`Options::threads` は `false` で初期化されています（`src/dsv41/ds4_model.hpp:49-57`）。
- parser は値が文字列 `off` と等しい場合だけ `false`、それ以外を `true` にします。したがって `on` が有効、`off` が無効ですが、未知の値も拒否されず有効扱いです。値の検証や大文字小文字の正規化はありません（`src/dsv41/ds4_main.cpp:1231-1234`）。
- 値を省略すると `--threads needs a value` を stderr に出して終了コード 2 になります（`src/dsv41/ds4_main.cpp:1200-1207`）。同じオプションを複数回指定した場合、parser が順に代入するため最後の値が残ります（`src/dsv41/ds4_main.cpp:1209-1234`）。

## 実行時の動作

- モデル初期化時、実効 `tp` が1より大きい場合、または `--threads` が有効な場合に `par` を有効にします。`par` が有効な decode window は `forward_par()` を通り、各 GPU の worker に `run_dev()` を投入してから全 worker を待ちます（`src/dsv41/ds4_model.cu:1912-1924, 8310-8317, 8391-8407`）。モデル既定の `tp` は2ですが、GGUF の分割条件により1まで補正されることがあります。実効 `tp > 1` の場合、`--threads off` だけでは並列経路を無効にしません。`--tp 1 --threads off` なら `par` は無効です（`src/dsv41/ds4_model.hpp:49-57`; `src/dsv41/ds4_model.cu:1892-1917`）。
- `par` または chunked prompt が有効なら GPU ごとの worker を起動します（`src/dsv41/ds4_model.cu:2770-2775`）。`Options` の説明では worker は各 GPU の層を enqueue し、受け渡しは host-mapped memory とされています（`src/dsv41/ds4_model.hpp:49-57`）。
- prompt の chunk 経路は `--threads` だけで決まるわけではありません。`par`、`tp > 1`、または chunked prompt の既定条件（`--prefill-chunk` が省略時の負値で `DS4_WINDOWS` が未設定）が `prompt_par` を有効にします。したがって `--tp 1 --threads off` でも、既定では chunked prompt が使われます。`DS4_WINDOWS` が設定されるとその既定条件は無効です（`src/dsv41/ds4_model.cu:1917-1924`; 既定値は `src/dsv41/ds4_model.cu:809-816`）。
- `--prefill-chunk` は別の制御です。chunk サイズを0にすると chunking を止めて window prompt にしますが、`--threads on` なら `par` 自体は有効なままです（`src/dsv41/ds4_model.cu:1917-1924, 1968-1984`）。

## 適用条件と副作用

- 処理は選択された GPU 群・層配置に対して行われ、GPU ごとに worker thread を作成します。GPU 間 hand-off 用の host-mapped memory を用います。CPU の expert 計算スレッド数を設定する `--cpu-threads` とは別のオプションです（`src/dsv41/ds4_model.hpp:29-33,49-57`; `src/dsv41/ds4_model.cu:2770-2775,8391-8407`）。
- `--tp` は group の幅を指定し、GGUF の expert block 分割などの条件によって実効値が下がることがあります。その補正後の `tp` と `--threads` の真偽から decode の並列経路が選択されます（`src/dsv41/ds4_model.cu:1892-1917`）。
- worker 作成や GPU 処理の詳細な OS ごとの差、および `--threads` による性能差は、このソース確認だけでは一般化できません。ベンチマークや GPU 実行は行っていません。

## 出力とエラー

- worker ごとの GPU 処理が失敗すると、そのエラー文字列を集約し、並列 forward は失敗を返します。空のエラー文字列なら `a device's thread failed` に置き換えます（`src/dsv41/ds4_model.cu:8393-8407`）。モデル load の失敗は `maya-ds4: <理由>` を stderr に出し、終了コード1になります（`src/dsv41/ds4_main.cpp:1289-1294`）。
- 未知の CLI オプションは `unknown option ...` と usage を stderr に出し終了コード2です。ただし `--threads` の未知の値は parser でエラーにならず、有効扱いになります（`src/dsv41/ds4_main.cpp:1233,1266-1272`）。

## 根拠

- `src/dsv41/ds4_main.cpp:85-93,1200-1207,1231-1234,1266-1272,1289-1294` — usage、値の取得、parser の真偽変換、引数エラー、load 失敗。
- `src/dsv41/ds4_model.hpp:29-33,49-57` — `cpu_threads` と `threads` の別個の設定、`tp` と `threads` の既定値・説明。
- `src/dsv41/ds4_model.cu:1892-1924,1968-1984` — `tp` の補正、decode 並列条件、prompt chunk の条件とサイズ。
- `src/dsv41/ds4_model.cu:2770-2775,8310-8317,8391-8407` — worker 作成、forward の分岐、並列処理と失敗伝播。
- `docs/cli/README.md:1353-1397` — 対象 CLI の索引 scope と `--threads` 文書リンク。
