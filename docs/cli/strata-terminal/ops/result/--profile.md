# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops result` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済みプロファイル名。小文字英字で始まり、小文字英字・数字・`_`・`-` を使う1〜64文字 |

## 役割

結果を取得する operation ID と組み合わせ、どの保存済みプロファイルに属する operation journal を検索するか指定します。parser で必須の値として定義され、既定値はありません（`strata_cli/cli.py:262-267`）。

## 使い方

```sh
strata ops result 0123456789abcdef0123456789abcdef --profile work
```

`operation_id` は32桁の小文字16進数です。これは位置引数で、journal のファイル名として使われます（`strata_cli/cli.py:262-267`、`strata_control/journal.py:60-63`）。

## 値と既定値

- `--profile` は省略できません。値は保存済みプロファイルの ID として検証されます。形式は `^[a-z][a-z0-9_-]{0,63}$` です（`strata_cli/cli.py:266-267`、`strata_control/profiles.py:25,48-55`）。
- 指定したプロファイルの JSON が存在しない場合は失敗します。`--profile` 自体に既定値や空値の特別な解釈はありません（`strata_control/profiles.py:150-166`）。
- 保存プロファイルの場所は `STRATA_PROFILE_DIR` が設定されていればそのディレクトリ、未設定時は OS ごとの既定ディレクトリです。POSIX では `XDG_CONFIG_HOME` または `~/.config/strata/profiles`、Windows では `%APPDATA%/Strata/profiles`（APPDATA がなければユーザープロファイル配下）です（`strata_control/profiles.py:38-45`）。

## 実行時の動作

`strata ops result` は `--profile` と `operation_id` を `journal.load(profile, operation_id)` に渡し、読み込んだ record を `record` フィールドにして出力します（`strata_cli/cli.py:1409-1411`）。journal は `<profile_dir>/.ops/<profile>/.runs/<operation_id>.json` を参照します。profile の運用ディレクトリは `recipes._directory()` が保存済み profile を読み込んでから決定し、journal 側はその下の `.runs` を使います（`strata_control/recipes.py:38-42`、`strata_control/journal.py:47-63`）。別 profile に同じ operation ID の記録があっても、指定した profile の配下だけが検索対象です。

`--output` は同じ parser scope の別オプションです。省略時の `human` でもこの結果表示は整形 JSON（`{"record": ...}`）で、`--output json` では `schema_version: 1` と `ok: true` を含む機械向け envelope（`{"schema_version":1,"ok":true,"record":...}`）になります（`strata_cli/cli.py:266-267,535-542,1410-1411`）。

operation の状態が `running` の場合、record はそのまま返され、さらに `completion_unverified: true` が付加されます。これは完了状態を確認できていない印であり、journal 実装の説明では caller の停止後に remote work が継続している可能性を示すもので、worker が現在も動いている証明ではありません（`strata_control/journal.py:1-5,247-251`）。

## 適用条件と副作用

- 対象の保存 profile が存在し、profile JSON が有効である必要があります。profile を読み込む際、権限状態によっては `private_files.read_bytes_repairing()` が profile ファイルを一度その場で修復します。したがって結果の照会自体は journal を書き換えませんが、profile 読み込みにはこの権限修復の副作用があり得ます（`strata_control/recipes.py:38-40`、`strata_control/profiles.py:150-166`）。
- `--profile` が違うと別の `.runs` ディレクトリを検索します。実行時の設定や operation の再実行・変更を指示するオプションではありません（`strata_cli/cli.py:1409-1411`、`strata_control/journal.py:47-63,247-251`）。
- journal ディレクトリがシンボリックリンクまたは通常ディレクトリでない場合、また POSIX で owner-only の権限条件を満たさない場合は拒否されます（`strata_control/journal.py:47-57`）。

## 出力とエラー

- operation ID が32桁の小文字16進数でない場合は `ProfileError` になります（`strata_control/journal.py:60-63`）。
- 指定 ID の記録がない場合は「operation record was not found」、記録が64 KiBを超える・通常ファイルでない・JSONや schema/intent/events が不正な場合は読み込みエラーになります（`strata_control/journal.py:185-244`）。profile 未保存・不正も失敗します（`strata_control/profiles.py:48-55,150-166`）。
- これらの `ProfileError` は `ValueError` 経路で処理され、通常出力では `strata: <message>` を stderr に出します。終了コードはエラーに設定された値を使い、未指定なら2、profile 未保存や不正な record など明示的に5とされたケースでは5です（`strata_cli/cli.py:527-532,2166-2173`、`strata_control/profiles.py:30-35,160-165`、`strata_control/journal.py:185-217`）。`--output json` の場合は `ok: false` と `error.code` / `error.message` を含む JSON error を stdout に出します（`strata_cli/cli.py:527-532,2172-2173`）。

## 根拠

- parser 定義と必須性: `strata_cli/cli.py:260-267`
- profile の形式、探索先、読み込み: `strata_control/profiles.py:25,38-55,150-166`
- operation journal の格納場所と ID 検証: `strata_control/recipes.py:38-42`、`strata_control/journal.py:47-63`
- result の取得と出力: `strata_cli/cli.py:535-542,1391-1411`
- journal の record 検証、実行中 record の補足: `strata_control/journal.py:185-251`
- エラー表示と終了コードの伝播: `strata_cli/cli.py:527-532,2166-2173`

調査は上記 commit の checkout 内の parser と実処理を対象としました。CLI の `--help` は実行せず、別 revision の help や Release 配布物は根拠に含めていません。
