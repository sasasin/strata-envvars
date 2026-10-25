# `--resume`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--resume` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定時に中断したモデルフォルダー移動を完了する |

## 役割

以前の `strata models move NEW_FOLDER` が停止または失敗し、移動元フォルダーに中断状態が残っているとき、その移動を続けます。移動先は中断状態から復元するため、`NEW_FOLDER` の位置引数は省略します（`strata_cli/cli.py:162-165, 668-705`）。

## 使い方

```sh
strata models move --resume
```

別の移動元を明示する場合は `--from OLD_FOLDER` を指定します。設置済み Strata の run config の探索先を限定する場合は `--install-dir INSTALL_FOLDER` を追加できます（`strata_cli/cli.py:167-171, 685-705`）。

## 値と既定値

- `--resume` は `action="store_true"` で、値も短縮別名もありません。オプション自体の入力値 validation はありません（`strata_cli/cli.py:162-171`）。
- `--from` を省略すると `discovery.data_dir(Path.home() / "Strata")[0]` が移動元になります。これは設定、アプリのデータフォルダー、モデルを含む Documents/Strata、既定フォルダーを調べて選ぶ処理です（`strata_cli/cli.py:617-622`; `strata_control/discovery.py:277-289`）。
- 中断状態に記録された移動元が、選択した移動元と一致しない場合はその状態を採用しません。復元先も保存済み状態の `to` から設定されます（`strata_cli/cli.py:668-672, 704-705`; `strata_control/models_move.py:303-325`）。

## 実行時の動作

1. CLI は選択した移動元の `models-move.json` を読み、中断状態を確認します。状態が `running`、`stopped`、`failed` のいずれかで `from` / `to` があり、保存された `from` が選択中の移動元と一致する必要があります。プロセス識別情報から同じ実行中プロセスと確認できる `running` 状態は中断扱いにしません（`strata_control/models_move.py:268-272, 303-325`）。
2. 状態がなければ「中断した移動はない」として終了コード 5 を返します（`strata_cli/cli.py:679-684`）。状態があれば、保存済みの `to` と `from` を引数に設定し直し、通常の移動処理を呼びます（`strata_cli/cli.py:685-705`）。
3. 通常処理は移動元に残る `models`、`packs`、`mtp` のファイルを再走査します。別ドライブへの移動では、残りの各ファイルを `.part` にコピーしてサイズと SHA-256 を照合し、必要なら `.done` 内の pin hash も確認してから配置し、移動元を削除します。中断時に残った `.part` は信頼せず削除します。同一ドライブでは rename になります（`strata_control/models_move.py:66-85, 223-259, 379-400, 441-501`）。
4. 移動状態は `models-move.json` として移動元・移動先の双方に保存されます。成功時は両方の状態ファイルを削除します。部分的に移動した状態で停止・失敗すると、状態を残して次回の resume に使います（`strata_control/models_move.py:275-293, 407-417, 508-531`）。
5. `--install-dir` があればそのインストール先の `strata-*.json` run config を対象にし、省略時は見つかった全 install の config を対象にします。モデルの全ファイルが移動先に揃い、元のパスには存在しない場合、config 内のパスを更新します（`strata_cli/cli.py:685-705`; `strata_control/models_move.py:328-365, 434-439, 504-507`）。

## 適用条件と副作用

- 移動元に有効な中断状態が必要です。保存状態はデータフォルダー内の `models-move.json` にあり、移動先にもポインターとして書かれます。現在動作中と判定される移動は resume 対象になりません（`strata_control/models_move.py:284-325, 407-417`）。
- この操作は読み取り専用ではありません。残存モデルファイルを移動し、移動先に残っている `.part` を消し、完了したモデルの run config を更新します。移動全体が終わると状態ファイルも削除します（`strata_control/models_move.py:395-400, 434-439, 498-510`）。
- `--cancel-file PATH` を併用すると、そのファイルが存在する間に安全停止します。`--resume` のみを指定した場合はキャンセルファイルによる停止判定は設定されません（`strata_cli/cli.py:170, 640-648`; `strata_control/models_move.py:387-400, 441-445`）。
- `--output` は `human`（既定）、`json`、`jsonl` を選べます。`--json` は one-shot コマンドで `--output json` の別表記です（`strata_cli/cli.py:171, 508-514, 671, 699-705`; `strata_cli/cli.py:2232-2236`）。`jsonl` は進捗イベントと最後の結果イベントを出し、`json` は結果 JSON を出します。human 形式では進捗行と完了メッセージを表示します（`strata_cli/cli.py:642-660`）。

## 相互作用とエラー

- `--status` と同時指定すると、`_models_move_unfinished` 内で status の分岐が先に実行され、状態表示だけで終了します。`--leave` と同時指定した場合は `leave` 分岐が実行され、resume は行いません（`strata_cli/cli.py:621-622, 668-705`）。
- `--plan` を併用すると、中断状態から元・先を復元した後、通常処理の plan 分岐に入ります。移動は行われません（`strata_cli/cli.py:627-634, 704-705`）。`--resume` とこれらのフラグを排他にする parser validation はありません（`strata_cli/cli.py:162-171`）。
- parser 上 `NEW_FOLDER` は任意ですが、`--resume`、`--leave`、`--status` のいずれも指定せず移動先も省略した場合は usage ではなく stderr に案内を出し、終了コード 2 で終わります（`strata_cli/cli.py:163, 621-625`）。
- 移動処理の `MoveError` は human 形式では stderr に `strata:` 付きで表示され、JSON/JSONL では `ok: false` とエラー情報を含む JSON が出て、終了コード 5 になります。ディスク不足、読み書き失敗、検証失敗などがこの経路です（`strata_control/models_move.py:35-42, 388-394, 522-531`; `strata_cli/cli.py:648-660`）。
- キャンセルによる停止は成功扱いの完了とは区別され、結果の `done` は false、human 出力は「Moving stopped. Nothing was lost.」、終了コードは 6 です。部分移動があれば中断状態が残ります（`strata_control/models_move.py:512-521`; `strata_cli/cli.py:656-660`）。

## 根拠

- parser とオプション scope: `strata_cli/cli.py:141-171`。
- `--resume` の分岐、状態なしの場合、復元後の再呼び出し、出力・終了コード: `strata_cli/cli.py:617-705`。
- 中断状態の保存・読込・判定: `strata_control/models_move.py:268-325, 407-417, 508-531`。
- 再開時のファイル走査、検証済みコピー、削除、config 更新: `strata_control/models_move.py:66-85, 223-259, 328-365, 379-400, 434-531`。
- 既定のデータフォルダー選択: `strata_control/discovery.py:277-289`。

調査範囲は上記 commit の checkout 内の parser・実装・関連資料です。OS ごとの filesystem 動作差および各種 I/O 失敗の実機再現は行っていません。CLI help の実行、build、テスト、GPU 実行、性能測定も行っていません。
