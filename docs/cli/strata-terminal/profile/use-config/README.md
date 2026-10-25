# `strata profile use-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| 位置引数 | `name`（参照先を変更する保存済み profile 名） |
| 主なオプション | `--from-config CONFIG.json`（必須）、`--plan`、`--if-revision REVISION`、`--output human\|json` |
| 共通オプション | `--json`（`--output json` の alias）、`--quiet` |

## 役割

保存済み profile が参照する run-config JSON ファイルを別のファイルへ切り替えます。profile の serving overrides は引き継がれます。run-config の内容を書き換えたり、このコマンドから稼働中の server を再起動したりはしません。parser の説明は「saved profile を another run config file に向ける」としています（`strata_cli/cli.py:69-95,969-985`、`strata_control/profiles.py:252-263`）。

## 使い方

まず変更案を確認し、そのとき出力された revision を使って保存できます。

```sh
strata profile use-config four-gpu --from-config /absolute/path/next-model.json --plan --output json
strata profile use-config four-gpu --from-config /absolute/path/next-model.json --if-revision PROFILE_REVISION --output json
```

`name` は既存の保存済み profile でなければなりません。`--from-config` は省略できません。`--plan` では source の変更案、profile revision、config の `model_name`（あれば）、変更が保存対象かどうかを返します。保存実行では更新後の profile と新旧 revision を返します（`strata_cli/cli.py:89-95,968-985`）。

## 実行時の動作

指定パスは `~` を展開し、存在する実体への絶対パスに解決します。対象は通常ファイルである必要があり、UTF-8（BOM 付きも可）の JSON として読み取れること、トップレベルの `args` が文字列だけの配列であること、`exe` と `tokenizer` が空でない文字列であることを確認します。`exe`・`tokenizer` のファイルが存在するか、`args` が実際に実行可能かまでは、この validation では確認しません（`strata_control/profiles.py:135-147,252-263`）。

`--plan` を指定すると保存処理を呼ばず、profile の source 切り替え案を表示します。省略時は profile を revision 条件付きで保存し、以前の profile 内容を履歴へ退避してから profile ファイルを atomic replace します。設定が同一なら revision と履歴を増やしません。いずれの場合も、既存 overrides を含む profile の他の値は維持されます（`strata_cli/cli.py:975-985`、`strata_control/profiles.py:252-263,266-295`）。

profile の保存先は通常 POSIX では `$XDG_CONFIG_HOME/strata/profiles`（未設定なら `~/.config/strata/profiles`）、Windows では `%APPDATA%/Strata/profiles`（未設定ならホーム以下）です。`STRATA_PROFILE_DIR` が設定されていればそちらが優先されます（`strata_control/profiles.py:38-55`）。

## 適用条件と副作用

- 対象 profile が存在し、読み込み可能で、指定した config が検証を通る必要があります。profile 名は小文字英字で始まり、以降は `a-z`、数字、`_`、`-` のみ、最大64文字です（`strata_control/profiles.py:25,48-55,150-166`）。
- 通常実行では profile データと `.history/<name>/` の履歴に書き込みます。profile の保存は名前ごとの lock を取り、更新前 revision を照合します（`strata_control/profiles.py:185-210,266-295`）。
- server プロセス、ネットワーク、GPU はこの処理から起動・変更しません。人間向け成功メッセージにも「running instance unchanged」と明記されています。新しい source config を稼働中の managed server に反映するには、別途 `strata runtime restart` の計画と実行が必要です（`strata_cli/cli.py:981-985`、使い方の例は Strata `docs/TERMINAL.md:78-85`）。
- `--if-revision` は preview 時点の profile revision と一致しなければ失敗します。未指定でも保存時に読み込んだ revision との競合検査は行われます（`strata_cli/cli.py:968-985`、`strata_control/profiles.py:266-294`）。

## 出力とエラー

既定の `--output human` は人間向けメッセージを stdout に出します。`--output json` は成功・失敗を JSON で stdout に出します。`--json` はこの one-shot コマンドでは `--output json` と同じです。`--quiet` は人間向け情報出力を抑えます（JSON 出力時は抑制されません）（`strata_cli/cli.py:508-515,527-542,2223-2248`）。

存在しない profile、読み取れない config、JSON/schema 不正などは `ProfileError` 等をエラーとして返します。profile 不在や config の読み込み失敗は終了コード `5`、変更競合・古い `--if-revision` は `6`、無効な profile 名など既定の validation error は `2` です。JSON 出力時は `ok: false` と `error.code` / `error.message` を含み、人間向けでは `strata: ...` を stderr に出します（`strata_control/profiles.py:30-35,48-50,135-147,150-166,252-263,266-294`、`strata_cli/cli.py:527-532,2166-2183`）。

## 関連文書

- [CLI 索引](../../../README.md) — コマンド階層とこのコマンドの option 一覧。option 個別文書は索引のリンクを参照してください。
- [profile コマンド概要](../README.md) — 索引上の profile 親コマンド概要。

## 根拠

- `strata_cli/cli.py:69-95` — `profile use-config` の parser と、`--json` / `--quiet` 共通 option の登録箇所 `strata_cli/cli.py:508-515`。
- `strata_cli/cli.py:958-985` — profile の読み込み、preview・revision 照合、保存、結果表示。
- `strata_control/profiles.py:25-55,120-166` — profile 名・保存先・profile と run-config の validation。
- `strata_control/profiles.py:185-234,252-295` — lock、source の選択、revision 競合検査、履歴と atomic 保存。
- `strata_cli/cli.py:527-542,2166-2183,2217-2248` — 成功・失敗の出力、例外から終了コードへの変換、共通 option の適用。
- Strata `docs/TERMINAL.md:78-85` — managed server で source を切り替えた後に別コマンドで restart する利用例。

調査範囲は上記 commit の checkout 内の Terminal CLI parser と profile 実装です。Release 配布物との照合や、各 OS での実行確認は行っていません。
