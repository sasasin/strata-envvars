# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops edit` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は false |

## 役割

編集した recipe の成功結果や処理エラーを JSON で出力します。`ops edit` の編集処理自体は変わらず、対象 recipe をエディターで開いて保存します。

## 使い方

```sh
strata ops edit restart --profile local --json
```

`restart` は recipe 名の例です。対象 profile に同名 recipe があり、`VISUAL` または `EDITOR` でエディターを設定している必要があります。

## 値と既定値

- 引数値を付けないフラグです。parser は `store_true` で登録され、未指定時は false です（`strata_cli/cli.py:508-515`）。
- このフラグは `strata ops edit` を含む one-shot parser 群に共通追加されています。`ops edit` の parser は recipe 名と必須の `--profile`、`--output {human,json}`（既定値 `human`）を定義しています（`strata_cli/cli.py:255-267,508-515`）。
- `--json` と `--output` を両方指定した場合も、`--json` が有効なら `main()` が出力形式を `json` に設定します。したがって `--json --output human` も JSON 出力になります（`strata_cli/cli.py:2232-2235`）。
- 複数回の `--json` は同じ真偽値を設定します。値を続けて指定する構文ではありません。

## 実行時の動作

`main()` は `--json` を `--output json` 相当に正規化し、`_run()` から ops handler に処理を渡します。handler は `a.output == "json"` を機械可読出力の選択条件に使います（`strata_cli/cli.py:1391-1394,2160-2161,2232-2237`）。

編集成功時は、`schema_version: 1`、`ok: true`、`recipe`、`previous_revision`、`revision` を含む JSON を標準出力へ1行で出します。`recipes.edit()` が現在の recipe を読み、エディターの編集内容を保存して前後の revision を返し、handler が結果を包みます（`strata_cli/cli.py:1419-1422,535-538`; `strata_control/recipes.py:299-323`）。変更がなければ保存処理は同じ revision を返すため、前後の revision は等しくなり得ます（`strata_control/recipes.py:214-221`）。

## 適用条件と副作用

- `--json` は表示形式だけを選び、エディターを起動する対話的な編集を省略しません。`recipes.edit()` は `VISUAL` を優先し、未設定なら `EDITOR` を使います。どちらも設定されていない、または分割後のコマンドが空なら失敗します（`strata_control/recipes.py:299-306`）。
- 編集用の一時 JSON ファイルを recipe ディレクトリに作成し、エディターへファイル名を渡します。編集が有効なら recipe を保存し、旧 revision の履歴も作ります。一時ファイルは成功時に削除されます（`strata_control/recipes.py:307-326,214-237`）。
- エディターが非ゼロで終了した場合や編集 JSON の読み込み・検証に失敗した場合、一時ドラフトは保持され、そのパスがエラーに含まれます。これは `--json` を指定しても変わりません（`strata_control/recipes.py:312-326`）。
- recipe の読込・保存では profile と recipe 名の形式、recipe JSON のスキーマおよび recipe 種別ごとのパラメーターが検証されます。recipe は通常ファイルであることと 64 KiB 未満であることも要求され、POSIX では所有者のみのアクセス権が確認されます（`strata_control/recipes.py:32-35,93-114,180-196`）。

## 出力と失敗経路

- 成功時は上記 JSON オブジェクトを標準出力に出し、終了コード 0 です（`strata_cli/cli.py:535-542,1419-1422`）。
- handler まで到達する `ValueError` 系エラーは、`--json` 有効時に `schema_version: 1`、`ok: false`、`error: {code, message}` の JSON を標準出力に出します。`ProfileError` は `ValueError` の派生で、既定終了コードは 2 です。エディターの非ゼロ終了や revision 競合などでは recipe 処理側が設定したコード（例: 6）が使われます（`strata_control/profiles.py:30-35`; `strata_control/recipes.py:312-322,214-225`; `strata_cli/cli.py:527-532,2166-2173`）。
- `OSError` は終了コード 6、割り込みは 130 としてエラー経路へ送られます。`--json` が設定した `output=json` により JSON 形式になります（`strata_cli/cli.py:2176-2193,2232-2235`）。
- `--json` 自体は値を取りません。必須の recipe 名とは別に余分な値を指定するなど、argparse が処理する構文エラーでは通常の usage/error 表示となり、JSON 応答にはなりません。余分な引数の拒否は JSON 形式への正規化より前に行われます（`strata_cli/cli.py:2223-2235`）。

## 根拠

- `strata_cli/cli.py:255-267,508-515` — `ops edit` の parser、`--output` の既定値、one-shot parser 群への `--json` 追加。
- `strata_cli/cli.py:527-542,1391-1422,2160-2193,2217-2248` — JSON 成功・失敗出力、ops edit の dispatch、例外処理、フラグの正規化。
- `strata_control/recipes.py:93-114,180-196,214-237,299-326` — recipe の検証・読込・保存、編集用一時ファイルとエディターの処理。
- `strata_control/profiles.py:30-35` — `ProfileError` の型と既定終了コード。
- 同一 revision の `python strata.py ops edit --help` も確認し、`--json` が `--output json` の alias と表示されることを parser 定義と照合しました。Release 配布物ごとの差は調査していません。
