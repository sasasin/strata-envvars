# `strata launch --move-data`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--move-data` |
| 値 | なし（`store_true`） |
| 既定値 | 無効 |

## 役割

`--data-dir DIR` で新しいモデルデータフォルダーを指定したとき、すでに Strata が利用しているモデルファイルをそのフォルダーへ移すよう指定します。対象は `strata launch` の parser です。ソース checkout は POSIX/Windows の共通 Python CLI 実装で、launch 処理は `setup.py` に引数を渡します（`strata_cli/launch/cmd.py:91-94`、`strata_cli/launch/runner.py:742-748,948-959`）。

```sh
strata launch --model q2_0 --data-dir /mnt/strata-models --move-data --no-tui
```

この例はモデル起動時にデータ先を指定し、移動を要求します。実際に移るファイルや、移せず元の場所に残るファイルは、setup.py が見つけたフォルダーとファイルの状態によります。

## 値と validation

値を取らない真偽フラグです。引数 parser に、移動先の検証や `--data-dir` との必須組み合わせ検証はありません（`strata_cli/launch/cmd.py:91-94`）。`--move-data` 単独では移動指示になりません。launch は `--data-dir` がないと選択を `False` にし、runner も `s.data_dir` がある場合だけ setup.py の引数へ `--move-data` を加えます（`strata_cli/launch/cmd.py:504-510`、`strata_cli/launch/runner.py:742-748`）。

## 実行時の動作

- `--data-dir` があり `--move-data` を指定すると、launch は移動選択を有効にして setup.py に `--data-dir DIR --move-data` を渡します。新しい data dir はさらに既定先として記憶するよう `--set-default-data-dir` も渡されます（`strata_cli/launch/cmd.py:509-510,731-732`、`strata_cli/launch/runner.py:742-748`）。
- `--move-data` を省略しても、対話可能な通常実行では移動可能な既存ライブラリがある場合に選択を尋ねます。`--yes`、machine/JSON モード、`--plan` では移動を選ばず、`--no-tui` または stdin が TTY でない実行でも移動確認はせず、旧フォルダーを保持する旨を表示します（`strata_cli/launch/cmd.py:504-526`）。
- setup.py は現在の Strata フォルダー、記録済みの他の Strata インストール、設定済みの data dir とその中の `Strata-data` などを候補にし、同一ドライブ上のデータを移動対象として扱います。モデルファイルは既存ファイルを残しながらファイル単位で統合し、`packs` 内の pack と `mtp` は移動先に同名のものがない場合に移動します。関連する model config のパスも、ファイルが新しい場所にあり旧場所にない場合に更新します（`setup.py:6068-6129`、同一ドライブ判定 `setup.py:5965-5969`、移動処理 `setup.py:5972-5991`、config 更新 `setup.py:5993-6015`）。
- データが見つからない場合、setup.py は新しい data dir を既定先として記録します。指定先が別ドライブのフォルダーにあるファイルは移動せず、その場所のまま利用できるフォルダーとして扱います（`setup.py:6097-6109,6130-6133`）。

## 適用条件と副作用

- 効果があるのは `strata launch` が `--data-dir` を設定として持つ場合です。`--move-data` だけを指定しても、既定の data dir を移動先として自動採用しません（`strata_cli/launch/cmd.py:507-510`、`strata_cli/launch/runner.py:742-748`）。
- 移動対象は setup.py が探索した場所の `models`、`packs`、`mtp` です。別ドライブのデータや移動後も旧フォルダーに残るデータは旧場所に残ります。ファイルが使用中などで移動できない場合も元に残り、setup.py は残存データがある旨を警告します（`setup.py:6110-6129`）。
- setup.py は指定先の検査後、ディレクトリーを作成し、移動・config 更新・設定保存を行います。指定先が不正なら「何もダウンロードまたは変更せず、data folder として保存しなかった」と案内して失敗します（`setup.py:6053-6065`）。移動処理は同一ドライブでの rename を試し、ディレクトリーのときは既存先と統合します（`setup.py:5972-5991`）。
- `--plan` は launch 内で計画を表示して終了するため、setup.py による移動は実行されません（`strata_cli/launch/cmd.py:731-760`）。

## 出力とエラー

移動を確認する通常の対話実行では、移動元とおおよそのサイズ、移動先が提示されます。`--no-tui` または入力できない実行で明示指定がない場合は、旧場所にモデルを保持し、新しいフォルダーを新規ダウンロード用にする旨を表示します（`strata_cli/launch/cmd.py:520-526`、表示文 `strata_cli/launch/library.py:51-66`）。

setup.py の失敗は `[X]` 行とヒントを表示し、setup を停止して終了コード 1 になります（`setup.py:825-830`）。launch は setup.py の非ゼロ終了を `LaunchError` に変換し、CLI のエラー経路から表示します（`strata_cli/launch/runner.py:997-1012`、`strata_cli/launch/cmd.py:784-787`）。移動時の具体的な OS エラーごとの出力は、ソースから一律には確認できません。

## 根拠

- `strata_cli/launch/cmd.py:75-94` — `launch` parser と `--move-data` 定義。
- `strata_cli/launch/cmd.py:504-526,731-760` — 適用条件、対話確認、計画モード。
- `strata_cli/launch/runner.py:742-748,948-959,997-1012` — setup.py への引き渡しと失敗処理。
- `strata_cli/launch/library.py:1-5,35-66` — launch 側のライブラリ検出と対話選択。
- `setup.py:5965-5991,6042-6150` — 同一ドライブ判定、ファイル移動、data dir と設定の更新。
- 作成先リポジトリ `docs/cli/README.md:925-968` — `strata launch` のスコープと指定リンクの照合（Strata ソースではなく、文書配置の根拠）。

## 調査範囲

指定 commit の checkout にあるソースを確認しました。別 OS 上での実ファイル移動、権限・ロック状態ごとの例外、配布済み CLI とこの checkout の一致は実行確認していません。CLI の help、build、テスト、GPU 実行は行っていません。
