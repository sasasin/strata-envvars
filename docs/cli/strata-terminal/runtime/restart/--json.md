# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると JSON 出力を選ぶ |

## 役割

restart の結果を機械処理しやすい JSON で標準出力へ出します。`--json` は出力形式だけを選択し、restart 自体をプレビューにはしません。実際の再起動をせずに計画を確認するには、別途 `--plan` を指定します。

## 使い方

計画だけを JSON で確認する例です。`--plan` は現在の runtime と保存済み profile の起動内容を比較し、drain せずに計画を返します。

```sh
strata runtime restart --profile my-profile --plan --json
```

通常実行の結果を JSON にする場合は `--plan` を外します。この場合 `--json` は再起動を抑止しません。

## 値と既定値

- 引数値は不要で、`argparse` の `store_true` フラグです。省略時は `False` で、人間向け出力が既定です。
- `--json` は `runtime restart` の個別 parser 定義ではなく、one-shot parser 群へ共通に追加されています。runtime restart parser には `--output`（`human` または `json`、既定値 `human`）もあります。
- `--json` を指定すると `--output` の値にかかわらず、main 処理が `output` を `json` に設定します。したがって `--output human --json` も JSON を選びます。restart の parser は `jsonl` を受理しません。
- `--json` 自体に値の validation や空値の解釈はありません。値を続けて指定すると未認識引数として parser が拒否します。

## 実行時の動作

`main()` は parse 後、`--json` が真なら one-shot コマンドの `output` を `json` にします。`runtime` は `_runtime()` に渡され、restart の引数は `management.runtime_action()` へ渡されます。JSON 分岐では管理層の戻り値を `schema_version: 1` とともに1行の JSON として標準出力へ出します。成功時の結果フィールドや失敗時の `state`、`error`、`exit_code` などは restart の結果に応じます。

JSON 指定そのものは runtime の実行計画、待機時間、profile、source 切り替え条件を変更しません。通常実行では management 層が restart を journal に記録して runtime restart を呼び、失敗なら結果の `exit_code`（なければ `6`）をプロセス終了コードとして返します。`--plan` 時は restart 計画を取得し、実行前提条件オプションを計画と同時に指定するとエラーになります。

## 適用条件と副作用

- `--json` は runtime restart の one-shot 結果に適用されます。`--quiet` も共通 parser にありますが、JSON 出力時は quiet による stdout 捕捉を行わず、通常どおり JSON を出力します。
- `--json` 単独ではファイル、プロセス、ネットワーク、runtime の状態を変更しません。ただし `--plan` を付けない `runtime restart` は実際の restart 操作です。その実行時の再起動・rollback 等の副作用は `--json` が変えるものではありません。
- 成功・失敗の両方で restart 結果を JSON 出力します。人間向け失敗時に表示される engine log のヒントは JSON 分岐では出力されません。

## 出力とエラー

- 通常の結果は標準出力へ `{"schema_version":1,...}` 形式で出力され、JSON の Unicode はそのまま出力されます。JSON 直列化は `allow_nan=False` です。
- 実行中に捕捉される `ValueError`、`OSError`、`ClientError`、割り込み等の共通エラーは、`--json` が有効なら `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON を標準出力へ出します。終了コードは各例外経路のコードを使います。割り込みは `130` です。
- 引数解析時の未認識引数、必須 `--profile` の欠落などは `_run()` より前に parser が処理するため、JSON エラー形式ではなく argparse の usage/error（標準エラー、終了コード `2`）になります。

## 根拠

- parser と restart 用 `--output` / 他の restart option: `strata_cli/cli.py:238-254`。
- 共通 one-shot parser への `--json` / `--quiet` の追加: `strata_cli/cli.py:508-515`。
- `--json` から `output=json` への変換、quiet 時の分岐: `strata_cli/cli.py:2223-2247`。
- runtime dispatch、JSON の成功・失敗結果、終了コード、人間向け log hint: `strata_cli/cli.py:1331-1373`。
- JSON 共通エラー出力形式: `strata_cli/cli.py:527-532`。
- restart の実行引数 validation、plan 条件、journal 記録と runtime 呼び出し: `strata_control/management.py:292-336`。
- restart の結果 validation と RPC 呼び出し: `strata_control/runtime.py:702-740`。
- restart plan が runtime の ready 状態と候補内容を確認し、候補情報を返す処理: `strata_control/runtime.py:1132-1160`。
- コマンド階層と `--json` の索引掲載: 調査リポジトリ `docs/cli/README.md` の `strata runtime restart` 節。

## 調査範囲

対象 revision の Terminal CLI parser、dispatch、runtime management 層を確認しました。同一 revision の `--help` は補助資料として使用していません。OS/backend ごとの runtime restart 内部処理全体や Release artifact はこのオプションの出力仕様の調査対象として検証していません。
