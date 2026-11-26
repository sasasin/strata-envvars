# `strata generate --yarn-beta-slow`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--yarn-beta-slow` |
| 別名 | なし |
| 値 | 正の有限浮動小数点数 `F` |

## 役割

YaRN RoPE の補正帯の低周波側の境界を決める beta 値です。YaRN の補正が有効な設定では、値が RoPE 補正帯の終端位置の計算に使われます。エンジン起動時に一度設定され、リクエストごとの切り替えには使われません。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens "1,2,3" \
  --rope-scaling yarn --rope-scale 2 --yarn-beta-slow 1
```

`--pack` と `--tokens` はエンジンの入力例です。実際のモデルとトークン列に置き換えてください。

## 値と既定値

- 値は `std::atof` で `double` に変換され、既定値は `1.0` です。パーサーでは同じオプションを複数回指定でき、後の値が前の値を置き換えます（`engine/src/program/generate.cpp:800-801,3879-3880`）。
- 起動時に有限値であること、かつ `0` より大きいことが検証されます。`0`、負数、NaN、無限大は拒否されます（`engine/src/program/generate.cpp:5243-5248,5260-5265`）。
- 数値引数を省略すると `--yarn-beta-slow needs a value` を標準エラーへ出して終了コード `2` になります（`engine/src/program/generate.cpp:3842-3847`）。

## 実行時の動作

パーサーは受け取った値を `Options::yarn_beta_slow` に格納します。起動時に RoPE 設定へコピーされ、その後 `RopeScaling::corr_dims` が `rope_yarn_corr_dim(..., beta_slow, ...)` を計算し、補正帯の終端を `ceil` した位置として使います。したがって値は他の RoPE 設定（元の学習コンテキスト、周波数基底、回転次元）とともに、どの回転ペアから補間・外挿を切り替えるかに影響します（`engine/src/program/generate.cpp:5721-5726`; `engine/include/strata/kernels/rope_scaling.hpp:92-100,120-127`）。

設定は `session_init` より前にプロセス共通で確定します。モデルファイルから beta 値を読み込む処理はこの起動経路に見当たらず、CLI の既定値または明示値が `RopeScaling` に設定されます（`engine/src/program/generate.cpp:788-801,5721-5726`; `engine/include/strata/kernels/rope_scaling.hpp:186-190`）。

補正帯は `ext_factor` が 0 でない場合に角度計算へ反映されます。通常の YaRN 設定では既定の自動値が `1` となり補正が有効ですが、RoPE scaling type が `none` なら設定値はリセットされ、補正は行われません。`none` の場合も CLI 値自体は正の有限値として検証されます。type が `linear` で `ext_factor` が 0 の通常設定でも beta 値は回転計算に影響しません（`engine/src/program/generate.cpp:5722-5739`; `engine/include/strata/kernels/rope_scaling.hpp:102-115,148-160`）。

## 適用条件と副作用

RoPE の起動時設定だけを変え、ファイルやネットワークへの副作用はありません。標準エンジン parser のほか SYCL エンジン parser にも同名の引数、既定値、範囲検証、RoPE 設定への反映があります（`engine/sycl/src/program/generate.cpp:481-485,1915-1919,2657-2679,2995-3000`）。

## 出力とエラー

- 値が有限でない場合は `strata generate: a rope scaling knob is not a finite number (...)`、beta が `0` 以下の場合は `strata generate: invalid rope scaling knob (...)` を標準エラーへ出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:5243-5248,5260-5265`）。
- YaRN 補正を使う解決済み設定は共通の RoPE 検証にも渡され、無効なら `invalid rope scaling configuration: ...` を標準エラーへ出して終了コード `2` になります（`engine/src/program/generate.cpp:5749-5759`; `engine/include/strata/kernels/rope_scaling.hpp:164-183`）。

## 根拠

- `engine/src/program/generate.cpp:788-801,3879-3880` — オプション状態と parser 登録。
- `engine/src/program/generate.cpp:3842-3847,5243-5265` — 値省略時の処理と有限値・正数の検証。
- `engine/src/program/generate.cpp:5721-5739,5749-5759` — 起動時の設定反映、`none` 時の無効化、解決済み設定の検証。
- `engine/include/strata/kernels/rope_scaling.hpp:92-100,120-127,148-160` — beta 値による補正帯境界の計算と回転角への適用条件。
- `engine/sycl/src/program/generate.cpp:481-485,1915-1919,2657-2679,2995-3000` — SYCL parser と対応する検証・設定反映。

範囲はこの revision の Strata 所有ソースにある標準および SYCL エンジン実装です。GPU 実行や数値性能の測定は行っていません。
