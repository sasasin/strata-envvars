# `strata-hy4 --spec-exact`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4` |
| オプション | `--spec-exact` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換し、0 は無効、0 以外は有効 |

## 役割

DFly2 speculative decoding の検証窓について、線形層と MoE decode の GEMV 系カーネルを使う上限を広げます。有効時は通常、M（窓の行数）が最大 16 までの検証で、行ごとに M に依存しない GEMV/decode カーネルを選べるようにします。これは speculative decoding の検証経路の設定で、通常の生成経路を単独で有効化するオプションではありません。既定値は有効です。

## 使い方

```sh
# DFly2 を使うオフライン生成で、既定の exact 検証を明示する
strata-hy4 --model Hy4-Flash.strata --engram Engram-Q8.strata \
  --tokens prompt-ids.txt --draft dfly2 --gen 64 --spec-exact 1

# serve で exact 検証を無効にする
strata-hy4 --serve --model Hy4-Flash.strata --draft dfly2 --spec-exact 0
```

## 値と既定値

- 値は必須です。parser は次の引数を `atoi` で整数変換し、その結果が 0 かどうかで boolean にします。`1` は有効、`0` は無効で、負数を含めた他の整数も有効になります。整数として解釈できない文字列は `atoi` の結果が 0 となり、無効として扱われます。数値範囲の検証や専用の不正値エラーはありません。`--spec-exact` を複数回指定した場合は、最後に読んだ値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:364,442`）。
- 未指定時は `SpecCfg::exact` の初期値 `true` です（`engine/src/hy4flash/run/hy4_spec.hip.h:18-23`）。
- 値を省略すると次の引数を値として消費します。コマンド末尾など値がない場合は `ERR --spec-exact needs a value` を stdout に出して終了コード 2 で終了します（共通の値取得処理: `engine/src/hy4flash/run/hy4_main.hip.cpp:376-384`）。

## 実行時の動作

parser は値を `scfg.exact` に格納し、`--serve` では `ServeOpts` にコピーします。オフライン生成では `--draft dfly2` かつ `--gen` が正で、`--dfly-alloc-only` がないと speculative 経路になり、その `Spec` に設定を渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:701,556,992-1000`）。A/B 比較の speculative 実行も同じ設定から `Spec` を作ります（同ファイル `:914-965`）。

`Spec` の構築時、設定が有効なら `skd::moe_dec_max_m()` と `skd::lin_gemv_max_m()` を 16 に設定します。これらの上限は MoE decode および線形層の M 行カーネル選択に使われます（`engine/src/hy4flash/run/hy4_spec.hip.h:74-89`、`engine/src/hy4flash/run/skmoe.hip.h:1478-1480,1510`、`engine/src/hy4flash/run/skhy4.hip.h:28-31,47-54`）。無効時はこのオプションによる上限変更をしません。基準値はビルド・GPU 条件で異なり、たとえば `lin_gemv_max_m()` は既定で通常 4、`!HY4_MMA` または RDNA2 では 16 です（`engine/src/hy4flash/run/skhy4.hip.h:29-31`）。

HIP の RDNA4（`HY4_MMA`）では、有効でも gfx12 デバイス上で `--spec-check` と `HY4_SPEC_FORCE_GEMV` のどちらも有効でなければ、上限 16 への変更を行いません。ソースコメントはこの条件で M=5..8 を Wave32 WMMA に残すと説明しています。`--spec-check` は `--spec-exact 0` を上書きせず、exact 設定が有効なときだけこの分岐の判定に使われます（`engine/src/hy4flash/run/hy4_spec.hip.h:77-89`）。

## 適用条件と副作用

- 対象は索引上の `strata-hy4`（CUDA/HIP）root parser です。Metal と SYCL は別の CLI scope であり、このオプション文書の対象外です（`docs/cli/README.md:1279,1358,1452`、`docs/cli/000_cli_tools.md:11`）。
- serve では `--draft off`、計画された chunk が 8 未満、または DFly2 drafter の初期化失敗の場合、`Spec` が作られずこの設定は使われません。chunk が 8 未満の場合や drafter 初期化失敗は serve を継続して drafter なしで動作します（`engine/src/hy4flash/run/hy4_serve.hip.h:319-341`）。
- オフライン実行では `--draft dfly2` で DFly2 を初期化した後、生成を行う speculative mode に入る場合に適用されます。既定の `--draft auto` は CLI runs では DFly2 を無効にし、serve では自動選択する設定です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,701,712-715,992-993`）。
- カーネルの選択上限を変えます。ファイルの変更や独立したネットワーク処理はありません。性能向上はこのソース調査だけでは保証できません。

## 出力とエラー

このオプションの値に対する専用の validation error、警告、出力はありません。値がない場合の stdout と終了コード 2 は「値と既定値」を参照してください。未知の引数は stderr に `unknown arg ...` を出して終了コード 2 になります（serve 時は加えて protocol 用の `ERR unknown flag ...` を stdout に出します）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:364,442` — `SpecCfg` の既定インスタンスと parser の値変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:376-384,498-505` — 値不足時と未知引数の失敗経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:556,701,914-965,992-1000` — serve 設定への転送とオフライン/A-B の `Spec` 生成。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30,74-97` — 既定値、上限変更、RDNA4 での条件、関連設定。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341` — serve で drafter と speculative decoder が有効になる条件。
- `engine/src/hy4flash/run/skmoe.hip.h:1478-1480,1510`、`engine/src/hy4flash/run/skhy4.hip.h:28-31,47-54` — 上限値とカーネル分岐での利用。
