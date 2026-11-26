# `--parallel`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`。CLI parser は `1..64` を受理する |

## 役割

一度に回答する要求数を指定する。明示値は選択済み preset の設定に重ねて今回の起動に適用される。省略時はカードの VRAM、モデル系列、モデルとコンテキストに応じた推奨値を使い、DFlash2 を自動選択する経路では既定の複数 slot を profile に設定しない。適用結果はモデル系列ごとに異なり、上限を超える値が CLI の共通範囲内であれば開始前に系列固有の注意を表示する。

## 使い方

```sh
# 4要求を同時に扱う設定で起動する
strata launch --model iq3_xxs --parallel 4

# 起動内容だけを確認する（設定やモデルファイルを変更しない）
strata launch --model iq3_xxs --parallel 4 --plan
```

## 値と既定値

- `N` は整数として変換され、`1` から `64` までが parser で受理される。整数でない値、範囲外の値は `argparse` の型エラーとなり、コマンドは開始処理に進まない。parser 宣言と変換・境界チェックは `terminal/strata_cli/launch/cmd.py:63-70,97`。
- 省略時の値は parser では `None`。preset が指定されていれば保存済み値が引き継がれ、明示した `--parallel` がそれを置き換える（`terminal/strata_cli/launch/cmd.py:215-220,252-253`）。preset も指定しない場合は、起動時に `fit_parallel_for` が推奨値を決める（`terminal/strata_cli/launch/runner.py:472-503,2365-2369`）。
- 通常系列の基準は VRAM に応じて 20 GB 未満で1、20 GB付近から2、24 GB付近から3、32 GB付近から4（境界判定には0.5 GBの許容差）。Qwen独自 engine の系列はこの値をさらにモデル・コンテキスト別推奨値以下に制限する。Inkling-2-Mini は NVIDIA の場合、モデル・コンテキスト等で K/V がカードに収まる slot 数を基準値以下で選ぶ。計算できない場合は基準値へ戻る（`terminal/strata_cli/launch/settings.py:77-87`; `terminal/strata_cli/launch/runner.py:472-503`）。明示値にはこの自動選択を適用しない。

## 実行時の動作

- 通常系列では、明示値または自動選択値を launch 専用 serving profile の `parallel` override に書き、profile の保存値を今回の host/port/parallel 設定に合わせて更新する。エンジンを含む run config も生成・保存される（`terminal/strata_cli/launch/runner.py:2204-2238,2323-2346`）。実際の要求 slot 数は選択された engine と serving profile の処理に委ねられる。
- Inkling-2-Mini では値が1より大きいと、生成する engine 引数へ `--parallel N` として渡し、slot 数を見込んで配置計画を作る。1の場合はこの引数を追加しない（`terminal/strata_cli/launch/runner.py:1377-1378`）。
- Hy4-Flash は1要求のみ。値が2以上でも拒否せず、値を使わない旨と他の要求は順番待ちになる旨を警告する（`terminal/strata_cli/launch/settings.py:275-281,319-334`）。
- Inkling-2-Mini は複数 slot の会話用メモリだけでカード容量を超えると、開始不能としてエラーにする。容量には収まっても slot 増加によりモデルの expert が VRAM から RAM/SSD 側へ移る場合は警告する（`terminal/strata_cli/launch/settings.py:284-316`）。
- その他の系列では、単一カード上の engine slot 上限は NVIDIA/AMD の Qwen 系で16、その他で8。指定値がその上限を超えても値は受理され、上限を超える要求は順番待ちになると警告する。またカードの通常 fit 数を超える値は、起動可能だがモデルが VRAM に載る量が減り回答が遅くなる可能性を警告する（`terminal/strata_cli/launch/settings.py:270-281,335-345`）。
- 明示した `--parallel` は DFlash2 が自動で選ばれる場合も指定数として扱う。省略値の場合に限り、DFlash2 の実行で MTP を維持するため自動 slot override を省く（`terminal/strata_cli/launch/cmd.py:97,101-104`; `terminal/strata_cli/launch/runner.py:2323-2333`）。

## 適用条件と副作用

- `--plan` は適用後の要求数や警告を表示し、「何も変更していない」と報告して終了する。通常起動では run config と launch 用 profile の保存・更新を伴う（`terminal/strata_cli/launch/cmd.py:882-925`; `terminal/strata_cli/launch/runner.py:2204-2238,2323-2346`）。
- engine の系列・backend・メモリ状況によって、値が警告付きで上限までに制限される、Hy4-Flash で未使用になる、Inkling でメモリ不足エラーになるなどの違いがある。一般系列のチェックは利用可能な GPU の情報に基づき、VRAM 情報がない場合は fit 超過警告を出せない（`terminal/strata_cli/launch/cmd.py:412-416`; `terminal/strata_cli/launch/settings.py:319-345`）。

## 出力とエラー

- parser の値変換エラーでは `argparse` がエラーを表示する。launch のメモリ計画で error level の notice が出た場合、`strata` 名義のエラーを stderr に出し終了コード `2` で終わる（`terminal/strata_cli/launch/cmd.py:887-889,1011-1012`）。
- 通常出力では適用値を plan の `parallel` 欄に表示し、範囲内だが engine 上限や fit を超える値には警告を表示する。JSON 出力モードでは plan と warning を JSON に含める（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:63-70,97` — parser の型変換、許容範囲、help と値の登録。
- `terminal/strata_cli/launch/cmd.py:215-220,252-253,344-416` — preset と CLI 値の優先順位、hardware/model に応じた警告検査。
- `terminal/strata_cli/launch/settings.py:77-87,270-345` — 自動 fit の基準、系列別上限、Inkling のメモリ判定と警告。
- `terminal/strata_cli/launch/runner.py:472-503,1377-1378` — 自動値の系列別補正と Inkling engine 引数への転送。
- `terminal/strata_cli/launch/runner.py:2204-2238,2323-2346` — run config と serving profile の生成・更新。
- `terminal/strata_cli/launch/cmd.py:887-889,897-925,1011-1014` — error notice、plan 表示、終了処理。
- `docs/cli/README.md:836-868` — 文書の索引上の scope が `strata launch` であることを確認。

本調査ではソースコード上の parser と設定・実行経路を確認した。GPU 実機での slot 数や性能は測定していない。
