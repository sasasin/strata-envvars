# `--parallel`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | `N`（整数、1〜8） |

## 役割

同時に処理するリクエスト数を指定します。複数の会話を並行して応答させる用途に使います。モデルによって、この値は DeepSeek-V4.1-Flash の会話数、または他モデルの engine slot 数として設定されます。値を省略した場合もモデルごとの通常設定はありますが、DeepSeek-V4.1-Flash は明示指定がなければ逐次応答です（`strata_cli/launch/cmd.py:100,427-429`、`strata_cli/launch/runner.py:1833-1845`）。

## 使い方

モデルと値を指定して、変更を加えず設定内容を見る例です。

```sh
strata launch --model iq3_xxs --parallel 4 --plan
```

`--plan` の表示では、通常モデルは指定値、DeepSeek-V4.1-Flash は予定される会話数と説明が表示されます。計画表示は「Nothing was changed」として終了します（`strata_cli/launch/cmd.py:330-345,930-960`）。

## 値と既定値

- `N` は整数で、1〜8 が有効です。整数に変換できない値は「requests の数ではない」、範囲外は「engine が扱えない」として parser が拒否します（`strata_cli/launch/cmd.py:65-72,100`）。
- このオプションの既定値は未指定です。設定モデルでは未指定を `None` として扱い、通常モデルの launch は GPU の VRAM に応じた値を profile に設定します。判定表は 32 GiB 以上で4、24 GiB 以上で3、20 GiB 以上で2、それ未満で1です（境界は表の値から0.5 GiBを差し引いた位置）。GPU が利用可能でない場合など、判定できないときは自動値を設定しません（`strata_cli/launch/settings.py:65-75,125`、`strata_cli/launch/runner.py:1840-1847`）。
- DeepSeek-V4.1-Flash は `--parallel` 未指定なら逐次処理です。値1も同じく逐次処理となり、2〜8で複数会話を要求します（`strata_cli/launch/cmd.py:427-429`、`strata_control/dsv41_parallel.py:39-44,82-83`）。
- `--preset NAME` と併用した場合、コマンドラインの指定が preset の設定に重なり、その起動に使われます。`--save-preset` を付けない限り、既存 preset の設定値はその指定で書き換えず、使用時刻のみ更新します（`strata_cli/launch/cmd.py:212-218,245-246,1000-1003`）。

## 実行時の動作

launch は選ばれた設定から run config を作ります。指定値は通常 serving profile の `parallel` override に入ります。サーバーは DeepSeek-V4.1-Flash なら engine 引数 `--parallel N` に、その他の engine なら `--batch N` に変換します。engine args に既に `--batch` / `--slots` がある場合は通常の変換を行いません。全カード split engine の run config では `parallel` を lane 数として既存の `--batch` 値へ反映し、最大8に抑えます（`strata_cli/launch/runner.py:1791-1814`、`serve/server.py:3845-3897`）。

DeepSeek-V4.1-Flash では、engine は各会話用の attention memory を GPU 上に持ち、複数会話の token をまとめて decode します。追加会話ぶんの VRAM を experts が使える領域から使うため、同時実行中の個々の応答は遅くなることがあります。plan と通常の launch 出力にはこの動作の説明が含まれます（`strata_control/dsv41_parallel.py:1-10,61-74`、`strata_cli/launch/runner.py:2476-2487`、`strata_cli/launch/cmd.py:943-965`）。

通常モデルでは、VRAM から見積もった同時数を超える明示値に警告を出しますが、launch を拒否しません。DeepSeek でも測定条件外の OS・GPU 等には警告を出しますが、これも拒否ではありません。engine は搭載メモリに応じて実際の同時数を減らすことがあります。DeepSeek engine が古く `--parallel` を受け付けないと確認できた場合、launch 側は値を落として逐次処理にし、engine 更新を案内します。engine の capability を確認できない場合は値を落とさず続行します（`strata_cli/launch/settings.py:230-243`、`strata_control/dsv41_parallel.py:77-118`、`strata_cli/launch/runner.py:1757-1770`、`strata_control/dsv41_flags.py:27-49`）。

`--drafting auto` は複数リクエストが並行すると MTP を使い、`--drafting dflash2` は指定した parallel 数で動作します（`strata_cli/launch/cmd.py:104-107`）。ただし、DFlash2 が利用できるモデル等の条件は drafting の選択に依存します。値を省略し DFlash2 の単一リクエスト動作を選ぶ場合、launch が自動設定する parallel override を抑制します（`strata_cli/launch/runner.py:1592-1600,1794-1799`）。

## 適用条件と副作用

- 4枚の Radeon AI PRO R9700 と該当する Qwen3.8-Flash-Next 構成では、ユーザー指定がない場合に専用 profile が parallel 数を補うことがあります。明示した `--parallel` はその自動値を置き換えます（`strata_cli/launch/runner.py:1772-1787`、`strata_control/amd_four_card.py:64-90`）。
- `--parallel` は launch 用 run config と serving profile の設定に影響します。`--save-preset` を指定した場合はその設定を preset として保存します。preset から起動した場合、保存せずに指定した値はその起動だけの変更です（`strata_cli/launch/runner.py:1689-1694,1791-1814`、`strata_cli/launch/cmd.py:999-1003`）。
- DeepSeek の古い engine 判定では、対象 engine に `--help` を渡して usage を確認します。調査時点の checkout に含まれるコードと、利用者のインストール済み engine の版は別です（`strata_control/dsv41_flags.py:27-49`）。

## 出力とエラー

- 非整数または1〜8の範囲外は parser error になります（`strata_cli/launch/cmd.py:65-72`）。
- 通常モデルで GPU の見積もりより大きい値は警告され、起動可能なまま続行します。DeepSeek の測定条件外も警告に留まります（`strata_cli/launch/settings.py:230-243`、`strata_control/dsv41_parallel.py:77-118`）。
- DeepSeek engine が `--parallel` 非対応と判明したときは、値を使わず逐次処理にする警告を表示します（`strata_cli/launch/runner.py:1757-1770`）。
- plan は値を含む設定と警告を表示して終了し、設定変更や起動は行いません（`strata_cli/launch/cmd.py:930-960`）。

## 根拠

- Parser と整数・範囲 validation: `strata_cli/launch/cmd.py:65-72,100`。
- preset と CLI 設定の重ね合わせ: `strata_cli/launch/cmd.py:212-218,239-246`。
- モデル別の説明・警告: `strata_cli/launch/cmd.py:427-451,461-472`。
- VRAM 別 default と警告: `strata_cli/launch/settings.py:65-75,230-243`。
- Run config / profile への反映と旧 DeepSeek engine 判定: `strata_cli/launch/runner.py:1681-1694,1757-1814,1833-1847`。
- engine 引数への変換と既存 slot 引数の扱い: `serve/server.py:3834-3897`。
- DeepSeek の同時実行・測定条件・環境別警告: `strata_control/dsv41_parallel.py:17-35,61-118`。
- DeepSeek engine の capability 確認: `strata_control/dsv41_flags.py:27-49`。
