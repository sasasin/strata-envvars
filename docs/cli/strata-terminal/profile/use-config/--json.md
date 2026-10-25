# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らないフラグ。出力形式を JSON にする |

## 役割

設定ファイルの切り替え結果やエラーを JSON で出力します。profile の保存を行うかどうかは `--json` ではなく `--plan` で決まります。

## 使い方

```sh
strata profile use-config work --from-config /path/to/strata-model.json --json
```

保存せず変更案を確認する場合:

```sh
strata profile use-config work --from-config /path/to/strata-model.json --plan --json
```

## 値と既定値

`--json` はフラグで、値を指定しません。未指定時は `--output` の既定値 `human` が使われます。`--output` は `human` または `json` を受け付け、`--json` は `--output json` の alias です。両方を指定した場合も JSON になります。`--from-config CONFIG.json` は必須です。

## 実行時の動作

parser は `use-config` に `--output {human,json}`（既定 `human`）を定義し、profile の one-shot parser 群へ `--json` フラグを加えます。引数解析後、`--json` が有効なら `output` を `json` に設定します。

処理は保存済み profile を読み、指定された設定ファイルを検証して切り替え案を作ります。`--plan` 併用時は `source_config` の変更前後、revision、参照先設定の `model_name`、変更が保存対象かを示す `would_save` を含む成功 JSON を出し、profile は保存しません。`--plan` がない場合は profile を保存し、profile 内容、前後の revision、`source_config` の変更前後を返します。保存しても実行中の instance は変わらない旨は人向け出力に記されます。

JSON 成功出力は `schema_version: 1` と `ok: true` を含みます。JSON エラー出力は `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含みます。JSON は標準出力へ一行で出力されます。

## 適用条件と副作用

`--json` は出力形式だけを変えます。profile の書き込みは `--plan` を付けない場合に行われ、既存内容が変わるときは profile の履歴を作成してから atomic replace で保存します。同じ内容なら revision を変えず保存処理を終えます。プロファイルの保存先は `STRATA_PROFILE_DIR`、Windows の `APPDATA`、または Unix 系の `XDG_CONFIG_HOME`（未設定時は `~/.config`）を基に決まります。

`--if-revision REVISION` を指定すると、プレビュー時点から profile が変わっていた場合に保存を拒否します。指定値が preview の revision と一致しない場合も失敗します。`--plan` の場合も既定の revision と任意指定の `--if-revision` を照合します。

## 出力とエラー

- profile 名、profile ファイル、`--from-config` の値や JSON 内容が不正・不在の場合、JSON モードではエラーオブジェクトを標準出力へ出します。失敗時の終了コードはエラーごとの `exit_code`（未指定なら 2）です。
- profile の revision が preview 後に変わった場合、または `--if-revision` が一致しない場合は終了コード 6 で失敗します。
- `--json` の付け忘れを含む parser 段階の不正引数は実行前に拒否されます。コードでは `parse_known_args` 後に未知引数を `ap.error` へ渡すため、これらは標準の argparse usage/error 表示となり、JSON 応答にはなりません。
- profile 読み込み時、権限修復が必要と判断されたファイルは一度その場で修復される場合があります。これは JSON 形式とは独立した読み込み時の副作用です。

## 根拠

- `strata_cli/cli.py:89-95` — `use-config` の位置引数、必須 `--from-config`、`--plan`、`--if-revision`、`--output` と既定値。
- `strata_cli/cli.py:508-515` — `profile_source` を含む one-shot parser 群へ `--json` を追加。
- `strata_cli/cli.py:2223-2236` — 引数解析、未知引数の拒否、`--json` から `output=json` への変換。
- `strata_cli/cli.py:527-542` — JSON 成功・エラー応答の構造と出力先。
- `strata_cli/cli.py:958-985` — profile/設定ファイルの読み込み、revision 照合、plan 応答と保存応答。
- `strata_cli/cli.py:2166-2188` — `ValueError`、`OSError` 等の捕捉と JSON エラー化。
- `strata_control/profiles.py:38-45` — profile 保存ディレクトリの環境変数・既定値。
- `strata_control/profiles.py:135-147,150-166` — run config と profile の読み込み・検証、読み込み失敗。
- `strata_control/profiles.py:252-263` — 新しい run config の実在確認・形式検証と変更案生成。
- `strata_control/profiles.py:266-295` — revision 競合確認、履歴保存、profile の atomic 保存。

調査範囲は上記 checkout のソースです。CLI の実行やテストは行っていません。
