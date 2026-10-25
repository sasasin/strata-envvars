# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

標準出力の形式を、人が読む要約または機械処理向け JSON に切り替えます。名前に `output` とありますが、出力ファイルのパスは受け取りません。

## 使い方

```sh
strata timeskip run --workspace ./project --prompt "format the report" --attempts 0 --output json
```

`run` はまず workspace のチェックポイントを作成し、宣言済みチェックを実行します。上の例もこの処理を行うため、実行する workspace とチェック内容を確認してください。

## 値と既定値

- `human` と `json` のみ受け付けます。既定値は `human` です。短縮別名はありません。
- `choices` にない値は argparse が拒否し、usage とエラーを表示して終了コード 2 になります。`main()` は `parse_known_args()` を呼ぶため、この parser エラーは `_run()` の JSON エラー変換より前に発生します。
- 同じ option を複数回指定した場合の個別仕様は Strata 側に定義されていません。argparse の通常の scalar 引数として扱われ、最後に解析された値が使われます。

## 実行時の動作

- `human`（既定）では、run ID と状態、試行ごとの判定、決定、確認用の `status` / `apply --dry-run` コマンドを人向けの行で標準出力へ表示します。
- `json` では成功時に `{"schema_version":1,"ok":true,"run":...}` 形式の JSON を1行で標準出力へ出します。JSON は `ensure_ascii=False`、`allow_nan=False` で直列化されます。
- run が `failed` または `interrupted` で終わった場合、`json` は `{"schema_version":1,"ok":false,"error":{"code":6,"message":...}}` 形式で失敗を出力し、終了コード 6 を返します。その他の run 状態（`inconclusive` を含む）は、run データを含む成功形式で返されます。これはコマンド実装が失敗判定をこの2状態に限定しているためです。
- `--output` は run の内容や保存先を変えません。run データは state directory に記録され、workspace の checkpoint 作成、revision（指定時）、チェック、判定は同じ経路で行われます。

## 適用条件と副作用

- `run` のみの option です。`strata timeskip status`、`list`、`apply` にも同じ名前の option がありますが、各サブコマンドの parser scope は別です。
- `--output json` でも、workspace に `.strata/checks.json` がない場合の注意は標準エラーに人向けの文で出ます。JSON 応答だけを読む利用側は stderr も別途扱ってください。
- `human` と `json` のどちらでも、run は state directory に状態を保存し workspace の内容を checkpoint へコピーします。`--revise-command` があると候補 directory でそのコマンドを実行し、定義されたチェックも実行します。`--output` 自体はファイルを作成・上書きしません。

## 出力とエラー

- 成功時の JSON 応答は stdout、JSON 選択時の処理エラーも `_error()` 経由で stdout に出ます。人向けエラーは `strata: ...` の形式で stderr に出ます。
- `run` の失敗・中断状態は終了コード 6 です。workspace が directory でない場合、または `.strata/checks.json` を読み込めない場合は終了コード 2 です。これらのエラー形式も `--output json` に従って JSON または人向け表示になります。
- チェック定義がない場合、処理を続けて結果を inconclusive とし、標準エラーに警告します。`--output json` でもこの警告は JSON 化されません。

## 根拠

- Strata `strata_cli/cli.py:352-369` — `timeskip run` parser と `--output` の choices / 既定値。
- Strata `strata_cli/cli.py:2217-2236` — 引数解析、未知引数・option 値の parser 処理、`--quiet` / `--json` による補正。
- Strata `strata_cli/cli.py:527-541,1467-1485` — JSON・人向け応答 helper と run state directory の決定。
- Strata `strata_cli/cli.py:1557-1602` — workspace 検査、チェック定義なしの stderr 警告、run 実行、出力分岐と終了コード。
- Strata `strata_cli/time_skip.py:321-372,408-420,422-493` — state directory への永続化、checkpoint と run の実行・完了状態。
