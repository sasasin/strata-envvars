# `strata models`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/models.py`、`strata_control/models_move.py` |

## 役割

Strata が認識しているモデル設定の一覧・検査、既存 GGUF ファイルの読み取り専用プレビュー、モデルデータの保存先移動を行うコマンド群です。`strata models` の後に `list`、`inspect`、`import`、`move` のいずれかのサブコマンドを指定します。単独の `strata models` はサブコマンドが必須です。

## 使い方

```sh
# Strata が見つけたローカルのモデル設定候補を表示
strata models list --installed

# 設定と参照コンポーネントを調査
strata models inspect MODEL_ID

# 手元の GGUF ファイルまたはフォルダーを変更せずに確認
strata models import /path/to/GGUF-folder --plan

# 保存先の移動計画を表示（モデルファイルは移動しない）
strata models move /path/to/new-folder --plan
```

JSON 出力が必要な場合は、各サブコマンドで `--output json` を指定できます。各サブコマンドの詳細は [`docs/cli/README.md`](../../README.md) の `strata-terminal` 節にある文書を参照してください。

## 実行モード

| サブコマンド | 用途 | 主な動作 |
| --- | --- | --- |
| `list` | ローカル設定または現在の server のモデルを一覧 | 既定では既知の Strata install にある `strata-*.json` を調査します。`--served` では現在の接続先 server が報告するモデルだけを取得します。 |
| `inspect MODEL_ID` | ローカルのモデル設定と参照コンポーネントを確認 | run config と必要な engine 等の存在状態を調べます。実際にモデルをロードしたり、engine との実行互換性を証明したりはしません。 |
| `import PATH --plan` | 既存 GGUF ファイル群を Strata の既知形式と照合 | 読み取り専用のプレビューです。採用、コピー、ダウンロード、修復、engine 起動は行いません。 |
| `move NEW_FOLDER` | models、packs、mtp のデータを別フォルダーへ移動 | ファイルを検証しながら移動し、関連する run config のパスも更新します。`--plan` はモデルファイルを移動せず計画を表示します。中断後は `--status`、`--resume`、`--leave` で状態を確認・処理できます。 |

## 主な動作と注意点

- `list` のローカル検索は設定ファイルを読む調査です。`--served` は現在の server instance のみを対象とし、導入済みモデル全体の一覧ではありません。`--served` と `--installed` は同時に指定できず、remote server 接続用の引数は `--served` と組み合わせる必要があります。
- `inspect` の `component_status: present` は必要ファイルの存在を示します。モデルの実ロードや backend 互換性は確認済みにならず、結果では互換性を未検証として扱います。
- `import` は `--plan` が必須です。これは採用操作ではなく、GGUF の形式や既知モデル候補を確認するためのプレビューです。プレビューに候補が出ても、その結果だけで実行互換性が確認されたことにはなりません。
- `move` は実際に実行すると保存先に書き込み、移動元ファイルを削除し、モデルファイルが移動済みの run config を更新します。同じドライブでは rename、別ドライブではコピーとして処理します。コピー経路ではサイズと SHA-256 を照合してから移動元を削除します。移動前に `--plan` で容量や保存先を確認してください。
- `move --plan` はモデルファイルを動かしませんが、保存先がまだない場合は書き込み可否を確かめるため保存先ディレクトリーを作成し、一時ファイルを書いて削除します。完全な読み取り専用確認ではありません。
- `move` の通常実行ではデータフォルダー内の `models`、`packs`、`mtp` が対象です。中断または失敗時は、完了したファイルは残り、未完了コピーは信頼されません。状態を見て `--resume` で続行するか `--leave` で中断移動を取り消します。

## 関連文書

- [モデル一覧 `strata models list`](list/README.md)
- [モデル検査 `strata models inspect`](inspect/README.md)
- [GGUF プレビュー `strata models import`](import/README.md)
- [モデルデータ移動 `strata models move`](move/README.md)
- [Terminal CLI の説明](../../../TERMINAL.md)
- [`strata launch` の概要](../launch/README.md)

## 根拠

- Strata `strata_cli/cli.py:141-171` — `models` のサブコマンド、引数、必須 `--plan`、一覧・検査・移動の parser 定義。
- Strata `strata_cli/cli.py:550-603` — `list` / `inspect` / `import` の処理、local と served の分岐、出力と一部エラー経路。
- Strata `strata_control/models.py:1-12,185-229,297-307` — run config の read-only 探索、一覧・検査結果の範囲、import プレビュー関連の読み取り専用動作。
- Strata `strata_cli/cli.py:617-660,668-705` — `move` の計画・実行・中断状態の処理、終了コードと出力。
- Strata `strata_control/models_move.py:1-12,123-132,137-184,223-258,379-440,478-524` — 対象データ、計画時の書き込み検査、コピー検証、run config 更新、移動状態と失敗処理。
- Strata `docs/TERMINAL.md:19-28` — 利用例、ローカル設定と served model の違い、互換性確認の限界、import プレビューの説明。

調査は記載した commit のソースと checkout 内の利用者向け文書に基づきます。別 revision の Release artifact や各 OS での実行結果は確認していません。
