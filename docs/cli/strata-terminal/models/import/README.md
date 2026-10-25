# `strata models import`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models import` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/models.py` |
| 位置引数 | `PATH`（ローカルの GGUF ファイルまたはディレクトリ） |

## 役割

手元にある GGUF ファイル一式を読み取り、Strata が認識する候補か、shard が揃っているか、モデルのメタデータや補助ファイルがどう見えるかを表示します。setup や `strata launch` に渡す前の確認に使えます。これはプレビューであり、モデルを採用・登録するコマンドではありません。

## 使い方

```sh
# GGUF ファイルを含むディレクトリを人間向けに確認
strata models import /absolute/path/to/model-folder --plan

# 分割 GGUF のいずれか1 shard を指定し、結果を JSON で取得
strata models import /absolute/path/to/model-00001-of-00002.gguf --plan --output json
```

`PATH` は絶対パスで指定します。ファイルを選ぶ場合は `.gguf` のモデルファイルを指定し、分割モデルではどの shard でも選べます。ディレクトリはモデルファイルを含む場所のほか、モデルを含む下位フォルダーを探す上位ディレクトリも指定できます。CLI parser では `--plan` が必須で、`--output` は `human`（既定）または `json` です。[`--plan`](--plan.md)、[`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)、[`--help`](--help.md) は個別文書を参照してください。

## 実行モードと主な動作

このコマンドはプレビュー専用です。指定パスを絶対パスとして検査し、GGUF ファイルの候補を列挙・グループ化します。モデル候補の判定、shard の欠落確認、GGUF ヘッダーとメタデータの確認、既存の setup 済みファイルや隣接する `mmproj` 画像 reader の有無を結果に含めます。通常の人間向け出力は、ファイル数と状態、判別できた family/model、既存セットアップ情報、採用状態を表示し、最後に「No files changed」と示します。JSON 出力では `plan` と `would_write: false` を含みます。

この処理はファイルをコピー・移動・修復せず、ダウンロードやエンジン起動もしません。GGUF の全 tensor payload を読み込まず、ファイル全体の hash や出所を検証せず、実際の engine load も試しません。したがって、候補として認識されても実行互換性を保証しません。実際に採用するには、architecture・quantization・tokenizer・model pack・engine version・hardware などの後続チェックが必要です。

## 注意点

- 複数のモデル群が見つかる場合は自動選択せず、選ぶべきファイルまたはフォルダーを案内します。モデルを含む上位ディレクトリの探索は深さ3までで、探索するディレクトリ数は最大300です。
- 分割 shard はファイル名の `-00001-of-00002.gguf` 形式で照合し、上限は128 shard です。欠落・不正な shard、認識できないモデル variant、非対応または不足する metadata は問題として返されます。
- 1フォルダーにつき最大5000個の `.gguf` ファイルまで確認します。選択したモデル群以外のファイルがあっても、認識済みのモデル群を一つだけ選べる場合はその群を使い、ほかはそのままにします。
- `mmproj*.gguf` はモデル shard として数えず補助ファイルとして評価します。指定した `.gguf` 自体が `mmproj` の場合は、モデル本体ではないとして拒否されます。
- 既知の shard 名は候補選択の手掛かりに過ぎず、ファイルの provenance や完全性の証明ではありません。結果の `execution_compatibility` は `unverified` です。
- parser は共通 one-shot option として `--json`（`--output json` の alias）と `--quiet` も受理します。`--quiet` は人間向け標準出力を抑制する設定で、JSON 出力には適用されません。

## 関連文書

- [CLI 索引](../../../../README.md) — `strata models import` の option 文書一覧。
- [Strata Terminal commands](../../../../TERMINAL.md) — `models import` を含む Terminal CLI の説明。
- [Terminal quick start](../../../../TERMINAL_QUICKSTART.md) — setup 済みモデルを確認・再利用する関連コマンド。

## 根拠

- Strata `strata_cli/cli.py:141-162` — `models import` の階層、位置引数、必須 `--plan`、`--output`。
- Strata `strata_cli/cli.py:508-515` — one-shot command 群に追加される `--json` と `--quiet`。
- Strata `strata_cli/cli.py:550-561,708-723` — プレビュー結果の分岐、人間向け表示、JSON 成功・問題出力。
- Strata `strata_control/models.py:579-638,641-663` — 絶対パス、ファイル/ディレクトリ、shard 群と拒否条件。
- Strata `strata_control/models.py:664-735` — header/metadata の調査、候補評価、`execution_compatibility`、`would_write: false`。
- Strata `strata_control/models.py:438-472,475-506` — ファイル列挙上限と上位フォルダー探索。
- Strata `docs/TERMINAL.md:16-28` — 利用者向け説明とプレビューの制約。
