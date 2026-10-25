# `--color`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--color` |
| 別名 | なし |
| 値 | `auto`、`always`、`never` のいずれか |

## 役割

対話型ターミナルモニターの色スタイルを指定します。色の有効・無効はテーマと組み合わせて、画面背景・文字色、見出し、状態表示、パネル等のスタイルに反映されます。

## 使い方

```sh
strata monitor --color never
```

この例では、通常の接続設定でサーバーに接続して対話モニターを開き、色を使わないよう指定します。接続先を明示する場合は `strata monitor --url http://127.0.0.1:8080 --color always` のように指定できます。

## 値と既定値

- 受理値は `auto`、`always`、`never`。省略時は `auto` です。値は `argparse` の `choices` で検証されます（`strata_cli/monitor_commands.py:49-60`）。
- モニターの色判定では `auto` と `always` はどちらも色有効として扱われ、`never` のみ無効になります（`strata_cli/monitor.py:138-140, 173-179, 200-212, 232-245`）。この実装箇所では `auto` を端末能力に応じて別途判定していません。
- 環境変数 `NO_COLOR` が存在すると、その値が空文字でも `--color` の指定値にかかわらず `never` に置き換わります。したがって `--color always` でも色は無効です（`strata_cli/monitor.py:138-140`）。
- `--color` に未定義の値を指定すると parser が拒否します。無効値時の `argparse` の usage/error 表示と終了は CLI parser によるもので、`strata_cli/monitor_commands.py:57` が選択肢を定義しています。

## 実行時の動作

`strata monitor` の parser が値を受け取り、対話モニターの生成時に `theme`、`color`、`glyphs` とともに `MonitorApp` または `LaunchMonitor` に渡します（`strata_cli/monitor_commands.py:222-229`）。`MonitorApp` は `NO_COLOR` を反映した選択値を保存し、`never` の場合は背景とパネルを透明、文字色を端末既定色にします（`strata_cli/monitor.py:138-140, 167-179`）。

描画時には色有効フラグを Overview、標準幅 Dashboard、詳細 Dashboard に渡します。これらの描画経路では色を無効にするとアクセント等を `default` にし、色有効時はテーマに応じた色スタイルを付けます（`strata_cli/monitor.py:198-230`; `strata_cli/overview.py:302-315`; `strata_cli/dashboard.py:529-537, 743-755`）。小さい画面のテキスト表示でも、`never` の場合は色のスタイル付けを行いません（`strata_cli/monitor.py:223-247`）。`strata launch` が開くモニターの Connect 画面も同じ選択値を使い、色無効時または `--theme terminal` 時には専用パレットを使いません（`strata_cli/launch/monitor_ext.py:32-36, 213-221, 246-266`）。

## 適用条件と副作用

- 色指定が使われるのは対話 TUI の起動経路です。`--once` はスナップショットを取得し、JSON なら JSON、human なら `render_view` のテキストを出力して終了します。この分岐では `a.color` は描画関数に渡されず、色指定は出力に作用しません（`strata_cli/monitor_commands.py:203-213`）。
- JSON 出力（`--json` または `--output json`）は `--once` と併用しないとエラーになり、対話モードでは使用できません（`strata_cli/monitor_commands.py:191-192`）。
- `--once` なしで標準出力が TTY でなければ、対話モニターは起動せずエラーになります（`strata_cli/monitor_commands.py:193-194`）。
- このオプションはモニターの表示スタイルを制御します。サーバーの状態や設定を変更する処理には渡されません（parser から UI 生成への受け渡し: `strata_cli/monitor_commands.py:222-229`）。

## 出力とエラー

`--color` 自体に固有の成功メッセージや警告出力はありません。選択肢外の値は parser の引数エラーになります。対話 TUI の前提条件に反する場合は、通常の CLI エラー経路で stderr に `strata: ...` を表示し、該当する終了コードを返します。JSON モードが指定されていればエラーを JSON として stdout に出力します（`strata_cli/monitor_commands.py:124-129, 191-194`）。

## 根拠

- parser 定義・既定値・選択値: `strata_cli/monitor_commands.py:49-60`
- 対話 UI への値の転送、JSON/TTY 条件: `strata_cli/monitor_commands.py:189-229`
- `NO_COLOR` の優先とテーマへの反映: `strata_cli/monitor.py:138-179`
- 表示サイズごとの色有効フラグの使用: `strata_cli/monitor.py:198-247`
- Overview と Dashboard の色スタイル: `strata_cli/overview.py:302-315`, `strata_cli/dashboard.py:529-537, 743-755`
- launch の Connect 画面でのパレット条件: `strata_cli/launch/monitor_ext.py:32-36, 213-221, 246-266`
- 補助資料（同一 checkout の利用者向け説明）: `docs/TERMINAL.md:238`。本記述は parser と実際の値処理を優先して整理しています。CLI `--help` は実行していません。
