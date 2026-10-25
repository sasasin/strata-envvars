# `strata doctor`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| POSIX の入口 | `bin/strata`（Terminal CLI） |
| 主な実装 | `strata_cli/cli.py`、`strata_control/doctor.py` |

## 役割

インストール済みエンジンと、選択した run config が参照するファイルの有無・基本状態を調べます。エンジンを起動せず、モデル設定に必要なコンポーネントの確認結果を human または JSON で報告します。プロファイルを選ばない場合は CLI と任意の monitor 依存を報告し、モデル固有の検査は行いません。

このページはコマンド全体の概要です。フラグの個別説明は [`docs/cli/README.md`](../../README.md) の `strata doctor` 節を参照してください。

## 基本的な使い方

```sh
# CLI と任意 monitor 依存の状態を確認
strata doctor

# run config のコンポーネントを調べる
strata doctor --profile /absolute/path/to/strata-model.json

# 保存済み profile を選び、NVIDIA GPU の可視性も照合
strata doctor --profile four-gpu --live --output json
```

`--profile` には保存済み profile 名、または run config JSON のパスを指定します。`.json` 拡張子、絶対パス、またはパス区切りを含む値はファイルパスとして扱われ、それ以外は保存済み profile 名として解決されます。保存済み profile は参照元 run config を検査します。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 基本検査 | `strata doctor` | CLI モジュールと任意 monitor 依存を報告します。profile 未選択を情報 issue として含みます。 |
| run config 検査 | `strata doctor --profile /path/to/run.json` | エンジン、tokenizer、設定引数が参照するファイル、任意 vision ファイルなどを調べます。 |
| 保存 profile 検査 | `strata doctor --profile NAME` | 保存 profile を解決し、その `source_config` に基づいて同じ検査を行います。 |
| live GPU probe | `strata doctor --profile NAME --live` | 対象環境の NVIDIA カード一覧を `nvidia-smi` で取得し、設定済み device index の可視性を照合します。 |
| JSON 出力 | `strata doctor --output json` | `{schema_version, ok, report}` を標準出力へ出します。 |

`--live` を profile なしで指定すると「比較対象の profile が必要」という error issue が作られ、終了コード 5 になります。HIP、SYCL、Metal などの device/driver 検証はこの live probe では実装されておらず、検証不能を report します。NVIDIA のカード一覧が取得できても、それはホストから見えるカードと index の照合に限られ、エンジン実行、CUDA 互換性、物理 topology を証明しません。

## 主な検査と制約

- run config がある場合、エンジン実行ファイルの存在・空でないこと（POSIX では実行権限も確認）、隣接 `BUILD.json` から読める version、tokenizer の `vocab.json`・`merges.txt`・`token_type.json` を調べます。
- `args` の `--pack`、`--native`、`--ple-gguf`、`--expert-profile`、`--mtp`、`--control-vector-scaled` が参照するパスを確認します。`--mtp` の値が数字だけなら draft depth とみなし、フォルダー検査を行いません。vision 設定がある場合は `exe`、`mmproj`、`model` の各パスも確認します。
- 任意の monitor 依存 `textual` はインストール有無と version を報告します。必須コンポーネントの `missing` / `invalid`、または error severity の issue があれば `ok` は false になり、終了コード 5 です。warning と info だけなら `ok` は true です。
- ハッシュ manifest を使ったファイル整合性確認や、エンジン・モデルの実ロード検証はしません。GPU driver probe は通常の検査では未検証として表示し、device/driver 互換性を判定しません。

通常の検査は診断レポートを作るもので、エンジンを起動したりコンポーネントを修復・ダウンロードしたりしません。`--live` は外部コマンド `nvidia-smi` を最大5秒で実行します。保存 profile の読込経路には、権限問題がある profile をその場で修復して読み直す処理があります。そのため、profile 読込時にはファイル権限の修復が起きる場合があります。

## オプション上の注意

`--components` は parser では受理されますが、現行 `_doctor` はこの値を参照せず、profile があればコンポーネント一覧を常に生成します。したがって現在は省略時との差がありません。

parser は共通 one-shot option として `--json` と `--quiet` も追加します。しかし成功時の `_doctor` は `--output` だけで出力形式を決め、quiet 判定を行いません。成功結果を JSON にするには `--output json` を使用してください。`--json` は失敗時の JSON error 形式には使われますが、成功時の出力形式を JSON に切り替えません。

## 出力とエラー

human 出力はコンポーネントごとの status・名前・path/reason/version、その後に issue の severity・code・message を表示します。live probe 結果がある場合は status とカード情報も出します。JSON 出力は report 全体を含み、JSON serialization で `NaN` / Infinity を許可しません。

診断上の必須欠落・不正、live probe の error、または profile 未選択での `--live` は exit code 5 です。profile/run config の読み込みなどで発生する `ValueError` は CLI の共通 error handler が出力し、例外に `exit_code` があればそれを使い、なければ 2 を使います。ファイル操作の `OSError` はアクセス修復・再試行の対象になる場合があり、解消しなければ exit code 6 で報告されます。argparse の不正な値（例: `--output` に `human` / `json` 以外）は argparse の usage error です。

## 関連文書

- [CLI オプション索引](../../README.md) — `strata doctor` のオプション文書
- [Terminal Quickstart](../../../TERMINAL_QUICKSTART.md) — run config・profile と doctor の利用例
- [Troubleshooting](../../../TROUBLESHOOTING.md) — doctor の説明と診断情報の扱い

## 根拠

- `strata_cli/cli.py:109-113` — doctor parser と `--profile`、`--components`、`--live`、`--output`。
- `strata_cli/cli.py:508-515` — doctor に共通 `--json` / `--quiet` option を追加。
- `strata_cli/cli.py:1023-1045` — profile 解決、inspect 呼び出し、human/JSON 出力、終了コード。
- `strata_cli/cli.py:2138-2139,2166-2188` — doctor dispatch と `ValueError` / `OSError` の CLI エラー処理。
- `strata_control/profiles.py:135-147,382-388` — run config の基本検証と profile 名・ファイルパスの解決規則。
- `strata_control/profiles.py:150-166` — 保存 profile の読込と、権限修復を試みる読込処理。
- `strata_control/doctor.py:30-53,56-77` — 相対パス解決、コンポーネントの存在判定、GPU index 値の検証。
- `strata_control/doctor.py:80-115,118-143` — `nvidia-smi` の5秒制限、出力検証、対応 backend と index 比較。
- `strata_control/doctor.py:146-160,162-235` — profile 未選択時と run config 検査、issue severity と `ok` 判定。
- `strata_control/doctor.py:238-273` — Linux HIP/SYCL device access warning と optional monitor version 判定。
- `docs/TERMINAL_QUICKSTART.md:34-39,64-71`、`docs/TROUBLESHOOTING.md:40-43` — 利用者向けの doctor 説明と使用例。実装上の挙動は上記ソースを基準に記述。

## 調査範囲

同一 commit の Terminal CLI parser と処理実装、profiles helper、関連する利用者向け文書を確認しました。OS/backend ごとの GPU probe の実機 qualification、全ての run config 形式の網羅、最新 Release artifact 上での動作はこの調査では確認していません。
