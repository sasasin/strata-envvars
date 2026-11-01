# `NO_COLOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数の挙動は対象外です。

## 役割

Strata の対話型ターミナルモニターで色付き表示を止め、端末既定色を使います。`strata monitor` の対話型 TUI と、`strata launch` が開く `LaunchMonitor` が対象です。環境変数の値の意味を解釈する処理ではなく、変数が環境に存在するかを見て色設定を決めます。

## 値と判定

| `NO_COLOR` の状態 | `MonitorApp.color_choice` |
|---|---|
| 未設定 | CLI から渡された `color` を使う。`strata monitor` の `--color` 省略時は `auto`。 |
| 空文字を含め設定あり | `never` |
| 任意の非空文字列を設定 | `never` |

判定は `os.environ.get("NO_COLOR") is not None` です。`1` など特定値との比較や文字列変換はありません。したがって空文字も「設定あり」です。`strata monitor --color` は `auto`, `always`, `never` を受け付け、既定は `auto` ですが、`NO_COLOR` が設定されるとこれらのいずれを指定しても `color_choice` は `never` になります。未設定の場合は指定値が使われます。根拠: `strata_cli/monitor.py:108-110,139`, `strata_cli/monitor_commands.py:49-58`。

## 有効になる条件

- `MonitorApp` が初期化される対話型 TUI 経路で有効です。通常の `strata monitor` は `LaunchMonitor`（`MonitorApp` の派生クラス）を起動し、portable monitor 用の fallback では `MonitorApp` を直接起動します。どちらも同じ判定を使います。根拠: `strata_cli/monitor_commands.py:214-229`, `strata_cli/launch/monitor_ext.py:39-45`。
- `strata launch` のモニターも `LaunchMonitor` を生成するため同じ判定を使います。根拠: `strata_cli/launch/app.py:419-426`。
- `strata monitor --once`（および `--once --json`）はスナップショットを直接描画して終了し、`MonitorApp` を生成しないので、この `NO_COLOR` 判定は通りません。根拠: `strata_cli/monitor_commands.py:203-213`。
- 判定に OS、GPU backend、build macro、モデル状態、他の環境変数は関与しません。値による警告・エラー・終了経路もありません。

## 実行時の詳細

`MonitorApp.__init__` が呼ばれたとき、プロセスの `os.environ` を一度確認し、その結果を `self.color_choice` に保持します。各描画ではこの値から色の使用可否を決めます。後続の poll や再描画で `NO_COLOR` を読み直すコードはなく、初期化後に環境を変更しても既存のモニターには反映されません。根拠: `strata_cli/monitor.py:108-110,139,190-247`。

`never` の場合、テーマの背景・前景を透明または `ansi_default` にし、light theme 用のクラスを無効にします。Overview、dashboard、詳細表示には `color=False` を渡し、通常ビューの文字強調処理も省きます。Connect 表示も同じ色可否を palette 選択に渡します。これらは端末表示の色・装飾の制御で、モニターの接続、収集、データ内容を変える分岐ではありません。根拠: `strata_cli/monitor.py:167-179,198-247`, `strata_cli/launch/monitor_ext.py:213-221,246-255`。

ソース内に `NO_COLOR` の参照はこの読み取り箇所一つだけです。ドキュメント `docs/TERMINAL.md:238` も `NO_COLOR` または `--color never` で端末既定色になると説明しており、実装と一致します。

## 根拠

- 読み取り、既定値と CLI 引数: `strata_cli/monitor.py:108-110,139`; `strata_cli/monitor_commands.py:49-58`
- 対話型・one-shot の分岐: `strata_cli/monitor_commands.py:203-229`
- テーマと色付き表示への適用: `strata_cli/monitor.py:167-179,198-247`; `strata_cli/launch/monitor_ext.py:39-45,213-221,246-255`
- `strata launch` からの生成: `strata_cli/launch/app.py:419-426`
- 既存ユーザー向け説明: `docs/TERMINAL.md:238`
