# `strata drafting fetch --data-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--data-dir` |
| 別名 | なし |
| 値 | `DIR`。モデルデータ用フォルダーのパス文字列 |

## 役割

ダウンロードまたは既存ファイルの確認・packを行う場所を指定します。DFlash2 の tuned pack または標準 pack、語彙ファイルなどは、このフォルダー配下の `dflash2/` に置かれます。モデル・drafting mode など fetch 対象を決める設定は `--config` 等から別に決まり、このオプションは保存先を指定します（`terminal/strata_cli/drafting_cmd.py:101-120,241-246`、`terminal/strata_control/drafting.py:295,676-688`）。

## 使い方

```sh
strata drafting fetch --data-dir /mnt/models/Strata-data
```

## 値と既定値

- `DIR` は値を1つ取ります。parser は型変換や選択肢検査をせず文字列を受け取り、実行時に `Path(DIR)` にします。相対パスはプロセスの作業ディレクトリ基準となり、`~` の展開や絶対パス検査はこのコマンドでは行いません（`terminal/strata_cli/drafting_cmd.py:24-25,110-116`）。
- オプションを省略するか空文字列を渡した場合は、まず設定ファイルの engine 引数にある `--pack` / `--mtp` からデータフォルダーを推定し、推定できなければ Strata が選ぶ既定フォルダーを使います（`terminal/strata_cli/drafting_cmd.py:110-116`、`terminal/strata_control/drafting.py:1662-1671`、`terminal/strata_cli/launch/catalog.py:753-760`）。既定フォルダー選択では保存済み設定、Desktop app のフォルダー、モデルを含む Documents フォルダー、インストール場所近くの既定値の順に調べます（`terminal/strata_control/discovery.py:258-306`）。
- `--data-dir` を複数回指定したときの個別処理は実装されていません。argparse の通常の値引数として登録されています（`terminal/strata_cli/drafting_cmd.py:24-25`）。

## 実行時の動作

`DIR` が空でなければ、config から推定したフォルダーや既定フォルダーより優先して fetch 関数へ渡されます。`--config` が併用されていればその設定からモデル名・backend 等を読みますが、保存先は `DIR` になります（`terminal/strata_cli/drafting_cmd.py:101-120,240-246,281-283`）。config の `args` にある `--pack` または `--mtp` からの推定は、それらの引数のパス階層を使います（`terminal/strata_control/drafting.py:1662-1671`）。

fetch は対象モデル・backend に応じて tuned pack を試し、適用対象外または tuned pack を取得できず fallback する場合は標準 pack を使います。tuned pack はサイズ・SHA-256 を確認し、標準 pack は既存の利用可能なファイルを確認して再利用します。どちらも必要なら `DIR/dflash2/` 以下へ取得・packし、標準 pack の準備が正常完了すると一時ソースファイルを削除します。pack と語彙ファイル等の書き込み先は指定したフォルダーです（`terminal/strata_control/drafting_fetch.py:349-373,376-442`、`terminal/strata_control/drafting.py:295,669-727,823-827,1482-1503`）。

`--if-needed` と併用すると、現在の選択が drafter を使い、必要なファイルがまだない場合にだけ fetch します。不要な場合は「Nothing to download.」を出して終了し、ファイルを変更しません（`terminal/strata_cli/drafting_cmd.py:243-246,267-272`）。裸の `strata drafting fetch` では、DFlash2 対応モデルが1つだけインストール済みなら、そのモデルの run config を自動選択します。複数ある場合は `--model` または `--config` の指定が必要で、`--data-dir` だけでは選択を解決しません（`terminal/strata_cli/drafting_cmd.py:80-98,234-239`）。

このオプション自体は保存済みのデータフォルダー設定を書き換えません。指定先へのディレクトリ作成、ダウンロード、pack、ライセンス・通知ファイルや語彙ファイルの配置は fetch の通常の副作用です（`terminal/strata_cli/drafting_cmd.py:110-116,281-283`、`terminal/strata_control/drafting_fetch.py:323-346,397-442`）。

## 適用条件と副作用

- `strata drafting plan` にも同じ parser ループで登録されますが、plan は取得内容を表示するだけで変更を行いません。この文書の対象は `fetch` です（`terminal/strata_cli/drafting_cmd.py:19-38`）。
- fetch に専用のフォルダー validation はありません。パスが書き込み不可、または作成できない場合はファイル操作が失敗し、未処理の `OSError` は CLI 共通処理でエラー表示・終了コード `6` になります（`terminal/strata_control/drafting_fetch.py:323-326,397-405`、`terminal/strata_cli/cli.py:2258-2265`）。
- 明示した `--data-dir` は設定に記憶されず、既存モデル・設定を移動しません。tuned pack は pinned size と SHA-256 を照合し、標準 pack は pack path 上に利用可能なファイルがあるかを確認して再利用します。取得が必要ならネットワークを使います（`terminal/strata_control/drafting_fetch.py:349-387`、`terminal/strata_control/drafting.py:669-727,823-827`）。

## 出力とエラー

通常の成功時は進捗を表示し、最後に作成・利用した pack のパスを表示します。`--output json` / `jsonl` では結果を JSON、進捗を JSONL event として出力します（`terminal/strata_cli/drafting_cmd.py:274-305`）。取得・検査・pack の `DraftingError` や `AcquisitionRefused` は stderr（machine 出力時は JSON）に表示し、終了コード `5` です。ネットワーク不通、チェックサム不一致、中断などがこの経路に含まれます（`terminal/strata_control/drafting_fetch.py:30-37,328-342,405-431`、`terminal/strata_cli/drafting_cmd.py:290-301`）。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `plan` と `fetch` に共通する parser 登録。`DIR` の metavar と他 option とのスコープ。
- `terminal/strata_cli/drafting_cmd.py:101-120` — 明示値、config 内の engine 引数、Strata の既定値の優先順。
- `terminal/strata_cli/drafting_cmd.py:234-246,267-305` — 複数モデル時の拒否、必要性判定、fetch 呼び出し、出力とエラー終了コード。
- `terminal/strata_control/drafting.py:1662-1671`、`terminal/strata_cli/launch/catalog.py:753-760`、`terminal/strata_control/discovery.py:258-306` — config 引数からのフォルダー推定と既定フォルダー選択。
- `terminal/strata_control/drafting_fetch.py:349-442`、`terminal/strata_control/drafting.py:295,676-688,1482-1503` — tuned / 標準 pack の選択、指定先への書き込み、再利用・検査・一時ファイル削除。
- `terminal/strata_cli/cli.py:2258-2265` — ファイル操作の `OSError` に対する CLI 共通エラー処理。
