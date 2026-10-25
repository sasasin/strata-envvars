# `--interval`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--interval` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数（parser の既定値 `1.0`、実行時の通常受理範囲は 0.5～30） |

## 役割

対話型ターミナル Monitor がテレメトリを再取得する周期を秒単位で指定します。`strata monitor` の parser にのみ属します。同じ名前の `strata logs --interval` は別 parser・別既定値のオプションです（`strata_cli/monitor_commands.py:49-69`）。

## 使い方

```sh
strata monitor --interval 2.5
```

## 値と既定値

- `argparse` の `type=float` で解釈し、省略時は `1.0` 秒です（`strata_cli/monitor_commands.py:49-60`）。
- Monitor の実行経路では `a.interval < 0.5` または `a.interval > 30` を検査し、範囲外なら終了コード 2 でエラーにします（`strata_cli/monitor_commands.py:189-190`）。端点の `0.5` と `30` は条件上受理されます。
- 数値に変換できない値は `argparse` が拒否します。重複指定の特別な処理はなく、通常の `argparse` の単一値引数として最後に指定した値が残ります。
- ソースの範囲検査は NaN を明示的には拒否しません（NaN との大小比較はどちらも真にならないため）。その値が対話 UI のタイマーでどう扱われるかは Strata ソースだけでは確認できません。

## 実行時の動作

対話 Monitor の起動時に `MonitorApp` へ値を渡し、`on_mount()` が `set_interval(self.interval, self._schedule_poll)` を登録します。poll 周期ごとに非同期 poll を開始し、`Endpoint.snapshot()` からサーバーのテレメトリを取得します（`strata_cli/monitor_commands.py:214-229`; `strata_cli/monitor.py:108-123,158-165,258-280`; `strata_cli/client.py:101-144`）。ネットワーク要求には別設定の endpoint timeout が使われ、`--interval` は要求 timeout ではありません（`strata_cli/client.py:84-95,107-125`）。

この値は `--once` でも同じく範囲検査されますが、one-shot 経路は `endpoint.snapshot()` を一度実行して終了するため、取得周期を設定しません（`strata_cli/monitor_commands.py:189-213`）。JSON 出力も `--once` が必要で、対話 UI は起動しません（同: `191-194`）。

## 適用条件と副作用

- 対話 Monitor では標準出力が TTY である必要があります。TTY でなければ `--once` または `strata status --json` を案内して終了コード 2 になります（`strata_cli/monitor_commands.py:193-194`）。
- 起動時に poll timer が設定されます。初期 snapshot がない場合は mount 時に最初の poll を即時要求します（`strata_cli/monitor.py:158-165`）。poll 実行中は重複起動を抑制します（同: `258-265`）。
- poll に失敗すると表示状態を stale/disconnected 等へ更新し、認証・互換性エラーでは再試行を停止、それ以外では最大30秒までの指数的な再試行待ちを設定します。この待ち時間により、指定周期より次の取得が遅れる場合があります（`strata_cli/monitor.py:284-308`）。
- Monitor は読み取り専用クライアントで、`Endpoint` は許可されたテレメトリ系 endpoint への HTTP GET を行います（`strata_cli/client.py:101-110,134-144`）。

## 出力とエラー

範囲外の値は、通常出力モードでは stderr に `strata: --interval must be 0.5–30 seconds and --requests must be 1–50` を出し、終了コード 2 を返します。JSON 系モードでは同じエラーを JSON に出力します（`strata_cli/monitor_commands.py:124-129,189-190`）。対話 poll 中の通信失敗は Monitor 内で状態・メッセージとして扱われ、初回の CLI 実行を終了させるエラー経路とは別です（`strata_cli/monitor.py:284-308`）。

## 根拠

- Parser 定義と既定値: `strata_cli/monitor_commands.py:49-60`
- 適用範囲、TTY/JSON/one-shot 分岐、Monitor への引き渡し: `strata_cli/monitor_commands.py:189-229`
- timer 設定と poll 周期の処理: `strata_cli/monitor.py:108-123,158-165,258-308`
- HTTP GET と timeout の分離: `strata_cli/client.py:84-125,134-144`
- CLI コマンド登録と dispatch: `strata_cli/cli.py:486-493,2153-2165`

調査範囲は上記 checkout のソースです。CLI `--help`、Release artifact、実際の UI timer 実装（Textual 側）は補助確認していません。
