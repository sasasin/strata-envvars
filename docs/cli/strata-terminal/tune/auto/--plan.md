# `strata tune auto --plan`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると `True` になる |

## 役割

指定したモデル・保存済み profile・run config を読み、現在の構成で自動 tuning を実行した場合に試す設定、対象外にする設定とその理由、engine 実行回数と所要時間の概算を表示する。測定や preset の保存には進まない。preview は `--mode`、`--goal`、`--use`、`--leave-ram`、`--concurrency`、`--allow-small-differences`、`--allow-not-repeatable` などの値を反映する。

## 使い方

```sh
# インストール済みモデルを quick tuning する場合の候補を確認
strata tune auto IQ3_S --plan

# JSON で計画を取得
strata tune auto my-profile --plan --output json
```

`target` は必須で、インストール済みモデル名、保存済み profile 名、または run config JSON のパスを指定する。モデル名の一意な部分も解決対象になる（`terminal/strata_cli/tune_commands.py:27`, `117-140`）。

## 値と既定値

値は不要で、別名はない。省略時は `False` となり通常の tuning 実行へ進む（`terminal/strata_cli/tune_commands.py:28`, `349-355`）。同じフラグを複数回指定した場合の特別な処理はありません。

## 実行時の動作

`--plan` の指定時は `autotune.preview` を呼び、結果に解決済みモデル名と config path を加えて出力する。この分岐は `WorkerSession` の生成と `tuner.run()` より前にあるため、engine の性能測定、tuning セッション、preset 作成、tuning report 保存には進まない（`terminal/strata_cli/tune_commands.py:349-353`, `355-387`, `408-424`）。preview は候補リストと除外理由、engine run 数、1 run の仮定時間、合計時間および mode の予算を返す。最初の run で得られる実測値はまだ不明なので、測定結果に依存する候補は設定からの予測として扱われる（`terminal/strata_control/autotune.py:856-866`）。

通常出力では計画、除外理由、run 数と時間概算を表示する。`--output json` を併用すると `schema_version: 1`, `ok: true`, `plan` を含む JSON を stdout に出す（`terminal/strata_cli/tune_commands.py:101-106`, `428-442`）。

## 適用条件と副作用

計画の作成にも対象 config と engine の存在が必要である。対象は `--plan` 分岐より前に解決・読み込みされ、engine が見つからなければ失敗する（`terminal/strata_cli/tune_commands.py:315-323`, `336-338`）。計画用 context はメモリ・GPU・CPU 情報、config の engine 引数、backend 等から組み立てられる（`terminal/strata_control/autotune.py:902-932`）。

preview 自体は engine 測定を行わないが、候補設定の適用可否を知るため `engine_flag_inventory` が engine バイナリへ `--help` を渡して起動し、必要に応じて個々の flag も probe する。したがって「何のプロセスも起動しない」dry-run ではない。Strata 側は probe の stdout/stderr を読み、最大 20 秒の `--help` 呼び出しが実行できない場合は flag inventory を `None` として扱う（`terminal/strata_cli/tune_commands.py:339-345`, `terminal/strata_control/tuning.py:224-254`, `257-260`）。外部 engine の `--help` 起動時の挙動や、各機器情報取得 helper の OS 固有副作用まではここでは断定しない。

## 出力とエラー

- `--goal` が `speed` / `full` / `room` / `room:MiB` 形式でない場合、または `room:` の数値部を整数にできない場合はエラーになる（`terminal/strata_cli/tune_commands.py:315-323`, `192-199`）。
- 対象が Hy4 または Inkling の場合、このコマンドの tuning 対象外として終了コード 2 で失敗する（`terminal/strata_cli/tune_commands.py:324-327`）。
- engine が config の指定位置に存在しない場合は終了コード 5 で失敗する（`terminal/strata_cli/tune_commands.py:336-338`）。
- その他、target 解決・config 読み込み中に捕捉したエラーは `_fail` で人向けなら stderr、JSON 出力なら `ok: false` と error object に出す。コードは例外の `exit_code` があればそれを使い、なければ 2（`terminal/strata_cli/tune_commands.py:315-323`, `109-114`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `auto` parser、位置引数、`--plan` の `store_true` 定義と関連 option。
- `terminal/strata_cli/tune_commands.py:101-114,117-140,192-199` — 出力・失敗形式、target 解決、goal の解釈。
- `terminal/strata_cli/tune_commands.py:309-353,355-387,408-424` — 事前検査、preview 分岐と通常 tuning の分岐、通常経路の副作用。
- `terminal/strata_control/autotune.py:856-866,902-932` — preview 内容と計画用 context の構築。
- `terminal/strata_control/tuning.py:224-260` — engine flag inventory が engine subprocess を呼ぶ範囲。
