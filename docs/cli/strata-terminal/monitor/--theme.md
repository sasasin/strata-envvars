# `--theme`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--theme` |
| 別名 | なし |
| 値 | `auto`、`dark`、`light`、`terminal` のいずれか |

## 役割

対話型 Terminal Monitor の配色を選びます。`auto` は端末テーマの自動検出ではなく、起動時に `terminal` として扱われます。

## 使い方

```sh
strata monitor --theme dark
```

接続先を指定して起動する場合:

```sh
strata monitor --url http://127.0.0.1:8080 --theme light
```

## 値と既定値

- 値は `argparse` の `choices` で上記4つに限定され、既定値は `auto` です。別名は定義されていません。
- `auto` は `MonitorApp` 内で `terminal` に置換されます。端末の明暗を検出して `dark` / `light` を選ぶ処理は確認できません。
- 選択は起動時の初期テーマです。対話中は `t` キーで `terminal` → `dark` → `light` → `terminal` の順に切り替えられます。
- `--once` を指定すると TUI を起動せずスナップショットを表示するため、このテーマ値は表示に使われません。
- 未知の値は parser が受け付けず、`argparse` の usage/error 経路になります（終了コード 2）。

## 実行時の動作

`strata monitor` parser はテーマ値を `MonitorApp` または `LaunchMonitor` に渡します。対話型画面では `dark` が暗色背景・明色文字、`light` が白系背景・暗色文字、`terminal` が透明背景と ANSI の既定色を使います。選択テーマは Overview、ダッシュボード、詳細表示にも渡され、各ビューのスタイルに反映されます。

`auto` は `terminal` と同じため、端末側の背景・前景色に任せます。`t` キーでの変更は画面へ即時適用されますが、ソース上に設定の保存処理はありません。

## 適用条件と副作用

- `--theme` が使われるのは対話型 monitor の画面描画です。`--once` のスナップショット表示では `render_view` を呼び出し、テーマ引数を渡しません。
- `NO_COLOR` 環境変数が存在すると、`--color always` を指定しても色設定は `never` に強制され、背景・パネル・文字色は `terminal` 相当に戻ります。テーマ選択自体は保持され、通常ビューの light/dark 強調色などに使われます。
- `strata launch` が開く monitor も同じ `MonitorApp` のテーマ処理を使います。Connect ビューの配色も `light` / `dark` / `terminal` に追従します。
- このオプション自体が設定ファイルやサーバー状態を書き換える処理は確認できません。monitor の接続・定期取得はテーマとは別に行われます。

## 出力とエラー

- 対話型でない stdout から `--once` なしで起動すると、monitor は `interactive monitor needs a terminal; use --once or strata status --json` をエラーとして返します（終了コード 2）。
- JSON 出力を `--once` なしで要求すると `JSON monitor output requires --once; interactive monitor uses a terminal` で拒否されます（終了コード 2）。
- テーマが不正な場合は、monitor 実行前に parser が拒否します。テーマ固有の警告や fallback はありません。

## 根拠

- 索引とスコープ: [`docs/cli/README.md`](../../README.md) の `strata monitor` 項目。
- parser の値・既定値: `strata_cli/monitor_commands.py:49-60`。
- 初期値の `auto` → `terminal` 変換、`NO_COLOR` 優先、起動時適用、ビューへのテーマ受け渡し: `strata_cli/monitor.py:108-110,138-140,158-179,198-230`。
- 端末画面用の色強調: `strata_cli/monitor.py:231-245`。
- `t` によるテーマ循環: `strata_cli/monitor.py:92,396-400`。
- `--once` / JSON / TTY の条件と snapshot 表示経路: `strata_cli/monitor_commands.py:189-213`。
- 対話型 monitor へのテーマ転送、起動不能時のエラー: `strata_cli/monitor_commands.py:214-229`。
- Connect ビューのテーマ色: `strata_cli/launch/monitor_ext.py:32-36,213-221,246-255`。

調査対象 checkout は `main`（`origin/main` との追従表示）で、`git status --short --branch` は `## main...origin/main` でした。未コミット変更は確認されませんでした。ソース checkout の調査であり、Release 配布物や各端末 emulator での実際の描画差は確認していません。
