# `--rope-scaling`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などからも委譲） |
| オプション | `--rope-scaling` |
| 別名 | なし |
| 値 | `none`、`linear`、`yarn` のいずれか |

## 役割

Flash-Next のモデルで、学習時の長さ 262,144 token を超える context を設定するときの RoPE（位置回転）方式を指定します。設定した値は setup が生成する当該モデルの engine 引数に入り、engine 起動時の RoPE 設定になります。これは setup CLI のオプションであり、engine の同名オプションとはスコープが異なります。

## 使い方

```sh
./setup.sh --setup --family qwen --context 393216 --rope-scaling yarn --yes
```

`--rope-scale` は方式に対応する拡張係数です。指定しない場合、setup は最終 context を 262,144 で割った係数（最低 1）を使います。`--rope-scale` を単独で指定することはできません（値・相互作用を参照）。

## 値と既定値

- parser は `none` / `linear` / `yarn` だけを受理します。省略時の parser 値は `None`（未指定）です。別名はありません。値を重複指定した場合は `argparse` の通常の `store` 動作により最後の値が使われます。
- 最終 context が 262,144 以下で方式を省略すると、RoPE scaling は設定されません。`linear` または `yarn` を明示するとその方式が選ばれ、係数も省略した場合は `max(1, context / 262144)` です。この範囲では係数 1 となり、context の拡張はしません。
- context が 262,144 を超え、方式を省略した場合は `--yes` なしなら対話質問（初期選択 `yarn`）が表示されます。`--yes` なら質問なしで `yarn` が選ばれます。係数の既定値は最終 context / 262,144 です。たとえば 393,216 では 1.5、524,288 では 2 です。
- context が 262,144 を超える場合、明示的な `none` は拒否されます。stock angles のまま学習範囲外を設定する構成を setup は作りません。
- `--rope-scale` を使う場合、context が 262,144 以下なら `--rope-scaling linear` または `yarn` が必要です。上限・正数性などの係数検証は setup の `float` parser では行われず、engine 側の検証で行われます。

## 実行時の動作

setup は `resolve_rope()` で最終 context と方式・係数を解決し、scaling が有効なら engine の引数に `--rope-scaling <方式> --rope-scale <係数>` を加えます。引数はモデル別の run config に保存されるため、setup が終了した後の engine 起動でも使われます。engine は CLI 指定をモデル GGUF の `rope.scaling.*` より優先し、起動時に一度解決した設定を RoPE table 作成前に固定します。実行中に切り替えるオプションではありません。

係数は setup 側では明示値をそのまま保持します（context が RAM 制約などで変更された場合も再計算しません）。そのため最終 context に見合わない係数が指定されたとき、setup が係数を補正するとは限りません。

## 適用条件と副作用

- 主要な有効経路は通常の `FAMILIES`（Flash-Next）です。Qwen3.6 の独自 engine 経路と DeepSeek-V4.1 の複数ファイル engine 経路ではこの設定を使用せず、値が指定されていれば「Flash-Next settings」と警告します。
- RoPE scaling は engine のプロセス設定です。KV cache に保存された key は RoPE 適用後のため、engine は実行中の変更をサポートしません。
- setup は通常、モデル・engine の準備、モデル別 run config の書き込みを行い、`--no-start` がなければ最後に起動します。このオプション単独ではそれらの副作用を抑止しません。RoPE 値の不整合で後段が失敗しても、すでに完了した準備処理は残り、再実行時にスキップされる場合があります。
- macOS の通常 setup は共通 parser の作成前に `metal/setup_mac.py` へ引数を委譲します。そこでの `--rope-scaling` の受理・挙動は本調査では確認していません。

## 出力とエラー

- `argparse` は選択肢外の方式や `float` に変換できない係数を parser error として拒否します。
- setup は scaling が解決されると方式・係数の `[ok]` 行を表示します。context が範囲外で `none`、または範囲内で係数だけが指定された場合は `fail()` がメッセージを表示して終了コード 1 で停止します。
- 係数が 1 未満、NaN / infinity など setup の `float` 変換を通る不正値は、生成引数を受け取った engine が起動時に検証します。不正な係数は `stderr` に `invalid ... rope scaling` 等を出して終了コード 2 になります。したがって setup が config を書いた後、モデル起動時に失敗する場合があります。

## 根拠

- `setup.py:8420-8435` — setup parser、値の選択肢、型、help。
- `setup.py:7286-7310` — context・方式・係数の既定値と拒否条件。
- `setup.py:9078-9095` — 対話時の方式選択、解決、表示、setup 側のエラー経路。
- `setup.py:9420-9425,9597-9599,9729-9730` — engine 引数への追加、run config 作成・保存。
- `setup.py:7610-7612,8030-8032,8932-8938` — 独自 family 経路での非適用と警告。
- `setup.py:825-830,8418-8419` — setup の停止表示と macOS の委譲。
- `setup.sh:6-13` — POSIX wrapper が引数を `setup.py` に渡す箇所。
- `src/program/generate.cpp:450-456,2444-2449` — engine 側の設定と parser。
- `src/program/generate.cpp:3312-3350,3681-3738` — engine の値検証、GGUF との優先順位、解決済み設定の固定と起動ログ。
- `include/strata/kernels/rope_scaling.hpp:30-35,164-190` — 起動時に一度設定する制約と設定値の検証。

調査範囲は上記 commit の checkout にある共通 `setup.py`、POSIX wrapper、ネイティブ engine の関連箇所です。Windows wrapper と macOS / SYCL の委譲先を実行しての挙動確認、既存 CLI の `--help` 実行、Release artifact の照合は行っていません。
