# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops show` |
| オプション | `--output` |
| 別名 | `--json`（共通 one-shot parser が追加する alias） |
| 値 | `human` または `json` |

## 役割

表示形式を選びます。`--output` は出力ファイルを指定するオプションではありません。対象の recipe は位置引数 `<name>` で指定し、必須の `--profile <profile>` で保存先 profile を選びます。

## 使い方

```sh
strata ops show restart --profile work --output json
```

`strata ops show restart --profile work` のように `--output` を省略すると既定の `human` になります。

## 値と既定値

- 受理する値は `human` と `json` のみで、既定値は `human` です。ほかの値は `argparse` が拒否し、usage とエラーを stderr に出して終了コード 2 で終了します。
- `--json` は同じ one-shot コマンド群に追加されるフラグで、指定すると `--output json` と同じ設定になります。両方を指定しても `--json` が有効なら JSON 出力です。
- 同じ `--output` を複数回指定した場合の parser 動作は `argparse` の通常の単一値引数で、最後に指定した値が残ります。

## 実行時の動作

`human` の場合も recipe と revision は整形済み JSON として stdout に出ます。`json` の場合は1行の JSON envelope（`schema_version: 1`、`ok: true`、`recipe`、`revision`）になります。いずれも `recipes.load(profile, name)` が保存 recipe を読み込み、値と revision を返します。このコマンド分岐自体は recipe を保存・編集しません。

`--quiet` を併用すると、JSON モードは通常どおり stdout に出ます。`human` モードの stdout は quiet 処理で捕捉され、成功時は表示されません。

## 適用条件と副作用

- `--profile` は必須です。profile 名と recipe 名は小文字英字で始まり、小文字英字・数字・`_`・`-` のみを使えます。指定 profile と recipe が読み込み可能である必要があります。
- 保存 recipe の読み込みでは、recipe ファイルが通常ファイルで 64 KiB 以下であること、POSIX ではファイル権限が owner-only（`0600`）であること、および schema・kind・parameters の整合性を検査します。欠落、破損、不正な権限などは失敗します。
- recipe の読み込みは書き換えません。ただし recipe directory の準備時に profile 自体も読み込まれます。Windows で profile の読み込みが `PermissionError` となり、そのファイルがユーザー所有領域内にある場合、共通読み込み処理がアクセス権を修復して再試行する経路があります。

## 出力とエラー

- 正常時の終了コードは 0 です。前述のとおり `human` は整形 JSON、`json` は成功 envelope を stdout に出します。
- recipe が存在しない場合は `strata ops init --profile <profile>` を案内するエラーとなり、`ProfileError` の終了コード 5 が使われます。`--output json` または `--json` なら `{schema_version, ok: false, error: {code, message}}` 形式、human モードなら `strata: ...` を stderr に出します。
- `--output` の値が choices 外の場合はコマンド本体に入る前に parser が拒否するため、`--output json` による JSON error envelope にはなりません。

## 根拠

- `strata_cli/cli.py:255-267` — `ops show` を含む parser 群と、`--profile` 必須・`--output` choices/default の定義。
- `strata_cli/cli.py:508-515,2217-2236` — 共通 `--json` alias の追加と `main` による JSON 指定の正規化、quiet の分岐。
- `strata_cli/cli.py:535-542,1416-1418` — 成功時の JSON/human 出力、および show が recipe/revision を読み出す処理。
- `strata_cli/cli.py:2166-2188,527-532` — `ValueError` / `OSError` / `ClientError` の捕捉、JSON error envelope または stderr 表示、終了コード。
- `strata_control/recipes.py:32-35,38-64,93-114,180-196` — 名前形式、profile 読み込みを伴う recipe directory、recipe ファイルと内容の検査、欠落時の終了コード 5。
- `strata_control/profiles.py:25,30-35,150-166` — profile 名形式と profile 読み込み。
- `strata_control/private_files.py:476-484` — Windows でアクセス拒否時にユーザー所有領域のアクセス権を修復して再試行する読み込み経路。

調査は上記 checkout のソースに基づきます。同一 revision の CLI help や Release 配布物は実行・照合していません。
