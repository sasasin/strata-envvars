# `strata-hy4-metal --pair-max`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--pair-max` |
| 別名 | なし |
| 値 | 整数。既定値は `4`。 |

## 役割

Metal runner が MoE の fallback 経路で使う pair GEMV を、何トークン以下の入力で選ぶかを指定する。ここで比較されるのはルーティング済みの expert pair 数ではなく、処理中のトークン数 `T` である。値は Metal の実行計画にのみ影響し、モデル出力や生成トークン数を直接指定するものではない。

## 使い方

```sh
# offline 実行で pair GEMV の対象上限を 8 トークンにする
strata-hy4-metal --model model.strata --tokens prompt.ids --pair-max 8 --gen 16
```

`--serve` でも引数としては受理されるが、serve 用の `ServeOpts` へ値を渡す処理がなく、serve 実行には反映されない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`）。`--load-only` は runner 作成前に終了するため、このオプションによる計算経路の変更はない（同 `:1635`）。

## 値と既定値

- 省略時の `pair_max` は `4`（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491`）。
- `--pair-max` の値は `atoi` で整数へ変換され、同一オプションを複数回指定した場合は最後に読んだ値が残る（同 `:1504-1506`, `:1525`）。数値として解釈できない文字列は `atoi` により `0` となり、数値の後ろに非数値文字が続く場合は数値部分が使われる。明示的な範囲検査やエラー報告はない。
- `0` または負数では正の `T` が `T <= pair_max` を満たさないため、pair 経路は選ばれない。正の値に上限検査はない（同 `:1228`）。

## 実行時の動作

offline 実行では parser の値が `Runner::pair_max` にコピーされ（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1720-1729`）、各 MoE 層の実行計画で参照される。`T` は `forward_chunk` に渡すトークン数で、通常の prefill では入力を `Tc` 以下の chunk に分け、生成時の各 decode 呼び出しでは `T=1` となる（同 `:1291-1294`, `:1789-1795`, `:1951-1958`）。

MoE の経路は次の順で判定される。

1. `--no-moe2` が指定されておらず `T <= 8` なら、既定で有効な distinct-expert decode/verify 経路が先に選ばれる。この場合 `--pair-max` は参照されない（同 `:363`, `:1174-1181`, `:1550`）。
2. それ以外で MPP grouped GEMM が利用可能かつ `T >= moe_mm_min` なら MPP 経路が選ばれる。`moe_mm_min` の既定値は `64`。`--moe-mm-min` と `--no-mpp` がこの条件に関係する（同 `:328`, `:337`, `:533-555`, `:1182-1184`, `:1527`, `:1546`, `:1730`, `:1752`）。
3. 上記のどちらにも該当しない場合に `T <= pair_max` なら `moe_gu_pair` と `moe_dn_pair` を追加し、そうでなければ route/sorted kernel 群を使う（同 `:1226-1238`）。

したがって `--pair-max` は MoE 経路選択の fallback 内でのみ効く。既定の `--no-moe2` なしでは `T <= 8` の decode/verify に効かず、MPP が選ばれる大きな prefill chunk にも効かない。pair 経路を decode/verify で試す場合は、たとえば `--no-moe2 --pair-max 4` のように指定する。Metal kernel のコメントは pair 経路を decode の少数 token 向けと説明している（`engine/src/hy4flash/metal/hy4.metal:850-883`）。

## 適用条件と副作用

- runner の Metal 実行計画で GPU kernel の選択を変える。ファイルや設定の書き換えはこのオプション自体からは行わない。
- `--no-moe2`、MPP の利用可否、`--moe-mm-min` が優先して別経路を選ぶ場合、この値は使われない。MPP 利用可否は MPP kernel のコンパイル結果にも依存する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-555`）。
- serve 実行では parser が値を保持しても serve 側へ転送されないため、効果を確認できない。serve 側の内部既定値の詳細はこのオプション文書の調査範囲外。

## 出力とエラー

このオプション固有のログ、警告、範囲エラーは確認できない。値は検証されず実行計画の分岐に使われる。数値引数を欠いたときの挙動は `nxt()` が `argv[++i]` を読む実装から安全には規定できないため、値を省略しないこと（同 `:1504-1506`, `:1525`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1525` — 既定値、`atoi` による parser 登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:355,1720-1729` — runner の既定値と parser 値の設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1174-1238` — MoE 経路の優先順位と `pair_max` による fallback 分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1674` — load-only の早期終了と serve 用構造体への値の非転送。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1789-1795,1951-1958` — offline prefill chunk と生成時 decode の `T`。
- `engine/src/hy4flash/metal/hy4.metal:850-883` — pair kernel が decode 向けであることの実装コメント。
