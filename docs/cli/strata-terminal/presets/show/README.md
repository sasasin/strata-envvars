# `strata presets show`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets show` |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py` |
| 引数 | `preset`（保存済み preset の名前または ID） |
| オプション | `--output {human,json}`（既定値: `human`）、`--help`（alias: `-h`） |

## 役割

保存済みのチューニング preset を一件検索し、そのレコード全体を表示します。tuning の測定結果、対象の選択条件、engine 設定などを確認するときに使います。`strata presets` のデータは Terminal CLI と Strata アプリで共有されます。ここで preset を有効化・編集・削除したり、engine を起動したりはしません。

## 使い方

```sh
# 名前で表示
strata presets show "Model 128K – Full speed"

# ID の先頭 8 文字で表示
strata presets show 1a2b3c4d

# 機械処理向けの JSON envelope で表示
strata presets show 1a2b3c4d --output json
```

`preset` は完全な ID、4 文字以上の ID prefix、または大文字・小文字を区別しない完全一致の名前で指定できます。名前が重複している場合は ID を使ってください。

## 実行モードと出力

- `--output` を省略するか `human` を指定すると、preset の全内容を整形した JSON として標準出力に表示します。人向けモードも要約表示ではありません。
- `--output json` は `{"schema_version":1,"ok":true,"preset":...}` の JSON を一行で標準出力に返します。エラー時も JSON 形式となり、`ok:false` と `error` を含みます。
- どちらの出力モードも成功時の終了コードは `0` です。対象が見つからない、または指定が曖昧な場合は終了コード `5` になります。

## 主な動作と副作用

コマンドは preset store を走査し、各 JSON ファイルを読み込んで schema が `strata.preset/1` のレコードを候補にします。`active.json` の active ID と照合した `active` 属性を加え、指定名または ID に一致する一件を返します。不正 JSON、期待する schema と異なるファイルは一覧対象から除かれます。

通常の保存先は profiles ディレクトリの親にある `presets/` です。環境変数 `STRATA_PRESET_DIR` が設定されている場合はそのパス（`~` 展開あり）を使います。保存ディレクトリが存在しなければ候補は空となり、指定 preset は見つかりません。

show の処理自体は保存データを読むだけで、preset store を変更しません。起動共通処理として `strata_cli.cli.main` は引数解析前に `private_files.adopt_user_defaults()` を呼びますが、これは Windows 以外では何もしません。Windows では以後このプロセスが作成するファイルの owner と既定 ACL を調整しようとします。

## 注意点

- show は短い要約ではなく preset 全体を出力します。JSON モードでは `settings`、`answers`、測定値などのレコード内容がそのまま返るため、出力を共有・保存する前に内容を確認してください。
- 部分一致する名前検索はありません。名前は完全一致です。複数レコードが同じ名前なら曖昧として失敗し、ID prefix が複数に一致した場合も同様です。
- `strata presets apply` は有効 preset の切り替え、`strata presets list` は一覧、`strata presets effective` は設定へ適用した場合の実効値を確認する別コマンドです。

## 関連文書

- [CLI 索引](../../../README.md) — コマンド階層と option scope
- [`strata presets list`](../list/README.md)
- [`strata presets apply`](../apply/README.md)
- [`strata presets effective`](../effective/README.md)
- [`strata tune auto`](../../tune/auto/README.md) — preset の作成元となる tuning
- [`strata launch`](../../launch/README.md) — 起動時に tuning preset が使われる文脈

## 根拠

- `strata_cli/cli.py:486-489` — root parser への presets parser 登録。
- `strata_cli/cli.py:2151-2152` — `presets` を `presets_command` handler に委譲。
- `strata_cli/tune_commands.py:49-62` — `show` の parser 定義、位置引数、共通 `--output`（human/json、既定 human）。
- `strata_cli/tune_commands.py:95-108,289-309,344-347` — 成功出力、検索と全レコード表示、PresetError の標準エラーまたは JSON エラーと終了コード。
- `strata_control/presets.py:45-50,211-252` — 保存場所、preset の列挙・schema 判定・active 属性付加・検索、名前と ID prefix の規則。
- `strata_cli/cli.py:2217-2237`、`strata_control/private_files.py:349-389` — 起動時共通処理と Windows での user default 設定。

調査範囲は上記 commit の Terminal CLI と同 checkout 内の preset store 実装です。Release 配布物や各 OS の実行バイナリは照合していません。
