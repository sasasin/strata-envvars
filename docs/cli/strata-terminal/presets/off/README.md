# `strata presets off`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets off` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/tune_commands.py`、`strata_control/presets.py` |
| 必須引数 | `target`（保存済み profile 名、または run config JSON のパス） |
| 出力形式 | `--output human`（既定）または `--output json` |

## 役割

指定した profile / run config の選択内容に対応する保存済み tuning を無効にし、その構成を次回起動するときは標準設定に戻します。preset のデータは削除せず保持するため、後で `strata presets apply` から再び有効化できます。サブコマンドは `strata presets off <target>` の形で、`target` は必須です（`strata_cli/tune_commands.py:49-55,80-81`）。

## 使い方

```sh
# 保存済み profile に対応する tuning を無効にする
strata presets off my-profile

# run config JSON を直接指定する
strata presets off ./run-config.json

# 機械処理向け JSON を出力する
strata presets off my-profile --output json
```

`target` が `.json` パス、絶対パス、または `/`・`\\` を含む場合は run config として扱われます。それ以外は保存済み profile 名として解決されます。profile の source run config を読み、そこから対象 preset slot を決めます（`strata_control/profiles.py:382-388`、`strata_cli/tune_commands.py:111-115`）。

## 実行時の動作と副作用

1. run config から model / context / KV format / vision / resource goal などの選択内容を取り出し、現在のモデル・エンジン・ハードウェア情報を使って slot を特定します（`strata_control/presets.py:89-117,128-131,136-155`、`strata_cli/tune_commands.py:381-387`）。
2. その slot に active preset がある場合、preset ID を履歴へ追加し、active を `None` にして index を保存します。preset ファイル自体は削除されません（`strata_control/presets.py:329-337`）。
3. 保存先は `STRATA_PRESET_DIR` があればそのディレクトリ、なければ profile ディレクトリの隣にある `presets/` です。更新は同じディレクトリ内の一時ファイルを経由して `active.json` に置き換える方式です（`strata_control/presets.py:45-68,202-208`）。
4. このコマンド自体は推論エンジンを起動せず、測定もしません。次の起動時には server が保存 preset を overlay しますが、off 後は該当 slot に active がないため tuning は適用されず、run config の標準設定で起動します（`serve/server.py:7868-7878`、`strata_control/presets.py:441-456`）。

既に active preset がない slot でも成功扱いとなり、同じ「標準設定に戻った」メッセージを返します。履歴への追加やファイル書き込みは active preset が存在する場合だけです（`strata_control/presets.py:329-337`）。

## 出力と失敗

- 既定の human 出力は `Back to the standard settings. Your tuning is kept and can be switched on again.` です。成功終了コードは `0` です（`strata_cli/tune_commands.py:95-100,381-388`）。
- `--output json` は `schema_version: 1`、`ok: true`、`active: null` を含む JSON を stdout に出します（`strata_cli/tune_commands.py:95-100,289-306`）。
- profile / run config の読み込み、保存先への書き込みなどが失敗すると、通常出力は stderr、JSON 出力では `ok: false` と `error` を含む JSON になり、非ゼロ終了します。`ProfileError` は設定された終了コード（通常 2、run config の読み込み失敗などは 5）を使います。`strata presets` の dispatch は `OSError` / `ValueError` をコマンド内で捕捉し、例外に `exit_code` がなければ 2 を返します（`strata_control/profiles.py:135-147,382-388`、`strata_cli/tune_commands.py:344-347`、`strata_cli/cli.py:527-532,2166-2183`）。
- 不正・不足の引数は `argparse` の usage/error 経路になります。引数の parser は必須の `target` と `--output` の選択肢を定義しています（`strata_cli/tune_commands.py:53-55,80-81`）。

## 注意点

- 対象 slot は構成の選択内容とモデル digest で決まります。意図した profile / run config を指定してください。同じ profile でも構成内容や対象モデルが異なると別 slot になります（`strata_control/presets.py:89-117,128-131`）。
- 本コマンドは active 指定を切り替えるだけです。現在稼働中の server を停止・再起動する処理はありません（`strata_cli/tune_commands.py:381-388`）。
- コマンド実行時にはハードウェア、エンジン、モデルの識別情報を取得して slot を選びます。確認した実装では、このコマンドからネットワーク通信や推論測定を開始する処理はありません（`strata_control/presets.py:136-155`、`strata_cli/tune_commands.py:381-388`）。

## 関連文書

- [`strata presets` の索引と他の preset 操作](../README.md)
- [CLI 文書索引](../../../README.md)
- [`strata presets apply`](../apply/README.md)（preset の再有効化）
- [`strata presets undo`](../undo/README.md)（slot の履歴を戻す）
- [このコマンドの `--output`](--output.md)

## 根拠

- Strata `strata_cli/tune_commands.py:49-55,80-81` — `presets off` の parser と引数。
- Strata `strata_cli/cli.py:487-489,2151-2152` — parser 登録と実行 dispatch。
- Strata `strata_cli/tune_commands.py:95-108,111-115,289-306,381-388` — target 解決、成功出力、無効化処理。
- Strata `strata_control/profiles.py:135-147,382-388` — run config の検証と profile 名 / JSON パスの解決。
- Strata `strata_control/presets.py:45-68,89-117,128-155,202-208,329-337,441-456` — slot 生成、active index の保存、preset overlay 条件。
- Strata `serve/server.py:7868-7893` — server 起動時の saved tuning 適用。
- 索引 [`docs/cli/README.md:905-910`](../../../README.md) は `strata presets off` をこの概要パスと `--help` / `--output` 文書に割り当てています。parser の実装とも一致します。
