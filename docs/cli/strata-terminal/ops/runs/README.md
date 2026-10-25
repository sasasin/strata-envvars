# `strata ops runs`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/journal.py` |
| 必須引数 | `--profile PROFILE` |
| 出力形式 | `--output human\|json`（既定値: `human`）、`--json` は JSON 出力の alias |
| 表示抑制 | `--quiet`（human 出力を抑制） |
| 件数上限 | `--limit N`（既定値: `20`、有効範囲: `1..100`） |

## 役割

指定 profile に記録されたローカル operation の一覧を表示します。recipe からの実行記録と、対応する direct runtime/calibration 操作の記録を journal から読み込みます。このコマンド自体は operation を実行せず、結果の詳細確認には `strata ops result` を使います。

## 使い方

```sh
# profile の直近20件を人向け表示
strata ops runs --profile four-gpu

# 最大100件を JSON で取得
strata ops runs --profile four-gpu --limit 100 --output json
```

`--profile` は必須です。`--limit` は整数として解析されます。出力形式は `human` または `json` で、`--json` は `--output json` の alias です。`--quiet` は one-shot command 共通 parser に追加され、human 出力を抑制します。JSON 出力を指定した場合は quiet による stdout 抑制の対象外です。各 option の詳細は [`--profile`](--profile.md)、[`--limit`](--limit.md)、[`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md) を参照してください。

## 表示内容と実行時の動作

journal は profile の operation 保存領域から読み込まれます。該当ディレクトリがなければ空の一覧になります。`.json` ファイルのうち、ファイル名の stem が32桁の小文字16進数の operation ID に一致するものを対象にし、更新時刻の降順で並べて `--limit` 件まで読みます。各正常行には operation ID、recipe 由来か direct 由来か、kind、state、開始・終了時刻が含まれます。実行中状態の記録には `completion_unverified: true` が付きます。

人向け表示は `OPERATION_ID  STATE` の行ごとの一覧です。壊れた・非対応の journal record は一覧全体を止めず、その ID と error を該当行に表示します。記録がない場合は `No operation runs recorded` と表示します。JSON 形式は `schema_version: 1`、`ok: true`、`profile`、`runs` を含む単一 JSON オブジェクトです。

このコマンドは一覧を読むだけで、journal ファイルを作成・変更・削除しません。運用記録の確認後、個別の全 record を確認する場合は [`strata ops result`](../result/README.md) を使います。`completion_unverified` は、呼び出し元が中断した記録などで完了状態を確定できないことを示します。worker が現在も実行中、または停止済みである証拠ではないため、結果や runtime 状態も確認してから再試行してください。

## 実行条件と注意点

- profile の読み込みに失敗した場合や保存領域の権限・形式が不正な場合はエラーになります。journal directory は symlink を拒否し、POSIX では owner-only 権限を検査します。
- `--limit` の範囲外（1〜100以外）は `operation list limit must be 1..100` で拒否されます。整数でない値は argparse の引数解析エラーです。
- operation journal は profile ごとのローカル記録です。保持上限は profile ごとに500件で、新しい operation を記録するときに古い完了済み record が prune されます。この一覧表示時には prune されません。
- POSIX の journal ファイル・directory のアクセス権は制限されます。Windows ACL の挙動は対象 revision の利用者向け文書で release qualification 未完了とされています。

## 関連文書

- [`strata ops run` の概要](../run/README.md)
- [`strata ops result` の概要](../result/README.md)
- [CLI 索引](../../../README.md) の `strata ops runs`
- Strata の [Terminal CLI 運用コマンド説明](../../../../TERMINAL.md)

## 根拠

- Strata `strata_cli/cli.py:255-269` — サブコマンド登録、必須 `--profile`、出力形式、`--limit` の型と既定値。
- Strata `strata_cli/cli.py:509-515,2235-2245` — one-shot parser への `--json` / `--quiet` 追加と quiet 時の出力抑制。
- Strata `strata_cli/cli.py:1404-1408` — journal 呼び出しと human 表示、空一覧時の出力。
- Strata `strata_cli/cli.py:535-542,2160-2173` — 成功時の JSON/human 出力と `ValueError`（`ProfileError` を含む）のエラー処理。
- Strata `strata_control/journal.py:47-57,254-273` — profile journal directory の検査、件数範囲、降順の選択、record 内容、破損 record の行単位エラー化。
- Strata `strata_control/journal.py:1-5,276-310` — journal の記録内容、実行中記録の意味、完了済み record の prune と500件上限。
- Strata `strata_control/recipes.py:38-59` — profile 読み込みと recipe 保存領域の symlink・POSIX 権限検査。
- Strata `docs/TERMINAL.md:96-122` — 利用例、一覧・結果確認、journal の用途・保持・プライバシー上の説明。
