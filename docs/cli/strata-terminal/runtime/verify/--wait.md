# `strata runtime verify --wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。`float` として解析され、実行時に有限値 `1..600` であることを検証 |

## 役割

所有中のローカル runtime に対する API・起動情報の照合と、必要に応じた1トークン生成確認に使う待ち時間（秒）です。CLI parser の既定値は `300` 秒です（`strata_cli/cli.py:216-225`）。

## 使い方

```sh
strata runtime verify --profile default --wait 45
```

`--profile` は必須です。モデルが未ロードの場合に生成確認のためロードさせるには `--load` を併用します（`strata_cli/cli.py:216-225`）。

## 値と既定値

- 値は `argparse` の `float` 変換で受け取ります。省略時は `300` 秒です（`strata_cli/cli.py:216-218`）。
- 実行時は有限の数値かつ `1..600` 秒（両端を含む）であることが必要です。ゼロ、範囲外、NaN、無限大は拒否されます（`strata_control/management.py:113-117,255`）。
- parser は重複指定を禁止していません。`argparse` の通常動作では最後に指定した値が使われます。
- `--plan` の経路では `wait` 検証・利用をせず、現在の状態と検証予定を返します（`strata_control/management.py:239-255`）。

## 実行時の動作

CLI は値を `management.runtime_action(..., wait=...)` に渡し、通常の `verify` 実行では範囲検証後、操作記録に `wait_s` を含めて `runtime.verify(timeout=wait, ...)` を呼び出します（`strata_cli/cli.py:1345-1356`、`strata_control/management.py:255-270`）。runtime 側でも `1..600` 秒と `load` の真偽値を検証し、RPC の応答タイムアウトには指定秒数に5秒を加えます（`strata_control/runtime.py:687-699`）。

所有 runtime 側では、この値から readiness probe の期限を作ります。probe はテレメトリ API で instance ID・launch attestation・model ID を照合し、モデルがロード済みか `--load` 指定時には1トークン生成 API を試します。生成要求が HTTP 409、429、503 で失敗した場合は、期限まで0.25秒間隔で再試行します（`strata_control/readiness.py:84-120,123-132`）。このオプション自体がプロセス起動や終了を指示するものではありません。

## 適用条件と副作用

- `--wait` が実際の probe に適用されるのは `--plan` なしの `verify` 実行です。`--plan` は状態を確認し、検証自体は実行しません（`strata_control/management.py:239-270`）。
- API 呼び出しや `--load` 時の生成要求は runtime server に送られます。未ロードのまま `--load` を付けない場合、API と instance の照合は行いますが、生成確認はせず readiness は `unloaded` になります（`strata_control/readiness.py:101-120`）。
- `--if-owner-id` と `--if-instance-id` は両方指定するか、両方省略する必要があります。指定時は現在の owner / instance と一致することを確認し、不一致なら操作を拒否します（`strata_control/management.py:256-263`、`strata_control/runtime.py:1176-1188`）。

## 出力とエラー

人間向け出力は profile、状態、instance ID、API URL、照合・readiness 状態を標準出力へ表示します。失敗時はエラーも表示し、`verify` ではエンジンログの案内を標準エラーへ追加します。終了コードは成功時 `0`、失敗時は結果の `exit_code`（未設定時 `6`）です（`strata_cli/cli.py:1357-1373`）。`--json` または `--output json` の場合は結果オブジェクトを JSON として標準出力へ出します（`strata_cli/cli.py:1359-1360`）。

値の形式・範囲エラーは `ProfileError` として拒否されます。runtime 未準備、owner / instance ID 不一致、ready file 不正、API・launch attestation・model・生成応答の不一致や probe 失敗は失敗結果（通常 `exit_code: 6`）になります（`strata_control/management.py:255-263`、`strata_control/runtime.py:1188-1205`、`strata_control/readiness.py:87-142`）。

## 根拠

- parser と `--wait` 既定値: `strata_cli/cli.py:216-225`
- option の runtime action への引き渡し、結果表示: `strata_cli/cli.py:1345-1373`
- finite 秒数 validator と verify の範囲・呼び出し: `strata_control/management.py:113-117,235-270`
- runtime verify timeout、RPC 転送: `strata_control/runtime.py:687-699`
- owner 側の検証、失敗結果: `strata_control/runtime.py:1172-1208`
- probe の期限、API照合、未ロード分岐、生成再試行: `strata_control/readiness.py:84-142`
- コマンド階層と索引リンク: `docs/cli/README.md:412-425`
