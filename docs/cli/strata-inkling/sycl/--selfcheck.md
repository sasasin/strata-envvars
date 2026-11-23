# `strata-inkling-sycl --selfcheck`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL） |
| オプション | `--selfcheck` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

指定した Inkling-2-Mini モデルを SYCL backend でロードし、runner を初期化した後、prompt token 列を一度 forward して logits を調べる。logits の非有限値（NaN または無限大）があれば異常として終了コード 2 を返す。数値の一致を別の参照実装と比較する検査ではなく、出力の非有限値を検出する処理である（`engine/src/inkling2/sycl/ink_sy_main.cpp:209-234`）。

## 使い方

```sh
# モデルを読み込み、既定の prompt token 列で SYCL の self-check を実行する
strata-inkling-sycl --model ./model.strata --selfcheck
```

## 値と既定値

`--selfcheck` は値を取らない真偽フラグで、指定すると `do_selfcheck` が `true` になる。別名は登録されていない（`engine/src/inkling2/sycl/ink_sy_main.cpp:109-120`）。モデルパスは別途必須で、空なら usage を stderr に出して終了コード 1 となる（同 `:166-169`）。

self-check に使う token 列は `--prompt-tokens`（別名 `--prompt-ids`）で渡せる。未指定時の値は `1,2,3,4,5,6,7,8`。CSV を整数に変換し、結果が空なら同じ既定列に戻す。各 token の範囲検証はこの parser にない（同 `:19-29`, `:103-104`, `:144`, `:206-207`）。

## 実行時の動作

通常経路では必須モデルをロードし、指定があれば vision/image の処理を行った後、runner を初期化する。その後 slot 0 を reset し、prompt の各 token を slot 0・位置 `0..P-1` に割り当てて一括 forward する。logits 全体の有限性を数え、device 名、build、NaN 等の個数、argmax、処理時間、上位 5 logits を stdout に出す（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-204`, `:206-232`）。

この処理は runner を初期化した後の追加モードであり、専用処理の後に必ず終了するわけではない。`--spec-check`、`--bench`、`--par-sweep` も指定した場合、それぞれの後続処理へ進む（同 `:209-288`）。一方 `--info` はモデルの probe 後に先に終了するため、併記した `--selfcheck` は実行されない（同 `:173-181`）。

## 適用条件と副作用

- `--model` によるモデルロードと SYCL runner の初期化が先に必要。モデルロードまたは runner 初期化に失敗すると self-check 部分へ到達せず、`[ERROR]` または `runner init:` を stderr に出して終了コード 1 を返す（`engine/src/inkling2/sycl/ink_sy_main.cpp:183`, `:198-204`）。
- self-check 自身は slot 0 を reset して forward する。`--parallel` は初期 slot 数、`--ctx`（別名 `--max-context`）は runner の context 設定に使われるが、この検査が使う slot は 0 のみ（同 `:104`, `:126-127`, `:198-217`）。SYCL backend runner は slot 数を 1..64、context を最低 256 に制限して保持する（`engine/src/inkling2/sycl/ink_sy_runner.h:223-229`）。
- `--vision` と `--image` を両方指定すると、その画像のロード・encode が self-check より先に行われ、失敗時は stderr に `[ERROR]` を出して終了コード 1 となる（`engine/src/inkling2/sycl/ink_sy_main.cpp:185-195`）。
- self-check の forward 呼び出しは戻り値を検査していない。直接呼び出す `InkSyRunner::forward_batch` は `M > max_batch` のとき `false` を返すが、呼出元にはその値からエラー終了する分岐がない。prompt が runner の batch 上限を超えた場合も結果行の出力と有限性判定へ進む（`engine/src/inkling2/sycl/ink_sy_main.cpp:198-218`; `engine/src/inkling2/sycl/ink_sy_runner.h:223-229`, `:421-427`）。

## 出力とエラー

logits に非有限値が一つ以上あれば `[SELFCHECK]` の結果行を出した後、終了コード 2 を返す。0 件の場合、この節の self-check による異常終了はなく、後続モードがなければ最終的に終了コード 0 となる（`engine/src/inkling2/sycl/ink_sy_main.cpp:219-234`, `:288`）。モデル・vision・runner の初期化失敗は前節のとおり終了コード 1。self-check 内の forward が `false` を返した場合の専用エラー出力や終了コード処理は呼出元に見当たらない（`engine/src/inkling2/sycl/ink_sy_main.cpp:216-218`; `engine/src/inkling2/sycl/ink_sy_runner.h:421-427`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — SYCL CLI の parser と `--selfcheck` のフラグ登録、関連する prompt オプション。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-204` — モデル必須条件、info の早期終了、モデル・vision・runner 初期化。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:206-234` — prompt の既定値、self-check の forward・出力・終了条件。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:236-288` — self-check 後の後続モードと通常終了。
- `engine/src/inkling2/sycl/ink_sy_runner.h:223-229` — runner が保持する slot/context の下限・上限。
- `engine/src/inkling2/sycl/ink_sy_runner.h:421-427` — self-check が直接使う runner の batch forward と batch 上限チェック。
