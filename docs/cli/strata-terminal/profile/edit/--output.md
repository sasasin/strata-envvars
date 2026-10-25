# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile edit` |
| オプション | `--output` |
| 別名 | `--json`（出力を `json` にする alias） |
| 値 | `human` または `json` |

## 役割

profile 編集の成功結果と CLI が処理するエラーを、人向けテキストまたは JSON として出力します。エディターの起動、編集対象、検証、保存方法は変えません。

## 使い方

```sh
strata profile edit work --output json
```

`work` は保存済み profile 名です。人向け表示が既定です。

## 値と既定値

- `human`: 既定値。成功時は `Saved profile <name>: <旧revision> -> <新revision>` を標準出力に表示します。
- `json`: 成功時に1行の JSON を標準出力に出します。通常の成功オブジェクトには `schema_version: 1`、`ok: true`、`profile`、`previous_revision`、`revision`、`changes` が含まれます。
- `--json` は `--output json` と同じ結果です。この alias は profile edit を含む one-shot parser に登録されます。指定すると `main` が `a.output` を `json` に設定します。
- `--output` を複数回指定した場合は argparse の通常の `store` 動作で最後の値が残ります。`human` と `json` 以外は parser が拒否し、usage とエラーを標準エラーに出して終了コード 2 になります。
- `--quiet` も同じ one-shot parser に追加されます。`human` と組み合わせた成功時は標準出力を抑制します。`json` 時は JSON を抑制しません。

## 実行時の動作

`_profile_command` は `a.output == "json"` を出力モードとして使い、`profiles.edit` の結果を `_success` に渡します。JSON 成功時は1行の JSON、人向け成功時は revision を含む1行です。差分 `changes` は profile のトップレベル項目ごとに旧値と新値を記録します。

編集の実処理は `strata_control.profiles.edit` が行います。保存済み profile を読み、`VISUAL`、なければ `EDITOR` の値を shell 文字列としてではなく `shlex.split` した argv に分け、profile ディレクトリ内の一時 JSON コピーを引数にしてエディターを起動します。エディター終了後に JSON と profile schema を検証し、元の revision と一致する場合に保存します。成功し内容が変わった場合は旧版を history に保存します。実行中のサーバー設定はこの処理では変更しません。

## 適用条件と副作用

- `--output` は `strata profile edit` にだけ属する parser option です。`strata profile` 親 parser や別サブコマンドの設定ではありません。
- `--output` 自体はファイルやプロセスに作用しません。`profile edit` 全体としては外部エディターのプロセスを起動し、成功時には profile を更新する可能性があります。
- profile の保存場所は `STRATA_PROFILE_DIR` があればその値、Windows では `%APPDATA%` 配下（未設定ならホームの `AppData/Roaming`）、その他の OS では `XDG_CONFIG_HOME` 配下（未設定なら `~/.config`）です。
- `VISUAL` と `EDITOR` のどちらも未設定、または分割後のコマンドが空なら edit は失敗します。エディターが非ゼロ終了、編集 JSON が不正、schema 検証失敗、または編集中に revision が変わった場合は保存せず、一時 draft の場所をエラーに含めて保持します。それ以外の経路では一時ファイルを削除します。
- profile 名は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です。名前が無効、profile が未保存、ファイルが不正な場合も edit は失敗します。

## 出力とエラー

- `--output human`（既定）の CLI エラーは `strata: <説明>` の形で標準エラーに出ます。`--output json` または `--json` の場合は `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を標準出力に出します。
- `ProfileError` は既定で終了コード 2 です。profile 不在・読み込み失敗はコード 5、エディター非ゼロ終了や revision 競合はコード 6 になります。編集 JSON の parse failure は `ProfileError` の既定コード 2 です。
- `--quiet` と人向け出力の併用では成功時の標準出力を捨てます。失敗時には捕捉済みの標準出力があれば標準エラーに戻します。JSON 出力は quiet の抑制対象外です。
- `--output` の選択肢違反は argparse の parser error 経路なので、JSON error object ではなく標準エラーの usage/error と終了コード 2 になります。

## 根拠

- `strata_cli/cli.py:96-98` — `profile edit` parser と `--output` の選択肢・既定値。
- `strata_cli/cli.py:508-515` — profile edit への `--json`、`--quiet` の追加。
- `strata_cli/cli.py:527-542` — human/JSON 成功・失敗の出力形式。
- `strata_cli/cli.py:958-1005` — profile edit handler と成功時 payload。
- `strata_cli/cli.py:2166-2188` — `ValueError` / `OSError` / `ClientError` のエラー出力と終了コード処理。
- `strata_cli/cli.py:2223-2248` — parser error、`--json` の適用、quiet の標準出力抑制。
- `strata_control/profiles.py:38-55` — profile ディレクトリと名前規則。
- `strata_control/profiles.py:120-132`, `150-166` — profile schema 検証と読込失敗。
- `strata_control/profiles.py:266-295` — revision 照合、history 作成、profile 保存。
- `strata_control/profiles.py:349-379` — editor 選択・起動、一時 JSON、編集後検証、draft 保持・削除。

調査は parser とソース上の処理を対象に行いました。CLI の実行、build、テストは行っていません。
