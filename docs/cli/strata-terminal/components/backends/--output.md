# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components backends` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

OS と backend family の対応表と、現在のマシンで各組み合わせを使えるかを表示形式で選びます。`--output` は出力先ファイルの指定ではなく、結果を人向けのテキストか JSON にする指定です。

## 使い方

```sh
strata components backends --output json
```

`--output` を省略した場合は `human` 形式です。

## 値と既定値

- 受理値は `human` と `json` のみで、既定値は `human` です。parser は `choices=("human", "json")` で値を検証します。
- 同じオプションを複数回指定した場合の独自処理はありません。通常の `argparse` の解析に委ねられます。
- それ以外の値は引数解析で拒否され、usage とエラーが標準エラーに出て終了コード 2 になります。

## 実行時の動作

コマンドは `host_platform()` でこのマシンの platform key を取得し、`BACKEND_MATRIX` を backend 名順に並べて、各行に許可 platform の一覧と「現在のマシンに該当するか」を加えます。行の `here` は現在の platform key がその backend の platform 一覧に含まれるかを表します。

- `human` は現在の platform key と、backend ごとの platform 一覧および `supported here` / `not supported here` を標準出力に表示します。
- `json` は `schema_version: 1`、`ok: true`、`host`、`matrix` を含む JSON オブジェクトを標準出力に1行で出します。`matrix` の各要素は `backend`、`platforms`、`here` を含みます。
- いずれの形式でも成功時の終了コードは 0 です。この出力選択によって matrix の内容や判定は変わりません。

## 適用条件と副作用

matrix は `strata_control.targets.BACKEND_MATRIX` の定義をそのまま使います。現行定義では Metal は `macos-arm64`、CUDA と HIP は `windows-x86_64` / `linux-x86_64`、SYCL は `linux-x86_64`、CPU は `macos-arm64` / `macos-x86_64` / `windows-x86_64` / `linux-x86_64` を対象とします。表示はプロジェクトが対応を表明する組み合わせを示し、実機での認定を意味しない旨も human 出力に記されています。

`host_platform()` は `platform.system()` と `platform.machine()` から platform key を作ります。未知の OS 名では `ComponentError` を送出し、対応表にないアーキテクチャ名はそのまま key に使われるため、後者ではコマンド自体は成功して全 backend が `here: false` になり得ます。このコマンドの処理にはファイル作成、ネットワークアクセス、backend 起動はありません。なお CLI 共通の起動処理は引数解析前に `private_files.adopt_user_defaults()` を呼びます。

## 出力とエラー

- JSON 成功出力は `schema_version: 1`, `ok: true`, `host`, `matrix` を含みます。
- parser で無効な `--output` 値を拒否します。
- 対応外 OS では `host_platform()` が `ComponentError` を送出します。`_run()` の例外処理には `ComponentError`（`RuntimeError` の派生型）専用処理がないため、通常の `strata: ...` 形式のエラー JSON や安定した終了コードに変換される経路は確認できません。

## 根拠

- `strata_cli/cli.py:129-131` — `components backends` parser と `--output` の選択肢・既定値。
- `strata_cli/cli.py:2044-2061` — host の取得、matrix の生成、human / JSON 出力、成功時の戻り値。
- `strata_cli/cli.py:527-542` — 共通の JSON 成功・エラー出力の形式。
- `strata_cli/cli.py:2129-2133` — `components backends` を `_components_backends()` に渡す dispatch。
- `strata_cli/cli.py:2166-2188` — `_run()` が個別に処理する例外型。
- `strata_cli/cli.py:2217-2225` — 引数解析前の共通起動処理。
- `strata_control/targets.py:20-39` — backend/platform matrix と host platform key の生成・OS エラー。
