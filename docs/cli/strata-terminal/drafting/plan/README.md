# `strata drafting plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| 主な実装 | `strata_cli/drafting_cmd.py`、`strata_control/drafting.py`、`strata_control/drafting_fetch.py` |

## 役割

DFlash2 drafter の取得計画と、指定モデル・設定でその drafter が必要かを表示します。既存 pack の有無、ダウンロード対象の repository と pinned revision、想定サイズ、配置先を確認できます。この `plan` サブコマンドはファイルを取得・作成せず、network download もしません。実際に取得・pack する操作は [`strata drafting fetch`](../fetch/README.md) です。

## 使い方

```sh
# Strata の既定 data folder で pack の状態と取得量を確認
strata drafting plan

# run config のモデル名・drafting 設定・data folder を使って判定
strata drafting plan --config /path/to/run-config.json --output json

# config がない場合に model family と選択を明示
strata drafting plan --family qwen --mode dflash2 --data-dir /path/to/model-data
```

`--mode` は `auto`、`mtp`、`dflash2`、`off` を受け付けます。省略時は run config の `drafting` 値を使い、それもなければ `auto` です。各 option の詳細は [`--config`](--config.md)、[`--data-dir`](--data-dir.md)、[`--family`](--family.md)、[`--mode`](--mode.md)、[`--output`](--output.md) を参照してください。

## 実行時の動作

- `--config` が指定されると JSON 設定を読み、`drafting`、`model_name` と `args` 内の model data path を判定に使います。読み取りに失敗した場合は空設定として続行します。data folder は明示した `--data-dir` が優先され、次に config の engine args から求め、見つからなければ Strata の `Catalog` 既定 folder を使います。
- GPU architecture を NVIDIA (`nvidia-smi`) / AMD driver data から調べ、既知 architecture を card class に対応付けます。取得できない場合は `other` です。現行 suggestion table は全 card class で MTP を返します。
- `plan` helper は `<data-dir>/dflash2/qwen3.8-flash-next-dflash2.q8.pack` が存在し 1 MiB を超えるかを確認し、`ready`、`gb`、pack path、repository、revision と説明文を作ります。判定結果には `needed`、engine が serve mode で DFlash2 を使えるか (`serves`)、選択された drafter (`drafter`)、理由 (`note`)、表示用の `line` も含まれます。
- 人間向け出力は取得案内、または model choice の説明です。`--output json` / `jsonl` はいずれも `schema_version: 1`, `ok: true` を含む一件の JSON 結果を stdout に出します。`jsonl` であっても `plan` は進捗 stream を出しません。

## 適用条件と副作用

この checkout では `ENGINE_SERVES_DFLASH2 = False` です。そのため `needed` は常に false で、`auto` の選択も現在は MTP です。明示的に `--mode dflash2` を指定した場合も、serve mode では利用できない旨を返し、結果の drafter は MTP になります。`plan` が表示する取得量 (`gb`) は pack の有無を示す値であり、それだけで現在の server 起動が DFlash2 を必要とするという意味にはなりません。設定ファイルと既存 pack は読みますが、このコマンド経路は download や pack を行いません。

GPU class の確認にはホストの `nvidia-smi` / driver 情報を参照します。GPU を照会できない場合は `other` class に進みます。Windows では Terminal CLI 共通起動処理が process token の既定 owner/DACL を現在ユーザー向けに設定しようとします。POSIX では何もしません。

## 出力とエラー

- 人間向け結果は stdout、JSON/JSONL 結果も stdout です。plan 結果は正常処理時に終了コード 0 を返します。
- `--config` の読み込みで `OSError` または JSON decode error が起きても、`drafting_cmd.py` はそのエラーを表示せず空設定として続けます。
- `--output` が `human` / `json` / `jsonl` 以外、または `--mode` が許可値以外の場合は argparse が引数エラーとして拒否します。
- `--data-dir` の pack 検査中の `OSError` は pack を未準備として扱います。

## 関連文書

- [CLI 索引](../../../README.md) — `strata-terminal` のコマンド階層と option scope。
- [`strata drafting`](../README.md) — drafting サブコマンド群。
- [`strata drafting fetch`](../fetch/README.md) — drafter file の取得と pack。
- [`strata launch`](../../launch/README.md) — serve 起動時のモデル設定。

## 根拠

- Strata `strata_cli/cli.py:172-173,2144-2146` — drafting parser の登録と dispatch。
- Strata `strata_cli/drafting_cmd.py:17-29` — `plan` / `fetch` parser、位置引数なし、各 option と既定値。
- Strata `strata_cli/drafting_cmd.py:40-55` — config 読み込み、data folder の優先順、card class 取得。
- Strata `strata_cli/drafting_cmd.py:57-73` — plan の判定、返却項目、human/JSON 出力。
- Strata `strata_control/drafting_fetch.py:29-39` — pack の存在確認と取得計画の repository/revision/size。
- Strata `strata_control/drafting.py:23-25,50-79,88-111,114-122` — mode、suggestion table、model compatibility、pack path/readiness。
- Strata `strata_control/drafting.py:141-183` — serve support flag、選択 drafter と `needed` の条件。
- Strata `strata_control/engine_component.py:702-734` — NVIDIA / AMD architecture 情報の取得。
- Strata `strata_cli/launch/catalog.py:494-501` — Terminal の既定 data folder。
- Strata `strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-389` — CLI 起動時の Windows user-default token 設定。
