# `--from-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config <name>` |
| オプション | `--from-config CONFIG.json` |
| 別名 | なし |
| 値 | run config JSON ファイルのパス。必須の文字列引数 |

## 役割

保存済み profile が参照する run config を別ファイルへ切り替えます。選んだファイルの内容は変更せず、profile の `source_config` にそのファイルの絶対パスを保存します。稼働中のインスタンスはこの操作では再起動されず、変更も適用されません（`strata_cli/cli.py:89-95, 969-985`、`strata_control/profiles.py:252-263`）。

同じ `--from-config` は `strata profile create` にもありますが、そちらは新規 profile 作成用の別スコープです。本書は `use-config` の動作を記載します（`strata_cli/cli.py:71-74, 89-95`）。

## 使い方

```sh
strata profile use-config my-profile --from-config /absolute/path/next-model.json --plan --output json
```

確認後、`--plan` を外すと profile を更新します。レビュー時に得た profile revision を `--if-revision` に渡すと、レビュー後に profile が変わっていた場合の更新を拒否できます（`strata_cli/cli.py:92-95, 973-981`）。

## 値と既定値

- parser では `required=True` の単一値オプションです。省略時は `argparse` が usage を stderr に表示して終了コード 2 で終了します。別名、CLI 側の型変換、既定値の指定はありません（`strata_cli/cli.py:89-95`）。
- 値はパス文字列として扱います。`~` を展開し、存在するパスへ strict 解決して絶対パス化します。解決先が通常ファイルであることを確認します。存在しない、アクセスできない、または通常ファイルでないパスは受理されません（`strata_control/profiles.py:252-263`）。
- ファイルは UTF-8（BOM 付きも可）の JSON として読み取られ、トップレベルが object、`args` が文字列だけの配列、`exe` と `tokenizer` が空でない文字列であることが必要です。この検査で run config 全体の意味的妥当性や参照先ファイルの存在までは検証しません（`strata_control/profiles.py:135-147`）。
- 空文字列や不正 JSON は有効な設定になりません。単一値 parser のため同じオプションを複数回指定した場合は argparse の通常動作で最後の値が採用されます。

## 実行時の動作

`use-config` はまず profile を読み込み、`propose_source` で指定 run config を検証して、`source_config` だけを置き換えた候補を作ります。profile の他のフィールド、特に serving overrides は引き継がれます（`strata_cli/cli.py:968-975`、`strata_control/profiles.py:252-263`）。

`--plan` を指定すると、変更前後のパス、profile revision、run config の `model_name`、パスが変わる場合の `would_save` を表示し、profile は保存しません。省略時は revision を照合したうえで保存します。同じパスが選ばれ、候補が現状と同一なら保存処理は revision を変えずに返ります（`strata_cli/cli.py:975-985`、`strata_control/profiles.py:266-295`）。

保存時には profile の排他ロックと revision 照合を行います。変更があれば旧 profile を `.history/<name>/<revision>.json` に保存し、profile JSON を一時ファイル経由で置換します。run config ファイル自体は書き換えません（`strata_control/profiles.py:185-210, 213-233, 266-295`）。

出力形式は既定で human です。`--output json` または同じ one-shot parser に追加される `--json` で JSON 出力にできます。`--quiet` も共通 parser にありますが、JSON 指定時は quiet による stdout 抑制の対象外です（`strata_cli/cli.py:95, 508-515, 535-542, 2232-2247`）。

## 適用条件と副作用

- 指定する profile が既に保存され、読み取り可能かつ有効である必要があります。未保存なら profile の作成を案内するエラーになります（`strata_control/profiles.py:120-166`）。
- このコマンドは実行中サーバーを停止・再起動しません。成功時の human 出力にも「running instance unchanged」と明記されます。新しい参照先を使う起動・再起動は別操作です（`strata_cli/cli.py:981-985`）。
- 通常の保存では profile 本体と revision 履歴が更新されます。`--plan` は profile を保存しません。ただし CLI 共通の起動処理はユーザーデフォルトの採用を試み、profile 読み込みは権限修復付き読み取りを使うため、実行全体について一切のファイル副作用がないとは限りません（`strata_cli/cli.py:2217-2222`、`strata_control/profiles.py:150-166`）。
- `--if-revision` は任意です。指定値が現在の revision と異なる場合は保存を中止し、終了コード 6 の競合エラーになります。revision は profile JSON の SHA-256 先頭 16 桁です（`strata_cli/cli.py:971-974`、`strata_control/profiles.py:58-64`）。

## 出力とエラー

- 成功時は終了コード 0。human 出力は計画時に `Config: <before> -> <after>`、保存時に `Saved source config for ...; running instance unchanged` を出します。JSON 出力では計画時に `source_config`、`model_name`、`would_save`、保存時に profile と前後の revision、`source_config` の変更を含みます（`strata_cli/cli.py:975-985, 535-542`）。
- run config が読めない場合や必須フィールドを欠く場合、profile がない・不正な場合などは `ProfileError`（`ValueError` 派生）経由でエラーになります。ファイル読み取り失敗などの設定読み込みエラーは通常終了コード 5、入力検証エラーは既定で 2 です。profile の同時変更、`--if-revision` 不一致は終了コード 6 です（`strata_control/profiles.py:30-36, 135-147, 150-166, 252-263`、`strata_cli/cli.py:971-974, 2166-2183`）。
- human エラーは stderr に `strata: <message>`、JSON モードでは stdout に `{"ok":false,"error":...}` 形式を出します（`strata_cli/cli.py:527-532, 2170-2183`）。

## 根拠

- parser とコマンド階層: `strata_cli/cli.py:69-105`
- parser から処理への分岐、plan・保存、 revision 条件: `strata_cli/cli.py:958-985`
- パス解決、通常ファイル確認、run config 検証: `strata_control/profiles.py:135-147, 252-263`
- profile 検証、ロック・履歴・atomic 保存: `strata_control/profiles.py:120-166, 185-233, 266-295`
- 成功・失敗出力と例外変換: `strata_cli/cli.py:527-542, 2166-2183`
- 関連する利用者向け例: `docs/TERMINAL.md:78-85`

この調査では同一 revision のソース parser と実装を確認しました。CLI `--help` の実行や Release artifact の照合は行っていません。
