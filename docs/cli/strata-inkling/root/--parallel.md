# `strata-inkling --parallel`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--parallel` |
| 別名 | `--batch`、`--slots` |
| 値 | 整数として `atoi` で変換し、`1..64` に丸める |

## 役割

同時に扱うリクエスト slot 数を指定します。主な効果は `--serve` の同時リクエスト枠で、`--bench` では同数の合成系列をまとめて実行します。値に応じて起動時の slot pool と KV cache の設定も変わります。CUDA/HIP 共通 parser は `--parallel`、`--batch`、`--slots` を同じ値に設定します（`engine/src/inkling2/ink_main.cpp:411-412`）。

## 使い方

```sh
# serve で最大 4 リクエストを同時に受け付ける
strata-inkling --serve --native ./model.strata --parallel 4

# benchmark で 4 系列の合成 prompt/decode を実行する
strata-inkling --bench --native ./model.strata --parallel 4
```

## 値と既定値

- 省略時は `BackendOpts::parallel` の初期値 `1` です（`engine/src/inkling2/ink_backend.h:17-20`）。
- parser は `std::atoi` の結果を `max(1, min(64, value))` に通します。したがって `0`、負数、数値に変換できない文字列は `1`、`64` を超える値は `64` になります。範囲外・非数値としてエラーにはしません（`engine/src/inkling2/ink_main.cpp:411-412`）。slot 上限の定数は `64` です（`engine/src/inkling2/ink_batch.h:11-14`）。
- 値が必要で次の引数がない場合は `missing value after --parallel` を stderr に出して終了コード `2` で終了します（別名でもその入力文字列を表示。`engine/src/inkling2/ink_main.cpp:381-383`）。
- 同じオプションを複数回指定した場合、引数を順に処理して同じフィールドへ代入するため最後の値が残ります（`engine/src/inkling2/ink_main.cpp:379-383,411-412`）。

## 実行時の動作

- **`--serve`**: 起動時に `P = clamp(parallel, 1, 64)` 個の slot を確保し、その数を `INFO` の `batch_slots` に出します。同出力の末尾の `parallel` 欄は上限値 `64` です。自動割り当ての `GENERATE` は空き slot を探し、すべて使用中なら `ERR busy: all P parallel slots active` を返します（`engine/src/inkling2/ink_serve.h:441-465,479-485,685-690`）。slot pool を作れない場合は `ERR alloc_slot ...` を出して終了コード `1` になります（同 `:458-464`）。
- **`--bench`**: `P` 個の slot に合成 prompt を投入し、decode も各 slot で実行します。出力には実際の `parallel=P` が含まれます（`engine/src/inkling2/ink_main.cpp:158-185,225-248`）。
- **直接生成（`--serve` / `--bench` なし）**: backend slot pool は `parallel` に応じて初期化されますが、直接生成経路は slot `0` のみを確保・使用します（`engine/src/inkling2/ink_main.cpp:564-578,588-610`）。ただし後述の KV 自動選択には値が使われます。
- CPU、CUDA、HIP backend はいずれも `opts.parallel` から `1..64` の slot 数を決めます。CPU backend は pool をその数で resize し、slot ごとに KV・ShortConv 等の状態を初期化します（`engine/src/inkling2/ink_cpu_backend.cpp:304-327`）。CUDA backend は同じ数を容量見積りに使い、slot 数が大きい場合は KV 等の起動時必要量も変わります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:146-189`）。
- `--kv-dtype` / `--kv` を `auto` のままにしている場合、parallel が `16` 以上なら parser 後に KV dtype を FP8_E4M3 に設定します（`engine/src/inkling2/ink_main.cpp:535-538`）。明示的な KV dtype は parser で auto を解除します（`engine/src/inkling2/ink_main.cpp:415-424`）。CUDA backend も `max_slots_ >= 16` なら auto 選択を FP8 にします（`engine/src/inkling2/cuda/ink_cuda_backend.cu:148-159`）。HIP backend の追加の自動選択は auto が有効で、parallel が 16 以上かつ実効 GPU メモリが 36 GiB 以下の場合、または UMA でない GPU が 13 GiB 以下の場合です（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:693-701`）。

## 適用条件と副作用

- この文書の対象は索引上の CUDA/HIP 共通 `strata-inkling` parser（`engine/src/inkling2/ink_main.cpp`）です。Metal と SYCL は別 parser・別 scope で、オプション文書も索引上別項目です（`docs/cli/README.md:1511-1513,1549-1552,1572-1575`）。
- `--serve` では起動時に指定数の slot 状態を用意します。KV は paged 方式ですが、サーバーは全 slot を初期化し、最初のリクエストに先立って全 slot の `alloc_slot` を呼びます（`engine/src/inkling2/ink_serve.h:458-465`）。CUDA では slot 数が KV・workspace の容量見積りに含まれます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:170-189`）。
- slot 数は最大同時リクエスト枠であり、単発生成を複数系列で行う指定ではありません。`--bench` を除く直接生成では slot 0 だけが使われます（`engine/src/inkling2/ink_main.cpp:575-610`）。
- FP8 自動選択は KV dtype が auto のときの動作です。明示的に `--kv-dtype fp16` 等を指定すると parser が auto を解除するため、parallel だけでは KV dtype を FP8 にしません（`engine/src/inkling2/ink_main.cpp:415-424,535-538`）。

## 出力とエラー

- serve 起動時の `INFO` は指定 slot 数を `batch_slots` に、上限値 `64` を `parallel` 欄に出します（`engine/src/inkling2/ink_serve.h:479-485`）。
- 自動 `GENERATE` 要求で空き slot がないときは busy エラーを protocol 出力します（`engine/src/inkling2/ink_serve.h:685-690`）。slot 初期化失敗時は protocol の `ERR alloc_slot` を出して `1` を返します（同 `:458-464`）。
- 値の形式検証はありません。`atoi` の変換結果が範囲へ丸められるだけで、非数値は `0` として扱われ `1` になります（`engine/src/inkling2/ink_main.cpp:411-412`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-383,411-412`: parser、別名、整数変換と上下限処理、値不足時の終了。
- `engine/src/inkling2/ink_backend.h:17-20`、`engine/src/inkling2/ink_batch.h:11-14`: 既定値と共通上限。
- `engine/src/inkling2/ink_main.cpp:535-538`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:146-189`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:693-701`: KV dtype の自動選択と backend 条件。
- `engine/src/inkling2/ink_serve.h:441-465,479-485,685-704`: serve slot 数、起動出力、同時実行枠とエラー。
- `engine/src/inkling2/ink_main.cpp:158-185,225-248,575-610`、`engine/src/inkling2/ink_cpu_backend.cpp:304-327`: benchmark と直接生成の利用箇所、および CPU slot pool。
