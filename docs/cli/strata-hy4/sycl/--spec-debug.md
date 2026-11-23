# `strata-hy4-sycl --spec-debug`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL runner） |
| オプション | `--spec-debug` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

HY4 の DFly2 投機デコードが実行されたとき、各検証 iteration の位置、候補数、分岐の有無、受理数、draft・verify の所要時間、先頭候補の信頼度を stderr に出します。デバッグ情報を追加するだけで、投機デコードの選択方法や生成トークンを変える処理はありません（`engine/src/hy4flash/sycl/sy_main.cpp:183`、`engine/src/hy4flash/sycl/sy_spec.h:394-396`）。

## 使い方

```sh
# serve モードで DFly2 投機デコードの診断ログを有効にする
strata-hy4-sycl --serve --native MODEL.strata --draft dfly2 --spec-debug
```

通常のモデル・トークン入力モードでは、たとえば `--model MODEL.strata --tokens ids.txt --draft dfly2 --gen 32 --spec-debug` のように指定します。`--draft dfly2` と正の生成数がなければ投機デコード経路にならず、このオプションによる iteration ログも出ません（`engine/src/hy4flash/sycl/sy_main.cpp:250-252,279-280,379-386`）。

## 値と既定値

値は不要です。parser は引数が `--spec-debug` と完全一致したとき `scfg.debug = true` とし、それ以外の初期値は `SpecCfg.debug = false` です（`engine/src/hy4flash/sycl/sy_main.cpp:96,183`、`engine/src/hy4flash/sycl/sy_spec.h:21-26`）。同じフラグを複数回指定しても同じ真偽値を設定します。値の範囲や数値 validation はありません。値を続けて渡す形式は認識されず、余分な引数は unknown argument として扱われます。

## 実行時の動作

parser で設定した `SpecCfg` は、`--serve` では `ServeOpts.spec` にコピーされ、serve 側で `use_spec` が真の場合に `Spec` へ渡されます（`engine/src/hy4flash/sycl/sy_main.cpp:226-248`、`engine/src/hy4flash/sycl/sy_serve.h:303-307`）。serve の投機経路は、モデルに DFly2 drafter があり、`--draft` が `off` でなく、chunk が 8 以上で drafter 初期化に成功した場合に有効になります。各 request では生成上限が正で画像入力がない場合に `spec->run(...)` が呼ばれます（`engine/src/hy4flash/sycl/sy_serve.h:248-278,464-475`）。`--draft dfly2` でモデルに drafter tensor がない、chunk が 8 未満、または drafter 初期化に失敗した場合はエラーになります。`--draft auto` では初期化失敗時に `use_spec` が無効のままとなり、逐次経路に進みます（`engine/src/hy4flash/sycl/sy_serve.h:248-278`）。

通常モードでは `draft` が `dfly2` で、生成数 `gen` が正のとき `Spec` を構築して `run` を呼びます。それ以外の生成経路は逐次 decode であり、`cfg.debug` を参照するログ箇所は通りません（`engine/src/hy4flash/sycl/sy_main.cpp:250-252,279-280,379-386,527-544`）。

投機デコードの iteration ごとに、stderr へ次の形式の行を出します（`engine/src/hy4flash/sycl/sy_spec.h:394-396`）。

```text
[spec] a=<位置> T=<検証行数> branch=<分岐有無> n=<受理数> draft <ms> ms verify <ms> ms conf1 <信頼度>
```

`--spec-debug` 自体がファイルを書き出す処理はありません。通常モードでは生成 ID や他の出力ファイルも別途出力されますが、それらはこのフラグの処理ではありません（`engine/src/hy4flash/sycl/sy_main.cpp:392-407`）。

## 適用条件と副作用

- ログ対象は投機デコードの検証 iteration です。投機経路に入らないケース、serve の画像 request、生成上限が 0 の request ではこの iteration ログは出ません（`engine/src/hy4flash/sycl/sy_serve.h:464-472`）。
- ログは `fprintf(stderr, ...)` による診断出力です。stdout の serve protocol 行とは別の出力先です（`engine/src/hy4flash/sycl/sy_spec.h:394-396`、`engine/src/hy4flash/sycl/sy_serve.h:53-61`）。
- この SYCL 実装で確認できた値の補正・拒否条件はありません。フラグ固有のファイル・ネットワーク・プロセス管理の副作用もソース上では確認できません。

## 出力とエラー

有効な投機 iteration では `[spec]` 行が stderr に出ます。`--spec-debug` 専用の失敗経路は確認できません。未知の引数は parser の共通経路で `unknown arg <引数>` を stderr に出し終了コード 2 となり、serve 指定時はさらに `ERR unknown flag <引数>` を stdout に出します（`engine/src/hy4flash/sycl/sy_main.cpp:190-196`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:79-105` — CLI 初期化と `SpecCfg` の既定構築。
- `engine/src/hy4flash/sycl/sy_main.cpp:180-196` — `--spec-debug` の parser 分岐と未知引数の処理。
- `engine/src/hy4flash/sycl/sy_spec.h:21-31` — `SpecCfg.debug` の初期値および関連設定。
- `engine/src/hy4flash/sycl/sy_spec.h:394-396` — iteration ごとの stderr ログ。
- `engine/src/hy4flash/sycl/sy_main.cpp:226-248,250-280,379-386` — serve への設定転送と通常モードでの投機経路。
- `engine/src/hy4flash/sycl/sy_serve.h:248-278,303-307,464-475` — serve の DFly2 有効条件、`Spec` 構築、request ごとの実行条件。
