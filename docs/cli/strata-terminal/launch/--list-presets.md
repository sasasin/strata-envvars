# `--list-presets`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--list-presets` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真、未指定時は偽。 |

## 役割

このユーザーの保存済み launch preset を列挙します。preset は `strata launch` の設定一式を名前付きで保存したものです。指定した場合、通常のモデル準備やサーバー起動経路には進まず、一覧を表示して終了します。

## 使い方

```sh
strata launch --list-presets
```

JSON で取得する場合:

```sh
strata launch --list-presets --output json
```

`--output` は `human` または `json` を受け取り、既定値は `human` です。

## 値と既定値

`--list-presets` 自体は `argparse` の `store_true` フラグで、引数値・別名・追加 validation はありません。未指定なら一覧表示分岐に入りません。`--output` の値が不正な場合は通常の parser validation で拒否されます（`strata_cli/launch/cmd.py:140-142`）。

## 実行時の動作

一覧の取得には `store.list_presets()` を使います。保存先は環境変数 `STRATA_LAUNCH_PRESET_DIR` があればその展開後のパス、なければ profiles ディレクトリの隣の `launch-presets/` です。保存ディレクトリが存在しない場合は空の一覧になります（`strata_cli/launch/store.py:27-32,115-120`）。

ディレクトリ直下の `*.json` を名前順で読み、読み込み時に `OSError` または `ValueError` が発生しなかった preset を `last_used`、次に `created` の文字列の降順で返します。読み取り不能や JSON 構文エラーなど、この例外に該当するファイルは一覧から黙って除外されます（`strata_cli/launch/store.py:120-129`）。

既定の human 出力では、preset がないときは保存方法を案内するメッセージを表示します。ある場合は名前、model、context、並列数または `fit to card`、調整済みかどうか、最終使用時刻を1件ずつ表示します（`strata_cli/launch/cmd.py:648-655`）。JSON 出力は `schema_version: 1`、`ok: true`、`presets` を含む JSON オブジェクトです。preset の設定項目を含みますが、`api_key` は `set` または `null` に置き換え、実値を出力しません（`strata_cli/launch/cmd.py:646-647`; `strata_cli/launch/settings.py:114-118`）。

## 適用条件と副作用

このオプションを先に処理するため、同じ呼び出しで `--delete-preset`、`--status`、`--stop`、`--show-key` なども指定した場合、それらの後続分岐には進まず一覧表示で終了します。複数の管理フラグの同時指定は専用エラーにはならず、ソース上の分岐順で `--list-presets` が優先されます（`strata_cli/launch/cmd.py:643-677`）。

一覧処理は preset の読み取りと標準出力への表示を行い、preset の保存・削除、モデルや tuning 結果の変更、サーバーの起動・停止は行いません（`strata_cli/launch/cmd.py:643-656`; `strata_cli/launch/store.py:115-129`）。この調査では異なる OS での実行結果や実データを使った実行確認はしていません。

## 出力とエラー

- preset がないときも正常終了し、human では案内文、JSON では空の `presets` 配列を出力します（`strata_cli/launch/cmd.py:646-656`）。
- 個別の preset ファイルを読む際に `OSError` または `ValueError` が発生した場合は、そのファイルだけを飛ばし、他の対象ファイルの列挙を続けます。ほかの例外型による失敗挙動までは、この処理から確認できません（`strata_cli/launch/store.py:120-127`）。
- human 出力は標準出力へ書き込まれます（`strata_cli/launch/cmd.py:416-419,648-655`）。
- `--output` に `human` / `json` 以外を指定した場合の parser エラー表示と終了コードは、共通の `argparse` 処理に委ねられます。CLI 本体は `parse_known_args` の後、未知引数を `strata:` 付きで標準エラーへ出し終了コード `2` を返します（`strata_cli/launch/cmd.py:140`; `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/launch/cmd.py:16-29,75-82,127-146` — `launch` の説明・例、共通 `--output` と `--list-presets` の parser 定義。
- `strata_cli/launch/cmd.py:630-656` — JSON/human の分岐、空一覧メッセージ、human の列、早期 return。
- `strata_cli/launch/store.py:27-32,115-129` — preset 保存先、読み込み対象、読み込み失敗のスキップ、並び順。
- `strata_cli/launch/settings.py:114-128` — JSON 化時の API key マスキングと preset 設定の復元。
- `strata_cli/cli.py:2223-2231` — parser 呼び出しと未知引数のエラー処理。
- 索引: [`docs/cli/README.md`](../../README.md) の `strata launch` 節に本書へのリンクが掲載されています。
