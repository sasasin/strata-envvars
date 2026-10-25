# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `False` |

## 役割

モデル保管フォルダーの移動計画を表示し、ファイル移動を始めないためのフラグです。計画は `models`、`packs`、`mtp` 内のファイルを調べ、移動元・移動先、容量、空き容量、同一ドライブかどうか、移動可否を返します。

## 使い方

```sh
strata models move /mnt/storage/Strata --plan
```

既定の移動元は現在のデータフォルダーです。明示する場合は `--from OLD_FOLDER` を使います。

```sh
strata models move /mnt/storage/Strata --from ~/Strata --plan --output json
```

## 値と既定値

- parser は `action="store_true"` で、値を受け付けません。未指定なら計画処理を行わず通常の移動経路へ進みます（`strata_cli/cli.py:162-171`）。
- `NEW_FOLDER` は位置引数ですが省略可能な parser 定義です。ただし `--plan` の処理に入る前に必須扱いされ、未指定では stderr に移動先を指定するよう表示して終了コード `2` を返します（`strata_cli/cli.py:617-628`）。
- 移動元は `--from` の値、または `discovery.data_dir(Path.home() / "Strata")` で決まります。移動先は `Path(...).expanduser()` を通るため `~` が展開されます（`strata_cli/cli.py:617-626`）。
- `--output` の選択肢は `human`、`json`、`jsonl`、既定値は `human` です。また、この one-shot parser 群には共通処理で `--json` と `--quiet` も追加されます。`--json` は `--output json` に切り替えます（`strata_cli/cli.py:168-171,508-515,2232-2237`）。

## 実行時の動作

`--plan` が指定され、`--status` / `--resume` / `--leave` のいずれでもない場合、CLI は `strata_control.models_move.plan(old, new)` を呼び出し、計画を出力して終了します。この分岐では実際の移動関数 `mm.move` は呼び出しません（`strata_cli/cli.py:617-634`）。

計画関数は移動元の `models`、`packs`、`mtp` ディレクトリを走査し、`.part` で終わるファイルを除いてファイルサイズを集計します。同一ドライブなら必要空き容量を 0、別ドライブなら合計サイズの 105% とし、移動可能かを `choices.move.possible` に記録します。ファイルがない場合は移動不可ですが、計画自体の `ok` は真になり得ます（`strata_control/models_move.py:57-85,104-111,137-184`）。

- `human` は問題があればそのメッセージ、なければモデル数・合計サイズ・移動先の空き容量を表示します。
- `json` と `jsonl` はどちらも `{"schema_version": 1, "ok": ..., "plan": ...}` 形式の JSON オブジェクトを1件出力します。`ok` は計画の基本検査結果であり、個別の移動可否は `plan.choices.move.possible` を確認します（`strata_cli/cli.py:628-634`）。
- 問題がある計画は終了コード `5`、`ok` の計画は `0` です。human 出力では問題文を stdout に出し、終了コード `5` とします（`strata_cli/cli.py:628-634`）。

## 適用条件と副作用

このオプションは計画だけを表示し、`mm.move` が行うファイル移動や run config の書き換えには進みません。ただし完全な読み取り専用ではありません。

- `plan()` の既定 `write_test=True` により、移動先がまだなければ親ディレクトリも含めて作成し、移動先に `.strata-write-test` 接頭辞の一時ファイルを作成して削除します。したがって移動先への書き込み権限とディスク状態を確認します（`strata_control/models_move.py:123-133,137,161-169`）。
- `--from` を省略すると `discovery.data_dir()` が呼ばれ、その内部で `sync_data_dir()` が実行されます。Terminal と Desktop の設定が異なり、更新日時で勝った側を採用する条件では、古い側の設定ファイルを同期更新することがあります（`strata_cli/cli.py:617-621`; `strata_control/discovery.py:241-259,277-289`）。
- `--status`、`--resume`、`--leave` が同時指定された場合は `--plan` より先に未完了移動の処理へ分岐するため、計画表示になりません（`strata_cli/cli.py:621-622`）。
- `--cancel-file` と `--install-dir` は計画分岐より後でのみ参照されるため、`--plan` の評価には使われません（`strata_cli/cli.py:627-648`）。
- `--quiet` では成功時の human 出力は抑制されます。計画に issue があり終了コードが非 0 の場合、捕捉した出力は stderr に出されます。JSON/JSONL 出力は quiet 処理の対象外です（`strata_cli/cli.py:2236-2247`）。

## 出力とエラー

- 移動元と移動先が同一なら `same`、互いに内包し合うなら `inside`、移動先のドライブが見つからない場合は `not_found`、移動先に書き込めない場合は `not_writable` の issue を返します。いずれも計画の `ok` は偽になり、CLI の終了コードは `5` です（`strata_control/models_move.py:151-169`; `strata_cli/cli.py:628-634`）。
- 移動先の空き容量取得が `OSError` で失敗した場合は `free_bytes=0` として計画を続けます。別ドライブでファイルがある場合、移動可能性は通常偽となります（`strata_control/models_move.py:170-183`）。
- 移動先引数を省略した場合は終了コード `2`、未知の引数は argparse の usage/error 経路になります（`strata_cli/cli.py:623-625,2223-2231`）。

## 根拠

- parser、移動元の解決、`--plan` の出力分岐: `strata_cli/cli.py:162-171,617-634`
- 計画用 inventory、同一ドライブ判定、容量・可否計算: `strata_control/models_move.py:57-85,104-111,137-184`
- 移動先への書き込み確認と一時ファイル: `strata_control/models_move.py:123-133,161-169`
- 既定データフォルダーと設定同期: `strata_control/discovery.py:241-259,277-289`
- 共通 `--json` / `--quiet` 処理と parser error: `strata_cli/cli.py:508-515,2223-2247`
