# `--interval`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--interval` |
| 別名 | なし |
| 値 | 秒数。浮動小数点数、0.5 以上 30 以下 |

## 役割

`--follow` で request activity を追跡するとき、次の snapshot を取得するまでの待ち時間を指定します。`strata logs` は保持された redacted request activity を読む read-only コマンドです。

## 使い方

```sh
strata logs --follow --interval 5
```

この例では follow 開始時に snapshot を取得して保持イベントを表示し、その後は各 snapshot 取得後に5秒待って次を取得します。接続先の指定を省略した場合は通常の接続解決規則が使われます。

## 値と既定値

- parser は `float` として読み取り、既定値は `2.0` 秒です。範囲の両端を含む `0.5`～`30` が有効です。
- 値は `--follow` を付けない場合にも検査されます。ただし有効な値でも one-shot 表示の取得頻度や待ち時間には使われません。
- 数値でない値は argparse の引数エラーになります。範囲外の値は終了コード 2 で拒否されます。
- 同じオプションを複数回指定した場合の独自処理はありません。argparse の通常の値設定に従います。

## 実行時の動作

`strata logs` parser は `--interval` を `float`、既定値 `2.0` で定義します。コマンド実行時には `0.5 <= interval <= 30` を確認してから、`follow`、出力形式とともに logs 処理へ渡します。したがって `--interval 0.2` は follow の有無にかかわらず拒否されます。

follow 処理は最初に snapshot を取得し、そのイベントを出力してから `time.sleep(interval)` を経て次の snapshot を取得します。以降も取得後に同じ待ち時間を挟みます。よって取得開始間隔は指定値だけでなく、snapshot 要求の所要時間も加わります。この値は保存されず、実行中の polling に使われます。

## 適用条件と副作用

- `--interval` 自体は follow の有無にかかわらず範囲検査されますが、待ち時間として作用するのは `--follow` を指定したときだけです。
- follow 中は接続先へ繰り返し snapshot 要求を送ります。ローカルにログ履歴を書き出す処理はこの値によって行われません。
- `--output jsonl` は follow と併用する必要があり、`--follow --output json` は拒否されます。`--json` は one-shot 専用です。これらは interval の範囲検査後に検証されます。
- request activity が server で利用できない場合や follow 用の serving instance ID がない場合は処理に失敗します。follow 中の接続エラーは最大3回まで再試行され、3回目で失敗します。待ち時間は再試行周期にも使われます。

## 出力とエラー

- 範囲外の場合、人向け出力では `strata: --interval must be 0.5–30 seconds` を標準エラーに出し、終了コード 2 を返します。`--output json` / `jsonl` など machine 出力ではエラー情報を JSON で標準出力に出します。
- follow 中は各 poll の間に指定秒数待ちます。人向けでは接続断と復旧を標準エラーに通知し（`--quiet` なら抑制）、3回連続の接続失敗後は `request activity connection failed after 3 attempts` で失敗します。
- follow 中の Ctrl+C は正常終了コード 0 として扱われます。

## 根拠

- `strata_cli/monitor_commands.py:63-72` — `logs` parser、既定値、型、関連オプションの定義。
- `strata_cli/monitor_commands.py:176-188` — interval の範囲検査、JSON/follow の組み合わせ、harness source の拒否。
- `strata_cli/monitor_commands.py:195-202` — 接続先解決と interval を含む logs 処理への引き渡し。
- `strata_cli/monitor_commands.py:124-129, 231-244` — エラーの出力先・終了コードと follow 中の割り込み処理。
- `strata_cli/cli.py:490-493, 2162-2165` — トップレベル CLI への logs parser 登録と monitor command への dispatch。
- `strata_cli/logs.py:101-151` — 初回 snapshot、one-shot 動作、follow loop、poll 間の sleep、接続再試行。
- `strata_cli/client.py:134-151` — snapshot の telemetry endpoint 読み取りと互換 endpoint への fallback。
