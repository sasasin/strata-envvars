# `strata-inkling-metal --parallel`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--parallel` |
| 別名 | `--slots` |
| 値 | 整数として `atoi()` で変換される値。runner の有効 slot 数は `1..64` に収められる |

## 役割

Metal 版 Inkling runner が確保する同時要求 slot の上限を指定します。Metal runner の slot ごとの KV cache や ShortConv state pool の容量に反映され、`--par-sweep` では指定上限以下の並列数の測定を行います。この単体 CLI の `--selfcheck`、`--spec-check`、通常の `--bench` は slot 0 を使うため、`--parallel` を指定しただけで複数要求を同時実行するものではありません（`engine/src/inkling2/metal/ink_metal_main.cpp:517-531,560-570,589-603`）。

## 使い方

```sh
# Metal runner の slot 上限を8にし、par-sweep の測定対象を1/4/8にする
strata-inkling-metal --model ./model.strata --par-sweep --parallel 8 --prompt-len 32 --gen 8
```

`--par-sweep` は `1, 4, 8, 32, 64` の順で測定し、上限を超える値で打ち切ります。したがって上例では 32 と 64 は測定されません。モデルファイルは実行環境にある Inkling-2 用 `.strata` を指定してください（`engine/src/inkling2/metal/ink_metal_main.cpp:606-613`）。

## 値と既定値

- 値は必須です。`--parallel` と `--slots` は同じ変数 `max_slots` に `atoi()` の結果を格納します（`engine/src/inkling2/metal/ink_metal_main.cpp:421-422,432-450`）。
- 省略時は `1` です（同:421）。runner 初期化時に `max(1, min(64, slots))` で `1..64` に制限されるため、0・負数は 1、64 を超える値は 64 になります。値を範囲外として拒否する処理はありません（`engine/src/inkling2/metal/ink_metal_runner.h:230-239`）。
- 数値書式の厳密な検証はありません。C/C++ の `atoi()` に渡され、変換できない文字列は 0 相当として扱われた後、runner 側で 1 になります。値を省略すると parser の `nxt()` が `missing value for --parallel`（または `--slots`）を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/metal/ink_metal_main.cpp:434-436,448-450`）。
- 同じオプションを複数回指定した場合は parser のループが都度代入するため、最後の値が残ります（同:432-450）。

## 実行時の動作

- `main()` は `max_slots` を受け取り、モデルのロード後に `runner.init()` へ渡します。runner は上限値で slot ごとの KV cache、ShortConv state pool、active slot 用 buffer を確保し、起動時に `slots=<有効値>` と割当量を stderr に表示します（`engine/src/inkling2/metal/ink_metal_main.cpp:417-423,481-493`、`engine/src/inkling2/metal/ink_metal_runner.h:230-239,428-468,758-764`）。
- 利用可能な working set に基づく自動 context 調整のメモリ見積もりにも slot 数が入ります。条件により context 上限が縮小されることがあります（`engine/src/inkling2/metal/ink_metal_runner.h:383-412`）。
- `--par-sweep` は指定上限が 64 未満なら parser 時点で `max_slots` を 64 に引き上げます。ただし後から現れる `--parallel` / `--slots` は値を再代入するため、引数順序で結果が変わります。`--par-sweep --parallel 8` は上限 8、`--parallel 8 --par-sweep` は上限 64 です（`engine/src/inkling2/metal/ink_metal_main.cpp:432-450,457`）。測定ループは有効上限より大きい候補で停止します（同:606-613）。
- 各並列測定は `c_req` 個の slot に prompt を割り当てて batch forward を行い、その後各 slot を decode します。`run_parallel_bench()` は `c_req > runner.max_slots` をエラーとして返しますが、通常の sweep 経路ではその前に候補を打ち切ります（`engine/src/inkling2/metal/ink_metal_main.cpp:363-414,606-613`）。

## 適用条件と副作用

- 対象は `strata-inkling-metal` の Metal runner です。通常の Inkling CLI および SYCL 版の同名オプションは別 parser・別文書です（`docs/cli/000_cli_tools.md:12`、`docs/cli/README.md:1549-1565`）。
- Slot 上限を増やすと slot 数に応じた cache/state buffer が大きくなります。working set 見積もりと自動 context 調整に影響しますが、指定値に対して実行可能なメモリ量を保証する validation は確認できません（`engine/src/inkling2/metal/ink_metal_runner.h:383-412,428-468`）。
- `--parallel` 自体はファイルやネットワークへ出力しません。実際に `--par-sweep` を併用すると推論計算を実行し、各測定結果を stdout に出します（`engine/src/inkling2/metal/ink_metal_main.cpp:362-414,606-613`）。

## 出力とエラー

- runner 初期化に失敗した場合は `[ERROR] runner init: ...` を stderr に出し、終了コード 1 になります。slot 数に関する専用の範囲エラーはありません（`engine/src/inkling2/metal/ink_metal_main.cpp:490-493`）。
- `--par-sweep` の測定結果は `[PAR c=...]` 行として stdout に出ます。測定処理が失敗すると `[ERROR] par c=...: ...` を stderr に出し、終了コード 1 です（同:606-613、および `engine/src/inkling2/metal/ink_metal_main.cpp:409-414`）。
- 値の欠落は stderr に `missing value for <option>` を出し、終了コード 2 です（同:434-436）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-450` — 既定値、`--parallel` / `--slots` parser、値の変換。
- `engine/src/inkling2/metal/ink_metal_main.cpp:457,606-613` — `--par-sweep` との引数順序の相互作用と測定候補。
- `engine/src/inkling2/metal/ink_metal_main.cpp:363-414,490-493` — 並列測定の slot 使用、初期化呼び出し、失敗経路。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-239,383-412,428-468,758-764` — slot 数の clamp、メモリ確保と working set による context 調整、起動ログ。
