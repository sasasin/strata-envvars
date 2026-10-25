# `--output`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--output` |
| 別名 | なし（`--json` は共通の別 option で、`--output json` にする） |
| 値 | `human`、`json`、`jsonl` |

## 役割

ローカルにある engine package を導入する処理の表示形式を選びます。ファイルの検証や engine の導入方法を指定する option ではありません。

## 使い方

```sh
strata components install-file --output json ./strata-engine.tar.gz
```

`file` 位置引数には、事前に取得した engine package のパスを指定します。`install-file` は feed を使わず、package の署名を検査して導入する経路です（`strata_cli/update_cmd.py:59-61,208-216`、`strata_control/updater.py:1088-1091`）。

## 値と既定値

- parser は `choices=("human", "json", "jsonl")`、既定値 `human` で定義されています。値を省略すると人間向け表示です（`strata_cli/update_cmd.py:30-39`）。
- `--json` は one-shot command に後から追加される別 option で、指定すると `--output json` と同じ状態になります（`strata_cli/cli.py:508-515,2232-2235`）。
- 選択肢以外の値は argparse が拒否し、usage とエラーを stderr に出して終了コード 2 になります。空値も選択肢に含まれないため受理されません。複数回指定した場合は argparse の通常の scalar option として最後の値が残ります（定義: `strata_cli/update_cmd.py:39`）。

## 実行時の動作

- `human` は通常の進捗・結果を stdout に出します。TTY ではダウンロード進捗を同じ行に更新し、非 TTY では概ね 10% ごとに表示します（`strata_cli/update_cmd.py:65-87`）。
- `json` は進捗イベントを抑え、成功時に `schema_version: 1` と `ok: true`、導入結果を含む JSON object を stdout に出します（`strata_cli/update_cmd.py:65-74,208-216`）。
- `jsonl` は処理中の phase/progress/waiting event を1行ずつ JSON で出し、成功時には最後に導入結果の JSON object も出します。install-file では `Context.say()` が phase event を生成し、検証・test-start・切替の段階で呼ばれます（`strata_cli/update_cmd.py:69-87,208-216`、`strata_control/updater.py:344-345,1109-1115,1002-1005,1038,1074`）。完了 object も JSONL として扱う場合は、各行が独立した JSON として読めます。
- `--json` と `--output jsonl` を同時に指定すると、共通処理が `--json` を one-shot 専用として扱い、JSONL と併用できない旨のエラー経路に入ります（`strata_cli/cli.py:2232-2235`）。JSONL を使うときは `--output jsonl` のみを指定します。
- `--quiet` は共通 option です。人間向け出力では stdout を一時捕捉し、成功時は表示せず、失敗時は捕捉した内容を stderr に戻します。`json` / `jsonl` は machine output として捕捉を迂回します（`strata_cli/cli.py:512-515,2236-2248`）。

## 適用条件と副作用

この option は出力経路だけを切り替えます。package の読み取り、署名・全ファイル検証、対象 PC との適合判定、test-start、engine の切替などは `--output` の値によらず実行されます（`strata_cli/update_cmd.py:208-216`、`strata_control/updater.py:1088-1145,994-1077`）。導入に成功すると component state や履歴が更新されます。選択した元 package ファイルは削除されません（`strata_control/updater.py:1089-1091,1066-1074,1142-1145`）。

## 出力とエラー

- 失敗時、`json` / `jsonl` は `schema_version: 1`、`ok: false`、エラーコードとメッセージを含む JSON object を出します。`human` は `strata: ...` を stderr に出します（`strata_cli/update_cmd.py:174-183,246-255`）。この failure object は JSONL の event としてはラップされません。
- package が見つからない、形式・署名・内容が不正、またはこの PC に適合しない場合は installer が `UpdateError` を返し、署名検証失敗等は通常 exit code 5 になります。実行中の engine があり待機しない場合や test-start 等の失敗は別の code になり得ます。I/O error は CLI 共通処理で code 6 のエラーとして扱われます（`strata_control/updater.py:1088-1132,994-1024`、`strata_cli/update_cmd.py:246-255`、`strata_cli/cli.py:2176-2183`）。
- 出力先ファイルを作成する機能はありません。出力は stdout/stderr です（`strata_cli/update_cmd.py:69-87,178-183,212-216`）。

## 根拠

- parser 定義と共通 option: `strata_cli/update_cmd.py:30-39,59-62`
- `--json` / `--quiet` の共通追加、実行時処理: `strata_cli/cli.py:508-515,2223-2248`
- install-file の出力分岐と失敗経路: `strata_cli/update_cmd.py:65-87,174-217,246-255`
- ローカル package の検証・適合判定・導入: `strata_control/updater.py:1088-1148,994-1077`

