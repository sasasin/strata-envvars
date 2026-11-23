# `--no-f32x`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--no-f32x` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

オフライン実行の Metal runner で、対応する float32 線形演算に使う `linear_f32x_*` カーネルを選ばないようにします。対象は全ての計算ではなく、`lin_f32` が処理する行数 1〜8、かつ入力列数が 128 の倍数である演算です。この条件を外れる演算には影響しません。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt-ids.txt --gen 32 --no-f32x
```

## 値と既定値

値を取りません。指定すると parser 内の `no_f32x` が `true` になり、未指定時は初期値 `false` です。繰り返し指定しても同じ `true` のままです。数値などの値を後ろに付ける構文はありません。

このフラグ固有の範囲検証はありません。parser は未知の引数を `unknown flag` として標準出力と標準エラーに出し、終了コード 2 で終了します。モデル指定がない場合も usage を標準エラーに出して終了コード 2 です。

## 実行時の動作

parser はフラグを `no_f32x` に記録し、オフライン runner の設定で `r.f32x = !no_f32x` とします。`lin_f32` は行数 `M >= 16` なら `linear_f32_mm` を使い、`M` が 1〜8 かつ列数が 128 の倍数で `f32x` が有効なら `linear_f32x_<M>` を投入します。`--no-f32x` を指定した場合、またはこの条件を満たさない場合は `linear_f32` にフォールバックします。現行ソースで `lin_f32` を呼び出すのは各層の `mlp.gate.weight` の処理です。

`--serve` も同時に指定した場合、parser はフラグを受理しますが、server 分岐は `Runner` の生成と `r.f32x` への代入より前に実行されます。そのため、このフラグは server 実行の設定には反映されません。`--load-only` や `--info` など早期終了する経路でも、オフラインのカーネル選択には到達しません。

## 適用条件と副作用

適用されるのは `strata-hy4-metal` のオフライン推論経路で `lin_f32` が実行される場合です。`M >= 16` は別の `linear_f32_mm` 経路であり、このフラグの影響を受けません。Metal カーネル呼び出しの選択を変えますが、この選択による速度・精度の差はソースコードだけでは確定できません。

## 出力とエラー

このフラグ自体に成功時の表示、警告、専用の失敗経路はありません。通常のカーネル実行や推論で発生するエラーは、フラグ固有のものとして区別されていません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1503` — `no_f32x` の初期値は `false`。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1553` — `--no-f32x` を値なしフラグとして受理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609` — 一部の別フラグは値を読んで未使用警告を出し、それ以外の未知引数は終了コード 2 で拒否。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1614` — モデル未指定時の usage と終了コード 2。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1674` — `--load-only` と `--serve` の分岐位置。`--serve` は runner の設定より前に処理される。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1715-1737` — オフライン `Runner` を作り、`r.f32x` にフラグの反転値を設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:481-520` — float32 演算の dispatch 条件と `linear_f32x_*` / `linear_f32` の選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1132-1148` — `lin_f32` の呼び出し箇所が MoE `mlp.gate.weight` であること。
- `docs/cli/README.md:1358-1361,1403` — `strata-hy4-metal` のコマンド scope と対象リンク。

調査では parser とその参照先を確認しました。同一 revision の `--help` 実行結果は確認していません。
