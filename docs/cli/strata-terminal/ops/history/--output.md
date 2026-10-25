# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops history` |
| オプション | `--output` |
| 別名 | なし（`--json` は JSON 出力に切り替える別のフラグ） |
| 値 | `human` または `json` |

## 役割

選択した保存済み operator recipe の revision 履歴を、人向け表示か機械処理向け JSON で出力します。このオプションは `strata ops` 配下の各 action parser に共通で設定されています。

## 使い方

```sh
strata ops history restart --profile default --output json
```

`NAME`（recipe 名）と必須の `--profile PROFILE` を指定します。例の `restart` は `strata ops init` が用意する recipe 名です（parser の位置引数と profile 指定: `strata_cli/cli.py:258-267`、初期 recipe 名: `strata_control/recipes.py:153-158`）。

## 値と既定値

- `human` と `json` のみ受理され、省略時は `human` です。未知の値は `argparse` が拒否し、通常の usage error（終了コード 2）になります（`strata_cli/cli.py:266-267`）。
- `--json` も one-shot command 用に登録されており、指定すると `--output json` と同じ出力形式になります。両方を指定しても `json` が選ばれます（登録: `strata_cli/cli.py:508-515`、反映: `strata_cli/cli.py:2232-2235`）。

## 実行時の動作

- `human` は履歴ごとに `<revision>  current` または `<revision>  saved` を1行ずつ表示します。現行 revision を先頭にし、過去 revision は保存時刻の新しい順です（履歴取得: `strata_cli/cli.py:1431-1435`、順序と識別: `strata_control/recipes.py:240-250`）。
- `json` は標準出力に1つの JSON object を出し、`schema_version: 1`、`ok: true`、`profile`、`recipe`、`history` を含みます。`history` は現行 revision を `{"revision": ..., "current": true}` として先頭に置き、過去 revision には `revision` と `saved_at`（ファイル更新時刻の Unix 秒）を含めます（`strata_cli/cli.py:535-542,1431-1435`、`strata_control/recipes.py:240-250`）。成功時の終了コードは 0 です。
- 履歴取得は最初に profile と recipe を読み込みます。履歴フォルダーが存在しない場合もエラーにはならず、現行 revision のみを返します。過去履歴としては16桁小文字16進数のファイル名を持つ通常ファイルだけを列挙し、シンボリックリンクは除外します（`strata_control/recipes.py:180-196,240-250`）。
- このコマンドは履歴を変更しません。ただし profile 読み込みが権限エラーになった場合、共通処理 `read_bytes_repairing` はアクセス権修復を試みて再読込します（`strata_control/profiles.py:150-166`、`strata_control/private_files.py:476-484`）。
- `--quiet` も登録されています。`--output human --quiet` では成功時の人向け stdout が抑制され、JSON 出力では quiet による抑制は適用されません（`strata_cli/cli.py:514-515,2236-2247`）。

## 適用条件と副作用

このオプションは `strata ops history` に適用されます。`--profile` は必須で、profile/recipe の存在・妥当性確認は `--output` の値にかかわらず行われます。revision 履歴の取得自体に保存・削除処理はありません（`strata_cli/cli.py:255-267,1431-1435`、`strata_control/recipes.py:240-250`）。

## 出力とエラー

- `json` での `ValueError` 系エラーは `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` の JSON を標準出力へ出します。人向け形式では `strata: <message>` を標準エラーへ出します（`strata_cli/cli.py:527-532,2166-2173`）。
- 指定 recipe が存在しない場合、読み込み処理は `ProfileError`（終了コード 5）を返します。不正な profile 名・recipe 名や壊れた recipe も失敗します。ファイルアクセス等の `OSError` は終了コード 6 として処理されます（`strata_control/recipes.py:32-35,180-196`、`strata_cli/cli.py:2176-2183`）。
- `--output` に未対応の値を指定した場合は parser が実行前に拒否し、終了コード 2 になります（`strata_cli/cli.py:266-267`）。

## 根拠

- parser とスコープ: `strata_cli/cli.py:255-267`、`strata_cli/cli.py:508-515`
- alias 処理と quiet: `strata_cli/cli.py:2217-2247`
- history の取得および表示: `strata_cli/cli.py:1391-1394,1431-1435`
- JSON 成功・失敗 envelope と例外処理: `strata_cli/cli.py:527-542,2166-2183`
- profile/recipe 読込と履歴順序: `strata_control/recipes.py:32-35,180-196,240-250`、`strata_control/profiles.py:150-166`
- profile 読込時のアクセス修復経路: `strata_control/private_files.py:476-484`
