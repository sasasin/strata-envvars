# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops show` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `false` |

## 役割

レシピの内容と revision を表示するとき、成功結果を `schema_version` / `ok` を含む JSON envelope で出力します。エラー時も JSON オブジェクトを標準出力に出す one-shot 出力モードです。

## 使い方

```sh
strata ops show restart --profile work --json
```

`restart` はレシピ名、`work` は既存の profile 名です。`--profile` は `strata ops show` で必須です。

## 値と既定値

`--json` は引数を取らず、指定時に有効になります。未指定時は無効です。`strata ops show` は `--output human|json` も受け付け、既定値は `human` です。`--json` が指定されると、引数解析後に `--output json` 相当へ設定されます。したがって `--output human --json` を同時指定しても JSON モードになります。

## 実行時の動作

`show` は profile とレシピ名を使ってレシピを読み込み、検証済み recipe と revision を返します。`--json` 指定時の成功出力は `{"schema_version":1,"ok":true,"recipe":...,"revision":"..."}` 形式で、1行の JSON です。日本語を ASCII escape せず、非有限数は許可しません。

`--json` を省略した場合も `show` は通常の人間向け文章を別途作らず、recipe と revision を整形 JSON として出力します。違いは機械モードでは成功時に envelope が付き、エラー時も JSON になる点です。

読み込み対象は profile ディレクトリ内の `.ops/<profile>/<name>.json` です。profile とレシピ名は小文字英字で始まり、英小文字・数字・`_`・`-` のみ、最大64文字です。レシピファイルは通常ファイルで64 KiB以下である必要があり、POSIX では所有者のみ読み書き可能な mode `0600` が検査されます。JSON の UTF-8 読み込み後、schema version、格納 profile / ID、recipe kind と params が検証されます。

## 適用条件と副作用

このオプションは one-shot コマンド向けの `--json` として全 `ops` action parser に追加されます。`show` の実処理は保存済みレシピの読込・表示のみで、レシピの編集や operation の実行は行いません。profile データの探索・読み込みは行います。コマンド共通の起動処理は `strata_control.private_files.adopt_user_defaults()` を呼びますが、この関数は Windows 以外では何もせず、Windows でも昇格プロセスの作成時既定 owner / DACL を設定する処理です。

## 出力とエラー

JSON モードでの成功は標準出力へ JSON を1行出し、終了コード `0` です。レシピが存在しない場合や読込・JSON parse・schema 検証に失敗した場合、`ProfileError` は `ValueError` として CLI の共通処理に渡され、標準出力に `{"schema_version":1,"ok":false,"error":{"code":... ,"message":...}}` が出ます。終了コードは例外の `exit_code` で、通常の入力エラーは `2`、読込・安全性検証エラーとして明示されたものは `5` です。I/O の `OSError` は JSON モードなら同じ error envelope となり、終了コード `6` です。引数の不足や未知の引数は argparse の parser error となり、JSON envelope にはなりません。

## 根拠

- parser: `strata_cli/cli.py:255-267` で `ops show` を含む各 action を作成し、`--profile` 必須、`--output` の選択肢と既定値を定義。`strata_cli/cli.py:508-514` で全 `ops_items` に `--json` (`store_true`) を追加。
- JSON フラグの適用: `strata_cli/cli.py:2223-2235` で引数解析後に `--json` を `output="json"` に反映。
- show の処理: `strata_cli/cli.py:1391-1394,1416-1418` で出力 mode を判定し、レシピと revision を読み込み成功応答へ渡す。
- 成功・失敗の出力形式: `strata_cli/cli.py:527-542`。例外処理と終了コード: `strata_cli/cli.py:2166-2183`。
- CLI 共通起動処理: `strata_cli/cli.py:2217-2222`。対象関数の Windows 限定動作: `strata_control/private_files.py:349-389`。
- レシピ識別子・ファイル検証・schema 検証: `strata_control/recipes.py:32-35,62-65,93-114,180-196`。profile 名規則と `ProfileError` の既定終了コード: `strata_control/profiles.py:25,30-35`。
