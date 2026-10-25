# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops show` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前。省略不可。 |

## 役割

表示する operator recipe が属する serving profile を選びます。recipe は profile ごとの `.ops` ディレクトリから検索されます。recipe 名は別の位置引数です。

## 使い方

```sh
strata ops show nightly-check --profile local
```

JSON 出力を明示する場合:

```sh
strata ops show nightly-check --profile local --output json
```

## 値と既定値

`--profile` は `required=True` で、値は argparse の文字列です。profile 名は小文字 `a-z` で始まり、小文字英字・数字・`_`・`-` を使う最大64文字の ID でなければなりません。profile ID と recipe 名の両方が同じ規則で検査されます。既定値はありません。値の省略は parser の usage error（終了コード2）になり、空文字や規則外の値は profile/recipe validation error になります。短縮別名はありません。

## 実行時の動作

コマンドは `recipes.load(profile, name)` を呼び、ロード・検証した recipe と、そのファイル内容から計算した revision を結果に含めます。ファイル位置は `<profile_dir>/.ops/<profile>/<name>.json` です。`profile_dir` は `STRATA_PROFILE_DIR` があればその値（`~` 展開後）、なければプラットフォームごとの Strata profiles 設定ディレクトリです。対象の serving profile が保存済みで有効であることも必要です。

recipe ファイルは通常ファイルで64 KiB以下、POSIX では所有者だけがアクセスできる mode `0600` である必要があります。内容は UTF-8 JSON として読み、schema version、profile ID、recipe ID、kind と kind ごとの params を検証します。revision はファイルの生バイト列の SHA-256 の先頭16桁です。

既定の `--output human` では `_success` の human 文言が指定されていないため、recipe と revision を整形 JSON で stdout に出します。`--output json`（または alias の `--json`）は `schema_version`、`ok`、`recipe`、`revision` を含む1行 JSON を出します。`--quiet` も parser で受理されます。人間向け出力を抑制するため、成功時は stdout が抑止されます。`--quiet` と JSON 出力を併用した場合は JSON が優先されます。

## 適用条件と副作用

`--profile` は recipe の探索先と recipe 内の profile ID 検証に使われます。別 profile への fallback はありません。show 処理は recipe を書き換えず、サブプロセスやネットワークも起動しません。

ただし recipe ディレクトリを決める前に保存済み serving profile をロードします。その profile のファイルでアクセス拒否が起きると、共通の `read_bytes_repairing` がアクセス権を一度修復して再読込する場合があります。recipe 自身の mode 不備や不正 JSON は修復せずエラーになります。

## 出力とエラー

- `--profile` を指定しない場合、argparse が usage error を出し終了コード2を返します。
- profile が未保存、recipe が存在しない、またはファイル属性・アクセス権・読込に問題がある場合は失敗します。recipe 不在時のメッセージは `strata ops init --profile <profile>` を案内し、終了コード5です。profile/recipe JSON のスキーマ・ID・params 検証エラーは `ProfileError` の既定終了コード2です。
- `_run` は `ValueError` を捕捉し、既定の human 出力では `strata: <message>` を stderr に、`--output json` または `--json` ではエラー envelope を stdout に出します。通常の profile 名・recipe 内容の検証エラーは終了コード2、未保存 profile や recipe の欠落、アクセス拒否など読込エラーはソースで明示された経路では終了コード5です。

## 根拠

- `strata_cli/cli.py:255-267` — `ops show` の登録、recipe 名位置引数、必須 `--profile` と `--output`。
- `strata_cli/cli.py:508-515` — ops parser 群への `--json` と `--quiet` の追加。
- `strata_cli/cli.py:1391-1418` — ops dispatch、show のロードと成功 payload。
- `strata_cli/cli.py:527-542` — human/JSON 成功・エラー出力形式。
- `strata_cli/cli.py:2119-2173` — JSON alias の変換と `ValueError` エラー処理。
- `strata_control/recipes.py:32-64` — profile/name ID 検査、profile 解決、recipe パス。
- `strata_control/recipes.py:89-114` — recipe 構造・kind/params の検証。
- `strata_control/recipes.py:180-196` — recipe 読込、サイズ・権限・JSON・revision の処理。
- `strata_control/profiles.py:25-50,150-166` — profile ID 規則、設定ディレクトリ、保存済み profile の読込と検証。
- `strata_control/private_files.py:476-484` — profile のアクセス拒否時に一度修復して再読込する処理。

確認範囲はこの checkout の Terminal CLI parser と上記の ops/profile 読込経路です。別 platform での実行結果や、個々の ACL・ファイルシステムが実際に修復可能かどうかは実行確認していません。
