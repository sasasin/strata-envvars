# `--status`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（`2026-10-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--status` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。未指定時は `False` |

## 役割

現在のデータフォルダに記録されたモデルファイル移動の中断状態を表示します。中断がなければその旨を表示します。`--resume`、`--leave` と同じ「未完了移動」処理経路へ入りますが、`--status` 分岐は照会結果を出力して終了します（`strata_cli/cli.py:621-622, 668-678`）。

## 使い方

```sh
strata models move --status
```

確認するデータフォルダを明示する場合:

```sh
strata models move --from /path/to/old-folder --status
```

`--from` を省略すると `discovery.data_dir(Path.home() / "Strata")` が選ぶフォルダを使います。`--from` の値は `Path` に渡され、ここでは `expanduser()` を呼びません。相対パスは起動時の作業ディレクトリ基準、`~` を含む場合も文字列どおりのパスとして扱われます（`strata_cli/cli.py:617-622`）。

## 値と既定値

値を取りません。`argparse` の `store_true` で定義され、未指定は偽です（`strata_cli/cli.py:162-171`）。位置引数 `NEW_FOLDER` は任意で、help の説明どおり `--status` では不要です。`--output` は `human`（既定）、`json`、`jsonl` を受理します（同 `cli.py:163, 171`）。トップレベル parser の one-shot 共通設定により `--json` と `--quiet` もこの parser で受理されます（同 `cli.py:508-515`）。

## 実行時の動作

1. `--from` があればその値を確認対象にし、省略時は利用中のデータフォルダを解決します（`strata_cli/cli.py:617-622`）。
2. `models_move.interrupted(old)` はフォルダ内の `models-move.json` を読み、状態が `running` / `stopped` / `failed` のいずれかで、`from` と `to` があり、記録された `from` が照会対象と一致し、そのフォルダが存在する場合に候補とします。`running` 状態でも PID と起動 token が一致するプロセスが生存中なら中断扱いにしません（`strata_control/models_move.py:268-272, 303-325`）。
3. 人向け出力は中断時に旧・新フォルダと `--resume` / `--leave` の案内を表示し、該当なしなら `No move was interrupted.` と表示します。どちらも終了コードは `0` です（`strata_cli/cli.py:663-678`）。
4. `--output json` または `jsonl` は機械可読モードとして、`{"schema_version": 1, "ok": true, "interrupted": ...}` の JSON オブジェクトを1件出力します。中断なしの場合 `interrupted` は `null` です。`jsonl` でも status 分岐が出すのはこの1オブジェクトです（同 `cli.py:671-678`）。`--json` は one-shot コマンドで `output=json` に置き換えられます（同 `cli.py:2232-2236`）。

`--status` が指定されると、同時指定の `--resume` / `--leave` より status 分岐が先に実行されます。`--install-dir`、`--plan`、`--cancel-file` および位置引数 `NEW_FOLDER` はこの分岐では参照されず、確認対象を変えるのは `--from` です（`strata_cli/cli.py:617-622, 668-678`）。`--quiet` は人向け標準出力を抑えますが、JSON/JSONL では抑制されません（同 `cli.py:2236-2247`）。

## 適用条件と副作用

通常の status 分岐自体は移動状態ファイルを読み取るだけで、`resume` や `leave` のファイル操作へは進みません（`strata_cli/cli.py:672-678`）。ただし `--from` を省略した場合の `discovery.data_dir()` は `sync_data_dir()` を呼び、Terminal と Desktop の設定が異なると更新時刻の新しい側を採用して、もう一方の設定ファイルへ `data_dir` と `data_dir_at` を書き戻します（`strata_control/discovery.py:227-238, 241-259, 277-289`）。したがって「状態照会によるモデル移動はしない」一方、既定フォルダ解決に伴う設定同期の書き込みは起こり得ます。`--from` を指定した場合はこのデータフォルダ解決を通りません（`strata_cli/cli.py:620`）。

`interrupted()` は読み取った状態ファイルが壊れている／読めない場合に空状態として扱い（`strata_control/models_move.py:268-272`）、フォルダ走査やモデル内容の検証は行いません。status が報告するのはこの journal 判定結果です。

## 出力とエラー

status 照会では、中断あり・なしのいずれも終了コード `0` です（`strata_cli/cli.py:673-678`）。ここで `--status` を使わず `--resume` または `--leave` だけを指定した場合、中断記録がなければ人向けエラーを stderr に出し `5`、JSON/JSONL なら `ok:false` の JSON を stdout に出して `5` を返します（同 `cli.py:679-684`）。これは `--status` 自身の失敗経路ではありません。

## 根拠

- parser、値の型、関連 option: `strata_cli/cli.py:162-171`
- one-shot 共通 `--json` / `--quiet` の登録と適用: `strata_cli/cli.py:508-515, 2232-2247`
- status の対象フォルダ選択と dispatch: `strata_cli/cli.py:617-622`
- status 出力・終了コード、および resume/leave との分岐: `strata_cli/cli.py:663-705`
- journal の読取と interrupted 判定: `strata_control/models_move.py:268-325`
- 既定データフォルダ選択時の設定同期: `strata_control/discovery.py:227-259, 277-289`

確認範囲は当該 commit の checkout 内の Python parser と実装です。Release 配布物や別 platform での実行結果は確認していません。
