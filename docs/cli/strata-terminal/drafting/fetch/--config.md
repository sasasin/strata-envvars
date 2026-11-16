# `--config`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。調査開始時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--config` |
| 別名 | なし |
| 値 | `FILE`。モデルの run config JSON ファイルのパス |

## 役割

指定したモデルの run config を読み、DFlash2 drafter の取得判断に必要なモデル名、drafting の選択、エンジン引数などを渡します。config の `args` からデータフォルダーを推定できる場合は取得先にも使います。`--data-dir` を併記した場合は、明示したフォルダーが取得先になります。parser 上は任意指定です。

## 使い方

```sh
strata drafting fetch --config ./model.json
```

既に drafter が選択されていて、ファイルが未配置の場合だけ取得する例:

```sh
strata drafting fetch --config ./model.json --if-needed
```

## 値と既定値

- `FILE` は必須の単一値です。parser は `--config` に文字列を受け取りますが、ファイルの存在や JSON 形式を parser 段階では検証しません（`strata_cli/drafting_cmd.py:24-29`）。
- オプション自体は省略できます。省略時、fetch でモデル名・family も指定されていなければ、DFlash2 対応のインストール済みモデルを検索します。該当モデルが1件ならその run config を自動選択し、複数なら選択を促すエラーになります。明示的な `--config` がある場合、この自動選択は行いません（`strata_cli/drafting_cmd.py:80-98, 103-109`）。
- 指定ファイルを UTF-8 with BOM 許容で読み、JSON として解析します。読み込み時の `OSError` または JSON の `ValueError` は捕捉され、空 config として扱われます。従ってこの場合も CLI の設定読込エラーにはならず、データフォルダー推定などは既定経路へ進みます（`strata_cli/drafting_cmd.py:105-116`）。

## 実行時の動作

config の `args` に `--pack <path>` があればそのパスの2階層上、なければ `--mtp <path>` の2階層上をデータフォルダーとして推定します。`--mtp` の値の basename が数字の場合はその候補を使いません。どちらからも推定できなければ `Catalog().data_dir()` の既定フォルダーを使います（`strata_control/drafting.py:1500-1509`、`strata_cli/drafting_cmd.py:110-116`）。明示的な `--data-dir` がある場合はこちらが優先されます（`strata_cli/drafting_cmd.py:110-116`）。既定フォルダー経路で `Catalog` を初期化すると、インストールルートの作成を試みます（`strata_cli/launch/catalog.py:249-259`）。

同じ config から `model_name`、`drafting`、`args`、`parallel` 等も参照され、モデルと現在の hardware/backend に応じた drafter 選択、既存 MTP layer の状態、engine 引数との整合を判断します。明示した `--mode` があれば config の `drafting` より優先されます。config で `mtp` が `false` かつ選択が `auto` の場合は `off` として扱われます（`strata_cli/drafting_cmd.py:117-134`）。`--if-needed` がある場合だけ、必要判定が偽なら取得をスキップします。付けない通常の fetch は必要判定が偽でも `ensure_for()` を呼ぶため、config の選択が drafter を必要としない場合にも取得を試みる経路があります（`strata_cli/drafting_cmd.py:159-190, 199-201`）。

## 適用条件と副作用

- `--config` は plan/fetch の両方に共通して登録されていますが、この文書は fetch のスコープです（`strata_cli/drafting_cmd.py:21-29`）。
- config の `args` からデータフォルダーを推定できるかは、その引数リストに `--pack` または `--mtp` と値が含まれるかによります。相対パスの解決や他の config キーの妥当性検証をこの処理が行うことは確認できません（`strata_control/drafting.py:1500-1509`）。
- `--if-needed` を付けない fetch は、必要判定にかかわらず `ensure_for()` を呼びます。config のモデル・選択と hardware 条件は取得する pack の選定に使われます。明示的な `--config` はモデル固有の選択のために使われますが、config の読込に失敗すると空 config として扱われるため、意図したモデルや取得先を使わない可能性があります（`strata_cli/drafting_cmd.py:101-134, 159-165, 186-215`）。

## 出力とエラー

- 複数のインストール済みモデルが見つかる bare fetch の曖昧さエラーは終了コード 2 です。ただし `--config` を明示した呼び出しはこの自動検索・曖昧さ判定の対象外です（`strata_cli/drafting_cmd.py:83-98, 153-158`）。
- fetch の取得失敗または取得禁止は終了コード 5 です。通常出力では `strata: ...` を stderr に、`--output json` / `jsonl` ではエラー JSON を stdout に出します（`strata_cli/drafting_cmd.py:210-215`）。
- ファイルシステム由来の未捕捉 `OSError` は共通 CLI handler が終了コード 6 として処理します（`strata_cli/cli.py:2189-2196`）。構文上の引数不足・余分な引数は argparse の usage/error 経路です（`strata_cli/cli.py:2256-2265`）。

## 根拠

- 索引上の scope と予定リンク: `docs/cli/README.md:329-341`。
- parser 定義と option の共通 scope: `strata_cli/drafting_cmd.py:19-38`。
- bare fetch 時の config 自動選択と config ファイル読み込み・失敗時の扱い: `strata_cli/drafting_cmd.py:80-116`。
- config の読み取り内容と `--data-dir` 優先、mode 等の決定: `strata_cli/drafting_cmd.py:117-134`。
- fetch の必要判定、スキップ、取得呼び出し、失敗時の終了コードと出力: `strata_cli/drafting_cmd.py:150-220`。
- config 引数からのデータフォルダー推定: `strata_control/drafting.py:1500-1509`。
- 既定フォルダー経路で使う Catalog の初期化とルート作成: `strata_cli/launch/catalog.py:249-259, 537-544`。
- 共通 CLI の `OSError` エラー処理: `strata_cli/cli.py:2189-2196`。

調査範囲は上記 commit の Strata 所有ソースです。CLI の help は実行していません。`--config` の不正な JSON や読み取りエラーは明示的な失敗ではなく空 config にフォールバックする実装を確認しましたが、JSON として読めても object ではない値を渡した場合の動作はこの調査では確認していません。
