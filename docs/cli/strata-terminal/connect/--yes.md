# `--yes`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main`（`origin/main` と同期）で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `False`、指定時 `True`。 |

## 役割

`strata connect <アプリ名> --write` が設定ファイルを書き込む前に行う確認を省略します。単独では書き込みを開始しません。parser は `connect` 専用であり、同じ綴りの `strata launch --yes` とは適用先が異なります（`strata_cli/launch/cmd.py:148-165`）。

## 使い方

```sh
strata connect opencode --write --yes
```

実際に書き込むファイルと接続設定はアプリ名および `--url`、`--key`、`--model`、`--preset` などで決まり、`--yes` 自体はそれらを変更しません（`strata_cli/launch/cmd.py:153-164, 864-870`）。

## 値と既定値

`argparse` の `action="store_true"` で宣言されています。引数値は受け付けず、指定の有無だけを読みます。既定値は偽です。別名、追加の値 validation、範囲制限はありません（`strata_cli/launch/cmd.py:162`）。

## 実行時の動作

アプリ名に対応する接続設定をレンダリングし、表示（または `--output json` の JSON 出力）した後、`--write` がある場合に書き込み処理へ進みます。生成対象ファイルがなければ「Nothing to write for this app.」を表示して終了し、確認も書き込みも行いません（`strata_cli/launch/cmd.py:857-879, 897-920, 930-933`）。

書き込み対象がある場合、`--yes` が真なら確認入力を行わず `harness.write_file` を呼びます。偽なら対話端末では `[y/N]` を尋ね、「y」または「yes」のみ承認します（空入力を含む他の回答、および EOF は拒否）。承認されない場合は「Nothing was written.」を出して終了します（`strata_cli/launch/cmd.py:934-947`）。

## 適用条件と副作用

- `--yes` は `--write` の確認だけに作用します。`--check` を付けた場合、そのチェックは書き込み判定より先に実行され、省略されません（`strata_cli/launch/cmd.py:921-947`）。
- 非対話環境で `--write` を使い、`--yes` を付けない場合は stderr に `strata: --write asks first; run it in a terminal or add --yes.` を出し、終了コード `2` で停止します（`strata_cli/launch/cmd.py:934-937`）。
- `--yes` と `--write` を併用すると、生成された設定ファイルを書き込みます。親ディレクトリがなければ作成し、既存ファイルは `.strata-bak-<時刻>` にコピーしてから置き換えます。JSON merge 対象では既存キーを保ち、新しいキーを優先します。書き込み後は可能なら mode `0600` を設定します（`strata_cli/launch/harness.py:275-298`）。
- `--yes` 単独（`--write` なし）ではこの書き込み処理に入らず、設定内容の表示だけです（`strata_cli/launch/cmd.py:930-947`）。

## 出力とエラー

確認を省略して書き込みが成功すると、ファイルごとに `Created`、`Replaced`、`Merged` とパスを表示し、バックアップがあればそのパスも表示します（`strata_cli/launch/cmd.py:945-947`, `strata_cli/launch/harness.py:297-298`）。書き込み時の `OSError` はトップレベルの CLI 処理で捕捉され、通常出力では `strata: <エラー>` を stderr に、JSON 出力では `ok: false` のエラー JSON を stdout に出して終了コード `6` を返します（`strata_cli/cli.py:527-532, 2176-2183`）。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` parser と `--yes` の定義。
- `strata_cli/launch/cmd.py:842-870` — アプリ名の解決、既定接続先・設定値の選択。
- `strata_cli/launch/cmd.py:921-947` — `--check`、確認・非対話時の拒否、書き込み呼び出し。
- `strata_cli/launch/harness.py:275-298` — 親ディレクトリ作成、バックアップ、JSON merge、書き込み、権限設定。
- `strata_cli/cli.py:527-532, 2176-2183` — 共通エラー出力と `OSError` の終了経路。

調査は指定 commit のローカルソースに限定しました。CLI の実行や `--help`、Release 配布物との照合は行っていません。
