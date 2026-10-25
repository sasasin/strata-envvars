# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops list` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力の alias） |
| 値 | `human` または `json` |

## 役割

指定した保存済みプロファイルの operator recipe 一覧を、人間向けテキストまたは機械処理向け JSON で標準出力へ出します。一覧を調べるコマンドであり、`--output` は出力形式を選択します。

## 使い方

```sh
strata ops list --profile four-gpu --output json
```

`--profile` は必須です。`--output` を省略したときは `human` です。

## 値と既定値

- `human` と `json` のみ受理します。parser の選択肢以外の値は argparse が拒否します。
- 既定値は `human` です。値は一つ取り、同じオプションを複数回指定した場合は argparse により最後に指定した値が残ります。
- `--json` は共通 one-shot parser が登録する alias で、指定すると `--output json` と同じ形式になります。`--output human --json` のように併用しても、`--json` の後処理で出力形式が `json` に設定されます。
- `jsonl` はこの parser の選択肢にありません。

## 実行時の動作

- `human` は recipe ごとに `id` と `kind` を `id  kind` の形式で一行表示します。読み込みに失敗した recipe は `kind` の代わりにエラー文字列を表示します。一覧が空なら `No recipes; use strata ops init --profile NAME` と案内します。
- `json` は `schema_version: 1`、`ok: true`、指定 profile 名、`recipes` 配列を含む JSON object を一行で stdout に出します。各有効 recipe の項目は `id`、`kind`、`revision`、個別に読み込めない recipe の項目は `id`、`error` を含みます。
- recipe は profile の `.ops/<profile>/` ディレクトリにある、ID 形式に合致した `*.json` ファイルから列挙され、ID 順に処理されます。recipe のファイル読込・検証は `recipes.list_recipes()` が行います。
- `--output` は stdout の形式だけを切り替え、一覧の対象や recipe の検証規則を変えません。出力先ファイルを指定するオプションではありません。

## 適用条件と副作用

- `--profile` の指定は必須です。保存済み profile が見つからない、または無効な場合は一覧処理前に失敗します。
- 一覧自体は recipe の作成・編集・削除を行いません。profile の読み込み時にファイルアクセス権エラーが起きた場合、共通 helper がアクセス修復を試みて一度再読込する実装です。この修復は `--output` の値に依存せず、修復できない場合は失敗します。
- `.ops` ディレクトリと profile 用 recipe ディレクトリについて、存在する場合はシンボリックリンクでないディレクトリであることを検査します。POSIX では owner-only の権限も検査します。
- `--quiet` はこの one-shot parser に登録されています。`human` 出力時は標準出力を捕捉し、終了コードが成功なら抑制します。JSON 出力では quiet capture を通らないため JSON は表示されます。

## 出力とエラー

- 一覧取得が成功した場合は終了コード `0` です。recipe 単位の読み込み・検証失敗は一覧の `error` 項目として返されるため、それだけではコマンド全体の失敗になりません。
- profile の欠落・不正など処理全体の `ValueError` は、その `exit_code`（指定がなければ `2`）で終了します。`OSError` は共通処理で終了コード `6` に変換されます。JSON 時は `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON を stdout に出し、human 時は `strata: ...` を stderr に出します。
- `--profile` の欠落や `--output` の不正値は parser 段階で拒否され、通常の usage/error 経路となります。これらは `--output json` を指定しても JSON error object になるとは限りません。

## 根拠

- `strata_cli/cli.py:255-267` — `ops` のサブコマンド parser、`list`、必須 `--profile`、`--output` の choices と既定値。
- `strata_cli/cli.py:508-515` — ops の各 one-shot parser への `--json` / `--quiet` 登録。
- `strata_cli/cli.py:1391-1403` — `ops list` の dispatch、一覧取得、human/JSON 成功 payload。
- `strata_cli/cli.py:527-542` — 共通の JSON error object と成功出力。
- `strata_cli/cli.py:2160-2163,2166-2188,2217-2247` — `_ops` への dispatch、例外の終了コード・出力形式、parser 実行、`--json` alias および `--quiet` の処理。
- `strata_control/recipes.py:38-64,180-211` — profile・recipe directory の検査、recipe 一覧の列挙、個別読込失敗の項目化。
- `strata_control/profiles.py:38-55,150-166` — profile directory、profile 読込と欠落・不正時の例外。
- `strata_control/private_files.py:476-484` — profile 読込で権限エラー時にアクセス修復後、一度再読込する共通 helper。

調査範囲は上記 commit の checkout 内ソースです。同 revision の CLI `--help` と Release 配布物は照合していません。別 OS でのファイル権限修復挙動は実行確認していません。
