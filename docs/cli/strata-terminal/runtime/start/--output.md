# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ JSON 出力を選ぶ別オプション） |
| 値 | `human` または `json` |

## 役割

起動結果や起動計画を端末向け表示または JSON で出力します。出力形式を選ぶオプションであり、runtime の起動・待機条件自体は変えません。

## 使い方

```sh
strata runtime start --profile four-gpu --output json
strata runtime start --profile four-gpu --plan --output json
```

1つ目は起動を実行して結果を JSON で出します。2つ目は起動候補を確認する計画を JSON で出し、runtime は開始しません（計画で `would_start` は `false`）。

## 値と既定値

- 省略時は `human` です。
- `human` と `json` のみを受理します。その他の値は `argparse` の choices 検証で拒否されます。
- 同じ `--output` を複数回指定した場合、`argparse` の通常の `store` 動作により最後に指定した値が残ります。
- `--json` は `runtime start` にも追加される one-shot 共通オプションで、指定時は `--output json` と同じ出力経路になります。`--output` の短縮 alias ではありません。

## 実行時の動作

通常起動では `--output` の値は runtime の `management.runtime_action()` へ渡されず、CLI 側で表示形式を選択します。JSON 指定時は stdout に `schema_version` と runtime の結果を含む1行 JSON を出します。human 指定時は `<profile>: <state>` を中心に、結果に応じて instance ID、API URL、launch 検証状態、readiness、エラーを添えた行を出します。起動失敗時の engine log hint は stderr に出します。

`--plan` と併用し、計画が成功した場合は `{"schema_version":1,"ok":true,"plan":...}` の JSON が stdout に出ます。`--output human` の場合も plan 分岐は人向け要約へ変換せず、`_success()` の既定動作により整形 JSON を stdout に出します。これは通常起動の human 表示とは異なる挙動です。

`--quiet` は one-shot コマンド用として登録されていますが、`--output json` または `--json` のときは JSON 出力を保つため quiet の human 出力抑止経路には入りません。

## 適用条件と副作用

通常の起動では saved profile に基づきバックグラウンド owner host を起動し、この端末を閉じても serving を継続します。これは `--output` の副作用ではなく、`runtime start` 自体の動作です。host のログは profile ごとの runtime log に追記モードで開かれ、host の stdout/stderr がそのファイルへ結合されます。出力形式を JSON にしても、このログ出力先は変わりません。

`--wait` の既定値は300秒で、有効範囲は0〜600秒です。0を指定すると host の状態ファイルができた段階で `state: "starting"` を成功結果として返し、ready まで待ちません。`--shutdown-timeout` は既定30秒、0〜300秒です。これらは `--output` の選択とは独立です。

## 出力とエラー

- JSON の通常結果は `schema_version` を付けた runtime 結果です。成功時の CLI 終了コードは0、runtime が返す失敗では結果の `exit_code`（通常の起動失敗6、startup wait 超過8）が CLI 終了コードになります。
- JSON の plan 成功も終了コード0です。plan が失敗した場合は共通エラー処理が JSON エラーを stdout に出します。
- human の通常結果は stdout、失敗時の `strata:` エラー文は stderr です。`ProfileError` などのエラーコードは例外の `exit_code`（なければ2）が用いられます。
- 起動 host 自体が状態ファイルを作れず失敗すると、runtime log の場所を含むエラーになります。startup wait 超過では `startup_wait_expired` と最後に観測した phase が結果に含まれます。
- choices にない `--output` 値など parser エラーは `argparse` の usage/error 経路で拒否されます。

## 根拠

- Parser と値の選択肢・既定値: `strata_cli/cli.py:203-212`。
- one-shot 共通の `--json` / `--quiet` 追加: `strata_cli/cli.py:508-515`。`--json` を `output=json` に反映: `strata_cli/cli.py:2232-2236`。
- 出力形式の分岐、plan 包装、人向け状態表示、終了コード: `strata_cli/cli.py:1331-1373`。
- machine/human 共通 success/error の stdout・stderr 形式: `strata_cli/cli.py:527-542`。
- quiet と JSON の相互作用: `strata_cli/cli.py:2236-2245`。
- start の待機時間・timeout 検証、plan が候補を2回照合すること、実行 journal、runtime への引き渡し: `strata_control/management.py:202-230`。
- host 起動、log append、stdout/stderr の log への結合、`wait=0`、ready wait timeout 時の結果: `strata_control/runtime.py:518-599`。
- runtime start が端末から独立した background service である旨: `strata_cli/cli.py:197-205`、`strata_control/runtime.py:528-530`。

調査範囲は上記 checkout の Python CLI と runtime 実装です。既存 CLI の `--help`、Release 配布物、Windows/macOS/Linux それぞれでの実行は照合していません。
