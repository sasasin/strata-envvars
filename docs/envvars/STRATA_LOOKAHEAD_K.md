# `STRATA_LOOKAHEAD_K`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ルーター先読みが各入力 token について予測対象にする expert の上位件数を指定する。予測された expert を先に warm してファイル tier や Foresight swap space への読み込みを先行させる用途であり、実際の MoE routing が選ぶ expert 数や結果を変更する値ではない。CUDA/HIP 実装は `RouterLookahead` の `k_` を使って予測候補を作り、SYCL 実装も同じ `k_` を使う。未設定時は両方とも `10`（`engine/src/program/generate.cpp:10319-10320`、`engine/sycl/src/program/generate.cpp:5806-5807`）。

## 値と判定

両 backend とも、環境変数が未設定なら `10`、設定済みなら `std::atoi` の結果を `RouterLookahead::start` に渡す。`start` は値を `[1, n_expert]` に clamp するため、空文字、0、負数、数値に変換できない文字列は `1` になる。`n_expert` を超える値はモデルの expert 数に丸められる（`engine/src/core/expert_source.cpp:3534-3544`、`engine/sycl/src/core/expert_source.cpp:1453-1464`）。

| 条件 | unset | 有効になる値の例 | 入力後の扱い・境界例 |
| --- | --- | --- | --- |
| CUDA/HIP または SYCL で先読み開始条件を満たす | `10` | `1`、`10`、`20` | `1` 未満（`0`、`-2`、空文字、`true`、`nonnumeric` を含む）は `1`。`n_expert` より大きい整数は `n_expert`。 |

`atoi` は先頭の空白と符号付き数値を読み、数値の後ろは検査しない。そのため `" 2 "` と `"2tail"` は `2`、`"0anything"` は `0` から clamp されて `1`、`"true"` は変換結果 `0` から `1` になる。文字列全体の妥当性や大文字小文字は検査されない。表の既定値は未設定の場合だけであり、明示的な空文字は既定値に戻らない。`atoi` で表現範囲外の値を変換した場合の結果はこのコードで定義されない（両 `generate.cpp` の読み取り行および上記 `start` 行）。

## 有効になる条件

- **CUDA/HIP:** `srcp` が存在し、`srcp == &src && src.warms()`、または `STRATA_FS_SLOTS` が `atoi` で正、かつ `STRATA_FS_AHEAD` が未設定か非ゼロ、または `STRATA_LOOKAHEAD_STATS` が非ゼロであり、さらに `STRATA_LOOKAHEAD` が未設定か `atoi` で非ゼロであること。ルーター重みが BF16-in-F32 で想定 byte 数と一致し、device からコピーできる必要もある（`engine/src/program/generate.cpp:10288-10303`, `10304-10320`）。
- **SYCL:** `srcp == &src` かつ `src.warms()`、`STRATA_LOOKAHEAD` が未設定か `atoi` で非ゼロであること。全 layer の router 重みが BF16-in-F32 で想定 byte 数と一致し、device からコピーできる必要がある（`engine/sycl/src/program/generate.cpp:5792-5807`）。
- CUDA/HIP では全 expert が GPU cache にある場合、既定の先読みは attach されないことがある。`STRATA_LOOKAHEAD` または `STRATA_IO_PREFETCH` が非空かつ `atoi` 非ゼロなら要求扱いになり、`STRATA_FS_AHEAD` または `STRATA_LOOKAHEAD_STATS` が有効な場合もこの自動停止分岐を避ける。状態変化後に request 開始時や VRAM resize 後の更新で再 attach される経路がある（`engine/src/program/generate.cpp:10288-10290`, `10328-10333`, `10341-10377`）。SYCL にはこの resident 判定による attach/detach 分岐はない。
- `STRATA_LOOKAHEAD=0`（または `atoi` 結果が 0）なら K の値に関係なく起動条件から外れる。CUDA/HIP の `STRATA_IO_PREFETCH` は全 expert resident 時の先読み維持要求には使われるが、`STRATA_LOOKAHEAD` の明示的な 0 を打ち消さない。
- CLI 引数による K の上書きは該当ソースに見つからない。`STRATA_IO_PREFETCH_DEPTH` は CUDA/HIP 側の先読み layer depth を変える別設定であり、K の優先値ではない（`engine/src/program/generate.cpp:10319-10326`）。

