# `strata components install-file --model-config`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`。モデルの run config JSON ファイルのパス。 |

## 役割

ローカルのエンジンパッケージをインストールするとき、切り替え前の試験起動で使うモデル設定を指定する。指定しない場合は、このエンジンコンポーネントに適合するインストール済みモデルの設定を探す。パッケージの署名検証や適合性判定には使われない。

## 使い方

```sh
# この run config のモデルで、ローカルのエンジンパッケージを試験起動してから導入する
strata components install-file ./engine-package.tar.gz --model-config ./model-run.json
```

## 値と既定値

- `terminal/strata_cli/update_cmd.py:54-56` では値を取る引数として登録され、`metavar` は `RUN_CONFIG.json`、既定値は `None`。型変換やパーサ段階でのファイル存在・JSON 内容の検証は定義されていない。
- 値は `Path` に変換され、試験起動で読み込まれる。明示値が空文字列なら `Context.run_config` が偽値となるため、未指定時と同じ自動検出経路に進む（`terminal/strata_cli/update_cmd.py:319-321`、`terminal/strata_control/updater.py:1342-1348`）。
- 同じ共通 parser は `components update`、`rollback`、`engines`、`use`、`remove`、`add-build` にもこの引数を登録するが、この文書の対象は `install-file`。`install-file` の処理では試験起動に限って参照される（`terminal/strata_cli/update_cmd.py:47-56, 92-98, 341-345`）。

## 実行時の動作

CLI は値を `updater.Context.run_config` に渡し、`install_engine_file` がパッケージを検証した後、共通の導入処理 `_finish_engine_install` を呼ぶ。ここで行われる試験起動が `default_test_start` を使い、指定値があればそのパスを設定元として選ぶ（`terminal/strata_cli/update_cmd.py:319-321, 341-345`、`terminal/strata_control/updater.py:1638-1641, 1692-1695, 1538-1550, 1342-1348`）。

設定ファイルから JSON を読み、設定内の Control パスを補正し、実行パスを解決してから、試験対象エンジンの component ID・backend に合わせて設定を組み立てる。引数がリストなら試験用に軽量化し、隔離された runtime・profile・components ディレクトリでモデルを起動して一 token の応答を確認する。成功後は試験用 runtime を停止し、新エンジンへ切り替える（`terminal/strata_control/updater.py:1355-1376, 1392-1419, 1545-1550, 1567-1627`）。

指定した run config が別の engine component を対象にしている場合、その設定を試験に使わず、対象 component に合うインストール済み設定を改めて検出する。指定値がない場合も同じ検出関数を使い、存在する設定のうち保存済み profile が参照するものを優先し、それ以外はモデル ID 順で選ぶ。該当設定がなければ、既定ではモデルをロードせずバイナリの smoke check に進む（`terminal/strata_control/updater.py:899-920, 1346-1354`）。

## 適用条件と副作用

- `--model-config` が影響するのは、署名・全ファイル検証と PC 適合性確認を通過し、パッケージが現在のエンジンより新しい（または `--force` が指定されている）ため、実際の導入・試験起動へ進む場合。パッケージのバージョンが既存エンジンより古く `--force` もない場合は、試験起動をせず何も変更しない（`terminal/strata_control/updater.py:1688-1695`）。
- 試験起動は隔離領域内で行われ、設定の `host`、`port`、`log` をローカル試験用に差し替える。設定ファイル自体は読み込み元として扱われ、書き換えない。明示したパスが別 component 向けなら自動検出へ切り替える（`terminal/strata_control/updater.py:1346-1376, 1392-1403`）。
- `install-file` はネットワークから取得せず、選択したアーカイブも削除しない。成功時にはコンポーネント状態・履歴などを更新し、新エンジンを次回起動から使用する。失敗した試験起動では旧エンジンは維持され、試験ログと失敗記録が保存される（`terminal/strata_control/updater.py:1638-1641, 1550-1566, 1616-1627`）。
- 試験対象モデルのロードに必要な RAM が不足すると、未検証モデル起動を許さない再試行状態でない限り、モデルをロードしない binary smoke check へ切り替わる。この場合、新エンジンは `unproven` として記録され、実際のモデル起動は後続の通常起動時になる（`terminal/strata_control/updater.py:1377-1391, 1604-1610`）。
- エンジンが serving 中なら、`--wait` がなければ対話端末では待機確認が行われ、非対話または JSON 出力では待たずに busy エラーとなる。これは `--model-config` による試験起動前の条件である（`terminal/strata_cli/update_cmd.py:500-515`）。

## 出力とエラー

- パッケージ検証や PC 適合性の失敗は `UpdateError` となり、通常出力では `strata: ...` を stderr に出す。JSON / JSONL 出力では `ok: false` と error code / message を JSON で出す（`terminal/strata_cli/update_cmd.py:303-312, 341-350`）。
- 指定した設定ファイルの読み込み失敗や不正 JSON は、`default_test_start` 内で `TestStartFailed` に変換されず CLI の一般エラー処理へ伝播する。`OSError` は終了コード 6、`ValueError`（JSON decode error を含む）は既定の終了コード 2 で処理される。いずれもエンジン切替より前に起きるため、新エンジンは切り替わらない（`terminal/strata_control/updater.py:1355-1358, 1433-1434`、`terminal/strata_cli/cli.py:2248-2265`）。設定が読み込めた後の試験起動失敗は `TestStartFailed`（終了コード 6）になり、旧エンジンは維持される（`terminal/strata_control/updater.py:1405-1427, 86-88, 125-134, 1545-1566`）。
- CLI の `UpdateError` 失敗出力は通常 stderr の `strata: ...`、JSON / JSONL 時は JSON error object（`terminal/strata_cli/update_cmd.py:303-312, 374-378`）。パッケージ形式・署名・適合性などの拒否は通常終了コード 5、起動中モデルとの競合は 7。`--model-config` 固有の parser validation error は定義されていない（`terminal/strata_control/updater.py:72-83, 1630-1635, 1642-1682`）。
- 起動中モデルとの競合は終了コード 7、パッケージ形式・署名・適合性などの拒否は通常終了コード 5。`--model-config` 固有の parser validation error は定義されていない（`terminal/strata_control/updater.py:72-83, 1630-1635, 1642-1682`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56, 92-98`: 共通 option parser と `install-file` の位置引数・option scope。
- `terminal/strata_cli/update_cmd.py:319-321, 341-350`: 値の `Context` への受け渡しと install-file の実行・出力。
- `terminal/strata_control/updater.py:899-920, 1342-1354`: 明示設定と自動検出、component 不一致時の再検出、設定がない場合の smoke check。
- `terminal/strata_control/updater.py:1355-1419`: 設定の読み込み、補正、隔離環境でのモデル試験起動。
- `terminal/strata_control/updater.py:1538-1566, 1567-1627`: 試験起動の失敗処理、エンジン切替、状態記録と副作用。
- `terminal/strata_control/updater.py:1638-1698`: ローカルパッケージの検証、バージョン条件、試験起動への引き渡し。アーカイブは利用者が選んだ場所に残す。
- `terminal/strata_control/updater.py:86-88, 125-134`、`terminal/strata_cli/cli.py:2248-2265`: 試験起動失敗と設定読み込み時例外の終了コード・エラー処理。
