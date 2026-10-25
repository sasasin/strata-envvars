# `--load`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--load` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると `True`、省略時は `False`。 |

## 役割

管理対象のローカルサーバーを検証するとき、モデルが未ロードなら1トークン生成の検証を実行してモデルをロードさせます。通常の `verify` も API の同一性・起動構成を確認し、モデルが既にロード済みなら1トークン生成まで確認します。`--load` は未ロード状態でもこの生成確認を行うための指定です。

## 使い方

```sh
strata runtime verify --profile PROFILE_NAME --load
```

`--profile` は必須です。出力を JSON にする場合は `--output json` を併用できます。コマンド階層とこのオプションの scope は索引の [`strata runtime verify`](../../../README.md) に掲載されています。

## 値と既定値

- `argparse` の `action="store_true"` で定義され、引数値は不要です。省略時は `False` です。
- `--load=true` のような値を受ける形式ではありません。
- `--wait` の既定値は300秒で、runtime 層では1〜600秒の範囲が検証されます。`--load` 専用の数値境界や追加 validation はありません。

## 実行時の動作

CLI は `--load` を runtime management に渡し、実行時には operation journal に `load` の真偽値を記録して `runtime.verify(..., load=load)` を呼びます（`strata_cli/cli.py:1345-1356`、`strata_control/management.py:235-270`）。runtime 層は `load` が真偽値であることを検証し、owner host へ `load` と待ち時間を RPC で送ります（`strata_control/runtime.py:687-699`）。

owner host は ready 状態と ready-file の PID・instance ID を確認したうえで readiness 検査を呼び出し、`--load` の値を `force_load` として渡します（`strata_control/runtime.py:1172-1208`）。readiness 検査はまず telemetry から instance ID、launch attestation、model ID、ロード状態を照合します。モデルが未ロードで `force_load` が偽なら生成要求を送らず、API と起動同一性を確認した結果として `generation_ready=false` を返します。未ロードで `--load` が真なら、またはモデルがすでにロード済みなら、`/v1/chat/completions` に `max_tokens=1`、`temperature=0` の要求を送り、生成トークンを確認します（`strata_control/readiness.py:84-120`、`strata_control/readiness.py:121-143`）。

`--plan` と併用した場合は実行せず、現在の `model_state`、`load`、`would_load`（モデル状態が `unloaded` の場合のみ真）、および1トークン probe を行う予定であることを表示します（`strata_control/management.py:239-254`）。

## 適用条件と副作用

- 対象は `runtime verify` が扱う Strata の owned local server です。runtime が ready でない場合、実検証は `runtime_not_ready` で失敗します（`strata_control/management.py:242-249`、`strata_control/runtime.py:1184-1190`）。
- モデル未ロード時に `--load` を指定すると、生成 API 要求によってサーバーにモデルロードと1トークン生成を行わせます。従ってモデルのメモリ・計算資源を使い、モデルをロード済み状態にします。モデルが既にロード済みの場合も、通常どおり1トークン生成の probe を行います（`strata_control/readiness.py:115-126`）。
- 検証は telemetry と chat completions API へのローカル HTTP 要求を行います。API key は run config のバイト列および `STRATA_API_KEY` から解決され、Authorization header に使われます。probe の応答本文は readiness モジュールの説明上、保存されません（`strata_control/readiness.py:1-5`、`strata_control/readiness.py:42-65`）。
- 実行は operation journal に記録されます。`--plan` は journal を伴う実行経路に進まず、効果の preview を返します（`strata_control/management.py:250-270`、`strata_control/journal.py:343-356`）。
- API 側が未ロードモデルをロードする実装条件の詳細（モデル形式や backend ごとの差）は readiness 呼び出し元からは確定できないため、ここでは断定しません。

## 出力とエラー

- 成功時の human 出力は profile、instance、API URL、launch verification、readiness の状態を表示します。`--output json` は結果オブジェクトを JSON で stdout に出力します（`strata_cli/cli.py:1357-1369`）。
- readiness の失敗は owner host から `ok=false`、エラー名、終了コードを返します。例として runtime 未 ready、instance 不一致、HTTP/API probe の失敗、生成応答にトークンがない場合があります。CLI は失敗結果の終了コードを返し、human 出力ではエラー時に取得できれば engine log の場所と末尾も stderr に出します（`strata_control/runtime.py:1184-1205`、`strata_control/readiness.py:67-80`、`strata_control/readiness.py:133-143`、`strata_cli/cli.py:1364-1373`）。
- `--wait` が1〜600秒外、または runtime の検証対象が不正な場合はエラーになります（`strata_control/management.py:255-263`、`strata_control/runtime.py:690-695`）。

## 根拠

- parser 定義、既定値および隣接する `--plan` 等: `strata_cli/cli.py:216-225`
- CLI から management への引き渡し、plan 表示、operation journal: `strata_cli/cli.py:1345-1373`、`strata_control/management.py:235-270`
- runtime validation、RPC payload、owned instance / ready-file の確認と readiness 呼び出し: `strata_control/runtime.py:687-699`、`strata_control/runtime.py:1172-1208`
- telemetry 照合、未ロード時の分岐、生成 probe の内容と応答 validation: `strata_control/readiness.py:84-143`
- 索引上の option scope: `docs/cli/README.md:412-425`

調査範囲は上記 commit の Terminal CLI、runtime management、readiness 実装です。調査時に Strata の build、テスト、GPU 実行、性能測定は行っていません。
