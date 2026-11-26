# `--rope-freq-scale`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--rope-freq-scale` |
| 別名 | なし |
| 値 | 浮動小数点数 `F`。有限かつ 0 以上。上限はコード上で定められていない |

## 役割

RoPE の角度に掛ける頻度スケールを指定する。`--rope-scaling` が `linear` または `yarn` のとき、正の値は `--rope-scale` から得る既定の縮小率 `1 / factor` を上書きする。0（既定値）は明示的な率を指定せず、`1 / factor` を使う。これは起動時に解決され、実行中の RoPE 回転に適用される。

## 使い方

```sh
# YaRN、factor 4 の既定縮小率 1/4 を使う
strata generate --pack pack/full --tokens "1,2,3" --rope-scaling yarn --rope-scale 4

# YaRN、factor 4 に対して角度縮小率を 0.5 に上書きする
strata generate --pack pack/full --tokens "1,2,3" --rope-scaling yarn --rope-scale 4 --rope-freq-scale 0.5
```

## 値と既定値

- parser は `std::atof` で値を読み、格納先の初期値は 0。オプションを省略した場合も 0 となる（`engine/src/program/generate.cpp:796,3875`）。
- 数値が有限で 0 以上であることを検査する。負値、NaN、無限大は拒否される。正の上限は設けられていない（`engine/src/program/generate.cpp:5243-5264`; 共通設定検査は `engine/include/strata/kernels/rope_scaling.hpp:169-182`）。
- 0 の場合、スケーリング種別が `none` でなければ `1 / factor` が解決値になる。正値の場合はその値が解決値になる（`engine/include/strata/kernels/rope_scaling.hpp:77-85`）。
- 同じオプションを複数回指定すると parser のループで同じ変数へ順に代入され、後の値が残る（`engine/src/program/generate.cpp:3842-3847,3875`）。値の変換結果が 0 になる文字列について、parser は変換失敗を別途検出していない（`engine/src/program/generate.cpp:3875`）。
- 値を省略すると `--rope-freq-scale needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3844-3846`）。

## 実行時の動作

parser が受け取った値は `RopeScaling::freq_scale_in` に渡される。RoPE 設定の解決後、種別が `linear` または `yarn` なら正値を角度縮小率として使い、0 なら `1 / factor` を使う。角度縮小率は各位置の RoPE 回転角に適用される（`engine/src/program/generate.cpp:5721`; `engine/include/strata/kernels/rope_scaling.hpp:77-85,148-161`）。

`factor` は `--rope-scale` の値、またはそれが未指定ならモデルの RoPE metadata が持つ値（1 より大きい場合）から解決される。従って本オプションが 0 のときはその `factor` に連動する。RoPE 種別自体は明示した `--rope-scaling` が優先され、指定がなければモデル metadata が参照される（`engine/src/program/generate.cpp:5700-5723`）。

`none` が選ばれた場合、この値を含むスケーリング knob は回転に使われず、設定が初期状態へ戻される。`--rope-freq-scale` が正値なら、他の関連 knob とともに「スケーリングは無効で、指定値は効果がない」という注記を stderr に出す（`engine/src/program/generate.cpp:5727-5739`）。構成全体の検査後、設定は `rope_scaling_set` で起動時に登録される（`engine/src/program/generate.cpp:5749-5759`）。

## 適用条件と副作用

- 通常のエンジン parser と SYCL parser の双方に同じ引数処理・範囲検査・設定解決がある（通常版: `engine/src/program/generate.cpp:3875,5243-5264,5721`; SYCL 版: `engine/sycl/src/program/generate.cpp:1914,2657-2679,2995`）。
- この値はプロセス起動時に固定される。RoPE 設定は session 初期化より前に確定し、その後の回転で参照される（`engine/src/program/generate.cpp:5759`; `engine/include/strata/kernels/rope_scaling.hpp:186-190`）。
- 不正な設定では回転処理へ進まず終了する。ファイルやネットワークへの副作用を本オプション自身が起こす箇所は確認できなかった。

## 出力とエラー

- 値が有限でない、または負の場合は rope knob のエラーを stderr に出し、終了コード 2 で終了する（`engine/src/program/generate.cpp:5243-5264`）。
- `--rope-scaling none` などで関連 knob が無効になる場合は stderr に注記を出す（`engine/src/program/generate.cpp:5727-5739`）。スケーリングが有効なら、解決した種別・factor・freq_scale 等を stderr に表示する（`engine/src/program/generate.cpp:5760-5778`）。
- モデル metadata と CLI 値から組み立てた設定全体が不正な場合も、理由を stderr に出して終了コード 2 となる（`engine/src/program/generate.cpp:5749-5757`; 検査規則は `engine/include/strata/kernels/rope_scaling.hpp:169-182`）。

## 根拠

- `engine/src/program/generate.cpp:796,1268-1279,3872-3879`: 値の初期値、help 表示、parser 登録。
- `engine/src/program/generate.cpp:3842-3847,5243-5264`: 値の取得、欠落時エラー、finite・範囲検査。
- `engine/src/program/generate.cpp:5700-5759`: モデル値との解決、無効時の扱い、構成検査と起動時登録。
- `engine/include/strata/kernels/rope_scaling.hpp:66-85,148-182`: 0 の解決規則、回転角への適用、構成全体の検証。
- `engine/sycl/src/program/generate.cpp:1911-1917,2641-2679,2976-3024`: SYCL parser と設定解決・検査が通常版と同等であること。
