# `strata drafting plan --data-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されませんでした。

## 概要

`--data-dir DIR` は、`strata drafting plan` が DFlash2 drafter の pack を確認し、ダウンロード計画を表示する際のモデル data folder を指定します。対象 pack は `<DIR>/dflash2/qwen3.8-flash-next-dflash2.q8.pack` です（`strata_cli/drafting_cmd.py:47-54`、`strata_control/drafting.py:98-100,114-120`）。

```sh
strata drafting plan --data-dir /srv/strata-data
```

## 値と既定値

- 値は `DIR` です。parser は文字列を受け取り、値の形式・絶対パス性・存在を検証しません。実装は `Path(a.data_dir)` に変換して使います（`strata_cli/drafting_cmd.py:23-24,47-49`）。
- `--data-dir` を省略すると、まず `--config` の `args` から `--pack` または `--mtp` のパスを探して data folder を推定します。見つからない場合は `Catalog().data_dir()` の結果を使います（`strata_cli/drafting_cmd.py:40-54`、`strata_control/drafting.py:203-212`）。
- 明示した `--data-dir` は config 由来の folder より優先されます（`strata_cli/drafting_cmd.py:47-54`）。`~` 展開や相対パスの絶対化はこの処理にはありません。相対パスは実行時の作業ディレクトリ基準で扱われます。

## 動作と相互作用

コマンドは指定 folder の pack がファイルとして存在し、サイズが 1 MiB を超えるかを調べます。`--data-dir` 自体を作成したり、pack をダウンロード・変更したりはしません（`strata_control/drafting.py:114-120`、`strata_control/drafting_fetch.py:29-39`）。明示した `--data-dir` があると既定 folder のための `Catalog` 初期化を通らないため、そこでの install root 作成も行われません。省略時に config から folder を得られず `Catalog` を初期化する場合は、`self.root.mkdir(..., exist_ok=True)` により install root が作成されることがあります（`strata_cli/drafting_cmd.py:47-54`、`strata_cli/launch/catalog.py:223-233`）。

`--config` はモデルの run config を読み込み、`--mode` はその config の `drafting` 設定を上書きして判定に使います。`--data-dir` が指定されていれば、config の `args` に記録された pack/MTP の場所は data folder の選択に使われません（`strata_cli/drafting_cmd.py:40-54,60-68`）。config が読めない、または JSON として不正な場合、読み込み例外は空 config として扱われます。その場合 `--data-dir` もなければ既定 folder にフォールバックします（`strata_cli/drafting_cmd.py:40-54`）。

pack の確認に失敗した場合は未準備として計画されます。`pack_ready` は `OSError` を捕捉して `False` を返します（`strata_control/drafting.py:118-122`）。現在のソースでは `ENGINE_SERVES_DFLASH2 = False` であり、DFlash2 を serve できません。`needed` は常に偽となり、明示した `--config` または `--mode` があり `needed` が偽なら JSON 結果の `gb` は `0.0` に設定されます（`strata_control/drafting.py:141-146,179-184`、`strata_cli/drafting_cmd.py:62-68`）。

## 出力と失敗経路

`plan` は終了コード 0 で、既定の human 出力では download plan の説明、または判断理由があれば drafting の要約行を標準出力に表示します。`--output json` / `jsonl` では `schema_version: 1` と計画情報を含む JSON を1行出力します（`strata_cli/drafting_cmd.py:29,57-73`）。このコマンドでは `jsonl` も `machine` 出力として扱われ、plan の結果は JSON 1行です（同 `:57-73`）。

`--data-dir` の値自体に対する独自エラー処理はありません。parser の `--mode` / `--output` 選択肢が不正な場合は argparse が拒否します（`strata_cli/drafting_cmd.py:23-29`）。省略時の `Catalog().data_dir()` 初期化では、Terminal に model list がない場合などに `CatalogUnavailable` となり得ます（`strata_cli/launch/catalog.py:223-232`）。

## 関連文書

- [`strata drafting plan` のコマンド概要](README.md)
- [`strata drafting fetch --data-dir`](../../fetch/--data-dir.md)

根拠は上記の Strata ソース位置です。CLI の実行や `--help` 表示は行っていません。
