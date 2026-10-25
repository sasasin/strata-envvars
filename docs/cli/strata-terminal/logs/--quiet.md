# `strata logs --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽値 flag。省略時 `false`、指定時 `true` |

## 役割

人間向け出力の進行案内を抑える。取得したリクエスト活動行まで隠すオプションではない。コマンドは読み取り専用の telemetry snapshot から、redacted な request activity を表示する。

## 使い方

```sh
strata logs --quiet
strata logs --follow --interval 5 --quiet
```

1つ目は直近の活動を一度取得し、2つ目は5秒間隔で follow する。どちらも `--source runtime` が既定値である。`--quiet` 自体には引数がなく、`--quiet=false` のような値指定は parser の定義にない。

## 値と既定値

`argparse` の `action="store_true"` で宣言され、明示指定が `true`、省略時が `false`。短縮 alias、選択肢、追加の値 validation はない。`logs` 用 parser は共通の接続引数に加えて `--source`、`--follow`、`--interval`、`--output`、`--json` を登録する（`strata_cli/monitor_commands.py:20-25,63-73`）。

## 実行時の動作

- `--output human`（既定）で `--quiet` を付けると、one-shot の見出し `Recent request activity ...` と、イベントがない場合の `No request transitions retained` を表示しない。保持されている活動行は引き続き標準出力へ出る（`strata_cli/logs.py:110-124`）。
- `--follow --output human` では、follow 開始案内を出さず、活動行・sequence gap・serving instance の変更通知は出す。接続失敗時の初回 retry 通知と接続回復通知（標準エラー）も抑える。3回連続で接続に失敗すると `ClientError` を送出するため、最終エラーは抑制されない。Ctrl+C による follow の中断は終了コード `0`（`strata_cli/logs.py:125-151`、`strata_cli/monitor_commands.py:241-244`）。
- `--output json`、`--output jsonl`、または `--json` を使う場合は machine 出力扱いとなり、quiet は無効。JSON/JSONL のレコードを抑制せず出力する。`--json` は one-shot 専用で、follow とは併用できない。follow の machine 出力には `--output jsonl` を使う（`strata_cli/monitor_commands.py:167-185`、`strata_cli/logs.py:14-23,110-123`）。
- `strata` の共通 CLI dispatcher は `status`、`monitor`、`logs` を静音出力の stdout capture 対象から除外し、`logs` に quiet の状態を直接渡す（`strata_cli/cli.py:2232-2248`、`strata_cli/monitor_commands.py:200-202`）。したがって、活動レコードを含む通常出力を全体として捨てる挙動ではない。

## 適用条件と副作用

この flag は `strata logs` の parser にのみ登録されている。flag 自体はローカル状態を変更しない。`logs` はサーバーに snapshot を問い合わせ、follow 時は interval ごとに再問い合わせする。remote URL は接続解決・HTTP クライアント側の制約に従い、snapshot は `/v1/telemetry` を優先し、未対応時に旧 endpoint へ fallback する（`strata_cli/monitor_commands.py:63-73,195-202`、`strata_cli/client.py:101-152`）。

`--quiet` は `--source harness` を有効化しない。この checkout では harness source は利用不可としてエラー終了し、`--source runtime` の利用を案内する（`strata_cli/monitor_commands.py:176-188`）。activity が利用できないサーバー、instance ID がない follow、または不正な sequence もエラーになる（`strata_cli/logs.py:25-40,105-109,125-126`）。サーバー上の activity は有界な redacted telemetry であり、永続 raw log ではない（補助資料: `docs/TERMINAL.md:244`）。

## 出力とエラー

quiet が抑えるのは human の進行・状態案内であり、失敗を隠さない。human エラーは `strata: ...` と標準エラーに出て、エラーコードを終了コードとして返す。machine 出力時は `{schema_version: 1, ok: false, error: ...}` 形式の JSON を標準出力へ出す（`strata_cli/monitor_commands.py:124-129,167-188,231-244`）。確認できる例として、interval が `0.5`〜`30` 秒の範囲外ならコード `2`、harness source はコード `5`。接続・サーバー・activity の詳細に応じた失敗コードは各 `ClientError` による（`strata_cli/monitor_commands.py:176-188`、`strata_cli/logs.py:25-40,105-126`）。

## 根拠

- 索引の command scope: `docs/cli/README.md:1019-1033`（`strata logs` 配下の予定リンクに `--quiet` を掲載）。
- parser 定義: `strata_cli/monitor_commands.py:63-73`。
- flag の machine/human 判定、validation、dispatch、標準エラー処理: `strata_cli/monitor_commands.py:124-129,167-202,231-244`。
- quiet による抑制と残る出力: `strata_cli/logs.py:14-23,101-151`。
- telemetry HTTP と fallback: `strata_cli/client.py:101-152`。
- 利用者向け説明との照合: `docs/TERMINAL.md:244`。
