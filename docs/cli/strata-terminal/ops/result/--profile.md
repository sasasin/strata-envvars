# `strata ops result --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops result` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済みプロファイル名（文字列）。必須。 |

## 役割

`--profile` は操作記録を探すプロファイルを選ぶ。`strata ops result` は、同じ呼び出しの位置引数 `operation_id` と組み合わせて、そのプロファイルの操作 journal から該当記録を読み、標準出力に返す。プロファイル名はパスではなく、保存済みプロファイルの ID である。

## 使い方

```sh
# local プロファイルに属する操作記録を表示
strata ops result 0123456789abcdef0123456789abcdef --profile local

# 同じ記録を機械処理向け JSON envelope で表示
strata ops result 0123456789abcdef0123456789abcdef --profile local --output json
```

## 値と既定値

- `--profile` は `ops` 配下の全アクションに共通して登録され、`required=True` のため省略できない。alias や default は設定されていない（`terminal/strata_cli/cli.py:283-295`）。
- 保存済みプロファイル名は小文字英字で始まり、小文字英字・数字・`_`・`-` を使う最大64文字の ID。大文字、パス、空文字は受理されない（`terminal/strata_control/profiles.py:48-55`）。プロファイル自体が存在しない場合も失敗する（`terminal/strata_control/profiles.py:153-173`）。
- このコマンドで参照する操作 ID は小文字16進数32文字でなければならない（`terminal/strata_control/journal.py:25-27,60-63`）。
- プロファイルの保存先は `STRATA_PROFILE_DIR` があればその値、なければ OS ごとの既定ディレクトリ。`--profile` の値を直接ファイルパスとしては使わない（`terminal/strata_control/profiles.py:38-55`）。

## 実行時の動作

1. parser は `ops result` に `operation_id` を位置引数として登録し、全 `ops` アクションに `--profile` を必須文字列として登録する（`terminal/strata_cli/cli.py:283-295`）。
2. dispatch は `a.profile` と `a.operation_id` を `journal.load` に渡し、戻った record を `_success` で出力する（`terminal/strata_cli/cli.py:1479-1481`）。journal の保存先は選択したプロファイル配下の `.ops/<profile>/.runs/<operation_id>.json`（`terminal/strata_control/recipes.py:38-42`、`terminal/strata_control/journal.py:47-63`）。
3. 記録が `running` 状態なら、結果に `completion_unverified: true` を付加する。これは呼び出し元の終了後も処理完了を確認できない状態を示す（`terminal/strata_control/journal.py:252-256`）。
4. 既定の human 出力でも record を整形 JSON として表示する。`--output json` の場合は `schema_version` と `ok` を含む envelope に `record` を格納する（`terminal/strata_cli/cli.py:566-573`、`1479-1481`）。

この値自体は検索先の選択に使われ、操作を実行・変更しない。ただしプロファイルを読む際、アクセス拒否時に `read_bytes_repairing` がアクセス修復を試みて再読込する実装がある（`terminal/strata_control/profiles.py:153-160`、`terminal/strata_control/private_files.py:479-487`）。OS ごとの修復内容はこの調査では追跡していない。

## 適用条件と副作用

- 指定したプロファイルが必要で、journal record の `profile` も指定 ID と一致する必要がある（`terminal/strata_control/profiles.py:153-173`、`terminal/strata_control/journal.py:204-210`）。別プロファイルの記録をこの指定で読むことはできない。
- 通常の成功経路はプロファイルと journal の読み込みおよび標準出力への表示。`--profile` によるモデル起動、ネットワーク接続、journal の書き換えはない。
- `--profile` は他の `ops` アクションと共有された parser 定義だが、この文書の対象は `ops result` における作用である（`terminal/strata_cli/cli.py:283-295`）。

## 出力とエラー

- 成功時は終了コード `0`。human 出力は `record` の整形 JSON、`--output json` は `{"schema_version":1,"ok":true,"record":...}` の JSON（`terminal/strata_cli/cli.py:566-573,1479-1481`）。
- profile 不正・未保存、operation ID の形式不正、記録の欠落・破損・指定 profile との不一致は失敗する。通常は stderr に `strata: <理由>` を出し、JSON 出力では error envelope を返す。`ProfileError` は既定終了コード `2`、record 不在や不正レコードはコード `5`（`terminal/strata_control/profiles.py:30-35,153-173`、`terminal/strata_control/journal.py:60-63,190-210`、`terminal/strata_cli/cli.py:558-563,2194-2255`）。
- `operation_id` の省略など parser 段階の引数エラーは argparse が usage とエラーを表示して終了する（位置引数の登録: `terminal/strata_cli/cli.py:290-295`）。

## 根拠

- `terminal/strata_cli/cli.py:283-295` — `ops` のサブコマンド群、`operation_id`、必須 `--profile` と `--output` の parser 定義。
- `terminal/strata_cli/cli.py:1479-1481` — `--profile` と ID による読み込み、および `record` の返却。
- `terminal/strata_control/journal.py:47-63,190-210,252-256` — journal の配置、ID 形式、record 検証、実行中記録の扱い。
- `terminal/strata_control/profiles.py:38-55,153-173` — profile ディレクトリ、名前規則、保存済み profile の読み込み。
- `terminal/strata_control/private_files.py:479-487` — profile 読み込み時にアクセス拒否があった場合の修復再試行。
- `terminal/strata_cli/cli.py:558-573,2194-2255` — 成功出力形式と `ValueError` / `OSError` の失敗出力・終了コード処理。

調査範囲は上記 commit の Terminal CLI parser と、その `ops result` 呼び出し経路および profile/journal 読み込み処理。実行時の OS 固有アクセス修復の詳細は調査していない。
