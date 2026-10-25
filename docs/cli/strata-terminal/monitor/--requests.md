# `strata monitor --requests`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--requests` |
| 別名 | なし |
| 値 | 整数。1〜50 |

## 役割

インタラクティブな Terminal Monitor のリクエスト表示で、表示・選択対象にする実行中リクエストと完了済みリクエストの各最大件数を指定します。サーバー側の同時実行数や保存件数を変更するオプションではありません。

## 使い方

```sh
strata monitor --requests 20
```

対話モードでは端末が必要です。サーバー接続先は `--url`、`--connection`、環境設定、または自動検出から解決されます。`--requests` は `strata monitor` のオプションです。

## 値と既定値

- 値は `int` で解析され、省略時は `12` です。
- 実行時検査で `1 <= N <= 50` が必要です。範囲外なら終了コード2で拒否されます。
- 整数として解析できない値は `argparse` が引数エラーとして拒否します。
- 同じオプションを複数回指定した場合の特別な処理はありません。`argparse` の通常の単一値引数として最後に解析された値が使われます。

## 実行時の動作

`strata monitor` の parser は `--requests` を `type=int, default=12` として登録します。検査を通過すると、値は通常の `MonitorApp` または `LaunchMonitor` に渡され、Monitor の共通状態に保持されます。

Monitor の snapshot ベースの描画・選択経路では、実行中リクエスト (`work.requests`) と完了済みリクエスト (`recent`) をそれぞれ先頭 N 件に切り詰めます。したがって N 件は両カテゴリを合算した総数ではありません。リクエスト画面ではこの上限内の行が一覧と選択対象になります。

この指定はサーバーへの取得件数指定ではなく、snapshot を取得した後のクライアント側表示制限です。`--once` の human/JSON 出力は `MonitorApp` を起動せず snapshot を直接描画・出力するため、`--requests` による行数制限を適用しません（ただし範囲検査は行われます）。

横幅・高さを満たし、新しいサーバーの `/metrics` から作った Overview を描画する経路では、Overview は別の `metrics_model` を使います。この表示の完了済みリクエスト数は画面高に応じて最大6件で、`--requests` の N では制限されません。snapshot ベースの他のリクエスト表示では N が適用されます。

## 適用条件と副作用

- `--requests` はインタラクティブ Monitor の表示設定です。HTTP snapshot の取得自体、サーバーの処理、またはログ・テレメトリの保存内容を変えません。
- `strata monitor --once` でもオプションは受理され、1〜50の検査対象になりますが、出力される snapshot の配列をこの値で切り詰めません。
- Monitor は read-only の接続クライアントです。標準出力が端末でない状態で `--once` を付けず起動すると拒否されます。
- Portable Monitor bundle では launch 用拡張がない場合に通常の `MonitorApp` を使います。`strata monitor` では `LaunchMonitor` を使いますが、いずれも同じ基底 Monitor に値を渡します。

## 出力とエラー

- N が1〜50の範囲外の場合、通常出力では標準エラーに `strata: --interval must be 0.5–30 seconds and --requests must be 1–50` を出し、終了コード2を返します。`--output json` または `--json` が有効なら、エラーを `ok: false` と終了コードを含む JSON オブジェクトで標準出力に出します。
- `--json` または `--output json` を `--once` なしで使うと、終了コード2で「JSON monitor output requires --once; interactive monitor uses a terminal」として拒否されます。
- 非端末で `--once` なしの場合は終了コード2で、`--once` または `strata status --json` を案内します。
- 接続/API エラーは `ClientError` のメッセージとその終了コードで報告されます。Monitor 内の後続ポーリング失敗は既存画面上の状態表示・再試行として処理されます。

## 根拠

- `strata_cli/monitor_commands.py:49-60` — `strata monitor` の parser 登録、`--requests` の整数型と既定値。
- `strata_cli/monitor_commands.py:167-194` — 値域検査、JSON と端末の条件、エラー文・終了コード。
- `strata_cli/monitor_commands.py:203-229` — `--once` の snapshot 経路と、対話時に Monitor へ値を渡す箇所。
- `strata_cli/monitor.py:108-124,190-212,478-487` — 値の保持、snapshot ベース描画での切り詰め、選択対象。
- `strata_cli/render.py:189-199,644-665` — 実行中・完了済み行それぞれの上限適用と Requests view の描画。
- `strata_cli/monitor.py:267-320` — snapshot polling と `/metrics` の別取得経路。
- `strata_cli/overview.py:85-93,423-432` — Overview 用 `/metrics` データの構築と、画面高で決まる最大6行。
- `strata_cli/client.py:134-152,361-389` — snapshot API の取得・互換 fallback、およびクライアント側の安全化で最大50件まで受理する処理。
- `strata_cli/cli.py:488-493,2119-2165` — monitor parser の登録と共通 monitor runner への dispatch。

## 調査範囲

Strata checkout は `git rev-parse HEAD` で上記 commit を確認し、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）でした。実機サーバー、各リリース配布物、すべての端末サイズでの表示は実行確認していません。説明は記載した revision の parser とソース経路に基づきます。
