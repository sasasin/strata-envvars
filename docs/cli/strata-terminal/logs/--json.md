# `strata logs --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata logs` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。省略時 `false` |

## 役割

保持されているリクエスト活動のスナップショットを JSON で出力します。`--output json` の別表記で、`--follow` を使わない一回取得向けです。対象の活動データはサーバーから読み取るものであり、このフラグ自体は設定やサーバー状態を変更しません。

## 使い方

```sh
strata logs --json
```

接続先は通常の `strata logs` と同じ解決規則を使います。例として URL を指定する場合:

```sh
strata logs --url https://strata.example --json
```

## 値と既定値

`--json` は `argparse` の `store_true` で、引数値を受け取りません。指定しなければ無効です。`strata logs` の `--output` は `human`、`json`、`jsonl` のいずれかで、既定値は `human` です。実行時に `--json` が有効なら、互換性検査を通った後 `output` を `json` に設定します (`strata_cli/monitor_commands.py:63-72`, `strata_cli/monitor_commands.py:167-186`)。

## 実行時の動作

`--json` が指定されると、ログ取得関数は機械可読モードになります。成功時は標準出力へ一行の JSON オブジェクトを出します。キーは `schema_version: 1`、`ok: true`、`source: "runtime_activity"`、`instance_id`、`last_seq`、`retained`、`events` です。`retained` は応答に含まれる保持イベント数で、`events` はサーバーの活動イベントです。JSON は Unicode をそのまま出力し、非有限数を許可しません (`strata_cli/logs.py:101-124`)。

このモードではスナップショットを一度取得して終了します。`--quiet` は人間向けの進捗・見出しを抑えるための指定ですが、JSON モードでは人間向け出力を行わないため追加の効果はありません (`strata_cli/monitor_commands.py:167-169`, `strata_cli/logs.py:110-124`)。

接続先の解決や認証方法を `--json` が変更することはありません。CLI は必要に応じて `Endpoint.snapshot()` を呼び、`/v1/telemetry` を優先して取得します。同エンドポイントが 404 の場合は `/metrics` と `/v1/status` へフォールバックします (`strata_cli/monitor_commands.py:195-202`, `strata_cli/client.py:134-152`)。

## 適用条件と副作用

- `--follow` と同時に指定すると拒否されます。追従出力には `--follow --output jsonl` を使います。`--json` と `--output jsonl` の併用も拒否されます (`strata_cli/monitor_commands.py:179-185`)。
- `--output jsonl` は `--follow` がなければ拒否されます。`--follow --output json` も拒否され、追従時は `human` または `jsonl` が必要です (`strata_cli/monitor_commands.py:183-186`)。
- `--interval` は追従時のポーリング間隔で、既定値は 2 秒、受理範囲は 0.5〜30 秒です。範囲検査は `--json` の処理より先に行われるため、一回取得でも範囲外の値はエラーになります (`strata_cli/monitor_commands.py:67-72`, `strata_cli/monitor_commands.py:176-186`)。
- `--source harness` は現在エラーになり、`--source runtime` を使うよう案内されます (`strata_cli/monitor_commands.py:66`, `strata_cli/monitor_commands.py:187-188`)。
- 取得する活動履歴はサーバーが保持している最大32件の範囲です。永続ログ全体を読む機能ではありません (`strata_cli/client.py:244-268`, `strata_cli/logs.py:110-124`)。
- サーバーとの読み取り専用通信を行います。接続 URL、保存済み接続、認証環境変数の選択規則はこのオプションでは変化しません (`strata_cli/monitor_commands.py:20-26`, `strata_cli/monitor_commands.py:195-202`)。

## 出力とエラー

JSON モードでは、CLI が捕捉するエラーも標準出力に JSON オブジェクト (`schema_version: 1`, `ok: false`, `error.code`, `error.message`) で出力されます。人間向けモードでは同じエラー文を標準エラーに `strata:` 接頭辞付きで出します (`strata_cli/monitor_commands.py:124-129`, `strata_cli/monitor_commands.py:167-169`, `strata_cli/monitor_commands.py:231-244`)。

`--follow` との矛盾や `--interval` の範囲外は終了コード 2、`--source harness` は 5 です。活動データがサーバーで利用できない場合も `ClientError` のコード 5 になります (`strata_cli/monitor_commands.py:176-188`, `strata_cli/logs.py:105-108`)。認証・権限エラーはコード 4、その他の通信エラーは既定のコード 3 です (`strata_cli/client.py:38-42`, `strata_cli/client.py:117-125`)。通信先、HTTP 応答、サーバー実装ごとの詳細な失敗条件はこのオプション単独では確定できません。

## 根拠

- `strata_cli/monitor_commands.py:63-72` — `logs` parser、`--json` 宣言、既定値と関連引数。
- `strata_cli/monitor_commands.py:124-129` — 機械可読エラーと人間向けエラーの出力先。
- `strata_cli/monitor_commands.py:167-202` — JSON モード判定、併用条件、接続解決、ログ処理への引き渡し。
- `strata_cli/monitor_commands.py:231-244` — 例外から終了コードへの変換。
- `strata_cli/logs.py:101-124` — 一回取得 JSON の内容と標準出力への出力。
- `strata_cli/client.py:101-132`, `strata_cli/client.py:134-152` — 読み取り専用 telemetry 通信と snapshot の取得・フォールバック。
- `strata_cli/client.py:244-268` — 活動イベントの最大32件への制限・正規化。
