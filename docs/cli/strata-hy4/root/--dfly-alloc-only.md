# `strata-hy4 --dfly-alloc-only`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--dfly-alloc-only` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

オフライン実行で DFly2 を有効にしたとき、DFly2 の初期化・作業領域確保を行いつつ、通常の投機デコード経路を選ばないためのフラグです。`--draft dfly2` と `--gen N`（`N > 0`）を併用すると、通常は DFly2 による投機デコードへ進みますが、このフラグを付けると投機経路を抑止し、後続の通常デコード分岐へ進みます。DFly2 の初期化自体を省く指定ではありません。

## 使い方

```sh
# DFly2 を初期化し、生成は通常デコード経路で行う
strata-hy4 --model model.strata --engram engram.strata --tokens prompt.ids \
  --draft dfly2 --gen 16 --dfly-alloc-only
```

実行には利用可能な CUDA/HIP GPU と対象モデルが必要です。上記のファイル名は例です。

## 値と既定値

値は不要です。引数解析で指定を受けると `alloc_only` が `true` になります。省略時は `false` です。同じフラグを複数回指定した場合も真偽値を `true` にするだけで、回数による差はありません。値を要求する処理や、このフラグ固有の数値 validation はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:374-375, 433`）。

## 実行時の動作

オフライン経路では `spec_mode` は `--draft dfly2`、生成数が正、かつ `--dfly-alloc-only` が未指定の場合にだけ真になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:701`）。そのため指定時は `--gen N` が正でも DFly2 投機デコード分岐を選ばず、`gen > 0` なら後続の通常デコード分岐に進みます（同 `:992-1018`）。

一方、モデル読み込みと `Runner::init` の後、`draft == "dfly2"` なら `DFly2::init` は引き続き呼ばれます（同 `:703-715`）。初期化はモデルに DFly2 の必須 tensor があることと空き VRAM を確認し、DFly2 用の device/host バッファを確保して投影テーブルを組み立てます（`engine/src/hy4flash/run/hy4_dfly2.hip.h:470-525, 526-570`）。したがってこのオプションは「DFly2 のメモリ確保だけを行い、モデル処理も生成も一切しない」モードではありません。プロンプトがある通常のオフライン実行では、後続の prefill は行われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:748-770`）。

## 適用条件と副作用

- 主な効果はオフライン経路の `spec_mode` 判定に限られます。`--draft` の既定値は `auto` で、ソースコメント上、オフライン CLI では drafter を無効にするため、このオプション単独では DFly2 を初期化しません。明示的に `--draft dfly2` を指定する必要があります（`engine/src/hy4flash/run/hy4_main.hip.cpp:363, 701, 711-715`）。
- `--serve` 経路は `spec_mode` の判定より前に serve handler へ戻るため、このフラグによるオフライン投機デコード抑止は適用されません（同 `:544-611, 701`）。serve モードでのフラグの実行時効果は確認できません。
- `--load-only` は GPU モデルのロード後、`DFly2::init` より前に正常終了するため、併用時は DFly2 作業領域の確保まで到達しません（同 `:658-665, 711-715`）。
- `--dfly-warm` も併用した場合、投機デコードは抑止されますが、通常デコード分岐内で drafter の warm-up 呼び出しが行われ得ます（同 `:1018-1029`）。
- 初期化は VRAM を消費し、成功時にも prefill や通常生成の GPU 処理が続く場合があります。指定による性能向上はソースからは判断できません。

## 出力とエラー

`DFly2::init` はモデルに DFly2 tensor がない場合 `this .strata has no DFly2 drafter tensors`、空き VRAM が 192 MiB 未満の場合 `insufficient free VRAM for DFly2 drafter (...)` を返します。呼び出し側は `dfly2: <理由>` を標準エラーへ出して終了コード `1` を返します（`engine/src/hy4flash/run/hy4_dfly2.hip.h:470-483`; `engine/src/hy4flash/run/hy4_main.hip.cpp:712-715`）。GPU 割り当てなど他の失敗経路は `HCK` 等の実装にも依存するため、このフラグ固有の出力・終了コードとしては断定しません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-375, 429-435` — `draft` と `alloc_only` の初期値、引数解析。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611, 658-715` — serve 経路、モデル/Runner 初期化、`--load-only` の早期終了、DFly2 初期化。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701, 748-770, 914-1018` — 投機モード条件、prefill、投機・通常デコードの分岐。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:1024-1029` — `--dfly-warm` との相互作用。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:470-570` — DFly2 tensor / 空き VRAM 検査、作業領域確保と初期化。