## 実行時の詳細

K は engine の生成準備中に `generate.cpp` の該当分岐で読み取られ、`RouterLookahead::start` に渡される。リクエストごとではなく、この `RouterLookahead` インスタンスを開始する時点で一度読み、`k_` に保存する。実行中の環境変更を再読するコードはない。CUDA/HIP では起動条件が満たされるたびにルーター行列を device から host vector へコピーし、SYCL も同様に copy 後に start する（`engine/src/program/generate.cpp:10302-10320`、`engine/sycl/src/program/generate.cpp:5792-5807`）。

処理中、現在 layer の activation に対して次 layer の router を CPU 側で評価し、各 token の上位 K 件から GPU 上に既にある expert を除いた候補をまとめて `warm` する。CUDA/HIP は先読み depth に応じた複数 layer を対象にでき、SYCL は次 layer を対象にする。CUDA/HIP の `STRATA_LOOKAHEAD_STATS` は測定用候補集合を追加評価するが、warm 対象は K 件のまま。lookahead の予測は既存 routing の前読みであり、実際の MoE 選択には接続されない（`engine/src/core/expert_source.cpp:3740-3759`, `3789-3792`; `engine/sycl/src/core/expert_source.cpp:1531-1543`）。各 layer の処理から `submit` が呼ばれる（`engine/src/core/expert_source.cpp:5436-5442`; `engine/sycl/src/core/expert_source.cpp:2569-2570`）。

## ログと測定値

開始に成功すると CUDA/HIP は `strata generate: routing-aware prefetch on (the next layer's router, file tier)`（Foresight 使用時は `..., feeding the Foresight swap space`）を stderr に出す。全 expert が GPU cache にあり自動停止した場合は `strata generate: routing-aware prefetch off (every expert is in the GPU caches; STRATA_LOOKAHEAD=1 runs it)`。開始できない場合は `routing-aware prefetch off (...)` とし、router 重み形式が合わない場合は `the routers are not BF16 in the arena`、それ以外は `start` の理由文字列を表示する。SYCL は成功時に `strata generate: routing-aware prefetch of the file tier on (the next layer's router)`、失敗時に同様の `off (...)` を出す（`engine/src/program/generate.cpp:10328-10338`; `engine/sycl/src/program/generate.cpp:5808-5819`）。

`start` が拒否する条件は source が warm しない、`n_embd` が 8 の倍数でない、または router 行列の shape 不一致で、それぞれ理由文字列を設定する。ただし呼び出し側の事前条件により通常は warm source と router shape を確認してから到達する。K 自体の範囲外値による失敗・終了はなく clamp される（`engine/src/core/expert_source.cpp:3534-3544`; `engine/sycl/src/core/expert_source.cpp:1453-1464`）。この変数について Strata の資料に条件付き性能測定値は見つからなかった。

## 根拠

- `engine/src/program/generate.cpp:10288-10338` — CUDA/HIP の開始条件、読み取り、既定値、ログ。
- `engine/src/program/generate.cpp:10341-10377` — GPU cache 状態変化時の detach / reattach。
- `engine/sycl/src/program/generate.cpp:5792-5819` — SYCL の開始条件、読み取り、既定値、ログ。
- `engine/src/core/expert_source.cpp:3534-3552`, `3740-3793` — CUDA/HIP の clamp、予測件数、warm 処理。
- `engine/sycl/src/core/expert_source.cpp:1453-1467`, `1531-1544` — SYCL の clamp、予測件数、warm 処理。
- `engine/src/core/expert_source.cpp:5436-5442`; `engine/sycl/src/core/expert_source.cpp:2569-2570` — 生成処理から lookahead を submit する箇所。
- `docs/DETAILS.md:304-317`, `docs/UNSLOTH_Q4.md:228-234` — ソースとの照合。どちらも K を先読みの tunable とし、既定値 10 を記載している。
