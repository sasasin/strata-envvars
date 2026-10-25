# `strata ops rollback` の `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の Strata checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--output` |
| 別名 | なし。`--json` は別のフラグとして用意されています |
| 値 | `human` または `json` |

## 役割

rollback の結果を人向け表示または JSON で標準出力へ出します。rollback の対象や復元処理は変えません。`ops` の各 action parser に同じ `--output {human,json}` が登録されており、この文書では `rollback` action の動作を扱います（`strata_cli/cli.py:255-267`）。

## 使い方

```sh
strata ops rollback deploy --profile local --to 0123456789abcdef --output json
```

`deploy` は recipe 名、`--profile` は対象 profile、`--to` は復元する履歴の revision です。例の revision は形式を示す値なので、実際には `strata ops history <recipe名> --profile <profile名>` で確認した履歴 revision に置き換えます。rollback の位置引数と必須 option は parser に定義されています（`strata_cli/cli.py:264-267`, `strata_cli/cli.py:276-277`）。

## 値と既定値

- 省略時は `human` です。
- 受理値は `human` と `json` のみです。空文字や他の値は argparse が拒否し、usage とエラーを標準エラーへ出して終了コード 2 になります（`strata_cli/cli.py:267`; parser は `argparse.ArgumentParser`、同:40）。
- `--output` の重複指定は argparse の通常の値 option として後に指定した値が残ります。
- `--json` は `--output` の alias ではなく独立したフラグです。指定すると `main()` が `output` を `json` に設定します（`strata_cli/cli.py:508-515`, `strata_cli/cli.py:2232-2235`）。

## 実行時の動作

handler は `a.output == "json"` を machine 出力として判定します。rollback 成功時、`human` は `Restored recipe <name>: <旧revision> -> <新revision>` を出力し、`json` は `schema_version`, `ok`, `recipe`, `previous_revision`, `revision` を含む JSON オブジェクトを1行で標準出力へ出します（`strata_cli/cli.py:1391-1394`, `strata_cli/cli.py:1436-1439`; 成功出力共通処理は同:535-542）。

復元処理は現在の recipe を読み、その SHA-256 先頭16桁の revision と一致する履歴ファイルを検証してから、現在の revision を期待値として保存します。保存時には現在内容の履歴バックアップを作り、recipe を atomic 更新します。したがって `--output` の値にかかわらず recipe と履歴ディレクトリへのファイル変更が起こります（`strata_control/recipes.py:253-275`, `strata_control/recipes.py:214-237`, revision 算出は `strata_control/profiles.py:62-63`）。

## 適用条件と副作用

- `--to` は小文字16進数16文字でなければなりません。履歴が見つからない、revision とファイル内容が一致しない、履歴 JSON や recipe が不正、または保存中に recipe が変わった場合は復元を拒否します（`strata_control/recipes.py:253-275`, `strata_control/recipes.py:214-237`）。
- `--quiet` はこの parser にも追加されます。`--output human` と併用すると成功時の標準出力は抑制されます。JSON 出力時は `main()` が quiet capture を通さず handler を実行するため、`--quiet` を指定しても JSON は出力されます（`strata_cli/cli.py:508-515`, `strata_cli/cli.py:2236-2247`）。
- profile 名と recipe 名には小文字英字で始まり、小文字英字・数字・`_`・`-` からなる最大64文字という制約があります。recipe 状態は `STRATA_PROFILE_DIR` があればその配下、なければ OS ごとの profile ディレクトリ配下にあります（`strata_control/recipes.py:32-35`, `strata_control/profiles.py:25`, `strata_control/profiles.py:38-45`）。

## 出力とエラー

- rollback が `ProfileError` を送出した場合、`_run()` が JSON 指定なら `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}`、human 指定なら `strata: <message>` を標準エラーへ出します。終了コードは各エラーの `exit_code` で、指定がない通常の入力エラーは 2、履歴や recipe の問題には 5、同時変更には 6 が設定されています（`strata_control/profiles.py:30-35`, `strata_control/recipes.py:253-275`, `strata_cli/cli.py:527-533`, `strata_cli/cli.py:2166-2173`）。
- `OSError` は共通 handler で JSON 指定時に JSON error、human 指定時に標準エラーの説明となり、通常は終了コード 6 です。permission error は既知の private directory 修復後に一度 retry する経路があります（`strata_cli/cli.py:2085-2104`, `strata_cli/cli.py:2176-2183`）。
- CLI parser の値不正・必須引数不足は rollback handler に到達せず、argparse の usage/error 経路になります（`strata_cli/cli.py:40`, `strata_cli/cli.py:2223-2231`）。

## 根拠

- parser 定義と option scope: `strata_cli/cli.py:255-277`, `strata_cli/cli.py:508-515`
- `--output` 判定と rollback 成功応答: `strata_cli/cli.py:1391-1394`, `strata_cli/cli.py:1436-1439`
- revision 検査・履歴読込・保存: `strata_control/recipes.py:253-275`, `strata_control/recipes.py:214-237`
- 標準出力・エラー変換・quiet 処理: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2183`, `strata_cli/cli.py:2232-2247`
- profile 保存先と ID 形式: `strata_control/profiles.py:25`, `strata_control/profiles.py:38-45`

調査範囲は上記 commit のソース checkout です。同一 revision の配布済みバイナリや Release artifact の動作は確認していません。
