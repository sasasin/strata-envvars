# `--to`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--to` |
| 別名 | なし |
| 値 | 必須。recipe 履歴の revision を表す小文字16進数16文字 |

## 役割

指定した profile 内の operation recipe を、保存済みの過去 revision の内容へ戻します。profile は `--profile`、対象 recipe 名は位置引数で指定します。recipe は `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれかの型付き設定で、任意のコマンド文字列ではありません（`strata_cli/cli.py:258-277`、`strata_control/recipes.py:28-29,93-114`）。

## 使い方

まず `strata ops history RECIPE --profile PROFILE` で表示される履歴から、`current` ではない revision を選びます。例:

```sh
strata ops rollback restart --profile work --to 0123456789abcdef
```

ここで `restart` は recipe 名、`work` は保存 profile 名です。revision は例示値なので、実際には対象 recipe の履歴に表示された値を指定してください。`--profile` と `--to` は必須です（`strata_cli/cli.py:258-277`）。

## 値と既定値

値の省略はできず、既定値はありません。parser は値を `REVISION` として受け取りますが、型変換や parser 側の choices は設定していません。rollback 実装が `^[0-9a-f]{16}$` に完全一致することを検証するため、略した revision、大文字、非16進文字は拒否されます（`strata_cli/cli.py:276-277`、`strata_control/recipes.py:253-255`）。

revision は保存された recipe JSON の UTF-8 bytes に対する SHA-256 の先頭16桁です。履歴は recipe の変更時に旧ファイルを `.ops/<profile>/.history/<recipe>/<revision>.json` へ保存して作られます（`strata_control/profiles.py:62-63`、`strata_control/recipes.py:214-237,240-250`）。従って、現在の recipe revision は `history` に `current` として表示されても、`--to` が読む過去履歴ファイルとは別です。

## 実行時の動作

CLI は `strata ops rollback` の parser で必須の `--to` を受理し、`recipes.rollback(profile, recipe_name, revision)` に渡します。その関数は recipe 名と profile 名を検証し、現行 recipe の revision を読み取った後、指定 revision と同名の履歴ファイルを開きます。履歴が通常ファイルであること、POSIX では owner-only の権限であること、ファイルサイズ上限 64 KiB、内容のハッシュ一致、recipe の schema・profile ID・recipe ID・kind・params の妥当性を確認します（`strata_control/recipes.py:32-64,180-196,253-275`）。

検証に成功すると、その内容を `recipes.save` に渡します。save は profile 単位の lock を取り、rollback 開始時に読んだ現行 revision と現在値が一致するかを再確認します。競合があれば更新を拒否します。内容が異なる場合は現行 recipe を履歴へ退避し、復元内容を atomically 保存します。同じ内容への rollback は保存を省略し、revision は変わりません（`strata_control/recipes.py:214-237`）。

この処理が変更するのは保存 recipe とその履歴です。rollback 分岐は `recipes.rollback` の結果を出力して終了し、`recipes.run` や対象 kind の operation 実行関数を呼びません（`strata_cli/cli.py:1431-1439`）。

## 適用条件と副作用

- 指定 profile と recipe が保存済みで、同じ profile・recipe の履歴に対象 revision が存在する必要があります。
- 履歴 revision の JSON は現在の schema で検証されます。破損・別 recipe/profile の履歴や、リンク・不正な権限などの不正なファイルは復元対象になりません。
- 成功時は recipe ファイルを書き換え、元の現行内容を履歴へ保全します。実行中サーバーへの操作、recipe operation の実行、ネットワークアクセスをこの rollback 分岐が行うことは確認できません。
- `--output` は `human` または `json`（既定 `human`）、`--json` は `--output json` の alias です。これらは `--to` の値規則を変えず、結果の形式を選びます（`strata_cli/cli.py:267,512-515,1391-1394`）。

## 出力とエラー

成功時は通常出力で `Restored recipe <name>: <旧revision> -> <復元revision>` を表示します。JSON 出力は `ok: true`、`recipe`、`previous_revision`、`revision` を含みます（`strata_cli/cli.py:1436-1439,535-542`）。

形式不正の revision は `ProfileError`（`ValueError`）となり、CLI は人間向けなら stderr に `strata: ...`、JSON モードならエラー JSON を出力して終了コード 2 を返します。履歴が見つからない、revision hash が内容と不一致、履歴 JSON が読めない等は実装で `ProfileError` code 5 にされます。revision の競合など保存中の変更検出は code 6 です。いずれも JSON モードでは `ok: false` と `error.code`、`error.message` が出力されます（`strata_control/recipes.py:218-225,253-273`、`strata_control/profiles.py:30-35`、`strata_cli/cli.py:527-533,2166-2183`）。

## 根拠

- parser と共通 `--json` / `--quiet` 登録: `strata_cli/cli.py:258-277,508-515`
- CLI の rollback dispatch と成功表示: `strata_cli/cli.py:1391-1394,1431-1439`
- revision 検証、履歴の読込・復元、失敗条件: `strata_control/recipes.py:180-196,253-275`
- 保存時の lock・競合確認・履歴退避・atomic 書込: `strata_control/recipes.py:214-237`
- revision の生成方法: `strata_control/profiles.py:62-63`
- CLI 共通のエラー出力と終了コード処理: `strata_cli/cli.py:527-542,2166-2183`
