# `--seed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--seed` |
| 別名 | なし |
| 値 | 10 進表記を想定した符号なし整数。parser は `strtoull` で変換する |

## 役割

確率的な offline 生成で使う擬似乱数器の初期値を指定します。CUDA/HIP 版の通常の greedy 生成を変えるオプションではありません。`--draft dfly2` による確率サンプリング、または `--dump-dfly-batch` の候補 token 選択で使われます。

## 使い方

```sh
# DFly2 の確率サンプリングを使う offline 生成
strata-hy4 --model model.strata --tokens prompt.txt --gen 128 --draft dfly2 --temperature 0.7 --seed 12345

# DFly2 用 batch を生成する処理の乱数初期値
strata-hy4 --model model.strata --dump-dfly-batch prompts.txt --seed 12345
```

## 値と既定値

- 値を省略すると、引数取得関数が `ERR --seed needs a value` を標準出力へ出し、プロセスを終了コード `2` で終了します。
- 値は `strtoull(value, nullptr, 10)` で `uint64_t` に代入されます。parser は変換終了位置や `errno` を検査せず、明示的な範囲検証も行いません。したがって、不正形式や範囲外値の厳密な扱いはこの parser だけから保証できません。
- 既定値は `SampleOpts::seed = 0` です。ただし利用箇所では 0 を「未指定」と同じ扱いにし、`20261120` を RNG seed に使います。このため `--seed 0` で RNG seed 0 を選ぶことはできません。
- 同じオプションを複数回指定した場合は、引数を左から処理して `cli_samp.seed` を上書きするため、最後に指定した値が残ります。

## 実行時の動作

- **DFly2 offline 生成:** `--draft dfly2`、`--gen` が正、かつ `--dfly-alloc-only` でない場合に spec mode へ入ります。サンプリング設定が greedy でなくなる（たとえば `--temperature` が正）か、penalty が有効な場合に `cli_samp` が `Spec::run` へ渡され、`cli_rng` が sampling RNG として渡されます。`cli_rng` は `--seed` が 0 なら `20261120`、それ以外なら指定値で初期化されます。`SampleOpts` の既定 temperature は 0（greedy）なので、seed だけ指定しても確率サンプリングには切り替わりません。
- **通常の offline greedy 生成:** spec mode でない生成経路は logits の argmax を選びます。ここでは `cli_samp.seed` を参照しないため、seed は生成 token を変えません。
- **`--dump-dfly-batch`:** 初期化後、このモードが通常の生成より先に実行され、seed（0 の場合は `20261120`）で `std::mt19937_64` を初期化して候補 token を選びます。引数で指定した seed は manifest 内の各 prompt に対して共有 RNG の初期値として使われます。
- **`--serve`:** CLI parser は `--seed` を受け付けますが、server 設定 `ServeOpts` へは `cli_samp.seed` を渡しません。server はリクエストの `seed=N` を読む別経路を持つため、CLI の `--seed` は server リクエストの seed を設定しません。

## 適用条件と副作用

この文書の対象は索引で `root/` に割り当てられた CUDA/HIP の `strata-hy4` です。Metal 版・SYCL 版は別 parser と別 scope です。seed はプロセス内の乱数選択に影響します。ファイルへの書き込みなど seed 自体が追加する副作用はありませんが、`--dump-dfly-batch` は同モード本来の出力ディレクトリ生成・出力を行います。

seed を固定しても、ソースから確認できるのは RNG の初期化値までです。異なる GPU、backend、実行条件をまたいだ結果の再現性はここでは保証できません。

## 出力とエラー

- seed 固有の値 validation や seed 専用エラー処理はありません。
- 値が必要なオプションの値が欠けている場合は、`ERR --seed needs a value` を stdout に出して終了コード `2` で終了します。
- 未知の引数は stderr に `unknown arg <引数>` を出して終了コード `2` となります。`--serve` が有効な場合は stdout に `ERR unknown flag <引数>` も出します。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:365-383` — sampling 設定の初期化と、値欠落時の出力・終了。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:416-420` — `--seed` の parser 定義と `strtoull` 変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-365, 498-505` — offline の既定 draft/sampling 設定と未知引数の失敗経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611` — serve 設定への転送項目。`cli_samp.seed` は転送されない。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35` — seed、temperature、greedy 判定の既定値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701-708, 997-1007` — spec mode の適用条件、seed を使った RNG 初期化、sampling 設定の受け渡し、batch モードの分岐。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1073` — 通常 offline decode の argmax 経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:183-214, 255-275` — batch モードの RNG 初期化と候補からの確率選択。
- `engine/src/hy4flash/run/hy4_serve.hip.h:155-185, 497-498` — server リクエスト単位の `seed` parser と RNG 初期化（CLI オプションとは別経路）。
