# `strata tune report`（Strata Terminal）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune report` |
| POSIX の入口 | `terminal/bin/strata` |
| Windows の入口 | `terminal/bin/strata.cmd`、`terminal/bin/strata-direct.ps1` |
| 主な実装 | `terminal/strata_cli/cli.py`、`terminal/strata_cli/tune_commands.py`、`terminal/strata_control/tune_report.py` |

## 役割

直近の `strata tune auto` の結果から保存された説明文を読み、人向けテキストまたは JSON で表示します。説明文には基準設定の測定値、試した設定と判定、省かれた設定、その後の案内が含まれます。保存済みの文章を読む処理であり、測定をやり直したり、プリセットや実行設定を変更したりはしません（`terminal/strata_cli/tune_commands.py:230-237`、`terminal/strata_control/tune_report.py:1-4,58-84`）。

## 基本的な使い方

```sh
# 直近の自動チューニングの説明を人向けに表示する
strata tune report

# スクリプトなどから扱うため JSON で表示する
strata tune report --output json

# 人向け形式を明示して表示する（省略時と同じ）
strata tune report --output human
```

このコマンド自体は読み取り専用です。`strata tune auto` をまだ実行していない場合、または保存済みレポートを読めない場合は、「No tune has been run yet.」と表示します。JSON 形式では同じ状態が `report: null` になります（`terminal/strata_cli/tune_commands.py:230-237`、`terminal/strata_control/tune_report.py:12-13,105-109`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 人向け（既定） | `strata tune report` | 保存されたレポートをそのまま標準出力へ出す。レポートがない、または読み出せない場合は「No tune has been run yet.」を出す。 |
| JSON | `strata tune report --output json` | `schema_version: 1`、`ok: true`、`report` を含む JSON オブジェクトを標準出力へ出す。レポートを読み出せない場合の `report` は `null`。 |

## 主な動作

1. `strata tune report` の parser は `--output` に `human` または `json` を受け付け、既定値を `human` にします（`terminal/strata_cli/tune_commands.py:51-52`）。
2. コマンド分岐から `tune_commands.report()` が呼ばれ、`tune_report.read()` で保存済みレポートを読み込みます（`terminal/strata_cli/cli.py:1722-1726`、`terminal/strata_cli/tune_commands.py:230-233`）。
3. 保存先はプリセットフォルダー内の `last-tune-report.txt` です。`STRATA_PRESET_DIR` が設定されていればそのディレクトリを使い、未設定ならプロファイルディレクトリの親にある `presets/` を使います（`terminal/strata_control/tune_report.py:12,87-90`、`terminal/strata_control/presets.py:45-50`）。
4. 人向け表示ではファイル内容を標準出力へ出します。JSON 表示ではレポート文字列を JSON に包んで標準出力へ出します。どちらも終了コードは `0` です（`terminal/strata_cli/tune_commands.py:101-106,230-237`）。
5. 自動チューニング側は結果から説明文を組み立て、毎回同じ保存先へ保存します。保存に失敗した場合はその失敗を無視し、チューニング結果の表示には保存案内を付けません（`terminal/strata_cli/tune_commands.py:417-425`、`terminal/strata_control/tune_report.py:92-102`）。

保存先が存在しない、読み取り権限がないなど `OSError` が起きると `read()` は `None` を返します。この場合も「レポート未実行時」と同じ表示になり、読み取り失敗そのものは区別されません（`terminal/strata_control/tune_report.py:105-109`）。

## オプションの文書

このコマンドの `--output` の仕様は索引 [`docs/cli/README.md`](../../../README.md) にあるリンク先を参照してください。

## 根拠

- `terminal/strata_cli/tune_commands.py:51-52` — `report` サブコマンドと `--output` の値・既定値。
- `terminal/strata_cli/cli.py:1722-1726` — `tune report` から処理関数への振り分け。
- `terminal/strata_cli/tune_commands.py:101-114,230-237` — 標準出力、JSON 包装、人向けの未取得時表示、終了コード。
- `terminal/strata_cli/tune_commands.py:417-425` — 自動チューニング完了時のレポート生成・保存と保存失敗時の扱い。
- `terminal/strata_control/tune_report.py:1-4,12-15,58-109` — レポートの内容、ファイル名、保存・読込動作。
- `terminal/strata_control/presets.py:45-64` — 保存先ディレクトリと原子的なファイル置換。
- `terminal/bin/strata:104-114,147`、`terminal/bin/strata.cmd:3-14,43`、`terminal/bin/strata-direct.ps1:1-15`、`terminal/strata.py:59-63` — POSIX / Windows の入口から Python CLI への委譲。
