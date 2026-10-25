# `--pool-cores`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル引数） |
| オプション | `--pool-cores` |
| 別名 | なし |
| 値 | 論理プロセッサ番号のリスト。例: `0,2,4,6`、`2-14:2` |

## 役割

CPU expert pool の worker thread を割り当てる論理プロセッサと順序を明示します。実験的な設定で、指定しなければ従来の既定配置を使います。CPU の場所を変える設定であり、性能向上は保証されません。エンジンの help 文面も実験的・既定無効とし、thread の場所だけを動かすと説明しています（`src/program/generate.cpp:1039-1045`）。

## 使い方

```sh
strata --native MODEL.gguf --pool-cores 2-14:2 --tokens IDS
```

`--native` のモデルを使う例です。モデルファイルと `IDS` は実際の入力に置き換えてください。`--pool-cores` は値を1つ取ります。値の直後に別のオプションを書いても、parser は値として取り込み、その文字列がリスト検証で不正になります（`src/program/generate.cpp:2418-2420,2529`）。

## 値と既定値

- カンマ区切りの番号、昇順範囲 `開始-終了`、または `開始-終了:step` を組み合わせられます。範囲の step は省略時 `1` です。空白とタブは番号や区切りの周囲で読み飛ばします（`include/strata/kernels/cpu/pool_plan.hpp:180-212`）。
- 各番号・範囲端・step は非負の10進数で、番号の上限は `100000`。逆順範囲、step `0`、空要素、負数、数字以外は不正です。重複番号は最初の出現だけ保持され、展開後の項目数が4096を超えるリストは拒否されます（同:188-224）。
- 未指定時の既定値は空文字で、従来の worker 配置を使います（`src/program/generate.cpp:527-528,2900-2910`）。同じオプションを複数回指定すると parser は値を順番に代入するため、最後の値が残ります（同:2416-2421,2529）。
- 値なしで指定すると `--pool-cores needs a value` を stderr に出して終了コード `2` で終了します（同:2418-2420）。

## 実行時の動作

parser は値を文字列として保存します。CPU pool の構築前に、値が空なら `STRATA_POOL_CORES` を読み、選ばれた非空文字列を解析します。CLI に非空の値がある場合は環境変数を読みません。CLI 値が空文字の場合は環境変数へフォールバックします。解析に失敗しても処理を中断せず、stderr に `strata generate: --pool-cores: ...; the pool uses its default placement` を出して既定配置を使います（`src/program/generate.cpp:2900-2910`; 値解析は `include/strata/kernels/cpu/pool_plan.hpp:183-224`）。

解析後、CPU pool は検出した論理プロセッサ配置と照合し、使用できない番号を除外します。除外した番号は stderr に警告します。同一物理 core の SMT sibling を複数指定した場合や host thread と同じ CPU / core を指定した場合は項目を残したまま警告します。すべての番号が使えない場合は既定配置へ戻ります（`include/strata/kernels/cpu/pool_plan.hpp:227-279`; `src/kernels/cpu/pool.cpp:765-779`）。

利用可能なリストの順序は維持されます。`--pool-workers` が正数で指定されていればその worker 数を使い、リストより多い worker はリストにない分だけ未 pin になります。`--pool-workers` を指定しない場合は、利用可能なリスト項目数が worker 数になります（`src/program/generate.cpp:1043-1044`; `src/kernels/cpu/pool.cpp:801-817,923-945`）。明示リストがあると NUMA 用の自動並べ替えも行われません（同:781-799）。

実際の pin は worker thread ごとに行われます。Linux では `pthread_setaffinity_np` を呼び、失敗した場合は stderr に affinity エラーを出して以前の affinity を維持します。macOS では pin 関数が no-op で、スケジューラが thread の実行場所を決めます（`src/kernels/cpu/pool.cpp:923-934`; `src/kernels/cpu/pool_affinity_linux.hpp:60-66,69-85`）。

## 適用条件と副作用

- CPU pool を利用する通常の `src/program/generate.cpp` / SYCL `sycl/src/program/generate.cpp` 経路で設定を読みます。SYCL 側にも同じ parser、環境変数フォールバック、pool 設定があります（`sycl/src/program/generate.cpp:506-507,936-938,1852,2089-2099`）。
- `--no-pool` が指定された実行では pool worker の処理は使われず、起動ログでも `UNUSED: --no-pool` と表示されます（`src/program/generate.cpp:6928-6936`）。
- Qwen3.6-35B-A3B はモデル family 判定で `strata::qwen35::run` に引き渡されます。この別 parser は `--pool-cores` を受理しません。serve mode では未対応オプションとして値とともに無視され、それ以外では usage を表示して終了コード `2` になります（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3742-3747,3782-3794`）。
- pool の worker thread 配置を変えます。ソース help は「thread を動かすだけで、結果は変えない」としていますが、配置別の性能差はこの調査では測定していません（`src/program/generate.cpp:1044`）。

## 出力とエラー

- リスト形式の不正値は stderr に説明を出し、終了せず既定配置で続行します（`src/program/generate.cpp:2905-2909`）。
- pool 構築時の使用不可番号、SMT / host thread 共有、全番号使用不可は `strata cpu pool: --pool-cores: ...` 形式で stderr に通知します（`src/kernels/cpu/pool.cpp:765-774`; 警告文の生成は `include/strata/kernels/cpu/pool_plan.hpp:245-279`）。
- worker の pin に失敗すると Linux では `strata cpu pool: affinity for worker ... failed: ...; previous affinity kept` を stderr に出します（`src/kernels/cpu/pool.cpp:580-590`）。

## 根拠

- 索引上のスコープ: [`docs/cli/README.md`](../../README.md) の `strata-engine` / `strata`（トップレベルエンジン引数）節。
- parser の値格納、missing value の終了、help 記述、`STRATA_POOL_CORES` fallback: `src/program/generate.cpp:527-528,1039-1045,2416-2421,2529,2900-2910`。
- リスト文法、重複除去、最大項目数、無効値: `include/strata/kernels/cpu/pool_plan.hpp:180-224`。
- topology 照合、除外・共有警告: `include/strata/kernels/cpu/pool_plan.hpp:227-279`; pool への適用と fallback: `src/kernels/cpu/pool.cpp:763-779`。
- worker 数、指定順維持、NUMA 並べ替え、未 pin worker: `src/kernels/cpu/pool.cpp:781-817,923-945`。
- SYCL 側の対応実装: `sycl/src/program/generate.cpp:506-507,936-938,1852,2089-2099`。
- Qwen3.6 専用経路: `src/program/generate.cpp:2393-2407`; 専用 parser: `src/qwen35/q36_engine.cu:3735-3794`。
