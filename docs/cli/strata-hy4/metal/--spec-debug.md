# `strata-hy4-metal --spec-debug`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal`（Metal backend、サブコマンドなし） |
| オプション | `--spec-debug` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Speculative decoding が実行されるとき、各 speculative iteration の進行状況と時間・confidence の診断行を標準エラーへ出します。通常の生成結果を変える設定値ではなく、`SpecCfg::debug` を有効にするフラグです。既定値は `false` です（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --tokens prompt_ids.txt --gen 128 --draft dfly2 --spec-debug
```

モデルに DFly2 drafter が含まれ、Metal runner で speculative decoding が有効になる条件を満たす場合の例です。`--spec-debug` 自体に値は付けません。

## 値と既定値

- 引数解析は `--spec-debug` に一致したとき `scfg.debug = true` とします。数値などの値は読み取らず、既定値は `SpecCfg` の `debug = false` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1556-1565`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-585`）。
- 同じフラグを複数回指定した場合も真を代入するだけで、別の動作は定義されていません（同 `hy4_metal_main.cpp:1559`）。
- オプション固有の値検証はありません。未対応の別フラグは `ERR unknown flag ...` を標準出力、`unknown arg ...` を標準エラーへ出し、終了コード `2` になります（同 `hy4_metal_main.cpp:1603-1609`）。

## 実行時の動作

`scfg` は `SpecCfg` の既定値で初期化され、パーサーでこのフラグが現れると `debug` が有効になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1559`）。Speculative decoding の各 iteration では `cfg.debug` が真のとき、標準エラーに `[spec]` 行を出します。この行には位置 `a`、候補数 `T`、分岐の有無 `branched`、受理数 `n`、draft/verify の時間、GPU/Engram の時間、先頭候補の confidence が含まれます（`engine/src/hy4flash/metal/hy4_metal_spec.h:934-940`）。

通常のオフライン実行では `scfg` が `Spec` に渡るのは speculative mode の経路です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1898-1912,1929-1941`）。この mode は生成・ベンチマーク・parity のいずれかが要求され、モデルに DFly2 用 tensor があり、context が16以上、`--all-logits` ではなく、画像入力がない場合に限り有効です。また `--draft off` では無効になります（同 `hy4_metal_main.cpp:1755-1761`）。したがってこの条件を満たさない通常実行ではフラグを受理しても iteration 診断行は出ません。

`--serve` 経路にも設定が渡されます（同 `hy4_metal_main.cpp:1636-1657`）。serve 側ではモデルに DFly2 用 tensor があり、context が16以上で `--draft off` でない場合に drafter 初期化を試み、成功した場合に `Spec` を作ります（`engine/src/hy4flash/metal/hy4_metal_serve.h:233-254`）。serve 中も speculative iteration が実行されたときに同じ診断出力条件が適用されます。

## 適用条件と副作用

- Metal backend の `strata-hy4-metal` 専用です。SYCL と HIP にも同名の parser 分岐がありますが、別ツールの実装なのでこの文書の対象外です（索引 `docs/cli/README.md:1358-1360`、Metal parser `engine/src/hy4flash/metal/hy4_metal_main.cpp:1559`）。
- 診断出力は stderr に追加されます。Speculative decoding が実行されない場合、このフラグによる診断行はありません。
- 本フラグがファイルやモデルを変更する処理は確認できません。ログ出力以外の副作用・アルゴリズム変更はコード上で確認できませんでした。

## 出力とエラー

Speculative iteration ごとの診断行は `fprintf(stderr, ...)` による出力です（`engine/src/hy4flash/metal/hy4_metal_spec.h:938-940`）。このフラグ固有の拒否経路やエラー出力はありません。モデルファイルや DFly2 初期化に起因する失敗は別の実行条件によるもので、このフラグの値検証ではありません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502,1556-1565` — `SpecCfg` の生成と CLI parser。`--spec-debug` が値なしで `scfg.debug = true` を設定する。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:576-585` — `SpecCfg` の既定値。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:934-940` — debug 有効時の iteration 診断出力。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1761,1898-1941` — offline の適用条件と `Spec` 実行経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1657`、`engine/src/hy4flash/metal/hy4_metal_serve.h:233-254` — serve 設定の転送と speculative decoding の初期化条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609` — 不明フラグの出力と終了コード。
