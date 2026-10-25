# `strata presets import`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets import` |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py` |
| 引数・オプション | `FILE`、`--output human|json`（既定 `human`） |

## 役割

JSON ファイルから Strata のチューニング preset を読み込み、現在の preset 保存領域へ新しい preset として登録します。preset はチューナーが見つけた設定と計測情報などを含み、Terminal CLI と desktop app で共有されます。これは `strata launch` の起動設定 preset ではなく、モデルの選択条件に対応する tuning preset です（`strata_control/presets.py:1-17,34`）。

## 使い方

```sh
# カレントディレクトリにある preset JSON を取り込む
strata presets import ./tuning.json

# 成功・失敗応答を JSON 形式で出力する
strata presets import ./tuning.json --output json
```

このコマンドは import だけでは preset を有効化しません。成功メッセージに表示された ID または名前を `strata presets apply` に渡して有効化できます（`strata_cli/tune_commands.py:338-342`）。

## 実行時の動作

1. `FILE` を `utf-8-sig` として読み込み、JSON として解析します。BOM 付き UTF-8 もこの読み込み指定で扱われます（`strata_cli/tune_commands.py:338-340`）。
2. ルート値がオブジェクトで、`schema` が `strata.preset/1` と一致することを確認します。さらに `settings.args` と `settings.env` をチューニング設定の安全規則で検査します。検査時の context は preset の `choices.context` を使い、値がなければ 32768 です（`strata_control/presets.py:34,396-402`）。
3. 検証を通ると、元データを複製し、新しいランダム ID を割り当て、`name` が空または欠落なら `Imported preset` を使います。同名 preset があれば ` (2)`、` (3)` のような連番を付け、`previous` を `null` にし、入力中の `active` 属性を除いて保存します（`strata_control/presets.py:255-265,403-409`）。
4. preset JSON を保存した後、その preset の概要を出力します。追加の有効化操作は行いません（`strata_cli/tune_commands.py:338-342`）。

保存先は既定で profiles directory の隣にある `presets/` です。環境変数 `STRATA_PRESET_DIR` が設定されていれば、その展開済みパスを使用します。JSON ファイルは一時ファイル経由で書き込み・置換されます（`strata_control/presets.py:45-68`）。

## 出力・失敗経路

- `--output` は `human` または `json` のみ受け付け、既定値は `human` です。このサブコマンドの parser では `--json` alias は定義されていません（`strata_cli/tune_commands.py:53-55,76-77`）。
- 成功時の human 出力は取り込み名と `strata presets apply <ID prefix>` の案内です。JSON 成功応答は `schema_version: 1`、`ok: true`、preset 概要を含みます（`strata_cli/tune_commands.py:95-100,338-342`）。
- Strata preset schema でないファイル、または安全規則に合わない設定は `PresetError` となります。human 出力では `strata: ...` を stderr に出し、終了コード 5 を返します。JSON 出力では `ok: false` とエラー情報を出力します（`strata_control/presets.py:39-41,396-402`; `strata_cli/tune_commands.py:103-108,344-345`）。
- ファイル読み込み・JSON 解析などの `OSError` / `ValueError` は共通例外処理に渡り、human では stderr、JSON ではエラー JSON になります。通常の `ValueError` は終了コード 2 です。保存時の OS エラーもここで処理されます（`strata_cli/tune_commands.py:338-347`）。
- `--output` の値の誤りや `FILE` の欠落は `argparse` が拒否し、通常の parser usage error（終了コード 2）になります。サブコマンド自体も必須です（`strata_cli/tune_commands.py:49-52,76-77`）。

## 注意点

- インポートは preset JSON を保存領域へ書き込みます。既存の preset と同じ名前でも上書きせず、別名に調整して保存します（`strata_control/presets.py:255-265,403-409`）。
- 取り込み時に新しい ID が付くため、後続の `apply` には元ファイル内の ID ではなく、成功応答に示される取り込み後の ID または名前を使います（`strata_control/presets.py:403-409`; `strata_cli/tune_commands.py:338-342`）。
- ソースで確認した検証は schema と `settings.args` / `settings.env` の安全規則です。計測値や identity など preset の全フィールドについて、完全な整合性検証を行うとは確認できませんでした。未確認の入力項目の受理範囲は断定しません。
- この調査では既存 CLI の `--help`、他 platform の実行、Release artifact は確認していません。記述は上記 revision の parser と処理コードに基づきます。

## 関連文書

- [CLI オプション索引](../../../README.md) — `strata presets import` の位置とオプション一覧。
- [`strata presets` の概要](../README.md) — tuning preset 全体の保存・有効化・共有の説明。
- [`strata presets apply` の概要](../apply/README.md) — 取り込んだ preset を有効化する方法。
- [`strata presets export` の概要](../export/README.md) — preset JSON の書き出し。

## 根拠

- `strata_cli/tune_commands.py:49-55,76-77` — `presets import FILE` と `--output` parser 定義。
- `strata_cli/cli.py:487-488,2151-2155` — presets parser の登録とコマンド dispatch。
- `strata_cli/tune_commands.py:95-108,338-347` — 成功・失敗時の human/JSON 出力と例外処理。
- `strata_control/presets.py:34,45-68` — schema 定数、保存先とファイル書き込み。
- `strata_control/presets.py:255-265,396-409` — 名前重複の処理、schema・安全規則検証、新 ID の割り当てと保存。
- `docs/cli/README.md:891-896` — このコマンド概要と option の索引上の scope。
