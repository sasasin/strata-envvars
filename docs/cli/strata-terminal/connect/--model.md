# `strata connect` の `--model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <app>` |
| オプション | `--model NAME` |
| 別名 | なし |
| 値 | アプリ設定に記録するモデル名。文字列で、parser に型・選択肢による制約はない |

## 役割

接続設定を表示・生成する際に、接続先アプリへ知らせるモデル名を指定します。サーバーが提供するモデルの切り替えや検証を行うオプションではありません。`--check` を併用すると、この名前がチェック要求の `model` 値にも使われます（`strata_cli/launch/cmd.py:153-164, 864-883`、`strata_cli/launch/check.py:50-68`）。

## 使い方

```sh
strata connect opencode --model my-server-model
```

生成される設定を実際にサーバーへ送って確かめる場合:

```sh
strata connect opencode --model my-server-model --check
```

`opencode` のほか、`codex`、`claude-code`、`omp`、`pi`、`hermes`、`openclaw`、`deepseek-harness` が登録されています（`strata_cli/launch/harness.py:209-235`）。

## 値と既定値

- 値は必須の位置値 `NAME` です。`argparse` 定義に `type`、`choices`、明示的な `default` はなく、空文字列を含めて CLI 側でモデル名の妥当性を検査しません（`strata_cli/launch/cmd.py:157`）。
- 値を省略した場合、実行中 launch の設定ファイルにある `model_name` が使われます。取得できない場合や値が空の場合は `strata` です。`--model` に空文字列を渡した場合も Python の `or` により同じ既定経路になります（`strata_cli/launch/cmd.py:605-627, 864-869`）。
- `--model NAME` の非空値は launch 情報より優先されます。`--preset NAME` は launch 情報の選択に使われますが、保存 preset のモデル名を直接 `--model` の既定値にはしていません。指定値を優先したい場合は `--model` を明示してください（`strata_cli/launch/cmd.py:605-627, 864-869`）。

## 実行時の動作

`run_connect` は `--model`、launch 情報、文字列 `strata` の順にモデル名を決め、`harness.target` に渡します。target はモデル名を変換せず保持し、サーバー URL の末尾 `/v1` の整理や API key の placeholder 設定を行います（`strata_cli/launch/cmd.py:864-870`、`strata_cli/launch/harness.py:253-260`）。

各アプリの renderer はこの値をモデル識別子として設定に埋め込みます。例として OpenCode では `strata/<NAME>` と provider の models key、Codex では `model`、Claude Code では `ANTHROPIC_MODEL` 系の環境変数に使用します。他の対応アプリでも既定モデルまたはモデル ID に使われます（`strata_cli/launch/harness.py:80-104, 111-149`）。したがってアプリ側の設定名を上書きするだけであり、Strata がモデル名をカタログ照合したり、サーバー上の実モデルを変更したりする処理はこのオプションにはありません。

`--check` を併用すると、同じモデル名で prompt と tool call の2要求をサーバーへ送ります（`strata_cli/launch/cmd.py:880-896, 921-929`、`strata_cli/launch/check.py:111-143`）。`--write` を併用すると、その名前を含む設定ファイルを書き込みます。既存ファイルは先に時刻付き `.strata-bak-...` にコピーされ、JSON merge 対象では新しい値が既存値に優先します（`strata_cli/launch/cmd.py:930-947`、`strata_cli/launch/harness.py:275-307`）。`--write` は確認を求め、非対話環境では `--yes` がなければ終了コード 2 で書き込みません（`strata_cli/launch/cmd.py:934-944`）。

## 適用条件と副作用

- `--model` 単独では設定内容を表示するだけで、モデルの起動・ダウンロード・切り替えやファイル書き込みはしません。ファイルを書き込むのは `--write`、サーバーへの要求を行うのは `--check` を付けた場合です（`strata_cli/launch/cmd.py:897-929`）。
- 値の構文・実在性を検証せず、renderer の設定文字列へ埋め込みます（`strata_cli/launch/cmd.py:157, 867-870`、`strata_cli/launch/harness.py:80-149`）。アプリ固有設定で有効なモデル ID を指定してください。引用符や改行などを含む値の扱いは、各設定形式でのエスケープが実装されていない箇所があり、すべての値について有効な設定になるとは確認できません。
- `--check` はモデル名をリクエスト body に入れ、prompt と tool call を送信します。両方成功で終了コード 0、少なくとも一方が失敗すれば 1 です。JSON 出力では失敗詳細が `error` と `checks` に含まれます（`strata_cli/launch/cmd.py:880-896`、`strata_cli/launch/check.py:50-68, 111-155`）。
- `--check` と `--write` を同時に指定した場合、チェックが失敗すると書き込み処理より前に終了します（`strata_cli/launch/cmd.py:921-930`）。
- `--output json` の経路は `--write` 処理より先に戻るため、JSON 出力では `--write` を指定してもファイルを書き込みません。`--check` と JSON 出力を組み合わせた場合も同じです（`strata_cli/launch/cmd.py:871-896, 930-947`）。

## 出力とエラー

通常の表示では、`--model` は選択したアプリの設定例や環境変数に反映されます。`--output json` では renderer の結果を JSON として出力します（`strata_cli/launch/cmd.py:871-895`）。未知の `--model` 値を拒否する専用エラー経路はありません。`--check` でサーバーがモデルを受け付けない場合は、チェック失敗として表示され終了コード 1 になります（`strata_cli/launch/cmd.py:880-896`、`strata_cli/launch/check.py:146-155`）。

オプション名の誤記など parser が認識しない引数は、`strata connect` の案内とともに stderr に出力され終了コード 2 です（`strata_cli/cli.py:2223-2231`、`strata_cli/launch/cmd.py:168-183`）。

## 根拠

- parser 定義と `connect` の option scope: `strata_cli/launch/cmd.py:148-165`
- launch 情報からの既定値取得: `strata_cli/launch/cmd.py:605-627`
- 値の優先順位、renderer・check・write の実行: `strata_cli/launch/cmd.py:842-947`
- 値をアプリ別設定に反映する処理と書き込み: `strata_cli/launch/harness.py:80-149, 253-307`
- check 要求にモデル名を渡す処理と失敗判定: `strata_cli/launch/check.py:50-68, 111-155`
- `strata connect` の索引上のスコープ: [`docs/cli/README.md`](../../README.md) の `strata connect` 節。配置・調査規約: [`001_investigation.md`](../../001_investigation.md)。

調査は上記 commit のソースに限定しました。同 revision の CLI `--help` や Release 配布物との照合は行っていません。
