# `strata runtime verify`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/management.py`、`strata_control/runtime.py`、`strata_control/readiness.py` |

## 役割

保存済み profile で起動した Strata の管理対象ローカル server について、現在の API が期待した instance と設定に結び付いているかを再確認します。モデルがロード済みなら固定の1 token 生成も行います。`runtime status` が最後の起動または明示的な verify の結果を示すのに対し、このコマンドはその場で検査を再実行します。成功しても継続的な稼働、回答品質、性能やハードウェア構成の安定性を保証するものではありません。

## 使い方

```sh
# 保存済み profile の server を検査する（モデル未ロードなら API 身元まで確認）
strata runtime verify --profile four-gpu --wait 300 --output json

# 未ロードモデルを明示的にロードして1 token 生成まで確認する
strata runtime verify --profile four-gpu --load --wait 300 --output json

# plan で owner / instance ID を確認してから、その instance に限定して検査
strata runtime verify --profile four-gpu --plan --output json
strata runtime verify --profile four-gpu --if-owner-id OWNER_ID --if-instance-id INSTANCE_ID
```

コマンドは server を起動しません。まず `strata runtime start --profile NAME` で管理対象 instance を起動します。`--plan` は現在の ready 状態と owner / instance ID、検査内容を表示するだけで、API probe や journal 記録は行いません。

## 実行モードと動作

- 通常実行では CLI が `management.runtime_action()` を呼び、profile revision と `wait`、`load`、任意の owner / instance precondition を含む `runtime.verify` 操作を journal に記録してから owner host に依頼します。owner host は instance が ready か、ready-file の PID と instance ID が自分の child と一致するかを確認します。
- その後、ready-file の bound endpoint へローカル接続し、`/v1/telemetry` の instance ID、model ID、server が報告する launch attestation を照合します。attestation は起動時に要求した config bytes と launch arguments の照合に使われます。
- モデルがロード済みの場合、`POST /v1/chat/completions` に固定の短い probe（`hi`、`max_tokens: 1`、`temperature: 0`、非 streaming）を送信し、completion token が1以上あることを確認します。HTTP 409 / 429 / 503 は timeout まで 250 ms 間隔で再試行します。
- モデルが未ロードで `--load` がなければ、API 身元と attestation を確認して `readiness_state=unloaded` として成功し、生成はしません。`--load` を指定すると probe の生成要求が未ロードモデルをロードする経路になります。
- API key は環境変数 `STRATA_API_KEY` が空でなければそれを優先し、そうでなければ保存済み run config の `api_key` を使います。`api_key: "none"` は key なしの意図的な設定です。資格情報は probe の Authorization header に使われ、journal の結果には生成文や credential を保存しません。

検査要求や1 token 生成は server の実処理を発生させます。任意の API monitor が有効なら固定 probe request が通常の推論要求と同様に記録される場合があります。未ロードモデルに `--load` を使うとモデルがロードされた状態になります。これらは保存 profile の編集や server の再起動とは別の操作です。

## 適用条件と注意点

- 必須の `--profile` は起動済みの managed runtime を指す必要があります。`--plan` も ready な owner と instance が必要で、見つからない場合は `runtime_not_ready` になります。
- `--if-owner-id` と `--if-instance-id` は両方指定するか、両方省略します。plan の出力 ID を指定した場合、CLI と owner host の双方で現在値を再確認し、owner または instance が入れ替わっていれば検査を拒否します。直接 CLI では省略可能ですが、Desktop management bridge は両 ID を要求します。
- 実際の待ち時間 `--wait` は 1〜600 秒で、既定値は300秒です。timeout は API 呼び出しに使われ、owner RPC にはさらに5秒の余裕を加えます。parser は float として受け取るため秒未満の値も指定できます。
- endpoint 不一致、異なる instance/model/attestation、認証・transport error、不正な応答、token のない生成などは検証失敗です。モデルが未ロードで `--load` を指定しない場合は生成 readiness が false のままでも API verify として成功し得ます。
- probe は固定入力を実際に server へ送る smoke check です。生成された回答内容は評価しません。また model artifact の hash、driver/backend 互換性、継続 throughput、回答品質、マルチ GPU の安定性を確認するものではありません。

## 出力とエラー

`--output human`（既定）は profile 名、状態、instance ID、API URL、launch verification、generation の状態と、存在する場合のエラーを表示します。失敗した verify では engine log の場所と末尾最大3行を stderr に補助表示します。`--output json` は `schema_version` と結果 object を出力します。索引にある `--json` は `--output json` の alias です。`--quiet` は human の標準出力を抑制し、失敗時には保存された標準出力を stderr に出します。JSON 出力時には quiet による抑制は行われません。成功の終了コードは0、CLI 側の失敗は結果の `exit_code`（主に6）を返します。値の型・範囲などの不正は argparse または validation error になります。

`--plan` が成功した場合は `_success()` による plan 結果を出し、通常 verify の成功結果・journal は作りません。API verification の失敗では `runtime_not_ready`、`probe_*` 系エラーなどを返し、実行した操作の要約は journal に残ります。

## 関連文書

- [`--profile`](--profile.md)、[`--wait`](--wait.md)、[`--load`](--load.md)、[`--plan`](--plan.md)、[`--if-owner-id`](--if-owner-id.md)、[`--if-instance-id`](--if-instance-id.md)、[`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)、[`--help`](--help.md) — このコマンドのオプション文書。
- [CLI 索引](../../../README.md) — Terminal CLI のコマンド・オプション一覧。
- Strata `docs/TERMINAL.md` — managed runtime、verify probe、限界の説明。
- Strata `docs/MANAGEMENT_PROTOCOL.md` — runtime verify の plan と journal の management bridge 契約。

## 根拠

- Strata `strata_cli/cli.py:197-225,508-515` — `runtime` 階層と verify の parser、必須 profile、wait 既定値、load / plan / ID precondition / output、および one-shot parser に追加される `--json` / `--quiet`。
- Strata `strata_cli/cli.py:1331-1373,2232-2248` — management への委譲、plan・human・JSON 出力、失敗時の log hint と終了コード、`--json` / `--quiet` の共通処理。
- Strata `strata_control/management.py:188-198,235-270` — plan の read-only 動作、ready/ID 検査、wait の範囲、journal 記録と runtime 呼び出し。
- Strata `strata_control/runtime.py:687-699,1172-1208` — owner RPC、ID validation、ready child と instance の照合、probe 結果処理。
- Strata `strata_control/readiness.py:42-52,55-81,84-143` — credential 選択、HTTP 応答上限・エラー、endpoint・telemetry・attestation・model 検査、未ロード時分岐、固定生成 probe と token 条件。
- Strata `strata_control/journal.py:402-405` — journal に保持する verify 結果項目。
- Strata `docs/TERMINAL.md:63-75,94` — 利用例、未ロードモデルと `--load`、probe の記録範囲・制約。
- Strata `docs/MANAGEMENT_PROTOCOL.md:46-47` — verify plan は probe/journal なし、実行は journal 対象であること。
