# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--output` |
| 別名 | `なし`（`--json` は同じ JSON モードを選ぶ別 option） |
| 値 | `human` または `json` |

## 役割

コマンド結果を人向け表示または JSON として標準出力に出します。値は parser で `human` / `json` に制限され、既定値は `human` です。ファイルパスを受け取る出力先指定ではありません（`strata_cli/cli.py:89-95`）。

## 使い方

```sh
strata profile use-config demo --from-config /path/to/run-config.json --plan --output json
```

`--plan` と組み合わせると保存せずに確認できます。`--output human` を省略した場合も同じ human モードです。

## 値と既定値

- `human`: 既定値。成功時は `Config: <変更前> -> <変更後>`（plan 時）、または保存結果を示す文を標準出力へ表示します（`strata_cli/cli.py:975-985`）。
- `json`: 成功時は `schema_version: 1` と `ok: true` を含む JSON を標準出力へ出します。plan の場合は `profile`、`revision`、`source_config` の変更前後、`model_name`、`would_save` が含まれ、保存時は profile、旧・新 revision と変更前後が含まれます（`strata_cli/cli.py:975-985, 535-542`）。
- 省略時は `human` です。別の値（空文字を含む）は argparse の `choices` 検証で拒否され、通常の parser usage error として標準エラーへ出て終了コード 2 になります（`strata_cli/cli.py:95, 2223-2231`）。

## 実行時の動作

`--output json` は `_profile_command` 内で機械可読モードとして扱われ、成功時には `_success` が JSON を1行標準出力へ出します。失敗時は `_error` が `schema_version: 1`、`ok: false`、`error.code`、`error.message` を JSON として標準出力へ出し、該当する終了コードを返します。human モードのエラーは `strata: ...` の形で標準エラーへ出ます（`strata_cli/cli.py:527-542, 958-960, 2127-2128, 2150-2188`）。

`--json` も one-shot profile command parser 群に追加される alias です。指定すると `main` が `a.output` を `json` に設定します。`--quiet` は human 表示を抑制しますが、`json` / `jsonl` は quiet の stdout 捕捉を通らないため JSON 出力は維持されます。`use-config` の parser で受理する `--output` 値に `jsonl` はありません（`strata_cli/cli.py:508-515, 2232-2247`）。

表示形式は profile 更新の有無を変えません。`--plan` なら変更候補を表示して保存せず、通常実行なら検証後に profile を保存します。保存時には旧 profile の履歴を必要に応じて記録し、profile ファイルを更新します。どちらの場合も run config は読み取り、実行中 instance は変更しません（`strata_cli/cli.py:969-985`; `strata_control/profiles.py:252-263, 266-295`）。

## 適用条件と副作用

この option は `strata profile use-config` の parser にのみ属します。同コマンドは `--from-config` を必須とし、指定先を実在するファイルとして解決し、run config の JSON 形式（`args` が文字列配列、`exe` と `tokenizer` が空でない文字列）を検証します（`strata_cli/cli.py:89-95`; `strata_control/profiles.py:135-147, 252-263`）。

`--output` 自体は保存・削除・外部プロセス起動を行いません。副作用は `--plan` の有無によります。保存する経路では profile 更新と履歴保存が行われ、実行中 instance はそのままです。`--if-revision` が指定され、現在の profile revision と一致しなければ保存前に失敗します（`strata_cli/cli.py:971-985`; `strata_control/profiles.py:266-295`）。

## 出力とエラー

- 指定可能な出力形式は `human` / `json` のみです。結果は標準出力に出ます。JSON の validation / revision などコマンド処理上の失敗は JSON モードなら JSON、human モードなら標準エラーのメッセージとなり、失敗コードを返します（`strata_cli/cli.py:527-542, 2150-2188`）。
- profile 未保存、run config の読み込み・形式不正、preview 後の revision 不一致などは失敗経路です。特に revision の競合は終了コード 6、欠落 profile や run config の利用不能は通常コード 5 を含む `ProfileError` として処理されます（`strata_cli/cli.py:971-974`; `strata_control/profiles.py:135-147, 150-166, 252-263, 266-295`）。
- option 値や必須引数など parser 段階のエラーは、`--output json` を指定していてもコマンド処理前に発生するため、argparse の標準エラー表示と終了コード 2 です（`strata_cli/cli.py:89-95, 2223-2231`）。

## 根拠

- parser 定義、値の choices と既定値、コマンド scope: `strata_cli/cli.py:89-95`
- `--json` と `--quiet` の追加、出力形式選択と quiet の分岐: `strata_cli/cli.py:508-515, 2232-2247`
- `use-config` の human / JSON 成功 payload と plan / save 分岐: `strata_cli/cli.py:958-985`
- 成功・失敗の stdout / stderr と JSON envelope: `strata_cli/cli.py:527-542`
- profile と run config の読込・validation、revision 確認、保存・履歴更新: `strata_control/profiles.py:135-166, 252-263, 266-295`

調査範囲は上記 revision の checkout 内の Terminal CLI と profile 実装です。配布済み Release artifact や各 OS の実行環境での出力差は確認していません。
