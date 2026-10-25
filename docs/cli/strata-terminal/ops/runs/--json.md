# `strata ops runs --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ |

## 役割

操作実行履歴の一覧を、人向け表示の代わりに機械処理しやすい JSON で標準出力します。履歴の取得範囲は `--limit`、対象プロファイルは必須の `--profile` で指定します。

## 使い方

```sh
strata ops runs --profile local --json
strata ops runs --profile local --limit 50 --json
```

`--json` は `--output json` の alias です。`--output json` を直接指定することもできます。

## 値と既定値

値は不要で、既定値は偽（人向け出力）です。parser は `store_true` として登録します。`--json` がないときの出力形式は `--output` の既定値 `human` です。`--limit` は整数で既定値 20、journal 側で 1〜100 に制限されます。0、負数、101 以上は履歴取得時にエラーになります。`--json` 自体に追加の値検証はありません。

## 実行時の動作

`--json` は `ops` の各 action parser に共通 option として追加されます。したがって `runs` でも利用でき、トップレベルの dispatch がこのフラグを `output=json` に変換します（`strata_cli/cli.py:508-515,2232-2236`）。parser でのコマンド階層、必須の `--profile`、`runs` に限る `--limit` は `strata_cli/cli.py:255-270` にあります。

`runs` の処理は `journal.list_runs(profile, limit)` を呼び、成功時に `{"schema_version": 1, "ok": true, "profile": ..., "runs": [...]}` を JSON 1行で標準出力します。JSON 出力は `ensure_ascii=False`、`allow_nan=False` です。人向け出力では各実行の ID と状態を行ごとに出し、空の場合は `No operation runs recorded` と表示します。JSON 出力が空一覧の場合も `runs: []` を含む成功オブジェクトを返します（`strata_cli/cli.py:1391-1408,535-542`）。

一覧に含む記録は更新時刻の降順で、上限件数までです。各要素には `operation_id`、`recipe`（直接実行の場合は null）、`origin`、`kind`、`state`、`started_at`、`finished_at`、`completion_unverified` が含まれます。`running` 状態は `completion_unverified: true` として示されます。読み取りに失敗した個別記録は一覧全体を失敗させず、該当要素に `operation_id` と `error` を含めます（`strata_control/journal.py:254-273`）。

## 適用条件と副作用

この option は出力形式だけを選び、journal の読み取り条件や一覧の内容を変えません。`runs` の実装は対象プロファイルの `.runs` ディレクトリと記録ファイルを読み取ります。ディレクトリが存在しなければ空一覧です。出力先ファイルの作成・上書きは行いません（`strata_cli/cli.py:1404-1408`、`strata_control/journal.py:47-57,254-273`）。

JSON 形式は `--json` のほか `--output json` でも選べます。`--output` は `human` または `json` の選択肢です。`--json` を指定すると main 処理が `output` を `json` に設定し、後続の `_ops` がその値で出力形式を選びます（`strata_cli/cli.py:266-267,2232-2236,1391-1394`）。

## 出力とエラー

正常終了は終了コード 0 です。`--limit` が 1〜100 の範囲外なら journal が `ProfileError`（`ValueError` 系）を発生させ、CLI は `{"schema_version": 1, "ok": false, "error": {"code": ..., "message": ...}}` の JSON を出力して対応するコードで終了します（`strata_control/journal.py:254-256`、`strata_cli/cli.py:527-532,2166-2173`）。

journal 内の個別記録が不正な場合は、前述のとおり一覧の `error` 要素として返されます。ディレクトリ走査などで `OSError` が起きた場合は CLI の共通エラー処理に入り、JSON 選択時はファイル操作エラーを JSON で標準出力し、終了コード 6 を返します（`strata_control/journal.py:260-273`、`strata_cli/cli.py:2176-2183`）。option の値不足・不正な値ではなく追加引数がある場合は parser が未認識引数として拒否します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:255-270` — `ops runs` の parser、`--profile` と `--limit`。
- `strata_cli/cli.py:508-515` — `--json` を各 `ops` action parser に後付けする共通登録。
- `strata_cli/cli.py:1391-1408,2232-2236` — JSON mode の選択と一覧コマンドの出力。
- `strata_cli/cli.py:527-542,2166-2183` — JSON 成功・エラー envelope と終了コード処理。
- `strata_control/journal.py:47-57,254-273` — journal の参照先、上限検証、並び順、返却フィールド、個別記録エラー。

調査は記載した checkout のソースに限定しました。CLI help の実行、ビルド、テストは行っていません。
