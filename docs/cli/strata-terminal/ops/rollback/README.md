# `strata ops rollback`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |

## 役割

保存済み operator recipe を、指定した過去 revision の内容に戻します。レシピファイルの更新だけを行い、その recipe が表す runtime restart、calibration、component verification などの操作は実行しません。実行したい場合は、復元後に `strata ops plan` で確認してから `strata ops run` を使います。

## 使い方

```sh
# 先に履歴を表示し、目的の revision を指定して復元
strata ops history restart --profile four-gpu
strata ops rollback restart --profile four-gpu --to 0123456789abcdef

# 機械処理向け JSON 出力
strata ops rollback restart --profile four-gpu --to 0123456789abcdef --output json
```

`restart` はレシピ名、`four-gpu` は既存の保存済み profile 名です。`--to` に渡す値は例示値ではなく、`strata ops history` が表示した実在する履歴 revision に置き換えてください。

## 実行時の動作

- `strata ops rollback` は `--profile` とレシピ名を必須とし、`--to REVISION` も必須です。`--output` は `human`（既定）または `json` を受け付けます。`--json` は `--output json` の alias です。各 one-shot `ops` parser には共通で `--quiet` も追加されます（`strata_cli/cli.py:255-278,508-515`）。
- Revision は小文字 16 桁の16進数です。`strata ops history NAME --profile PROFILE` で現在 revision と保存済み履歴を確認できます。履歴は、レシピの変更保存時に変更前のファイルを保存したものです（`strata_control/recipes.py:214-250,253-275`）。
- rollback は現在のレシピを読み、指定 revision の履歴 JSON を読み込んで revision hash とレシピ schema を検証し、その内容を保存します。保存時には現在版を履歴に残し、レシピを atomic に更新します。保存処理は profile ごとの lock 下で revision を再確認するため、読み込み後に別プロセスが変更した場合は上書きせず競合エラーになります（`strata_control/recipes.py:214-237,253-275`）。
- 成功時、human 出力は `Restored recipe NAME: OLD_REVISION -> NEW_REVISION`、JSON 出力は `schema_version`、`ok`、`recipe`、`previous_revision`、`revision` を含みます。JSON 出力は `--output json` または `--json` で選べます（`strata_cli/cli.py:1391-1394,1436-1439,527-542,2232-2237`）。

## 副作用と注意点

- 変更対象は profile に紐づく recipe ファイルと、その recipe の履歴ディレクトリです。POSIX では recipe 関連ディレクトリを owner-only（0700）、ファイルを owner-only（0600）に保つ検査があり、不適切な権限や symlink などは拒否されます（`strata_control/recipes.py:38-86,180-196,253-275`）。
- profile 自体、run config、operation journal はこの rollback の保存先ではありません。network、engine、GPU の処理や、recipe action の実行もこの分岐からは行われません（`strata_cli/cli.py:1436-1439`）。
- 同じ内容への rollback は保存層で no-op になり、現行 revision のまま成功します（`strata_control/recipes.py:214-221`）。
- revision が不正なら終了コード 2、履歴が見つからない・内容が破損している・権限等の検証に失敗した場合はコード 5、保存中の変更競合はコード 6 で失敗します。通常出力ではエラーを stderr に `strata: ...` と表示し、JSON 指定時は `ok: false` と `error.code` / `error.message` を出力します（`strata_control/recipes.py:253-273,214-225`; `strata_control/profiles.py:30-35`; `strata_cli/cli.py:527-532,2166-2183`）。

## 関連文書

- [CLI 索引](../../../README.md) — `strata ops rollback` の階層とオプション一覧。
- [Terminal CLI ガイド](../../../../../../Niko1221/Strata/docs/TERMINAL.md) — operation recipe の利用例。リンク先は調査対象 Strata checkout 上の資料です。

## 根拠

- `strata_cli/cli.py:255-278,508-515` — `ops rollback` の登録、位置引数、必須オプション、共通出力オプション。
- `strata_cli/cli.py:1391-1394,1436-1439,2160-2163` — rollback の dispatch と成功出力。
- `strata_control/recipes.py:214-237,240-275` — revision 履歴の作成、rollback の検証・保存、競合防止。
- `strata_control/recipes.py:38-86,180-196` — recipe / 履歴の保存場所、権限・ファイル検証。
- `strata_control/profiles.py:30-35`; `strata_cli/cli.py:527-542,2166-2183` — エラーコードと human / JSON の出力経路。
- `docs/TERMINAL.md:96-122` — 利用者向け recipe 操作例と、plan / run の役割。
