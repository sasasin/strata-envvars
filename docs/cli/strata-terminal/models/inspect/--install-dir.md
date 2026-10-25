# `--install-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査 checkout は `main` で `origin/main` と一致し、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect MODEL_ID` |
| オプション | `--install-dir` |
| 別名 | なし |
| 値 | 既存の絶対パスのディレクトリ |

## 役割

`MODEL_ID` に対応するローカルの `strata-<MODEL_ID>.json` run config を探す場所を指定します。省略すると通常の Strata install discovery を使います。`models inspect` はその設定を使って engine、tokenizer、関連コンポーネントの状態を調べます。

## 使い方

```sh
strata models inspect my-model --install-dir /absolute/path/to/strata-install
```

指定ディレクトリ直下に `strata-my-model.json` がある場合に対象になります。設定ファイル名と `MODEL_ID` は大文字小文字を区別します。

## 値と既定値

値を1つ取ります。CLI parser 自体は文字列として受け取るだけですが、実処理は `~` をホームディレクトリに展開し、絶対パスかつ既存ディレクトリであることを要求します。条件を満たさない場合は `install directory must be an existing absolute directory` で失敗します。指定値は `Path.resolve()` で解決されます（`strata_control/models.py:84-92`）。

この引数を省略した場合は `STRATA_INSTALL_DIR` 環境変数があればその場所を使います。CLI 引数がある場合は環境変数より優先されます。どちらもなければ、Strata の discovery が候補を調べます。候補は `STRATA_DATA_DIR/install`、Terminal 自身のフォルダー、設定ファイルに記録された以前の install、Desktop app の install とその設定に記録された install です。run config が見つかった場所だけが候補になります（`strata_control/models.py:67-81`、`strata_control/discovery.py:160-192`）。

## 実行時の動作

指定時はそのディレクトリだけを探索します。省略時は discovery が返す install を順に探索し、同じ `MODEL_ID` が複数箇所にあれば最初の一致を使います（`strata_control/models.py:74-81,213-229`）。候補はディレクトリ直下の `strata-*.json` で、`.shared-settings.json` は除外され、ID は小文字英数字で始まる最大128文字の小文字英数字・`_`・`-` です（`strata_control/models.py:31,88-103`）。

run config は最大1 MiBの通常ファイルとして読み、シンボリックリンクを拒否します。engine、tokenizer、文字列引数の形式を確認したうえで、engine と tokenizer の各ファイル、run config 内で参照される pack・モデル・補助ファイルなどの存在を読み取り専用で調べます。検査前後で config の内容が変わっていないことも確認します（`strata_control/models.py:106-137,173-182`、`strata_control/doctor.py:30-53,146-235`）。結果には設定ファイルの SHA-256 とコンポーネント状況が含まれます。実行互換性は `unverified` として報告されます（`strata_control/models.py:158-182`）。

## 適用条件と副作用

このオプションは `strata models inspect` に属し、`models list` や `models move` では各コマンドの別 parser に定義された同名引数です（`strata_cli/cli.py:143-168`）。inspect の探索先を決めるだけで、設定、モデル、コンポーネントを作成・移動・修復せず、engine やモデルをロードしません。ファイルの読み取り、ファイル・ディレクトリ状態の照会、利用可能な任意 monitor Python module のバージョン確認、Linux の SYCL/HIP での device node アクセス確認は行われます（`strata_control/models.py:173-182`、`strata_control/doctor.py:218-235,238-272`）。GPU の live probe やネットワーク通信はこの inspect 経路では呼び出されません。

## 出力とエラー

成功時は human 形式でモデル ID、コンポーネント状態、config のパス、コンポーネント数と issue 数を標準出力へ出します。`--output json`（または `--json`）では `schema_version: 1`、`ok: true`、モデルとコンポーネントの詳細を JSON で出します。コンポーネントに不足・無効があっても inspect 自体は結果を返し、model の `component_status` を `missing_or_invalid` として報告します（`strata_cli/cli.py:153-156,597-603`、`strata_cli/cli.py:527-542`、`strata_control/models.py:163-170`）。

無効な install directory、対象モデルが設定されていない場合、または設定が不正・読み取り不能な場合は終了コード `5` で失敗します。`MODEL_ID` の形式が不正な場合は `ProfileError` の既定コード `2` です。人間向けエラーは標準エラーの `strata: ...`、JSON 出力時は `{"schema_version":1,"ok":false,"error":...}` です。検査中に config が変更された場合は再試行を促し、終了コード `6` になります。コマンド形式の誤りは argparse が usage とエラーを表示し、終了コード `2` です（`strata_control/models.py:84-85,213-229`、`strata_control/profiles.py:30-35`、`strata_cli/cli.py:527-532,2119-2173,2223-2235`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:141-156`
- dispatch、引数の受け渡し、出力: `strata_cli/cli.py:550-603`
- install directory 解決と model config 探索: `strata_control/models.py:67-103,213-229`
- 候補 install の探索順と明示指定時の単一ディレクトリ動作: `strata_control/discovery.py:160-203`
- config 制限、再読込による変更検出、component 検査: `strata_control/models.py:106-137,173-182`
- 参照ファイルの存在確認と report の生成: `strata_control/doctor.py:30-53,146-235`
- `ProfileError` の終了コードと CLI 共通エラー形式: `strata_control/profiles.py:30-35`、`strata_cli/cli.py:527-532,2119-2173`

調査範囲は上記 checkout のソースです。同一 revision の配布バイナリや Release artifact は確認しておらず、実機での CLI help 実行も行っていません。
