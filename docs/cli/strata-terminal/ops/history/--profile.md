# `strata ops history --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops history` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前。小文字英字で始まり、小文字英字・数字・`_`・`-` を使う 1〜64 文字の識別子 |

## 役割

履歴を表示する recipe の所属先 profile を指定する。recipe 名は別の位置引数で指定する。`--profile` は `strata ops` の `init`、`list`、`history` など各アクションに共通して必須であり、history ではその profile を使って現行 recipe と保存 revision の一覧を取得する（`terminal/strata_cli/cli.py:283-295,1501-1505`）。

## 使い方

```sh
strata ops history restart --profile four-gpu
```

`restart` は recipe 名、`four-gpu` は保存済み serving profile 名の例。JSON 出力にする場合は `--output json`（または `--json`）を追加できる（`terminal/strata_cli/cli.py:294-295,539-546`）。

## 値と既定値

- 値を必ず 1 つ指定する。parser では `required=True` で、既定値はない（`terminal/strata_cli/cli.py:283-295`）。
- profile 識別子は小文字英字で始まり、以降は小文字英字・数字・`_`・`-` のみ、最大 64 文字。profile 名の検証は `profiles.load()` から `_name()` を通じて行われる（`terminal/strata_control/recipes.py:38-41`、`terminal/strata_control/profiles.py:48-55`）。
- 指定した名前の保存済み profile が必要。ファイルパスを profile 名として扱う分岐は確認できず、recipe の profile/name として同じ識別子が検証される（`terminal/strata_control/recipes.py:32-40,62-64`）。

## 実行時の動作

`strata ops history` の処理は `recipes.history(a.profile, a.name)` に引数を渡す。profile データは `STRATA_PROFILE_DIR` が設定されていればその場所から、未設定なら OS ごとの既定設定ディレクトリから読む（`terminal/strata_cli/cli.py:1501-1503`、`terminal/strata_control/profiles.py:38-45`）。

history API は先に指定 profile の recipe を読み込み、現在の revision を得る。次に `.ops/<profile>/.history/<recipe>` にある通常ファイルのうち、ファイル名 stem が 16 桁の小文字 16 進数であるものを履歴候補として列挙する。結果は現行 revision を先頭に置き、過去 revision は保存時刻（mtime）の降順にする。履歴ディレクトリが存在しない場合は現行 revision のみを返す（`terminal/strata_control/recipes.py:240-250`）。このオプション自体は表示対象を絞るだけで、履歴の作成・更新・削除は行わない。

人間向け出力は revision ごとに `current` または `saved` を表示する。`--output json` / `--json` では `profile`、`recipe`、`history` を含む成功 JSON を出力する。`--quiet` を指定した場合も JSON 出力は抑制されない（`terminal/strata_cli/cli.py:1501-1505,539-546,566-573,2335-2340`）。

## 適用条件と副作用

profile と recipe の読み取りが必要であり、profile の保存場所は `STRATA_PROFILE_DIR` または OS ごとの既定値で決まる。recipe がない場合や profile の内容・権限・ファイル種別が不正な場合は履歴を列挙できず失敗する。history 保存先が存在する場合、シンボリックリンクや不正なディレクトリ・所有者権限も拒否される（`terminal/strata_control/recipes.py:32-64,180-196,71-86,240-250`）。

## 出力とエラー

- recipe が見つからない場合、`strata ops init --profile <profile>` を案内する `ProfileError` となる。壊れた recipe やアクセス不能などのエラーは CLI の共通処理でエラーとして返される（`terminal/strata_control/recipes.py:180-196`、`terminal/strata_cli/cli.py:2248-2265`）。
- 人間向けエラーは `strata: <message>` を stderr に出力し、例外に設定された終了コードを返す。機械向け出力では `schema_version`、`ok: false`、エラーコードとメッセージを含む JSON を stdout に出力する（`terminal/strata_cli/cli.py:558-563,2248-2265`）。
- 有効な recipe がある場合の成功終了コードは 0。人間向けの空履歴ディレクトリでも現在 revision が返るため、history の成功結果が空配列になる経路はありません（`terminal/strata_cli/cli.py:1501-1505`、`terminal/strata_control/recipes.py:240-250`）。

## 根拠

- parser と必須指定、値の共有 scope: `terminal/strata_cli/cli.py:283-295`
- profile / recipe のディスパッチと出力: `terminal/strata_cli/cli.py:1461-1464,1501-1505`
- `--json`、`--quiet` の追加と成功・エラー形式: `terminal/strata_cli/cli.py:539-546,558-573,2335-2340`
- profile 識別子、保存場所、recipe の profile 解決: `terminal/strata_control/profiles.py:25,38-55`、`terminal/strata_control/recipes.py:32-41,62-64`
- recipe 読み込み時の失敗、履歴ファイルの列挙と順序: `terminal/strata_control/recipes.py:71-86,180-196,240-250`
