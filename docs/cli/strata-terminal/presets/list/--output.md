# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets list` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

保存済み tuning preset の一覧を、人が読む行形式か機械処理向け JSON で標準出力へ出します。対象コマンドは `strata presets list` です（`strata_cli/tune_commands.py:49-58`）。

## 使い方

```sh
strata presets list --output json
```

人向けの表示は既定なので、通常は `strata presets list` と実行します。

## 値と既定値

`--output` は必須の値引数で、受理値は `human` と `json` のみ、既定値は `human` です。別名や `--json` alias はこの parser に定義されていません（`strata_cli/tune_commands.py:53-58`）。`--model` を複数回指定した場合の扱いを特別に上書きするコードはなく、argparse が最後に解析した値が使われます。

`--model TEXT` を併用すると、preset の `choices` を JSON 化した文字列に `TEXT` が大文字・小文字を区別せず含まれる項目だけが一覧に残ります。`--model` 自体に型変換や内容 validation はありません。空文字列は絞り込み条件として評価されず、全件が対象になります（`strata_cli/tune_commands.py:57-58`; `strata_control/presets.py:234-252`）。

## 実行時の動作

- `human` では preset ごとに active 印、ID の先頭 8 文字、名前、測定 gain（整数パーセント表示）、answer class を1行に出します。0件なら `No saved presets yet. Run: strata tune auto <profile>` と表示します（`strata_cli/tune_commands.py:295-300`）。
- `json` では標準出力に1行の JSON を出します。成功 payload は `schema_version: 1`、`ok: true`、`presets` を含み、各項目は `_summary` が作る ID、名前、active 状態、作成時刻、choices、settings、answers、notice、測定値などです（`strata_cli/tune_commands.py:95-100, 295-300, 351-358`）。
- 一覧は preset 保存ディレクトリの `*.json` から読みます。`STRATA_PRESET_DIR` が設定されていればその展開後パス、なければ profile ディレクトリの隣にある `presets` が使われます。`active.json` は一覧項目ではなく active ID の索引として読まれます（`strata_control/presets.py:45-50, 202-205, 234-252`）。
- ディレクトリが存在しない場合は空一覧です。`active.json` または個々の preset ファイルが読み込み不能・不正 JSON の場合、読み取り helper は既定値を返し、active 情報が空になったり当該 preset がスキップされたりします。schema が `strata.preset/1` ではない JSON もスキップされます（`strata_control/presets.py:71-75, 202-205, 234-252`）。

## 適用条件と副作用

このコマンドは preset 一覧と active 索引を読み取るだけで、エンジン起動や preset の変更を行いません。active preset の判定は `active.json` に記録された ID と各 preset の ID の照合です（`strata_control/presets.py:234-252`）。一覧処理自体は他のオプションとの特別な相互作用を持ちません。`--model` は出力対象だけを絞ります。

## 出力とエラー

`--output` に値がない、または `human` / `json` 以外の値を指定した場合は argparse の引数エラーとなり、usage とエラーが標準エラーに出て終了コード 2 になります。未知の引数も `strata_cli/cli.py:2223-2231` の parser 経路で拒否されます。

通常の一覧成功時は終了コード 0 です。preset 操作層から `PresetError` が上がった場合はコード 5、`OSError` または `ValueError` の場合は原則コード 2 で失敗します。human モードでは `strata: <message>` を標準エラーに出し、JSON モードでは `schema_version: 1`、`ok: false`、`error.code` と `error.message` の JSON を標準出力に出します（`strata_cli/tune_commands.py:103-108, 289-300, 344-347`）。ただし一覧内の個別 JSON 読み取りエラーは読み取り helper により既定値へ置き換えられるため、必ずしもコマンド失敗にはなりません（`strata_control/presets.py:71-75, 234-252`）。

## 根拠

- parser と値・既定値・隣接する `--model`: `strata_cli/tune_commands.py:49-58`
- 出力形式、一覧実行、失敗処理: `strata_cli/tune_commands.py:95-108, 289-300, 344-358`
- CLI のトップレベル登録と実行委譲: `strata_cli/cli.py:40-45, 486-489, 2151-2152`
- preset 保存先、active 索引、一覧の読み取り・絞り込み・整列: `strata_control/presets.py:45-50, 71-75, 202-205, 234-252`
- 索引上のコマンド階層と予定リンク: `docs/cli/README.md:826-838`

同一 revision の既存 CLI `--help` は実行せず、parser 定義を主根拠として確認しました。Release 配布物での挙動はこの調査では確認していません。
