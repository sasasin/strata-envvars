# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops list` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると JSON 出力を選ぶ |

## 役割

保存済み operator recipe の一覧を、機械処理しやすい JSON で出力します。`--output json` の別表記です。recipe の選択や検証内容は変えず、出力形式を切り替えます。

## 使い方

```sh
strata ops list --profile PROFILE_NAME --json
```

同じ出力形式は `strata ops list --profile PROFILE_NAME --output json` でも指定できます。

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、値を取りません。省略時は偽で、`--output` の既定値 `human` が使われます。指定時は `output` が `json` に設定されます。フラグを重複指定しても真のままです。フラグの後ろに値を置く形式は定義されていません。

`strata ops list` の parser は `--profile` を必須とし、`--output` は `human` / `json` の選択式です。`--json` は ops の全 action parser を作った後で one-shot parser 群へ共通追加されます（`strata_cli/cli.py:255-267, 508-515`）。

## 実行時の動作

引数処理後、`main()` は `--json` が真なら `a.output = "json"` にします。そのため同時に `--output human` を明示していても JSON が選ばれます。`--output json` と併用した場合も同じ JSON 出力です（`strata_cli/cli.py:2223-2236`）。

`strata ops list` は `recipes.list_recipes(a.profile)` の結果を `{"profile": ..., "recipes": [...]}` として成功 payload に渡します。JSON モードでは共通成功 envelope として `schema_version: 1`、`ok: true` が付加され、UTF-8 文字をそのまま出力します。recipe がない場合は `recipes: []` です。人間向け表示の「No recipes; use ...」は JSON モードでは出力されません（`strata_cli/cli.py:1391-1403, 535-542`）。

一覧は profile の `.ops/<profile>/*.json` をファイル名順に読みます。有効な recipe は `id`、`kind`、`revision` を返し、個別 recipe の読み込み・検証に失敗したものは一覧全体を失敗させず、`id` と `error` を含む要素として返します（`strata_control/recipes.py:38-64, 199-211`）。

## 適用条件と副作用

`--profile` は必須です。profile 名は小文字英字で始まり、小文字英字・数字・`_`・`-` を使う 1〜64 文字で、保存済み profile の読み込みが必要です。profile 置き場は `STRATA_PROFILE_DIR` があればその値、Windows では `APPDATA` 配下（なければユーザーの `AppData/Roaming`）、その他の OS では `XDG_CONFIG_HOME`（なければ `~/.config`）配下の `strata/profiles` です（`strata_control/profiles.py:25, 38-55, 150-166`）。

`--json` 自体は出力形式を選ぶだけで、recipe の作成・変更・実行はしません。list 経路では profile と recipe ファイルを読みます。profile loader は権限昇格実行でロックされた profile を読む場合に一度修復する処理を呼びます（`strata_control/profiles.py:150-166`）。recipe ディレクトリが存在しなければ一覧は空になりますが、profile のロード自体は先に行われるため、未保存・不正な profile は失敗します（`strata_control/recipes.py:38-59, 199-202`）。

## 出力とエラー

成功時は標準出力へ JSON 1 オブジェクトを出し、終了コード `0` です。profile の読み込み失敗など `ValueError` 系の失敗は、JSON モードなら標準出力へ `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式で出力され、profile の `ProfileError` は既定で終了コード `2`、保存・読み込み上の一部エラーはコード `5` を返します（`strata_control/profiles.py:30-35, 150-166`; `strata_cli/cli.py:527-532, 2166-2173`）。個別 recipe の `ProfileError` は上述の通り `recipes` 配列内の `error` として報告され、コマンド成功扱いになります（`strata_control/recipes.py:199-211`）。

未知の引数や不正な `--output` 値など parser 段階のエラーは `main()` の実行処理より前に `argparse` が拒否し、usage とエラーを標準エラーに表示して終了コード `2` とします。`--json` に値を付ける構文はありません（`strata_cli/cli.py:266-267, 513, 2223-2231`）。

## 根拠

- parser のコマンド階層・`--output` 定義: `strata_cli/cli.py:255-267`
- one-shot parser への `--json` 追加: `strata_cli/cli.py:508-515`
- JSON への切り替えと標準出力 envelope: `strata_cli/cli.py:527-542, 2223-2236`
- ops list の payload と人間向け空一覧表示: `strata_cli/cli.py:1391-1403`
- profile / recipe directory の読み込み、recipe ごとのエラー項目: `strata_control/recipes.py:38-64, 180-211`
- profile 名・保存場所・profile 読み込みと loader の修復呼び出し: `strata_control/profiles.py:25, 38-55, 150-166`

