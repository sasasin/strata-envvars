# `--rollback-result`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、確認時に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--rollback-result` |
| 別名 | なし |
| 値 | 必須の `REPORT.json`。適用済みの calibration report ファイルへのパス |

## 役割

以前 `--apply-result` で適用した calibration について、適用前に保存した run config と setup 設定を復元します。単にファイルを戻す操作ではなく、適用記録と現在の状態を照合し、復元候補でエンジンのスモーク生成を行ってから書き戻します。

## 使い方

```sh
strata engine calibrate --profile four-gpu --review-rollback /absolute/path/to/calibration.json
strata engine calibrate --profile four-gpu --rollback-result /absolute/path/to/calibration.json --exclusive
```

最初のコマンドは読み取り専用の適用可否確認です。復元を実行するコマンドでは `--exclusive` が必須です。`--profile` には保存 profile 名、または明示的な JSON run-config パスを指定できます。

## 値と既定値

- `REPORT.json` は値必須で、オプションに既定値はありません。値の型・形式は parser では文字列引数として受け取り、実行時にそのパスの report を読み込みます。parser は複数回指定の独自処理やパス形式の制約を定義していません。
- `--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` は相互排他で、いずれか一つが必須です。`--rollback-result` は `--out` と併用できません。
- `--exclusive` はフラグで、`--measure`、`--apply-result`、`--rollback-result` のいずれかとだけ併用できます。rollback では指定がなければ終了コード 2 で拒否されます。
- `--output` は `human`（既定）または `json`。JSON 出力は `--output json` で指定します。

## 実行時の動作

CLI は report を読み、`review_rollback` 相当の検査を実行します。report は通常ファイルかつ 2 MiB 以下で、schema version、種類、suite、report ID、設定値、内容 checksum が現行形式に合わなければ拒否されます。適用時には対応する owner-only application record とバックアップも必要です。record が指す setup settings パスが現在のパスと一致することも確認します。

復元可否の検査では、report の source config と対象が一致し、バックアップ checksum、適用後 run config、setup settings が application record の checksum と一致し、エンジン・モデル・hardware・profile identity も適用時の値に合う必要があります。profile のポートが応答中なら適用不可です。どれかが変化・欠落していれば stale として終了コード 6 になり、ファイルは復元されません。

実行時は profile config のロックと managed activity の exclusive lease を取得し、設定ポートの server と managed Strata instance がないことを確認します。その後、保存済みの適用前 run config を候補として engine を起動し、少なくとも1 token の smoke generation が成功することを確認します。スモーク中にも run config と setup settings が変わっていないこと、再検査でも適用可能なことを確かめてから、適用前 config と setup settings を復元します。適用前に setup settings ファイルが存在しなかった場合は、そのファイルを削除します。復元後も calibration backup と application record は残ります。

保存 profile を `--profile` で指定した直接実行は `engine.calibrate.rollback` の operation record としてローカル journal に記録されます。明示的な run-config パスを指定した場合は、CLI helper の仕様上この journal 記録を行わない legacy 経路です。journal の記録に失敗した場合も rollback 処理へ進む前にエラーとなります。

## 適用条件と副作用

- `--exclusive` は、対象デバイスを使う他の model instance が停止済みだという利用者の確認です。Strata は設定ポートと managed instance を検査し、対応 OS では managed host と共有する activity lease を排他取得しますが、直接起動された旧式 server、無関係な GPU プロセス、Windows 上の managed activity lease はこの保護対象外です。これらの停止確認は利用者側で必要です。
- rollback は engine を起動して smoke generation を実行するため、GPU 等の実リソースを使います。rollback 対象は report に対応する application record と backup から特定されるので、同記録がない古い適用の自動 rollback はできません。
- profile が保存名か JSON パスかにより journal 記録の有無が異なります。profile 名の解決と run config の読込は `profiles.resolve` に従います。

## 出力とエラー

- 成功時は終了コード 0。human 出力は `Previous calibration configuration restored; restart the model to use it`、JSON 出力は `ok: true` と `rollback` 結果を含みます。結果には変更有無、report ID、source config、復元 config checksum、setup settings 削除有無、smoke token 数、backup パスが含まれます。
- `--exclusive` 不足など CLI 側の引数条件エラーはコード 2。report、application record、backup の形式・読込エラー等は通常コード 5、stale 状態、smoke 失敗、復元失敗等はコード 6 です。human エラーは stderr の `strata: ...`、JSON モードでは stdout の `ok: false` と error object に出ます。
- smoke generation が失敗するか token を返さなければ復元を行いません。smoke 後に設定が変わった場合も、変更を検知して書き戻しを中止します。復元の片側書き込みに失敗した場合は、元の適用後状態への復帰を試み、復帰にも失敗すれば backup から手動復旧が必要な旨をエラーに含めます。
- 中断時は操作完了が不明になる場合があります。保存 profile の journal は例外時に失敗または `completion_unknown` を記録し、keyboard interrupt の CLI 終了コードは 130 です。

## 根拠

- Parser、action の相互排他、値名、`--exclusive`・出力形式: `strata_cli/cli.py:174-189`。
- CLI の必須条件、rollback 呼び出し、journal intent、成功表示: `strata_cli/cli.py:1048-1056`, `strata_cli/cli.py:1059-1064`, `strata_cli/cli.py:1104-1113`。
- profile 名と JSON path の区別: `strata_control/profiles.py:382-388`。
- exclusive lease、port / managed instance 検査、rollback の照合・smoke・再確認・復元・復旧経路: `strata_control/calibration.py:205-229`, `strata_control/calibration.py:684-749`。
- report と application record の検証、owner-only backup 読み込み: `strata_control/calibration.py:339-359`, `strata_control/calibration.py:483-523`, `strata_control/calibration.py:629-643`。
- config / setup settings backup、適用記録、settings 復元、atomic replacement: `strata_control/calibration.py:576-626`, `strata_control/calibration.py:412-423`。
- human / JSON 成功・エラー出力と例外コードの変換: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2119-2193`。
- 保存 profile の直接実行 journal と interruption の状態記録: `strata_control/journal.py:376-393`。
- 公式利用例と運用上の制約（ソース同 revision 内の Terminal 文書）: `docs/TERMINAL.md:124-132`, `docs/TERMINAL.md:160`。

今回の調査では CLI `--help` や Release artifact は追加確認していません。記載は上記 checkout の parser、処理実装、同 checkout の Terminal 文書に基づきます。
