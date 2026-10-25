# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile rollback` |
| オプション | `--json` |
| 別名 | なし（`--output json` も同じ出力形式を選べます） |
| 値 | 取らないフラグ。省略時は `False` |

## 役割

rollback の成否を機械可読な JSON で標準出力へ出します。これは表示形式の指定であり、rollback の実行をプレビューしたり抑止したりするフラグではありません。rollback は保存済み profile とその履歴を読み、指定 revision の内容を現在の profile に保存します。

## 使い方

```sh
strata profile rollback work --to 0123456789abcdef --json
```

`work` は profile 名、`--to` の値は戻す履歴 revision です。例の revision は形式を示すプレースホルダーです。実際には `strata profile history work` で確認した revision を指定してください。

## 値と既定値

`--json` は値を取りません。rollback parser では `--output` の選択肢が `human` / `json`、既定値が `human` です。`--json` が指定されると、引数解析後に `--output json` 相当へ設定されます。そのため `--json` を省略し `--output` も省略した場合は人向け出力です。`--json` と `--output human` を同時に指定しても、後段の共通処理が `--output` を `json` にします。

## 実行時の動作

rollback は成功時に `schema_version: 1`、`ok: true`、`profile`、`previous_revision`、`revision` を含む JSON オブジェクトを1行出力し、終了コード `0` を返します。`profile` は復元後の profile オブジェクト、`previous_revision` は実行直前の revision、`revision` は保存後の revision です。JSON は UTF-8 の非 ASCII 文字をエスケープせず、NaN 等を許可せずに直列化します。

フラグは出力形式だけを変えます。対象 revision の復元、既存 profile の更新、現在動作中の instance を変更しない性質は human 出力の場合と同じです。profile 保存時は現在 revision を照合し、履歴があれば現行内容を履歴へ退避してから新しい内容を隣接一時ファイル経由で置き換えます。指定内容が現在と同一なら保存処理は変更せず同じ revision を返します。

## 適用条件と副作用

`strata profile rollback` 専用のフラグです。`--json` の対象 profile rollback は `strata profile rollback` parser に属し、共通処理で `--output json` に変換されます。

Rollback の副作用として profile ファイルと必要な履歴ファイルを更新しますが、実行中の serving instance は変更されません。`--json` 自体はファイル、ネットワーク、process、server を操作しません。

## 出力とエラー

JSON モードの失敗は標準出力に `{"schema_version":1,"ok":false,"error":{"code":<終了コード>,"message":"..."}}` 形式を出し、同じ `code` を終了コードとして返します。少なくとも、profile 名・revision 形式などの入力エラーは通常コード `2`、profile または履歴がない場合や履歴内容の検証・読み込みに失敗した場合はコード `5`、保存中に profile が変化した場合はコード `6` です。JSON を指定しない human モードではエラー文を `strata: ...` の形式で標準エラーへ出します。

`--json` の parser 宣言は rollback の parser を作った後、one-shot parser 群へ `store_true` として追加されます。`main` は `--json` を `output=jsonl` と併用できない経路ではなく、profile rollback では `--output` の choices が `human` / `json` のみなので、JSONL 形式は選べません。

## 根拠

- `strata_cli/cli.py:102-105` — `profile rollback` の parser、位置引数 `name`、必須 `--to`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — rollback parser を含む one-shot 群へ `--json`（`store_true`）と `--quiet` を追加。
- `strata_cli/cli.py:2232-2236` — `--json` を `output=json` へ変換する共通処理。
- `strata_cli/cli.py:958-959,1011-1014` — rollback 分岐と成功 payload、人向け成功文。
- `strata_cli/cli.py:527-542` — JSON 成功・失敗出力、終了コード、および human error の出力先。
- `strata_cli/cli.py:2166-2173` — `ValueError` 系の失敗を JSON モードでは JSON error に変換。
- `strata_control/profiles.py:326-346` — revision の16桁小文字16進形式検証、履歴ファイルの存在・通常ファイル・hash・profile validation、復元と保存。
- `strata_control/profiles.py:266-295` — revision 照合、変更がある場合の履歴退避と profile 更新、変更なしの場合の no-op。
- `strata_control/profiles.py:213-233` — 隣接一時ファイル、fsync、atomic replace による書き込み。
- `strata_control/profiles.py:48-55,120-132` — profile 名と復元 profile の schema / ID / source path / override 検証。

調査範囲は上記 commit の Terminal CLI parser と rollback 実装です。OS ごとのファイルシステム挙動や公式 Release artifact の実行確認は行っていません。
