# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models import` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。parser で `action="store_true"`、`required=True` |

## 役割

ローカルの GGUF ファイルまたはフォルダーを読み取り、Strata が認識するモデル候補か、ファイル一式が揃っているか、既に設定済みかをプレビューします。このコマンドはモデルを採用・コピーせず、実行互換性も確定しません。parser 上 `--plan` が必須なので、このサブコマンドは必ず指定して実行します（`strata_cli/cli.py:157-161`、`strata_control/models.py:579-585, 731-736`）。

## 使い方

```sh
strata models import --plan /absolute/path/to/model.gguf
strata models import /absolute/path/to/model-folder --plan --output json
```

`PATH` は GGUF ファイル（分割ファイルの一片を含む）、モデルファイルのあるフォルダー、またはモデルを含む上位フォルダーを指定できます。相対パスは受け付けず、`~` は展開されます（`strata_control/models.py:579-592`）。

## 値と既定値

`--plan` に値はなく、既定値は `False` ですが、`required=True` により省略時は処理に進まず argparse が使用法エラーにします。`--plan=false` のような値指定はできません（`strata_cli/cli.py:157-161`）。

このコマンドの出力形式は `--output human|json`（既定 `human`）で、one-shot parser 共通の `--json` は `--output json` の別表記です。`--plan` 自体の結果内容はこれらで変わらず、成功時の表示形式が変わります（`strata_cli/cli.py:161, 508-515, 2232-2235`）。

## 実行時の動作

parser が受け取った `PATH` は `_models()` から `strata_control.models.plan_import()` に渡されます（`strata_cli/cli.py:550-561`）。`--plan` の真偽値で別の実行経路を切り替える処理はなく、このサブコマンド自体が読み取り専用のプレビューです。

`plan_import()` はパスの存在と種別を確認し、フォルダーなら GGUF ファイルを列挙します。選んだフォルダーにファイルがない場合は、上位フォルダー内を深さ3、最大300フォルダーまで探索します。フォルダー内の GGUF は最大5000件まで調べます。分割ファイル名から一式を構成する場合、shard 数は1〜128が対象です。複数の候補があれば既知モデル名などで一つに絞れる場合を除き、選択を求める問題として報告します（`strata_control/models.py:34, 438-472, 475-506, 579-663`）。

候補のファイルは読み取り専用で開き、GGUF ヘッダーと互換性判定に使うメタデータを検査します。既知の shard 名は選択の手掛かりに使われ、必要に応じてヘッダー情報も既知の fingerprint と照合されます。`--plan` はモデルの採用やコピーを行わず、結果には `would_write: false`、`execution_compatibility: "unverified"` と、後続の architecture・quantization・tokenizer・engine 検査が必要である旨が含まれます（`strata_control/models.py:232-273, 276-294, 579-585, 664-695, 709-736`、`strata_control/gguf_preflight.py:105-123`）。

成功時は human 出力にファイル数・file set 状態・認識したモデル候補・既存設定の有無・採用状態を表示し、最後に `No files changed` と表示します。JSON では `schema_version: 1`、`ok: true`、`plan` を出力します（`strata_cli/cli.py:535-542, 708-723`）。この結果だけでは実行互換性を保証しません。

## 適用条件と副作用

- 入力は絶対パスで、存在するファイルまたはフォルダーである必要があります。パスのリンク先も追跡しますが、`mmproj*.gguf` をモデル本体として直接指定すると拒否します（`strata_control/models.py:579-638`）。
- split shard の欠落、GGUF 形式や metadata の不備、未対応 architecture、認識できない variant などは `issues` として返されます。候補名が既知でも由来や完全性の証明にはならないと、結果の `notes` に明記されます（`strata_control/models.py:656-695, 709-736`）。
- 既存 run config、準備済み pack・draft layer・picture reader の有無を照会します。ソースではこの確認も読み取り専用です（`strata_control/models.py:297-307, 720-736`）。
- `plan_import()` はコピーや採用を行いません。入力ファイルは `os.O_RDONLY` で開かれます（`strata_control/models.py:232-250`、`strata_control/gguf_preflight.py:105-114`）。フォルダー列挙や既存状態の照会は行います。
- CLI 共通起動処理は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。POSIX では何もせず、Windows では昇格実行時にこのプロセスの既定 owner/DACL を設定しようとします。これは `--plan` 固有のファイル変更ではありません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-390`）。

## 出力とエラー

- 検査結果に `issues` がある場合、human 形式では問題の要約を標準エラーに出し、終了コード `5` を返します。JSON 形式では `schema_version: 1`、`ok: false`、`plan` を標準出力に出し、同じく `5` を返します（`strata_cli/cli.py:553-560, 606-614`）。
- パス不在、相対パス、GGUF がない、非 GGUF の通常ファイル、mmproj の直接指定、分割数の範囲外など、検査開始時点の拒否は `ProfileError` になります。相対パスのエラーは既定コード `2`、多くの入力・検査エラーは明示コード `5` です（`strata_control/profiles.py:30-35`、`strata_control/models.py:579-640`）。
- `_run()` は `ProfileError` の基底である `ValueError` を捕捉し、human では `strata: ...` を標準エラーへ、JSON 指定時は `error` object を標準出力へ出します（`strata_cli/cli.py:527-532, 2166-2173`）。
- `--plan` を省略した場合は parser の必須引数エラーです（`strata_cli/cli.py:157-161`）。

## 根拠

- parser 定義とオプション scope: `strata_cli/cli.py:157-161`。one-shot 共通の `--json` 追加: `strata_cli/cli.py:508-515`。
- `PATH` の解釈、検査、結果フィールド: `strata_control/models.py:579-736`。
- CLI から検査関数への接続と成功・問題時の出力: `strata_cli/cli.py:550-561, 606-614, 708-723`。
- GGUF ヘッダー・metadata の読み取り: `strata_control/models.py:232-250`、`strata_control/gguf_preflight.py:105-123`。
- CLI 共通起動時の Windows token defaults: `strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-390`。
- 調査開始時の Strata checkout は `main`、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）でした。
