# `--yarn-attn-factor`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--yarn-attn-factor` |
| 別名 | なし |
| 値 | 正の有限浮動小数点数 `F` |

## 役割

RoPE の実行時設定で、回転位置埋め込みの cos/sin に掛ける追加の振幅係数を指定します。YaRN など RoPE scaling が有効なときに使われ、角度の周波数補間を指定する `--rope-scale` などとは別に、回転値の大きさを調整します。既定値は `1.0` です。

## 使い方

```sh
# モデルのトークン 1 を入力し、YaRN を有効にして振幅係数を 1.2 にする
strata generate --pack MODEL.gguf --tokens 1 \
  --rope-scaling yarn --rope-scale 2 --yarn-attn-factor 1.2
```

## 値と既定値

- `F` は `std::atof` で `double` に変換され、既定値は `1.0` です。複数回指定した場合、parser は各値を同じフィールドへ順に代入するため、最後の値が残ります。
- RoPE の各 knob は有限値である必要があり、このオプションは `F > 0` が必要です。`0`、負数、NaN、無限大は拒否されます。文字列を `atof` が数値として変換できない場合は `0` となり、正数条件で拒否されます。
- オプション名の後に値がない場合は `--yarn-attn-factor needs a value` を stderr に出し、終了コード `2` で終了します。

## 実行時の動作

parser は値を `Options::yarn_attn_factor` に格納します。RoPE 設定解決時に `RopeScaling::attn_factor` へ渡され、RoPE type が `linear` または `yarn` なら、回転の cos/sin の大きさに適用されます。実装上の magnitude correction は `ext_factor == 0` のとき `attn_factor`、それ以外では `attn_factor * (1 + 0.1 * ln(1 / freq_scale))` です。したがって YaRN の correction が有効な場合は `--yarn-ext-factor` や周波数スケールとの組み合わせで最終係数も変わります。

このオプション単独では RoPE type を `yarn` に切り替えません。type は `--rope-scaling`、または（CLI で type を指定しない場合）モデル GGUF の `rope.scaling.type` から解決されます。モデルの RoPE attention factor はこの engine の解決箇所で読み込まれず、CLI option の既定値 `1.0` が常に設定へ渡されます。

設定は起動時に一度解決され、session 初期化前に process の RoPE 設定へ登録されます。リクエストごとに変更する引数ではありません。

## 適用条件と副作用

- `--rope-scaling none`、またはモデル設定から解決した type が `none` の場合、他の scaling knob とともに RoPE 設定が初期値へ戻され、この値は効果を持ちません。`F != 1.0` なら stderr に「RoPE scaling は active でないため `--yarn-*` は効果がない」という注記が出ます。
- type が `linear` / `yarn` の場合、解決後の全体設定も検証され、magnitude correction が有限かつ正であることが確認されます。全体設定が不正なら推論開始前に拒否されます。
- 標準 engine と SYCL engine の parser、既定値、範囲検証、RoPE 設定反映は同じ実装です。

## 出力とエラー

- `F` が有限でない場合、または RoPE knob の範囲外の場合、stderr に RoPE knob のエラーを出し終了コード `2` で終了します。
- 解決済み RoPE 設定が不正な場合は、stderr に理由と type・factor 等の設定値を表示して終了コード `2` で終了します。
- scaling が有効なら stderr に scaling type、factor、`mscale` 等が表示されます。`mscale != 1.0` のときは cos/sin に掛かる magnitude correction について追加注記があります。
- `none` により値が無効化された場合でも、正数・有限値の CLI knob 検証は先に実行されます。

## 根拠

- `engine/src/program/generate.cpp:799, 1278-1279, 3872-3880` — フィールド既定値、usage 表示、parser の数値変換。
- `engine/src/program/generate.cpp:3842-3847, 5243-5264` — 値の欠落時の終了、有限値・正数検証と失敗経路。
- `engine/src/program/generate.cpp:5650-5673, 5700-5726` — GGUF の scaling metadata 読み込みと、CLI 値を解決済み設定へ反映する順序。
- `engine/src/program/generate.cpp:5727-5759, 5760-5778` — `none` での無効化、全体設定の検証・登録、stderr の通知。
- `engine/sycl/src/program/generate.cpp:483, 1917, 2657-2678, 2998-3024, 3037-3043` — SYCL engine の対応する既定値、parser、検証、効果と出力。
- `engine/include/strata/kernels/rope_scaling.hpp:66-90, 102-116, 169-183, 186-190` — `RopeScaling` の意味、magnitude 計算、正当性検査、起動時登録の契約。
- `engine/include/strata/kernels/rope_scaling.hpp:148-161` — resolved magnitude correction を回転 cos/sin に適用する処理。
