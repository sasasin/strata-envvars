# `--temperature`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--temperature` |
| 別名 | なし |
| 値 | 浮動小数点数として `atof` で変換される値 |

## 役割

通常の CLI 生成経路で、次トークンのサンプリング温度を指定します。既定値は `0` で、貪欲選択（greedy）です。正の値では sampler が候補 logits を温度でスケールして確率的に選びます。

## 使い方

モデル pack と prompt token ID を指定して生成する例です（`--pack` の値は利用環境の pack ディレクトリに置き換えます）。

```sh
strata-dsv41 --pack /models/example/maya-ds4 --ids 1,2,3 --n 128 --temperature 0.7
```

## 値と既定値

- 値を1つ取ります。parser は `std::atof` で `float` に変換し、同じオプションを複数回渡すと後の値が使われます。
- 省略時は `0.0f` です。`temperature <= 0` は貪欲選択として扱われます。正の値はサンプリング経路に渡されます。
- このオプション専用の範囲検証や上限・下限の clamp は parser にありません。`atof` が数値として変換できない文字列を受け取った場合は 0 相当になり、貪欲選択になります。
- 値を省略すると `--temperature needs a value` を stderr に出して終了コード 2 で終了します。

## 実行時の動作

通常の生成で `--n` が正の場合、最初の token 選択と後続の decode round の両方に温度が渡されます。通常生成では `top_p=1.0`、`min_p=0.0`、温度が正なら `top_k=64`、それ以外は `top_k=1` です。sampler は候補の top-k/top-p/min-p による選別後に logits を `1 / temperature` 倍し、その分布から選択します。したがって温度は候補集合の truncation 条件を直接変えず、選別後の確率分布に作用します。

`--serve` を指定した場合、この root オプションの値は serving request の温度として使われません。各 `GEN`/`GENI` request の `temperature=F` キーが使われ、request 側の既定値は `0.0f`（貪欲）です。`--spec-eval` も生成時に `0.0f` を直接渡すため、root の値は反映されません。`--score`、`--profile-run`、画像 encode など、token 生成を行わない経路でも温度の使用箇所には到達しません。

## 適用条件と副作用

- `strata-dsv41` は CMake の `STRATA_BUILD_DSV41=ON` で生成される独立 engine executable で、この build option は既定で OFF です。索引は Release での配布有無を断定していません。
- 通常生成では `--n N` が正の場合に token を生成します。生成 token は stdout にカンマ区切りで出力され、計測情報は stderr に出力されます。
- 温度値自体に対して warning や補正を行う専用処理は確認できません。異常な浮動小数点値（例: NaN、無限大）の生成結果は別途検証されていないため、ここでは規定しません。

## 出力とエラー

- parser が値を読めない場合は stderr にエラーを出し、終了コード 2 です。
- オプション名が不明な場合は `unknown option ...` と usage を stderr に出し、終了コード 2 です。
- temperature の数値範囲エラー専用の出力・終了経路はありません。生成途中の sampler kernel 起動失敗は `sample_tokens launch: ...` を stderr に出してプロセスを終了しますが、これは温度固有の validation ではありません。

## 根拠

- 索引上の分類と対象範囲: `docs/cli/README.md:1353-1397`（`strata-dsv41`、温度文書のリンク、build option・配布範囲）。
- build target と既定状態: `CMakeLists.txt:797-811`。
- parser の既定値・変換・不足値・未知 option の処理: `src/dsv41/ds4_main.cpp:1191-1207`, `src/dsv41/ds4_main.cpp:1246-1273`。
- 通常生成が温度を sampler と speculative round に渡す箇所: `src/dsv41/ds4_main.cpp:1385-1405`。
- sampler で `temperature <= 0` を greedy として扱い、候補選別後に温度を適用する箇所: `src/dsv41/ds4_model.cu:8966-8982`, `src/dsv41/vendor/sampler.cu:191-193`, `src/dsv41/vendor/sampler.cu:403-440`, `src/dsv41/vendor/sampler.cu:514-539`。
- serve request の温度既定値・`temperature=` の読み込みと、request 値で sampling する箇所: `src/dsv41/ds4_main.cpp:206-219`, `src/dsv41/ds4_main.cpp:283-315`, `src/dsv41/ds4_main.cpp:842-843`, `src/dsv41/ds4_main.cpp:897-900`。
- `--spec-eval` が温度 0 を直接渡す箇所: `src/dsv41/ds4_main.cpp:1154-1163`。
- usage 関数には `--temperature` の記載がありません（表示内容）: `src/dsv41/ds4_main.cpp:85-94`。この調査では既存 `strata-dsv41 --help` binary は実行していません。
