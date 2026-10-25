# `strata runtime status`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime status` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/management.py`、`strata_control/runtime.py` |

## 役割

保存済み profile 名を指定し、その profile 名に対応するローカルの owner-managed runtime の状態を一度表示します。`runtime start` が起動するバックグラウンド server を調べるためのコマンドです。foreground server を起動する `strata serve` や、任意の URL の server を調べる `strata status` とは別のコマンドです。

## 使い方

```sh
# 人間向け表示
strata runtime status --profile four-gpu

# JSON 表示（--json も --output json の alias）
strata runtime status --profile four-gpu --output json
```

`--profile` は必須です。例の `four-gpu` は profile ID の例で、実際には利用者の環境にある名前を指定します。

## 実行時の動作

- parser は `runtime status` に `--profile`、`--output {human,json}`（既定値 `human`）を登録します。one-shot parser 共通処理で `--json` と `--quiet` も追加されます。
- profile 名は `[a-z][a-z0-9_-]{0,63}` の形式で検査されます。status 経路では profile 設定を読み込まず、該当する runtime 状態ファイルを調べます。状態ファイルがなければ `stopped` を成功として返します。
- owner host の lease が有効なら、ローカルの認証済み control channel に `status` を問い合わせます。host は子 server の生存状態、ready file、直近の probe 結果などから `stopped`、`starting`、`ready`、`failed` 等の状態を返します。
- ready file に一致する子 server があり、その instance の probe がまだ始まっていない場合、host はバックグラウンドで readiness probe を始めます。probe はローカル `/v1/telemetry` で instance・model・launch attestation を照合し、model が load 済みなら固定の短い prompt で最大1 token の生成を要求します。model が unloaded の場合は生成せず、`unloaded` として報告します。
- `--output json` または `--json` は schema version 1 の JSON を stdout に出します。人間向け出力は profile 名、state、あれば instance ID・API URL・error を一行で表示します。`--quiet` は成功時の人間向け表示を抑制します。

## 適用条件と副作用

- このコマンドは指定 profile 名のローカル managed runtime を対象にします。profile 名の形式だけを検査し、保存済み profile の存在確認は行いません。そのため、形式が有効で状態ファイルがない名前も `stopped` と表示されます。
- `runtime.status()` が状態パスを解決すると `runtime_dir()` を通ります。状態ディレクトリが未作成なら private directory として作成されます。既存の状態ファイルは owner-only 性、形式、profile 名、control address、token の形を検査してから利用します。
- `status` は停止・再起動・stale state の回収を行いません。owner host の lease が失われた状態ファイルを見つけた場合は `stale` と `owner_host_lost` を返し、次の `runtime start` による回復を案内します。
- status は連続的な server liveness monitor ではありません。起動・明示的な verify による readiness 情報を返します。一方、上記の初回 readiness probe はローカル API への読み取りと、load 済み model に対する1 token 生成を伴い得ます。API monitor が有効なら、その固定 probe request が他の inference request と同様に記録される場合があります。
- サポート外 platform、非 private または不正な runtime state、owner host への接続失敗などでは status を得られず、エラーになります。`STRATA_RUNTIME_DIR` を使う場合は絶対パスが必要で、runtime directory は owner-only である必要があります。

## 出力とエラー

- 通常の成功（状態ファイルなしを含む）は終了コード `0` です。JSON の成功出力は `schema_version: 1` と runtime の状態情報を含みます。
- stale state は `ok: false`、`state: stale`、`exit_code: 6` を含み、CLI も `6` で終了します。active host の failed 状態では `ok: false` と error を表示し、CLI は返却された `exit_code` を終了値に使います。子 server の終了を報告する経路ではそのプロセス終了値が `exit_code` になるため、`ok: false` でも終了値が必ず非 0 とは限りません。
- 制御 channel が使えない・応答しない場合はエラー（runtime の実装では通常 `3`、応答待ち timeout は `8`）になります。非 JSON 表示時は CLI が `strata: ...` を stderr に出します。JSON 表示時の例外エラーは `schema_version` と `error.code` / `error.message` を持つ JSON です。
- `--quiet` で人間向け表示を抑止している場合でも、失敗時は捕捉済みの出力が stderr に返されます。

## 関連文書

- [runtime コマンド概要](../README.md)
- [runtime start](../start/README.md)、[runtime verify](../verify/README.md)、[runtime stop](../stop/README.md)、[runtime cleanup](../cleanup/README.md)
- オプション: [`--profile`](--profile.md)、[`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)
- [CLI 文書索引](../../../README.md)

## 根拠

- `strata_cli/cli.py:197-215,508-516` — runtime hierarchy、status parser、one-shot parser への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:1331-1373,2119-2165,2166-2183` — runtime status の dispatch、human/JSON 出力、終了コードと例外出力。
- `strata_control/management.py:188-201,231-234` — profile ID の確認と status action の委譲。status は profile 設定をロードせず `runtime.status()` を呼ぶ。
- `strata_control/profiles.py:25-25` — profile ID の形式。
- `strata_control/runtime.py:95-129,205-235` — profile ID 検査、runtime directory の作成と private check、state file の検証。
- `strata_control/runtime.py:402-455` — control RPC と、state 不在・host lease 消失・active host の status 分岐。
- `strata_control/runtime.py:933-976,1166-1172` — host が報告する runtime 状態と、初回 readiness probe の開始。
- `strata_control/readiness.py:84-142` — telemetry/attestation 照合、unloaded の扱い、最大1 token の probe。
- `docs/TERMINAL.md:94` — status が直近の startup / explicit verify に基づくこと、stale 状態の利用者向け説明。

調査制約: この文書は指定 commit の source checkout と同 checkout の利用者向け文書を根拠にしています。別 platform 上の実行結果や Release artifact は照合していません。
