# `--from`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--from` |
| 別名 | なし |
| 値 | `OLD_FOLDER`。移動元データフォルダーのパス |

## 役割

モデルデータの移動元フォルダーを指定します。対象はその直下にある `models`、`packs`、`mtp` フォルダー内のファイルです。省略すると Terminal が現在使うデータフォルダーを解決します。

## 使い方

```sh
strata models move --from /srv/strata-data /mnt/storage/strata-data --plan
```

`--plan` を外すと移動を実行します。パーサー上は `NEW_FOLDER` が位置引数で、`--from` の値はそれとは別に指定します。

## 値と既定値

- 値は必須の `OLD_FOLDER` です。`argparse` に型変換、選択肢、存在確認などの parser validation はありません。値は `Path(a.source)` に渡されます。相対パスはプロセスの作業ディレクトリー基準で解釈され、`--from` の値には `expanduser()` が呼ばれないため `~` はホームディレクトリーに展開されません。
- 省略時は `discovery.data_dir(Path.home() / "Strata")[0]` が移動元になります。解決順は Terminal と Desktop の設定を同期した後、設定値、存在する Desktop 側フォルダー、モデルを含む `Documents/Strata`、最後に `~/Strata` です。
- `--status` / `--resume` / `--leave` と併用した場合も、まずこの移動元（または省略時の既定フォルダー）で中断状態を検索します。該当状態があれば、`--resume` は保存された移動元・移動先を使って再開し、`--leave` は保存状態を元に部分コピーを片付けます。
- 指定値について明示的な「既存ディレクトリーであること」の検査はありません。移動計画はそのパスをディレクトリーとして走査し、対象ファイルがなければ空の一覧になります。

## 実行時の動作

通常実行では `--from` のパスと `NEW_FOLDER` を `models_move.move(old, new, ...)` に渡します。走査対象は `models` / `packs` / `mtp` という名前（大文字小文字を無視）のサブディレクトリーで、`.part` ファイルは一覧から除外されます。

`--plan` を併用すると実際の移動を行わず、対象モデル・容量・移動先の空き容量を表示します。計画時と実行時に、移動先が同じフォルダー、移動元または移動先の内側、移動先ドライブがない、移動先へ書き込めない、といった状態を検査します。同一ボリュームなら rename、別ボリュームならコピーになります。別ボリュームでは移動先にデータ総量の 1.05 倍を必要容量として見積もります。

別ボリュームへのコピーでは一時 `.part` ファイルを作り、サイズと SHA-256 を照合し、該当ファイルに `.done` の pinned SHA-256 があればそれとも照合してから移動先へ置き、移動元を削除します。移動済みファイルを含むモデルの run config は、ファイルが移動先に存在し移動元には存在しなくなったパスに限って更新されます。中断・失敗に備え、状態ファイル `models-move.json` を移動元と移動先に記録します。

なお、`--from` を省略した場合の既定値解決は `discovery.data_dir()` を呼びます。この関数は Terminal と Desktop の設定が異なる場合、変更時刻が新しい側の値をもう一方の設定ファイルへ同期することがあります。

## 適用条件と副作用

- `--from` 自体は移動元の選択だけを行い、単独でファイルを動かしません。移動は `NEW_FOLDER` を指定して通常実行したときに行います。
- 設定ファイル内の既定データフォルダーは `--from` を指定すると移動元選択に使われません。ただし `--install-dir` を省略した場合は、実行時に検出された全 install の `strata-*.json` run config（`.shared-settings.json` を除く）が移動先パス更新の候補になります。
- `--plan` は読み取り専用の計画表示ですが、移動先に対する書き込み可能性検査としてフォルダー作成と一時ファイルの作成・削除を行います。そのため移動先が未作成でも作成されることがあります。
- 中断時は現在コピー中の `.part` を破棄し、すでに移動したファイルはそのまま残します。`--cancel-file PATH` を指定すると、そのファイルが存在するかを処理中に確認して停止します。
- このオプションと `--resume` / `--leave` / `--status` の組み合わせは相互排他になっていません。複数指定時は実装上 `--status`、次に `--resume` / `--leave` の分岐で処理され、`--status` が優先します。

## 出力とエラー

- 出力形式の既定値は `--output human` です。`--output json` または共通追加オプション `--json` は JSON を出力し、`--output jsonl` は進捗イベントを JSON Lines で出力します。人向けの通常移動では進捗行を表示します。
- 通常の移動エラーは stderr に `strata: ...` を出し終了コード 5 です。JSON / JSONL モードではエラーオブジェクトを出力します。移動中に停止した場合は成功扱いの結果形式で `done: false` を返し、終了コード 6 です。
- 移動先が未指定で、`--resume` / `--leave` / `--status` もない場合は stderr に使い方を示すエラーを出し、終了コード 2 です。中断状態がない状態で `--resume` または `--leave` を使うと終了コード 5 です。
- 明示した移動元が存在しない、または対象サブフォルダーにファイルがない場合、そのことだけでは専用エラーになりません。対象ゼロ件の計画は「移動できるモデルなし」となり、通常実行では空の移動として完了し得ます。

## 根拠

- Parser 定義、`--from` の `source` への格納、位置引数・関連オプション: `strata_cli/cli.py:162-171`。
- 共通 `--json` の追加: `strata_cli/cli.py:508-514`。
- 既定移動元、`--status` / `--resume` / `--leave` 分岐、計画・実行呼び出し、出力と終了コード: `strata_cli/cli.py:617-660`、未完了移動処理: `strata_cli/cli.py:668-705`。
- 既定データフォルダーの解決と設定同期: `strata_control/discovery.py:241-259`、`strata_control/discovery.py:277-289`。
- 対象サブフォルダー、`.part` 除外: `strata_control/models_move.py:29-32`、`strata_control/models_move.py:64-85`。
- 計画のパス検査・書き込み検査・空き容量・空リスト扱い: `strata_control/models_move.py:123-184`。
- コピー検証: `strata_control/models_move.py:223-258`。状態記録と移動・中断・失敗処理: `strata_control/models_move.py:284-293`、`strata_control/models_move.py:379-532`。
- Run config の更新と対象一覧: `strata_control/models_move.py:328-365`。

調査範囲は上記 checkout の Terminal parser、dispatch、および呼び出されるデータ移動処理です。安全な既存 CLI の `--help` は実行せず、parser 定義を確認しました。別 OS での実行や配布済み Release artifact の挙動は検証していません。
