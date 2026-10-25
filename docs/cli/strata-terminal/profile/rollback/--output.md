# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile rollback` |
| オプション | `--output` |
| 別名 | なし（`--json` は別オプション） |
| 値 | `human` または `json` |

## 役割

rollback の結果を、人向けテキストか機械処理向け JSON のどちらで標準出力へ出すか選びます。rollback 対象は別オプション `--to REVISION` で指定します。このオプションは結果表示を切り替えるもので、rollback の対象や保存処理は変えません（`strata_cli/cli.py:102-105, 1011-1014`）。

## 使い方

```sh
strata profile rollback my-profile --to 0123456789abcdef --output json
```

`REVISION` には `strata profile history my-profile` などで確認した履歴 revision を指定します。

## 値と既定値

parser は `human` と `json` のみを受け付け、既定値は `human` です。値は位置引数ではなく `--output` の直後に指定します。別の値を指定すると `argparse` が引数エラーとして拒否し、終了コード 2 になります（`strata_cli/cli.py:102-105, 2223-2231`）。

`--json` は one-shot parser 群に追加される別オプションです。指定時は `main()` が `output` を `json` に設定するため、rollback でも JSON 出力になります（`strata_cli/cli.py:508-515, 2232-2235`）。

## 実行時の動作

`human`（省略時）は成功時に `Restored profile <名前>: <旧revision> -> <新revision>; running instances are unchanged` を標準出力へ出します。`json` は標準出力へ `schema_version: 1`、`ok: true`、`profile`、`previous_revision`、`revision` を含む1つの JSON オブジェクトを出します（`strata_cli/cli.py:1011-1014, 535-542`）。

出力モードにかかわらず、rollback は指定 revision の保存済み profile を読み込み、現在の profile をその内容に更新します。現在の profile の旧 revision を `.history/<profile名>/<revision>.json` に履歴として保存してから、profile ファイルを置き換えます。revision がすでに現在の内容と同じ場合は保存処理が変更なしとして返るため、新しい revision にはなりません（`strata_control/profiles.py:326-346, 266-295`）。実行中の serving instance はこの操作で変更されません（`strata_cli/cli.py:1012-1014`）。

## 適用条件と副作用

`--to` は必須です。指定する revision は小文字16進数16文字でなければならず、profile の履歴ディレクトリにある通常ファイルで、その内容の revision hash（profile JSON の SHA-256 先頭16文字）がファイル名と一致し、profile として妥当である必要があります（`strata_cli/cli.py:102-105; strata_control/profiles.py:62-63, 326-346`）。成功時はユーザーの profile 保存領域にある profile と履歴ファイルを更新します。保存先は `STRATA_PROFILE_DIR` が設定されていればその値、未設定なら OS に応じた既定の設定ディレクトリです（`strata_control/profiles.py:38-45`）。

`--output` は stdout の形式だけに適用され、rollback のファイル更新を無効化しません。`--quiet` も同じ one-shot parser で利用できます。human 出力と `--quiet` を併用すると成功時の標準出力は抑制されます。JSON 出力は quiet より優先され、JSON のまま表示されます（`strata_cli/cli.py:508-515, 2232-2247`）。

## 出力とエラー

profile が存在しない、revision 形式が不正、履歴がない・破損している、または更新中に profile が変化した場合は rollback が失敗します。確認できるエラーコードは、通常の入力エラーが 2、profile/履歴の不在や不正が 5、競合などの更新失敗が 6 です（`strata_control/profiles.py:30-35, 326-346`）。JSON モードでは失敗を `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON として標準出力に出します。human モードでは `strata: <エラー>` を標準エラーに出します（`strata_cli/cli.py:527-532, 2166-2183`）。

## 根拠

- parser 定義、値の制約と既定値: `strata_cli/cli.py:102-105`
- `--json` / `--quiet` の追加と `--json` の適用: `strata_cli/cli.py:508-515, 2232-2247`
- rollback 呼び出しと成功表示: `strata_cli/cli.py:1011-1014`
- profile revision の検証、履歴からの復元: `strata_control/profiles.py:326-346`
- 履歴保存と profile の更新: `strata_control/profiles.py:266-295`
- 出力形式と共通エラー処理: `strata_cli/cli.py:527-542, 2166-2183`
- profile 保存ディレクトリ: `strata_control/profiles.py:38-45`
