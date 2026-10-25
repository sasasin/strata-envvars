# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--json` |
| 別名 | なし（`--output json` が同等の出力指定） |
| 値 | 値を取らないフラグ |

## 役割

`strata ops run` の応答を機械処理向けの JSON 1 オブジェクトにする。実行する操作の選択や実行内容はレシピで決まり、このフラグ自体は変更しない。

## 使い方

```sh
strata ops run check --profile four-gpu --json
```

`check` は例としてのレシピ名。`--profile` は必須で、`--json` の代わりに `--output json` も指定できる。`strata ops run` は保存済みレシピを実行するコマンドであり、読み取り専用の事前確認には `strata ops plan` を使う（`strata_cli/cli.py:255-290`）。

## 値と既定値

`argparse` の `store_true` フラグであり、値は取らない。省略時は `False` で通常出力、指定時は `a.output` を `json` に設定する。`--output` は `human` / `json` の選択で既定値は `human`。両方を指定したときは `--json` が最終的に `json` を選ぶ（`strata_cli/cli.py:255-290, 508-516, 2232-2236`）。重複指定による追加効果はない。

## 実行時の動作

実行成功時は stdout に `schema_version: 1`、`ok`、および `operation` を含む JSON オブジェクトを1行で出力する。`operation` にはレシピ名、レシピ revision、操作種別、operation ID、操作結果が入る。JSON は `ensure_ascii=False`、`allow_nan=False` で生成される（`strata_cli/cli.py:1451-1464`）。

`--json` は `ops` 配下の各 one-shot parser に共通で追加され、`main()` が `--json` を `--output json` に正規化する。したがって本コマンドでは実行ロジックの共通 `a.output` 判定を通って JSON 形式が選ばれる。レシピ処理中に出る通常の stdout は stderr に向けられ、最終 JSON 応答は stdout に出る（`strata_cli/cli.py:508-516, 1451-1464, 2232-2237`）。

フラグは操作の副作用を抑止しない。レシピ種別に応じて runtime restart、engine calibration measurement、または component verification が行われ、実行記録も作成される。具体的な操作内容はレシピに依存する（`strata_control/recipes.py:28, 363-439`）。

## 適用条件と副作用

`strata ops run` に適用される。JSON 形式への切替以外に、ファイル・ネットワーク・プロセスへの副作用を `--json` 自身は追加しない。ただし対象のレシピ実行には副作用がある。実行前に recipe revision、任意の profile revision、restart recipe の owner / instance / source digest 条件を照合する。校正測定レシピは各回 `--exclusive` を要求し、別種レシピで `--exclusive` を使うと終了コード2のエラーになる（`strata_control/recipes.py:369-397`; `strata_cli/cli.py:1448-1450`）。

実行開始時に operation journal へ running 記録を作り、終了時に succeeded / failed を記録する。journal は profile ごとの `.ops/<profile>/.runs` 以下に保存される。POSIX ではディレクトリを owner-only と検査し、記録ファイルを mode `0600` で新規作成する。上限に達したときは完了済み記録を prune し、未完了記録だけで上限に達している場合は新規実行を拒否する（`strata_control/journal.py:47-57, 276-313`; `strata_control/recipes.py:397-400, 429-437`）。

## 出力とエラー

成功時は終了コード `0`（操作結果が `ok` の場合）、操作結果が失敗なら結果の `exit_code`（未指定なら `5`）を返す（`strata_cli/cli.py:1458-1464`）。JSON 指定中に共通エラーハンドラへ到達する失敗は、stdout に `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` 形式を出し、エラーコードを終了コードとして返す。たとえば recipe / profile revision の不一致や、必須の `--exclusive` 欠落は実行前エラーになる（`strata_cli/cli.py:527-532, 2166-2193`; `strata_control/recipes.py:369-397`）。

Python の引数 parser 自体が拒否する不正な引数や未知引数は、`main()` の処理開始前に argparse が扱うため、この JSON エラー形式になるとは限らない（`strata_cli/cli.py:2223-2235`）。

## 根拠

- parser と `--output` の既定値: `strata_cli/cli.py:255-290`
- one-shot parser 群への `--json` 登録: `strata_cli/cli.py:508-516`
- `--json` から `output=json` への正規化: `strata_cli/cli.py:2223-2237`
- `ops run` の JSON 応答、stdout 振り分け、終了コード: `strata_cli/cli.py:1448-1464`
- エラー JSON と例外処理: `strata_cli/cli.py:527-532, 2166-2193`
- レシピ実行・事前条件・journal 記録: `strata_control/recipes.py:363-439`
- journal の格納場所、権限検査、上限処理: `strata_control/journal.py:47-57, 276-313`

調査は上記 commit のソースを対象とした。別 OS 上での実行や配布済み CLI の挙動はこの調査では実行・確認していない。
